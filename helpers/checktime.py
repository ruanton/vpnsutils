import concurrent.futures
import socket
import logging
import ntplib
import random
import time
import threading
from concurrent.futures import ThreadPoolExecutor

# local imports
from .misc import xdescr

TIMESHIFT_SECONDS_FATAL = 10;     """Time shift in seconds for the exception to be raised"""
TIMESHIFT_SECONDS_WARNING = 1;    """Time shift in seconds for the warning message to be logged"""
TIMEOUT_SOCKET_DEFAULT = 2;       """Timeout in seconds for network socket operations"""
NUM_MEASUREMENTS_REQUIRED = 5;    """Number of successful measurements required to assess time accuracy"""

_ntp_hostname_suffix = 'pool.ntp.org'
_ntp_hostname_country_parts = [
    '', 'europe.', 'at.', 'be.', 'bg.', 'by.', 'ch.', 'de.', 'dk.',
    'ee.', 'es.', 'fr.', 'gr.', 'it.', 'lv.', 'nl.', 'pl.', 'ru.', 'se.', 'uk.'
]
_ntp_servers = [f'{a}.{b}{_ntp_hostname_suffix}' for a in ['0', '1', '2', '3'] for b in _ntp_hostname_country_parts]
_ntp_servers_lock = threading.Lock();  """locker for changing the order of elements in the _ntp_servers"""

log = logging.getLogger(__name__)


class IncorrectSystemTimeError(RuntimeError):
    """The system time is incorrect compared to what was received via NTP"""


def verify_time_is_correct(wait=True, log_result=True, log_unresponsive=False) -> float | None:
    """
    Verifies that the system date/time matches that received via NTP.
    Raises IncorrectSystemTimeError if there is a mismatch.
    @param wait: wait until the required number of NTP servers give results.
    @param log_result: log the result to the standard Python logging system.
    @param log_unresponsive: log every time the NTP server does not respond.
    @return: time offset in seconds, the second-smallest result obtained using NTP servers, None if failed to measure.
    """
    while True:
        offset = _verify_time_is_correct_internal(log_unresponsive)
        if offset is not None or not wait:
            break

    if offset is not None and log_result:
        log.info(f'the system time is correct, current offset is {offset * 1000:.2f} ms')

    return offset


def _verify_time_is_correct_internal(log_unresponsive=True) -> float | None:
    """
    Verifies that the system date/time matches that received via NTP.
    Raises IncorrectSystemTimeError if there is a mismatch.
    @param log_unresponsive: log every time the NTP server does not respond.
    @return: time offset in seconds, the second-smallest result obtained using NTP servers, None if failed to measure.
    """
    num_servers = len(_ntp_servers)
    mid_idx = num_servers // 2
    indexes_priority = list(range(mid_idx));              """indexes of the first half of the list of NTP servers"""
    indexes_reserve = list(range(mid_idx, num_servers));  """indexes of the second half of the list of NTP servers"""

    random.shuffle(indexes_priority)
    random.shuffle(indexes_reserve)
    indexes_all = indexes_priority + indexes_reserve

    results: dict[str, float] = {};   """results of NTP requests, ipaddr => offset dictionary"""
    unresponsive_servers = set();     """hostnames of HTP servers that did not respond"""
    lock = threading.Lock();          """locker for updating measurement results and unresponsive servers"""

    def measure_time_offset(hostname: str):
        if len(results) >= NUM_MEASUREMENTS_REQUIRED:
            return  # we already have required number of measurement results

        try:
            ipaddr = socket.gethostbyname(hostname)
            if ipaddr in results:
                return  # we already have a measurement result for this IP

            client = ntplib.NTPClient()
            resp = client.request(ipaddr, timeout=TIMEOUT_SOCKET_DEFAULT)

        except Exception as e:
            if log_unresponsive:
                log.info(f'host: {hostname}, exception: {xdescr(e)}')
            with lock:
                unresponsive_servers.add(hostname)
            return  # silently return on any exception

        with lock:
            results[ipaddr] = abs(resp.offset)

    with ThreadPoolExecutor(max_workers=NUM_MEASUREMENTS_REQUIRED+2) as wp:
        with _ntp_servers_lock:
            futures: list[concurrent.futures.Future]
            futures = [wp.submit(measure_time_offset, _ntp_servers[x]) for x in indexes_all]

        while not all(x.done() for x in futures):
            if len(results) >= NUM_MEASUREMENTS_REQUIRED:
                wp.shutdown(wait=True, cancel_futures=True)
                break
            time.sleep(0.1)

    if len(results) < NUM_MEASUREMENTS_REQUIRED:
        log.warning(f'measurements required: {NUM_MEASUREMENTS_REQUIRED}, completed: {len(results)}')
        return None

    offsets = sorted(list(results.values()))
    offset = offsets[1]  # we take the second-smallest result

    if offset > TIMESHIFT_SECONDS_FATAL:
        raise IncorrectSystemTimeError(f'system time differs from NTP by {offset:.2f} seconds')
    if offset > TIMESHIFT_SECONDS_WARNING:
        log.warning(f'system time differs from NTP by {offset:.2f} seconds')

    if unresponsive_servers:
        # non-responsive servers where found, move their hostnames to the end of the list of NTP servers
        with _ntp_servers_lock:
            for h in unresponsive_servers:
                _ntp_servers.remove(h)
            _ntp_servers.extend(unresponsive_servers)
        assert len(_ntp_servers) == len(indexes_all)

    return offset
