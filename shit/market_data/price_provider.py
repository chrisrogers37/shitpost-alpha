"""
Price Provider Abstraction
Defines the interface for market data sources (yfinance, Alpha Vantage, etc.).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from shit.logging import get_service_logger

logger = get_service_logger("price_provider")


@dataclass
class RawPriceRecord:
    """Raw price data from a provider, not yet stored in the database.

    This is a plain data transfer object -- no SQLAlchemy dependency.
    """
    symbol: str
    date: date
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: float
    volume: Optional[int]
    adjusted_close: Optional[float]
    source: str  # e.g. "yfinance", "alphavantage"


class PriceProvider(ABC):
    """Abstract base class for price data providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the provider (e.g. 'yfinance', 'alphavantage')."""
        ...

    @abstractmethod
    def fetch_prices(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> List[RawPriceRecord]:
        """Fetch historical price data from this provider.

        Args:
            symbol: Ticker symbol (e.g., 'AAPL', 'BTC-USD')
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)

        Returns:
            List of RawPriceRecord objects. Empty list if no data found.

        Raises:
            ProviderError: If the provider is unavailable or returns an error.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Quick check: is this provider configured and likely to work?

        Returns:
            True if the provider has credentials/configuration and is ready.
        """
        ...


class ProviderError(Exception):
    """Raised when a price provider fails to fetch data."""

    def __init__(self, provider_name: str, message: str, original_error: Optional[Exception] = None):
        self.provider_name = provider_name
        self.original_error = original_error
        super().__init__(f"[{provider_name}] {message}")


class ProviderChain:
    """Tries multiple providers in order until one succeeds.

    Usage:
        chain = ProviderChain([yfinance_provider, alphavantage_provider])
        prices = chain.fetch_with_fallback("AAPL", start, end)
    """

    def __init__(self, providers: List[PriceProvider]):
        self.providers = [p for p in providers if p.is_available()]
        if not self.providers:
            logger.warning("No price providers are available/configured")

    def fetch_with_fallback(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> List[RawPriceRecord]:
        """Try each provider in order. Return results from the first that succeeds.

        Args:
            symbol: Ticker symbol
            start_date: Start of date range
            end_date: End of date range

        Returns:
            List of RawPriceRecord from the first successful provider.

        Raises:
            ProviderError: If ALL providers fail.
        """
        errors = []

        for provider in self.providers:
            try:
                logger.info(
                    f"Attempting {provider.name} for {symbol}",
                    extra={"provider": provider.name, "symbol": symbol}
                )
                records = provider.fetch_prices(symbol, start_date, end_date)
                if records:
                    logger.info(
                        f"{provider.name} returned {len(records)} records for {symbol}",
                        extra={"provider": provider.name, "symbol": symbol, "count": len(records)}
                    )
                    return records
                else:
                    logger.warning(
                        f"{provider.name} returned empty results for {symbol}",
                        extra={"provider": provider.name, "symbol": symbol}
                    )
            except Exception as e:
                logger.warning(
                    f"{provider.name} failed for {symbol}: {e}",
                    extra={"provider": provider.name, "symbol": symbol, "error": str(e)}
                )
                errors.append(ProviderError(provider.name, str(e), original_error=e))

        # All providers failed
        error_summary = "; ".join(str(e) for e in errors)
        raise ProviderError(
            "all_providers",
            f"All providers failed for {symbol}: {error_summary}"
        )
