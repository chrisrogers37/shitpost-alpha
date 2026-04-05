"""Price data API router — OHLCV candles for charts + live quotes."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.queries.price_queries import get_price_data
from api.schemas.feed import LiveQuoteResponse, PriceResponse

router = APIRouter()


@router.get("/{symbol}/live", response_model=LiveQuoteResponse)
def get_live_quote(symbol: str):
    """Get the current live price for a symbol.

    Uses yfinance fast_info for a lightweight single HTTP call (~300ms).
    Returns 404 if the symbol is invalid or yfinance is unavailable.
    """
    from shit.market_data.yfinance_provider import fetch_live_quote

    quote = fetch_live_quote(symbol.upper())
    if quote is None:
        raise HTTPException(status_code=404, detail=f"No quote available for {symbol}")
    return LiveQuoteResponse(
        symbol=quote.symbol,
        price=quote.price,
        previous_close=quote.previous_close,
        day_high=quote.day_high,
        day_low=quote.day_low,
        volume=quote.volume,
        captured_at=quote.captured_at.isoformat(),
    )


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
