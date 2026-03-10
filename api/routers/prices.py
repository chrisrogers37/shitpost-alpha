"""Price data API router — OHLCV candles for charts."""

from typing import Optional

from fastapi import APIRouter, Query

from api.queries.price_queries import get_price_data
from api.schemas.feed import PriceResponse

router = APIRouter()


@router.get("/{symbol}", response_model=PriceResponse)
def get_prices(
    symbol: str,
    days: int = Query(default=30, ge=1, le=365),
    post_timestamp: Optional[str] = Query(default=None),
):
    """Get OHLCV price data for a symbol.

    Args:
        symbol: Ticker symbol (e.g. 'AAPL').
        days: Calendar days of data (default 30, max 365).
        post_timestamp: ISO timestamp to mark on the chart.
    """
    data = get_price_data(symbol, days, post_timestamp)
    return PriceResponse(**data)
