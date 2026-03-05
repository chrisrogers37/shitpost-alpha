"""
Fundamentals Provider
Fetches company fundamental data from yfinance and stores it in the TickerRegistry.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Any

import yfinance as yf

from shit.market_data.models import TickerRegistry
from shit.db.sync_session import get_session
from shit.logging import get_service_logger

logger = get_service_logger("fundamentals_provider")

# Mapping from yfinance .info keys to TickerRegistry column names
_INFO_FIELD_MAP: Dict[str, str] = {
    "longName": "company_name",
    "shortName": "company_name",  # fallback if longName missing
    "sector": "sector",
    "industry": "industry",
    "marketCap": "market_cap",
    "trailingPE": "pe_ratio",
    "forwardPE": "forward_pe",
    "dividendYield": "dividend_yield",
    "beta": "beta",
    "exchange": "exchange",
    "quoteType": "asset_type",
    "longBusinessSummary": "description",
    "shortBusinessSummary": "description",  # fallback
}

# yfinance quoteType -> our asset_type mapping
_QUOTE_TYPE_MAP: Dict[str, str] = {
    "EQUITY": "stock",
    "ETF": "etf",
    "MUTUALFUND": "etf",
    "CRYPTOCURRENCY": "crypto",
    "CURRENCY": "crypto",
    "FUTURE": "commodity",
    "INDEX": "index",
}

# Maximum description length to store (avoid bloating the DB)
_MAX_DESCRIPTION_LENGTH = 500

# Default staleness threshold: re-fetch if older than this
DEFAULT_STALENESS_HOURS = 24


class FundamentalsProvider:
    """Fetches and stores company fundamental data from yfinance.

    Usage:
        provider = FundamentalsProvider()
        provider.update_fundamentals("AAPL")  # Single ticker
        provider.update_all_fundamentals()      # All active tickers
    """

    def __init__(self, staleness_hours: int = DEFAULT_STALENESS_HOURS):
        """Initialize the provider.

        Args:
            staleness_hours: Hours after which fundamentals are considered stale
                and should be re-fetched. Default 24 hours.
        """
        self.staleness_hours = staleness_hours

    def fetch_info(self, symbol: str) -> Dict[str, Any]:
        """Fetch raw .info dict from yfinance for a single symbol.

        Args:
            symbol: Ticker symbol (e.g. "AAPL", "BTC-USD").

        Returns:
            Dict of yfinance info fields. Empty dict on failure.
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            if not info or info.get("regularMarketPrice") is None:
                # yfinance returns a dict with trailingPegRatio=None for invalid tickers
                # Check for a reliable sentinel field
                if not info.get("shortName") and not info.get("longName"):
                    logger.warning(
                        f"yfinance returned no usable info for {symbol}",
                        extra={"symbol": symbol},
                    )
                    return {}
            return info or {}
        except Exception as e:
            logger.error(
                f"Failed to fetch info for {symbol}: {e}",
                extra={"symbol": symbol, "error": str(e)},
            )
            return {}

    def _extract_fundamentals(self, info: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and normalize fundamental fields from yfinance info dict.

        Args:
            info: Raw yfinance .info dict.

        Returns:
            Dict with TickerRegistry column names as keys.
        """
        result: Dict[str, Any] = {}

        # Company name: prefer longName, fall back to shortName
        result["company_name"] = info.get("longName") or info.get("shortName")

        # Sector & Industry (only for equities; ETFs/crypto won't have these)
        result["sector"] = info.get("sector")
        result["industry"] = info.get("industry")

        # Market cap
        market_cap = info.get("marketCap")
        if market_cap is not None:
            try:
                result["market_cap"] = int(market_cap)
            except (ValueError, TypeError):
                result["market_cap"] = None
        else:
            result["market_cap"] = None

        # P/E ratios
        pe = info.get("trailingPE")
        result["pe_ratio"] = float(pe) if pe is not None else None

        fpe = info.get("forwardPE")
        result["forward_pe"] = float(fpe) if fpe is not None else None

        # Dividend yield
        div_yield = info.get("dividendYield")
        result["dividend_yield"] = float(div_yield) if div_yield is not None else None

        # Beta
        beta = info.get("beta")
        result["beta"] = float(beta) if beta is not None else None

        # Exchange
        result["exchange"] = info.get("exchange")

        # Asset type from quoteType
        quote_type = info.get("quoteType", "")
        result["asset_type"] = _QUOTE_TYPE_MAP.get(quote_type, "stock")

        # Description: truncate to avoid DB bloat
        desc = info.get("longBusinessSummary") or info.get("shortBusinessSummary")
        if desc and len(desc) > _MAX_DESCRIPTION_LENGTH:
            desc = desc[: _MAX_DESCRIPTION_LENGTH - 3] + "..."
        result["description"] = desc

        return result

    def _is_stale(self, entry: TickerRegistry) -> bool:
        """Check whether a ticker's fundamentals need refreshing.

        Args:
            entry: TickerRegistry row.

        Returns:
            True if fundamentals_updated_at is None or older than staleness_hours.
        """
        if entry.fundamentals_updated_at is None:
            return True
        age = datetime.now(tz=timezone.utc) - entry.fundamentals_updated_at.replace(
            tzinfo=timezone.utc
        )
        return age > timedelta(hours=self.staleness_hours)

    def update_fundamentals(self, symbol: str, force: bool = False) -> bool:
        """Fetch and store fundamentals for a single ticker.

        Skips the fetch if data is fresh (< staleness_hours old) unless force=True.

        Args:
            symbol: Ticker symbol.
            force: If True, fetch even if data is fresh.

        Returns:
            True if fundamentals were updated, False if skipped or failed.
        """
        symbol = symbol.strip().upper()

        with get_session() as session:
            entry = (
                session.query(TickerRegistry)
                .filter(TickerRegistry.symbol == symbol)
                .first()
            )

            if not entry:
                logger.warning(
                    f"Ticker {symbol} not in registry, cannot update fundamentals",
                    extra={"symbol": symbol},
                )
                return False

            # Skip if fresh
            if not force and not self._is_stale(entry):
                logger.debug(
                    f"Fundamentals for {symbol} are fresh, skipping",
                    extra={"symbol": symbol},
                )
                return False

            # Fetch from yfinance
            info = self.fetch_info(symbol)
            if not info:
                logger.warning(
                    f"No info returned for {symbol}, skipping update",
                    extra={"symbol": symbol},
                )
                return False

            # Extract and apply
            fundamentals = self._extract_fundamentals(info)
            for column, value in fundamentals.items():
                if value is not None:
                    setattr(entry, column, value)

            entry.fundamentals_updated_at = datetime.now(tz=timezone.utc)
            session.commit()

            logger.info(
                f"Updated fundamentals for {symbol}",
                extra={
                    "symbol": symbol,
                    "company_name": fundamentals.get("company_name"),
                    "sector": fundamentals.get("sector"),
                },
            )
            return True

    def update_all_fundamentals(
        self, force: bool = False, status: str = "active"
    ) -> Dict[str, Any]:
        """Batch-update fundamentals for all registered tickers.

        Args:
            force: If True, re-fetch even fresh data.
            status: Only update tickers with this status. Default "active".

        Returns:
            Stats dict with keys: total, updated, skipped, failed.
        """
        with get_session() as session:
            query = session.query(TickerRegistry)
            if status:
                query = query.filter(TickerRegistry.status == status)
            tickers = query.all()
            symbols = [t.symbol for t in tickers]

        stats = {"total": len(symbols), "updated": 0, "skipped": 0, "failed": 0}

        for symbol in symbols:
            try:
                updated = self.update_fundamentals(symbol, force=force)
                if updated:
                    stats["updated"] += 1
                else:
                    stats["skipped"] += 1
            except Exception as e:
                logger.error(
                    f"Failed to update fundamentals for {symbol}: {e}",
                    extra={"symbol": symbol, "error": str(e)},
                )
                stats["failed"] += 1

        logger.info("Batch fundamentals update complete", extra=stats)
        return stats
