import transaction
import persistent
import persistent.mapping
import ZODB.Connection

# noinspection PyUnresolvedReferences
from BTrees.OOBTree import OOBTree

# local imports
from . import tcm

# force explicit transactions in the main thread
# see: https://relstorage.readthedocs.io/en/latest/things-to-know.html#use-explicit-transaction-managers
transaction.manager.explicit = True


class AppRoot(persistent.Persistent):  # in Cookiecutter: base class was PersistentMapping
    """App Root object. Root of all other persistent objects.
    """
    __parent__ = __name__ = None   # used by Request.resource_path()

    def __init__(self):
        # add custom DB initialization here
        pass


def get_app_root(conn: ZODB.Connection.Connection) -> AppRoot:
    """
    Get the AppRoot persistent object. Creates a new one, if it does not already exist.
    Side effect: if the object does not already exist in the database, creates it; if not in a transaction,
    a new transaction is started and committed.
    """
    # verify that the transaction is set to explicit mode for given connection
    tm = conn.transaction_manager
    if isinstance(tm, transaction.ThreadTransactionManager):
        tm: transaction.TransactionManager = tm.manager
    if not tm.explicit:
        raise RuntimeError(f'the transaction is not set to explicit mode for given connection')

    # get root ZODB entity
    zodb_root: persistent.mapping.PersistentMapping = conn.root()

    if 'app_root' in zodb_root:
        # get object from database
        app_root: AppRoot = zodb_root['app_root']
    else:
        # create a new object
        if tcm.has_transaction(cot=conn):
            # we are already in transaction
            app_root = AppRoot()
            zodb_root['app_root'] = app_root
        else:
            # start and commit a new transaction
            with tcm.in_transaction(conn):
                app_root = AppRoot()
                zodb_root['app_root'] = app_root

    return app_root
