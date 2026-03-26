"""Price data queries for the chart API.

Fetches live OHLCV data from yfinance for fresh charts.
Falls back to the market_prices database table if yfinance fails.
"""

import time
from datetime import datetime, timedelta, date
from typing import Any, Optional

from api.dependencies import execute_query, logger

# TTL cache: avoid hammering yfinance on repeated requests
_price_cache: dict[tuple[str, int], tuple[list[dict[str, Any]], float]] = {}
_CACHE_TTL = 300  # 5 minutes


def _fetch_from_yfinance(symbol: str, start: date, end: date) -> list[dict[str, Any]]:
    """Fetch OHLCV candles via the existing YFinanceProvider."""
    from shit.market_data.yfinance_provider import YFinanceProvider
    from shit.market_data.price_provider import ProviderError

    try:
        provider = YFinanceProvider()
        records = provider.fetch_prices(symbol, start, end)
        return [
            {
                "date": str(r.date),
                "open": float(r.open) if r.open is not None else 0,
                "high": float(r.high) if r.high is not None else 0,
                "low": float(r.low) if r.low is not None else 0,
                "close": float(r.close) if r.close is not None else 0,
                "volume": int(r.volume) if r.volume is not None else 0,
            }
            for r in records
        ]
    except ProviderError as e:
        logger.warning(f"YFinanceProvider failed for {symbol}: {e}")
        return []


def _fetch_from_database(symbol: str, start: date) -> list[dict[str, Any]]:
    """Fallback: fetch from market_prices database table."""
    query = """
        SELECT date, open, high, low, close, volume
        FROM market_prices
        WHERE symbol = :symbol AND date >= :start_date
        ORDER BY date ASC
    """
    rows, columns = execute_query(
        query, {"symbol": symbol.upper(), "start_date": start}
    )

    return [
        {
            "date": str(row_dict["date"]),
            "open": float(row_dict["open"]) if row_dict["open"] is not None else 0,
            "high": float(row_dict["high"]) if row_dict["high"] is not None else 0,
            "low": float(row_dict["low"]) if row_dict["low"] is not None else 0,
            "close": float(row_dict["close"]) if row_dict["close"] is not None else 0,
            "volume": int(row_dict["volume"]) if row_dict["volume"] is not None else 0,
        }
        for row_dict in (dict(zip(columns, row)) for row in rows)
    ]


def _get_candles(symbol: str, days: int) -> list[dict[str, Any]]:
    """Get candles with TTL caching. Tries yfinance first, DB fallback."""
    cache_key = (symbol.upper(), days)
    now = time.time()

    if cache_key in _price_cache:
        cached_candles, cached_at = _price_cache[cache_key]
        if now - cached_at < _CACHE_TTL:
            return cached_candles

    start_date = (datetime.now() - timedelta(days=days)).date()
    end_date = datetime.now().date()

    candles = _fetch_from_yfinance(symbol.upper(), start_date, end_date)
    if candles:
        logger.info(
            f"Fetched {len(candles)} candles from yfinance for {symbol}",
            extra={"symbol": symbol, "count": len(candles)},
        )
    else:
        candles = _fetch_from_database(symbol.upper(), start_date)

    _price_cache[cache_key] = (candles, now)
    return candles


def get_price_data(
    symbol: str,
    days: int = 30,
    post_timestamp: Optional[str] = None,
) -> dict[str, Any]:
    """Get OHLCV candle data for a symbol with live yfinance data.

    Fetches directly from yfinance for fresh data (with 5-min TTL cache).
    Falls back to the market_prices database if yfinance is unavailable.
    """
    candles = _get_candles(symbol, days)

    # Find the candle index closest to the post timestamp
    post_date_index = None
    if post_timestamp and candles:
        try:
            post_dt = datetime.fromisoformat(post_timestamp.replace("Z", "+00:00"))
            post_date_str = str(post_dt.date())

            for i, candle in enumerate(candles):
                if candle["date"] == post_date_str:
                    post_date_index = i
                    break
                if candle["date"] > post_date_str:
                    post_date_index = max(0, i - 1) if i > 0 else 0
                    break

            if post_date_index is None and candles:
                post_date_index = len(candles) - 1
        except (ValueError, TypeError) as e:
            logger.warning(f"Could not parse post_timestamp '{post_timestamp}': {e}")

    return {
        "symbol": symbol.upper(),
        "post_timestamp": post_timestamp,
        "candles": candles,
        "post_date_index": post_date_index,
    }
