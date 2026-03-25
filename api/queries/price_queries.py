"""Price data queries for the chart API.

Fetches live OHLCV data from yfinance for fresh charts.
Falls back to the market_prices database table if yfinance fails.
"""

from datetime import datetime, timedelta, date
from typing import Any, Optional

import yfinance as yf

from api.dependencies import execute_query, logger


def _fetch_from_yfinance(symbol: str, start: date, end: date) -> list[dict[str, Any]]:
    """Fetch OHLCV candles directly from yfinance."""
    ticker = yf.Ticker(symbol)
    hist = ticker.history(start=start, end=end + timedelta(days=1))

    if hist.empty:
        return []

    candles = []
    for idx, row in hist.iterrows():
        price_date = idx.date() if hasattr(idx, "date") else idx
        candles.append(
            {
                "date": str(price_date),
                "open": float(row["Open"]) if row["Open"] is not None else 0,
                "high": float(row["High"]) if row["High"] is not None else 0,
                "low": float(row["Low"]) if row["Low"] is not None else 0,
                "close": float(row["Close"]) if row["Close"] is not None else 0,
                "volume": int(row["Volume"]) if row["Volume"] is not None else 0,
            }
        )
    return candles


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

    candles = []
    for row in rows:
        row_dict = dict(zip(columns, row))
        candles.append(
            {
                "date": str(row_dict["date"]),
                "open": float(row_dict["open"]) if row_dict["open"] is not None else 0,
                "high": float(row_dict["high"]) if row_dict["high"] is not None else 0,
                "low": float(row_dict["low"]) if row_dict["low"] is not None else 0,
                "close": float(row_dict["close"]) if row_dict["close"] is not None else 0,
                "volume": int(row_dict["volume"]) if row_dict["volume"] is not None else 0,
            }
        )
    return candles


def get_price_data(
    symbol: str,
    days: int = 30,
    post_timestamp: Optional[str] = None,
) -> dict[str, Any]:
    """Get OHLCV candle data for a symbol with live yfinance data.

    Fetches directly from yfinance for fresh data. Falls back to the
    market_prices database if yfinance is unavailable.
    """
    start_date = (datetime.now() - timedelta(days=days)).date()
    end_date = datetime.now().date()

    # Try yfinance first for live data
    try:
        candles = _fetch_from_yfinance(symbol.upper(), start_date, end_date)
        if candles:
            logger.info(
                f"Fetched {len(candles)} candles from yfinance for {symbol}",
                extra={"symbol": symbol, "count": len(candles)},
            )
    except Exception as e:
        logger.warning(f"yfinance failed for {symbol}, falling back to DB: {e}")
        candles = []

    # Fall back to database if yfinance returned nothing
    if not candles:
        candles = _fetch_from_database(symbol.upper(), start_date)

    # Find the candle index closest to the post timestamp
    post_date_index = None
    if post_timestamp and candles:
        try:
            post_dt = datetime.fromisoformat(post_timestamp.replace("Z", "+00:00"))
            post_date_str = str(post_dt.date())

            # Find exact date match or closest trading day
            for i, candle in enumerate(candles):
                if candle["date"] == post_date_str:
                    post_date_index = i
                    break
                if candle["date"] > post_date_str:
                    post_date_index = max(0, i - 1) if i > 0 else 0
                    break

            # If post date is after all candles (data gap), use last candle
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
