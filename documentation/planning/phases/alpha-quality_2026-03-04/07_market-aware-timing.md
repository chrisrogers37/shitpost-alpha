# Phase 7: Market-Aware Timing

## Header

| Field | Value |
|-------|-------|
| **PR Title** | feat: add market calendar, trading-day timeframes, and intraday price capture |
| **Risk Level** | HIGH -- behavioral change to existing T+1/T+3/T+7/T+30 calculations; schema migration on production table |
| **Estimated Effort** | High (3-5 days) |
| **Files Created** | 3 (`market_calendar.py`, `intraday_provider.py`, `test_market_calendar.py`) |
| **Files Modified** | 7 (`outcome_calculator.py`, `models.py`, `client.py`, `yfinance_provider.py`, `price_provider.py`, `__init__.py`, `requirements.txt`) |
| **Files Deleted** | 0 |

---

## Context

The system currently has no concept of trading days, market hours, or intraday prices. All outcome timeframes use raw `timedelta(days=N)` calendar-day offsets (see `outcome_calculator.py:224-234`). This produces incorrect results in multiple scenarios:

1. **Friday predictions**: T+1 lands on Saturday. The backward-walk in `get_price_on_date()` finds Friday's close, so "T+1 return" is actually 0% (same day).
2. **Holiday gaps**: A Monday holiday means T+1 lands on a non-trading day, again using the previous Friday's close.
3. **No intraday tracking**: Posts made at 10 AM cannot measure the "same-day close" or "1-hour" reaction window -- the most valuable signals for a trading system.
4. **Dashboard heuristic**: `asset_queries.py:372-375` uses a rough 2x multiplier to convert trading days to calendar days for the price sparkline window. This is fragile and over-fetches.

This phase adds a `MarketCalendar` utility, converts all outcome calculations to trading-day offsets, introduces intraday price capture for near-term timeframes, and adds new columns to `PredictionOutcome` for same-day and 1-hour tracking.

---

## Dependencies

- **Depends on**: None (this phase is self-contained within `shit/market_data/`)
- **Unlocks**: None explicitly, but the market calendar utility becomes available for any future phase that needs trading-day awareness (e.g., dashboard sparkline improvements)

---

## Detailed Implementation Plan

### Step 1: Add `exchange_calendars` to requirements.txt

**File**: `/Users/chris/Projects/shitpost-alpha/requirements.txt`

Add after line 51 (`yfinance>=0.2.48`):

```python
# Market calendar
exchange_calendars>=4.5.0
```

**Why**: The `exchange_calendars` library provides NYSE/NASDAQ session schedules including holidays, early closes, and open/close times. It is the standard library for this purpose (successor to `trading_calendars` from Quantopian).

---

### Step 2: Create `shit/market_data/market_calendar.py`

**File**: `/Users/chris/Projects/shitpost-alpha/shit/market_data/market_calendar.py` (NEW)

This is a thin wrapper around `exchange_calendars` that provides the project's specific needs: trading-day arithmetic, market-hours awareness, and "next session" logic for posts made outside market hours.

```python
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

    # ── Trading-day queries ────────────────────────────────────────

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

    # ── Market-hours queries ───────────────────────────────────────

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

    # ── Calendar-day to trading-day conversion ─────────────────────

    def calendar_days_for_trading_days(self, trading_days: int) -> int:
        """Estimate calendar days needed to span *trading_days* trading days.

        More accurate than the naive 2x multiplier used in asset_queries.py.
        Adds buffer for weekends and potential holidays.
        """
        # 5 trading days = 7 calendar days + 1 buffer for holidays
        weeks = trading_days // 5
        remainder = trading_days % 5
        return weeks * 7 + remainder + 2  # +2 buffer for holidays

    # ── Private helpers ────────────────────────────────────────────

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
```

**Why this design**:
- All public methods accept `datetime.date` / `datetime.datetime` and return the same -- no `pd.Timestamp` leaks into calling code.
- Fallback methods handle edge cases where `exchange_calendars` raises `ValueError` (dates outside its calendar range).
- `trading_day_offset` is the key method for outcome calculation: it replaces `timedelta(days=N)`.
- `next_market_close` and `next_market_open` are needed for the new same-day-close timeframe.
- `calendar_days_for_trading_days` provides a more accurate replacement for the 2x heuristic in `asset_queries.py:374`.

---

### Step 3: Add intraday fetch capability to `YFinanceProvider`

**File**: `/Users/chris/Projects/shitpost-alpha/shit/market_data/yfinance_provider.py`

Add a new method `fetch_intraday_prices` after the existing `fetch_prices` method (after line 69):

```python
    def fetch_intraday_prices(
        self,
        symbol: str,
        target_date: date,
        interval: str = "1h",
    ) -> List[RawPriceRecord]:
        """Fetch intraday price data from yfinance for a specific date.

        yfinance limitations:
        - 1m data: last 30 days only
        - 1h data: last 730 days
        - Data may not be available for all symbols (e.g., some ETFs)

        Args:
            symbol: Ticker symbol (e.g., 'AAPL')
            target_date: The date to fetch intraday data for
            interval: Price interval ('1h', '5m', '1m'). Default '1h'.

        Returns:
            List of RawPriceRecord with intraday timestamps.
            Records have ``date`` set to the bar's datetime (not just date).
        """
        try:
            ticker = yf.Ticker(symbol)
            start = target_date
            end = target_date + timedelta(days=1)
            hist = ticker.history(
                start=start, end=end, interval=interval
            )

            if hist.empty:
                logger.debug(
                    f"yfinance returned no intraday data for {symbol} on {target_date}",
                    extra={"symbol": symbol, "date": str(target_date), "interval": interval},
                )
                return []

            records = []
            for idx, row in hist.iterrows():
                bar_dt = idx.to_pydatetime() if hasattr(idx, 'to_pydatetime') else idx
                # Store the bar date (not the intraday timestamp) for RawPriceRecord
                bar_date = bar_dt.date() if hasattr(bar_dt, 'date') else bar_dt

                record = RawPriceRecord(
                    symbol=symbol,
                    date=bar_date,
                    open=float(row['Open']) if 'Open' in row and row['Open'] is not None else None,
                    high=float(row['High']) if 'High' in row and row['High'] is not None else None,
                    low=float(row['Low']) if 'Low' in row and row['Low'] is not None else None,
                    close=float(row['Close']) if 'Close' in row else 0.0,
                    volume=int(row['Volume']) if 'Volume' in row and row['Volume'] is not None else None,
                    adjusted_close=None,
                    source="yfinance_intraday",
                )
                # Attach the full bar timestamp as a custom attribute
                record.bar_datetime = bar_dt
                records.append(record)

            return records

        except Exception as e:
            logger.warning(
                f"Failed to fetch intraday data for {symbol} on {target_date}: {e}",
                extra={"symbol": symbol, "date": str(target_date), "error": str(e)},
            )
            return []
```

**Why**: The existing `fetch_prices` only fetches daily OHLCV. For `price_at_post` and `price_1h_after`, we need intraday bars. yfinance supports `interval="1h"` with 730 days of history -- sufficient for this use case since we only call it when a prediction is first created (not as a historical backfill).

**Important**: This method is NOT part of the `PriceProvider` interface (which returns daily data). It is yfinance-specific. This is intentional -- intraday is a bonus feature with limited provider support.

---

### Step 4: Create `shit/market_data/intraday_provider.py`

**File**: `/Users/chris/Projects/shitpost-alpha/shit/market_data/intraday_provider.py` (NEW)

A small helper that fetches and interpolates intraday prices for a specific post timestamp.

```python
"""
Intraday Price Provider
Fetches intraday prices near a specific timestamp for prediction tracking.

This is intentionally simple -- it fetches 1h bars for a single day and finds
the bar closest to the requested timestamp. NOT stored in the database
(intraday data is too voluminous). Used only to populate snapshot columns
on PredictionOutcome at creation time.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Optional, Tuple

from shit.market_data.yfinance_provider import YFinanceProvider
from shit.market_data.market_calendar import MarketCalendar
from shit.logging import get_service_logger

logger = get_service_logger("intraday_provider")


class IntradayPriceSnapshot:
    """Container for intraday price data near a post timestamp."""

    def __init__(
        self,
        price_at_post: Optional[float] = None,
        price_1h_after: Optional[float] = None,
        price_at_next_close: Optional[float] = None,
    ):
        self.price_at_post = price_at_post
        self.price_1h_after = price_1h_after
        self.price_at_next_close = price_at_next_close


def fetch_intraday_snapshot(
    symbol: str,
    post_datetime: datetime,
) -> IntradayPriceSnapshot:
    """Fetch intraday prices around a post's publication time.

    Captures three data points:
    - price_at_post: The price of the closest 1h bar at or before the post time
    - price_1h_after: The price of the bar ~1 hour after the post
    - price_at_next_close: The daily close price of the next trading session
      (uses the daily close from MarketPrice, not intraday)

    If intraday data is not available (symbol not supported, data too old),
    falls back gracefully by returning None for each unavailable field.

    Args:
        symbol: Ticker symbol
        post_datetime: When the post was published (timezone-aware or naive-UTC)

    Returns:
        IntradayPriceSnapshot with available prices filled in.
    """
    snapshot = IntradayPriceSnapshot()
    calendar = MarketCalendar()

    # Ensure timezone-aware
    if post_datetime.tzinfo is None:
        post_datetime = post_datetime.replace(tzinfo=timezone.utc)

    # Determine the relevant trading session
    post_date = post_datetime.date()

    # If the post is during/after market hours, the "relevant day" is today.
    # If the post is before market open or on a non-trading day,
    # the "relevant day" is the next trading session.
    if calendar.is_trading_day(post_date):
        session_close = calendar.session_close_time(post_date)
        if session_close and post_datetime < session_close:
            # Post is before today's close -- use today's session
            relevant_date = post_date
        else:
            # Post is after today's close -- next session
            relevant_date = calendar.next_trading_day(post_date)
    else:
        relevant_date = calendar.nearest_trading_day(post_date)

    # Fetch 1h bars for the relevant trading day
    provider = YFinanceProvider()
    try:
        bars = provider.fetch_intraday_prices(symbol, relevant_date, interval="1h")
    except Exception as e:
        logger.warning(
            f"Intraday fetch failed for {symbol} on {relevant_date}: {e}",
            extra={"symbol": symbol, "date": str(relevant_date)},
        )
        return snapshot

    if not bars:
        logger.debug(
            f"No intraday bars for {symbol} on {relevant_date}",
            extra={"symbol": symbol},
        )
        return snapshot

    # Find the bar closest to post time (at or before)
    bar_datetimes = []
    for bar in bars:
        bar_dt = getattr(bar, "bar_datetime", None)
        if bar_dt is not None:
            if bar_dt.tzinfo is None:
                bar_dt = bar_dt.replace(tzinfo=timezone.utc)
            bar_datetimes.append((bar_dt, bar))

    bar_datetimes.sort(key=lambda x: x[0])

    if not bar_datetimes:
        return snapshot

    # price_at_post: latest bar at or before post time
    at_or_before = [(dt, bar) for dt, bar in bar_datetimes if dt <= post_datetime]
    if at_or_before:
        _, closest_bar = at_or_before[-1]
        snapshot.price_at_post = closest_bar.close
    else:
        # Post is before first bar (pre-market post) -- use first bar's open
        _, first_bar = bar_datetimes[0]
        snapshot.price_at_post = first_bar.open if first_bar.open else first_bar.close

    # price_1h_after: bar closest to post_time + 1 hour
    target_1h = post_datetime + timedelta(hours=1)
    at_or_before_1h = [(dt, bar) for dt, bar in bar_datetimes if dt <= target_1h]
    if at_or_before_1h:
        _, bar_1h = at_or_before_1h[-1]
        snapshot.price_1h_after = bar_1h.close
    # else: no bar available 1h after post (post too close to close)

    # price_at_next_close: use the last bar's close as proxy for daily close
    # (The actual daily close from MarketPrice table is more accurate,
    #  so the caller should prefer that if available.)
    _, last_bar = bar_datetimes[-1]
    snapshot.price_at_next_close = last_bar.close

    return snapshot
```

**Why a separate module**: The intraday fetch is conceptually different from daily price storage. It is ephemeral (not stored in `market_prices`), used only once at prediction-creation time, and has different failure modes. Keeping it isolated means the daily price pipeline is unaffected.

---

### Step 5: Add new columns to `PredictionOutcome` model

**File**: `/Users/chris/Projects/shitpost-alpha/shit/market_data/models.py`

Add the following columns to the `PredictionOutcome` class, after line 69 (after `price_at_prediction`):

```python
    # Intraday snapshot prices (captured once at prediction creation)
    price_at_post = Column(Float, nullable=True)       # Price when post was published (intraday)
    price_at_next_close = Column(Float, nullable=True)  # Price at next market close after post
    price_1h_after = Column(Float, nullable=True)       # Price 1 hour after post (intraday)
```

Add new return/correct/pnl columns after line 81 (after `return_t30`):

```python
    # Short-term intraday returns
    return_same_day = Column(Float, nullable=True)  # % change: price_at_post -> price_at_next_close
    return_1h = Column(Float, nullable=True)         # % change: price_at_post -> price_1h_after

    # Short-term accuracy
    correct_same_day = Column(Boolean, nullable=True)  # Correct at same-day close?
    correct_1h = Column(Boolean, nullable=True)         # Correct at +1 hour?

    # Short-term P&L
    pnl_same_day = Column(Float, nullable=True)  # P&L at same-day close ($1000 position)
    pnl_1h = Column(Float, nullable=True)         # P&L at +1 hour ($1000 position)
```

Also add a new column to store the full post timestamp (currently `_get_source_date` only returns `date`, but we now need the full `datetime` for intraday logic):

```python
    # Post publication timestamp (full datetime for intraday calculations)
    post_published_at = Column(DateTime, nullable=True)
```

The full diff for the `PredictionOutcome` class columns (lines 51-102 of `models.py`) becomes:

**BEFORE** (lines 57-69):
```python
    # Link to prediction
    prediction_id = Column(Integer, ForeignKey("predictions.id"), nullable=False, index=True)

    # Asset being tracked
    symbol = Column(String(20), nullable=False, index=True)

    # Prediction details (denormalized for easier querying)
    prediction_date = Column(Date, nullable=False, index=True)
    prediction_sentiment = Column(String(20), nullable=True)
    prediction_confidence = Column(Float, nullable=True)
    prediction_timeframe_days = Column(Integer, nullable=True)

    # Price at prediction time
    price_at_prediction = Column(Float, nullable=True)
```

**AFTER**:
```python
    # Link to prediction
    prediction_id = Column(Integer, ForeignKey("predictions.id"), nullable=False, index=True)

    # Asset being tracked
    symbol = Column(String(20), nullable=False, index=True)

    # Prediction details (denormalized for easier querying)
    prediction_date = Column(Date, nullable=False, index=True)
    prediction_sentiment = Column(String(20), nullable=True)
    prediction_confidence = Column(Float, nullable=True)
    prediction_timeframe_days = Column(Integer, nullable=True)

    # Post publication timestamp (full datetime for intraday calculations)
    post_published_at = Column(DateTime, nullable=True)

    # Price at prediction time (daily close)
    price_at_prediction = Column(Float, nullable=True)

    # Intraday snapshot prices (captured once at prediction creation)
    price_at_post = Column(Float, nullable=True)        # Price when post was published
    price_at_next_close = Column(Float, nullable=True)   # Next market close after post
    price_1h_after = Column(Float, nullable=True)        # 1 hour after post
```

And after line 81 (the return columns), add:

**BEFORE** (lines 77-93):
```python
    # Returns (percentage change)
    return_t1 = Column(Float, nullable=True)
    return_t3 = Column(Float, nullable=True)
    return_t7 = Column(Float, nullable=True)
    return_t30 = Column(Float, nullable=True)

    # Accuracy validation
    correct_t1 = Column(Boolean, nullable=True)
    correct_t3 = Column(Boolean, nullable=True)
    correct_t7 = Column(Boolean, nullable=True)
    correct_t30 = Column(Boolean, nullable=True)

    # Profit/Loss simulation
    pnl_t1 = Column(Float, nullable=True)
    pnl_t3 = Column(Float, nullable=True)
    pnl_t7 = Column(Float, nullable=True)
    pnl_t30 = Column(Float, nullable=True)
```

**AFTER**:
```python
    # Returns (percentage change) -- daily timeframes (trading days)
    return_t1 = Column(Float, nullable=True)   # T+1 trading day
    return_t3 = Column(Float, nullable=True)   # T+3 trading days
    return_t7 = Column(Float, nullable=True)   # T+7 trading days
    return_t30 = Column(Float, nullable=True)  # T+30 trading days

    # Returns -- intraday timeframes
    return_same_day = Column(Float, nullable=True)  # price_at_post -> price_at_next_close
    return_1h = Column(Float, nullable=True)         # price_at_post -> price_1h_after

    # Accuracy validation -- daily timeframes
    correct_t1 = Column(Boolean, nullable=True)
    correct_t3 = Column(Boolean, nullable=True)
    correct_t7 = Column(Boolean, nullable=True)
    correct_t30 = Column(Boolean, nullable=True)

    # Accuracy -- intraday timeframes
    correct_same_day = Column(Boolean, nullable=True)
    correct_1h = Column(Boolean, nullable=True)

    # Profit/Loss simulation ($1000 position) -- daily
    pnl_t1 = Column(Float, nullable=True)
    pnl_t3 = Column(Float, nullable=True)
    pnl_t7 = Column(Float, nullable=True)
    pnl_t30 = Column(Float, nullable=True)

    # P&L -- intraday
    pnl_same_day = Column(Float, nullable=True)
    pnl_1h = Column(Float, nullable=True)
```

**Schema migration SQL** (to be run via the `db-admin` command):
```sql
ALTER TABLE prediction_outcomes ADD COLUMN IF NOT EXISTS post_published_at TIMESTAMP;
ALTER TABLE prediction_outcomes ADD COLUMN IF NOT EXISTS price_at_post FLOAT;
ALTER TABLE prediction_outcomes ADD COLUMN IF NOT EXISTS price_at_next_close FLOAT;
ALTER TABLE prediction_outcomes ADD COLUMN IF NOT EXISTS price_1h_after FLOAT;
ALTER TABLE prediction_outcomes ADD COLUMN IF NOT EXISTS return_same_day FLOAT;
ALTER TABLE prediction_outcomes ADD COLUMN IF NOT EXISTS return_1h FLOAT;
ALTER TABLE prediction_outcomes ADD COLUMN IF NOT EXISTS correct_same_day BOOLEAN;
ALTER TABLE prediction_outcomes ADD COLUMN IF NOT EXISTS correct_1h BOOLEAN;
ALTER TABLE prediction_outcomes ADD COLUMN IF NOT EXISTS pnl_same_day FLOAT;
ALTER TABLE prediction_outcomes ADD COLUMN IF NOT EXISTS pnl_1h FLOAT;
```

All new columns are nullable, so this is an additive-only migration. Existing rows will have `NULL` for these columns, which is correct -- historical predictions did not have intraday data captured.

---

### Step 6: Rewrite `_calculate_single_outcome` to use trading days

**File**: `/Users/chris/Projects/shitpost-alpha/shit/market_data/outcome_calculator.py`

This is the core change. The `_calculate_single_outcome` method (lines 140-298) must be updated to:
1. Use `MarketCalendar.trading_day_offset()` instead of `timedelta(days=N)`.
2. Use a new `_get_source_datetime()` method (full datetime, not just date) for intraday.
3. Calculate the new intraday timeframes (`return_same_day`, `return_1h`).

#### 6a. Add imports at the top of the file

**BEFORE** (lines 1-18):
```python
"""
Prediction Outcome Calculator
Calculates actual outcomes for predictions by comparing with real market data.
"""

from datetime import date, timedelta
from typing import List, Optional, Dict, Any
import logging
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from shit.market_data.models import PredictionOutcome, MarketPrice
from shit.market_data.client import MarketDataClient
from shit.db.sync_session import get_session
from shit.logging import get_service_logger
from shitvault.shitpost_models import Prediction  # noqa: F401
from shitvault.signal_models import Signal  # noqa: F401 - registers Signal with SQLAlchemy mapper

logger = get_service_logger("outcome_calculator")
```

**AFTER**:
```python
"""
Prediction Outcome Calculator
Calculates actual outcomes for predictions by comparing with real market data.

Timeframe semantics (v2 -- trading-day based):
- T+1 = 1 trading day after the post date (Friday -> Monday)
- T+3 = 3 trading days after the post date
- T+7 = 7 trading days after the post date (~1.5 calendar weeks)
- T+30 = 30 trading days after the post date (~6 calendar weeks)
- same_day = price_at_post -> next market close
- 1h = price_at_post -> 1 hour after post
"""

from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
import logging
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from shit.market_data.models import PredictionOutcome, MarketPrice
from shit.market_data.client import MarketDataClient
from shit.market_data.market_calendar import MarketCalendar
from shit.market_data.intraday_provider import fetch_intraday_snapshot
from shit.db.sync_session import get_session
from shit.logging import get_service_logger
from shitvault.shitpost_models import Prediction  # noqa: F401
from shitvault.signal_models import Signal  # noqa: F401 - registers Signal with SQLAlchemy mapper

logger = get_service_logger("outcome_calculator")
```

#### 6b. Add `MarketCalendar` to `__init__` and `__enter__`

**BEFORE** (lines 22-46):
```python
class OutcomeCalculator:
    """Calculates prediction outcomes by comparing predictions with actual market data."""

    def __init__(self, session: Optional[Session] = None):
        self.session = session
        self._session_context = None
        self._own_session = session is None
        self._failed_symbols: set = set()

    def __enter__(self):
        if self._own_session:
            self._session_context = get_session()
            self.session = self._session_context.__enter__()
        self.market_client = MarketDataClient(session=self.session)
        return self
```

**AFTER**:
```python
class OutcomeCalculator:
    """Calculates prediction outcomes by comparing predictions with actual market data.

    Uses trading-day offsets (via MarketCalendar) for all timeframe calculations.
    T+1 means "1 trading day later" (Friday -> Monday), not "1 calendar day later".
    """

    def __init__(self, session: Optional[Session] = None):
        self.session = session
        self._session_context = None
        self._own_session = session is None
        self._failed_symbols: set = set()
        self._calendar = MarketCalendar()

    def __enter__(self):
        if self._own_session:
            self._session_context = get_session()
            self.session = self._session_context.__enter__()
        self.market_client = MarketDataClient(session=self.session)
        return self
```

#### 6c. Add `_get_source_datetime` method

Add this new method after `_get_source_date` (after line 460):

```python
    def _get_source_datetime(self, prediction) -> Optional[datetime]:
        """Get the full datetime of the source post publication.

        Unlike ``_get_source_date`` which returns only a date, this returns
        the full datetime including time-of-day -- needed for intraday
        price lookups (price_at_post, price_1h_after).

        Returns:
            Timezone-aware datetime (UTC), or None.
        """
        # Truth Social shitpost timestamp
        try:
            if prediction.shitpost and prediction.shitpost.timestamp:
                ts = prediction.shitpost.timestamp
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                return ts
        except Exception:
            pass

        # Source-agnostic signal published_at
        try:
            if prediction.signal and prediction.signal.published_at:
                ts = prediction.signal.published_at
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                return ts
        except Exception:
            pass

        # Fallback: prediction creation time
        if prediction.created_at:
            ts = prediction.created_at
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return ts

        return None
```

#### 6d. Rewrite `_calculate_single_outcome`

Replace the timeframe loop (lines 223-278) with trading-day logic:

**BEFORE** (lines 223-278):
```python
        # Calculate outcomes for different timeframes
        timeframes = [
            (1, "price_t1", "return_t1", "correct_t1", "pnl_t1"),
            (3, "price_t3", "return_t3", "correct_t3", "pnl_t3"),
            (7, "price_t7", "return_t7", "correct_t7", "pnl_t7"),
            (30, "price_t30", "return_t30", "correct_t30", "pnl_t30"),
        ]

        outcome.is_complete = True

        for days, price_attr, return_attr, correct_attr, pnl_attr in timeframes:
            target_date = prediction_date + timedelta(days=days)

            # Skip future dates
            if target_date > date.today():
                outcome.is_complete = False
                continue

            # Get price at T+N
            price_tn = self.market_client.get_price_on_date(symbol, target_date)

            if not price_tn:
                # Try to fetch it
                try:
                    self.market_client.fetch_price_history(
                        symbol,
                        start_date=target_date - timedelta(days=7),
                        end_date=target_date,
                    )
                    price_tn = self.market_client.get_price_on_date(symbol, target_date)
                except Exception as e:
                    logger.debug(
                        f"Could not fetch price for {symbol} on {target_date}: {e}",
                        extra={"symbol": symbol, "date": str(target_date)},
                    )

            if price_tn:
                setattr(outcome, price_attr, price_tn.close)
                return_pct = outcome.calculate_return(price_t0.close, price_tn.close)
                setattr(outcome, return_attr, return_pct)
                is_correct = (
                    outcome.is_correct(sentiment, return_pct) if sentiment else None
                )
                setattr(outcome, correct_attr, is_correct)
                pnl = outcome.calculate_pnl(return_pct, position_size=1000.0)
                setattr(outcome, pnl_attr, pnl)
            else:
                outcome.is_complete = False
```

**AFTER**:
```python
        # Calculate outcomes for trading-day timeframes
        # NOTE: These are TRADING DAYS, not calendar days.
        # T+1 on Friday = Monday. T+1 before a holiday skips the holiday.
        timeframes = [
            (1, "price_t1", "return_t1", "correct_t1", "pnl_t1"),
            (3, "price_t3", "return_t3", "correct_t3", "pnl_t3"),
            (7, "price_t7", "return_t7", "correct_t7", "pnl_t7"),
            (30, "price_t30", "return_t30", "correct_t30", "pnl_t30"),
        ]

        outcome.is_complete = True

        for trading_days, price_attr, return_attr, correct_attr, pnl_attr in timeframes:
            target_date = self._calendar.trading_day_offset(prediction_date, trading_days)

            # Skip future dates
            if target_date > date.today():
                outcome.is_complete = False
                continue

            # Get price at T+N (trading days)
            price_tn = self.market_client.get_price_on_date(symbol, target_date)

            if not price_tn:
                # Try to fetch it -- use calendar-aware window for the fetch range
                fetch_start = self._calendar.previous_trading_day(target_date)
                try:
                    self.market_client.fetch_price_history(
                        symbol,
                        start_date=fetch_start,
                        end_date=target_date,
                    )
                    price_tn = self.market_client.get_price_on_date(symbol, target_date)
                except Exception as e:
                    logger.debug(
                        f"Could not fetch price for {symbol} on {target_date}: {e}",
                        extra={"symbol": symbol, "date": str(target_date)},
                    )

            if price_tn:
                setattr(outcome, price_attr, price_tn.close)
                return_pct = outcome.calculate_return(price_t0.close, price_tn.close)
                setattr(outcome, return_attr, return_pct)
                is_correct = (
                    outcome.is_correct(sentiment, return_pct) if sentiment else None
                )
                setattr(outcome, correct_attr, is_correct)
                pnl = outcome.calculate_pnl(return_pct, position_size=1000.0)
                setattr(outcome, pnl_attr, pnl)
            else:
                outcome.is_complete = False
```

#### 6e. Add intraday calculations to `_calculate_single_outcome`

Add this block **after** the trading-day timeframe loop (after the code above) and **before** the `outcome.last_price_update = date.today()` line (line 279):

```python
        # ── Intraday timeframes (same-day close, +1 hour) ────────
        # Only attempt for predictions where we have the full post datetime
        post_dt = self._get_source_datetime(
            self.session.query(Prediction)
            .filter(Prediction.id == prediction_id)
            .first()
        ) if not hasattr(self, '_current_post_datetime') else self._current_post_datetime

        if post_dt and price_t0:
            outcome.post_published_at = post_dt

            # Only fetch intraday for outcomes that don't already have it
            if outcome.price_at_post is None:
                try:
                    snapshot = fetch_intraday_snapshot(symbol, post_dt)
                    outcome.price_at_post = snapshot.price_at_post
                    outcome.price_1h_after = snapshot.price_1h_after
                    # Prefer daily close from MarketPrice over intraday last bar
                    if outcome.price_at_next_close is None:
                        # Get the next trading day's close for "same-day close"
                        next_close_date = self._calendar.nearest_trading_day(post_dt.date())
                        # If post is after market close, next close is next trading day
                        if self._calendar.is_trading_day(post_dt.date()):
                            close_time = self._calendar.session_close_time(post_dt.date())
                            if close_time and post_dt >= close_time:
                                next_close_date = self._calendar.next_trading_day(post_dt.date())
                        next_close_price = self.market_client.get_price_on_date(
                            symbol, next_close_date
                        )
                        if next_close_price:
                            outcome.price_at_next_close = next_close_price.close
                        elif snapshot.price_at_next_close:
                            outcome.price_at_next_close = snapshot.price_at_next_close
                except Exception as e:
                    logger.debug(
                        f"Intraday snapshot failed for {symbol}: {e}",
                        extra={"symbol": symbol, "error": str(e)},
                    )

            # Calculate intraday returns (from price_at_post, not price_at_prediction)
            base_price = outcome.price_at_post
            if base_price and base_price > 0:
                # Same-day close return
                if outcome.price_at_next_close is not None:
                    outcome.return_same_day = outcome.calculate_return(
                        base_price, outcome.price_at_next_close
                    )
                    outcome.correct_same_day = (
                        outcome.is_correct(sentiment, outcome.return_same_day)
                        if sentiment
                        else None
                    )
                    outcome.pnl_same_day = outcome.calculate_pnl(
                        outcome.return_same_day, position_size=1000.0
                    )

                # 1-hour return
                if outcome.price_1h_after is not None:
                    outcome.return_1h = outcome.calculate_return(
                        base_price, outcome.price_1h_after
                    )
                    outcome.correct_1h = (
                        outcome.is_correct(sentiment, outcome.return_1h)
                        if sentiment
                        else None
                    )
                    outcome.pnl_1h = outcome.calculate_pnl(
                        outcome.return_1h, position_size=1000.0
                    )
```

**IMPORTANT**: To avoid a redundant query for the prediction object (which we already have in `calculate_outcome_for_prediction`), pass the post datetime through. Modify the `_calculate_single_outcome` signature and the call site.

Update the `_calculate_single_outcome` signature (line 140) to accept an optional `post_datetime`:

**BEFORE**:
```python
    def _calculate_single_outcome(
        self,
        prediction_id: int,
        symbol: str,
        prediction_date: date,
        sentiment: Optional[str],
        confidence: Optional[float],
        force_refresh: bool = False,
    ) -> Optional[PredictionOutcome]:
```

**AFTER**:
```python
    def _calculate_single_outcome(
        self,
        prediction_id: int,
        symbol: str,
        prediction_date: date,
        sentiment: Optional[str],
        confidence: Optional[float],
        force_refresh: bool = False,
        post_datetime: Optional[datetime] = None,
    ) -> Optional[PredictionOutcome]:
```

And update the call site in `calculate_outcome_for_prediction` (lines 112-121) to pass `post_datetime`:

**BEFORE** (lines 93-121):
```python
        prediction_date = self._get_source_date(prediction)
        ...
        for asset in prediction.assets:
            try:
                outcome = self._calculate_single_outcome(
                    prediction_id=prediction_id,
                    symbol=asset,
                    prediction_date=prediction_date,
                    sentiment=sentiment,
                    confidence=prediction.confidence,
                    force_refresh=force_refresh,
                )
```

**AFTER**:
```python
        prediction_date = self._get_source_date(prediction)
        ...
        post_datetime = self._get_source_datetime(prediction)
        ...
        for asset in prediction.assets:
            try:
                outcome = self._calculate_single_outcome(
                    prediction_id=prediction_id,
                    symbol=asset,
                    prediction_date=prediction_date,
                    sentiment=sentiment,
                    confidence=prediction.confidence,
                    force_refresh=force_refresh,
                    post_datetime=post_datetime,
                )
```

Then in `_calculate_single_outcome`, use `post_datetime` directly instead of re-querying:

```python
        # ── Intraday timeframes ────────
        if post_datetime and price_t0:
            outcome.post_published_at = post_datetime
            # ... (rest of intraday block as above, using post_datetime directly)
```

---

### Step 7: Update `get_price_on_date` to use MarketCalendar for lookback

**File**: `/Users/chris/Projects/shitpost-alpha/shit/market_data/client.py`

The current `get_price_on_date` (lines 254-296) walks backward by calendar days. With the market calendar, it can walk backward by trading days for a more accurate fallback.

**BEFORE** (lines 254-296):
```python
    def get_price_on_date(
        self,
        symbol: str,
        target_date: date,
        lookback_days: int = 7
    ) -> Optional[MarketPrice]:
        """Get price for a specific date, with fallback for market closed days."""
        price = self.session.query(MarketPrice).filter(
            and_(
                MarketPrice.symbol == symbol,
                MarketPrice.date == target_date
            )
        ).first()

        if price:
            return price

        logger.debug(
            f"No price found for {symbol} on {target_date}, checking previous days",
            extra={"symbol": symbol, "target_date": str(target_date)}
        )

        for days_back in range(1, lookback_days + 1):
            check_date = target_date - timedelta(days=days_back)
            price = self.session.query(MarketPrice).filter(
                and_(
                    MarketPrice.symbol == symbol,
                    MarketPrice.date == check_date
                )
            ).first()

            if price:
                logger.debug(
                    f"Found price for {symbol} on {check_date} ({days_back} days before {target_date})",
                    extra={"symbol": symbol, "price_date": str(check_date)}
                )
                return price

        logger.warning(
            f"No price found for {symbol} within {lookback_days} days of {target_date}",
            extra={"symbol": symbol, "target_date": str(target_date), "lookback_days": lookback_days}
        )
        return None
```

**AFTER**:
```python
    def get_price_on_date(
        self,
        symbol: str,
        target_date: date,
        lookback_days: int = 7
    ) -> Optional[MarketPrice]:
        """Get price for a specific date, with fallback for non-trading days.

        Uses the market calendar to walk backward through actual trading days
        rather than calendar days. If target_date is a weekend or holiday,
        this returns the most recent trading day's close.
        """
        from shit.market_data.market_calendar import MarketCalendar

        price = self.session.query(MarketPrice).filter(
            and_(
                MarketPrice.symbol == symbol,
                MarketPrice.date == target_date
            )
        ).first()

        if price:
            return price

        logger.debug(
            f"No price found for {symbol} on {target_date}, checking previous trading days",
            extra={"symbol": symbol, "target_date": str(target_date)}
        )

        # Use market calendar to find the most recent trading day
        calendar = MarketCalendar()
        check_date = target_date
        for _ in range(lookback_days):
            try:
                check_date = calendar.previous_trading_day(check_date)
            except Exception:
                # Fallback to naive walk if calendar fails
                check_date = check_date - timedelta(days=1)
                while check_date.weekday() >= 5:
                    check_date -= timedelta(days=1)

            price = self.session.query(MarketPrice).filter(
                and_(
                    MarketPrice.symbol == symbol,
                    MarketPrice.date == check_date
                )
            ).first()

            if price:
                logger.debug(
                    f"Found price for {symbol} on {check_date} (nearest trading day before {target_date})",
                    extra={"symbol": symbol, "price_date": str(check_date)}
                )
                return price

        logger.warning(
            f"No price found for {symbol} within {lookback_days} trading days of {target_date}",
            extra={"symbol": symbol, "target_date": str(target_date), "lookback_days": lookback_days}
        )
        return None
```

**Why**: The import is inside the method (not at module level) to avoid circular imports, since `client.py` is imported by many modules. The `MarketCalendar` is cheap to instantiate (exchange_calendars caches internally).

---

### Step 8: Update `__init__.py` exports

**File**: `/Users/chris/Projects/shitpost-alpha/shit/market_data/__init__.py`

Add the new imports:

**BEFORE** (lines 1-28):
```python
from shit.market_data.models import MarketPrice, PredictionOutcome, TickerRegistry
from shit.market_data.client import MarketDataClient
from shit.market_data.outcome_calculator import OutcomeCalculator
from shit.market_data.price_provider import PriceProvider, ProviderChain, RawPriceRecord, ProviderError
from shit.market_data.yfinance_provider import YFinanceProvider
from shit.market_data.alphavantage_provider import AlphaVantageProvider
from shit.market_data.health import run_health_check, HealthReport

__all__ = [
    "MarketPrice",
    "PredictionOutcome",
    "TickerRegistry",
    "MarketDataClient",
    "OutcomeCalculator",
    "PriceProvider",
    "ProviderChain",
    "RawPriceRecord",
    "ProviderError",
    "YFinanceProvider",
    "AlphaVantageProvider",
    "run_health_check",
    "HealthReport",
]
```

**AFTER**:
```python
from shit.market_data.models import MarketPrice, PredictionOutcome, TickerRegistry
from shit.market_data.client import MarketDataClient
from shit.market_data.outcome_calculator import OutcomeCalculator
from shit.market_data.price_provider import PriceProvider, ProviderChain, RawPriceRecord, ProviderError
from shit.market_data.yfinance_provider import YFinanceProvider
from shit.market_data.alphavantage_provider import AlphaVantageProvider
from shit.market_data.health import run_health_check, HealthReport
from shit.market_data.market_calendar import MarketCalendar

__all__ = [
    "MarketPrice",
    "PredictionOutcome",
    "TickerRegistry",
    "MarketDataClient",
    "OutcomeCalculator",
    "PriceProvider",
    "ProviderChain",
    "RawPriceRecord",
    "ProviderError",
    "YFinanceProvider",
    "AlphaVantageProvider",
    "run_health_check",
    "HealthReport",
    "MarketCalendar",
]
```

---

## Test Plan

### New test file: `shit_tests/shit/market_data/test_market_calendar.py`

Create a comprehensive test suite for the `MarketCalendar` class:

```python
"""Tests for MarketCalendar (shit/market_data/market_calendar.py)."""

import pytest
from datetime import date, datetime, timezone

from shit.market_data.market_calendar import MarketCalendar


@pytest.fixture
def cal():
    return MarketCalendar()


class TestIsTradingDay:
    def test_weekday_is_trading_day(self, cal):
        # Monday 2025-06-16
        assert cal.is_trading_day(date(2025, 6, 16)) is True

    def test_saturday_is_not_trading_day(self, cal):
        assert cal.is_trading_day(date(2025, 6, 14)) is False

    def test_sunday_is_not_trading_day(self, cal):
        assert cal.is_trading_day(date(2025, 6, 15)) is False

    def test_christmas_is_not_trading_day(self, cal):
        assert cal.is_trading_day(date(2025, 12, 25)) is False

    def test_july_4th_is_not_trading_day(self, cal):
        assert cal.is_trading_day(date(2025, 7, 4)) is False

    def test_new_years_day_is_not_trading_day(self, cal):
        assert cal.is_trading_day(date(2026, 1, 1)) is False


class TestNextTradingDay:
    def test_friday_next_is_monday(self, cal):
        result = cal.next_trading_day(date(2025, 6, 13))  # Friday
        assert result == date(2025, 6, 16)  # Monday

    def test_saturday_next_is_monday(self, cal):
        result = cal.next_trading_day(date(2025, 6, 14))  # Saturday
        assert result == date(2025, 6, 16)

    def test_wednesday_next_is_thursday(self, cal):
        result = cal.next_trading_day(date(2025, 6, 11))  # Wednesday
        assert result == date(2025, 6, 12)  # Thursday

    def test_day_before_holiday_skips_holiday(self, cal):
        # July 3 2025 is Thursday, July 4 is holiday, next = July 7 (Monday)
        result = cal.next_trading_day(date(2025, 7, 3))
        assert result == date(2025, 7, 7)


class TestTradingDayOffset:
    def test_t_plus_1_on_friday_is_monday(self, cal):
        result = cal.trading_day_offset(date(2025, 6, 13), 1)  # Friday +1
        assert result == date(2025, 6, 16)  # Monday

    def test_t_plus_3_on_friday(self, cal):
        result = cal.trading_day_offset(date(2025, 6, 13), 3)  # Friday +3
        assert result == date(2025, 6, 18)  # Wednesday

    def test_t_plus_7_spans_full_week(self, cal):
        result = cal.trading_day_offset(date(2025, 6, 9), 7)  # Monday +7
        assert result == date(2025, 6, 18)  # Next Wednesday

    def test_t_plus_1_on_saturday_snaps_forward(self, cal):
        result = cal.trading_day_offset(date(2025, 6, 14), 1)  # Saturday +1
        assert result == date(2025, 6, 17)  # Tuesday (Monday=snap + 1)

    def test_offset_zero_returns_nearest_trading_day(self, cal):
        result = cal.trading_day_offset(date(2025, 6, 14), 0)  # Saturday
        assert result == date(2025, 6, 16)  # Monday

    def test_negative_offset(self, cal):
        result = cal.trading_day_offset(date(2025, 6, 16), -1)  # Monday -1
        assert result == date(2025, 6, 13)  # Friday

    def test_offset_across_holiday(self, cal):
        # July 3 2025 (Thu) + 1 should skip July 4 (holiday) -> July 7 (Mon)
        result = cal.trading_day_offset(date(2025, 7, 3), 1)
        assert result == date(2025, 7, 7)


class TestTradingDaysBetween:
    def test_monday_to_friday_is_5(self, cal):
        result = cal.trading_days_between(date(2025, 6, 9), date(2025, 6, 13))
        assert result == 5

    def test_friday_to_monday_is_2(self, cal):
        result = cal.trading_days_between(date(2025, 6, 13), date(2025, 6, 16))
        assert result == 2

    def test_same_day_trading_day_is_1(self, cal):
        result = cal.trading_days_between(date(2025, 6, 9), date(2025, 6, 9))
        assert result == 1

    def test_same_day_non_trading_is_0(self, cal):
        result = cal.trading_days_between(date(2025, 6, 14), date(2025, 6, 14))
        assert result == 0


class TestMarketHours:
    def test_next_market_close_during_hours(self, cal):
        # 2 PM UTC on a Monday (10 AM ET) -- market is open, close is 8 PM UTC (4 PM ET)
        dt = datetime(2025, 6, 16, 14, 0, 0, tzinfo=timezone.utc)
        result = cal.next_market_close(dt)
        assert result.date() == date(2025, 6, 16)

    def test_next_market_close_after_hours(self, cal):
        # 9 PM UTC on Monday (5 PM ET) -- after close, next close is Tuesday
        dt = datetime(2025, 6, 16, 21, 0, 0, tzinfo=timezone.utc)
        result = cal.next_market_close(dt)
        assert result.date() == date(2025, 6, 17)

    def test_next_market_close_on_weekend(self, cal):
        dt = datetime(2025, 6, 14, 12, 0, 0, tzinfo=timezone.utc)  # Saturday
        result = cal.next_market_close(dt)
        assert result.date() == date(2025, 6, 16)  # Monday's close

    def test_is_market_open_during_session(self, cal):
        # 2 PM UTC (10 AM ET) on a trading day
        dt = datetime(2025, 6, 16, 14, 0, 0, tzinfo=timezone.utc)
        assert cal.is_market_open(dt) is True

    def test_is_market_open_after_close(self, cal):
        dt = datetime(2025, 6, 16, 21, 0, 0, tzinfo=timezone.utc)
        assert cal.is_market_open(dt) is False

    def test_is_market_open_on_weekend(self, cal):
        dt = datetime(2025, 6, 14, 14, 0, 0, tzinfo=timezone.utc)
        assert cal.is_market_open(dt) is False


class TestNaiveFallbacks:
    """Test that fallback methods work when exchange_calendars fails."""

    def test_naive_next_trading_day_skips_weekend(self):
        result = MarketCalendar._naive_next_trading_day(date(2025, 6, 13))
        assert result == date(2025, 6, 16)

    def test_naive_previous_trading_day_skips_weekend(self):
        result = MarketCalendar._naive_previous_trading_day(date(2025, 6, 16))
        assert result == date(2025, 6, 13)

    def test_naive_offset_forward(self):
        result = MarketCalendar._naive_offset(date(2025, 6, 13), 3)
        assert result == date(2025, 6, 18)
```

### New test file: `shit_tests/shit/market_data/test_intraday_provider.py`

```python
"""Tests for intraday_provider.py."""

import pytest
from datetime import date, datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from shit.market_data.intraday_provider import (
    IntradayPriceSnapshot,
    fetch_intraday_snapshot,
)


class TestIntradayPriceSnapshot:
    def test_defaults_to_none(self):
        snap = IntradayPriceSnapshot()
        assert snap.price_at_post is None
        assert snap.price_1h_after is None
        assert snap.price_at_next_close is None

    def test_accepts_values(self):
        snap = IntradayPriceSnapshot(
            price_at_post=150.0,
            price_1h_after=151.0,
            price_at_next_close=149.5,
        )
        assert snap.price_at_post == 150.0


class TestFetchIntradaySnapshot:
    @patch("shit.market_data.intraday_provider.YFinanceProvider")
    @patch("shit.market_data.intraday_provider.MarketCalendar")
    def test_returns_empty_snapshot_when_no_bars(self, mock_cal_cls, mock_yf_cls):
        mock_cal = mock_cal_cls.return_value
        mock_cal.is_trading_day.return_value = True
        mock_cal.session_close_time.return_value = datetime(2025, 6, 16, 20, 0, tzinfo=timezone.utc)
        mock_cal.nearest_trading_day.return_value = date(2025, 6, 16)

        mock_provider = mock_yf_cls.return_value
        mock_provider.fetch_intraday_prices.return_value = []

        result = fetch_intraday_snapshot("AAPL", datetime(2025, 6, 16, 14, 0, tzinfo=timezone.utc))
        assert result.price_at_post is None

    @patch("shit.market_data.intraday_provider.YFinanceProvider")
    @patch("shit.market_data.intraday_provider.MarketCalendar")
    def test_finds_price_at_post(self, mock_cal_cls, mock_yf_cls):
        mock_cal = mock_cal_cls.return_value
        mock_cal.is_trading_day.return_value = True
        mock_cal.session_close_time.return_value = datetime(2025, 6, 16, 20, 0, tzinfo=timezone.utc)
        mock_cal.nearest_trading_day.return_value = date(2025, 6, 16)

        # Create mock bars
        bar1 = MagicMock(close=150.0, open=149.5)
        bar1.bar_datetime = datetime(2025, 6, 16, 13, 30, tzinfo=timezone.utc)
        bar2 = MagicMock(close=151.0, open=150.0)
        bar2.bar_datetime = datetime(2025, 6, 16, 14, 30, tzinfo=timezone.utc)
        bar3 = MagicMock(close=152.0, open=151.0)
        bar3.bar_datetime = datetime(2025, 6, 16, 15, 30, tzinfo=timezone.utc)

        mock_provider = mock_yf_cls.return_value
        mock_provider.fetch_intraday_prices.return_value = [bar1, bar2, bar3]

        # Post at 2:15 PM UTC
        result = fetch_intraday_snapshot(
            "AAPL",
            datetime(2025, 6, 16, 14, 15, tzinfo=timezone.utc),
        )
        # Closest bar at or before 2:15 PM is bar1 (1:30 PM)
        assert result.price_at_post == 150.0
        # 1h after 2:15 PM is 3:15 PM, closest bar at/before that is bar2 (2:30 PM)
        assert result.price_1h_after == 151.0
```

### Modify existing test file: `shit_tests/shit/market_data/test_outcome_calculator.py`

Update existing tests to account for `MarketCalendar` being used instead of `timedelta`:

1. **Mock the calendar in the `calculator` fixture**:

```python
@pytest.fixture
def calculator(mock_session):
    calc = OutcomeCalculator(session=mock_session)
    calc.market_client = MagicMock()
    # Mock the market calendar to behave like simple date arithmetic for existing tests
    mock_calendar = MagicMock()
    mock_calendar.trading_day_offset.side_effect = lambda d, n: d + timedelta(days=n)
    mock_calendar.previous_trading_day.side_effect = lambda d: d - timedelta(days=1)
    mock_calendar.nearest_trading_day.side_effect = lambda d: d
    mock_calendar.is_trading_day.return_value = True
    mock_calendar.session_close_time.return_value = None
    calc._calendar = mock_calendar
    return calc
```

2. **Add a new test class for trading-day behavior**:

```python
class TestTradingDayTimeframes:
    """Verify that outcome calculation uses trading days, not calendar days."""

    @patch("shit.market_data.outcome_calculator.date")
    def test_friday_prediction_t1_is_monday(self, mock_date, calculator, mock_session):
        """T+1 on Friday should use Monday's close, not Saturday."""
        mock_date.today.return_value = date(2025, 7, 20)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)

        # Override calendar mock to use real trading-day logic
        real_cal = MarketCalendar()
        calculator._calendar = real_cal

        mock_session.query.return_value.filter.return_value.first.return_value = None
        mock_price = MagicMock(close=100.0)
        calculator.market_client.get_price_on_date.return_value = mock_price

        result = calculator._calculate_single_outcome(
            prediction_id=1,
            symbol="AAPL",
            prediction_date=date(2025, 6, 13),  # Friday
            sentiment="bullish",
            confidence=0.8,
        )

        # Verify T+1 call was for Monday June 16, not Saturday June 14
        calls = calculator.market_client.get_price_on_date.call_args_list
        # First call is price_at_prediction (June 13)
        # Second call should be T+1 = June 16 (Monday)
        t1_call_date = calls[1][0][1]  # second positional arg of second call
        assert t1_call_date == date(2025, 6, 16)

    @patch("shit.market_data.outcome_calculator.date")
    def test_holiday_skip(self, mock_date, calculator, mock_session):
        """T+1 before July 4 holiday should skip to the next trading day."""
        mock_date.today.return_value = date(2025, 7, 20)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)

        real_cal = MarketCalendar()
        calculator._calendar = real_cal

        mock_session.query.return_value.filter.return_value.first.return_value = None
        mock_price = MagicMock(close=100.0)
        calculator.market_client.get_price_on_date.return_value = mock_price

        result = calculator._calculate_single_outcome(
            prediction_id=1,
            symbol="AAPL",
            prediction_date=date(2025, 7, 3),  # Thursday before July 4
            sentiment="bullish",
            confidence=0.8,
        )

        calls = calculator.market_client.get_price_on_date.call_args_list
        # T+1 should be July 7 (Monday), skipping July 4 (holiday) and weekend
        t1_call_date = calls[1][0][1]
        assert t1_call_date == date(2025, 7, 7)
```

3. **Add tests for the new `_get_source_datetime` method**:

```python
class TestGetSourceDatetime:
    def test_returns_datetime_from_shitpost(self, calculator):
        pred = _make_prediction(
            shitpost_timestamp=datetime(2025, 6, 14, 9, 30, 0),
        )
        result = calculator._get_source_datetime(pred)
        assert result == datetime(2025, 6, 14, 9, 30, 0, tzinfo=timezone.utc)

    def test_returns_none_when_no_timestamps(self, calculator):
        pred = _make_prediction(shitpost=None, signal=None, created_at=None)
        result = calculator._get_source_datetime(pred)
        assert result is None
```

---

## Documentation Updates

### CLAUDE.md

Update the `prediction_outcomes` table documentation in the Database Architecture section to include the new columns:

```markdown
**`prediction_outcomes`** - Validated prediction accuracy with returns
- `id`, `prediction_id` (FK -> predictions.id), `symbol`
- Prediction snapshot: `prediction_date`, `prediction_sentiment`, `prediction_confidence`
- Post timing: `post_published_at` (full datetime of source post)
- Price at prediction: `price_at_prediction` (daily close)
- Intraday prices: `price_at_post`, `price_at_next_close`, `price_1h_after`
- Price evolution: `price_t1`, `price_t3`, `price_t7`, `price_t30` (trading-day offsets)
- Returns (daily): `return_t1`, `return_t3`, `return_t7`, `return_t30`
- Returns (intraday): `return_same_day`, `return_1h`
- Accuracy (daily): `correct_t1`, `correct_t3`, `correct_t7`, `correct_t30`
- Accuracy (intraday): `correct_same_day`, `correct_1h`
- P&L (daily): `pnl_t1`, `pnl_t3`, `pnl_t7`, `pnl_t30`
- P&L (intraday): `pnl_same_day`, `pnl_1h`
- `is_complete` (boolean) -- All timeframes tracked?
```

Add a note in the Architecture section:

```markdown
**Timeframe semantics**: All T+N timeframes use **trading days**, not calendar days.
T+1 on a Friday resolves to Monday. Holidays are skipped automatically via `exchange_calendars`.
```

### db-admin command

Update the `prediction_outcomes` table in `.claude/commands/db-admin.md` to include the new columns.

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Added
- **Market Calendar** - NYSE trading-day awareness via `exchange_calendars` library
  - New `shit/market_data/market_calendar.py` utility class
  - `is_trading_day()`, `next_trading_day()`, `trading_day_offset()`, `next_market_close()`, etc.
- **Intraday Price Capture** - Snapshot prices at post time for short-term tracking
  - New `price_at_post`, `price_1h_after`, `price_at_next_close` columns on `prediction_outcomes`
  - New `return_same_day`, `return_1h` timeframes with corresponding `correct_*` and `pnl_*` columns
  - New `post_published_at` column storing full publication datetime

### Changed
- **Trading-Day Timeframes** - T+1/T+3/T+7/T+30 now use trading days, not calendar days
  - Friday T+1 resolves to Monday (not Saturday)
  - Holidays are automatically skipped
  - Existing outcome data is NOT retroactively recalculated; new behavior applies to future outcomes
- **Price Lookback** - `get_price_on_date()` now walks backward through trading days using the market calendar instead of raw calendar days
```

---

## Stress Testing & Edge Cases

### Edge Cases to Handle

1. **Post at 10 PM EST on Friday**: Next market session is Monday. Intraday snapshot should fetch Monday's bars. `price_at_post` will use Monday's open (since post is before market open).

2. **Post on Christmas Day**: `nearest_trading_day` should return the next open session (Dec 26 if that is a weekday, otherwise later).

3. **Post 1 minute before market close**: `price_1h_after` will be `None` because no bar exists 1 hour later (market closed). This is expected -- the field is nullable.

4. **Crypto symbols (e.g., BTC-USD)**: The market calendar is for NYSE. Crypto trades 24/7. For crypto symbols, the intraday logic will still work (yfinance returns hourly bars for crypto), but the "trading day" concept does not apply. The `trading_day_offset` will still produce reasonable dates (skipping weekends), which is conservative but not harmful.

5. **exchange_calendars range limits**: The library covers a finite range (typically past ~20 years to ~2-3 years in the future). The fallback methods handle `ValueError` for out-of-range dates.

6. **yfinance intraday data unavailable**: Some symbols (OTC stocks, some international) may not have intraday data. The `fetch_intraday_snapshot` returns `None` for all fields, and the outcome calculator gracefully skips intraday calculations.

7. **Backward compatibility**: Existing `PredictionOutcome` rows will have `NULL` for all new columns. The `return_t7`/`correct_t7`/`pnl_t7` columns that the dashboard uses are unchanged in name and semantics (they still represent "7 periods later"). The only behavioral change is that new outcomes will measure 7 *trading* days instead of 7 *calendar* days, which is actually more accurate.

### Performance Considerations

- `MarketCalendar` instantiation is cheap (the underlying `exchange_calendars` library caches calendar objects globally).
- Intraday fetches add one yfinance API call per symbol per prediction. For a typical prediction with 2 assets, this adds 2 API calls. Given the system processes ~5-10 predictions per day, this is negligible.
- No new database indexes are needed for the new columns (they are never queried as filters -- only read when displaying an outcome).

---

## Behavioral Change Migration Note

**IMPORTANT**: This phase changes the meaning of T+1/T+3/T+7/T+30 from calendar days to trading days.

- **Before**: T+7 = `prediction_date + timedelta(days=7)` = 7 calendar days (includes weekends)
- **After**: T+7 = `calendar.trading_day_offset(prediction_date, 7)` = 7 trading days (~9-10 calendar days)

**Impact on existing data**: Existing `PredictionOutcome` rows were calculated using calendar days. They will NOT be retroactively recalculated unless the user runs `calculate-outcomes --force`. New outcomes going forward will use trading days.

**Impact on dashboard**: The dashboard queries reference `return_t7`, `correct_t7`, etc. These column names are unchanged. The dashboard will seamlessly display outcomes calculated under either regime. Over time, as old outcomes age out and new trading-day outcomes accumulate, the metrics will become more accurate.

**Recommendation**: After deploying this phase, consider running `calculate-outcomes --force --days-back 90` to recalculate recent outcomes using trading-day logic. This is optional and costs nothing (no API calls for already-stored prices).

---

## Verification Checklist

1. [ ] `exchange_calendars>=4.5.0` added to `requirements.txt`
2. [ ] `pip install exchange_calendars` succeeds
3. [ ] `python -c "from shit.market_data.market_calendar import MarketCalendar; c = MarketCalendar(); print(c.is_trading_day(__import__('datetime').date(2025, 12, 25)))"` prints `False`
4. [ ] All new columns added to production via `ALTER TABLE` SQL
5. [ ] `source venv/bin/activate && pytest shit_tests/shit/market_data/test_market_calendar.py -v` passes
6. [ ] `source venv/bin/activate && pytest shit_tests/shit/market_data/test_intraday_provider.py -v` passes
7. [ ] `source venv/bin/activate && pytest shit_tests/shit/market_data/test_outcome_calculator.py -v` passes (existing tests still pass with calendar mock)
8. [ ] `source venv/bin/activate && pytest shit_tests/shit/market_data/ -v` -- all market data tests pass
9. [ ] `source venv/bin/activate && pytest -v` -- full test suite passes
10. [ ] `ruff check shit/market_data/market_calendar.py shit/market_data/intraday_provider.py`
11. [ ] `ruff format shit/market_data/`
12. [ ] Manual verification: Run `python -m shit.market_data calculate-outcomes --limit 5` and check that T+1 dates skip weekends in the logs
13. [ ] CHANGELOG.md updated
14. [ ] CLAUDE.md database schema docs updated

---

## "What NOT To Do" Section

1. **Do NOT store intraday prices in `market_prices`**. The `market_prices` table is daily OHLCV only. Intraday data is ephemeral -- fetched once, used to populate PredictionOutcome columns, then discarded. Adding intraday rows to `market_prices` would bloat the table and complicate all existing queries.

2. **Do NOT retroactively recalculate all historical outcomes automatically**. The behavioral change from calendar days to trading days should be opt-in (via `--force`). Silently changing historical accuracy metrics could confuse users.

3. **Do NOT add the `MarketCalendar` import at the top of `client.py`**. Use a local import inside `get_price_on_date` to avoid circular imports. The `client.py` module is imported by many other modules and adding heavy imports at the top can cause import ordering issues.

4. **Do NOT make `fetch_intraday_prices` part of the `PriceProvider` abstract interface**. The `PriceProvider` interface is for daily OHLCV with a well-defined contract. Intraday is a yfinance-specific bonus feature. Forcing AlphaVantage to implement it would couple the interface to a feature not all providers support.

5. **Do NOT use `exchange_calendars` for crypto symbols**. The calendar is NYSE-specific. Crypto trades 24/7. The trading-day offset will still work (weekday arithmetic) but the intraday "market open/close" concepts do not apply. The intraday provider should just use the bars as-is for crypto.

6. **Do NOT add the new intraday columns to dashboard queries yet**. This phase focuses on data capture and outcome calculation. Dashboard integration for `return_same_day` and `return_1h` should be a separate phase to keep the PR focused.

7. **Do NOT use `bar_datetime` as a formal field on `RawPriceRecord`**. It is attached as a dynamic attribute because `RawPriceRecord` is a frozen-like dataclass designed for daily prices. Changing its schema would break the `PriceProvider` interface contract.

8. **Do NOT forget to handle the `post_datetime=None` case in `_calculate_single_outcome`**. If the post datetime is unavailable (legacy predictions), the intraday block must be entirely skipped. Never pass `None` to `fetch_intraday_snapshot`.
