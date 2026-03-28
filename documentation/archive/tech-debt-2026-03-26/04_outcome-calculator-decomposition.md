# Phase 04: Decompose outcome_calculator + Split market_data CLI

**Status:** ✅ COMPLETE
**Started:** 2026-03-28
**Completed:** 2026-03-28

- **PR Title**: `refactor: decompose outcome_calculator + split market_data CLI`
- **Risk**: Medium (refactoring actively-used production code, but 725-line test file provides safety net)
- **Estimated Effort**: Medium
- **Files Modified**: 2 (`shit/market_data/outcome_calculator.py`, `shit/market_data/cli.py`)
- **Files Created**: 3 (`shit/market_data/cli_fetch.py`, `shit/market_data/cli_outcomes.py`, `shit/market_data/cli_registry.py`)
- **Files Deleted**: 0

---

## Context

### Why This Change Matters

`_calculate_single_outcome` in `shit/market_data/outcome_calculator.py` is 245 lines with 8 parameters. It handles three distinct responsibilities in a single method:

1. **Base price resolution** (lines 170-244) — fetching the T+0 reference price with retry logic
2. **Trading-day timeframe filling** (lines 248-311) — iterating T+1/T+3/T+7/T+30 and computing returns/correctness/PnL
3. **Intraday price filling** (lines 313-381) — same_day and 1h price snapshots

Similarly, `shit/market_data/cli.py` is 754 lines containing 13 Click commands that serve three unrelated domains: price fetching, outcome calculation, and ticker registry management. Finding a specific command requires scrolling through the entire file.

Both files are actively used in production (Railway cron workers call the outcome calculator; developers use the CLI for ad-hoc operations). The existing 725-line test file (`test_outcome_calculator.py`) and 354-line CLI test file (`test_market_data_cli.py`) provide a comprehensive safety net for this refactoring.

### Goal

Reduce cognitive load and improve maintainability by:
- Breaking `_calculate_single_outcome` into 3 focused helper methods (~50-80 lines each)
- Reducing the main method to ~40-50 lines of orchestration
- Splitting the CLI into domain-specific submodules while preserving the single Click group entry point

---

## Dependencies

- **Depends on**: None (standalone refactoring)
- **Unlocks**: None (quality-of-life improvement)
- **Parallel-safe**: Yes, this phase touches files not modified by other phases in this session

---

## Detailed Implementation Plan

### Part 1: Decompose `_calculate_single_outcome`

The current method at lines 158-402 of `outcome_calculator.py` will be split into three private helpers plus a slimmed-down orchestrator.

#### Step 1A: Extract `_resolve_base_price`

This helper extracts lines 170-244 of the current `_calculate_single_outcome` — the logic that checks the failed symbols cache, looks up existing outcomes, creates/reuses the outcome object, and fetches the T+0 price with retry.

**New method** — add immediately after `_calculate_single_outcome` (which will be rewritten in Step 1D):

```python
def _resolve_base_price(
    self,
    symbol: str,
    prediction_date: date,
    prediction_id: int,
) -> Optional[float]:
    """Fetch the closing price on the prediction date, with retry.

    Tries the local database first.  If no price is found, fetches
    a 7-day window from the market data provider and retries.

    Args:
        symbol: Ticker symbol (e.g. "AAPL").
        prediction_date: Date of the source post/signal.
        prediction_id: For logging context only.

    Returns:
        The closing price as a float, or None if unavailable
        (also adds the symbol to ``_failed_symbols`` on failure).
    """
    price_t0 = self.market_client.get_price_on_date(symbol, prediction_date)
    if not price_t0:
        # Try to fetch it
        try:
            self.market_client.fetch_price_history(
                symbol,
                start_date=prediction_date - timedelta(days=7),
                end_date=prediction_date,
            )
            price_t0 = self.market_client.get_price_on_date(symbol, prediction_date)
        except Exception as e:
            logger.warning(
                f"Could not fetch price for {symbol} on {prediction_date}: {e}",
                extra={
                    "symbol": symbol,
                    "date": str(prediction_date),
                    "error": str(e),
                },
            )
            return None

    if not price_t0:
        self._failed_symbols.add(symbol)
        logger.warning(
            f"No price found for {symbol} on {prediction_date}",
            extra={"symbol": symbol, "date": str(prediction_date)},
        )
        return None

    return price_t0.close
```

#### Step 1B: Extract `_fill_timeframe_prices`

This helper extracts lines 248-311 — the loop over T+1/T+3/T+7/T+30 trading-day offsets that fills price, return, correctness, and PnL fields.

**New method** — add after `_resolve_base_price`:

```python
def _fill_timeframe_prices(
    self,
    outcome: PredictionOutcome,
    symbol: str,
    prediction_date: date,
    base_price: float,
    sentiment: Optional[str],
) -> None:
    """Fill trading-day timeframe fields (T+1, T+3, T+7, T+30) on an outcome.

    For each timeframe, calculates the target trading day, fetches the
    closing price, and sets the price/return/correctness/PnL attributes.
    Sets ``outcome.is_complete = False`` if any target date is in the
    future or if the price cannot be fetched.

    Mutates ``outcome`` in place; returns nothing.

    Args:
        outcome: The PredictionOutcome row to fill.
        symbol: Ticker symbol.
        prediction_date: Date of the source post/signal.
        base_price: Closing price on the prediction date (T+0).
        sentiment: Predicted sentiment string (e.g. "bullish").
    """
    timeframes = [
        (1, "price_t1", "return_t1", "correct_t1", "pnl_t1"),
        (3, "price_t3", "return_t3", "correct_t3", "pnl_t3"),
        (7, "price_t7", "return_t7", "correct_t7", "pnl_t7"),
        (30, "price_t30", "return_t30", "correct_t30", "pnl_t30"),
    ]

    outcome.is_complete = True  # Assume complete until we find missing data

    for trading_days, price_attr, return_attr, correct_attr, pnl_attr in timeframes:
        target_date = self._calendar.trading_day_offset(
            prediction_date, trading_days
        )

        # Skip future dates
        if target_date > date.today():
            outcome.is_complete = False
            continue

        # Skip timeframes that are already filled (avoid redundant API calls)
        if getattr(outcome, price_attr) is not None:
            continue

        # Get price at T+N (trading days)
        price_tn = self.market_client.get_price_on_date(symbol, target_date)

        if not price_tn:
            # Try to fetch it -- use calendar-aware window for the fetch range
            fetch_start = self._calendar.previous_trading_day(target_date)
            try:
                self.market_client.fetch_price_history(
                    symbol,
                    start_date=fetch_start,
                    end_date=target_date,
                )
                price_tn = self.market_client.get_price_on_date(symbol, target_date)
            except Exception as e:
                logger.debug(
                    f"Could not fetch price for {symbol} on {target_date}: {e}",
                    extra={"symbol": symbol, "date": str(target_date)},
                )

        if price_tn:
            # Set price
            setattr(outcome, price_attr, price_tn.close)

            # Calculate return
            return_pct = outcome.calculate_return(base_price, price_tn.close)
            setattr(outcome, return_attr, return_pct)

            # Determine if prediction was correct
            is_correct = (
                outcome.is_correct(sentiment, return_pct) if sentiment else None
            )
            setattr(outcome, correct_attr, is_correct)

            # Calculate P&L for $1000 position
            pnl = outcome.calculate_pnl(return_pct, position_size=1000.0)
            setattr(outcome, pnl_attr, pnl)
        else:
            outcome.is_complete = False
```

#### Step 1C: Extract `_fill_intraday_prices`

This helper extracts lines 313-381 — the intraday snapshot logic for same_day and 1h returns.

**New method** — add after `_fill_timeframe_prices`:

```python
def _fill_intraday_prices(
    self,
    outcome: PredictionOutcome,
    symbol: str,
    post_published_at: datetime,
    sentiment: Optional[str],
) -> None:
    """Fill intraday price fields (same-day close, +1 hour) on an outcome.

    Only fetches intraday data when ``outcome.price_at_post`` is still
    None (avoids redundant API calls on re-evaluation).

    Mutates ``outcome`` in place; returns nothing.

    Args:
        outcome: The PredictionOutcome row to fill.
        symbol: Ticker symbol.
        post_published_at: Full timezone-aware datetime of the source post.
        sentiment: Predicted sentiment string (e.g. "bullish").
    """
    outcome.post_published_at = post_published_at

    # Only fetch intraday for outcomes that don't already have it
    if outcome.price_at_post is None:
        try:
            snapshot = fetch_intraday_snapshot(symbol, post_published_at)
            outcome.price_at_post = snapshot.price_at_post
            outcome.price_1h_after = snapshot.price_1h_after
            # Prefer daily close from MarketPrice over intraday last bar
            if outcome.price_at_next_close is None:
                # Get the next trading day's close for "same-day close"
                next_close_date = self._calendar.nearest_trading_day(
                    post_published_at.date()
                )
                # If post is after market close, next close is next trading day
                if self._calendar.is_trading_day(post_published_at.date()):
                    close_time = self._calendar.session_close_time(
                        post_published_at.date()
                    )
                    if close_time and post_published_at >= close_time:
                        next_close_date = self._calendar.next_trading_day(
                            post_published_at.date()
                        )
                next_close_price = self.market_client.get_price_on_date(
                    symbol, next_close_date
                )
                if next_close_price:
                    outcome.price_at_next_close = next_close_price.close
                elif snapshot.price_at_next_close:
                    outcome.price_at_next_close = snapshot.price_at_next_close
        except Exception as e:
            logger.debug(
                f"Intraday snapshot failed for {symbol}: {e}",
                extra={"symbol": symbol, "error": str(e)},
            )

    # Calculate intraday returns (from price_at_post, not price_at_prediction)
    base_price = outcome.price_at_post
    if base_price and base_price > 0:
        # Same-day close return
        if outcome.price_at_next_close is not None:
            outcome.return_same_day = outcome.calculate_return(
                base_price, outcome.price_at_next_close
            )
            outcome.correct_same_day = (
                outcome.is_correct(sentiment, outcome.return_same_day)
                if sentiment
                else None
            )
            outcome.pnl_same_day = outcome.calculate_pnl(
                outcome.return_same_day, position_size=1000.0
            )

        # 1-hour return
        if outcome.price_1h_after is not None:
            outcome.return_1h = outcome.calculate_return(
                base_price, outcome.price_1h_after
            )
            outcome.correct_1h = (
                outcome.is_correct(sentiment, outcome.return_1h)
                if sentiment
                else None
            )
            outcome.pnl_1h = outcome.calculate_pnl(
                outcome.return_1h, position_size=1000.0
            )
```

#### Step 1D: Rewrite `_calculate_single_outcome` as Orchestrator

Replace the **entire** current `_calculate_single_outcome` method (lines 158-402) with this slim orchestrator that calls the three helpers:

```python
def _calculate_single_outcome(
    self,
    prediction_id: int,
    symbol: str,
    prediction_date: date,
    sentiment: Optional[str],
    confidence: Optional[float],
    force_refresh: bool = False,
    post_datetime: Optional[datetime] = None,
) -> Optional[PredictionOutcome]:
    """Calculate outcome for a single asset prediction."""

    # Skip symbols that already failed price fetch (avoids repeated 7s+ retry delays)
    if symbol in self._failed_symbols:
        logger.debug(
            f"Skipping known-bad symbol {symbol}",
            extra={"symbol": symbol, "prediction_id": prediction_id},
        )
        return None

    # Check if outcome already exists
    existing = (
        self.session.query(PredictionOutcome)
        .filter(
            and_(
                PredictionOutcome.prediction_id == prediction_id,
                PredictionOutcome.symbol == symbol,
            )
        )
        .first()
    )

    if existing and not force_refresh:
        if existing.is_complete:
            logger.debug(
                f"Outcome already complete for prediction {prediction_id}, symbol {symbol}",
                extra={"prediction_id": prediction_id, "symbol": symbol},
            )
            return existing
        else:
            logger.debug(
                f"Outcome incomplete for prediction {prediction_id}, symbol {symbol} — re-evaluating",
                extra={"prediction_id": prediction_id, "symbol": symbol},
            )

    # Create or update outcome
    outcome = (
        existing
        if existing
        else PredictionOutcome(
            prediction_id=prediction_id,
            symbol=symbol,
            prediction_date=prediction_date,
            prediction_sentiment=sentiment,
            prediction_confidence=confidence,
        )
    )

    # Step 1: Resolve base price (T+0)
    base_price = self._resolve_base_price(symbol, prediction_date, prediction_id)
    if base_price is None:
        return None

    outcome.price_at_prediction = base_price

    # Step 2: Fill trading-day timeframe prices (T+1, T+3, T+7, T+30)
    self._fill_timeframe_prices(
        outcome, symbol, prediction_date, base_price, sentiment
    )

    # Step 3: Fill intraday prices (same-day close, +1 hour)
    if post_datetime and base_price:
        self._fill_intraday_prices(outcome, symbol, post_datetime, sentiment)

    outcome.last_price_update = date.today()

    # Save to database
    if not existing:
        self.session.add(outcome)

    self.session.commit()

    logger.info(
        f"Calculated outcome for {symbol} in prediction {prediction_id}",
        extra={
            "prediction_id": prediction_id,
            "symbol": symbol,
            "sentiment": sentiment,
            "return_t7": outcome.return_t7,
            "correct_t7": outcome.correct_t7,
        },
    )

    return outcome
```

#### Summary of Line Ranges in Current File

| Current line range | What it does | Extracted to |
|---|---|---|
| 158-167 | Method signature + docstring | Stays in `_calculate_single_outcome` |
| 170-176 | Failed symbol cache check | Stays in `_calculate_single_outcome` |
| 178-214 | Existing outcome lookup + create/update | Stays in `_calculate_single_outcome` |
| 216-244 | Base price fetch + retry | `_resolve_base_price` |
| 246-256 | Price_at_prediction assignment + timeframes list | Split: assignment stays, list moves to `_fill_timeframe_prices` |
| 258-311 | Timeframe loop (T+1/3/7/30) | `_fill_timeframe_prices` |
| 313-381 | Intraday snapshot logic | `_fill_intraday_prices` |
| 383-401 | Save + log | Stays in `_calculate_single_outcome` |

#### Full File Edit Sequence

The edit is a single replacement of the `_calculate_single_outcome` method body (lines 158-402) with the new orchestrator, followed by inserting the three helper methods between `_calculate_single_outcome` and `calculate_outcomes_for_all_predictions`.

**Concrete edit**: Replace lines 158-402 of `outcome_calculator.py` with:

1. The new slim `_calculate_single_outcome` (~60 lines)
2. The new `_resolve_base_price` method (~40 lines)
3. The new `_fill_timeframe_prices` method (~55 lines)
4. The new `_fill_intraday_prices` method (~60 lines)

The method order in the class after refactoring will be:

```
class OutcomeCalculator:
    __init__
    __enter__
    __exit__
    calculate_outcome_for_prediction   (unchanged)
    _calculate_single_outcome          (rewritten as orchestrator)
    _resolve_base_price                (NEW)
    _fill_timeframe_prices             (NEW)
    _fill_intraday_prices              (NEW)
    calculate_outcomes_for_all_predictions  (unchanged)
    mature_outcomes                     (unchanged)
    get_accuracy_stats                  (unchanged)
    _get_source_datetime               (unchanged)
    _get_source_date                   (unchanged)
    _extract_sentiment                 (unchanged)
```

**No imports change.** The existing imports at lines 1-27 already include everything needed (`date`, `datetime`, `timedelta`, `timezone`, `Optional`, `Session`, `and_`, `PredictionOutcome`, `MarketDataClient`, `MarketCalendar`, `fetch_intraday_snapshot`, `get_session`, `get_service_logger`, `Prediction`, `Signal`).

---

### Part 2: Split `shit/market_data/cli.py`

The 754-line CLI file with 14 commands will be split into a thin entry-point module plus 3 domain submodules.

#### Command Assignment

| Command | Current lines | Target file |
|---|---|---|
| `fetch-prices` | 28-71 | `cli_fetch.py` |
| `update-all-prices` | 73-146 | `cli_fetch.py` |
| `backfill-all-missing` | 635-671 | `cli_fetch.py` |
| `auto-backfill` | 606-632 | `cli_fetch.py` |
| `price-stats` | 407-461 | `cli_fetch.py` |
| `calculate-outcomes` | 149-181 | `cli_outcomes.py` |
| `fix-sentiments` | 184-243 | `cli_outcomes.py` |
| `mature-outcomes` | 246-283 | `cli_outcomes.py` |
| `accuracy-report` | 286-404 | `cli_outcomes.py` |
| `auto-pipeline` | 540-603 | `cli_outcomes.py` |
| `health-check` | 464-537 | `cli_outcomes.py` |
| `ticker-registry` | 674-728 | `cli_registry.py` |
| `register-tickers` | 731-750 | `cli_registry.py` |

#### Step 2A: Create `shit/market_data/cli_fetch.py`

```python
"""
Market Data CLI — Price Fetching Commands
Commands for fetching, backfilling, and inspecting market prices.
"""

import click
from datetime import date, timedelta
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from shit.market_data.client import MarketDataClient
from shit.logging import print_success, print_error, print_info
from shit.db.sync_session import get_session

console = Console()


@click.command()
@click.option("--symbol", "-s", required=True, help="Ticker symbol (e.g., AAPL, TSLA)")
@click.option("--days", "-d", default=30, help="Number of days of history to fetch")
@click.option("--force", "-f", is_flag=True, help="Force refresh even if data exists")
def fetch_prices(symbol: str, days: int, force: bool):
    """Fetch historical prices for a symbol."""
    start_date = date.today() - timedelta(days=days)
    end_date = date.today()

    print_info(f"Fetching {days} days of price data for {symbol}...")

    try:
        with MarketDataClient() as client:
            prices = client.fetch_price_history(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                force_refresh=force,
            )

            if prices:
                print_success(f"✅ Fetched {len(prices)} prices for {symbol}")

                # Show recent prices
                table = Table(title=f"Recent Prices for {symbol}")
                table.add_column("Date", style="cyan")
                table.add_column("Close", style="green", justify="right")
                table.add_column("Volume", style="yellow", justify="right")

                for price in prices[-10:]:  # Last 10 prices
                    table.add_row(
                        str(price.date),
                        f"${price.close:.2f}",
                        f"{price.volume:,}" if price.volume else "N/A",
                    )

                console.print(table)
            else:
                print_error(f"❌ No prices found for {symbol}")

    except Exception as e:
        print_error(f"❌ Error fetching prices: {e}")
        raise click.Abort()


@click.command()
@click.option(
    "--days", "-d", default=30, help="Fetch prices for assets mentioned in last N days"
)
@click.option("--limit", "-l", type=int, help="Limit number of predictions to process")
def update_all_prices(days: int, limit: Optional[int]):
    """Update prices for all assets mentioned in predictions."""
    from shitvault.shitpost_models import Prediction
    from shitvault.signal_models import Signal  # noqa: F401 - registers Signal with SQLAlchemy mapper
    from sqlalchemy import func, distinct

    print_info(f"Finding assets mentioned in predictions (last {days} days)...")

    try:
        with get_session() as session:
            # Get unique assets from predictions
            cutoff_date = date.today() - timedelta(days=days)

            query = session.query(
                func.jsonb_array_elements_text(Prediction.assets).label("asset")
            ).distinct()

            if limit:
                query = query.limit(limit)

            # This is PostgreSQL specific - for SQLite we'll need a different approach
            try:
                assets = [row[0] for row in query.all()]
            except Exception:
                # Fallback: jsonb_array_elements_text fails when column is JSON (not JSONB)
                session.rollback()
                predictions = (
                    session.query(Prediction).filter(Prediction.assets != None).all()
                )

                if limit:
                    predictions = predictions[:limit]

                assets = set()
                for pred in predictions:
                    if pred.assets:
                        assets.update(pred.assets)
                assets = list(assets)

            if not assets:
                print_info("No assets found in predictions")
                return

            print_info(f"Found {len(assets)} unique assets: {', '.join(assets)}")

            # Update prices for each asset
            client = MarketDataClient(session=session)
            start_date = date.today() - timedelta(days=days)

            results = client.update_prices_for_symbols(
                symbols=assets, start_date=start_date
            )

            # Print results
            table = Table(title="Price Update Results")
            table.add_column("Symbol", style="cyan")
            table.add_column("Prices Fetched", style="green", justify="right")

            total_fetched = 0
            for symbol, count in sorted(results.items()):
                table.add_row(symbol, str(count))
                total_fetched += count

            console.print(table)
            print_success(f"✅ Fetched {total_fetched} total price records")

    except Exception as e:
        print_error(f"❌ Error updating prices: {e}")
        raise click.Abort()


@click.command()
@click.option("--symbol", "-s", help="Show stats for specific symbol")
def price_stats(symbol: Optional[str]):
    """Show statistics about stored price data."""
    try:
        with MarketDataClient() as client:
            if symbol:
                # Stats for specific symbol
                stats = client.get_price_stats(symbol)

                if stats["count"] == 0:
                    print_info(f"No price data found for {symbol}")
                    return

                rprint(f"\n[bold]Price Data for {symbol}:[/bold]")
                rprint(f"  Total Records: {stats['count']}")
                rprint(
                    f"  Date Range: {stats['earliest_date']} to {stats['latest_date']}"
                )
                rprint(f"  Latest Price: ${stats['latest_price']:.2f}")

            else:
                # Stats for all symbols
                from shit.market_data.models import MarketPrice
                from sqlalchemy import func

                with get_session() as session:
                    symbols = (
                        session.query(
                            MarketPrice.symbol,
                            func.count(MarketPrice.id).label("count"),
                            func.max(MarketPrice.date).label("latest_date"),
                        )
                        .group_by(MarketPrice.symbol)
                        .all()
                    )

                    if not symbols:
                        print_info("No price data found in database")
                        return

                    table = Table(title="Price Data Summary")
                    table.add_column("Symbol", style="cyan")
                    table.add_column("Records", style="green", justify="right")
                    table.add_column("Latest Date", style="yellow")

                    for symbol, count, latest_date in sorted(symbols):
                        table.add_row(symbol, str(count), str(latest_date))

                    console.print(table)
                    print_info(f"\nTotal symbols: {len(symbols)}")

    except Exception as e:
        print_error(f"❌ Error getting stats: {e}")
        raise click.Abort()


@click.command()
@click.option("--days", "-d", default=7, help="Process predictions from last N days")
@click.option("--limit", "-l", type=int, help="Limit number of predictions to process")
def auto_backfill(days: int, limit: Optional[int]):
    """Automatically backfill assets for recent predictions."""
    from shit.market_data.auto_backfill_service import AutoBackfillService

    print_info(f"Auto-backfilling assets for predictions from last {days} days...")

    try:
        service = AutoBackfillService()
        stats = service.process_new_predictions(days_back=days, limit=limit)

        rprint("\n[bold]Auto-Backfill Results:[/bold]")
        rprint(f"  Predictions processed: {stats['predictions_processed']}")
        rprint(f"  Assets backfilled: {stats['assets_backfilled']}")
        rprint(f"  Outcomes calculated: {stats['outcomes_calculated']}")
        rprint(f"  Errors: {stats['errors']}")

        if stats["assets_backfilled"] > 0:
            print_success(f"✅ Backfilled {stats['assets_backfilled']} assets")
        else:
            print_info("No new assets needed backfilling")

    except Exception as e:
        print_error(f"❌ Error during auto-backfill: {e}")
        raise click.Abort()


@click.command()
def backfill_all_missing():
    """One-time backfill of ALL missing assets (initial setup)."""
    from shit.market_data.auto_backfill_service import AutoBackfillService

    print_info("Starting comprehensive backfill of all missing assets...")
    print_info("This may take 10-20 minutes depending on number of assets...")

    try:
        service = AutoBackfillService()
        stats = service.process_all_missing_assets()

        rprint("\n[bold]Comprehensive Backfill Results:[/bold]")
        rprint(f"  Total unique assets: {stats['total_assets']}")
        rprint(f"  Missing assets found: {stats['missing_assets']}")
        rprint(f"  Successfully backfilled: {stats['backfilled']}")
        rprint(f"  Failed: {stats['failed']}")

        success_rate = (
            (stats["backfilled"] / stats["missing_assets"] * 100)
            if stats["missing_assets"] > 0
            else 0
        )
        rprint(f"\n  [bold magenta]Success Rate: {success_rate:.1f}%[/bold magenta]")

        if stats["backfilled"] > 0:
            print_success(f"✅ Backfilled {stats['backfilled']} assets")

            # Suggest next step
            print_info("\nNext step: Calculate outcomes for all predictions")
            print_info("Run: python -m shit.market_data calculate-outcomes --days 365")
        else:
            print_info("No assets needed backfilling")

    except Exception as e:
        print_error(f"❌ Error during backfill: {e}")
        raise click.Abort()
```

#### Step 2B: Create `shit/market_data/cli_outcomes.py`

```python
"""
Market Data CLI — Outcome Calculation Commands
Commands for calculating, maturing, and reporting on prediction outcomes.
"""

import click
from datetime import date, timedelta
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from shit.market_data.outcome_calculator import OutcomeCalculator
from shit.logging import print_success, print_error, print_info
from shit.db.sync_session import get_session

console = Console()


@click.command()
@click.option("--limit", "-l", type=int, help="Limit number of predictions to process")
@click.option(
    "--days", "-d", type=int, help="Only process predictions from last N days"
)
@click.option("--force", "-f", is_flag=True, help="Recalculate existing outcomes")
def calculate_outcomes(limit: Optional[int], days: Optional[int], force: bool):
    """Calculate outcomes for predictions."""
    print_info("Calculating prediction outcomes...")

    try:
        with OutcomeCalculator() as calculator:
            stats = calculator.calculate_outcomes_for_all_predictions(
                limit=limit, days_back=days, force_refresh=force
            )

            # Print statistics
            rprint("\n[bold]Outcome Calculation Results:[/bold]")
            rprint(f"  Total predictions: {stats['total_predictions']}")
            rprint(f"  Processed: {stats['processed']}")
            rprint(f"  Outcomes created: {stats['outcomes_created']}")
            rprint(f"  Errors: {stats['errors']}")

            if stats["outcomes_created"] > 0:
                print_success(
                    f"✅ Successfully calculated {stats['outcomes_created']} outcomes"
                )
            else:
                print_info("No new outcomes created")

    except Exception as e:
        print_error(f"❌ Error calculating outcomes: {e}")
        raise click.Abort()


@click.command(name="fix-sentiments")
@click.option("--dry-run", is_flag=True, help="Show what would be recalculated without making changes")
def fix_sentiments(dry_run: bool):
    """Recalculate outcomes for multi-asset predictions with incorrect sentiment.

    Finds predictions with multiple assets where market_impact has per-asset
    sentiment data, then force-refreshes their outcomes so each asset gets
    its correct sentiment from the market_impact dict.
    """
    from shitvault.shitpost_models import Prediction
    from sqlalchemy import func

    print_info("Finding multi-asset predictions to fix sentiment...")

    try:
        with OutcomeCalculator() as calculator:
            preds = (
                calculator.session.query(Prediction)
                .filter(
                    Prediction.analysis_status == "completed",
                    Prediction.assets.isnot(None),
                    Prediction.market_impact.isnot(None),
                    func.jsonb_array_length(Prediction.assets) > 1,
                )
                .all()
            )

            rprint(f"\n  Found [bold]{len(preds)}[/bold] multi-asset predictions")

            if dry_run:
                for pred in preds:
                    rprint(
                        f"  Would recalculate prediction {pred.id}: "
                        f"assets={pred.assets}, market_impact={pred.market_impact}"
                    )
                print_info("Dry run complete — no changes made")
                return

            recalculated = 0
            errors = 0

            for pred in preds:
                try:
                    outcomes = calculator.calculate_outcome_for_prediction(
                        pred.id, force_refresh=True
                    )
                    recalculated += len(outcomes)
                except Exception as e:
                    errors += 1
                    rprint(f"  [red]Error recalculating prediction {pred.id}: {e}[/red]")

            rprint(f"\n  Recalculated: [green]{recalculated}[/green] outcomes")
            if errors:
                rprint(f"  Errors: [red]{errors}[/red]")

            print_success(f"✅ Fixed sentiments for {len(preds)} predictions")

    except Exception as e:
        print_error(f"❌ Error fixing sentiments: {e}")
        raise click.Abort()


@click.command(name="mature-outcomes")
@click.option("--limit", "-l", type=int, help="Limit number of incomplete outcomes to process")
@click.option("--emit-event", is_flag=True, help="Emit outcomes_matured event when done")
def mature_outcomes(limit: Optional[int], emit_event: bool):
    """Re-evaluate incomplete prediction outcomes to fill matured timeframes.

    Finds all prediction_outcomes where is_complete=False and re-runs
    outcome calculation for any timeframes that have now matured.
    This fills in T+7 and T+30 values that were NULL at initial creation.
    """
    print_info("Maturing incomplete prediction outcomes...")

    try:
        with OutcomeCalculator() as calculator:
            stats = calculator.mature_outcomes(
                limit=limit, emit_event=emit_event
            )

            # Print statistics
            rprint("\n[bold]Outcome Maturation Results:[/bold]")
            rprint(f"  Incomplete outcomes found: {stats['total_incomplete']}")
            rprint(f"  Outcomes re-evaluated: {stats['matured']}")
            rprint(f"  Newly complete: [green]{stats['newly_complete']}[/green]")
            rprint(f"  Still incomplete: [yellow]{stats['still_incomplete']}[/yellow]")
            rprint(f"  Errors: [red]{stats['errors']}[/red]")

            if stats["newly_complete"] > 0:
                print_success(
                    f"✅ {stats['newly_complete']} outcomes are now fully complete"
                )
            elif stats["matured"] > 0:
                print_info("Some outcomes updated but still have future timeframes pending")
            else:
                print_info("No incomplete outcomes found to mature")

    except Exception as e:
        print_error(f"❌ Error maturing outcomes: {e}")
        raise click.Abort()


@click.command()
@click.option(
    "--timeframe",
    "-t",
    default="t7",
    type=click.Choice(["t1", "t3", "t7", "t30"]),
    help="Timeframe to analyze (t1=1 day, t7=7 days, etc.)",
)
@click.option(
    "--min-confidence", "-c", type=float, help="Minimum confidence threshold (0.0-1.0)"
)
@click.option(
    "--by-confidence", "-b", is_flag=True, help="Show breakdown by confidence levels"
)
def accuracy_report(
    timeframe: str, min_confidence: Optional[float], by_confidence: bool
):
    """Generate accuracy report for predictions."""
    print_info(f"Generating accuracy report for {timeframe}...")

    try:
        with OutcomeCalculator() as calculator:
            if by_confidence:
                # Show accuracy by confidence levels
                confidence_levels = [
                    (0.0, 0.6, "Low"),
                    (0.6, 0.75, "Medium"),
                    (0.75, 1.0, "High"),
                ]

                table = Table(title=f"Accuracy by Confidence Level ({timeframe})")
                table.add_column("Confidence Level", style="cyan")
                table.add_column("Total", style="white", justify="right")
                table.add_column("Correct", style="green", justify="right")
                table.add_column("Incorrect", style="red", justify="right")
                table.add_column("Pending", style="yellow", justify="right")
                table.add_column("Accuracy", style="bold magenta", justify="right")

                for min_conf, max_conf, label in confidence_levels:
                    # Filter outcomes in this confidence range
                    from shit.market_data.models import PredictionOutcome

                    with get_session() as session:
                        outcomes = (
                            session.query(PredictionOutcome)
                            .filter(
                                PredictionOutcome.prediction_confidence >= min_conf,
                                PredictionOutcome.prediction_confidence < max_conf,
                            )
                            .all()
                        )

                        if len(outcomes) == 0:
                            table.add_row(
                                f"{label} ({min_conf:.0%}-{max_conf:.0%})",
                                "0",
                                "0",
                                "0",
                                "0",
                                "N/A",
                            )
                            continue

                        correct_attr = f"correct_{timeframe}"
                        total = len(outcomes)
                        correct = sum(
                            1 for o in outcomes if getattr(o, correct_attr) is True
                        )
                        incorrect = sum(
                            1 for o in outcomes if getattr(o, correct_attr) is False
                        )
                        pending = sum(
                            1 for o in outcomes if getattr(o, correct_attr) is None
                        )
                        accuracy = (
                            (correct / (correct + incorrect) * 100)
                            if (correct + incorrect) > 0
                            else 0.0
                        )

                        table.add_row(
                            f"{label} ({min_conf:.0%}-{max_conf:.0%})",
                            str(total),
                            str(correct),
                            str(incorrect),
                            str(pending),
                            f"{accuracy:.1f}%",
                        )

                console.print(table)

            else:
                # Show overall accuracy
                stats = calculator.get_accuracy_stats(
                    timeframe=timeframe, min_confidence=min_confidence
                )

                rprint("\n[bold]Prediction Accuracy Report:[/bold]")
                rprint(f"  Timeframe: {timeframe}")
                if min_confidence:
                    rprint(f"  Min Confidence: {min_confidence:.0%}")
                rprint(f"\n  Total Predictions: {stats['total']}")
                rprint(f"  Correct: [green]{stats['correct']}[/green]")
                rprint(f"  Incorrect: [red]{stats['incorrect']}[/red]")
                rprint(f"  Pending: [yellow]{stats['pending']}[/yellow]")
                rprint(
                    f"\n  [bold magenta]Accuracy: {stats['accuracy']:.1f}%[/bold magenta]"
                )

                if stats["accuracy"] >= 60:
                    print_success("✅ Above random chance!")
                elif stats["accuracy"] >= 50:
                    print_info("📊 Around random chance")
                else:
                    print_error("❌ Below random chance")

    except Exception as e:
        print_error(f"❌ Error generating report: {e}")
        raise click.Abort()


@click.command(name="health-check")
@click.option("--providers/--no-providers", default=True, help="Check provider connectivity")
@click.option("--freshness/--no-freshness", default=True, help="Check data freshness")
@click.option("--alert/--no-alert", default=False, help="Send Telegram alert if unhealthy")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def health_check(providers: bool, freshness: bool, alert: bool, as_json: bool):
    """Run health check on market data pipeline."""
    from shit.market_data.health import run_health_check

    print_info("Running market data health check...")

    try:
        report = run_health_check(
            check_providers=providers,
            check_freshness=freshness,
            send_alert_on_failure=alert,
        )

        if as_json:
            import json
            rprint(json.dumps(report.to_dict(), indent=2, default=str))
            return

        # Pretty print the report
        status_icon = "\u2705" if report.overall_healthy else "\u274c"
        rprint(f"\n{status_icon} [bold]Market Data Health: {'HEALTHY' if report.overall_healthy else 'UNHEALTHY'}[/bold]")

        if report.providers:
            rprint("\n[bold]Provider Status:[/bold]")
            provider_table = Table()
            provider_table.add_column("Provider", style="cyan")
            provider_table.add_column("Available", justify="center")
            provider_table.add_column("Can Fetch", justify="center")
            provider_table.add_column("Latency", justify="right")
            provider_table.add_column("Error", style="red")

            for p in report.providers:
                provider_table.add_row(
                    p.name,
                    "\u2705" if p.available else "\u274c",
                    "\u2705" if p.can_fetch else "\u274c",
                    f"{p.response_time_ms:.0f}ms" if p.response_time_ms else "N/A",
                    p.error or "",
                )
            console.print(provider_table)

        if report.freshness:
            rprint("\n[bold]Data Freshness:[/bold]")
            fresh_table = Table()
            fresh_table.add_column("Symbol", style="cyan")
            fresh_table.add_column("Latest Date", style="yellow")
            fresh_table.add_column("Days Stale", justify="right")
            fresh_table.add_column("Status", justify="center")

            for f in report.freshness:
                status = "\u2705 Fresh" if not f.is_stale else "\u26a0\ufe0f Stale"
                fresh_table.add_row(
                    f.symbol,
                    str(f.latest_date) if f.latest_date else "No data",
                    str(f.days_stale),
                    status,
                )
            console.print(fresh_table)

        rprint(f"\n[bold]Summary:[/bold] {report.summary}")

        if not report.overall_healthy:
            raise SystemExit(1)

    except SystemExit:
        raise
    except Exception as e:
        print_error(f"\u274c Error running health check: {e}")
        raise click.Abort()


@click.command(name="auto-pipeline")
@click.option(
    "--days-back",
    "-d",
    default=7,
    help="Backfill prices for predictions from last N days",
)
@click.option("--limit", "-l", type=int, help="Limit number of predictions to process")
def auto_pipeline(days_back: int, limit: Optional[int]):
    """Run the full market data pipeline: backfill prices then calculate outcomes."""
    from shit.market_data.auto_backfill_service import auto_backfill_recent
    from shit.logging import get_service_logger

    logger = get_service_logger("market_data_pipeline")

    logger.info(
        "Starting market data pipeline", extra={"days_back": days_back, "limit": limit}
    )
    print_info(
        f"Starting market data pipeline (days_back={days_back}, limit={limit})..."
    )

    try:
        # Step 1: Backfill prices for recent predictions
        print_info("Step 1: Backfilling prices for recent predictions...")
        backfill_stats = auto_backfill_recent(days=days_back)
        logger.info("Backfill complete", extra=backfill_stats)

        rprint("\n[bold]Backfill Results:[/bold]")
        rprint(
            f"  Predictions processed: {backfill_stats.get('predictions_processed', 0)}"
        )
        rprint(f"  Assets backfilled: {backfill_stats.get('assets_backfilled', 0)}")
        rprint(f"  Errors: {backfill_stats.get('errors', 0)}")

        # Step 2: Calculate/refresh outcomes for all predictions
        print_info("\nStep 2: Calculating outcomes for predictions...")
        with OutcomeCalculator() as calculator:
            outcome_stats = calculator.calculate_outcomes_for_all_predictions(
                limit=limit, days_back=days_back
            )
        logger.info("Outcome calculation complete", extra=outcome_stats)

        rprint("\n[bold]Outcome Calculation Results:[/bold]")
        rprint(f"  Total predictions: {outcome_stats.get('total_predictions', 0)}")
        rprint(f"  Processed: {outcome_stats.get('processed', 0)}")
        rprint(f"  Outcomes created: {outcome_stats.get('outcomes_created', 0)}")
        rprint(f"  Errors: {outcome_stats.get('errors', 0)}")

        total_errors = backfill_stats.get("errors", 0) + outcome_stats.get("errors", 0)
        if total_errors > 0:
            print_info(f"\n⚠️  Pipeline completed with {total_errors} errors")
        else:
            print_success("\n✅ Market data pipeline completed successfully")

        logger.info(
            "Pipeline complete",
            extra={"backfill_stats": backfill_stats, "outcome_stats": outcome_stats},
        )

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        print_error(f"❌ Market data pipeline failed: {e}")
        raise SystemExit(1)
```

#### Step 2C: Create `shit/market_data/cli_registry.py`

```python
"""
Market Data CLI — Ticker Registry Commands
Commands for managing the ticker registry.
"""

import click
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from shit.logging import print_success, print_error, print_info
from shit.db.sync_session import get_session

console = Console()


@click.command(name="ticker-registry")
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


@click.command(name="register-tickers")
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

#### Step 2D: Rewrite `shit/market_data/cli.py` as Entry Point

Replace the **entire** contents of `cli.py` with this thin entry point:

```python
"""
Market Data CLI
Command-line interface for market data operations.

Commands are organized into submodules:
- cli_fetch.py — Price fetching, backfilling, and stats
- cli_outcomes.py — Outcome calculation, maturation, accuracy, health, pipeline
- cli_registry.py — Ticker registry management
"""

import click

from shit.market_data.cli_fetch import (
    fetch_prices,
    update_all_prices,
    price_stats,
    auto_backfill,
    backfill_all_missing,
)
from shit.market_data.cli_outcomes import (
    calculate_outcomes,
    fix_sentiments,
    mature_outcomes,
    accuracy_report,
    health_check,
    auto_pipeline,
)
from shit.market_data.cli_registry import (
    ticker_registry_cmd,
    register_tickers_cmd,
)


@click.group()
def cli():
    """Market data commands for tracking prices and prediction outcomes."""
    pass


# Price fetching commands
cli.add_command(fetch_prices)
cli.add_command(update_all_prices)
cli.add_command(price_stats)
cli.add_command(auto_backfill)
cli.add_command(backfill_all_missing)

# Outcome commands
cli.add_command(calculate_outcomes)
cli.add_command(fix_sentiments)
cli.add_command(mature_outcomes)
cli.add_command(accuracy_report)
cli.add_command(health_check)
cli.add_command(auto_pipeline)

# Registry commands
cli.add_command(ticker_registry_cmd)
cli.add_command(register_tickers_cmd)


if __name__ == "__main__":
    cli()
```

**Critical**: The `cli` group object stays in `cli.py`, which is what `__main__.py` imports (`from shit.market_data.cli import cli`). The Click group interface is unchanged — all commands remain registered on the same `cli` group, just via `cli.add_command()` instead of `@cli.command()` decorators.

---

## Test Plan

### No New Tests Needed

Both existing test files provide comprehensive coverage:

- **`shit_tests/shit/market_data/test_outcome_calculator.py`** (725 lines) — Tests `_calculate_single_outcome` behavior end-to-end through the public `calculate_outcome_for_prediction` method. Since the three new helpers are private methods called by `_calculate_single_outcome`, and the method signature and behavior are identical, all existing tests pass without modification.

- **`shit_tests/shit/market_data/test_market_data_cli.py`** (354 lines) — Tests the CLI through the Click `CliRunner` by invoking `cli` and command names (e.g., `runner.invoke(cli, ["auto-pipeline"])`). Since `cli` remains the same object in `shit/market_data/cli.py` and all commands are registered on it via `cli.add_command()`, the test imports and invocations are unchanged.

### Existing Tests Must Pass Unchanged

After refactoring, run:

```bash
./venv/bin/python -m pytest shit_tests/shit/market_data/test_outcome_calculator.py -v
./venv/bin/python -m pytest shit_tests/shit/market_data/test_market_data_cli.py -v
```

Both must produce zero failures and zero errors.

### Test Patch Paths Still Valid

The CLI test file uses these patch paths, all of which remain correct after the split:

```python
BACKFILL_PATCH = "shit.market_data.auto_backfill_service.auto_backfill_recent"  # still valid (source module)
LOGGER_PATCH = "shit.logging.get_service_logger"  # still valid
CALC_PATCH = "shit.market_data.cli.OutcomeCalculator"  # NEEDS UPDATE — see below
```

**Important**: The `CALC_PATCH` in `test_market_data_cli.py` patches `shit.market_data.cli.OutcomeCalculator`. After the split, `OutcomeCalculator` is imported in `cli_outcomes.py`, not `cli.py`. The `auto-pipeline` command lives in `cli_outcomes.py`, so the patch path must change to:

```python
CALC_PATCH = "shit.market_data.cli_outcomes.OutcomeCalculator"
```

**Two test files require patch path updates.** After the split, `OutcomeCalculator` is imported in `cli_outcomes.py`, not `cli.py`.

**File 1: `test_market_data_cli.py`** — Edit line 24:

```python
# Before:
CALC_PATCH = "shit.market_data.cli.OutcomeCalculator"
# After:
CALC_PATCH = "shit.market_data.cli_outcomes.OutcomeCalculator"
```

**File 2: `test_outcome_maturation.py`** — 4 inline patch strings at lines 337, 360, 381, 402:

```python
# Before (each instance):
@patch("shit.market_data.cli.OutcomeCalculator")
# After:
@patch("shit.market_data.cli_outcomes.OutcomeCalculator")
```

No other test changes are needed. The `runner.invoke(cli, ["auto-pipeline"])` calls still work because `cli` is still imported from `shit.market_data.cli` and the `auto_pipeline` command is registered on it.

---

## Documentation Updates

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Changed
- **Outcome Calculator** - Decomposed 245-line `_calculate_single_outcome` into 3 focused helpers: `_resolve_base_price`, `_fill_timeframe_prices`, `_fill_intraday_prices`
- **Market Data CLI** - Split 754-line CLI into domain submodules: `cli_fetch.py`, `cli_outcomes.py`, `cli_registry.py`; entry point preserved at `cli.py`
```

### No README Changes

The `shit/market_data/` directory does not have its own README. The module's public API (`__init__.py`) is unchanged.

### Inline Comments

No new inline comments needed. The docstrings on the three new helper methods provide sufficient documentation.

---

## Stress Testing & Edge Cases

### Edge Cases Handled by Existing Tests

The 725-line test file already covers:
- **Missing prices** — `_resolve_base_price` returns None, caller gets None
- **Failed symbols cache** — symbols that fail once are skipped on retry
- **Incomplete outcomes** — `_fill_timeframe_prices` sets `is_complete = False` for future dates
- **No intraday data** — `_fill_intraday_prices` gracefully handles exceptions from `fetch_intraday_snapshot`
- **Force refresh** — existing outcomes are recalculated when `force_refresh=True`

### Performance

No performance change. The method call overhead of 3 extra function calls per outcome is negligible compared to the network I/O of price fetches (each taking 100ms-7s).

### Error Handling

Each helper method preserves the exact same error handling as the original monolithic method:
- `_resolve_base_price`: catches fetch exceptions, logs warning, returns None
- `_fill_timeframe_prices`: catches per-timeframe fetch exceptions, logs debug, marks incomplete
- `_fill_intraday_prices`: catches intraday snapshot exceptions, logs debug, continues

The outer `_calculate_single_outcome` still commits/logs at the end, and the outer `calculate_outcome_for_prediction` still has its per-asset try/except with session rollback.

---

## Verification Checklist

1. [ ] All 3 new files created: `cli_fetch.py`, `cli_outcomes.py`, `cli_registry.py`
2. [ ] `outcome_calculator.py` has 3 new private methods and slimmed-down `_calculate_single_outcome`
3. [ ] `cli.py` reduced to ~50 lines (group + imports + `add_command` calls)
4. [ ] `__main__.py` unchanged (still imports `cli` from `shit.market_data.cli`)
5. [ ] `__init__.py` unchanged (does not import CLI symbols)
6. [ ] `CALC_PATCH` in `test_market_data_cli.py` updated to `"shit.market_data.cli_outcomes.OutcomeCalculator"`
7. [ ] 4 inline `@patch("shit.market_data.cli.OutcomeCalculator")` in `test_outcome_maturation.py` updated to `cli_outcomes`
8. [ ] Run: `./venv/bin/python -m pytest shit_tests/shit/market_data/test_outcome_calculator.py -v` — all pass
9. [ ] Run: `./venv/bin/python -m pytest shit_tests/shit/market_data/test_market_data_cli.py -v` — all pass
10. [ ] Run: `./venv/bin/python -m pytest shit_tests/shit/market_data/ -v` — full market_data test suite passes
11. [ ] Run: `./venv/bin/python -m ruff check shit/market_data/` — no lint errors
12. [ ] Run: `./venv/bin/python -m ruff format shit/market_data/` — formatting clean
13. [ ] Verify `python -m shit.market_data --help` still lists all 13 commands (import check)
14. [ ] Verify command names are unchanged: `fetch-prices`, `update-all-prices`, `calculate-outcomes`, `fix-sentiments`, `mature-outcomes`, `accuracy-report`, `price-stats`, `health-check`, `auto-pipeline`, `auto-backfill`, `backfill-all-missing`, `ticker-registry`, `register-tickers`
15. [ ] CHANGELOG.md updated

---

## What NOT To Do

1. **Do NOT change the `cli` group object's location.** It must remain in `cli.py` because `__main__.py` imports it from there, and tests import it from `shit.market_data.cli`. Moving it would break both.

2. **Do NOT use `@cli.command()` decorators in the submodules.** The submodule files define standalone `@click.command()` functions. The main `cli.py` uses `cli.add_command()` to register them. If you use `@cli.command()` in the submodules, you create a circular import (submodule imports `cli` from `cli.py`, which imports submodule).

3. **Do NOT change the method signatures of `_calculate_single_outcome`.** The parameter list (7 params + self) stays exactly the same. Tests mock and call this method through `calculate_outcome_for_prediction`, which passes these exact parameters.

4. **Do NOT make the new helper methods public (no leading underscore).** They are implementation details of `_calculate_single_outcome` and should remain private (`_resolve_base_price`, `_fill_timeframe_prices`, `_fill_intraday_prices`).

5. **Do NOT add the new CLI submodules to `__init__.py`'s `__all__`.** CLI modules are not part of the public API. They are only used via `python -m shit.market_data`.

6. **Do NOT forget to update `CALC_PATCH` in BOTH test files.** `test_market_data_cli.py` (line 24 constant) and `test_outcome_maturation.py` (4 inline `@patch` strings). After the split, `OutcomeCalculator` is imported in `cli_outcomes.py`, not `cli.py`. Patching the old path will cause tests to fail because the mock won't intercept the real import.

7. **Do NOT change the `price_t0` variable to just use `base_price` float everywhere in `_fill_timeframe_prices`.** The helper receives `base_price` as a float (the closing price), but the timeframe loop calls `outcome.calculate_return(base_price, price_tn.close)`. This is correct — `base_price` is already a float, and `price_tn.close` is also a float. Do NOT try to pass the full `MarketPrice` object.

8. **Do NOT split the test files.** The tests are organized by the class they test (`OutcomeCalculator`), not by internal method. Splitting tests to mirror the helper decomposition would be over-engineering.

9. **Do NOT import `Signal` in the CLI submodules unless needed.** The current `cli.py` has `from shitvault.signal_models import Signal  # noqa: F401` at the top level to register the SQLAlchemy mapper. This import only needs to happen once per process. Keep it in `cli.py` (the entry point that always runs first) and in `cli_fetch.py`'s `update_all_prices` function body where it's already present. Do NOT add it to every submodule.
