"""
Transaction Context Manager helpers.
"""

import logging
import typing
import transaction
import transaction.interfaces
import ZODB.Connection
from helpers.misc import xdescr

log = logging.getLogger(__name__)


class TransactionContextManager(object):
    """PEP 343 context manager"""
    def __init__(self, conn: ZODB.Connection.Connection, note: str = None):
        self.conn = conn
        self.note = note

    def __enter__(self) -> ZODB.Connection.Connection:
        self.tm = tm = self.conn.transaction_manager
        try:
            tran = tm.begin()
        except Exception:  # as e:
            # log.error(f 'failed to start transaction: {xdescr(e)}, aborting')
            try:
                tm.abort()
                log.info('transaction aborted successfully after attempt to start')
            except Exception as ex:
                log.error(f'failed to abort transaction: {xdescr(ex)}, ignoring')
            raise

        if self.note:
            tran.note(self.note)

        return self.conn

    def __exit__(self, typ, val, tb):
        if typ is None:
            try:
                self.tm.commit()
            except Exception:
                log.info('aborting transaction')
                self.tm.abort()
                raise
        else:
            log.info('aborting transaction')
            self.tm.abort()


def in_transaction(conn: ZODB.Connection.Connection, note: str = None) -> TransactionContextManager:
    """
    Execute a block of code as a transaction.
    Starts database transaction. Commits on success __exit__, rollbacks on exception.
    If a note is given, it will be added to the transaction's description.
    The 'in_transaction' returns a context manager that can be used with the ``with`` statement.
    """
    return TransactionContextManager(conn, note)


def has_transaction(cot: typing.Union[ZODB.Connection.Connection, transaction.interfaces.ITransaction]) -> bool:
    """
    Determines whether a given connection or transaction manager is currently in a transaction.

    @param cot: connection or transaction manager instance
    """
    if isinstance(cot, ZODB.Connection.Connection):
        cot: transaction.interfaces.ITransaction = cot.transaction_manager

    if isinstance(cot, transaction.ThreadTransactionManager):
        cot = cot.manager

    if isinstance(cot, transaction.TransactionManager):
        return getattr(cot, '_txn') is not None

    raise ValueError(f'unexpected connection or transaction manager instance type: {cot}')
