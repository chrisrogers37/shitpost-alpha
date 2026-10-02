"""The New York Stock Exchange calendar (XNYS), in UTC, from `exchange_calendars`.

A session is a trading date. Its regular hours run from its open (inclusive) to its close
(exclusive), both UTC datetimes; half days close at 13:00 New York time. Coins trade around
the clock and don't use this.
"""

from datetime import UTC, date, datetime
from functools import cache
from typing import Any

import exchange_calendars
import pandas as pd

XNYS = "XNYS"


@cache
def _xnys() -> Any:
    return exchange_calendars.get_calendar(XNYS)


def _minute(at: datetime) -> pd.Timestamp:
    if at.tzinfo is None:
        raise ValueError(f"{at} has no timezone")
    return pd.Timestamp(at).tz_convert(UTC).floor("min")


def _utc(stamp: pd.Timestamp) -> datetime:
    when: datetime = stamp.to_pydatetime().astimezone(UTC)
    return when


def _session(session: date) -> pd.Timestamp:
    if not is_session(session):
        raise ValueError(f"{session} is not an XNYS session")
    return pd.Timestamp(session)


def is_session(day: date) -> bool:
    """Whether the exchange trades on `day`."""
    return bool(_xnys().is_session(pd.Timestamp(day)))


def session_on_or_after(at: datetime) -> date:
    """The session trading at `at`, or the next one if the market is closed then: a post
    before the open belongs to that day's session, one after the close to the next."""
    session: date = _xnys().minute_to_session(_minute(at), direction="next").date()
    return session


def is_open(at: datetime) -> bool:
    """Whether regular trading is on at `at`."""
    return bool(_xnys().is_open_on_minute(_minute(at)))


def session_open(session: date) -> datetime:
    return _utc(_xnys().session_open(_session(session)))


def session_close(session: date) -> datetime:
    return _utc(_xnys().session_close(_session(session)))


def next_open(at: datetime) -> datetime:
    """The first regular open at or after `at`."""
    session = session_on_or_after(at)
    opens = session_open(session)
    return opens if opens >= at else session_open(trading_days_after(session, 1))


def trading_days_after(session: date, days: int) -> date:
    """The session `days` sessions after `session` (before it, for a negative number)."""
    later: date = _xnys().session_offset(_session(session), days).date()
    return later
