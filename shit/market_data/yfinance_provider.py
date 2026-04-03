"""
yfinance Price Provider
Wraps the yfinance library behind the PriceProvider interface.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

import yfinance as yf

from shit.market_data.price_provider import PriceProvider, RawPriceRecord, ProviderError
from shit.logging import get_service_logger

logger = get_service_logger("yfinance_provider")


class YFinanceProvider(PriceProvider):
    """Price provider backed by the yfinance library."""

    @property
    def name(self) -> str:
        return "yfinance"

    def is_available(self) -> bool:
        """yfinance is always available (no API key needed)."""
        return True

    def fetch_prices(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> List[RawPriceRecord]:
        """Fetch prices from yfinance.

        Note: yfinance end_date is exclusive, so we add 1 day.
        """
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(start=start_date, end=end_date + timedelta(days=1))

            if hist.empty:
                logger.warning(
                    f"yfinance returned empty data for {symbol}",
                    extra={"symbol": symbol},
                )
                return []

            records = []
            for idx, row in hist.iterrows():
                price_date = idx.date() if hasattr(idx, "date") else idx

                record = RawPriceRecord(
                    symbol=symbol,
                    date=price_date,
                    open=float(row["Open"])
                    if "Open" in row and row["Open"] is not None
                    else None,
                    high=float(row["High"])
                    if "High" in row and row["High"] is not None
                    else None,
                    low=float(row["Low"])
                    if "Low" in row and row["Low"] is not None
                    else None,
                    close=float(row["Close"]) if "Close" in row else 0.0,
                    volume=int(row["Volume"])
                    if "Volume" in row and row["Volume"] is not None
                    else None,
                    adjusted_close=float(row["Close"]) if "Close" in row else None,
                    source="yfinance",
                )
                records.append(record)

            return records

        except Exception as e:
            raise ProviderError(
                "yfinance", f"Failed to fetch {symbol}: {e}", original_error=e
            )

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
            Records have ``bar_datetime`` set to the bar's datetime.
        """
        try:
            ticker = yf.Ticker(symbol)
            start = target_date
            end = target_date + timedelta(days=1)
            hist = ticker.history(start=start, end=end, interval=interval)

            if hist.empty:
                logger.debug(
                    f"yfinance returned no intraday data for {symbol} on {target_date}",
                    extra={
                        "symbol": symbol,
                        "date": str(target_date),
                        "interval": interval,
                    },
                )
                return []

            records = []
            for idx, row in hist.iterrows():
                bar_dt = idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else idx
                # Store the bar date (not the intraday timestamp) for RawPriceRecord
                bar_date = bar_dt.date() if hasattr(bar_dt, "date") else bar_dt

                record = RawPriceRecord(
                    symbol=symbol,
                    date=bar_date,
                    open=float(row["Open"])
                    if "Open" in row and row["Open"] is not None
                    else None,
                    high=float(row["High"])
                    if "High" in row and row["High"] is not None
                    else None,
                    low=float(row["Low"])
                    if "Low" in row and row["Low"] is not None
                    else None,
                    close=float(row["Close"]) if "Close" in row else 0.0,
                    volume=int(row["Volume"])
                    if "Volume" in row and row["Volume"] is not None
                    else None,
                    adjusted_close=None,
                    source="yfinance_intraday",
                    bar_datetime=bar_dt,
                )
                records.append(record)

            return records

        except Exception as e:
            logger.warning(
                f"Failed to fetch intraday data for {symbol} on {target_date}: {e}",
                extra={"symbol": symbol, "date": str(target_date), "error": str(e)},
            )
            return []


@dataclass
class LiveQuote:
    """Point-in-time price quote from yfinance fast_info."""

    symbol: str
    price: float
    previous_close: Optional[float] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    volume: Optional[int] = None
    captured_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    source: str = "yfinance_fast_info"


def fetch_live_quote(symbol: str) -> Optional[LiveQuote]:
    """Fetch the current live price for a symbol via yfinance.

    Uses fast_info for a lightweight single HTTP call. Returns None
    on any failure — never raises.

    Args:
        symbol: Ticker symbol (e.g., "AAPL", "TSLA").

    Returns:
        LiveQuote with current price data, or None on failure.
    """
    try:
        ticker = yf.Ticker(symbol)
        fi = ticker.fast_info
        price = fi.last_price

        if price is None or price <= 0:
            logger.warning(
                f"Invalid price from fast_info for {symbol}: {price}"
            )
            return None

        return LiveQuote(
            symbol=symbol,
            price=float(price),
            previous_close=_safe_float(fi.previous_close),
            day_high=_safe_float(fi.day_high),
            day_low=_safe_float(fi.day_low),
            volume=_safe_int(fi.last_volume),
        )
    except Exception as e:
        logger.warning(
            f"Failed to fetch live quote for {symbol}: {e}",
            extra={"symbol": symbol, "error": str(e)},
        )
        return None


def _safe_float(value) -> Optional[float]:
    """Safely convert to float, returning None on failure."""
    try:
        if value is None:
            return None
        f = float(value)
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


def _safe_int(value) -> Optional[int]:
    """Safely convert to int, returning None on failure."""
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
