"""
Market Timing Utilities

Shared functions for classifying timestamps relative to NYSE market hours.
Used by the feed router (for display), snapshot service (for metadata),
and potentially other consumers.
"""

from datetime import datetime, timezone
from functools import lru_cache

from shit.logging import get_service_logger

logger = get_service_logger("market_timing")


@lru_cache(maxsize=1)
def _get_calendar():
    """Lazy singleton for MarketCalendar (avoids import at module load)."""
    from shit.market_data.market_calendar import MarketCalendar

    return MarketCalendar()


def classify_market_status(dt: datetime) -> str:
    """Classify a datetime relative to NYSE market hours.

    Returns one of: "PRE_MARKET", "MARKET_OPEN", "AFTER_HOURS",
    "CLOSED" (weekend/holiday), or "UNKNOWN" (on error).
    """
    try:
        cal = _get_calendar()
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        if not cal.is_trading_day(dt.date()):
            return "CLOSED"

        if cal.is_market_open(dt):
            return "MARKET_OPEN"

        open_time = cal.session_open_time(dt.date())
        if open_time and dt < open_time:
            return "PRE_MARKET"

        return "AFTER_HOURS"
    except Exception:
        logger.debug("Could not classify market status", exc_info=True)
        return "UNKNOWN"


def compute_market_timing(
    timestamp: datetime,
) -> tuple[str, str]:
    """Classify a post timestamp and compute a human-readable delta.

    Returns:
        (status, delta_text) e.g. ("PRE_MARKET", "47m before open")
    """
    try:
        cal = _get_calendar()
        if timestamp.tzinfo is None:
            dt = timestamp.replace(tzinfo=timezone.utc)
        else:
            dt = timestamp
        d = dt.date()

        if not cal.is_trading_day(d):
            next_open = cal.next_market_open(dt)
            delta = next_open - dt
            hours = int(delta.total_seconds() // 3600)
            mins = int((delta.total_seconds() % 3600) // 60)
            if hours > 24:
                return "CLOSED", f"{hours // 24}d {hours % 24}h to open"
            elif hours > 0:
                return "CLOSED", f"{hours}h {mins}m to open"
            else:
                return "CLOSED", f"{mins}m to open"

        open_time = cal.session_open_time(d)
        close_time = cal.session_close_time(d)

        if open_time and close_time:
            if dt < open_time:
                delta = open_time - dt
                mins = int(delta.total_seconds() // 60)
                if mins >= 60:
                    return "PRE_MARKET", f"{mins // 60}h {mins % 60}m before open"
                return "PRE_MARKET", f"{mins}m before open"
            elif dt >= close_time:
                delta = dt - close_time
                mins = int(delta.total_seconds() // 60)
                if mins >= 60:
                    return "AFTER_HOURS", f"{mins // 60}h {mins % 60}m after close"
                return "AFTER_HOURS", f"{mins}m after close"
            else:
                return "MARKET_OPEN", "during market hours"

        return "MARKET_OPEN", "during market hours"
    except Exception:
        logger.debug("Could not compute market timing", exc_info=True)
        return "UNKNOWN", ""


def compute_marker_dates(
    prediction_date, returns: dict
) -> dict[str, str]:
    """Compute actual dates for T+1, T+3, T+7, T+30 outcome markers."""
    if not prediction_date:
        return {}
    try:
        cal = _get_calendar()
        if hasattr(prediction_date, "date"):
            base_date = prediction_date.date()
        elif isinstance(prediction_date, str):
            from datetime import datetime as dt_cls

            base_date = dt_cls.fromisoformat(prediction_date).date()
        else:
            base_date = prediction_date

        markers = {}
        for offset, key in [(1, "t1"), (3, "t3"), (7, "t7"), (30, "t30")]:
            if returns.get(f"return_{key}") is not None:
                target = cal.trading_day_offset(base_date, offset)
                markers[key] = target.isoformat()
        return markers
    except Exception:
        logger.debug("Could not compute marker dates", exc_info=True)
        return {}
