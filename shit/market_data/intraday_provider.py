"""
Intraday Price Provider
Fetches intraday prices near a specific timestamp for prediction tracking.

This is intentionally simple -- it fetches 1h bars for a single day and finds
the bar closest to the requested timestamp. NOT stored in the database
(intraday data is too voluminous). Used only to populate snapshot columns
on PredictionOutcome at creation time.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

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
        bar_dt = bar.bar_datetime
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
