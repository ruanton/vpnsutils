import argparse
import logging
import asyncio
import aiohttp
import pytz
import random
from datetime import datetime, timedelta
from urllib.parse import urlparse
from pyramid.paster import bootstrap, setup_logging
from pyramid_zodbconn import get_connection
from ZODB.Connection import Connection
from urllib3.exceptions import ProtocolError, HTTPError
from aiohttp.client_exceptions import ClientResponseError
from suid import utcnow
from pathlib import Path

# module import
from helpers.checktime import verify_time_is_correct
from helpers.misc import xdescr, json_dumps
from zmodels import tcm, get_app_root, AppRoot

# local imports
from .settings import settings
from . import sys_exit

log = logging.getLogger(__name__)

URI_CONFIG_DEFAULT = 'config/makerep.ini'


class TrafficStatsCollector(asyncio.TaskGroup):
    def __init__(self, urls: list[str], last_snapshots: dict[str, dict]):
        super().__init__()
        self.urls = urls
        self.last_snapshots = last_snapshots
        self.snapshots: dict[str, dict[datetime, dict]] = {};  """hostname => datetime => fetched snapshot"""

        connector = aiohttp.TCPConnector(limit_per_host=settings.aiohttp_limit_per_host)
        self.http_client = aiohttp.ClientSession(connector=connector, json_serialize=json_dumps, raise_for_status=True)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            await super().__aexit__(exc_type, exc_val, exc_tb)
        finally:
            await self.http_client.close()

    @staticmethod
    def pdot():
        print('.', end='', flush=True)

    @staticmethod
    def print_error():
        print('e', end='', flush=True)

    async def execute(self):
        for url in self.urls:
            self.create_task(self.fetch_url(url))

    async def fetch(self, url: str) -> dict:
        tries = settings.aiohttp_tries
        pause_initial = settings.aiohttp_retry_pause_initial
        retry_pause = random.uniform(pause_initial, pause_initial * 1.5)
        while True:
            try:
                resp = await self.http_client.get(url)
                try:
                    resp_json = await resp.json()
                except ValueError:
                    raise ProtocolError(f'response content is not Json')

                if resp.status != 200:
                    # this should never happen, as we set raise_on_status=True
                    raise RuntimeError(f'HTTP status: {resp.status}, URL: {url}')

                return resp_json

            except (aiohttp.ClientConnectorError, ProtocolError, HTTPError, ClientResponseError):
                self.print_error()
                if tries <= 0:
                    raise

            await asyncio.sleep(retry_pause)

            retry_pause *= settings.aiohttp_retry_pause_multiplier
            tries -= 1

    @staticmethod
    def verify_dir_item_get_name(item: dict, type_expected: str, name_min: str = None, name_max: str = None) -> str:
        item_type = item['type']
        if item_type != type_expected:
            raise RuntimeError(f'unexpected directory item type: {item_type}, expected: {type_expected}')

        item_name = item['name']
        if name_min and item_name < name_min:
            raise RuntimeError(f'unexpected directory item name: {item_name}, expected to be >= {name_min}')
        if name_max and item_name > name_max:
            raise RuntimeError(f'unexpected directory item name: {item_name}, expected to be <= {name_max}')

        return item_name

    async def fetch_url(self, url: str):
        hostname = urlparse(url).hostname
        last_snapshot = self.last_snapshots.get(hostname, None)
        last_datetime: datetime = datetime.fromisoformat(last_snapshot['__datetime']) if last_snapshot else None
        items = await self.fetch(url)
        self.pdot()
        for item in items:
            year = int(self.verify_dir_item_get_name(item, 'directory', '2024', '2500'))
            if last_datetime and year < last_datetime.year:
                # this year is earlier then the last saved snapshot in the database for this server
                continue
            self.create_task(self.fetch_year(hostname, url, year, last_datetime))

    async def fetch_year(self, hostname: str, url: str, year: int, last_dt: datetime):
        items = await self.fetch(f'{url}/{year}/')
        self.pdot()
        for item in items:
            month = int(self.verify_dir_item_get_name(item, 'directory', '01', '12'))
            if last_dt and year == last_dt.year and month < last_dt.month:
                # this month is earlier then the last saved snapshot in the database for this server
                continue
            self.create_task(self.fetch_month(hostname, url, year, month, last_dt))

    async def fetch_month(self, hostname: str, url: str, year: int, month: int, last_dt: datetime):
        items = await self.fetch(f'{url}/{year}/{month:02}/')
        self.pdot()
        for item in items:
            day = int(self.verify_dir_item_get_name(item, 'directory', '01', '31'))
            if last_dt and year == last_dt.year and month == last_dt.month and day < last_dt.day:
                # this day is earlier then the last saved snapshot in the database for this server
                continue
            self.create_task(self.fetch_day(hostname, url, year, month, day, last_dt))

    async def fetch_day(self, hostname: str, url: str, year: int, month: int, day: int, last_dt: datetime):
        items = await self.fetch(f'{url}/{year}/{month:02}/{day:02}/')
        self.pdot()
        for item in items:
            filename = self.verify_dir_item_get_name(item, 'file')
            filename_suffix = filename[-settings.snapshot_filename_suffix_length:]
            dt = datetime.strptime(filename_suffix, settings.snapshot_filename_suffix_format).replace(tzinfo=pytz.UTC)
            if last_dt and dt <= last_dt:
                # this snapshot is earlier then the last saved snapshot in the database for this server
                continue
            self.create_task(self.fetch_snapshot(hostname, url, year, month, day, filename))

    async def fetch_snapshot(self, hostname: str, url: str, year: int, month: int, day: int, filename: str):
        snapshot = await self.fetch(f'{url}/{year}/{month:02}/{day:02}/{filename}')
        self.pdot()
        dt_str = snapshot[settings.snapshot_dict_datetime_key]
        dt = datetime.fromisoformat(dt_str)
        self.snapshots[hostname] = self.snapshots.get(hostname, {})
        self.snapshots[hostname][dt] = snapshot


def save_amounts(appr: AppRoot, hostname: str, user_id: str, dt_prev: datetime, dt: datetime, am_down: int, am_up: int):
    # distribute amounts proportionally to the time intervals
    hour_dt = dt.replace(minute=0, second=0, microsecond=0);  """The hour the current snap belongs"""
    hour_dt_prev = dt_prev.replace(minute=0, second=0, microsecond=0);  """The hour that the prev snapshot belongs to"""

    hour = hour_dt_prev
    while hour <= hour_dt:
        dt_left = max(hour, dt_prev)
        dt_right = min(dt, hour + timedelta(hours=1))
        am_down_sec = am_down / (dt - dt_left).total_seconds()
        am_up_sec = am_up / (dt - dt_left).total_seconds()
        am_down_part = round(am_down_sec * (dt_right - dt_left).total_seconds())
        am_up_part = round(am_up_sec * (dt_right - dt_left).total_seconds())
        am_down -= am_down_part
        am_up -= am_up_part
        key = hour, hostname, user_id
        am_down_saved, am_up_saved = appr.tlog.get(key, (0, 0))
        appr.tlog[key] = (am_down_saved + am_down_part, am_up_saved + am_up_part)
        hour += timedelta(hours=1)


def parse_snap(appr: AppRoot, hostname: str, snap_current: dict, snap_prev: dict):
    dt = datetime.fromisoformat(snap_current[settings.snapshot_dict_datetime_key])
    dt_prev = datetime.fromisoformat(snap_prev[settings.snapshot_dict_datetime_key])

    for user_id, amounts in snap_current.items():
        if user_id in (settings.snapshot_dict_datetime_key, settings.snapshot_dict_comment_key):
            continue

        am_down, am_up = amounts
        am_down_prev, am_up_prev = snap_prev.get(user_id, (0, 0))

        if (am_down_prev > am_down or am_up_prev > am_up) or (am_down_prev == am_down and am_up_prev == am_up):
            # traffic statistics have been reset for this VPN user on this hostname, or no user traffic
            continue

        am_down -= am_down_prev
        am_up -= am_up_prev

        save_amounts(appr, hostname, user_id, dt_prev, dt, am_down, am_up)


def parse_snaps(appr: AppRoot, hostname: str, snaps: dict[datetime, dict]):
    snap_prev = appr.last_snapshots.get(hostname, None)
    dt_prev = datetime.fromisoformat(snap_prev[settings.snapshot_dict_datetime_key]) if snap_prev else None

    for dt, snap_current in sorted(snaps.items()):
        if dt_prev and dt_prev > dt:
            raise RuntimeError(f'hostname={hostname}, dt_prev={dt_prev.isoformat()}, dt={dt.isoformat()}')

        if dt_prev and (dt - dt_prev).total_seconds() > 3600 + 1800:
            num_missed = int(((dt - dt_prev).total_seconds() - 1800) // 3600)
            msg_snaps_missed = f'{hostname}: missed {num_missed} snapshot(s) before {dt:%Y%m%d-%H%M}'
            log.warning(msg_snaps_missed)
            appr.issues[utcnow()] = msg_snaps_missed

        if snap_prev:
            parse_snap(appr, hostname, snap_current, snap_prev)

        snap_prev = snap_current
        dt_prev = dt

    appr.last_snapshots[hostname] = snap_prev  # save the latest snapshot for this hostname


async def make_report(conn: Connection):
    with tcm.in_transaction(conn):
        appr = get_app_root(conn)

        collector = TrafficStatsCollector(urls=settings.urls_traffic_snapshots, last_snapshots=appr.last_snapshots)
        log.info(f'collecting traffic snapshots from {len(settings.urls_traffic_snapshots)} servers')

        print('Fetching ', end='')
        async with collector:
            await collector.execute()
        print(' DONE')

        if collector.snapshots:
            log.info(f'parsing {sum([len(x) for _, x in collector.snapshots.items()])} received snapshots')
            for hostname, snaps in collector.snapshots.items():
                parse_snaps(appr, hostname, snaps)

            log.info(f'parsed')

        else:
            log.info(f'there are no new snapshots')

    uid_to_bytes = {}

    with tcm.in_transaction(conn):
        appr = get_app_root(conn)

        dt_from = utcnow() - timedelta(days=7)
        key_min = (dt_from, '', '')
        # noinspection PyArgumentList
        for k, v in appr.tlog.items(min=key_min):
            uid = k[2].split('-')[0]
            uid_to_bytes[uid] = uid_to_bytes.get(uid, 0) + v[0] + v[1]

    arr_stats = [
        (k, round(v / 1024 / 1024 / 1024, ndigits=2))
        for k, v in sorted(uid_to_bytes.items(), key=lambda x: x[1], reverse=True)
    ]
    arr_issues = [(x.isoformat(), v) for x, v in appr.issues.items()]

    str_report = json_dumps({
        'stats': arr_stats,
        'issues': arr_issues
    })

    path_out = Path(settings.dir_report)
    path_out.mkdir(parents=True, exist_ok=True)

    filename = 'report.json'
    filepath_tmp = path_out.joinpath(f'{filename}.tmp')
    filepath = path_out.joinpath(filename)

    log.info(f'writing to: {filepath_tmp}')
    with filepath_tmp.open(mode='w', encoding='utf-8') as f:
        f.write(str_report)
    filepath_tmp.rename(filepath)
    log.info(f'saved to: {filepath}')


def main():
    try:
        parser = argparse.ArgumentParser(
            description='Collects traffic statistics from several VPN servers and makes a report.'
        )
        parser.add_argument(
            'config_uri', default=URI_CONFIG_DEFAULT, nargs='?',
            help='The URI to the configuration file.'
        )
        args = parser.parse_args()

        # setup logging from config file settings
        setup_logging(args.config_uri)

        # bootstrap Pyramid environment to get configuration
        with bootstrap(args.config_uri) as env:
            # compares the local time with the time received from the NTP servers
            # throws an exception if it differs significantly
            verify_time_is_correct(diff_fatal=settings.max_allowable_time_drift)

            log.debug('get database connection and run asyncio loop')
            asyncio.run(make_report(conn=get_connection(request=env['request'])))

    except KeyboardInterrupt as ex:
        print(f'{xdescr(ex)}')
        sys_exit(130)

    except Exception as ex:
        log.error(f'{xdescr(ex)}')
        exit(1)


if __name__ == '__main__':
    main()
