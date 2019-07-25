"""
Functions related to the pScheduler REST and Plugin APIs
"""

import calendar
import pscheduler
import urlparse


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
    "packet-count-sent": [
        {
            "summary-window":   300,
            "event-type":   "packet-count-sent",
            "summary-type":   "aggregation",
        },
        {
            "summary-window":   3600,
            "event-type":   "packet-count-sent",
            "summary-type":   "aggregation",
        },
        {
            "summary-window":   86400,
            "event-type":   "packet-count-sent",
            "summary-type":   "aggregation",
        },
    ],
    "packet-count-lost": [
        {
            "summary-window":   300,
            "event-type":   "packet-count-lost",
            "summary-type":   "aggregation",
        },
        {
            "summary-window":   3600,
            "event-type":   "packet-count-lost",
            "summary-type":   "aggregation",
        },
        {
            "summary-window":   86400,
            "event-type":   "packet-count-lost",
            "summary-type":   "aggregation",
        },
    ],
    "packet-count-lost-bidir": [
        {
            "summary-window":   300,
            "event-type":   "packet-count-lost-bidir",
            "summary-type":   "aggregation",
        },
        {
            "summary-window":   3600,
            "event-type":   "packet-count-lost-bidir",
            "summary-type":   "aggregation",
        },
        {
            "summary-window":   86400,
            "event-type":   "packet-count-lost-bidir",
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
            "summary-window":   0,
            "event-type":   "histogram-owdelay",
            "summary-type":   "statistics",
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
            "summary-window":   0,
            "event-type":   "histogram-rtt",
            "summary-type": "statistics",
        },
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
# TODO: Doesn't the pScheduler module have a function that does this?
def iso8601_to_seconds(val):
    td = pscheduler.iso8601_as_timedelta(val)
    return (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10.0**6) / 10.0**6




class EsmondBaseRecord:
    test_type = None
    
    def __init__(self,
                    test_type=None,
                    test_spec=None,
                    reference={},
                    lead_participant=None, 
                    measurement_agent=None, 
                    tool_name=None,
                    run_href=None,
                    summaries=None,
                    duration=None,
                    ts=None, 
                    test_result={},
                    src_field="source", 
                    dst_field="dest", 
                    ipv_field="ip-version",
                    succeeded_field="succeeded",
                    error_field="error",
                    fast_mode=False
                ):
        #init
        self.metadata = { 'event-types': [] }
        self.data = []
        
        if not fast_mode:
            #determine if we are forcing an ip-version
            ip_version = None
            if ipv_field in test_spec:
                ip_version = test_spec[ipv_field]
            
            #Figure out source, destination, and subject type    
            self.parse_addresses(test_spec, src_field, dst_field, ip_version, lead_participant, measurement_agent)
            
            #set misc fields
            self.metadata['tool-name'] = tool_name
            self.metadata['time-duration'] = duration
            
            #set test type to new value if provided
            if test_type:
                self.test_type = test_type
            #may be overridden by subclass, so use value even if not in constructor params
            if self.test_type:
                self.metadata['pscheduler-test-type'] = self.test_type
        
            #Handle event types
            summary_map = DEFAULT_SUMMARIES
            if summaries:
                summary_map = summaries
            for et in self.get_event_types(test_spec=test_spec):
                self.add_event_type(et, summary_map)
            if run_href:
                self.add_event_type('pscheduler-run-href', summary_map)
    
        #add extra metadata fields
        self.add_metadata_fields(test_spec=test_spec)
        self.add_additional_metadata(test_spec=test_spec)
        self.add_reference_metadata(reference=reference)
        
        #handle data 
        data_point = { 'ts': ts, 'val': [] }
        if succeeded_field in test_result and test_result[succeeded_field]:
            data_field_map = self.get_data_field_map()
            for field in data_field_map:
                if field in test_result:
                    if isinstance(test_result[field], dict) and not test_result[field]:
                        #esmond doesn't like empty dicts so skip
                        pass
                    else:
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
        #add run-href
        if run_href:
            data_point['val'].append({ 'event-type': 'pscheduler-run-href', 'val': { 'href': run_href }})
        
        self.data.append(data_point)
    
    def parse_addresses(self, test_spec, src_field, dst_field, ip_version, lead_participant, measurement_agent):
            #determine source since its optional
            input_source = lead_participant
            if src_field and src_field in test_spec:
                input_source = test_spec[src_field]
            
            #get dest if this is point-to-point
            dest_ip = None
            if dst_field:
                self.metadata['subject-type'] = 'point-to-point'
                self.metadata['input-destination'] = test_spec[dst_field]
                src_ip, dest_ip = pscheduler.ip_normalize_version(input_source, self.metadata['input-destination'], ip_version=ip_version)
            else:
                self.metadata['subject-type'] = 'network-element'
                src_ip, tmp_ip = pscheduler.ip_normalize_version(input_source, input_source, ip_version=ip_version)
            
            #set fields
            self.metadata['source'] = src_ip
            if dest_ip:
                self.metadata['destination'] = dest_ip
            self.metadata['input-source'] = input_source

            #Make measurement-agent the created_by_address if we have it, otherwise the lead participant, with same ip type as source
            if measurement_agent:
                src_ip, self.metadata['measurement-agent'] = pscheduler.ip_normalize_version(src_ip, measurement_agent)
            else:
                src_ip, self.metadata['measurement-agent'] = pscheduler.ip_normalize_version(src_ip, lead_participant)
    
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

    def enable_data_raw(self, test_result={}, data_index=0):
        self.add_event_type('pscheduler-raw', {})
        self.add_data(data_point=self.data[data_index], event_type='pscheduler-raw', val=test_result)
    
    def parse_metadata_field(self, key, val):
        if type(val) is list:
            for (i, v) in enumerate(val):
                k = "%s-%d" % (key, i)
                self.metadata[k] = v
        elif type(val) is dict:
            for sub_key in val:
                if sub_key.startswith('_'):
                    continue
                k = "%s-%s" % (key, sub_key)
                self.parse_metadata_field(k, val[sub_key])
        else:
            self.metadata[key] = val
            
    def add_reference_metadata(self, reference={}):
        if reference is None:
            return
        
        for field in reference:
            if field.startswith('_'):
                continue
            key = "pscheduler-reference-%s" % (field)
            val = reference[field]
            self.parse_metadata_field(key, val)
            
    ## Override
    def set_test(self, test_spec={}):
        return []
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
        
class EsmondDiskToDiskRecord(EsmondBaseRecord):
    test_type = 'disk-to-disk'
    
    def get_event_types(self, test_spec={}):
        event_types = [
            'failures',
            'throughput'
        ]
        return event_types
    
    # The source and dest are URls, so need special processing
    def parse_addresses(self, test_spec, src_field, dst_field, ip_version, lead_participant, measurement_agent):
        src_ip=None
        dest_ip=None
        input_source = lead_participant
        input_dest = lead_participant
        self.metadata['subject-type'] = 'point-to-point'
        
        #get source field from URL, then try measurement agent, then fallback to lead
        if src_field and src_field in test_spec:
            source_url = test_spec[src_field]
            source_url_host = urlparse.urlparse(test_spec[src_field]).hostname
            if source_url_host:
                input_source = source_url_host
            elif measurement_agent:
                input_source = measurement_agent
        
        #do same thingv we did for source but for dest
        if dst_field and dst_field in test_spec:
            dest_url = test_spec[dst_field]
            dest_url_host = urlparse.urlparse(test_spec[dst_field]).hostname
            if dest_url_host:
                input_dest = dest_url_host
            elif measurement_agent:
                input_dest = measurement_agent
        
        #normalize ips
        src_ip, dest_ip = pscheduler.ip_normalize_version(input_source, input_dest, ip_version=ip_version)
        
        # set fields
        self.metadata['source'] = src_ip
        self.metadata['destination'] = dest_ip
        self.metadata['input-source'] = input_source
        self.metadata['input-destination'] = input_dest
        
        #Normalize the measurement agent IP and fallback to lead if not set
        if measurement_agent:
            src_ip, self.metadata['measurement-agent'] = pscheduler.ip_normalize_version(src_ip, measurement_agent)
        else:
            src_ip, self.metadata['measurement-agent'] = pscheduler.ip_normalize_version(src_ip, lead_participant)


    def add_additional_metadata(self, test_spec={}):
        for field in test_spec:
            key = "pscheduler-%s-%s" % (self.test_type, field)
            val = test_spec[field]
            self.parse_metadata_field(key, val)
            
    def get_metadata_field_map(self):
        field_map = {
            'parallel': 'bw-parallel-streams',
        }
        return field_map
        
    def add_additional_data(self, data_point={}, test_spec={}, test_result={}):
        if 'throughput' in test_result and test_result['throughput'] is not None:
            normalized_tput=float(test_result['throughput'])
            data_point['val'].append({ 'event-type': 'throughput', 'val': normalized_tput})
            
class EsmondLatencyRecord(EsmondBaseRecord):
    test_type = 'latency'
    
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

class EsmondLatencyBGRecord(EsmondLatencyRecord):
    test_type = 'latencybg'
    
class EsmondThroughputRecord(EsmondBaseRecord):
    test_type = 'throughput'
    
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
        is_udp =  test_spec.get('udp', False)
        if test_result.get("summary", None):
            if test_result["summary"].get("summary", None):
                summary = test_result["summary"]["summary"]
                self.add_data_if_exists(data_point=data_point, event_type="throughput", obj=summary, field="throughput-bits")
                if is_udp:
                    self.add_data_if_exists(data_point=data_point, event_type="packet-count-sent", obj=summary, field="sent")
                    self.add_data_if_exists(data_point=data_point, event_type="packet-count-lost", obj=summary, field="lost")
                    self.add_data_rate(data_point=data_point, event_type="packet-loss-rate", test_result=summary, numerator='lost', denominator='sent')
                else:
                    self.add_data_if_exists(data_point=data_point, event_type="packet-retransmits", obj=summary, field="retransmits")
                    self.add_data_if_exists(data_point=data_point, event_type="packet-rtt", obj=summary, field="rtt")
                    self.add_data_if_exists(data_point=data_point, event_type="tcp-windowsize", obj=summary, field="tcp-window-size")
            if test_result["summary"].get("streams", None):
                if 'parallel' in test_spec and test_spec['parallel'] > 1:
                    streams = test_result["summary"]["streams"]
                    streams.sort(key=lambda x: x["stream-id"])
                    streams_throughput = []
                    streams_packet_retransmits = []
                    streams_packet_rtt = []
                    streams_packet_tcp_windowsize = []
                    for stream in streams:
                        streams_throughput.append(stream.get("throughput-bits", None))
                        if stream.get("retransmits", None):
                            streams_packet_retransmits.append(stream["retransmits"])
                        if stream.get("rtt", None):
                            streams_packet_rtt.append(stream["rtt"])
                        if stream.get("tcp-window-size", None):
                            streams_packet_tcp_windowsize.append(stream["tcp-window-size"])
                    self.add_data(data_point=data_point, event_type="streams-throughput", val=streams_throughput)
                    if not is_udp:
                        if len(streams_packet_retransmits) > 0:
                            self.add_data(data_point=data_point, event_type="streams-packet-retransmits", val=streams_packet_retransmits)
                        if len(streams_packet_rtt) > 0:
                            self.add_data(data_point=data_point, event_type="streams-packet-rtt", val=streams_packet_rtt)
                        if len(streams_packet_tcp_windowsize) > 0:
                            self.add_data(data_point=data_point, event_type="streams-tcp-windowsize", val=streams_packet_tcp_windowsize)
                            
        if test_result.get("intervals", None):
            throughput_intervals = []
            retransmits_intervals = []
            rtt_intervals = []
            tcp_windowsize_intervals = []
            throughput_stream_intervals = {}
            retransmit_stream_intervals = {}
            rtt_stream_intervals = {}
            tcp_windowsize_stream_intervals = {}
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
                    retransmits = interval["summary"].get("retransmits", None)
                    if retransmits is not None:
                        retransmits_intervals.append({ "start": start, "duration": duration, "val": retransmits})
                    rtt = interval["summary"].get("rtt", None)
                    if rtt is not None:
                        rtt_intervals.append({ "start": start, "duration": duration, "val": rtt})
                    tcp_windowsize = interval["summary"].get("tcp-window-size", None)
                    if tcp_windowsize is not None:
                        tcp_windowsize_intervals.append({ "start": start, "duration": duration, "val": tcp_windowsize})
                if interval.get("streams", None):
                    if 'parallel' in test_spec and test_spec['parallel'] > 1:
                        for stream in interval["streams"]:
                            start = stream.get("start", None)
                            end = stream.get("end", None)
                            if start is None or end is None:
                                continue # pragma: no cover
                            duration = end - start
                            stream_id = stream.get("stream-id", None)
                            if stream_id is None:
                                continue # pragma: no cover
                            #throughput
                            if stream_id not in throughput_stream_intervals:
                                throughput_stream_intervals[stream_id] = []
                            throughput = stream.get("throughput-bits", None)
                            if throughput is not None:
                                throughput_stream_intervals[stream_id].append({
                                    "start": start,
                                     "duration": duration, 
                                     "val": throughput
                                })
                            #retransmits
                            if stream_id not in retransmit_stream_intervals:
                                retransmit_stream_intervals[stream_id] = []
                            retransmits = stream.get("retransmits", None)
                            if retransmits is not None:
                                retransmit_stream_intervals[stream_id].append({
                                    "start": start,
                                     "duration": duration, 
                                     "val": retransmits
                                })
                            #rtt
                            if stream_id not in rtt_stream_intervals:
                                rtt_stream_intervals[stream_id] = []
                            rtt = stream.get("rtt", None)
                            if rtt is not None:
                                rtt_stream_intervals[stream_id].append({
                                    "start": start,
                                     "duration": duration, 
                                     "val": rtt
                                })
                            #tcp windowsize
                            if stream_id not in tcp_windowsize_stream_intervals:
                                tcp_windowsize_stream_intervals[stream_id] = []
                            tcp_window_size = stream.get("tcp-window-size", None)
                            if tcp_window_size is not None:
                                tcp_windowsize_stream_intervals[stream_id].append({
                                    "start": start,
                                     "duration": duration, 
                                     "val": tcp_window_size
                                })
            #add types               
            if len(throughput_intervals) > 0:
                self.add_data(data_point=data_point, event_type="throughput-subintervals", val=throughput_intervals)
            if throughput_stream_intervals > 0:
                formatted_tsi = []
                sorted_streams = throughput_stream_intervals.keys()
                sorted_streams.sort()
                for id in sorted_streams:
                    formatted_tsi.append(throughput_stream_intervals[id])
                self.add_data(data_point=data_point, event_type="streams-throughput-subintervals", val=formatted_tsi)
            if not is_udp:
                if len(retransmits_intervals) > 0:
                    self.add_data(data_point=data_point, event_type="packet-retransmits-subintervals", val=retransmits_intervals)
                if len(rtt_intervals) > 0:
                    self.add_data(data_point=data_point, event_type="packet-rtt-subintervals", val=rtt_intervals)
                if len(tcp_windowsize_intervals) > 0:
                    self.add_data(data_point=data_point, event_type="tcp-windowsize-subintervals", val=tcp_windowsize_intervals)
                if retransmit_stream_intervals > 0:
                    formatted_rsi = []
                    sorted_streams = retransmit_stream_intervals.keys()
                    sorted_streams.sort()
                    for id in sorted_streams:
                        formatted_rsi.append(retransmit_stream_intervals[id])
                    self.add_data(data_point=data_point, event_type="streams-packet-retransmits-subintervals", val=formatted_rsi)
                if rtt_stream_intervals > 0:
                    formatted_rttsi = []
                    sorted_streams = rtt_stream_intervals.keys()
                    sorted_streams.sort()
                    for id in sorted_streams:
                        formatted_rttsi.append(rtt_stream_intervals[id])
                    self.add_data(data_point=data_point, event_type="streams-packet-rtt-subintervals", val=formatted_rttsi)
                if tcp_windowsize_stream_intervals > 0:
                    formatted_twssi = []
                    sorted_streams = tcp_windowsize_stream_intervals.keys()
                    sorted_streams.sort()
                    for id in sorted_streams:
                        formatted_twssi.append(tcp_windowsize_stream_intervals[id])
                    self.add_data(data_point=data_point, event_type="streams-tcp-windowsize-subintervals", val=formatted_twssi)

                

class EsmondTraceRecord(EsmondBaseRecord):   
    test_type = 'trace'
             
    def get_event_types(self, test_spec={}):
        event_types = [
            'failures',
            'packet-trace',
            'path-mtu'
        ]
        if "paris-traceroute" == test_spec.get('algorithm', ''):
            event_types.append('packet-trace-multi')
            
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
                if hop.get("hostname", None): 
                    formatted_hop['hostname'] = hop['hostname']
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
        if "paris-traceroute" == test_spec.get('algorithm', '') and packet_trace_multi:
            self.add_data(data_point=data_point, event_type="packet-trace-multi", val=packet_trace_multi)

class EsmondRTTRecord(EsmondBaseRecord):  
    test_type = 'rtt'
       
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

class EsmondRawRecord(EsmondBaseRecord):
    
    def get_event_types(self, test_spec={}):
        event_types = [
            'pscheduler-raw'
        ]
        return event_types
            
    def add_additional_metadata(self, test_spec={}):
        #this should not happen
        if not self.test_type:
            raise RuntimeError("No type set for raw record.")
            
        for field in test_spec:
            key = "pscheduler-%s-%s" % (self.test_type, field)
            val = test_spec[field]
            self.parse_metadata_field(key, val)
            
    def add_additional_data(self, data_point={}, test_spec={}, test_result={}):
        self.add_data(data_point=data_point, event_type='pscheduler-raw', val=test_result)




def pscheduler_to_esmond(json):

    task_href = json.get('task-href', '').encode("utf-8") #encode to utf-8 so memcache can handle i
    run_href = json.get('run-href', '').encode("utf-8")
    test_type = json['result']['test']['type']
    test_spec = json['result']['test']['spec']
    reference = json['result'].get('reference', {})
    test_result = {}
    if json['result']['result'] is not None:
        test_result = json['result']['result']
    tool_name = 'pscheduler/%s' % json['result']['tool']['name']
    test_start_time = calendar.timegm(pscheduler.iso8601_as_datetime(json['result']['schedule']['start']).utctimetuple())
    lead_participant = json['result']['participants'][0]
    duration = iso8601_to_seconds(json['result']['schedule']['duration'])
    try:
        url = json['data']['url']
    except KeyError:
        return {
            "succeeded": False,
            "error": "You must provide the URL of the Esmond archive"
        }

    #Get security and auth-related optional fields
    auth_token = None
    if "_auth-token" in json['data']:
        auth_token = json['data']['_auth-token']
    verify_ssl=False
    if "verify-ssl" in json['data']:
        verify_ssl = json['data']['verify-ssl']
    try:
        bind = json['data']['bind']
    except KeyError:
        bind = None

    #get explicit measurement-agent if se
    measurement_agent = None
    if "measurement-agent" in json['data']:
        measurement_agent = json['data']['measurement-agent']

    #get fields related to data formatting
    format_mapping = True
    add_raw_event_type = False
    fallback_raw = True
    if "data-formatting-policy" in json['data']:
        if json['data']['data-formatting-policy'] == 'prefer-mapped':
            pass # this is the defaul
        elif json['data']['data-formatting-policy'] == 'mapped-and-raw':
            add_raw_event_type = True
        elif json['data']['data-formatting-policy'] == 'mapped-only':
            fallback_raw = False
        elif json['data']['data-formatting-policy'] == 'raw-only':
            format_mapping = False

    #setup default data summaries
    summary_map = None
    if "summaries" in json['data'] and json['data']['summaries']:
        summary_map = {}
        for summary in json['data']['summaries']:
            if "event-type" not in summary:
                continue
            if summary["event-type"] not in summary_map:
                summary_map[summary["event-type"]] = []
            summary_map[summary["event-type"]].append(summary)

    #prep retry policy
    try:
        attempts = int(json['attempts'])
    except:
        return {
            "succeeded": False,
            "error": "Archiver must be given 'attempts' as a valid integer"
        }
    retry_policy= []
    if 'retry-policy' in json['data']:
        retry_policy = json['data']['retry-policy']


    # TODO: Is this needed?
    ##lookup metadata key in cache
    #cache_key = ("%s@%s" % (task_href, url)).encode("utf-8") #encode to utf-8 so memcache can handle i
    #mc = memcache.Client(memcache_servers, debug=0)
    #metadata_key = mc.get(cache_key)
    metadata_key = None

    if metadata_key:
        fast_mode = True
    else:
        fast_mode = False


    #determine test type and format metadata and data
    record = None
    if format_mapping:
        if test_type == 'latency':
            record = EsmondLatencyRecord(
                test_spec=test_spec,
                reference=reference,
                lead_participant=lead_participant,
                measurement_agent=measurement_agent,
                tool_name=tool_name,
                summaries=summary_map,
                duration=duration,
                ts=test_start_time,
                test_result=test_result,
                run_href=run_href,
                fast_mode=fast_mode
            )
        elif test_type == 'latencybg':
            record = EsmondLatencyBGRecord(
                test_spec=test_spec,
                reference=reference,
                lead_participant=lead_participant,
                measurement_agent=measurement_agent,
                tool_name=tool_name,
                summaries=summary_map,
                duration=duration,
                ts=test_start_time,
                test_result=test_result,
                run_href=run_href,
                fast_mode=fast_mode
            )
        elif test_type == 'throughput':
            record = EsmondThroughputRecord(
                test_spec=test_spec,
                reference=reference,
                lead_participant=lead_participant,
                measurement_agent=measurement_agent,
                tool_name=tool_name,
                summaries=summary_map,
                duration=duration,
                ts=test_start_time,
                test_result=test_result,
                run_href=run_href,
                fast_mode=fast_mode
            )
        elif test_type == 'disk-to-disk':
            record = EsmondDiskToDiskRecord(
                test_spec=test_spec,
                reference=reference,
                lead_participant=lead_participant,
                measurement_agent=measurement_agent,
                tool_name=tool_name,
                summaries=summary_map,
                duration=duration,
                ts=test_start_time,
                test_result=test_result,
                run_href=run_href,
                fast_mode=fast_mode
            )
            #always store raw for this as well
            add_raw_event_type = True
        elif test_type == 'trace':
            record = EsmondTraceRecord(
                test_spec=test_spec,
                reference=reference,
                lead_participant=lead_participant,
                measurement_agent=measurement_agent,
                tool_name=tool_name,
                summaries=summary_map,
                duration=duration,
                ts=test_start_time,
                test_result=test_result,
                run_href=run_href,
                fast_mode=fast_mode
            )
        elif test_type == 'rtt':
            record = EsmondRTTRecord(
                test_spec=test_spec,
                reference=reference,
                lead_participant=lead_participant,
                measurement_agent=measurement_agent,
                tool_name=tool_name,
                summaries=summary_map,
                duration=duration,
                ts=test_start_time,
                test_result=test_result,
                run_href=run_href,
                fast_mode=fast_mode
            )
        elif fallback_raw:
            record = EsmondRawRecord(
                test_type=test_type,
                test_spec=test_spec,
                reference=reference,
                lead_participant=lead_participant,
                measurement_agent=measurement_agent,
                tool_name=tool_name,
                summaries=summary_map,
                duration=duration,
                ts=test_start_time,
                test_result=test_result,
                src_field=None,
                dst_field=None,
                run_href=run_href,
                fast_mode=fast_mode
            )
            #we already added raw type, so don't add it again
            add_raw_event_type = False
        else:
            return {
                "succeeded": False,
                "error": "Unable to store result because 'mapped-only' policy is being used and the test is of an unrecognized type %s" % (test_type)
            }
    else:
        record = EsmondRawRecord(
            test_type=test_type,
            test_spec=test_spec,
            reference=reference,
            lead_participant=lead_participant,
            measurement_agent=measurement_agent,
            tool_name=tool_name,
            summaries=summary_map,
            duration=duration,
            ts=test_start_time,
            test_result=test_result,
            src_field=None,
            dst_field=None,
            run_href=run_href,
            fast_mode=fast_mode
        )

    #add raw test result if it was requested we do so
    if add_raw_event_type:
        record.enable_data_raw(test_result=test_result)

    return (record.data, record.metadata)




if __name__ == "__main__":

    for record in [
        {u'last-attempt': None, u'attempts': 0, u'data': {u'retry-policy': [{'attempts': 2, 'wait': "PT10S"}, {'attempts': 1, 'wait': "PT60S"}], u'url': u'http://10.0.1.17/esmond/perfsonar/archive', u'_auth-token': u'74c67388ca1d3c48b3660bda88de9729ac2c6f07'}, u'result': {u'schedule': {u'duration': u'PT15S', u'start': u'2016-07-29T12:47:31-04:00'}, u'tool': {u'verion': u'1.0', u'name': u'owping'}, u'participants': [u'psched-dev2'], u'result': {u'max-clock-error': 1.9199999999999999, u'packets-duplicated': 0, u'succeeded': True, u'histogram-latency': {u'-0.33': 5, u'-0.28': 11, u'-0.29': 9, u'-0.24': 2, u'-0.25': 12, u'-0.26': 4, u'-0.27': 3, u'-0.20': 5, u'-0.21': 5, u'-0.22': 6, u'-0.23': 8, u'-0.43': 1, u'-0.40': 2, u'-0.15': 1, u'-0.32': 3, u'-0.31': 4, u'-0.30': 6, u'-0.41': 2, u'-0.36': 1, u'-0.35': 1, u'-0.34': 1, u'-0.39': 2, u'-0.38': 1, u'-0.19': 2, u'-0.17': 3}, u'histogram-ttl': {u'255': 100}, u'packets-sent': 100, u'packets-reordered': 0, u'packets-lost': 0, u'packets-received': 100, u'schema': 1}, u'test': {u'type': u'latency', u'spec': {u'dest': u'10.0.1.25', u'source': u'10.0.1.28', u'single-participant-mode': True, u'schema': 1}}, u'id': u'f9b66107-05ea-4e79-ac71-bb16f8f82e3c'}},

        {u'last-attempt': None, u'attempts': 0, u'data': {u'url': u'http://10.0.1.17/esmond/perfsonar/archive', u'_auth-token': u'74c67388ca1d3c48b3660bda88de9729ac2c6f07', u'retry-policy': [{u'attempts': 2, u'wait': u'PT10S'}, {u'attempts': 1, u'wait': u'PT30S'}]}, u'result': {u'schedule': {u'duration': u'PT15S', u'start': u'2016-07-31T11:48:18-04:00'}, u'tool': {u'verion': u'1.0', u'name': u'iperf'}, u'participants': [u'10.0.1.28', u'10.0.1.25'], u'result': {u'diags': u'------------------------------------------------------------\nClient connecting to 10.0.1.25, TCP port 5001\nTCP window size: 19.3 KByte (default)\n------------------------------------------------------------\n[  3] local 10.0.1.28 port 60318 connected with 10.0.1.25 port 5001\n[ ID] Interval       Transfer     Bandwidth\n[  3]  0.0-10.0 sec  2.30 GBytes  1.98 Gbits/sec\n', u'intervals': [], u'succeeded': True, u'summary': {u'streams': [{u'jitter': None, u'lost': None, u'stream-id': u'3', u'throughput-bytes': 2300000000.0, u'start': 0.0, u'end': 10.0, u'throughput-bits': 1980000000.0, u'sent': None}], u'summary': {u'jitter': None, u'lost': None, u'stream-id': u'3', u'throughput-bytes': 2300000000.0, u'start': 0.0, u'end': 10.0, u'throughput-bits': 1980000000.0, u'sent': None}}}, u'test': {u'type': u'throughput', u'spec': {u'source': u'10.0.1.28', u'dest': u'10.0.1.25', u'schema': 1}}, u'id': u'd05436cb-b4f3-44fb-9581-0ed5c1622868'}},


        {u'last-attempt': None, u'attempts': 0, u'data': {u'url': u'http://10.0.1.17/esmond/perfsonar/archive', u'_auth-token': u'74c67388ca1d3c48b3660bda88de9729ac2c6f07', 'data-formatting-policy': 'mapped-and-raw', u'retry-policy': [{u'attempts': 2, u'wait': u'PT10S'}, {u'attempts': 1, u'wait': u'PT30S'}]}, u'result': {u'schedule': {u'duration': u'PT8S', u'start': u'2016-07-29T20:54:14-04:00'}, u'tool': {u'verion': u'0.0', u'name': u'traceroute'}, u'participants': [u'psched-dev2'], u'result': {u'paths': [[{u'ip': u'10.0.1.25', u'rtt': u'PT0.0005S'}]], u'succeeded': True, u'schema': 1}, u'test': {u'type': u'trace', u'spec': {u'dest': u'10.0.1.25', u'schema': 1}}, u'id': u'58404bb5-8a72-459a-b118-12e879d9dc99'}},

        {"task-href": "ABC123", "last-attempt": None, "attempts": 0, "data": {"url": "http://10.0.1.39/esmond/perfsonar/archive", "_auth-token": "95c92a80295153503d34dec3e904539be266eede", "retry-policy": [{"attempts": 2, "wait": "PT10S"}, {"attempts": 1, "wait": "PT30S"}]}, "result": {"schedule": {"duration": "PT11S", "start": "2016-11-30T00:13:00-05:00"}, "tool": {"verion": "0.0", "name": "ping"}, "participants": ["psched-dev2"], "result": {"loss": 0.0, "succeeded": True, "lost": 0, "min": "PT0.000333S", "duplicates": 0, "max": "PT0.000624S", "received": 5, "reorders": 0, "stddev": "PT0.000104S", "roundtrips": [{"ip": "10.0.1.25", "length": 64, "ttl": 64, "seq": 1, "rtt": "PT0.000333S"}, {"ip": "10.0.1.25", "length": 64, "ttl": 64, "seq": 2, "rtt": "PT0.000421S"}, {"ip": "10.0.1.25", "length": 64, "ttl": 64, "seq": 3, "rtt": "PT0.000362S"}, {"ip": "10.0.1.25", "length": 64, "ttl": 64, "seq": 4, "rtt": "PT0.000624S"}, {"ip": "10.0.1.25", "length": 64, "ttl": 64, "seq": 5, "rtt": "PT0.000408S"}], "schema": 1, "sent": 5, "mean": "PT0.000429S"}, "test": {"type": "rtt", "spec": {"dest": "10.0.1.25", "schema": 1}}, "id": "ee1f2ee6-8c6b-45ee-b89a-8ee32a71b981"}}
    ]:
        (data, meta) = pscheduler_to_esmond(record)
        print
        print pscheduler.json_dump(data, pretty=True)




    pass
