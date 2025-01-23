import logging

# module import
from helpers.checktime import verify_time_is_correct, IncorrectSystemTimeError
from helpers.misc import xdescr

# local imports
from . import sys_exit

# Configure logging locally
logging.basicConfig(format='%(levelname)-8s [%(asctime)s] %(message)s', level=logging.INFO)
log = logging.getLogger(__name__)


def main() -> int:
    exit_code = 2  # failed to measure (by default)
    try:
        for _ in range(5):
            if verify_time_is_correct(wait=False):
                exit_code = 0  # system time is correct
                break

    except IncorrectSystemTimeError as e:
        log.warning(str(e))
        exit_code = 1  # system time is incorrect

    return exit_code


if __name__ == '__main__':
    try:
        exit(main())
    except KeyboardInterrupt as ex:
        print(f'{xdescr(ex)}')
        sys_exit(130)
