# Phase 01: Reactive Ticker Lifecycle & Market Data Pipeline

## Header

| Field | Value |
|---|---|
| **PR Title** | `feat: reactive ticker lifecycle with auto-backfill on prediction creation` |
| **Risk Level** | Low |
| **Estimated Effort** | Medium (3-5 hours implementation, 1-2 hours testing) |
| **Files Created** | `shit/market_data/ticker_registry.py`, `shit_tests/shit/market_data/test_ticker_registry.py`, `shit_tests/shit/market_data/test_auto_backfill_service.py`, `shit_tests/shitpost_ai/test_reactive_backfill.py` |
| **Files Modified** | `shit/market_data/models.py`, `shit/market_data/__init__.py`, `shit/market_data/auto_backfill_service.py`, `shit/market_data/cli.py`, `shitpost_ai/shitpost_analyzer.py`, `shit/db/sync_session.py`, `railway.json`, `CHANGELOG.md`, `CLAUDE.md` |
| **Files Deleted** | None |

---

## Context: Why This Matters

Currently the Shitpost Alpha pipeline has a critical gap in its measurement lifecycle:

1. **The analyzer creates predictions with ticker symbols** (e.g., `["AAPL", "TSLA"]`) but does nothing to ensure market data exists for those tickers.
2. **The `auto_backfill_service.py` exists** and is fully implemented, but it is never called from the analyzer. It sits idle.
3. **The Railway `market-data` cron service is defined in `railway.json`** but is reportedly not deployed. Even if it were deployed, it only catches tickers on a 15-minute lag via batch processing of recent predictions.
4. **The dashboard (`shitty_ui`) cannot show prediction outcomes** because `prediction_outcomes` rows are never created -- they depend on market price data that is never backfilled.
5. **No ticker tracking exists.** There is no way to know which tickers the system has ever seen, when they were first encountered, or whether their price data is current.

This phase closes the loop: when the LLM says "this post affects AAPL," the system immediately fetches AAPL's price history, registers the ticker for ongoing tracking, and calculates the initial outcome record. The dashboard becomes self-sustaining.

---

## Dependencies

- **Phase 01 has no dependencies.** It is the first phase in the system-evolution session.
- **Phases 03 and 07 depend on this phase.** Phase 03 (Signal-Over-Trend Dashboard View) requires `prediction_outcomes` to be populated automatically. Phase 07 (Market Data Resilience) requires the market data pipeline to be deployed first.

---

## Detailed Implementation Plan

### Step 1: Add `TickerRegistry` SQLAlchemy Model

**File:** `/Users/chris/Projects/shitpost-alpha/shit/market_data/models.py`

**What:** Add a new SQLAlchemy model at the end of the file (before the `Index` lines at line 151) that tracks every unique ticker symbol the system has ever encountered.

**Why:** Without a registry, the system has no memory of which tickers it has seen. Every cron run re-discovers tickers from scratch by scanning all predictions. A registry enables: (a) instant "is this ticker new?" checks, (b) status tracking (active/inactive/invalid), (c) auditing when a ticker was first seen.

Add this model after the `PredictionOutcome` class (after line 148, before line 150):

```python
class TickerRegistry(Base, IDMixin, TimestampMixin):
    """Registry of all ticker symbols the system tracks.

    Once a ticker appears in an LLM prediction, it is registered here
    and tracked for ongoing price updates. This provides:
    - Instant lookup of whether a ticker is already known
    - Status tracking (active, inactive, invalid)
    - Audit trail of when each ticker was first seen
    - Source prediction linkage for debugging
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

    # Metadata
    asset_type = Column(String(20), nullable=True)  # stock, crypto, etf, commodity, index
    exchange = Column(String(20), nullable=True)  # NYSE, NASDAQ, etc.

    def __repr__(self):
        return f"<TickerRegistry(symbol='{self.symbol}', status='{self.status}', first_seen={self.first_seen_date})>"
```

Also add indexes after the existing index declarations (after line 156):

```python
Index('idx_ticker_registry_symbol', TickerRegistry.symbol, unique=True)
Index('idx_ticker_registry_status', TickerRegistry.status)
```

---

### Step 2: Create `TickerRegistryService`

**File to create:** `/Users/chris/Projects/shitpost-alpha/shit/market_data/ticker_registry.py`

**What:** A service class that manages the ticker registry. It provides methods to register new tickers, check if tickers are already known, list active tickers, and update ticker metadata.

**Why:** This encapsulates all registry logic in one place, following the project's pattern of having service classes (like `AutoBackfillService`, `BypassService`).

```python
"""
Ticker Registry Service
Manages the lifecycle of tracked ticker symbols.

When the LLM analyzer identifies tickers in a prediction, this service:
1. Checks if the ticker is already registered
2. Registers new tickers with source_prediction_id
3. Marks invalid tickers (ones yfinance cannot find)
4. Provides the list of active tickers for the cron service to update
"""

from datetime import date, datetime
from typing import List, Optional, Tuple

from sqlalchemy.exc import IntegrityError

from shit.market_data.models import TickerRegistry, MarketPrice
from shit.db.sync_session import get_session
from shit.logging import get_service_logger

logger = get_service_logger("ticker_registry")


class TickerRegistryService:
    """Manages the ticker registry for ongoing price tracking."""

    def register_tickers(
        self,
        symbols: List[str],
        source_prediction_id: Optional[int] = None,
    ) -> Tuple[List[str], List[str]]:
        """
        Register new tickers in the registry.

        Args:
            symbols: List of ticker symbols to register
            source_prediction_id: ID of the prediction that introduced these tickers

        Returns:
            Tuple of (newly_registered, already_known) symbol lists
        """
        if not symbols:
            return ([], [])

        newly_registered = []
        already_known = []

        with get_session() as session:
            for symbol in symbols:
                symbol = symbol.strip().upper()

                # Validate symbol format
                if not symbol or len(symbol) > 20 or " " in symbol:
                    logger.warning(f"Skipping invalid symbol format: '{symbol}'")
                    continue

                # Check if already registered
                existing = (
                    session.query(TickerRegistry)
                    .filter(TickerRegistry.symbol == symbol)
                    .first()
                )

                if existing:
                    already_known.append(symbol)
                    logger.debug(f"Ticker {symbol} already registered (status={existing.status})")
                    continue

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

    def get_new_tickers(self, symbols: List[str]) -> List[str]:
        """
        Identify which tickers from a list are NOT yet registered.

        Args:
            symbols: List of ticker symbols to check

        Returns:
            List of symbols not yet in the registry
        """
        if not symbols:
            return []

        with get_session() as session:
            existing = (
                session.query(TickerRegistry.symbol)
                .filter(TickerRegistry.symbol.in_([s.strip().upper() for s in symbols]))
                .all()
            )
            existing_set = {row[0] for row in existing}

        return [s for s in symbols if s.strip().upper() not in existing_set]

    def get_active_tickers(self) -> List[str]:
        """
        Get all active tickers that should have prices updated.

        Returns:
            List of active ticker symbols
        """
        with get_session() as session:
            results = (
                session.query(TickerRegistry.symbol)
                .filter(TickerRegistry.status == "active")
                .all()
            )
            return [row[0] for row in results]

    def mark_ticker_invalid(self, symbol: str, reason: str) -> None:
        """
        Mark a ticker as invalid (e.g., yfinance cannot find it).

        Args:
            symbol: Ticker symbol
            reason: Why it is being marked invalid
        """
        with get_session() as session:
            entry = (
                session.query(TickerRegistry)
                .filter(TickerRegistry.symbol == symbol.strip().upper())
                .first()
            )

            if entry:
                entry.status = "invalid"
                entry.status_reason = reason[:255]
                session.commit()
                logger.info(f"Marked ticker {symbol} as invalid: {reason}")

    def update_price_metadata(self, symbol: str) -> None:
        """
        Update a ticker's price metadata from the market_prices table.

        Args:
            symbol: Ticker symbol to update
        """
        from sqlalchemy import func

        with get_session() as session:
            entry = (
                session.query(TickerRegistry)
                .filter(TickerRegistry.symbol == symbol.strip().upper())
                .first()
            )

            if not entry:
                return

            stats = (
                session.query(
                    func.min(MarketPrice.date).label("earliest"),
                    func.max(MarketPrice.date).label("latest"),
                    func.count(MarketPrice.id).label("count"),
                )
                .filter(MarketPrice.symbol == symbol)
                .first()
            )

            if stats and stats.count > 0:
                entry.price_data_start = stats.earliest
                entry.price_data_end = stats.latest
                entry.total_price_records = stats.count
                entry.last_price_update = datetime.utcnow()
                session.commit()

    def get_registry_stats(self) -> dict:
        """Get summary statistics about the ticker registry."""
        from sqlalchemy import func

        with get_session() as session:
            total = session.query(func.count(TickerRegistry.id)).scalar() or 0
            active = (
                session.query(func.count(TickerRegistry.id))
                .filter(TickerRegistry.status == "active")
                .scalar()
                or 0
            )
            invalid = (
                session.query(func.count(TickerRegistry.id))
                .filter(TickerRegistry.status == "invalid")
                .scalar()
                or 0
            )
            inactive = (
                session.query(func.count(TickerRegistry.id))
                .filter(TickerRegistry.status == "inactive")
                .scalar()
                or 0
            )

            return {
                "total": total,
                "active": active,
                "invalid": invalid,
                "inactive": inactive,
            }
```

---

### Step 3: Update `AutoBackfillService` to Use Ticker Registry

**File:** `/Users/chris/Projects/shitpost-alpha/shit/market_data/auto_backfill_service.py`

**Change 1 -- Add import (after line 11):**

```python
from shit.market_data.ticker_registry import TickerRegistryService
```

**Change 2 -- Add registry to `__init__` (line 39-47):**

Currently:
```python
def __init__(self, backfill_days: int = 365):
    self.backfill_days = backfill_days
    self.logger = logger
```

After:
```python
def __init__(self, backfill_days: int = 365):
    self.backfill_days = backfill_days
    self.logger = logger
    self.registry = TickerRegistryService()
```

**Change 3 -- Update `backfill_ticker` method (line 95-147):**

After a successful backfill (after line 133, inside the `if len(prices) > 0:` block), add:

```python
                    # Update ticker registry metadata
                    try:
                        self.registry.update_price_metadata(symbol)
                    except Exception as reg_err:
                        self.logger.warning(
                            f"Failed to update registry metadata for {symbol}: {reg_err}",
                            extra={"symbol": symbol}
                        )
```

After an unsuccessful backfill where no price data is available (after line 138, inside the `else:` block for `len(prices) == 0`), add:

```python
                    # Mark as invalid in ticker registry if no data found
                    try:
                        self.registry.mark_ticker_invalid(symbol, "yfinance returned no price data")
                    except Exception as reg_err:
                        self.logger.warning(
                            f"Failed to mark {symbol} invalid in registry: {reg_err}",
                            extra={"symbol": symbol}
                        )
```

**Change 4 -- Update `process_single_prediction` (line 149-201):**

Inside the method, before the missing tickers check (after line 177 / before line 178), add:

```python
            # Register any new tickers in the ticker registry
            try:
                newly_registered, _ = self.registry.register_tickers(
                    prediction.assets,
                    source_prediction_id=prediction.id,
                )
                if newly_registered:
                    self.logger.info(
                        f"Registered {len(newly_registered)} new tickers: {newly_registered}",
                        extra={"tickers": newly_registered, "prediction_id": prediction.id},
                    )
            except Exception as reg_err:
                self.logger.warning(
                    f"Failed to register tickers for prediction {prediction_id}: {reg_err}",
                    extra={"prediction_id": prediction_id},
                )
```

---

### Step 4: Add Reactive Backfill Call in the Analyzer

**File:** `/Users/chris/Projects/shitpost-alpha/shitpost_ai/shitpost_analyzer.py`

**Why:** Currently the analyzer stores a prediction and moves on. By adding one call here, we close the loop: prediction creation immediately triggers market data availability.

**Important design decision:** The backfill uses synchronous code (via `get_session` and `MarketDataClient`). The analyzer is async. We must run the backfill in a thread executor to avoid blocking the event loop.

**Change 1 -- Add import at the top of the file (after line 17):**

```python
import concurrent.futures
from shit.market_data.auto_backfill_service import auto_backfill_prediction
```

**Change 2 -- Modify `_analyze_shitpost` method (around lines 381-394):**

Currently (lines 381-394):
```python
            if not dry_run:
                # Store analysis in database
                analysis_id = await self.prediction_ops.store_analysis(
                    shitpost_id,
                    enhanced_analysis,
                    shitpost
                )

                if analysis_id:
                    logger.debug(f"Stored analysis for shitpost {shitpost_id}")
                else:
                    logger.warning(f"Failed to store analysis for shitpost {shitpost_id}")

            return enhanced_analysis
```

After modification:
```python
            if not dry_run:
                # Store analysis in database
                analysis_id = await self.prediction_ops.store_analysis(
                    shitpost_id,
                    enhanced_analysis,
                    shitpost
                )

                if analysis_id:
                    logger.debug(f"Stored analysis for shitpost {shitpost_id}")

                    # Reactively trigger market data backfill for new tickers
                    assets = enhanced_analysis.get("assets", [])
                    if assets:
                        await self._trigger_reactive_backfill(int(analysis_id), assets)
                else:
                    logger.warning(f"Failed to store analysis for shitpost {shitpost_id}")

            return enhanced_analysis
```

**Change 3 -- Add the `_trigger_reactive_backfill` method** (add after `_enhance_analysis_with_shitpost_data`, before `cleanup`, around line 472):

```python
    async def _trigger_reactive_backfill(self, prediction_id: int, assets: list) -> None:
        """Trigger market data backfill for new tickers found in a prediction.

        Runs the synchronous backfill service in a thread executor to avoid
        blocking the async event loop. Failures are logged but do not
        propagate -- the prediction was already stored successfully.

        Args:
            prediction_id: ID of the newly created prediction
            assets: List of ticker symbols from the prediction
        """
        try:
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                result = await loop.run_in_executor(
                    executor,
                    auto_backfill_prediction,
                    prediction_id,
                )

            if result:
                logger.info(
                    f"Reactive backfill completed for prediction {prediction_id}, assets: {assets}",
                    extra={"prediction_id": prediction_id, "assets": assets},
                )
            else:
                logger.debug(
                    f"Reactive backfill: no new data needed for prediction {prediction_id}",
                    extra={"prediction_id": prediction_id, "assets": assets},
                )

        except Exception as e:
            # Never let backfill failure break the analysis pipeline
            logger.warning(
                f"Reactive backfill failed for prediction {prediction_id}: {e}",
                extra={"prediction_id": prediction_id, "assets": assets, "error": str(e)},
            )
```

---

### Step 5: Update Module Exports and Table Registration

**File:** `/Users/chris/Projects/shitpost-alpha/shit/market_data/__init__.py`

Update imports and `__all__`:

```python
from shit.market_data.models import MarketPrice, PredictionOutcome, TickerRegistry
from shit.market_data.client import MarketDataClient
from shit.market_data.outcome_calculator import OutcomeCalculator

__all__ = [
    "MarketPrice",
    "PredictionOutcome",
    "TickerRegistry",
    "MarketDataClient",
    "OutcomeCalculator",
]
```

**File:** `/Users/chris/Projects/shitpost-alpha/shit/db/sync_session.py`

Update `create_tables()` (line 79) to import `TickerRegistry`:

Currently:
```python
    from shit.market_data.models import MarketPrice, PredictionOutcome
```

After:
```python
    from shit.market_data.models import MarketPrice, PredictionOutcome, TickerRegistry
```

---

### Step 6: Verify Railway Cron Service Configuration

**File:** `/Users/chris/Projects/shitpost-alpha/railway.json`

The current configuration at lines 28-33 already defines the `market-data` service. Reduce `--days-back` from 30 to 7 since the reactive backfill handles new predictions immediately. The cron job now handles: (a) re-running outcome calculations as new trading days pass, (b) catching edge cases where reactive backfill failed.

```json
"market-data": {
    "source": ".",
    "startCommand": "python -m shit.market_data auto-pipeline --days-back 7",
    "cronSchedule": "*/15 * * * *"
}
```

**Post-merge:** Verify on Railway that the service is actually deployed and running.

---

### Step 7: Add Ticker Registry CLI Commands

**File:** `/Users/chris/Projects/shitpost-alpha/shit/market_data/cli.py`

Add after the `backfill_all_missing` command (after line 491, before `if __name__`):

```python
@cli.command(name="ticker-registry")
@click.option(
    "--status",
    "-s",
    type=click.Choice(["active", "inactive", "invalid", "all"]),
    default="all",
    help="Filter by ticker status",
)
def ticker_registry_cmd(status: str):
    """Show all tracked tickers in the registry."""
    from shit.market_data.ticker_registry import TickerRegistryService
    from shit.market_data.models import TickerRegistry

    try:
        service = TickerRegistryService()
        stats = service.get_registry_stats()

        rprint(f"\n[bold]Ticker Registry Stats:[/bold]")
        rprint(f"  Total: {stats['total']}")
        rprint(f"  Active: [green]{stats['active']}[/green]")
        rprint(f"  Invalid: [red]{stats['invalid']}[/red]")
        rprint(f"  Inactive: [yellow]{stats['inactive']}[/yellow]")

        with get_session() as session:
            query = session.query(TickerRegistry)
            if status != "all":
                query = query.filter(TickerRegistry.status == status)
            query = query.order_by(TickerRegistry.first_seen_date.desc())
            tickers = query.all()

            if not tickers:
                print_info("No tickers found matching filter")
                return

            table = Table(title=f"Ticker Registry ({status})")
            table.add_column("Symbol", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("First Seen", style="yellow")
            table.add_column("Last Update", style="white")
            table.add_column("Records", style="magenta", justify="right")

            for t in tickers:
                table.add_row(
                    t.symbol,
                    t.status,
                    str(t.first_seen_date),
                    str(t.last_price_update.date()) if t.last_price_update else "Never",
                    str(t.total_price_records),
                )

            console.print(table)

    except Exception as e:
        print_error(f"Error reading ticker registry: {e}")
        raise click.Abort()


@cli.command(name="register-tickers")
@click.argument("symbols", nargs=-1, required=True)
def register_tickers_cmd(symbols: tuple):
    """Manually register tickers for tracking (e.g., register-tickers AAPL TSLA BTC-USD)."""
    from shit.market_data.ticker_registry import TickerRegistryService

    try:
        service = TickerRegistryService()
        newly_registered, already_known = service.register_tickers(list(symbols))

        if newly_registered:
            print_success(
                f"Registered {len(newly_registered)} new tickers: {', '.join(newly_registered)}"
            )
        if already_known:
            print_info(f"Already registered: {', '.join(already_known)}")

    except Exception as e:
        print_error(f"Error registering tickers: {e}")
        raise click.Abort()
```

---

## Test Plan

### New Test File 1: `shit_tests/shit/market_data/test_ticker_registry.py`

Tests for `TickerRegistryService`. All tests use mocked `get_session` to avoid database dependencies.

```
class TestRegisterTickers:
    test_registers_new_ticker_successfully
    test_skips_already_registered_ticker
    test_returns_newly_registered_and_already_known_lists
    test_handles_empty_symbol_list
    test_skips_invalid_symbol_format_space
    test_skips_invalid_symbol_format_too_long
    test_skips_empty_string_symbol
    test_uppercases_symbols
    test_sets_source_prediction_id
    test_sets_first_seen_date_to_today
    test_default_status_is_active

class TestGetNewTickers:
    test_returns_unknown_tickers
    test_returns_empty_when_all_known
    test_handles_empty_input
    test_uppercases_before_comparison

class TestGetActiveTickers:
    test_returns_only_active_tickers
    test_returns_empty_when_no_active

class TestMarkTickerInvalid:
    test_marks_existing_ticker_invalid
    test_sets_status_reason
    test_handles_nonexistent_ticker_gracefully
    test_truncates_long_reason

class TestUpdatePriceMetadata:
    test_updates_metadata_from_market_prices
    test_handles_nonexistent_ticker
    test_handles_zero_price_records

class TestGetRegistryStats:
    test_returns_correct_counts
    test_returns_zeros_when_empty
```

**Approximate count: 25 tests**

### New Test File 2: `shit_tests/shit/market_data/test_auto_backfill_service.py`

Tests for `AutoBackfillService` with registry integration. Mock `get_session`, `MarketDataClient`, `OutcomeCalculator`, and `TickerRegistryService`.

```
class TestBackfillTicker:
    test_successful_backfill_returns_true
    test_returns_false_for_no_data
    test_skips_invalid_symbols
    test_skips_krx_symbols
    test_handles_yfinance_exception
    test_updates_registry_on_success
    test_marks_invalid_on_no_data

class TestProcessSinglePrediction:
    test_backfills_missing_tickers_and_calculates_outcome
    test_registers_tickers_in_registry
    test_handles_prediction_not_found
    test_handles_prediction_with_no_assets
    test_handles_outcome_calculation_failure

class TestProcessNewPredictions:
    test_processes_recent_predictions
    test_respects_limit_parameter
    test_handles_errors_gracefully

class TestConvenienceFunctions:
    test_auto_backfill_prediction_calls_service
    test_auto_backfill_recent_calls_service
    test_auto_backfill_all_calls_service
```

**Approximate count: 22 tests**

### New Test File 3: `shit_tests/shitpost_ai/test_reactive_backfill.py`

Tests for the reactive backfill integration in the analyzer.

```
class TestTriggerReactiveBackfill:
    test_calls_auto_backfill_prediction_with_correct_id
    test_logs_success_on_backfill
    test_logs_debug_when_no_new_data_needed
    test_catches_exception_and_logs_warning
    test_does_not_propagate_backfill_errors

class TestAnalyzeShitpostReactiveIntegration:
    test_triggers_backfill_after_successful_analysis
    test_does_not_trigger_backfill_on_dry_run
    test_does_not_trigger_backfill_when_no_assets
    test_does_not_trigger_backfill_when_store_fails
    test_does_not_trigger_backfill_for_bypassed_posts
```

**Approximate count: 10 tests**

### Existing Tests to Update

Add new test cases for the two new CLI commands to `shit_tests/shit/market_data/test_market_data_cli.py`:

```
class TestTickerRegistryCommand:
    test_ticker_registry_command_exists
    test_ticker_registry_shows_stats
    test_ticker_registry_filters_by_status

class TestRegisterTickersCommand:
    test_register_tickers_command_exists
    test_registers_new_symbols
    test_shows_already_known_symbols
```

**Approximate count: 5 additional tests**

**Total new tests: ~62**

---

## Documentation Updates

### CHANGELOG.md

Add under `## [Unreleased]` / `### Added`:

```markdown
- **Reactive Ticker Lifecycle** - LLM analyzer now triggers market data backfill immediately when a prediction contains new tickers
  - New `ticker_registry` database table tracks all ticker symbols the system has ever encountered
  - `TickerRegistryService` manages ticker lifecycle (active/inactive/invalid status)
  - `ShitpostAnalyzer._trigger_reactive_backfill()` runs backfill in a thread executor after each successful analysis
  - `AutoBackfillService` integrates with ticker registry for registration and metadata updates
  - Railway `market-data` cron service verified for 15-minute auto-pipeline execution
  - New CLI commands: `ticker-registry` (view tracked tickers) and `register-tickers` (manually add tickers)
```

### CLAUDE.md (Database Architecture Section)

Add the new table to the "Key Tables" section:

```markdown
**`ticker_registry`** - Registry of all tracked ticker symbols
- `id`, `symbol` (unique), `first_seen_date`
- `source_prediction_id` (FK -> predictions.id)
- `status` (active/inactive/invalid), `status_reason`
- `last_price_update`, `price_data_start`, `price_data_end`, `total_price_records`
- `asset_type`, `exchange`
```

---

## Stress Testing & Edge Cases

### Invalid Tickers
- **Scenario:** LLM produces a ticker like `"FAKE123"` or `"THE ECONOMY"`.
- **Handling:** `backfill_ticker` validates symbol format (line 107): `len(symbol) > 10 or ' ' in symbol`. Invalid symbols are skipped. `TickerRegistryService.register_tickers` adds the same validation. If a valid-format-but-nonexistent ticker passes validation, yfinance will return empty data, and `mark_ticker_invalid` will flag it.

### yfinance Failures
- **Scenario:** yfinance API is rate-limited or returns an error.
- **Handling:** `backfill_ticker` catches all exceptions (line 141) and logs them. The reactive backfill in `_trigger_reactive_backfill` wraps the call in a try/except and logs a warning but never crashes. The 15-minute cron job will retry on the next cycle.

### Duplicate Tickers Across Predictions
- **Scenario:** AAPL appears in prediction 1 and prediction 5.
- **Handling:** `TickerRegistryService.register_tickers` checks for existing entries before inserting. The `symbol` column has a unique constraint. The `source_prediction_id` records only the FIRST prediction that introduced the ticker.

### Race Conditions
- **Scenario:** Two concurrent predictions both mention a new ticker NVDA. Both call `register_tickers` simultaneously.
- **Handling:** The `symbol` column has a `unique=True` constraint. If both try to insert at the same time, one will get a database `IntegrityError`. The service catches this with `except IntegrityError: session.rollback()` and logs it gracefully.

### Async/Sync Boundary
- **Scenario:** The analyzer is async. The backfill service is sync.
- **Handling:** `_trigger_reactive_backfill` uses `loop.run_in_executor` with a `ThreadPoolExecutor(max_workers=1)` to run sync code in a separate thread. The sync session uses its own connection pool. No shared state between async and sync sessions. No deadlock risk.

### Korean Exchange Symbols
- **Scenario:** LLM produces `KRX:005930` (Samsung on Korean exchange).
- **Handling:** Already handled in `backfill_ticker` at line 112-114. The symbol is registered in the registry but backfill is skipped and marked invalid.

### Empty Assets List
- **Scenario:** LLM analysis returns `assets: []` (no financial implications).
- **Handling:** The reactive backfill check `if assets:` skips the call entirely. No registry entries created, no backfill attempted.

---

## Verification Checklist

```bash
# 1. Activate virtual environment
source venv/bin/activate

# 2. Run the full test suite to ensure no regressions
pytest -v

# 3. Run only the new tests
pytest -v shit_tests/shit/market_data/test_ticker_registry.py
pytest -v shit_tests/shit/market_data/test_auto_backfill_service.py
pytest -v shit_tests/shitpost_ai/test_reactive_backfill.py

# 4. Run the existing market data tests to check for regressions
pytest -v shit_tests/shit/market_data/

# 5. Verify new CLI commands exist
python3 -m shit.market_data ticker-registry --help
python3 -m shit.market_data register-tickers --help

# 6. Verify the auto-pipeline still works
python3 -m shit.market_data auto-pipeline --help

# 7. Check code style
python3 -m ruff check shit/market_data/ticker_registry.py
python3 -m ruff check shit/market_data/models.py
python3 -m ruff check shit/market_data/auto_backfill_service.py
python3 -m ruff check shitpost_ai/shitpost_analyzer.py

# 8. Verify database table creation works
python3 -c "from shit.market_data.models import TickerRegistry; print('TickerRegistry model OK')"
python3 -c "from shit.market_data.ticker_registry import TickerRegistryService; print('TickerRegistryService OK')"

# 9. Verify imports are clean
python3 -c "from shit.market_data import TickerRegistry; print('Export OK')"

# 10. Show database stats (safe -- read-only)
python3 -m shitvault stats
```

**Post-merge Railway verification:**
- Confirm the `market-data` service appears in Railway dashboard
- Confirm cron schedule shows `*/15 * * * *`
- Check Railway logs after first cron execution for successful pipeline run

---

## What NOT To Do

### DO NOT run `auto_backfill_prediction` synchronously inside the async analyzer
The analyzer runs in an async event loop. The backfill service uses synchronous SQLAlchemy sessions. Calling sync code directly from async code will block the event loop. Always use `loop.run_in_executor()` as shown in Step 4.

### DO NOT make reactive backfill failures crash the analyzer
The prediction was already stored successfully. If backfill fails, the 15-minute cron job will catch it. Wrap the backfill call in try/except and log a warning. Never re-raise.

### DO NOT create a new async version of the backfill service
The sync backfill service works correctly. Converting it to async would require rewriting `MarketDataClient` and `OutcomeCalculator`. The `run_in_executor` approach is the correct pattern.

### DO NOT skip the `TickerRegistry` and rely only on `market_prices` table
The `market_prices` table stores raw OHLCV data. Querying `SELECT DISTINCT symbol FROM market_prices` is expensive on large tables and provides no metadata about when a ticker was first seen, what prediction introduced it, or whether it is still active.

### DO NOT register bypassed/error predictions' tickers
Only predictions with `analysis_status == 'completed'` and a non-empty `assets` list should trigger backfill. Bypassed posts have `assets: []` by design.

### DO NOT change the `store_analysis` return type
`store_analysis` returns `str(prediction.id)` or `None`. The reactive backfill consumes this as `int(analysis_id)`. Do not change the return type -- just cast it.

### DO NOT use Alembic for the database migration
This project does not use Alembic. Tables are created via `Base.metadata.create_all(engine)` in `sync_session.py:create_tables()`. The new `TickerRegistry` model will be picked up automatically. For the production Neon database, a manual `CREATE TABLE` SQL statement will be needed before first deployment. Document this in the PR description.

### DO NOT hardcode the backfill_days value
The `AutoBackfillService` constructor accepts `backfill_days` as a parameter (default 365). Let the default handle it.

### DO NOT modify `prediction_operations.py`
The `store_analysis` method already returns the prediction ID. Adding backfill logic inside `store_analysis` would violate separation of concerns.
