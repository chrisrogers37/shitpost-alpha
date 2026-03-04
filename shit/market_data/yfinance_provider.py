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
