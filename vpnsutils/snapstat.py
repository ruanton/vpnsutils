import argparse
import logging
from pyramid.paster import bootstrap, setup_logging
from py3xui import Api
from suid import utcnow
from pathlib import Path

# module import
from helpers.checktime import verify_time_is_correct
from helpers.misc import xdescr, json_dumps

# local imports
from .settings import settings
from . import sys_exit

log = logging.getLogger(__name__)

URI_CONFIG_DEFAULT = 'config/snapstat.ini'


def save_stats():
    stats = {}
    log.info(f'connecting to: {settings.xui_name}')
    api = Api(settings.xui_url, settings.xui_username, settings.xui_password)
    api.login()
    dt_stats = utcnow()
    inbounds = api.inbound.get_list()
    for inbound in inbounds:
        for cstats in inbound.client_stats:
            stats[cstats.email] = (cstats.down, cstats.up)

    stats[settings.snapshot_dict_datetime_key] = dt_stats
    stats[settings.snapshot_dict_comment_key] = 'client_id => [bytes downloaded, bytes uploaded]'

    str_stats = json_dumps(stats)
    path_out = Path(settings.dir_snapshots, f'{dt_stats:%Y/%m/%d}')
    path_out.mkdir(parents=True, exist_ok=True)
    filename = f'{settings.xui_name}-{dt_stats:{settings.snapshot_filename_suffix_format}}'
    filepath_tmp = path_out.joinpath(f'{filename}.tmp')
    filepath = path_out.joinpath(filename)
    log.info(f'writing to: {filepath_tmp}')
    try:
        with filepath_tmp.open(mode='w', encoding='utf-8') as f:
            f.write(str_stats)
        filepath_tmp.rename(filepath)

    finally:
        filepath_tmp.unlink(missing_ok=True)

    log.info(f'saved to: {filepath}')


def main():
    try:
        parser = argparse.ArgumentParser(
            description='Saves a snapshot of the traffic statistics of the local VPN server.'
        )
        parser.add_argument(
            'config_uri',
            default=URI_CONFIG_DEFAULT, nargs='?',
            help=f'The URI to the configuration file. Defaults to "{URI_CONFIG_DEFAULT}"'
        )
        args = parser.parse_args()

        # setup logging from config file settings
        setup_logging(args.config_uri)

        # bootstrap Pyramid environment to get configuration
        with bootstrap(args.config_uri):
            # compares the local time with the time received from the NTP servers
            # throws an exception if it differs significantly
            verify_time_is_correct(diff_fatal=settings.max_allowable_time_drift)

            save_stats()

    except KeyboardInterrupt as ex:
        print(f'{xdescr(ex)}')
        sys_exit(130)

    except Exception as ex:
        log.error(f'{xdescr(ex)}')
        exit(1)


if __name__ == '__main__':
    main()
