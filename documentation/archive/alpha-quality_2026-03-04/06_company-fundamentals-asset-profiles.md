# Phase 06: Company Fundamentals & Asset Profiles

## Header

| Field | Value |
|---|---|
| **PR Title** | feat: add company fundamentals fetching, storage, and display |
| **Risk Level** | Medium |
| **Estimated Effort** | High (3-4 days) |
| **Files Created** | 3 |
| **Files Modified** | 9 |
| **Files Deleted** | 0 |

---

## Context

The system tracks 50+ ticker symbols across stocks, ETFs, crypto, and commodities. Every ticker goes through a `TickerRegistry` that records its symbol, status, and price metadata -- but nothing about the *company* behind the ticker. The `asset_type` and `exchange` columns on `TickerRegistry` (lines 180-181 of `shit/market_data/models.py`) are always NULL. The `sector` column on `PredictionOutcome` (line 97) is always NULL.

The yfinance library already installed in `requirements.txt` exposes a rich `.info` endpoint with company name, sector, industry, market cap, P/E ratios, business summary, and more. This data is never fetched. The asset detail page (`shitty_ui/pages/assets.py`) shows only the ticker symbol and price -- no company context. The screener table (`shitty_ui/components/screener.py`) has no sector column, making it impossible to analyze performance by sector.

This phase closes that gap by:
1. Extending the `TickerRegistry` model with fundamental data columns
2. Creating a `FundamentalsProvider` that calls yfinance `.info`
3. Auto-populating fundamentals when tickers are registered
4. Displaying company profiles on the asset detail page
5. Adding sector badges and filtering to the screener
6. ~~Providing a CLI command for batch population~~ **TRIMMED (challenge round):** Auto-populate hook handles new tickers. For existing tickers, use a one-time script in PR description.

---

## Dependencies

- **No phase dependencies.** This phase touches files that are not modified by other phases in this session.
- **Database migration required.** New columns added to `ticker_registry` table via `ALTER TABLE` (no Alembic in this project -- schema changes are applied via direct SQL or `create_tables()`).

## Unlocks

- Future sector-level analytics dashboards
- Sector rotation detection in LLM analysis
- Enriched alert messages with company context

---

## Detailed Implementation Plan

### Step 1: Extend TickerRegistry Model

**File:** `/Users/chris/Projects/shitpost-alpha/shit/market_data/models.py`

Add new columns to the `TickerRegistry` class after line 181 (after the existing `exchange` column).

**Current code (lines 149-184):**
```python
class TickerRegistry(Base, IDMixin, TimestampMixin):
    """Registry of all ticker symbols the system tracks."""

    __tablename__ = "ticker_registry"

    # Ticker identification
    symbol = Column(String(20), unique=True, nullable=False, index=True)

    # Lifecycle tracking
    first_seen_date = Column(Date, nullable=False, index=True)
    source_prediction_id = Column(Integer, ForeignKey("predictions.id"), nullable=True)

    # Status
    status = Column(String(20), nullable=False, default="active", index=True)
    status_reason = Column(String(255), nullable=True)

    # Price data tracking
    last_price_update = Column(DateTime, nullable=True)
    price_data_start = Column(Date, nullable=True)
    price_data_end = Column(Date, nullable=True)
    total_price_records = Column(Integer, default=0)

    # Metadata
    asset_type = Column(String(20), nullable=True)  # stock, crypto, etf, commodity, index
    exchange = Column(String(20), nullable=True)  # NYSE, NASDAQ, etc.

    def __repr__(self):
        return f"<TickerRegistry(symbol='{self.symbol}', status='{self.status}', first_seen={self.first_seen_date})>"
```

**New code (replace lines 149-184):**
```python
class TickerRegistry(Base, IDMixin, TimestampMixin):
    """Registry of all ticker symbols the system tracks.

    Once a ticker appears in an LLM prediction, it is registered here
    and tracked for ongoing price updates. This provides:
    - Instant lookup of whether a ticker is already known
    - Status tracking (active, inactive, invalid)
    - Audit trail of when each ticker was first seen
    - Source prediction linkage for debugging
    - Company fundamental data from yfinance
    """

    __tablename__ = "ticker_registry"

    # Ticker identification
    symbol = Column(String(20), unique=True, nullable=False, index=True)

    # Lifecycle tracking
    first_seen_date = Column(Date, nullable=False, index=True)
    source_prediction_id = Column(Integer, ForeignKey("predictions.id"), nullable=True)

    # Status: active (tracked), inactive (manually disabled), invalid (yfinance can't find it)
    status = Column(String(20), nullable=False, default="active", index=True)
    status_reason = Column(String(255), nullable=True)

    # Price data tracking
    last_price_update = Column(DateTime, nullable=True)
    price_data_start = Column(Date, nullable=True)
    price_data_end = Column(Date, nullable=True)
    total_price_records = Column(Integer, default=0)

    # Metadata (existing)
    asset_type = Column(String(20), nullable=True)  # stock, crypto, etf, commodity, index
    exchange = Column(String(20), nullable=True)  # NYSE, NASDAQ, etc.

    # Company fundamentals (populated by FundamentalsProvider)
    company_name = Column(String(255), nullable=True)  # e.g. "Apple Inc."
    sector = Column(String(100), nullable=True)  # e.g. "Technology"
    industry = Column(String(100), nullable=True)  # e.g. "Consumer Electronics"
    market_cap = Column(BigInteger, nullable=True)  # Market capitalization in USD
    pe_ratio = Column(Float, nullable=True)  # Trailing P/E ratio
    forward_pe = Column(Float, nullable=True)  # Forward P/E ratio
    dividend_yield = Column(Float, nullable=True)  # Dividend yield (0.0-1.0)
    beta = Column(Float, nullable=True)  # Beta coefficient
    description = Column(Text, nullable=True)  # Short business summary
    fundamentals_updated_at = Column(DateTime, nullable=True)  # Last fundamentals refresh

    def __repr__(self):
        name_part = f" ({self.company_name})" if self.company_name else ""
        return f"<TickerRegistry(symbol='{self.symbol}'{name_part}, status='{self.status}')>"
```

**Additional import needed on line 8:** `Text` is already imported on that line. Verify that `BigInteger` is also imported. Current line 8:
```python
from sqlalchemy import Column, String, Date, DateTime, Float, BigInteger, ForeignKey, Integer, Boolean, Text
```
`BigInteger` and `Text` are already imported. No import changes needed.

**Add a new index** after line 195 (the existing indexes section):
```python
Index('idx_ticker_registry_sector', TickerRegistry.sector)
```

This enables efficient sector-based grouping queries.

---

### Step 2: Create FundamentalsProvider

**New file:** `/Users/chris/Projects/shitpost-alpha/shit/market_data/fundamentals_provider.py`

```python
"""
Fundamentals Provider
Fetches company fundamental data from yfinance and stores it in the TickerRegistry.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

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
            desc = desc[:_MAX_DESCRIPTION_LENGTH - 3] + "..."
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
```

---

### Step 3: Update TickerRegistryService to Trigger Fundamentals on Registration

**File:** `/Users/chris/Projects/shitpost-alpha/shit/market_data/ticker_registry.py`

After a new ticker is registered in `register_tickers()`, trigger a background fundamentals fetch. This should be non-blocking and wrapped in try/except so it never breaks the registration flow.

**Current code (lines 68-89):**
```python
                # Register new ticker
                registry_entry = TickerRegistry(
                    symbol=symbol,
                    first_seen_date=date.today(),
                    source_prediction_id=source_prediction_id,
                    status="active",
                    last_price_update=None,
                    total_price_records=0,
                )
                session.add(registry_entry)
                newly_registered.append(symbol)
                logger.info(
                    f"Registered new ticker: {symbol}",
                    extra={"symbol": symbol, "source_prediction_id": source_prediction_id},
                )

            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                logger.info("IntegrityError during ticker registration, handling concurrent insert")

        return (newly_registered, already_known)
```

**New code (replace lines 68-91):**
```python
                # Register new ticker
                registry_entry = TickerRegistry(
                    symbol=symbol,
                    first_seen_date=date.today(),
                    source_prediction_id=source_prediction_id,
                    status="active",
                    last_price_update=None,
                    total_price_records=0,
                )
                session.add(registry_entry)
                newly_registered.append(symbol)
                logger.info(
                    f"Registered new ticker: {symbol}",
                    extra={"symbol": symbol, "source_prediction_id": source_prediction_id},
                )

            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                logger.info("IntegrityError during ticker registration, handling concurrent insert")

        # Populate fundamentals for newly registered tickers (best-effort, non-blocking)
        if newly_registered:
            try:
                from shit.market_data.fundamentals_provider import FundamentalsProvider

                provider = FundamentalsProvider()
                for symbol in newly_registered:
                    try:
                        provider.update_fundamentals(symbol, force=True)
                    except Exception as e:
                        logger.warning(
                            f"Failed to fetch fundamentals for new ticker {symbol}: {e}",
                            extra={"symbol": symbol},
                        )
            except Exception as e:
                logger.warning(f"Failed to initialize FundamentalsProvider: {e}")

        return (newly_registered, already_known)
```

**Why this approach:** The fundamentals fetch is synchronous and happens inline after registration. This is acceptable because:
- `register_tickers()` is only called during the market data backfill pipeline (not on hot paths)
- yfinance `.info` calls take ~0.5-1s per ticker
- New tickers arrive at most a few per day
- The try/except ensures registration never fails due to fundamentals issues

---

### Step 4: Register FundamentalsProvider in Module Exports

**File:** `/Users/chris/Projects/shitpost-alpha/shit/market_data/__init__.py`

**Current code (lines 1-28):**
```python
"""
Market Data Module
Fetches stock prices and calculates prediction outcomes.
"""

from shit.market_data.models import MarketPrice, PredictionOutcome, TickerRegistry
from shit.market_data.client import MarketDataClient
from shit.market_data.outcome_calculator import OutcomeCalculator
from shit.market_data.price_provider import PriceProvider, ProviderChain, RawPriceRecord, ProviderError
from shit.market_data.yfinance_provider import YFinanceProvider
from shit.market_data.alphavantage_provider import AlphaVantageProvider
from shit.market_data.health import run_health_check, HealthReport

__all__ = [
    "MarketPrice",
    "PredictionOutcome",
    "TickerRegistry",
    "MarketDataClient",
    "OutcomeCalculator",
    "PriceProvider",
    "ProviderChain",
    "RawPriceRecord",
    "ProviderError",
    "YFinanceProvider",
    "AlphaVantageProvider",
    "run_health_check",
    "HealthReport",
]
```

**New code:**
```python
"""
Market Data Module
Fetches stock prices, company fundamentals, and calculates prediction outcomes.
"""

from shit.market_data.models import MarketPrice, PredictionOutcome, TickerRegistry
from shit.market_data.client import MarketDataClient
from shit.market_data.outcome_calculator import OutcomeCalculator
from shit.market_data.price_provider import PriceProvider, ProviderChain, RawPriceRecord, ProviderError
from shit.market_data.yfinance_provider import YFinanceProvider
from shit.market_data.alphavantage_provider import AlphaVantageProvider
from shit.market_data.fundamentals_provider import FundamentalsProvider
from shit.market_data.health import run_health_check, HealthReport

__all__ = [
    "MarketPrice",
    "PredictionOutcome",
    "TickerRegistry",
    "MarketDataClient",
    "OutcomeCalculator",
    "PriceProvider",
    "ProviderChain",
    "RawPriceRecord",
    "ProviderError",
    "YFinanceProvider",
    "AlphaVantageProvider",
    "FundamentalsProvider",
    "run_health_check",
    "HealthReport",
]
```

---

### ~~Step 5: Add CLI Command for Batch Population~~ — TRIMMED (challenge round)

**This step has been removed.** The auto-populate hook (Step 3) handles new tickers automatically. For existing tickers, include a one-time population script in the PR description using `FundamentalsProvider().update_all_fundamentals(force=True)` via `python -c "..."`. No formal CLI command needed.

### Original Step 5 (preserved for reference, DO NOT IMPLEMENT):

**File:** `/Users/chris/Projects/shitpost-alpha/shit/market_data/cli.py`

Add a new `populate-fundamentals` command at the end of the file, before the `if __name__ == "__main__":` block (before line 651).

**Insert after the `register_tickers_cmd` function (after line 648):**

```python
@cli.command(name="populate-fundamentals")
@click.option("--force", "-f", is_flag=True, help="Re-fetch even if data is fresh")
@click.option(
    "--status",
    "-s",
    type=click.Choice(["active", "inactive", "invalid", "all"]),
    default="active",
    help="Only update tickers with this status",
)
@click.option("--symbol", help="Update a single ticker instead of all")
def populate_fundamentals_cmd(force: bool, status: str, symbol: str):
    """Populate company fundamentals for all registered tickers.

    Fetches company name, sector, industry, market cap, P/E ratio, and more
    from yfinance for each ticker in the registry.

    Examples:
        python -m shit.market_data populate-fundamentals
        python -m shit.market_data populate-fundamentals --force
        python -m shit.market_data populate-fundamentals --symbol AAPL
    """
    from shit.market_data.fundamentals_provider import FundamentalsProvider

    try:
        provider = FundamentalsProvider()

        if symbol:
            print_info(f"Fetching fundamentals for {symbol}...")
            updated = provider.update_fundamentals(symbol.strip().upper(), force=force)
            if updated:
                # Show what was fetched
                from shit.market_data.models import TickerRegistry as TR

                with get_session() as session:
                    entry = (
                        session.query(TR)
                        .filter(TR.symbol == symbol.strip().upper())
                        .first()
                    )
                    if entry:
                        rprint(f"\n[bold]{entry.symbol} - {entry.company_name or 'N/A'}[/bold]")
                        rprint(f"  Sector: {entry.sector or 'N/A'}")
                        rprint(f"  Industry: {entry.industry or 'N/A'}")
                        rprint(f"  Market Cap: ${entry.market_cap:,.0f}" if entry.market_cap else "  Market Cap: N/A")
                        rprint(f"  P/E Ratio: {entry.pe_ratio:.2f}" if entry.pe_ratio else "  P/E Ratio: N/A")
                        rprint(f"  Forward P/E: {entry.forward_pe:.2f}" if entry.forward_pe else "  Forward P/E: N/A")
                        rprint(f"  Beta: {entry.beta:.2f}" if entry.beta else "  Beta: N/A")
                        rprint(f"  Exchange: {entry.exchange or 'N/A'}")
                        rprint(f"  Type: {entry.asset_type or 'N/A'}")
                        print_success(f"Updated fundamentals for {symbol}")
            else:
                print_info(f"Fundamentals for {symbol} are already fresh (use --force to override)")
        else:
            filter_status = None if status == "all" else status
            print_info(f"Populating fundamentals for {status} tickers...")

            stats = provider.update_all_fundamentals(
                force=force, status=filter_status
            )

            table = Table(title="Fundamentals Population Results")
            table.add_column("Metric", style="cyan")
            table.add_column("Count", style="green", justify="right")

            table.add_row("Total tickers", str(stats["total"]))
            table.add_row("Updated", str(stats["updated"]))
            table.add_row("Skipped (fresh)", str(stats["skipped"]))
            table.add_row("Failed", str(stats["failed"]))

            console.print(table)

            if stats["updated"] > 0:
                print_success(f"Updated fundamentals for {stats['updated']} tickers")
            elif stats["skipped"] == stats["total"]:
                print_info("All fundamentals are already fresh (use --force to override)")

    except Exception as e:
        print_error(f"Error populating fundamentals: {e}")
        raise click.Abort()
```

---

### Step 6: Add Fundamentals Query Function for the Dashboard

**File:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/data/asset_queries.py`

Add a new query function at the end of the file (after line 667).

```python
@ttl_cache(ttl_seconds=600)  # Cache for 10 minutes (fundamentals change slowly)
def get_ticker_fundamentals(symbol: str) -> Dict[str, Any]:
    """Get company fundamental data from the ticker registry.

    Args:
        symbol: Ticker symbol (e.g., 'AAPL').

    Returns:
        Dictionary with keys: company_name, sector, industry, market_cap,
        pe_ratio, forward_pe, dividend_yield, beta, exchange, asset_type,
        description, fundamentals_updated_at.
        Returns dict with all None values if ticker not found.
    """
    query = text("""
        SELECT
            company_name,
            sector,
            industry,
            market_cap,
            pe_ratio,
            forward_pe,
            dividend_yield,
            beta,
            exchange,
            asset_type,
            description,
            fundamentals_updated_at
        FROM ticker_registry
        WHERE symbol = :symbol
    """)

    empty = {
        "company_name": None,
        "sector": None,
        "industry": None,
        "market_cap": None,
        "pe_ratio": None,
        "forward_pe": None,
        "dividend_yield": None,
        "beta": None,
        "exchange": None,
        "asset_type": None,
        "description": None,
        "fundamentals_updated_at": None,
    }

    try:
        rows, columns = _base.execute_query(query, {"symbol": symbol.upper()})
        if rows and rows[0]:
            row = rows[0]
            return {col: row[i] for i, col in enumerate(columns)}
    except Exception as e:
        logger.error(f"Error loading fundamentals for {symbol}: {e}")

    return empty


@ttl_cache(ttl_seconds=300)
def get_screener_sectors() -> Dict[str, str]:
    """Get sector mapping for all active tickers.

    Returns:
        Dict mapping symbol -> sector (e.g., {"AAPL": "Technology", "XOM": "Energy"}).
        Tickers without sector data are excluded.
    """
    query = text("""
        SELECT symbol, sector
        FROM ticker_registry
        WHERE status = 'active'
            AND sector IS NOT NULL
    """)

    try:
        rows, columns = _base.execute_query(query)
        return {row[0]: row[1] for row in rows} if rows else {}
    except Exception as e:
        logger.error(f"Error loading screener sectors: {e}")
        return {}
```

---

### Step 7: Export New Query Functions

**File:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/data/__init__.py`

Add the new functions to the asset queries import block (after line 76, after `get_related_assets`):

```python
# In the "Asset queries" import section (around line 67-77):
from data.asset_queries import (  # noqa: F401
    get_asset_screener_data,
    get_screener_sparkline_prices,
    get_similar_predictions,
    get_predictions_with_outcomes,
    get_asset_price_history,
    get_sparkline_prices,
    get_asset_predictions,
    get_asset_stats,
    get_related_assets,
    get_ticker_fundamentals,      # NEW
    get_screener_sectors,          # NEW
)
```

Add to `clear_all_caches()` (after line 110, after `get_sparkline_prices.clear_cache()`):

```python
    get_ticker_fundamentals.clear_cache()  # type: ignore
    get_screener_sectors.clear_cache()  # type: ignore
```

Add to `__all__` list (after `"get_related_assets"` around line 169):

```python
    "get_ticker_fundamentals",
    "get_screener_sectors",
```

---

### Step 8: Add Company Profile UI to Asset Detail Page

**File:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/assets.py`

#### 8a. Update imports (line 19-25)

**Current:**
```python
from data import (
    get_asset_price_history,
    get_asset_predictions,
    get_asset_stats,
    get_price_with_signals,
    get_related_assets,
)
```

**New:**
```python
from data import (
    get_asset_price_history,
    get_asset_predictions,
    get_asset_stats,
    get_price_with_signals,
    get_related_assets,
    get_ticker_fundamentals,
)
```

#### 8b. Update `create_asset_header` to include company name placeholder (lines 210-284)

Replace the function with a version that includes a company name subtitle populated by callback:

**New `create_asset_header` (replace lines 210-284):**
```python
def create_asset_header(symbol: str) -> html.Div:
    """
    Create the header bar for an asset page.
    Includes back navigation, symbol name, company name, and a placeholder for
    current price (populated by callback).

    Args:
        symbol: Ticker symbol

    Returns:
        html.Div header component
    """
    return html.Div(
        [
            # Navigation row
            html.Div(
                [
                    dcc.Link(
                        [html.I(className="fas fa-arrow-left me-2"), "Screener"],
                        href="/",
                        style={
                            "color": COLORS["accent"],
                            "textDecoration": "none",
                            "fontSize": "0.85rem",
                        },
                    ),
                ],
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "marginBottom": "10px",
                },
            ),
            # Symbol + Company Name + Price
            html.Div(
                [
                    html.Div(
                        [
                            html.H1(
                                symbol,
                                style={
                                    "fontSize": "2rem",
                                    "fontWeight": "bold",
                                    "margin": 0,
                                    "color": COLORS["text"],
                                },
                            ),
                            html.Span(
                                id="asset-current-price",
                                style={
                                    "fontSize": "1.5rem",
                                    "color": COLORS["accent"],
                                    "marginLeft": "15px",
                                },
                            ),
                        ],
                        style={"display": "flex", "alignItems": "baseline"},
                    ),
                    # Company name + sector badge (populated by callback)
                    html.Div(
                        id="asset-company-subtitle",
                        style={
                            "display": "flex",
                            "alignItems": "center",
                            "gap": "8px",
                            "marginTop": "2px",
                        },
                    ),
                    html.P(
                        COPY["asset_page_subtitle"].format(symbol=symbol),
                        style={
                            "color": COLORS["text_muted"],
                            "margin": 0,
                            "fontSize": "0.9rem",
                            "marginTop": "4px",
                        },
                    ),
                ]
            ),
        ],
        style={
            "padding": "20px",
            "borderBottom": f"1px solid {COLORS['border']}",
            "backgroundColor": COLORS["secondary"],
        },
    )
```

#### 8c. Add Company Profile card to the page layout

In `create_asset_page()` (lines 28-207), add a Company Profile card between the stat cards and the price chart row. Insert after the stat cards `dcc.Loading` block (after line 55) and before the price chart `dbc.Row` (line 57).

**Insert after line 55:**
```python
                    # Company Profile card (populated by callback)
                    dcc.Loading(
                        type="default",
                        color=COLORS["accent"],
                        children=html.Div(id="asset-company-profile", className="mb-4"),
                    ),
```

#### 8d. Update the callback to include new outputs

In `register_asset_callbacks` (line 287), update the callback to include the two new outputs.

**Current outputs (lines 293-299):**
```python
    @app.callback(
        [
            Output("asset-stat-cards", "children"),
            Output("asset-current-price", "children"),
            Output("asset-performance-summary", "children"),
            Output("asset-signal-summary", "children"),
            Output("asset-prediction-timeline", "children"),
            Output("asset-related-assets", "children"),
        ],
        [Input("asset-page-symbol", "data")],
    )
```

**New outputs:**
```python
    @app.callback(
        [
            Output("asset-stat-cards", "children"),
            Output("asset-current-price", "children"),
            Output("asset-company-subtitle", "children"),
            Output("asset-company-profile", "children"),
            Output("asset-performance-summary", "children"),
            Output("asset-signal-summary", "children"),
            Output("asset-prediction-timeline", "children"),
            Output("asset-related-assets", "children"),
        ],
        [Input("asset-page-symbol", "data")],
    )
```

**Update the `update_asset_page` function body.** Add after the `stats = get_asset_stats(symbol)` line (line 314) and before the stat_cards section:

```python
            # --- COMPANY FUNDAMENTALS ---
            fundamentals = get_ticker_fundamentals(symbol)
            company_subtitle = _build_company_subtitle(fundamentals)
            company_profile = _build_company_profile_card(fundamentals)
```

**Update the empty return (line 310):**
```python
            empty = html.P("No asset selected.", style={"color": COLORS["text_muted"]})
            return empty, "", [], html.Div(), empty, empty, empty, empty
```

**Update the success return (lines 429-436):**
```python
            return (
                stat_cards,
                current_price_text,
                company_subtitle,
                company_profile,
                performance_summary,
                signal_summary,
                timeline_cards,
                related_links,
            )
```

**Update the error return (line 441):**
```python
            return error_card, "", [], html.Div(), error_card, error_card, error_card, error_card
```

#### 8e. Add helper functions for company profile rendering

Add these helper functions at the bottom of `assets.py` (after the `_mini_stat_card` function, after line 697):

```python
def _format_market_cap(market_cap: Optional[int]) -> str:
    """Format market cap as human-readable string.

    Args:
        market_cap: Market capitalization in USD.

    Returns:
        Formatted string like "$2.8T", "$150.3B", "$4.2M", or "N/A".
    """
    if market_cap is None:
        return "N/A"
    if market_cap >= 1_000_000_000_000:
        return f"${market_cap / 1_000_000_000_000:.1f}T"
    if market_cap >= 1_000_000_000:
        return f"${market_cap / 1_000_000_000:.1f}B"
    if market_cap >= 1_000_000:
        return f"${market_cap / 1_000_000:.1f}M"
    return f"${market_cap:,.0f}"


def _sector_badge(sector: Optional[str]) -> html.Span:
    """Render a compact sector badge.

    Args:
        sector: Sector name (e.g. "Technology"). None renders nothing.

    Returns:
        html.Span badge component, or empty Span if sector is None.
    """
    if not sector:
        return html.Span()

    return html.Span(
        sector,
        style={
            "backgroundColor": f"{COLORS['navy']}40",
            "color": COLORS["text"],
            "fontSize": "0.75rem",
            "padding": "2px 10px",
            "borderRadius": "9999px",
            "fontWeight": "500",
            "letterSpacing": "0.02em",
            "display": "inline-block",
        },
    )


def _build_company_subtitle(fundamentals: dict) -> list:
    """Build the company name + sector badge row for the header.

    Args:
        fundamentals: Dict from get_ticker_fundamentals().

    Returns:
        List of Dash components for the subtitle div.
    """
    children = []

    company_name = fundamentals.get("company_name")
    if company_name:
        children.append(
            html.Span(
                company_name,
                style={
                    "color": COLORS["text_muted"],
                    "fontSize": "1rem",
                    "fontWeight": "400",
                },
            )
        )

    sector = fundamentals.get("sector")
    if sector:
        children.append(_sector_badge(sector))

    return children


def _build_company_profile_card(fundamentals: dict) -> html.Div:
    """Build the Company Profile card for the asset page.

    Shows sector, industry, market cap, P/E, dividend yield, beta, and description.
    Returns an empty Div if no fundamental data is available.

    Args:
        fundamentals: Dict from get_ticker_fundamentals().

    Returns:
        dbc.Card component or empty html.Div.
    """
    # Check if any meaningful data exists
    has_data = any(
        fundamentals.get(key) is not None
        for key in ["company_name", "sector", "market_cap", "pe_ratio", "description"]
    )

    if not has_data:
        return html.Div()  # No fundamentals, render nothing

    # Build metric items
    metrics = []

    def _add_metric(label: str, value: str, icon: str):
        metrics.append(
            html.Div(
                [
                    html.Div(
                        [
                            html.I(
                                className=f"fas fa-{icon} me-2",
                                style={"color": COLORS["accent"], "width": "16px"},
                            ),
                            html.Span(
                                label,
                                style={
                                    "color": COLORS["text_muted"],
                                    "fontSize": "0.8rem",
                                },
                            ),
                        ],
                        style={"display": "flex", "alignItems": "center"},
                    ),
                    html.Div(
                        value,
                        style={
                            "color": COLORS["text"],
                            "fontSize": "0.9rem",
                            "fontWeight": "600",
                            "marginTop": "2px",
                        },
                    ),
                ],
                style={
                    "padding": "8px 0",
                    "borderBottom": f"1px solid {COLORS['border']}",
                },
            )
        )

    if fundamentals.get("sector"):
        _add_metric("Sector", fundamentals["sector"], "layer-group")

    if fundamentals.get("industry"):
        _add_metric("Industry", fundamentals["industry"], "industry")

    if fundamentals.get("market_cap") is not None:
        _add_metric("Market Cap", _format_market_cap(fundamentals["market_cap"]), "coins")

    if fundamentals.get("pe_ratio") is not None:
        pe_str = f"{fundamentals['pe_ratio']:.1f}"
        if fundamentals.get("forward_pe") is not None:
            pe_str += f" / {fundamentals['forward_pe']:.1f} fwd"
        _add_metric("P/E Ratio", pe_str, "calculator")

    if fundamentals.get("dividend_yield") is not None:
        _add_metric(
            "Dividend Yield",
            f"{fundamentals['dividend_yield'] * 100:.2f}%",
            "percentage",
        )

    if fundamentals.get("beta") is not None:
        _add_metric("Beta", f"{fundamentals['beta']:.2f}", "wave-square")

    if fundamentals.get("exchange"):
        _add_metric("Exchange", fundamentals["exchange"], "building-columns")

    # Build the card
    card_body_children = []

    if metrics:
        card_body_children.append(html.Div(metrics))

    # Description (truncated)
    if fundamentals.get("description"):
        card_body_children.append(
            html.P(
                fundamentals["description"],
                style={
                    "color": COLORS["text_muted"],
                    "fontSize": "0.8rem",
                    "lineHeight": "1.5",
                    "marginTop": "12px",
                    "marginBottom": "0",
                },
            )
        )

    return dbc.Card(
        [
            dbc.CardHeader(
                [
                    html.I(className="fas fa-building me-2"),
                    "Company Profile",
                ],
                className="fw-bold",
            ),
            dbc.CardBody(card_body_children),
        ],
        style={"backgroundColor": COLORS["secondary"]},
    )
```

---

### Step 9: Add Sector Badge to Screener Table

**File:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/screener.py`

#### 9a. Update `build_screener_table` signature to accept sector data

**Current signature (lines 197-202):**
```python
def build_screener_table(
    screener_df: pd.DataFrame,
    sparkline_data: Dict[str, pd.DataFrame],
    sort_column: str = "total_predictions",
    sort_ascending: bool = False,
) -> html.Div:
```

**New signature:**
```python
def build_screener_table(
    screener_df: pd.DataFrame,
    sparkline_data: Dict[str, pd.DataFrame],
    sector_data: Optional[Dict[str, str]] = None,
    sort_column: str = "total_predictions",
    sort_ascending: bool = False,
) -> html.Div:
```

Add `Optional` to the imports on line 8:
```python
from typing import Dict, Optional, Tuple
```
This import is already present. No change needed.

#### 9b. Add a "Sector" column to the header

In the header `html.Tr` (around line 251), add a Sector column after the Asset column and before the 30d Price column:

**Insert after the Asset Th (after line 254):**
```python
                html.Th(
                    "Sector",
                    className="screener-hide-mobile",
                    style={
                        **_HEADER_STYLE,
                        "textAlign": "left",
                        "width": "100px",
                    },
                ),
```

#### 9c. Add sector cell to each row

In the row-building loop (around line 308), add a sector cell after the Asset ticker cell.

**After the Asset ticker `html.Td` (after line 327), insert:**
```python
                    # Sector badge
                    html.Td(
                        _screener_sector_badge(
                            sector_data.get(symbol) if sector_data else None
                        ),
                        className="screener-hide-mobile",
                        style={
                            "padding": "10px 8px",
                            "verticalAlign": "middle",
                        },
                    ),
```

#### 9d. Add the `_screener_sector_badge` helper

Add after the `_sentiment_badge` function (after line 104):

```python
# Sector abbreviation map for compact display
_SECTOR_ABBREV: Dict[str, str] = {
    "Technology": "TECH",
    "Healthcare": "HLTH",
    "Financial Services": "FIN",
    "Consumer Cyclical": "CYCL",
    "Consumer Defensive": "DEF",
    "Communication Services": "COMM",
    "Energy": "ENGY",
    "Industrials": "INDL",
    "Basic Materials": "MATL",
    "Real Estate": "REAL",
    "Utilities": "UTIL",
}


def _screener_sector_badge(sector: Optional[str]) -> html.Span:
    """Render a compact sector badge for the screener table.

    Args:
        sector: Sector name from yfinance (e.g., "Technology"). None renders a dash.

    Returns:
        html.Span with abbreviated sector name.
    """
    if not sector:
        return html.Span(
            "-",
            style={"color": COLORS["text_muted"], "fontSize": "0.75rem"},
        )

    label = _SECTOR_ABBREV.get(sector, sector[:4].upper())

    return html.Span(
        label,
        title=sector,  # Full name on hover
        style={
            "backgroundColor": f"{COLORS['navy']}30",
            "color": COLORS["text_muted"],
            "fontSize": "0.65rem",
            "padding": "2px 6px",
            "borderRadius": "4px",
            "fontWeight": "500",
            "letterSpacing": "0.03em",
            "textTransform": "uppercase",
            "display": "inline-block",
            "cursor": "default",
        },
    )
```

---

### Step 10: Pass Sector Data to Screener from Dashboard Callback

**File:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard_callbacks/content.py`

Update the import to include the new query function (line 20-26):

**Add to imports:**
```python
from data import (
    get_asset_screener_data,
    get_screener_sparkline_prices,
    get_screener_sectors,          # NEW
    load_recent_posts,
    get_dashboard_kpis_with_fallback,
    get_dynamic_insights,
)
```

**Update the screener section in `update_dashboard`** (around lines 71-83):

**Current:**
```python
            screener_df = get_asset_screener_data(days=days)
            sparkline_data = {}
            if not screener_df.empty:
                symbols = tuple(screener_df["symbol"].tolist())
                sparkline_data = get_screener_sparkline_prices(symbols=symbols)

            screener_table = build_screener_table(
                screener_df=screener_df,
                sparkline_data=sparkline_data,
                sort_column="total_predictions",
                sort_ascending=False,
            )
```

**New:**
```python
            screener_df = get_asset_screener_data(days=days)
            sparkline_data = {}
            sector_data = {}
            if not screener_df.empty:
                symbols = tuple(screener_df["symbol"].tolist())
                sparkline_data = get_screener_sparkline_prices(symbols=symbols)
                sector_data = get_screener_sectors()

            screener_table = build_screener_table(
                screener_df=screener_df,
                sparkline_data=sparkline_data,
                sector_data=sector_data,
                sort_column="total_predictions",
                sort_ascending=False,
            )
```

---

### Step 11: Database Schema Migration

Since this project does not use Alembic, the schema change must be applied via direct SQL. Add the columns to the production database.

**SQL migration script** (to be run manually or via a one-time CLI command):

```sql
-- Add company fundamentals columns to ticker_registry
ALTER TABLE ticker_registry ADD COLUMN IF NOT EXISTS company_name VARCHAR(255);
ALTER TABLE ticker_registry ADD COLUMN IF NOT EXISTS sector VARCHAR(100);
ALTER TABLE ticker_registry ADD COLUMN IF NOT EXISTS industry VARCHAR(100);
ALTER TABLE ticker_registry ADD COLUMN IF NOT EXISTS market_cap BIGINT;
ALTER TABLE ticker_registry ADD COLUMN IF NOT EXISTS pe_ratio FLOAT;
ALTER TABLE ticker_registry ADD COLUMN IF NOT EXISTS forward_pe FLOAT;
ALTER TABLE ticker_registry ADD COLUMN IF NOT EXISTS dividend_yield FLOAT;
ALTER TABLE ticker_registry ADD COLUMN IF NOT EXISTS beta FLOAT;
ALTER TABLE ticker_registry ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE ticker_registry ADD COLUMN IF NOT EXISTS fundamentals_updated_at TIMESTAMP;

-- Add index for sector-based queries
CREATE INDEX IF NOT EXISTS idx_ticker_registry_sector ON ticker_registry(sector);
```

This can be run via `psql` against the Neon database URL, or added as a CLI command. The `IF NOT EXISTS` / `IF NOT EXISTS` guards make it idempotent.

---

## Test Plan

### New Test File: `/Users/chris/Projects/shitpost-alpha/shit_tests/shit/market_data/test_fundamentals_provider.py`

Create a comprehensive test suite following the existing pattern in `test_ticker_registry.py`.

```
Tests to write:

class TestFetchInfo:
    - test_returns_info_dict_for_valid_symbol
    - test_returns_empty_dict_for_invalid_symbol
    - test_returns_empty_dict_on_exception
    - test_logs_warning_for_invalid_symbol

class TestExtractFundamentals:
    - test_extracts_all_fields_from_complete_info
    - test_handles_missing_sector_for_etf
    - test_handles_missing_pe_for_commodity
    - test_truncates_long_description
    - test_maps_quote_type_to_asset_type
    - test_prefers_longName_over_shortName
    - test_handles_none_market_cap
    - test_handles_non_numeric_market_cap

class TestIsStale:
    - test_returns_true_when_never_updated
    - test_returns_true_when_older_than_threshold
    - test_returns_false_when_fresh

class TestUpdateFundamentals:
    - test_updates_single_ticker_successfully
    - test_skips_fresh_ticker_without_force
    - test_updates_fresh_ticker_with_force
    - test_returns_false_for_unregistered_ticker
    - test_returns_false_when_no_info_returned
    - test_sets_fundamentals_updated_at

class TestUpdateAllFundamentals:
    - test_processes_all_active_tickers
    - test_respects_status_filter
    - test_counts_updated_skipped_failed
    - test_continues_on_individual_failures
```

All tests mock `get_session` and `yf.Ticker` to avoid real API calls and database dependencies.

### Existing Test Modifications

**File:** `/Users/chris/Projects/shitpost-alpha/shit_tests/shit/market_data/test_ticker_registry.py`

Add tests for the new fundamentals trigger in `register_tickers()`:

```
class TestRegisterTickersFundamentals:
    - test_triggers_fundamentals_fetch_for_new_tickers
    - test_fundamentals_failure_does_not_break_registration
    - test_does_not_fetch_fundamentals_when_no_new_tickers
```

These tests mock `FundamentalsProvider.update_fundamentals` to verify it gets called with the right symbols without actually hitting yfinance.

**File:** `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_screener.py`

Add tests for the new sector badge and sector column:

```
class TestScreenerSectorBadge:
    - test_renders_known_sector_abbreviation
    - test_renders_unknown_sector_truncated
    - test_renders_dash_for_none_sector
    - test_sector_badge_has_tooltip

class TestBuildScreenerTableWithSectors:
    - test_table_has_sector_column_header
    - test_rows_include_sector_badges
    - test_works_without_sector_data (sector_data=None)
```

### Manual Verification Steps

1. Run `python -m shit.market_data populate-fundamentals --symbol AAPL` and verify output shows company name, sector, P/E, etc.
2. Run `python -m shit.market_data populate-fundamentals` and verify batch mode processes all active tickers.
3. Visit the asset detail page for a stock (e.g., `/assets/AAPL`) and verify:
   - Company name appears in the header
   - Sector badge appears next to the name
   - Company Profile card shows all available metrics
4. Visit the screener on the dashboard and verify sector badges appear.
5. Run `pytest -v` and confirm all existing tests still pass.

---

## Documentation Updates

### CLAUDE.md

Add to the "Database Architecture > Key Tables > `ticker_registry`" section:

```markdown
- Company fundamentals: `company_name`, `sector`, `industry`, `market_cap`, `pe_ratio`, `forward_pe`, `dividend_yield`, `beta`, `description`, `fundamentals_updated_at`
```

Add to "Essential Commands > Common Development Tasks":

```markdown
# Populate company fundamentals for all tickers
python -m shit.market_data populate-fundamentals

# Populate for a single ticker
python -m shit.market_data populate-fundamentals --symbol AAPL

# Force-refresh all fundamentals
python -m shit.market_data populate-fundamentals --force
```

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Added
- **Company Fundamentals** - Fetch and store company name, sector, industry, market cap, P/E ratios, dividend yield, beta, and business summary from yfinance
  - New `FundamentalsProvider` class in `shit/market_data/fundamentals_provider.py`
  - Auto-populates fundamentals when new tickers are registered
  - CLI: `python -m shit.market_data populate-fundamentals`
- **Company Profile Card** on asset detail page showing sector, industry, market cap, P/E, and description
- **Sector badges** in the asset screener table and asset page header
```

---

## Stress Testing & Edge Cases

### Edge Cases to Handle

1. **ETFs have no sector/industry/P/E:** yfinance returns None for these fields on ETFs like SPY, QQQ. The `_extract_fundamentals` method handles this by leaving them as None. The UI renders "N/A" or hides the metric entirely.

2. **Crypto tickers (BTC-USD) have minimal info:** yfinance returns very limited data for crypto. Only company_name (usually "Bitcoin USD") and asset_type will be populated. The Company Profile card gracefully renders nothing if no meaningful data exists.

3. **Invalid/delisted tickers:** yfinance returns empty or None info. The `fetch_info` method returns `{}` and `update_fundamentals` logs a warning and returns False. The ticker's fundamentals columns stay NULL.

4. **Concurrent registration race condition:** Two workers might register the same ticker simultaneously. The `IntegrityError` handler already catches this for the symbol itself. The fundamentals fetch runs after commit, so only the winner's fetch executes. The loser's `register_tickers` call returns the symbol in `already_known`, and the fundamentals fetch is skipped (no new tickers).

5. **yfinance API rate limiting:** yfinance has no documented rate limit but can throttle aggressive requests. The batch `update_all_fundamentals` processes tickers sequentially (not in parallel) to be a good citizen. For the initial batch of ~50 tickers, this takes ~30-60 seconds.

6. **Description with special characters:** Business summaries can contain Unicode, HTML entities, or very long text. The provider truncates to 500 chars and the UI renders as plain text (no HTML injection risk since Dash escapes by default).

7. **Market cap overflow:** Market caps can be extremely large (Apple = ~$3.5T). Using `BigInteger` (SQLAlchemy maps to PostgreSQL `BIGINT`, max 9.2 quintillion) handles this with room to spare.

### Performance Considerations

- **Startup impact:** None. Fundamentals are fetched lazily when tickers are registered, not at application startup.
- **Dashboard query impact:** The `get_ticker_fundamentals` query is a simple primary key lookup (indexed on `symbol`). The `get_screener_sectors` query scans the registry (typically <100 rows). Both are cached with TTL.
- **yfinance latency:** Each `.info` call takes ~0.5-1.5 seconds. For a batch of 50 tickers, expect ~30-90 seconds. This is a one-time cost per ticker plus daily refreshes.

---

## Verification Checklist

- [ ] `TickerRegistry` model has all 10 new columns (company_name through fundamentals_updated_at)
- [ ] New index `idx_ticker_registry_sector` exists
- [ ] `FundamentalsProvider` class exists and has `update_fundamentals` and `update_all_fundamentals` methods
- [ ] `TickerRegistryService.register_tickers()` triggers fundamentals fetch for new tickers
- [ ] `populate-fundamentals` CLI command works: `python -m shit.market_data populate-fundamentals --symbol AAPL`
- [ ] Batch mode works: `python -m shit.market_data populate-fundamentals`
- [ ] Asset detail page shows company name in header
- [ ] Asset detail page shows Company Profile card with metrics
- [ ] Screener table has Sector column with badges
- [ ] All new query functions are exported from `shitty_ui/data/__init__.py`
- [ ] Cache clearing includes new functions
- [ ] All tests pass: `source venv/bin/activate && pytest -v`
- [ ] No ruff lint errors: `source venv/bin/activate && python -m ruff check .`
- [ ] CHANGELOG.md updated
- [ ] SQL migration applied to production database

---

## What NOT To Do

1. **Do NOT use `ticker.fast_info` instead of `ticker.info`.** The `fast_info` endpoint returns a subset of fields and lacks sector, industry, and description. We need the full `.info` dict.

2. **Do NOT make the fundamentals fetch async.** The `TickerRegistryService` uses synchronous sessions (`get_session`). Introducing async here would require refactoring the entire registration flow. Synchronous is fine because registration happens in background workers, not in request handlers.

3. **Do NOT fetch fundamentals in the dashboard query layer.** The dashboard should only read from the database. Fetching from yfinance during a page load would introduce 1-2 second latency and potential failures. Fundamentals are populated by the registration flow and the CLI command.

4. **Do NOT add fundamentals columns to `prediction_outcomes.sector`.** The `PredictionOutcome.sector` column (line 97 of models.py) already exists but is always NULL. Do NOT try to populate it from ticker_registry in this phase. That would require modifying the outcome calculator, which is a separate concern. Leave it for a future phase.

5. **Do NOT use `ALTER TABLE ... SET NOT NULL` on any new columns.** All existing rows have NULL for these columns. Making them NOT NULL would require a data migration. Keep them nullable.

6. **Do NOT add sector filtering/grouping to the screener in this phase.** The requirements mention "filter/group by sector" but the screener currently has no filter UI. Adding sector badges is sufficient for this PR. Interactive sector filtering should be a separate phase to keep the PR focused.

7. **Do NOT call `create_tables()` to apply schema changes.** The `Base.metadata.create_all()` call in `sync_session.py:create_tables()` uses `CREATE TABLE IF NOT EXISTS`, which does NOT add columns to existing tables. Use the explicit `ALTER TABLE` SQL migration instead.

8. **Do NOT store the full yfinance `.info` dict as JSON.** It's tempting to add a `raw_info` JSON column for future-proofing. Don't. It would add ~5KB per ticker of rarely-used data. Explicit columns are better for querying and indexing.
