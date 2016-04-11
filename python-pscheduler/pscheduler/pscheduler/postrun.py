"""
Internally-used functions for posting runs to the timelines on
multiple servers.
"""

# In-module things we use
from pstime import *
from psurl import *

import datetime
import pscheduler
import random
import re
import requests
import time
import urlparse


def run_post(
    task_url_text, # URL for task
    start_time,    # Desired start time
    log=None
    ):
    """
    Schedule a run of a task on all participating nodes.

    Returns a tuple containing a list of the posted run URLs (which
    will be None in the event of an error) and an error message (None
    if there was no error).
    """

    log and log.debug("Posting %s at %s", task_url_text, start_time)

    # TODO: Error handling when calling url_* needs improvement.  Lots.

    task_url = urlparse.urlparse(task_url_text)
    assert type(start_time) == datetime.datetime

    status, task = pscheduler.url_get(task_url_text, params={'detail': 1})

    # Generate a list of the task URLs

    task_urls =[]
    participants = task['detail']['participants']
    assert len(participants) >= 1

    parts = list(task_url)
    for participant in participants:
        # TODO: Use the canonicalizer for generating these URLs.
        parts[1] = re.sub( '^[^:]*',
                           pscheduler.api_this_host()
                           if participant is None else str(participant),
                           parts[1])
        url = urlparse.urlunsplit(parts[:-1])
        task_urls.append(url)
        log and log.debug("Participant task URL is %s", url)

    #
    # Figure out the range of times in which the task can be run.
    #

    task_duration = pscheduler.iso8601_as_timedelta(task['detail']['duration'])
    try:
        task_slip = pscheduler.iso8601_as_timedelta(task['detail']['slip'])
    except KeyError:
        task_slip = datetime.timedelta()

    run_range_end = start_time + task_duration + task_slip

    range_params = {
        'start': pscheduler.datetime_as_iso8601(start_time),
        'end': pscheduler.datetime_as_iso8601(run_range_end)
        }

    #
    # Get a list of the time ranges each participant has available to
    # run the task that overlap with the range we want.
    #

    # TODO: Get lead's list from the database.

    range_set = []

    for task_url in task_urls:

        runtime_url = task_url + '/runtimes'
        status, json_ranges = pscheduler.url_get( runtime_url,
                                                  params=range_params,
                                                  throw = False )

        if status != 200:
            return (None, None, None,
                    "Error trying to schedule with %s: %s %d: %s"
                    % (participant, runtime_url, status, json_ranges))

        if len(json_ranges) == 0:
            return (None, None, None,
                    "Host %s cannot schedule this run: %s %d: %s"
                    % (participant, runtime_url, status, json_ranges))
        
        range_set.append( [ (pscheduler.iso8601_as_datetime(item['lower']),
                             pscheduler.iso8601_as_datetime(item['upper']))
                            for item in json_ranges ] )

    #
    # Find the range that fits
    #

    # The adjustment of the duration by one second forces
    # coalesce_ranges() to behave like the ranges are closed instead
    # of half-closed.

    schedule_range = \
        pscheduler.coalesce_ranges( range_set,
                                    task_duration \
                                        - datetime.timedelta(seconds=1) )
    if schedule_range is None:
        return (None, None, None, "No mutually-agreeable time to run this task."
                + str(range_set) + ' ' + str(task_duration))

    (schedule_lower, schedule_upper) = schedule_range
    assert schedule_lower < schedule_upper
    log and log.debug("Time range is %s - %s", schedule_lower, schedule_upper)

    # Apply random slip if one was specified

    try:
        randslip = task['schedule']['randslip']
        slip_available = schedule_upper - schedule_lower - task_duration
        slip_seconds = pscheduler.timedelta_as_seconds(slip_available) \
            * random.random()
        schedule_lower += pscheduler.seconds_as_timedelta(int(slip_seconds))
        log and log.debug("Applying random slip of %d seconds",
                          int(slip_seconds))
    except KeyError:
        pass  # No random slip, no problem.

    # Make sure we haven't slipped further than allowed.
    assert schedule_upper - schedule_lower >= task_duration

    schedule_upper = schedule_lower + task_duration

    #
    # Post the runs to the participants
    #

    run_params = { 'start-time': schedule_lower.isoformat() }

    runs_posted = []

    # First one is the lead.  Post it and get the UUID.

    if log:
        log.debug("Posting lead run to %s", task_urls[0])
        log.debug("Data %s", run_params)
    status, run_lead_url \
        = pscheduler.url_post(task_urls[0] + '/runs',
                              data=pscheduler.json_dump(run_params))
    log and log.debug("Lead URL is %s", run_lead_url)
    assert type(run_lead_url) in [str, unicode]
    runs_posted.append(run_lead_url)

    # TODO: This should parse the URL and change the netloc instead of
    # assembling URLs.

    # What to add to a task URL to make the run URL
    run_suffix = run_lead_url[len(task_urls[0]):]

    # Cover the rest of the participants if there are any.

    errors = []

    put_params = { 'run': pscheduler.json_dump(run_params) }

    for task_url in task_urls[1:]:

        put_url = task_url + run_suffix

        if log:
            log.debug("Putting run to participant %s", put_url)
            log.debug("Parameters: %s", run_params)

        status, output = pscheduler.url_put(put_url,
                                            params=put_params,
                                            throw=False,
                                            json=False  # No output.
                                            )

        log and log.debug("PUT %d: %s", status, output)

        if status != 200:
            log and log.debug("Failed: %s", output)
            errors.append(output)
            continue

        runs_posted.append(put_url)
        log and log.debug("Succeeded.")

    if len(runs_posted) != len(task_urls):
        pscheduler.url_delete_list(runs_posted)
        # TODO: Better error?
        return (None, None, None, "Failed to post/put runs to all participants.")

    #
    # Fetch all per-participant data, merge it and distribute the
    # result to all participants.
    #

    log and log.debug("Fetching per-participant data")

    part_data = []

    for run in runs_posted:

        # TODO: Should this be multiple attempts to avoid a race condition?
        log and log.debug("Getting part data from %s", run)
        status, result = pscheduler.url_get(run, throw=False)
        if status != 200 or not 'participant-data' in result:
            pscheduler.url_delete_list(runs_posted)
            # TODO: Better error?
            return (None, None, None, "Failed to get run data from all participants")
        part_data.append(result['participant-data'])
        log and log.debug("Got %s", result['participant-data'])

    full_data = pscheduler.json_dump ({
        'part-data-full': part_data
        })

    log and log.debug("Full part data: %s", full_data)

    for run in runs_posted:
        log and log.debug("Putting full part data to %s", run)
        status, result = pscheduler.url_put(run,
                                            params={ 'run': full_data },
                                            json=False,
                                            throw=False)
        if status != 200:
            pscheduler.url_delete_list(runs_posted)
            # TODO: Better error?
            log and log.debug("Failed: %s", result)
            return (None, None, None, "Failed to post run data to all participants")


    # TODO: Probably also want to return the start and end times?
    log and log.debug("Run posting finished")
    return (runs_posted[0], schedule_lower, schedule_upper, None)



def run_fetch_result(
    url,
    tries=10,
    timeout=pscheduler.seconds_as_timedelta(10)
    ):
    """
    Fetch the results of a run, trying repeatedly until a timeout
    specified as a timedeltas been passed.
    """

    end_time = pscheduler.time_now() + timeout
    sleep_time = pscheduler.timedelta_as_seconds(timeout / tries)

    while pscheduler.time_now() < end_time:

        status, result = pscheduler.url_get(url, throw=False)
        if status == 200 and result['state'] == 'finished':
                return result
        time.sleep(sleep_time)

    # TODO: This or throw something?
    return None
