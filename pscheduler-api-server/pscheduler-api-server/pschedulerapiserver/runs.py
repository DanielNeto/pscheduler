#
# Run-Related Pages
#

import pscheduler

from pschedulerapiserver import application

from flask import request

from .dbcursor import dbcursor
from .json import *
from .log import log
from .response import *
from .tasks import task_exists


# Proposed times for a task
@application.route("/tasks/<task>/runtimes", methods=['GET'])
def task_uuid_runtimes(task):
    try:
        range_start = arg_datetime('start')
        range_end   = arg_datetime('end')
    except ValueError:
        return bad_request('Invalid start or end time')
    if not task_exists(task):
        return not_found()

    return json_query_simple(dbcursor(), """
        SELECT row_to_json(apt.*)
        FROM  api_proposed_times(%s, %s, %s) apt
        """, [task, range_start, range_end], empty_ok=True)



# Established runs for a task
@application.route("/tasks/<task>/runs", methods=['GET', 'POST'])
def tasks_uuid_runs(task):

    if request.method == 'GET':

        query = "SELECT '" + base_url() + """/' || run.uuid
             FROM
                 run
                 JOIN task ON task.id = run.task
             WHERE
                task.uuid = %s"""
        args = [task]

        try:

            start_time = arg_datetime('start')
            if start_time is not None:
                query += " AND lower(times) >= %s"
                args.append(start_time)

            end_time = arg_datetime('end')
            if end_time is not None:
                query += " AND upper(times) <= %s"
                args.append(end_time)

            query += " ORDER BY times"

            limit = arg_cardinal('limit')
            if limit is not None:
                query += " LIMIT " + str(limit)

            # TODO: This should be exapandable

        except ValueError as ex:

            return bad_request(str(ex))


        return json_query_simple(dbcursor(), query, args, empty_ok=True)

    elif request.method == 'POST':

        log.debug("Run POST: %s --> %s", request.url, request.data)

        try:
            data = pscheduler.json_load(request.data)
            start_time = pscheduler.iso8601_as_datetime(data['start-time'])
        except KeyError:
            return bad_request("Missing start time")
        except ValueError:
            return bad_request("Invalid JSON:" + request.data)

        try:
            dbcursor().execute("SELECT api_run_post(%s, %s)", [task, start_time])
            uuid = dbcursor().fetchone()[0]
        except:
            log.exception()
            return error("Database query failed")

        # TODO: Assert that rowcount is 1
        url = base_url() + '/' + uuid
        log.debug("New run posted to %s", url)
        return ok_json(url)

    else:

        return not_allowed()



@application.route("/tasks/<task>/runs/<run>", methods=['GET', 'PUT', 'DELETE'])
def tasks_uuid_runs_run(task, run):

    if task is None:
        return bad_request("Missing or invalid task")

    if run is None:
        return bad_request("Missing or invalid run")

    if request.method == 'GET':

        # TODO: Should handle POST, PUT of full participant data and DELETE
        dbcursor().execute("""
            SELECT
                lower(run.times),
                upper(run.times),
                upper(run.times) - lower(run.times),
                task.participant,
                task.nparticipants,
                run.part_data,
                run.part_data_full,
                run.result,
                run.result_full,
                run.result_merged,
                run_state.enum,
                run_state.display
            FROM
                run
                JOIN task ON task.id = run.task
                JOIN run_state ON run_state.id = run.state
            WHERE
                task.uuid = %s
                AND run.uuid = %s
            """, [task, run])

        if dbcursor().rowcount == 0:
            return not_found()

        result = {}
        row = dbcursor().fetchone()
        result['href'] = request.url
        result['start-time'] = pscheduler.datetime_as_iso8601(row[0])
        result['end-time'] = pscheduler.datetime_as_iso8601(row[1])
        result['duration'] = pscheduler.timedelta_as_iso8601(row[2])
        result['participant'] = row[3]
        result['participants'] = row[4]
        result['participant-data'] = row[5]
        result['participant-data-full'] = row[6]
        result['result'] = row[7]
        result['result-full'] = row[8]
        result['result-merged'] = row[9]
        result['state'] = row[10]
        result['state-display'] = row[11]
        result['task-href'] = root_url('tasks/' + task)

        return json_response(result)

    elif request.method == 'PUT':

        log.debug("Run PUT %s", request.url)

        # This expects one argument called 'run'
        try:
            log.debug("ARG run %s", request.args.get('run'))
            run_data = arg_json('run')
        except ValueError:
            log.exception()
            log.debug("Run data was %s", request.args.get('run'))
            return error("Invalid or missing run data")

        # If the run doesn't exist, take the whole thing as if it were
        # a POST.

        dbcursor().execute("SELECT EXISTS (SELECT * FROM run WHERE uuid = %s)", [run])
        # TODO: Handle Failure
        # TODO: Assert that rowcount is 1
        if not dbcursor().fetchone()[0]:

            log.debug("Record does not exist; full PUT.")

            try:
                start_time = \
                    pscheduler.iso8601_as_datetime(run_data['start-time'])
            except KeyError:
                return bad_request("Missing start time")
            except ValueError:
                return bad_request("Invalid start time")

            try:
                dbcursor().execute("SELECT api_run_post(%s, %s, %s)", [task, start_time, run])
                # TODO: Assert that rowcount is 1
                log.debug("Full put of %s, got back %s", run, dbcursor().fetchone()[0])
            except:
                log.exception()
                return error("Database query failed")

            return ok()

        # For anything else, only one thing can be udated at a time,
        # and even that is a select subset.

        log.debug("Record exists; partial PUT.")

        if 'part-data-full' in run_data:

            log.debug("Updating part-data-full from %s", run_data)

            try:
                part_data_full = \
                    pscheduler.json_dump(run_data['part-data-full'])
            except KeyError:
                return bad_request("Missing part-data-full")
            except ValueError:
                return bad_request("Invalid part-data-full")

            log.debug("Full data is: %s", part_data_full)

            dbcursor().execute("""UPDATE
                                  run
                              SET
                                  part_data_full = %s
                              WHERE
                                  uuid = %s
                                  AND EXISTS (SELECT * FROM task WHERE UUID = %s)
                              """,
                           [ part_data_full, run, task])
            if dbcursor().rowcount != 1:
                return not_found()

            log.debug("Full data updated")

            return ok()

        elif 'result-full' in run_data:

            log.debug("Updating result-full from %s", run_data)

            try:
                result_full = \
                    pscheduler.json_dump(run_data['result-full'])
            except KeyError:
                return bad_request("Missing result-full")
            except ValueError:
                return bad_request("Invalid result-full")

            log.debug("Updating result-full: %s", result_full)


            dbcursor().execute("""UPDATE
                                  run
                              SET
                                  result_full = %s
                              WHERE
                                  uuid = %s
                                  AND EXISTS (SELECT * FROM task WHERE UUID = %s)
                              """,
                           [ result_full, run, task])
            if dbcursor().rowcount != 1:
                return not_found()

            return ok()

    elif request.method == 'DELETE':

        # TODO: If this is the lead, the run's counterparts on the
        # other participating nodes need to be removed as well.

        dbcursor().execute("""
            DELETE FROM run
            WHERE
                task in (SELECT id FROM task WHERE uuid = %s)
                AND uuid = %s 
            """, [task, run])

        return ok() if dbcursor().rowcount == 1 else not_found()

    else:

        return not_allowed()
