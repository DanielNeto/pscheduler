#!/bin/sh -e
#
# Monitor the state of pScheduler's schedule.
#
# Usage:  pscheduler-monitor [ --sleep n ]
#
# Where:
#     --sleep n   Sleeps for n seconds between checks.  The default
#                 is 2.
#     --uuid      Show task/run UUIDs instead of DB row IDs
#
#
# NOTE: This program is not particularly resource-efficient and should
# really only be used for debug and diagnostics.
# TODO: Write a better version of this in Python with curses.
# TODO: Need to handle reading the DSN file.
#

SLEEP=2
RUN_ID=run
TASK_ID=task


while echo "$1" | egrep -qe '^--.'
do
  OPTION="$1"
  shift

  case "${OPTION}" in

      --sleep)
          SLEEP="$1"
          shift
          ;;

      --uuid)
          RUN_ID=run_uuid
	  TASK_ID=task_uuid
          ;;

      *)
          die "Unknown option ${OPTION}"
          ;;

  esac

done








while true
do
    clear

    printf "pScheduler Server Monitor | %s |  Updated every ${SLEEP} seconds\n\n" \
	"$(date '+%Y-%m-%d %H:%M:%S')"


    PGPASSFILE=__PGPASSFILE__ psql -U __PGUSER__ __PGDATABASE__ <<EOF

SELECT
  ${RUN_ID} AS run,
  ${TASK_ID} AS task,
  test::char(10),
  tool::char(10),
  lower(times) AS start,
  upper(times) - lower(times) AS duration,
  CASE
    WHEN state = 'Pending' THEN 'AWOL'::char(10)
    WHEN state = 'Finished' THEN 'Finished'::char(10)
    ELSE state::char(10)
    END
FROM (SELECT *
      FROM
          run_status
      WHERE
        upper(times) < now()
      ORDER BY times DESC
      LIMIT 10) older
UNION

SELECT
  ${RUN_ID} AS run,
  ${TASK_ID} AS task,
  test::char(10),
  tool::char(10),
  lower(times) AS start,
  upper(times) - lower(times) AS duration,
  CASE
    WHEN state = 'Pending' THEN ''::char(10)
    ELSE state::char(10)
    END
FROM (SELECT * FROM run_status
      WHERE
        times @> now()
        OR lower(times) >= now()
      LIMIT 10) newer

ORDER BY start ASC
;

EOF

    sleep $SLEEP
done
