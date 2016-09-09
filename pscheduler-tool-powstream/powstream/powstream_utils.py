###
# utilities used by powstream command
#

import pscheduler
from powstream_defaults import *
import ConfigParser
import datetime
import os
import re
import shutil
import sys
import time

#output contants
DELAY_BUCKET_DIGITS = 2 #number of digits to round delay buckets
DELAY_BUCKET_FORMAT = '%.2f' #Set buckets to nearest 2 decimal places
CLOCK_ERROR_DIGITS = 2 #number of digits to round clock error

#logger
log = pscheduler.Log(prefix="tool-powstream", quiet=True)

##
# Open config file
def get_config():
    config = None
    try:
        config = ConfigParser.ConfigParser()
        config.read(CONFIG_FILE)
    except:
        log.warning("Unable to read configuration file %s. Proceeding with defaults.")
    
    return config

##
# Remove data directory
def cleanup_dir(tmpdir, keep_data_files=False):
    if keep_data_files: return
    #Remove our tmpdir, but don't fail the test if it doesn't remove
    try:
        shutil.rmtree(tmpdir, ignore_errors=False)
    except:
        log.warning("Unable to remove powstream temporary directory %s: %s" % (tmpdir, sys.exc_info()[0]))

##
# Called by signal handlers to clean-up then exit
def graceful_exit(tmpdir, keep_data_files=False, proc=None):
    #kill process if any, but keep in on try so doesn't prevent directory clean-up
    try:
        if proc: 
            proc.terminate()
            log.debug("Sent terminate to powstream process %s" % proc.pid)
    except: 
        pass
    
    #clean directory
    try:
        cleanup_dir(tmpdir, keep_data_files=False)
    except:
        pass
    finally:
        sys.exit(1)
    
##
# Removes a data file
def cleanup_file(tmpfile, keep_data_files=False):
    if keep_data_files: return
    #Remove our tmpfile, but don't fail the test if it doesn't remove
    try:
        os.remove(tmpfile)
    except:
        log.warning("Unable to remove powstream temporary directory %s: %s" % (tmpdir, sys.exc_info()[0]))

##
# Handles reporting errors in pscheduler format
def handle_run_error(msg, diags=None, do_log=True):
    if do_log:
        log.error(msg)
    results = { 
        'schema': LATENCY_SCHEMA_VERSION, 
        'succeeded': False,
        'error': msg,
        'diags': diags
    }
    print pscheduler.json_dump(results)
    print pscheduler.api_result_delimiter()
    print sys.stdout.flush()

##
# Calculates time to sleep or returns True if end time reached
def sleep_or_end(seconds, end_time, parent_pid):
    #check if we are at or beyond endtime
    now = datetime.datetime.now()
    if now >= end_time:
        return True
    elif seconds == 0:
        #if we don't care about sleeping, don't mess with the rest
        return False
    
    #check parent still running
    if (parent_pid is not None) and (not os.path.exists("/proc/%d" % parent_pid)):
         return True
        
    #Determine how long to sleep
    time_left = end_time - now
    if time_left > datetime.timedelta(seconds=seconds) :
        #sleep for given time if it will be less than end time when we wake-up
        time.sleep(seconds)
    else:
        #sleep until end time
        # don't convert until here because could be a real big value otherwise
        # also once 2.6 is out of the picture, can just call time_left.total_seconds()
        time.sleep((time_left.microseconds + (time_left.seconds + time_left.days * 24 * 3600) * 10.0**6) / 10.0**6)
    
    return False

##
# Parse output
def parse_raw_owamp_output(file, raw_output=False, bucket_width=TIME_SCALE):

    #Process output
    results = { 
        'schema': LATENCY_SCHEMA_VERSION, 
        'succeeded': False 
    }
    powstream_regex = re.compile('^(\d+) (\d+) (\d) ([-.0-9e+]*) (\d+) (\d) ([-.0-9e+]*) (\d+)$')
    results['packets-sent'] = 0
    results['packets-received'] = 0
    results['packets-duplicated'] = 0
    results['packets-reordered'] = 0
    results['histogram-latency'] = {}
    results['histogram-ttl'] = {}
    if raw_output:
        results['raw-packets'] = []
    packets_seen = {}
    prev_seq_number = -1
    for line in file:
        powstream_match = powstream_regex.match(line)
        if powstream_match:
            seq_number               = powstream_match.group(1);
            source_timestamp         = powstream_match.group(2);
            source_synchronized      = powstream_match.group(3);
            source_error             = powstream_match.group(4);
            destination_timestamp    = powstream_match.group(5);
            destination_synchronized = powstream_match.group(6);
            destination_error        = powstream_match.group(7);
            ttl                      = powstream_match.group(8);
            
            #publish raw pings
            if raw_output:
                #init packet object
                packet = {
                    'seq-num': int(seq_number),
                    'src-ts': int(source_timestamp),
                    'src-clock-sync': source_synchronized == "1",
                    'src-clock-err': source_error,
                    'dst-ts': int(destination_timestamp),
                    'dst-clock-sync': destination_synchronized == "1",
                    'dst-clock-err': destination_error,
                    'ip-ttl': int(ttl)
                }
                #The error values may not exist, but format as floats if they do
                if source_error:
                    packet['src-clock-err'] = float(source_error)
                if destination_error:
                    packet['dst-clock-err'] = float(destination_error)
                #add to list
                results['raw-packets'].append(packet)
    
            #duplicates
            if seq_number in packets_seen:
                results['packets-duplicated'] += 1
                continue
            
            #sent
            results['packets-sent'] += 1
            
            #packet lost
            if int(destination_timestamp) == 0:
                continue
            
            #received
            results['packets-received'] += 1
            
            #delay histogram
            ##calculate delay in terms of seconds. OWAMP uses odd timestamps so need the divide by 2 ^ 32
            delay = (float(destination_timestamp) - float(source_timestamp)) / pow(2, 32)
            #round and add 0 to prevent -0.00
            delay_bucket = DELAY_BUCKET_FORMAT%(round(delay/bucket_width, DELAY_BUCKET_DIGITS) + 0)
            if delay_bucket in results['histogram-latency']:
                results['histogram-latency'][delay_bucket] += 1
            else:
                results['histogram-latency'][delay_bucket] = 1
                
            #TTL histogram
            if ttl in results['histogram-ttl']:
                results['histogram-ttl'][ttl] += 1
            else:
                results['histogram-ttl'][ttl] = 1
            
            #reorders
            if int(seq_number) < int(prev_seq_number):
                results['packets-reordered'] += 1
            prev_seq_number = seq_number
            
            #clock error
            if source_error and destination_error:
                clock_error = float(source_error) + float(destination_error)
                if ('max-clock-error' not in results) or (clock_error > results['max-clock-error']):
                    results['max-clock-error'] = clock_error

    #add packets lost for convenience
    results['packets-lost'] = results['packets-sent'] - results['packets-received']
    
    #convert clock error to ms
    if ('max-clock-error' in results):
        results['max-clock-error'] = round(results['max-clock-error']/TIME_SCALE, CLOCK_ERROR_DIGITS)
    
    results['succeeded'] = True
    
    return results
