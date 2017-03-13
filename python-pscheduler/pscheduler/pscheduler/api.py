"""
Functions related to the pScheduler REST and Plugin APIs
"""

import multiprocessing
import multiprocessing.dummy
import socket
import threading
import urlparse
import uuid

# HACK: BWCTLBC
import os

from .psdns import *
from .psurl import *


def api_root():
    "Return the standard root location of the pScheduler hierarchy"
    return '/pscheduler'

def api_this_host():
    "Return a fully-qualified name for this host"
    return socket.getfqdn()


def __host_per_rfc_2732(host):
    "Format a host name or IP for a URL according to RFC 2732"

    try:
        socket.inet_pton(socket.AF_INET6, host)
        return "[%s]" % (host)
    except socket.error:
        return host  # Not an IPv6 address


def api_replace_host(url_text, replacement):
    "Replace the host portion of a URL"

    url = list(urlparse.urlparse(url_text))
    if replacement is not None:
        url[1] = __host_per_rfc_2732(replacement)
    return urlparse.urlunparse(url)



def api_url(host = None,
            path = None,
            port = None,
            protocol = 'https'
            ):
    """Format a URL for use with the pScheduler API."""

    host = api_this_host() if host is None else str(host)
    host = __host_per_rfc_2732(host)

    if path is not None and path.startswith('/'):
        path = path[1:]
    return protocol + '://' \
        + host \
        + ('' if port is None else (':' + str(port))) \
        + api_root() + '/'\
        + ('' if path is None else str(path))




def api_is_task(url):
    """Determine if a URL looks like a valid task URL"""
    # Note that this generates an extra array element because of the
    # leading slash.
    url_parts = urlparse.urlparse(url).path.split('/')

    if len(url_parts) != 4 \
            or (url_parts[:3] != ['', 'pscheduler', 'tasks' ]):
        return False

    try:
        uuid.UUID(url_parts[3])
    except ValueError:
        return False

    return True



def api_is_run(url):
    """Determine if a URL looks like a valid run URL"""
    # Note that this generates an extra array element because of the
    # leading slash.
    url_parts = urlparse.urlparse(url).path.split('/')
    if len(url_parts) != 6 \
            or (url_parts[:3] != ['', 'pscheduler', 'tasks' ]) \
            or (url_parts[4] != 'runs'):
        return False

    try:
        uuid.UUID(url_parts[3])
        uuid.UUID(url_parts[5])
    except ValueError:
        return False

    return True


def api_result_delimiter():
    """
    Return the delimiter to be used by background tests when producing
    multiple results.
    """
    return "---- pScheduler End Result ----"



def api_ping(host, timeout=3):
    """
    See if an API server is alive within a given timeout.  If 'host'
    is None, ping the local server.
    """
    if host is None:
        host = api_this_host()
    status, result = url_get("https://%s/pscheduler/api" % (host),
                             timeout=timeout, json=False, throw=False)
    return status == 200



def api_ping_list(hosts, timeout=None, threads=10):
    """
    Ping a list of hosts and return a list of their statuses.
    """

    if len(hosts) == 0:
        return {}

    # Work around a bug in 2.6
    # TODO: Get rid of this when 2.6 is no longer in the picture.
    if not hasattr(threading.current_thread(), "_children"):
        threading.current_thread()._children = weakref.WeakKeyDictionary()

    pool = multiprocessing.dummy.Pool(processes=min(len(hosts), threads))

    pool_args = [(host, timeout) for host in hosts]
    result = {}

    def ping_one(arg):
        host, timeout = arg
        return (host, api_ping(host, timeout=timeout))

    for host, state in pool.imap(
            ping_one,
            pool_args,
            chunksize=1):
        result[host] = state
    pool.close()
    return result



def api_ping_all_up(hosts, timeout=None):
    """
    Determine if all hosts in a list are up.
    """
    results = api_ping_list(hosts, timeout)

    for host in results:
        if not results[host]:
            return False
    return True



#
# TODO: Remove this when the backward-compatibility code is removed
#

def api_has_pscheduler(host, timeout=5, bind=None):
    """
    Determine if pScheduler is running on a host
    """
    # Null implies localhost
    if host is None:
        host = "localhost"


    # Make sure the address resolves, otherwise url_get will return
    # non-200.

    resolved = None
    for ip_version in [ 4, 6 ]:
        resolved = pscheduler.dns_resolve(host,
                                          ip_version=ip_version,
                                          timeout=timeout)
        if resolved:
            break

    if not resolved:
        return False


    # HACK: BWTCLBC
    # If the environment says to bind to a certain address, do it.
    if bind is None:
        bind = os.environ.get('PSCHEDULER_LEAD_BIND_HACK', None)

    status, raw_spec = pscheduler.url_get(pscheduler.api_url(resolved),
                                          timeout=timeout,
                                          throw=False,
                                          bind=bind # HACK: BWTCLBC
                                          )

    return status == 200



from contextlib import closing


def api_has_bwctl(host):
    """
    Determine if a host is running the BWCTL daemon
    """

    # HACK: BWCTLBC
    #
    # Note that we don't do any binding in this function because BWCTL
    # does its control and test traffic from the same interface no
    # matter what.

    for family in [socket.AF_INET, socket.AF_INET6]:
        try:
            with closing(socket.socket(family, socket.SOCK_STREAM)) as sock:
                sock.settimeout(3)
                return sock.connect_ex((host, 4823)) == 0
        except socket.error:
            pass

    return False




if __name__ == "__main__":
    print api_url()
    print api_url(protocol='https')
    print api_url(host='host.example.com')
    print api_url(host='host.example.com', path='/both-slash')
    print api_url(host='host.example.com', path='both-noslash')
    print api_url(path='nohost')
    print
    print api_full_host()

    print api_has_bwctl(None)
    print api_has_pscheduler(None)
