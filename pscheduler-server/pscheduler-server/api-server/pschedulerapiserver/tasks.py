#
# Task-Related Pages
#

import pscheduler
import urlparse

# HACK: BWCTLBC
import os

from pschedulerapiserver import application

from flask import request

from .access import *
from .dbcursor import dbcursor_query
from .json import *
from .limitproc import *
from .log import log
from .response import *
from .util import *


class TaskPostingException(Exception):
    """This is used internally when some phase of task posting fails."""
    pass


def task_exists(task):
    """Determine if a task exists by its UUID"""
    try:
        cursor = dbcursor_query("SELECT EXISTS (SELECT * FROM task WHERE uuid = %s)",
                                [task], onerow=True)
    except Exception as ex:
        return error(str(ex))

    return cursor.fetchone()[0]
    


def pick_tool(lists, pick_from=None):
    """Count and score the number of times each tool appears in a list
    of lists retrieved from servers, then return the name of the tool
    that was preferred or None if there were none in common.  (Not to
    be used outside this module.)"""

    participants = len(lists)

    # The count is used to determine whether or not a tool is supported
    # by all participants.

    # The score is the sum of each tool's position in each list and is
    # used to determine its overall preference.  Like golf, the tool
    # with the smallest score has the highest preference.

    # TODO: At some point, we'll have to account for minimum schema
    # version supported, too.  (Or will hosts that don't support it just
    # bow out?)

    count = {}
    score = {}

    for tool_list in lists:

        if tool_list is None:
            continue

        for position in range(len(tool_list)):

            tool = tool_list[position]['name']

            try:
                count[tool] += 1
            except KeyError:
                count[tool] = 1

            try:
                score[tool] += position
            except KeyError:
                score[tool] = position

    # Pick out the tools all lists have in common and their scores.

    common = {}
    for tool in count:
        if count[tool] == participants:
            common[tool] = score[tool]

    # Nothing in common means no thing can be picked.
    if not len(common):
        return None

    if pick_from is None:

        # Take the tool with the lowest score.
        ordered = sorted(common.items(), key=lambda value: value[1])
        return ordered[0][0]

    else:

        # Find the first tool in the pick list that matches
        for candidate in pick_from:
            if candidate in common:
                return candidate

    # If we got here, nothing matched.
    return None




@application.route("/tasks", methods=['GET', 'POST'])
def tasks():

    if request.method == 'GET':

        expanded = is_expanded()

        query = """
            SELECT json, uuid
            FROM task
            """
        args = []

        try:
            json_query = arg_json("json")
        except ValueError as ex:
            return bad_request(str(ex))

        if json_query is not None:
            query += "WHERE json @> %s"
            args.append(request.args.get("json"))

        query += " ORDER BY added"

        try:
            cursor = dbcursor_query(query, args)
        except Exception as ex:
            return error(str(ex))

        result = []
        for row in cursor:
            url = base_url(row[1])
            if not expanded:
                result.append(url)
                continue
            row[0]['href'] = url
            result.append(row[0])
        return json_response(result)

    elif request.method == 'POST':

        try:
            task = pscheduler.json_load(request.data)
        except ValueError:
            return bad_request("Invalid JSON:" + request.data)

        # TODO: Validate the JSON against a TaskSpecification


        # See if the task spec is valid

        try:
            returncode, stdout, stderr = pscheduler.run_program(
                [ "pscheduler", "internal", "invoke", "test",
                  task['test']['type'], "spec-is-valid" ],
                stdin = pscheduler.json_dump(task['test']['spec'])
                )

            if returncode != 0:
                return bad_request("Invalid test specification: " + stderr)
        except Exception as ex:
            return error("Unable to validate test spec: " + str(ex))

        log.debug("Validated test: %s", pscheduler.json_dump(task['test']))

        # Find the participants

        try:

            # HACK: BWCTLBC
            if "lead-bind" in task:
                lead_bind_env = {
                    "PSCHEDULER_LEAD_BIND_HACK": task["lead-bind"]
                }
            else:
                lead_bind_env = None


            returncode, stdout, stderr = pscheduler.run_program(
                [ "pscheduler", "internal", "invoke", "test",
                  task['test']['type'], "participants" ],
                stdin = pscheduler.json_dump(task['test']['spec']),
                timeout=5,
                env_add=lead_bind_env
                )

            if returncode != 0:
                return error("Unable to determine participants: " + stderr)

            participants = [ host if host is not None
                             else server_fqdn()
                             for host in pscheduler.json_load(stdout)["participants"] ]
        except Exception as ex:
            return error("Exception while determining participants: " + str(ex))
        nparticipants = len(participants)

        # TODO: The participants must be unique.  This should be
        # verified by fetching the host name from each one.

        #
        # TOOL SELECTION
        #

        lead_bind = task.get("lead-bind", None)

        # TODO: Need to provide for tool being specified by the task
        # package.

        tools = []

        tool_params={ "test": pscheduler.json_dump(task["test"]) }
        # HACK: BWCTLBC
        if lead_bind is not None:
            log.debug("Using lead bind of %s" % str(lead_bind))
            tool_params["lead-bind"] = lead_bind

        for participant_no in range(0, len(participants)):

            participant = participants[participant_no]

            try:

                # Make sure the other participants are running pScheduler

                participant_api = pscheduler.api_url(participant)

                log.debug("Pinging %s" % (participant))
                status, result = pscheduler.url_get(
                    participant_api, throw=False, timeout=10,
                    bind=lead_bind)

                if status == 400:
                    raise TaskPostingException(result)
                elif status in [ 202, 204, 205, 206, 207, 208, 226,
                                 300, 301, 302, 303, 304, 205, 306, 307, 308 ] \
                    or ( (status >= 400) and (status <=499) ):
                    raise TaskPostingException("Host is not running pScheduler")
                elif status != 200:
                    raise TaskPostingException("returned status %d: %s"
                                               % (status, result))


                # TODO: This will fail with a very large test spec.
                status, result = pscheduler.url_get(
                    "%s/tools" % (participant_api),
                    params=tool_params,
                    # HACK: BWCTLBC
                    bind=lead_bind if participant_no == 0 else None
                    )
                if status != 200:
                    raise TaskPostingException("%d: %s" % (status, result))
                tools.append(result)
            except TaskPostingException as ex:
                return error("Error getting tools from %s: %s" \
                                     % (participant, str(ex)))
            log.debug("Participant %s offers tools %s", participant, tools)

        if len(tools) != nparticipants:
            return error("Didn't get a full set of tool responses")

        if "tools" in task:
            tool = pick_tool(tools, pick_from=task['tools'])
        else:
            tool = pick_tool(tools)

        if tool is None:
            # TODO: This could stand some additional diagnostics.
            return no_can_do("Couldn't find a tool in common among the participants.")

        task['tool'] = tool

        #
        # TASK CREATION
        #

        tasks_posted = []

        # Evaluate the task against the limits and reject the request
        # if it doesn't pass.

        log.debug("Checking limits on %s", task["test"])

        (processor, whynot) = limitprocessor()
        if processor is None:
            log.debug("Limit processor is not initialized. %s", whynot)
            return no_can_do("Limit processor is not initialized: %s" % whynot)

        hints = request_hints();
        hints_data = pscheduler.json_dump(hints)

        log.debug("Processor = %s" % processor)
        passed, limits_passed, diags = processor.process(task["test"], hints)

        if not passed:
            return forbidden("Task forbidden by limits:\n" + diags)

        # Post the lead with the local database, which also assigns
        # its UUID.  Make it disabled so the scheduler doesn't try to
        # do anything with it until the task has been submitted to all
        # of the other participants.

        try:
            cursor = dbcursor_query(
                "SELECT * FROM api_task_post(%s, %s, %s, %s, 0, NULL, FALSE)",
                [pscheduler.json_dump(task), participants, hints_data,
                 pscheduler.json_dump(limits_passed)], onerow=True)
        except Exception as ex:
            return error(str(ex.diag.message_primary))

        if cursor.rowcount == 0:
            return error("Task post failed; poster returned nothing.")

        task_uuid = cursor.fetchone()[0]

        log.debug("Tasked lead, UUID %s", task_uuid)

        # Other participants get the UUID and participant list forced upon them.

        task["participants"] = participants
        task_data = pscheduler.json_dump(task)

        for participant in range(1,nparticipants):

            part_name = participants[participant]
            log.debug("Tasking participant %s", part_name)
            try:

                # Post the task

                log.debug("Tasking %d@%s: %s", participant, part_name, task_data)
                post_url = pscheduler.api_url(part_name,
                                              'tasks/' + task_uuid)
                log.debug("Posting task to %s", post_url)
                status, result = pscheduler.url_post(
                    post_url,
                    params={ 'participant': participant },
                    data=task_data,
                    bind=lead_bind,
                    json=False,
                    throw=False)
                log.debug("Remote returned %d: %s", status, result)
                if status != 200:
                    raise TaskPostingException("Unable to post task to %s: %s"
                                               % (part_name, result))
                tasks_posted.append(result)

                # Fetch the task's details and add the list of limits
                # passed to our own.

                status, result = pscheduler.url_get(post_url,
                                                    params={ "detail": True },
                                                    bind=lead_bind,
                                                    throw=False)
                if status != 200:
                    raise TaskPostingException(
                        "Unable to fetch posted task from %s: %s"
                        % (part_name, result))
                log.debug("Fetched %s", result)
                try:
                    details = result["detail"]["spec-limits-passed"]
                    log.debug("Details from %s: %s", post_url, details)
                    limits_passed.extend(details)
                except KeyError:
                    pass

            except TaskPostingException as ex:

                for url in tasks_posted:
                    # TODO: Handle failure?
                    status, result = pscheduler.url_delete(url,
                                                           throw=False, 
                                                           timeout=5,
                                                           bind=lead_bind)

                    try:
                        dbcursor_query("SELECT api_task_delete(%s)",
                                       [task_uuid])
                    except Exception as ex:
                        log.exception()

                return error("Error while tasking %s: %s" % (part_name, ex))


        # Update the list of limits passed in the local database
        # TODO: How do the other participants know about this?
        log.debug("Limits passed: %s", limits_passed)
        try:
            cursor = dbcursor_query(
                "UPDATE task SET limits_passed = %s::JSON WHERE uuid = %s",
                [pscheduler.json_dump(limits_passed), task_uuid])
        except Exception as ex:
            return error(str(ex.diag.message_primary))



        # Enable the task so the scheduler will schedule it.
        try:
            dbcursor_query("SELECT api_task_enable(%s)", [task_uuid])
        except Exception as ex:
            log.exception()
            return error("Failed to enable task %s.  See system logs." % task_uuid)
        log.debug("Task enabled for scheduling.")

        return ok_json("%s/%s" % (request.base_url, task_uuid))

    else:

        return not_allowed()



@application.route("/tasks/<uuid>", methods=['GET', 'POST', 'DELETE'])
def tasks_uuid(uuid):
    if request.method == 'GET':

        # Get a task, adding server-derived details if a 'detail'
        # argument is present.

        try:
            cursor = dbcursor_query("""
                SELECT
                    task.json,
                    task.added,
                    task.start,
                    task.slip,
                    task.duration,
                    task.post,
                    task.runs,
                    task.participants,
                    scheduling_class.anytime,
                    scheduling_class.exclusive,
                    scheduling_class.multi_result,
                    task.participant,
                    task.enabled,
                    task.cli,
                    task.limits_passed,
                    task.participant
                FROM
                    task
                    JOIN test ON test.id = task.test
                    JOIN scheduling_class
                        ON scheduling_class.id = test.scheduling_class
                WHERE uuid = %s
            """, [uuid])
        except Exception as ex:
            return error(str(ex))

        if cursor.rowcount == 0:
            return not_found()

        row = cursor.fetchone()
        if row is None:
            return not_found()
        json = row[0]

        # The lead participant passes the participant list to the
        # others within the JSON, but that shouldn't come out when
        # querying it.

        try:
            del json["participants"]
        except KeyError:
            pass

        # Add details if we were asked for them.

        if arg_boolean('detail'):

            part_list = row[7];
            # The database is not supposed to allow this, but spit out
            # a sane default as a last resort in case it happens.
            if part_list is None:
                part_list = [None]
            if row[10] == 0 and part_list[0] is None:
                part_list[0] = server_fqdn()

            json['detail'] = {
                'added': None if row[1] is None \
                    else pscheduler.datetime_as_iso8601(row[1]),
                'start': None if row[2] is None \
                    else pscheduler.datetime_as_iso8601(row[2]),
                'slip': None if row[3] is None \
                    else pscheduler.timedelta_as_iso8601(row[3]),
                'duration': None if row[4] is None \
                    else pscheduler.timedelta_as_iso8601(row[4]),
                'post': None if row[5] is None \
                    else pscheduler.timedelta_as_iso8601(row[5]),
                'runs': None if row[6] is None \
                    else int(row[6]),
                'participants': part_list,
                'anytime':  row[8],
                'exclusive':  row[9],
                'multi-result':  row[10],
                'enabled':  row[12],
                'cli':  row[13],
                'spec-limits-passed': row[14],
                'participant': row[15],
                'runs-href': "%s/runs" % (request.base_url),
                'first-run-href': "%s/runs/first" % (request.base_url),
                'next-run-href': "%s/runs/next" % (request.base_url)
                }

        return ok_json(json)

    elif request.method == 'POST':

        log.debug("Posting to %s", uuid)
        log.debug("Data is %s", request.data)

        # TODO: This is only for participant 1+
        # TODO: This should probably a PUT and not a POST.

        try:
            json_in = pscheduler.json_load(request.data)
        except ValueError:
            return bad_request("Invalid JSON")
        log.debug("JSON is %s", json_in)

        try:
            participant = arg_cardinal('participant')
        except ValueError as ex:
            return bad_request("Invalid participant: " + str(ex))
        log.debug("Participant %d", participant)

        # Evaluate the task against the limits and reject the request
        # if it doesn't pass.

        log.debug("Checking limits on task")

        processor, whynot = limitprocessor()
        if processor is None:
            message = "Limit processor is not initialized: %s" % whynot
            log.debug(message)
            return no_can_do(message)

        hints = request_hints()
        hints_data = pscheduler.json_dump(hints)

        passed, limits_passed, diags = processor.process(json_in["test"], hints)

        if not passed:
            return forbidden("Task forbidden by limits:\n" + diags)
        log.debug("Limits passed")

        # TODO: Pluck UUID from URI
        uuid = url_last_in_path(request.url)

        log.debug("Posting task %s", uuid)

        try:
            try:
                participants = pscheduler.json_load(request.data)["participants"]
            except:
                return bad_request("No participants provided")
            cursor = dbcursor_query(
                "SELECT * FROM api_task_post(%s, %s, %s, %s, %s, %s, TRUE)",
                [request.data, participants, hints_data, pscheduler.json_dump(limits_passed), participant, uuid])
        except Exception as ex:
            return error(str(ex))
        if cursor.rowcount == 0:
            return error("Task post failed; poster returned nothing.")
        # TODO: Assert that rowcount is 1
        log.debug("All done: %s", base_url())
        return ok(base_url())

    elif request.method == 'DELETE':

        parsed = list(urlparse.urlsplit(request.url))
        parsed[1] = "%s"
        template = urlparse.urlunsplit(parsed)

        try:
            requester = task_requester(uuid)
            if requester is None:
                return not_found()

            if not access_write_ok(requester):
                return forbidden()

            cursor = dbcursor_query(
                "SELECT api_task_disable(%s, %s)", [uuid, template])
            cursor.close()

        except Exception as ex:
            return error(str(ex))

        return ok()

    else:

        return not_allowed()





@application.route("/tasks/<uuid>/cli", methods=['GET'])
def tasks_uuid_cli(uuid):

    # Get a task, adding server-derived details if a 'detail'
    # argument is present.

    try:
        cursor = dbcursor_query(
            """SELECT
                   task.json #>> '{test, spec}',
                   test.name
               FROM
                   task
                   JOIN test on test.id = task.test
               WHERE task.uuid = %s""", [uuid])
    except Exception as ex:
        return error(str(ex))

    if cursor.rowcount == 0:
        return not_found()

    row = cursor.fetchone()
    if row is None:
        return not_found()
    json, test = row

    try:
        returncode, stdout, stderr = pscheduler.run_program(
            [ "pscheduler", "internal", "invoke", "test",
              test, "spec-to-cli" ], stdin = json )
        if returncode != 0:
            return error("Unable to convert test spec: " + stderr)
    except Exception as ex:
        return error("Unable to convert test spec: " + str(ex))

    returned = pscheduler.json_load(stdout)
    returned.insert(0, test)

    return ok(pscheduler.json_dump(returned))
