"""
Ticker Validation Service

Validates and normalizes ticker symbols extracted by LLMs before they
reach prediction storage. Three layers of defense:

1. Static blocklist — known non-ticker strings (DEFENSE, CRYPTO, etc.)
2. Alias remapping — delisted/renamed symbols (RTN→RTX, FB→META, etc.)
3. yfinance spot-check — catches novel bad tickers (~300ms per symbol)

Registry-first optimization: symbols already active in ticker_registry
skip the yfinance check entirely (0ms cached lookup).
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class TickerValidator:
    """Validates ticker symbols against blocklist, aliases, and yfinance."""

    # Known non-ticker strings the LLM commonly extracts
    BLOCKLIST: frozenset[str] = frozenset({
        "DEFENSE", "CRYPTO", "ECONOMY", "NEWSMAX", "TARIFF",
        "GDP", "CPI", "FED", "NATO", "CEO", "IPO", "ESG",
    })

    # Known delisted → current mappings (None = no replacement, filter out)
    ALIASES: dict[str, Optional[str]] = {
        "RTN": "RTX",
        "FB": "META",
        "TWTR": None,       # Twitter taken private (Oct 2022)
        "RDS.A": "SHEL",
        "RDS.B": "SHEL",
        "CBS": "PARA",
        "PTR": None,         # PetroChina delisted from NYSE (Sep 2022)
        "SNP": None,         # China Petroleum delisted from NYSE (Sep 2022)
        "AKS": "CLF",
        "KOL": None,         # VanEck Coal ETF closed (Dec 2020)
        "OIL": None,         # iPath Oil ETN delisted (Apr 2021)
    }

    def __init__(self):
        """Initialize validator. Registry and yfinance caches are lazy-loaded."""
        self._known_active: Optional[set[str]] = None
        self._tradeable_cache: dict[str, bool] = {}

    def validate_symbols(self, symbols: list[str]) -> list[str]:
        """Validate and normalize a list of ticker symbols.

        Returns only valid, tradeable symbols. Applies blocklist filtering,
        alias remapping, and yfinance spot-check (skipped for known-active).

        Args:
            symbols: Raw ticker symbols from LLM extraction.

        Returns:
            List of validated, normalized symbols (deduped, order preserved).
        """
        validated = []
        seen: set[str] = set()

        for raw in symbols:
            symbol = raw.strip().upper()
            if not symbol:
                continue

            # Blocklist check
            if symbol in self.BLOCKLIST:
                logger.info(f"Blocked non-ticker symbol: {symbol}")
                continue

            # Alias remapping
            if symbol in self.ALIASES:
                replacement = self.ALIASES[symbol]
                if replacement is None:
                    logger.info(
                        f"Filtered delisted ticker with no replacement: {symbol}"
                    )
                    continue
                logger.info(f"Remapped {symbol} → {replacement}")
                symbol = replacement

            # Dedup (e.g., RDS.A and RDS.B both map to SHEL)
            if symbol in seen:
                continue
            seen.add(symbol)

            # Registry-first optimization: skip yfinance for known-active symbols
            if self._is_known_active(symbol):
                validated.append(symbol)
                continue

            # yfinance spot-check for unknown symbols
            if not self._is_tradeable(symbol):
                logger.info(f"yfinance validation failed for {symbol}")
                continue

            validated.append(symbol)

        return validated

    def _is_known_active(self, symbol: str) -> bool:
        """Check if symbol is already active in ticker_registry.

        Opens its own sync session on first call, caches the full active set.
        """
        if self._known_active is None:
            try:
                from shit.db.sync_session import get_session
                from shit.market_data.models import TickerRegistry
                with get_session() as session:
                    rows = session.query(TickerRegistry.symbol).filter(
                        TickerRegistry.status == "active"
                    ).all()
                    self._known_active = {r.symbol for r in rows}
            except Exception:
                # DB unavailable — skip optimization, fall through to yfinance
                self._known_active = set()
        return symbol in self._known_active

    def _is_tradeable(self, symbol: str) -> bool:
        """Quick yfinance check if this is a tradeable symbol.

        Caches results to avoid repeated calls for the same symbol.
        Fails open on network errors — the backfill service will catch it later.
        """
        if symbol in self._tradeable_cache:
            return self._tradeable_cache[symbol]

        result = self._check_yfinance(symbol)
        self._tradeable_cache[symbol] = result
        return result

    @staticmethod
    def _check_yfinance(symbol: str) -> bool:
        """Raw yfinance lookup. Separated for testability."""
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            info = ticker.info or {}
            quote_type = info.get("quoteType", "")
            if quote_type in (
                "EQUITY", "ETF", "MUTUALFUND", "CRYPTOCURRENCY",
                "FUTURE", "INDEX",
            ):
                return True
            fast = ticker.fast_info
            if hasattr(fast, "last_price") and fast.last_price is not None:
                return True
            return False
        except Exception:
            # Network errors shouldn't block registration — fail open
            return True
