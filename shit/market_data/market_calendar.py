"""
Market Calendar Utility
Wraps exchange_calendars for NYSE/NASDAQ trading day awareness.

Usage:
    from shit.market_data.market_calendar import MarketCalendar

    cal = MarketCalendar()
    cal.is_trading_day(date(2025, 12, 25))  # False (Christmas)
    cal.next_trading_day(date(2025, 7, 4))  # date(2025, 7, 7) (skip Fri holiday + weekend)
    cal.trading_days_between(date(2025, 1, 6), date(2025, 1, 10))  # 5
    cal.trading_day_offset(date(2025, 6, 13), 1)  # date(2025, 6, 16) -- Friday +1 = Monday
"""

from datetime import date, datetime, timedelta, timezone
from typing import Optional

import exchange_calendars as xcals
import pandas as pd

from shit.logging import get_service_logger

logger = get_service_logger("market_calendar")


class MarketCalendar:
    """NYSE/NASDAQ market calendar for trading-day arithmetic.

    This class is stateless and cheap to instantiate. It wraps a singleton
    exchange_calendars.ExchangeCalendar under the hood (the library caches
    calendar instances internally).

    All methods accept plain ``datetime.date`` objects and return plain
    ``datetime.date`` or ``datetime.datetime`` objects -- no pandas types
    leak into the public API.
    """

    # NYSE calendar covers both NYSE and NASDAQ holidays (same schedule)
    _EXCHANGE_KEY = "XNYS"

    def __init__(self) -> None:
        self._cal = xcals.get_calendar(self._EXCHANGE_KEY)

    # -- Trading-day queries --------------------------------------------------

    def is_trading_day(self, d: date) -> bool:
        """Return True if *d* is a regular NYSE trading session."""
        ts = pd.Timestamp(d)
        try:
            return self._cal.is_session(ts)
        except ValueError:
            # Date outside calendar range (far future / far past)
            return False

    def next_trading_day(self, d: date) -> date:
        """Return the next trading day strictly after *d*.

        If *d* is a trading day, this returns the *following* trading day.
        If *d* is a weekend or holiday, this returns the next open session.
        """
        ts = pd.Timestamp(d)
        try:
            return self._cal.next_session(ts).date()
        except ValueError:
            # Fallback: naive walk forward (handles edge of calendar range)
            return self._naive_next_trading_day(d)

    def previous_trading_day(self, d: date) -> date:
        """Return the most recent trading day strictly before *d*."""
        ts = pd.Timestamp(d)
        try:
            return self._cal.previous_session(ts).date()
        except ValueError:
            return self._naive_previous_trading_day(d)

    def nearest_trading_day(self, d: date) -> date:
        """Return *d* if it is a trading day, otherwise the next trading day."""
        if self.is_trading_day(d):
            return d
        return self.next_trading_day(d)

    def trading_day_offset(self, d: date, offset: int) -> date:
        """Return the trading day *offset* sessions away from *d*.

        Args:
            d: Anchor date. If not a trading day, snaps to the nearest
               trading day (next for positive offset, previous for negative).
            offset: Number of trading days to advance (positive) or go back
                    (negative). ``offset=0`` returns the nearest trading day.

        Returns:
            The target trading day.

        Examples:
            Friday 2025-06-13, offset=1  -> Monday 2025-06-16
            Friday 2025-06-13, offset=3  -> Wednesday 2025-06-18
            Saturday 2025-06-14, offset=1 -> Monday 2025-06-16
        """
        if offset == 0:
            return self.nearest_trading_day(d)

        # Snap to nearest session first
        ts = pd.Timestamp(d)
        try:
            if self._cal.is_session(ts):
                anchor = ts
            elif offset > 0:
                anchor = self._cal.date_to_session(ts, direction="next")
            else:
                anchor = self._cal.date_to_session(ts, direction="previous")
            result = self._cal.session_offset(anchor, offset)
            return result.date()
        except ValueError:
            # Fallback for edge-of-range dates
            return self._naive_offset(d, offset)

    def trading_days_between(self, start: date, end: date) -> int:
        """Count the number of trading sessions in [start, end] inclusive.

        Both endpoints are included if they are trading days.
        """
        ts_start = pd.Timestamp(start)
        ts_end = pd.Timestamp(end)
        try:
            sessions = self._cal.sessions_in_range(ts_start, ts_end)
            return len(sessions)
        except ValueError:
            return 0

    # -- Market-hours queries -------------------------------------------------

    def next_market_open(self, dt: datetime) -> datetime:
        """Return the next NYSE market open after *dt* (timezone-aware, UTC).

        If *dt* is during market hours, returns the *next day's* open.
        If *dt* is before today's open, returns today's open (if today is a session).
        """
        dt_utc = self._ensure_utc(dt)
        ts = pd.Timestamp(dt_utc)
        result = self._cal.next_open(ts)
        return result.to_pydatetime().replace(tzinfo=timezone.utc)

    def next_market_close(self, dt: datetime) -> datetime:
        """Return the next NYSE market close after *dt* (timezone-aware, UTC).

        If *dt* is during market hours, returns *today's* close.
        If *dt* is after today's close, returns the next session's close.
        """
        dt_utc = self._ensure_utc(dt)
        ts = pd.Timestamp(dt_utc)
        result = self._cal.next_close(ts)
        return result.to_pydatetime().replace(tzinfo=timezone.utc)

    def session_close_time(self, d: date) -> Optional[datetime]:
        """Return the close time (UTC) for a specific session date.

        Returns None if *d* is not a trading day.
        """
        if not self.is_trading_day(d):
            return None
        ts = pd.Timestamp(d)
        close_ts = self._cal.session_close(ts)
        return close_ts.to_pydatetime().replace(tzinfo=timezone.utc)

    def session_open_time(self, d: date) -> Optional[datetime]:
        """Return the open time (UTC) for a specific session date.

        Returns None if *d* is not a trading day.
        """
        if not self.is_trading_day(d):
            return None
        ts = pd.Timestamp(d)
        open_ts = self._cal.session_open(ts)
        return open_ts.to_pydatetime().replace(tzinfo=timezone.utc)

    def is_market_open(self, dt: datetime) -> bool:
        """Return True if the market is open at the given datetime."""
        dt_utc = self._ensure_utc(dt)
        d = dt_utc.date()
        if not self.is_trading_day(d):
            return False
        open_time = self.session_open_time(d)
        close_time = self.session_close_time(d)
        if open_time is None or close_time is None:
            return False
        return open_time <= dt_utc < close_time

    # -- Calendar-day to trading-day conversion --------------------------------

    def calendar_days_for_trading_days(self, trading_days: int) -> int:
        """Estimate calendar days needed to span *trading_days* trading days.

        More accurate than the naive 2x multiplier used in asset_queries.py.
        Adds buffer for weekends and potential holidays.
        """
        # 5 trading days = 7 calendar days + 1 buffer for holidays
        weeks = trading_days // 5
        remainder = trading_days % 5
        return weeks * 7 + remainder + 2  # +2 buffer for holidays

    # -- Private helpers -------------------------------------------------------

    @staticmethod
    def _ensure_utc(dt: datetime) -> datetime:
        """Ensure a datetime is timezone-aware in UTC."""
        if dt.tzinfo is None:
            # Assume UTC for naive datetimes
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def _naive_next_trading_day(d: date) -> date:
        """Fallback: walk forward skipping weekends."""
        candidate = d + timedelta(days=1)
        while candidate.weekday() >= 5:  # 5=Sat, 6=Sun
            candidate += timedelta(days=1)
        return candidate

    @staticmethod
    def _naive_previous_trading_day(d: date) -> date:
        """Fallback: walk backward skipping weekends."""
        candidate = d - timedelta(days=1)
        while candidate.weekday() >= 5:
            candidate -= timedelta(days=1)
        return candidate

    @staticmethod
    def _naive_offset(d: date, offset: int) -> date:
        """Fallback: walk forward/backward by offset trading days."""
        step = 1 if offset > 0 else -1
        remaining = abs(offset)
        candidate = d
        while remaining > 0:
            candidate += timedelta(days=step)
            if candidate.weekday() < 5:
                remaining -= 1
        return candidate
