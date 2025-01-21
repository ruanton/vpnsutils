import atexit
import logging
import pyramid.config
import pyramid_zodbconn
import pyramid_tm
import ZODB
import sys
import os
import signal

# module imports
import zmodels
import helpers.misc

log = logging.getLogger(__name__)


def root_factory(request):
    """ This function is called on every web request
    """
    conn = pyramid_zodbconn.get_connection(request)
    return zmodels.get_app_root(conn)


# contains all ZODB database objects created by pyramid_zodbconn
_zodbconn_databases: dict[str, ZODB.DB] | None = None


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    _unused = global_config

    # force explicit transactions in waitress sub-threads
    # see: https://docs.pylonsproject.org/projects/pyramid_tm/en/latest/index.html#custom-transaction-managers
    settings['tm.manager_hook'] = pyramid_tm.explicit_manager

    with pyramid.config.Configurator(settings=settings) as config:
        config.include('pyramid_jinja2')
        config.include('pyramid_tm')
        config.include('pyramid_retry')
        config.include('pyramid_zodbconn')
        config.include('.settings')
        config.include('.routes')
        config.set_root_factory(root_factory)
        config.scan()

    # save a link to ZODB database objects for closing on application exit
    global _zodbconn_databases
    _zodbconn_databases_current = getattr(config.registry, '_zodb_databases')
    if _zodbconn_databases is not None and id(_zodbconn_databases) != id(_zodbconn_databases_current):
        raise RuntimeError('_zodbconn_databases is already initialized with a dict with a different identity')
    _zodbconn_databases = _zodbconn_databases_current

    return config.make_wsgi_app()


# see: https://relstorage.readthedocs.io/en/latest/things-to-know.html#the-importance-of-closing-the-database
# (unfortunately not called under Waitress even on reload)
@atexit.register
def zodb_close():
    if _zodbconn_databases:
        log.info('closing all ZODB database objects created by pyramid_zodbconn tween')
        for db in _zodbconn_databases.values():
            try:
                db.close()
            except pyramid_zodbconn.NoTransaction as ex:
                log.info(f'zodb_close: {ex}')
            except Exception as ex:
                log.warning(f'zodb_close: {ex}')
    else:
        log.info(f'zodb_close: no zodbconn database objects')


def sys_exit(status: str | int | None):
    try:
        sys.exit(status)
    except SystemExit:
        print(f'SystemExit caught')
        # noinspection PyUnresolvedReferences,PyProtectedMember
        os._exit(status)


def _sigint_handler(_sig, _frame):
    print(f'Signal SIGINT caught')
    sys_exit(130)


try:
    signal.signal(signal.SIGINT, _sigint_handler)
except ValueError as ex_:
    print(f'Cannot set signal handler: {helpers.misc.xdescr(ex_)}, ignoring')
