###
# Utilities for talking to esmond


import pscheduler
import requests
import socket

#disable SSL warnings
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

log = pscheduler.Log(prefix="archiver-esmond", quiet=True)

DEFAULT_SUMMARIES = {
    "throughput": [
        {
            "summary-window":   86400,
            "event-type":   "throughput",
            "summary-type":   "average",
        },
    ],
    "packet-loss-rate": [
        {
            "summary-window":   300,
            "event-type":   "packet-loss-rate",
            "summary-type":   "aggregation",
        },
        {
            "summary-window":   3600,
            "event-type":   "packet-loss-rate",
            "summary-type":   "aggregation",
        },
        {
            "summary-window":   86400,
            "event-type":   "packet-loss-rate",
            "summary-type":   "aggregation",
        },
    ],
    "histogram-owdelay": [
        {
            "summary-window":   300,
            "event-type":   "histogram-owdelay",
            "summary-type":   "aggregation",
        },
        {
            "summary-window":   300,
            "event-type":   "histogram-owdelay",
            "summary-type":   "statistics",
        },
        {
            "summary-window":   3600,
            "event-type":   "histogram-owdelay",
            "summary-type":   "aggregation",
        },
        {
            "summary-window":   3600,
            "event-type":   "histogram-owdelay",
            "summary-type":   "statistics",
        },
        {
            "summary-window":   86400,
            "event-type":   "histogram-owdelay",
            "summary-type":   "aggregation",
        },
        {
            "summary-window":   86400,
            "event-type":   "histogram-owdelay",
            "summary-type":  "statistics",
        },
    ],
    "packet-loss-rate-bidir":[
        {
            "summary-window":   3600,
            "event-type":   "packet-loss-rate-bidir",
            "summary-type":   "aggregation",
        },
        {
            "summary-window":   86400,
            "event-type":   "packet-loss-rate-bidir",
            "summary-type":   "aggregation",
        },
    ],
    "histogram-rtt": [
        {
            "summary-window":   3600,
            "event-type":   "histogram-rtt",
            "summary-type":   "aggregation",
        },
    
        {
            "summary-window":   3600,
            "event-type":   "histogram-rtt",
            "summary-type":  "statistics",
        },
        {
            "summary-window":   86400,
            "event-type":   "histogram-rtt",
            "summary-type":   "aggregation",
        },
        {
            "summary-window":   86400,
            "event-type":   "histogram-rtt",
            "summary-type": "statistics",
        }
    ],
}


###
# Utility functions
def iso8601_to_seconds(val):
    td = pscheduler.iso8601_as_timedelta(val)
    return (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10.0**6) / 10.0**6

def get_ips(addr):
    ip_v4 = None
    ip_v6 = None
    try:
        addrinfo = socket.getaddrinfo(addr, None)
        for ai in addrinfo:
            if ai[0] == socket.AF_INET:
                ip_v4 = ai[4][0]
            elif ai[0] == socket.AF_INET6:
                ip_v6 = ai[4][0]
    except:
        pass
    return ip_v4, ip_v6
    
def normalize_ip_versions(src, dest, ip_version=None):
    src_ip = None
    dest_ip = None
    src_ip_v4, src_ip_v6 = get_ips(src)
    dest_ip_v4, dest_ip_v6 = get_ips(dest)
    #prefer v6 if not specified
    if not ip_version or ip_version == 6:
       if src_ip_v6 and dest_ip_v6:
            src_ip = src_ip_v6
            dest_ip = dest_ip_v6
    if not src_ip or not dest_ip or ip_version == 4:
        if src_ip_v4 and dest_ip_v4:
            src_ip = src_ip_v4
            dest_ip = dest_ip_v4

    return src_ip, dest_ip

def handle_storage_error(result, attempts=0, policy=[]):
    #build object
    retry = False
    archive_err_result = { 'succeeded': False, 'error': result }
    policy_attempt_sum = 0
    for p in policy:
        policy_attempt_sum += p['attempts']
        if policy_attempt_sum > attempts:
            retry = True
            archive_err_result['retry'] = p['wait']
            break
    if retry:
        pscheduler.succeed_json(archive_err_result)
    else:
        pscheduler.fail("Archiver permanently abandoned registering test after %d attempt(s): %s" % (attempts+1, result))


###
# Utility classes
class EsmondClient:
    url = ""
    verify_ssl = False
    headers = {}
    
    def __init__(self, url="http://127.0.0.1/esmond/perfsonar/archive", 
                        auth_token=None, 
                        verify_ssl=False):
        self.url = url
        self.verify_ssl = verify_ssl
        self.headers = { 'Content-Type': 'application/json' }
        if auth_token:
            self.headers['Authorization'] = "Token %s" % auth_token
    
    def create_metadata(self, metadata):
        result = {}
        post_url = self.url
        if not post_url.endswith('/'):
            post_url += '/'
        log.debug("Posting metadata to %s: %s" % (post_url, metadata))
        r = requests.post(post_url, data=pscheduler.json_dump(metadata), headers=self.headers, verify=self.verify_ssl)
        if r.status_code != 200 and r.status_code != 201:
            try:
                return False, "%d: %s" % (r.status_code, pscheduler.json_load(r.text)['detail'])
            except:
                return False, "%d: %s" % (r.status_code, r.text)
        try:
            rjson = pscheduler.json_load(r.text)
            log.debug("Metadata POST result: %s" % rjson)
        except:
            return False, "Invalid JSON returned from server: %s" % r.text 
        
        return True, rjson
    
    def create_data(self, metadata_key, data_points):
        result = {}
        put_url = self.url
        if not put_url.endswith('/'):
            put_url += '/'
        put_url += ("%s/" % metadata_key)
        data = { 'data': data_points }
        log.debug("Putting data to %s: %s" % (put_url, data))
        r = requests.put(put_url, data=pscheduler.json_dump(data), headers=self.headers, verify=self.verify_ssl)
        if r.status_code== 409:
            #duplicate data
            log.debug("Attempted to add duplicate data point. Skipping")
        elif r.status_code != 200 and r.status_code != 201:
            try:
                return False, "%d: %s" % (r.status_code, pscheduler.json_load(r.text)['detail'])
            except:
                return False, "%d: %s" % (r.status_code, r.text)
        
        return True, ""

class EsmondBaseRecord:
    metadata ={}
    data = []
    
    def __init__(self,
                    test_spec=None,
                    lead_participant=None, 
                    tool_name=None,
                    summaries=None,
                    duration=None,
                    ts=None, 
                    test_result={},
                    src_field="source", 
                    dst_field="dest", 
                    ipv_field="ip-version",
                    succeeded_field="succeeded",
                    error_field="error"
                ):
        #init
        self.metadata = { 'subject-type': 'point-to-point', 'event-types': [] }
    
        #determine source since its optional
        input_source = lead_participant
        if src_field in test_spec:
            input_source = test_spec[src_field]
        
        #get dest - should be required
        input_dest = test_spec[dst_field]
    
        #determine if we are forcing an ip-version
        ip_version = None
        if ipv_field in test_spec:
            ip_version = test_spec[ipv_field]
        
        #normalize ips
        src_ip, dest_ip = normalize_ip_versions(input_source, input_dest, ip_version=ip_version)
    
        #set fields
        self.metadata['source'] = src_ip
        self.metadata['destination'] = dest_ip
        self.metadata['input-source'] = input_source
        self.metadata['input-destination'] = input_dest
        self.metadata['tool-name'] = tool_name
        self.metadata['time-duration'] = duration
        #Make measurement-agent the lead participant, with same ip type as source
        src_ip, self.metadata['measurement-agent'] = normalize_ip_versions(src_ip, lead_participant)
    
        #Handle event types
        summary_map = DEFAULT_SUMMARIES
        if summaries:
            summary_map = summaries
        for et in self.get_event_types(test_spec=test_spec):
            self.add_event_type(et, summary_map)
        
        #add extra metadata fields
        self.add_metadata_fields(test_spec=test_spec)
        self.add_additional_metadata(test_spec=test_spec)
        
        #handle data 
        data_point = { 'ts': ts, 'val': [] }
        if test_result[succeeded_field]:
            data_field_map = self.get_data_field_map()
            for field in data_field_map:
                if field in test_result:
                    data_point['val'].append({ 'event-type': data_field_map[field], 'val': test_result[field]})
            self.add_additional_data(data_point=data_point, test_spec=test_spec, test_result=test_result)
            
        else:
            #run failed, record the results
            msg = ""
            if error_field in test_result and test_result[error_field]:
                msg = test_result[error_field]
            else:
                msg = "The test failed for an unspecified reason. See the server logs of the testing host(s)."
            data_point['val'].append({ 'event-type': 'failures', 'val': { 'error': msg }})
        
        self.data.append(data_point)
    
    def add_metadata_fields(self, test_spec={}):
        field_map = self.get_metadata_field_map()
        for field in field_map:
            if field in test_spec:
                self.metadata[field_map[field]] = test_spec[field]
    
    def add_event_type(self, event_type, summaries):
        et = { "event-type": event_type }
        if event_type in summaries:
            et["summaries"] = summaries[event_type]
        self.metadata['event-types'].append(et)
    
    def add_data(self, data_point={}, event_type=None, val=None):
        data_point['val'].append({ 'event-type': event_type, 'val': val})
    
    def add_data_if_exists(self, data_point={}, event_type=None, obj={}, field=""):
        if field in obj and obj[field] is not None:
            data_point['val'].append({ 'event-type': event_type, 'val': obj[field]})
        
    def add_data_rate(self, data_point={}, event_type=None, test_result={}, numerator='', denominator=''):
        rate = 0
        if (numerator not in test_result) or (denominator not in test_result) or (test_result[numerator] is None) or (test_result[denominator] is None):
            return
        try:
            int(test_result[numerator])
            if int(test_result[denominator]) == 0: return 
        except:
            return
        data_point['val'].append({ 'event-type': event_type, 
                                    'val': {'numerator': test_result[numerator], 'denominator': test_result[denominator]}})

    ## Override
    def get_event_types(self, test_spec={}):
        return []
    def get_metadata_field_map(self):
        return {}
    def add_additional_metadata(self, test_spec={}):
        return
    def get_data_field_map(self):
        return {}
    def add_additional_data(self, data_point={}, test_spec={}, test_result={}):
        return
        

class EsmondLatencyRecord(EsmondBaseRecord):

    def get_event_types(self, test_spec={}):
        event_types = [
            'failures',
            'packet-count-sent',
            'histogram-owdelay',
            'histogram-ttl',
            'packet-duplicates',
            'packet-loss-rate',
            'packet-count-lost',
            'packet-reorders',
            'time-error-estimates'
        ]
        return event_types
        
    def get_metadata_field_map(self):
        field_map = {
            "packet-count":  "sample-size", 
            "bucket-width":  "sample-bucket-width", 
            "packet-interval": "time-probe-interval", 
            "packet-timeout": "time-probe-timeout", 
            "ip-tos": "ip-tos", 
            "flip": "mode-flip", 
            "packet-padding": "ip-packet-padding", 
            "single-participant-mode": "mode-single-participant"
        }
        return field_map
        
    def get_data_field_map(self):
        field_map = {
            'histogram-latency': 'histogram-owdelay',
            'histogram-ttl': 'histogram-ttl',
            'packets-sent': 'packet-count-sent',
            'packets-lost': 'packet-count-lost',
            'packets-reordered': 'packet-reorders',
            'packets-duplicated': 'packet-duplicates',
            'max-clock-error': 'time-error-estimates'
        }
        return field_map
        
    def add_additional_data(self, data_point={},  test_spec={}, test_result={}):
        self.add_data_rate(
            data_point=data_point,
            event_type='packet-loss-rate',
            test_result=test_result, 
            numerator='packets-lost',
            denominator='packets-sent')

class EsmondThroughputRecord(EsmondBaseRecord):

    def get_event_types(self, test_spec={}):
        event_types = [
            'failures',
            'throughput',
            'throughput-subintervals',
        ]
        if 'parallel' in test_spec and test_spec['parallel'] > 1:
            event_types.append('streams-throughput')
            event_types.append('streams-throughput-subintervals')
        if 'udp' in test_spec and test_spec['udp']:
            event_types.append('packet-loss-rate')
            event_types.append('packet-count-lost')
            event_types.append('packet-count-sent')
        else:
            event_types.append('packet-retransmits')
            event_types.append('packet-retransmits-subintervals')
            if 'parallel' in test_spec and test_spec['parallel'] > 1:
                event_types.append('streams-packet-retransmits')
                event_types.append('streams-packet-retransmits-subintervals')
        return event_types
        
    def get_metadata_field_map(self):
        field_map = {
            'tos': 'ip-tos',
            'dscp': 'ip-dscp',
            'buffer-length': 'bw-buffer-size',
            'parallel': 'bw-parallel-streams',
            'bandwidth': 'bw-target-bandwidth',
            'window-size': 'tcp-window-size',
            'dynamic-window-size': 'tcp-dynamic-window-size',
            'mss': 'tcp-max-segment-size',
            'omit': 'bw-ignore-first-seconds',
        }
        return field_map
           
    def add_additional_metadata(self, test_spec={}):
        if 'udp' in test_spec and test_spec['udp']:
            self.metadata['ip-transport-protocol'] = 'udp'
        else:
            self.metadata['ip-transport-protocol'] = 'tcp'
        
    def add_additional_data(self, data_point={}, test_spec={}, test_result={}):
        if test_result.get("summary", None):
            if test_result["summary"].get("summary", None):
                summary = test_result["summary"]["summary"]
                self.add_data_if_exists(data_point=data_point, event_type="throughput", obj=summary, field="throughput-bits")
                if 'udp' in test_spec and test_spec['udp']:
                    self.add_data_if_exists(data_point=data_point, event_type="packet-count-sent", obj=summary, field="sent")
                    self.add_data_if_exists(data_point=data_point, event_type="packet-count-lost", obj=summary, field="lost")
                    self.add_data_rate(data_point=data_point, event_type="packet-loss-rate", test_result=summary, numerator='lost', denominator='sent')
            if test_result["summary"].get("streams", None):
                if 'parallel' in test_spec and test_spec['parallel'] > 1:
                    streams = test_result["summary"]["streams"]
                    streams.sort(key=lambda x: x["stream-id"])
                    streams_throughput = []
                    for stream in streams:
                        streams_throughput.append(stream.get("throughput-bits", None))
                    self.add_data(data_point=data_point, event_type="streams-throughput", val=streams_throughput)
        if test_result.get("intervals", None):
            throughput_intervals = []
            throughput_stream_intervals = {}
            for interval in test_result["intervals"]:
                if interval.get("summary", None):
                    start = interval["summary"].get("start", None)
                    end = interval["summary"].get("end", None)
                    if start is None or end is None:
                        continue
                    duration = end - start
                    throughput = interval["summary"].get("throughput-bits", None)
                    if throughput is not None:
                        throughput_intervals.append({ "start": start, "duration": duration, "val": throughput})
                if interval.get("streams", None):
                    if 'parallel' in test_spec and test_spec['parallel'] > 1:
                        for stream in interval["streams"]:
                            start = stream.get("start", None)
                            end = stream.get("end", None)
                            if start is None or end is None:
                                continue
                            duration = end - start
                            stream_id = stream.get("stream-id", None)
                            if stream_id is None:
                                continue
                            if stream_id not in throughput_stream_intervals:
                                throughput_stream_intervals[stream_id] = []
                            throughput = stream.get("throughput-bits", None)
                            if throughput is not None:
                                throughput_stream_intervals[stream_id].append({
                                    "start": start,
                                     "duration": duration, 
                                     "val": throughput
                                })
                        self.add_data(data_point=data_point, event_type="throughput-subintervals", val=throughput_intervals)
                        #TODO: sort this
                        formatted_tsi = []
                        sorted_streams = throughput_stream_intervals.keys()
                        sorted_streams.sort()
                        for id in sorted_streams:
                            formatted_tsi.append(throughput_stream_intervals[id])
                        self.add_data(data_point=data_point, event_type="streams-throughput-subintervals", val=formatted_tsi)

class EsmondTraceRecord(EsmondBaseRecord):            
    def get_event_types(self, test_spec={}):
        event_types = [
            'failures',
            'packet-trace',
            'path-mtu'
        ]
        return event_types
    
    def get_metadata_field_map(self):
        field_map = {
            "algorithm":   'trace-algorithm',
            "first-ttl":   'trace-first-ttl',
            "fragment":    'ip-fragment',
            "hops":        'trace-max-ttl',
            "length":      'ip-packet-size',
            "probe-type":  'ip-transport-protocol',
            "queries":     'trace-num-queries',
            "tos":         'ip-tos'
        }
        return field_map
    
    def add_additional_metadata(self, test_spec={}):
        if test_spec.get("sendwait", None):
            self.metadata["time-probe-interval"] = iso8601_to_seconds(test_spec["sendwait"])
        if test_spec.get("wait", None):
            self.metadata["time-test-timeout"] = iso8601_to_seconds(test_spec["wait"])
    
    def add_additional_data(self, data_point={}, test_spec={}, test_result={}):
        paths = test_result['paths']
        #Note: packet-trace only supports one path so just store first
        packet_trace_multi = []
        packet_trace = None
        mtu = None  # current mtu
        pmtu = None # path mtu
        for path in paths:
            formatted_path = []
            for (hop_num, hop) in enumerate(path):
                formatted_hop = {}
                formatted_hop['ttl'] = hop_num + 1
                formatted_hop['query'] = 1 #trace test doesn't support multiple  queries
                #determine success
                if hop.get("error", None):
                    formatted_hop['success'] = 0
                    formatted_hop['error-message'] = hop["error"]
                else:
                    formatted_hop['success'] = 1
                #figure out what other info we have
                if hop.get("ip", None): 
                    formatted_hop['ip'] = hop['ip']
                if hop.get("host", None): 
                    formatted_hop['host'] = hop['host']
                if hop.get("as", None): 
                    formatted_hop['as'] = hop['as']
                if ("rtt" in hop) and (hop["rtt"] is not None): 
                    formatted_hop['rtt'] = iso8601_to_seconds(hop['rtt'])*1000 #convert to ms
                if ("mtu" in hop) and (hop["mtu"] is not None): 
                    formatted_hop['mtu'] = hop["mtu"]
                    mtu = hop["mtu"]
                    if pmtu is None or pmtu > mtu: 
                        # set pmtu as minimum mtu observed
                        pmtu = mtu
                elif mtu is not None:
                    formatted_hop['mtu'] = mtu
                formatted_path.append(formatted_hop)
            #append formatted path to list of paths
            packet_trace_multi.append(formatted_path)
            #add first path as packet-trace path - need this for backward compatibility
            if not packet_trace:
                packet_trace = formatted_path
        
        #add data points
        if packet_trace:
            self.add_data(data_point=data_point, event_type="packet-trace", val=packet_trace)
        if pmtu is not None:
            self.add_data(data_point=data_point, event_type="path-mtu", val=pmtu)
        #if packet_trace_multi:
        #    self.add_data(data_point=data_point, event_type="packet-trace-multi", val=packet_trace_multi)

class EsmondRTTRecord(EsmondBaseRecord):     
    def get_event_types(self, test_spec={}):
        event_types = [
            'failures',
            'packet-count-sent',
            'histogram-rtt',
            'histogram-ttl-reverse',
            'packet-duplicates-bidir',
            'packet-loss-rate-bidir',
            'packet-count-lost-bidir',
            'packet-reorders-bidir'
        ]
        return event_types
    
    def get_metadata_field_map(self):
        field_map = {
            "count": "sample-size",
            "flowlabel": "ip-packet-flowlabel",
            "tos": "ip-tos",
            "length": "ip-packet-size",
            "ttl": "ip-ttl",
        }
        return field_map
    
    def add_additional_metadata(self, test_spec={}):
        if test_spec.get("interval", None):
            self.metadata["time-probe-interval"] = iso8601_to_seconds(test_spec["interval"])
        if test_spec.get("timeout", None):
            self.metadata["time-test-timeout"] = iso8601_to_seconds(test_spec["timeout"])
        if test_spec.get("deadline", None):
            self.metadata["time-probe-timeout"] = iso8601_to_seconds(test_spec["deadline"])
    
    def get_data_field_map(self):
        field_map = {
            'sent': 'packet-count-sent',
            'lost': 'packet-count-lost-bidir',
            'duplicates': 'packet-duplicates-bidir',
            'reorders': 'packet-reorders-bidir',
        }
        return field_map
        
    def add_additional_data(self, data_point={}, test_spec={}, test_result={}):
        #handle histograms
        histogram_rtt = {}
        histogram_ttl = {}
        for rt in test_result.get("roundtrips", []):
            if rt.get('rtt', None):
                rtt = "%.2f" % (iso8601_to_seconds(rt['rtt']) * 1000)
                if rtt in histogram_rtt:
                    histogram_rtt[rtt] += 1
                else:
                    histogram_rtt[rtt] = 1
            if rt.get('ttl', None):
                if rt['ttl'] in histogram_ttl:
                    histogram_ttl[rt['ttl']] += 1
                else:
                    histogram_ttl[rt['ttl']] = 1
        if histogram_rtt:
            self.add_data(data_point=data_point, event_type="histogram-rtt", val=histogram_rtt)
        if histogram_ttl:
            self.add_data(data_point=data_point, event_type="histogram-ttl-reverse", val=histogram_ttl)
        
        #handle packet loss rate
        self.add_data_rate(
            data_point=data_point,
            event_type='packet-loss-rate-bidir',
            test_result=test_result, 
            numerator='lost',
            denominator='sent')
                
