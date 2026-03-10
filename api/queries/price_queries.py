"""Price data queries for the chart API.

Adapted from shitty_ui/data/asset_queries.py patterns.
"""

from datetime import datetime, timedelta
from typing import Any, Optional

from api.dependencies import execute_query, logger


def get_price_data(
    symbol: str,
    days: int = 30,
    post_timestamp: Optional[str] = None,
) -> dict[str, Any]:
    """Get OHLCV candle data for a symbol, optionally centered around a post timestamp.

    Args:
        symbol: Ticker symbol (e.g. 'AAPL').
        days: Number of calendar days of data to return.
        post_timestamp: ISO timestamp of the post. Used to calculate post_date_index.

    Returns:
        Dict with 'symbol', 'candles' (list of OHLCV dicts), 'post_date_index',
        and 'post_timestamp'.
    """
    start_date = (datetime.now() - timedelta(days=days)).date()

    query = """
        SELECT
            date,
            open,
            high,
            low,
            close,
            volume
        FROM market_prices
        WHERE symbol = :symbol
            AND date >= :start_date
        ORDER BY date ASC
    """

    rows, columns = execute_query(
        query, {"symbol": symbol.upper(), "start_date": start_date}
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
                "close": float(row_dict["close"])
                if row_dict["close"] is not None
                else 0,
                "volume": int(row_dict["volume"])
                if row_dict["volume"] is not None
                else 0,
            }
        )

    # Find the candle index closest to the post timestamp
    post_date_index = None
    if post_timestamp and candles:
        try:
            post_dt = datetime.fromisoformat(post_timestamp.replace("Z", "+00:00"))
            post_date_str = str(post_dt.date())

            # Find exact date match or closest date
            for i, candle in enumerate(candles):
                if candle["date"] == post_date_str:
                    post_date_index = i
                    break
                if candle["date"] > post_date_str:
                    # Post was before market data starts or falls on weekend
                    post_date_index = max(0, i - 1) if i > 0 else 0
                    break

            # If post date is after all candles, use last candle
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
