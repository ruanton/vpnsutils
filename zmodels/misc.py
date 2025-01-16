"""
Miscellaneous persistent ZODB models and useful auxiliary types.
"""

import persistent
from decimal import Decimal
from datetime import datetime, date, timedelta, tzinfo, timezone

# noinspection PyUnresolvedReferences
from BTrees.OOBTree import OOBTree, OOTreeSet

# useful shortcuts
DEC0 = Decimal(0)
DEC1 = Decimal(1)
DT_NONE: datetime | None = None;            """None-value typed as datetime"""
DATE_NONE: date | None = None;              """None-value typed as date"""
STR_NONE: str | None = None;                """None-value typed as str"""
BOOL_NONE: bool | None = None;              """None-value typed as bool"""
DEC_NONE: Decimal | None = None;            """None-value typed as Decimal"""
DEC_INT_NONE: int | Decimal | None = None;  """None-value typed as Decimal or int"""
INT_NONE: int | None = None;                """None-value typed as int"""


class TodayCounter(persistent.Persistent):
    """Sums numeric values for today and yesterday. Keeps the latest date/time."""
    def __init__(self):
        self.date_today = DATE_NONE;              """The maximum date among all incoming dates"""
        self.total_for_today = DEC_INT_NONE;      """Total counted value for date_today"""
        self.total_for_yesterday = DEC_INT_NONE;  """Total counted value for the date before date_today"""
        self.at_max = DT_NONE;                    """Maximum date/time among all seen"""

    def int_value_at(self, at: datetime, tz: tzinfo) -> int:
        """Get the total counted value for a date corresponding to a given datetime in a given timezone"""
        at_date = at.astimezone(tz=tz).date()
        if at_date == self.date_today:
            value = self.total_for_today
        elif at_date + timedelta(days=1) == self.date_today:
            value = self.total_for_yesterday
        else:
            value = 0

        assert isinstance(value, int)
        return value

    def dec_value_at(self, at: datetime, tz: tzinfo) -> Decimal:
        """Get the total counted value for a date corresponding to a given datetime in a given timezone"""
        at_date = at.astimezone(tz=tz).date()
        if at_date == self.date_today:
            value = self.total_for_today
        elif at_date + timedelta(days=1) == self.date_today:
            value = self.total_for_yesterday
        else:
            value = DEC0

        assert isinstance(value, Decimal)
        return value

    def add(self, value: int | Decimal, at: datetime, tz: tzinfo):
        """
        Adds value to the counter. Maintains date_today. Updates at_max if 'at' is later, converts to UTC.
        The date/time values in the 'at' argument are expected to arrive in nearly chronological order.
        """
        if self.date_today is not None:
            # once initialized we control that the value types are consistent
            if isinstance(value, int):
                assert isinstance(self.total_for_today, int) and isinstance(self.total_for_yesterday, int)
            else:
                assert isinstance(value, Decimal)
                assert isinstance(self.total_for_today, Decimal) and isinstance(self.total_for_yesterday, Decimal)

        at_date = at.astimezone(tz=tz).date()
        if at_date == self.date_today:
            # add value for today
            self.total_for_today += value
        elif at_date + timedelta(days=1) == self.date_today:
            # add value for yesterday
            # this may happen for some time after a timezone change
            self.total_for_yesterday += value
        elif at_date - timedelta(days=1) == self.date_today:
            # the next date has begun, rollover the counters
            self.date_today = at_date
            self.total_for_yesterday = self.total_for_today
            self.total_for_today = value
        else:
            # start new counters
            self.date_today = at_date
            self.total_for_yesterday = 0 if isinstance(value, int) else DEC0
            self.total_for_today = value

        if not self.at_max or at > self.at_max:
            self.at_max = at.astimezone(tz=timezone.utc)  # convert to UTC for pickling compatibility
