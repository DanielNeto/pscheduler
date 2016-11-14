#!/usr/bin/python
#
# pScheduler Archiver Daemon
#

import daemon
import datetime
import errno
import json
import optparse
import os
import pscheduler
import psycopg2
import psycopg2.extensions
import select
import signal
import socket
import sys
import threading
import time
import traceback

from dateutil.tz import tzlocal



# Gargle the arguments

opt_parser = optparse.OptionParser()

# Daemon-related options

opt_parser.add_option("--daemon",
                      help="Daemonize",
                      action="store_true",
                      dest="daemon", default=False)
opt_parser.add_option("--pid-file",
                      help="Location of PID file",
                      action="store", type="string", dest="pidfile",
                      default=None)

# Program options

opt_parser.add_option("-a", "--archive-defaults",
                      help="Directory containing default archivers",
                      action="store", type="string", dest="archive_defaults",
                      default="__DEFAULT_DIR__")
opt_parser.add_option("-c", "--channel",
                      help="Schedule notification channel",
                      action="store", type="string", dest="channel",
                      default="archiving_change")
opt_parser.add_option("-d", "--dsn",
                      help="Database connection string",
                      action="store", type="string", dest="dsn",
                      default="dbname=pscheduler")
opt_parser.add_option("-m", "--max-parallel",
                      help="Maximum concurrent archivings",
                      action="store", type="int", dest="max_parallel",
                      default=15)
opt_parser.add_option("-r", "--refresh",
                      help="Forced refresh interval (ISO8601)",
                      action="store", type="string", dest="refresh",
                      default="PT1M")
opt_parser.add_option("-s", "--short-refresh",
                      help="Short refresh interval (ISO8601)",
                      action="store", type="string", dest="short_refresh",
                      default="PT10S")
opt_parser.add_option("--verbose", action="store_true", dest="verbose")
opt_parser.add_option("--debug", action="store_true", dest="debug")


(options, args) = opt_parser.parse_args()

long_refresh = pscheduler.iso8601_as_timedelta(options.refresh)
if long_refresh is None:
    opt_parser.error('Invalid refresh interval "' + options.refresh + '"')
if pscheduler.timedelta_as_seconds(long_refresh) == 0:
    opt_parser.error("Refresh interval must be calculable as seconds.")

short_refresh = pscheduler.iso8601_as_timedelta(options.short_refresh)
if short_refresh is None:
    opt_parser.error('Invalid short refresh interval "' + options.short_refresh + '"')
if pscheduler.timedelta_as_seconds(short_refresh) == 0:
    opt_parser.error("Short refresh interval must be calculable as seconds.")

if options.max_parallel < 1:
    opt_parser.error("Number of concurrent archivings must be positive.")

log = pscheduler.Log(verbose=options.verbose, debug=options.debug)

dsn = options.dsn


#
# Maintainer for default archives
#

class DefaultArchiveMaintainer:

    def __init__(self, path, dsn, log):

        self.path = path
        self.dsn = dsn
        self.log = log

        # This needs its own database connection without autocommit.
        self.db = pscheduler.pg_connection(dsn)
        self.db.autocommit = False
        self.cursor = self.db.cursor()

        # Most recent file or directory change we saw
        self.most_recent = 0


    def refresh(self):

        self.log.debug("Refreshing default archivers from %s", self.path)

        if not os.path.isdir(self.path):
            self.log.debug("%s is not a directory", self.path)
            return

        timestamps = [ os.path.getmtime(self.path) ]

        # Examine everything before tinkering with the database

        archives = []

        # Hold warnings until after we see something's changed so we
        # don't spew them repeatedly.
        warnings = []

        try:
            paths = [ os.path.join(self.path, f)
                      for f in os.listdir(self.path) ]
        except OSError as ex:
            self.log.debug("Unable to read %s: %s", self.path, ex)
            return

        # Gather the timestamps

        for path in paths:

            self.log.debug("Examining file %s", path)

            try:

                if os.path.isfile(path):

                    # Append the timestamp whether the file is valid or
                    # not, because we're looking for any kind of change.
                    # Note that we check mtime *and* ctime to catch
                    # permission changes and the like.
                    timestamps.append( max(os.path.getctime(path),
                                           os.path.getmtime(path)) )
                else:
                    self.log.debug("Not a file")
                    continue

            except Exception as ex:
                warnings.append("Ignoring %s: %s" % (path, str(ex)))
                continue

        # If nothing's changed, we're done.

        timestamps = sorted(timestamps, reverse=True)
        newest = timestamps[0]
        if newest <= self.most_recent:
            self.log.debug("Nothing has changed; not updating.")
            return

        self.most_recent = newest

        # Parse the files and make a list to be inserted into the database

        for path in paths:

            self.log.debug("Reading file %s", path)

            try:
                with open(path, 'r') as content:
                    spec = pscheduler.json_load(content)
            except Exception as ex:
                warnings.append("Ignoring %s: %s" % (path, str(ex)))
                continue

            archives.append({
                    "path": path,
                    "spec": spec
                    })

        # Spit out any warnings that were accumulated

        for warning in warnings:
            self.log.warning(warning)

        # Write to the database.  Note that we don't take any steps to
        # suppress exceptions; if something goes south we want the
        # entire program to restart.

        self.log.debug("Writing the database")

        try:
            self.cursor.execute("DELETE FROM archive_default")
        except Exception as ex:
            self.log.error("Failed to delete defaults: %s", str(ex))

        for archive in archives:

            self.cursor.execute("SAVEPOINT archiver_insert")
            failed = True
            try:
                self.cursor.execute("INSERT INTO archive_default (archive) VALUES (%s)",
                                    [ pscheduler.json_dump(archive["spec"]) ])
                self.log.debug("Inserted data from %s", archive["path"])
                failed = False
            except psycopg2.Error as ex:
                self.log.warning("Ignoring %s: %s", archive["path"], ex.diag.message_primary)
            except Exception as ex:
                self.log.error("%s: %s", archive["path"], str(ex))

            if failed:
                self.cursor.execute("ROLLBACK TO SAVEPOINT archiver_insert")

        # Finish up and get out

        self.db.commit()




# Dictionary of archivings in progress

workers = pscheduler.ThreadSafeDictionary()


#
# Archive Worker
#

class ArchiveWorker():

    def __init__(self, db, log, row):
        self.db = db
        self.log = log
        self.row = row

        self.id = row[0]
        self.cursor = db.cursor()

        self.worker = threading.Thread(target=lambda: self.run())
        self.worker.start()


    def run(self):
        """
        Archive the result in a thread-safe way
        """
        self.log.debug("%d: Thread running", self.id)
        try:
            self.__run()
        except Exception as ex:
            # Don't worry about the result here.  If __run() failed to
            # post anything, that will be the end of it.  If it did,
            # it might be salvageable.
            self.log.exception()
        self.log.debug("%d: Thread finished", self.id)
        self.cursor.close()
        del workers[self.id]


    def __run(self):
        """
        Do the deed
        """

        run_id, uuid, archiver, archiver_data, start, duration, test, \
            tool, participants, result_merged, attempts, \
            last_attempt = self.row

        participants_merged = []
        for participant in participants:
            participants_merged.append(socket.gethostname() \
                                       if participant is None \
                                       else participant)

        json = {
            'data': archiver_data,
            'result': {
                'id': uuid,
                'schedule': {
                    'start': pscheduler.datetime_as_iso8601(start),
                    'duration': pscheduler.timedelta_as_iso8601(duration)
                },
                'test': test,
                'tool': {
                    'name': tool['name'],
                    'version': tool['version'],
                },
                'participants': participants_merged,
                'result': result_merged
            },
            'attempts': attempts,
            'last-attempt': None if last_attempt is None \
            else pscheduler.datetime_as_iso8601(last_attempt) 
        }


        archiver_in = pscheduler.json_dump(json)
        self.log.debug("%d: Running archiver %s with input %s",
                       self.id, archiver, archiver_in)

        returncode, stdout, stderr = pscheduler.run_program(
            [ "pscheduler", "internal", "invoke", "archiver", archiver, "archive" ],
            stdin = archiver_in
        )

        self.log.debug("%d: Archiver exited %d", self.id, returncode)
        self.log.debug("%d: Returned JSON from archiver: %s", self.id, stdout)
        self.log.debug("%d: Returned errors from archiver: %s", self.id, stderr)

        attempt = pscheduler.json_dump( [ {
            "time": pscheduler.datetime_as_iso8601(datetime.datetime.now(tzlocal())),
            "return-code": returncode,
            "stdout": stdout,
            "stderr": stderr
        } ] )



        if returncode != 0:

            self.log.debug("%d: Permanent Failure: %s", self.id, stderr)
            self.cursor.execute("""UPDATE archiving
                                     SET
                                       archived = TRUE,
                                       attempts = attempts + 1,
                                       last_attempt = now(),
                                       next_attempt = NULL,
                                       diags = diags || (%s::JSONB)
                                     WHERE id = %s""",
                                  [ attempt, run_id ])

        else:

            try:
                returned_json = pscheduler.json_load(stdout)
            except ValueError:
                self.log.error("%d: Archiver %s returned invalid JSON: %s",
                               self.id, archiver, stdout)
                return

            if returned_json['succeeded']:
                self.log.debug("%d: Succeeded: %s to %s",
                               self.id, uuid, archiver)
                self.cursor.execute("""UPDATE archiving
                                         SET
                                             archived = TRUE,
                                             attempts = attempts + 1,
                                             last_attempt = now(),
                                             next_attempt = NULL,
                                             diags = diags || (%s::JSONB)
                                         WHERE id = %s""",
                                      [ attempt, run_id ])

            else:

                self.log.debug("%d: Failed: %s to %s: %s",
                               self.id, uuid, archiver, stdout)

                # If there's a retry, schedule the next one.

                if "retry" in returned_json:

                    next_delta = pscheduler.iso8601_as_timedelta(
                        returned_json['retry'])

                    next = datetime.datetime.now(tzlocal()) \
                           + next_delta

                    self.log.debug("%d: Rescheduling for %s", self.id, next)

                    self.cursor.execute("""UPDATE archiving
                                             SET
                                                 attempts = attempts + 1,
                                                 last_attempt = now(),
                                                 next_attempt = %s,
                                                 diags = diags || (%s::JSONB)
                                             WHERE id = %s""",
                                          [ next, attempt, run_id ])

                else:

                    self.log.debug("%d: No retry requested.  Giving up.", self.id)





#
# Main Program
#

def main_program():

    # Exit nicely when certain signals arrive so running processes are
    # cleaned up.

    def exit_handler(signum, frame):
        log.info("Exiting on signal %d", signum)
        exit(0)

    for sig in [ signal.SIGHUP, signal.SIGINT, signal.SIGQUIT, signal.SIGTERM ]:
        signal.signal(sig, exit_handler)

    pg = pscheduler.pg_connection(dsn)

    cursor = pg.cursor()
    cursor.execute("LISTEN " + options.channel)
    

    # Something to maintain the default archiver list
    default_maintainer = DefaultArchiveMaintainer(options.archive_defaults, dsn, log)
    default_maintainer.refresh()

    next_refresh = None

    while True:

        # Wait for something to happen.

        if next_refresh is None:

            log.debug("Retrieving immediately.")

        else:

            log.debug("Waiting %s for change or notification", next_refresh)

            try:
                if select.select([pg],[],[],
                                 pscheduler.timedelta_as_seconds(next_refresh)) \
                                 != ([],[],[]):
                    pg.poll()
                    del pg.notifies[:]
                    log.debug("Notified.")

            except select.error as ex:

                err_no, message = ex
                if err_no != errno.EINTR:
                    log.exception()
                    raise ex


        # Until we hear otherwise...
        next_refresh = long_refresh

        cursor.execute("""SELECT id, uuid, archiver, archiver_data, start,
                      duration, test, tool, participants, result,
                      attempts, last_attempt
                      FROM archiving_eligible""")

        if cursor.rowcount == 0:
            log.debug("Nothing to archive.")
            continue

        # Only refresh after there's been a wait and we got rows.
        if next_refresh is not None:
            default_maintainer.refresh()

        log.debug("Got %d rows", cursor.rowcount)

        for row in cursor.fetchall():

            # Don't bother if there are already too many archivers running.
            if len(workers) >= options.max_parallel:
                log.debug("Already running %d archivers.", len(workers))
                next_refresh = short_refresh
                break

            id = row[0]

            if id in workers:
                log.debug("%d: Already running a worker", id)
                continue

            log.debug("%d: Starting worker", id)
            workers[id] = ArchiveWorker(pg, log, row)



if options.daemon:
    pidfile = pscheduler.PidFile(options.pidfile)
    with daemon.DaemonContext(pidfile=pidfile):
        pscheduler.safe_run(lambda: main_program())
else:
    main_program()
