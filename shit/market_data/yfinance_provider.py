"""
yfinance Price Provider
Wraps the yfinance library behind the PriceProvider interface.
"""

from datetime import date, timedelta
from typing import List

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
                    extra={"symbol": symbol}
                )
                return []

            records = []
            for idx, row in hist.iterrows():
                price_date = idx.date() if hasattr(idx, 'date') else idx

                record = RawPriceRecord(
                    symbol=symbol,
                    date=price_date,
                    open=float(row['Open']) if 'Open' in row and row['Open'] is not None else None,
                    high=float(row['High']) if 'High' in row and row['High'] is not None else None,
                    low=float(row['Low']) if 'Low' in row and row['Low'] is not None else None,
                    close=float(row['Close']) if 'Close' in row else 0.0,
                    volume=int(row['Volume']) if 'Volume' in row and row['Volume'] is not None else None,
                    adjusted_close=float(row['Close']) if 'Close' in row else None,
                    source="yfinance",
                )
                records.append(record)

            return records

        except Exception as e:
            raise ProviderError("yfinance", f"Failed to fetch {symbol}: {e}", original_error=e)
