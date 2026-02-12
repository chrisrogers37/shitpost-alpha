"""
Alpha Vantage Price Provider
Fallback price source using the Alpha Vantage free API.
"""

from datetime import date, datetime
from typing import List, Optional

import requests

from shit.market_data.price_provider import PriceProvider, RawPriceRecord, ProviderError
from shit.config.shitpost_settings import settings
from shit.logging import get_service_logger

logger = get_service_logger("alphavantage_provider")

ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"


class AlphaVantageProvider(PriceProvider):
    """Price provider backed by the Alpha Vantage REST API."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Alpha Vantage provider.

        Args:
            api_key: Alpha Vantage API key. Falls back to settings if not provided.
        """
        self._api_key = api_key or settings.ALPHA_VANTAGE_API_KEY

    @property
    def name(self) -> str:
        return "alphavantage"

    def is_available(self) -> bool:
        """Available only if an API key is configured."""
        return self._api_key is not None and len(self._api_key) > 0

    def fetch_prices(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> List[RawPriceRecord]:
        """Fetch daily prices from Alpha Vantage TIME_SERIES_DAILY endpoint.

        Note: Alpha Vantage returns up to 100 days of data by default
        (full output with outputsize=full returns 20+ years but counts as 1 call).
        """
        if not self.is_available():
            raise ProviderError("alphavantage", "API key not configured")

        # Determine output size: compact (last 100 days) vs full (20 years)
        days_requested = (end_date - start_date).days
        output_size = "full" if days_requested > 100 else "compact"

        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "outputsize": output_size,
            "apikey": self._api_key,
        }

        try:
            response = requests.get(
                ALPHA_VANTAGE_BASE_URL,
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

        except requests.exceptions.Timeout:
            raise ProviderError("alphavantage", f"Request timed out for {symbol}")
        except requests.exceptions.RequestException as e:
            raise ProviderError("alphavantage", f"HTTP error for {symbol}: {e}", original_error=e)

        # Check for API error responses
        if "Error Message" in data:
            raise ProviderError("alphavantage", f"API error for {symbol}: {data['Error Message']}")

        if "Note" in data:
            # Rate limit message
            raise ProviderError("alphavantage", f"Rate limited: {data['Note']}")

        if "Information" in data:
            raise ProviderError("alphavantage", f"API info: {data['Information']}")

        time_series = data.get("Time Series (Daily)", {})

        if not time_series:
            logger.warning(
                f"Alpha Vantage returned no time series data for {symbol}",
                extra={"symbol": symbol}
            )
            return []

        records = []
        for date_str, daily_data in time_series.items():
            try:
                price_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                continue

            # Filter to requested date range
            if price_date < start_date or price_date > end_date:
                continue

            try:
                record = RawPriceRecord(
                    symbol=symbol,
                    date=price_date,
                    open=float(daily_data.get("1. open", 0)),
                    high=float(daily_data.get("2. high", 0)),
                    low=float(daily_data.get("3. low", 0)),
                    close=float(daily_data.get("4. close", 0)),
                    volume=int(daily_data.get("5. volume", 0)),
                    adjusted_close=float(daily_data.get("4. close", 0)),
                    source="alphavantage",
                )
                records.append(record)
            except (ValueError, TypeError) as e:
                logger.warning(
                    f"Skipping malformed price record for {symbol} on {date_str}: {e}",
                    extra={"symbol": symbol, "date": date_str}
                )

        # Sort by date ascending (Alpha Vantage returns newest first)
        records.sort(key=lambda r: r.date)

        logger.info(
            f"Alpha Vantage returned {len(records)} records for {symbol}",
            extra={"symbol": symbol, "count": len(records)}
        )

        return records
