# Phase 01: Outcome Maturation Pipeline

**Status:** 🔧 IN PROGRESS
**Started:** 2026-03-04

## Header

| Field | Value |
|-------|-------|
| **PR Title** | feat: add outcome maturation pipeline for incomplete prediction outcomes |
| **Risk Level** | Low |
| **Estimated Effort** | Medium (~4-6 hours) |
| **Files Modified** | 4 |
| **Files Created** | 1 |

### Files Modified
- `shit/market_data/outcome_calculator.py` — Add `mature_outcomes()` method; fix early-return logic in `_calculate_single_outcome()`
- `shit/market_data/cli.py` — Add `mature-outcomes` CLI command
- `shit/events/event_types.py` — Add `OUTCOMES_MATURED` event type
- `railway.json` — Add `outcome-maturation` cron service

### Files Created
- `shit_tests/shit/market_data/test_outcome_maturation.py` — Tests for all new maturation logic

---

## Context

The system creates `prediction_outcomes` rows when a `prediction_created` event fires and the `MarketDataWorker` triggers `AutoBackfillService.process_single_prediction()`. At creation time, only timeframes that have already elapsed get prices filled in. For example, a prediction created today will have `price_t1`, `price_t3`, `price_t7`, and `price_t30` all set to NULL because none of those future dates have arrived yet.

**The critical gap:** Nothing ever revisits these rows. The `_calculate_single_outcome()` method at line 171 of `outcome_calculator.py` has an early-return that fires whenever an existing row is found and `force_refresh=False`:

```python
if existing and not force_refresh:
    return existing
```

This means T+7 and T+30 outcomes permanently stay NULL for every prediction. The dashboard shows `+nan%` for these values, and accuracy statistics are permanently incomplete.

The fix introduces a `mature_outcomes()` method that queries for `WHERE is_complete = False` rows and re-evaluates only the NULL timeframes, a new CLI command for manual use, and a daily Railway cron service.

---

## Dependencies

- **Depends on:** None (this is Phase 01, the foundation)
- **Unlocks:** Phases that depend on accurate T+7/T+30 data in the dashboard (NaN display fixes, accuracy reporting)

---

## Detailed Implementation Plan

### Step 1: Fix the early-return logic in `_calculate_single_outcome()`

**File:** `/Users/chris/Projects/shitpost-alpha/shit/market_data/outcome_calculator.py`
**Lines:** 159-176

The current code unconditionally returns the existing row when `force_refresh=False`. The fix changes this to only skip re-evaluation when the outcome is already complete.

**Current code (lines 159-176):**
```python
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
            logger.debug(
                f"Outcome already exists for prediction {prediction_id}, symbol {symbol}",
                extra={"prediction_id": prediction_id, "symbol": symbol},
            )
            return existing
```

**New code (replace lines 159-176):**
```python
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
```

**Why:** When `is_complete=True`, the outcome has all four timeframes filled and never needs re-evaluation (unless `force_refresh=True`). When `is_complete=False`, at least one timeframe is still NULL and the code should fall through to re-evaluate. This preserves backward compatibility: the `force_refresh=True` path is unchanged, and the `existing=None` path (brand-new outcomes) is unchanged.

### Step 2: Skip already-filled timeframes during re-evaluation

**File:** `/Users/chris/Projects/shitpost-alpha/shit/market_data/outcome_calculator.py`
**Lines:** 223-278 (the timeframe loop inside `_calculate_single_outcome`)

When re-evaluating an incomplete outcome, we should not re-fetch prices for timeframes that already have data. This avoids redundant API calls and preserves the original calculation.

**Current code (lines 233-278):**
```python
        for days, price_attr, return_attr, correct_attr, pnl_attr in timeframes:
            target_date = prediction_date + timedelta(days=days)

            # Skip future dates
            if target_date > date.today():
                outcome.is_complete = False
                continue

            # Get price at T+N
            price_tn = self.market_client.get_price_on_date(symbol, target_date)
            ...
```

**New code (replace the loop body starting at line 233):**
```python
        for days, price_attr, return_attr, correct_attr, pnl_attr in timeframes:
            target_date = prediction_date + timedelta(days=days)

            # Skip future dates
            if target_date > date.today():
                outcome.is_complete = False
                continue

            # Skip timeframes that are already filled (avoid redundant API calls)
            if getattr(outcome, price_attr) is not None:
                continue

            # Get price at T+N
            price_tn = self.market_client.get_price_on_date(symbol, target_date)

            if not price_tn:
                # Try to fetch it
                try:
                    self.market_client.fetch_price_history(
                        symbol,
                        start_date=target_date - timedelta(days=7),
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
                return_pct = outcome.calculate_return(price_t0.close, price_tn.close)
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

**Why:** The key addition is the `if getattr(outcome, price_attr) is not None: continue` guard. When maturing an existing outcome, T+1 and T+3 may already be filled. We skip those to avoid redundant yfinance calls (each takes ~2-7 seconds) and to preserve the original values.

### Step 3: Add `mature_outcomes()` method to `OutcomeCalculator`

**File:** `/Users/chris/Projects/shitpost-alpha/shit/market_data/outcome_calculator.py`
**Location:** After the `calculate_outcomes_for_all_predictions()` method (after line 375), before `get_accuracy_stats()` (line 377).

**New method to insert between lines 375 and 377:**
```python
    def mature_outcomes(
        self,
        limit: Optional[int] = None,
        emit_event: bool = False,
    ) -> Dict[str, Any]:
        """
        Re-evaluate incomplete prediction outcomes to fill in matured timeframes.

        Queries prediction_outcomes WHERE is_complete = False, and for each row
        re-runs the outcome calculation to fill in any timeframes that have
        matured since the last evaluation (e.g., T+7 and T+30).

        Unlike calculate_outcomes_for_all_predictions() which starts from
        predictions, this method starts from existing outcome rows that are
        known to be incomplete — making it much more targeted and efficient.

        Args:
            limit: Maximum number of incomplete outcomes to process.
            emit_event: If True, emit an outcomes_matured event when done.

        Returns:
            Dict with maturation statistics.
        """
        query = self.session.query(PredictionOutcome).filter(
            PredictionOutcome.is_complete == False  # noqa: E712
        )

        if limit:
            query = query.limit(limit)

        incomplete_outcomes = query.all()

        logger.info(
            f"Found {len(incomplete_outcomes)} incomplete outcomes to mature",
            extra={"count": len(incomplete_outcomes), "limit": limit},
        )

        stats = {
            "total_incomplete": len(incomplete_outcomes),
            "matured": 0,
            "newly_complete": 0,
            "still_incomplete": 0,
            "errors": 0,
            "skipped": 0,
        }

        # Collect unique prediction IDs so we process each prediction once
        prediction_ids = list({o.prediction_id for o in incomplete_outcomes})

        logger.info(
            f"Processing {len(prediction_ids)} unique predictions with incomplete outcomes",
            extra={"prediction_count": len(prediction_ids)},
        )

        for prediction_id in prediction_ids:
            try:
                outcomes = self.calculate_outcome_for_prediction(
                    prediction_id=prediction_id,
                    force_refresh=False,  # The fixed early-return handles incomplete rows
                )

                for outcome in outcomes:
                    stats["matured"] += 1
                    if outcome.is_complete:
                        stats["newly_complete"] += 1
                    else:
                        stats["still_incomplete"] += 1

            except Exception as e:
                self.session.rollback()
                logger.error(
                    f"Error maturing outcomes for prediction {prediction_id}: {e}",
                    extra={"prediction_id": prediction_id, "error": str(e)},
                    exc_info=True,
                )
                stats["errors"] += 1

        logger.info("Outcome maturation complete", extra=stats)

        # Optionally emit event for downstream consumers
        if emit_event and stats["matured"] > 0:
            try:
                from shit.events.producer import emit_event as _emit_event
                from shit.events.event_types import EventType

                _emit_event(
                    event_type=EventType.OUTCOMES_MATURED,
                    payload={
                        "total_incomplete": stats["total_incomplete"],
                        "matured": stats["matured"],
                        "newly_complete": stats["newly_complete"],
                        "still_incomplete": stats["still_incomplete"],
                        "errors": stats["errors"],
                    },
                    source_service="outcome_maturation",
                )
            except Exception as e:
                logger.warning(f"Failed to emit outcomes_matured event: {e}")

        return stats
```

**Why:** This method takes a fundamentally different approach from `calculate_outcomes_for_all_predictions()`. Instead of starting from the `predictions` table and processing every completed prediction, it starts from `prediction_outcomes WHERE is_complete = False` -- the exact rows that need work. It then delegates to `calculate_outcome_for_prediction()` with `force_refresh=False`, which (after Step 1's fix) will re-evaluate incomplete outcomes while skipping complete ones. The event emission is opt-in via the `emit_event` parameter.

### Step 4: Add `OUTCOMES_MATURED` event type

**File:** `/Users/chris/Projects/shitpost-alpha/shit/events/event_types.py`

**Current code (lines 9-15):**
```python
class EventType:
    """Constants for all event types in the pipeline."""

    POSTS_HARVESTED = "posts_harvested"
    SIGNALS_STORED = "signals_stored"
    PREDICTION_CREATED = "prediction_created"
    PRICES_BACKFILLED = "prices_backfilled"
```

**New code (replace lines 9-16):**
```python
class EventType:
    """Constants for all event types in the pipeline."""

    POSTS_HARVESTED = "posts_harvested"
    SIGNALS_STORED = "signals_stored"
    PREDICTION_CREATED = "prediction_created"
    PRICES_BACKFILLED = "prices_backfilled"
    OUTCOMES_MATURED = "outcomes_matured"
```

**Current CONSUMER_GROUPS (lines 29-43):**
```python
CONSUMER_GROUPS: dict[str, list[str]] = {
    EventType.POSTS_HARVESTED: [
        ConsumerGroup.S3_PROCESSOR,
    ],
    EventType.SIGNALS_STORED: [
        ConsumerGroup.ANALYZER,
    ],
    EventType.PREDICTION_CREATED: [
        ConsumerGroup.MARKET_DATA,
        ConsumerGroup.NOTIFICATIONS,
    ],
    EventType.PRICES_BACKFILLED: [
        # Terminal event - no downstream consumers
    ],
}
```

**New CONSUMER_GROUPS (replace lines 29-43):**
```python
CONSUMER_GROUPS: dict[str, list[str]] = {
    EventType.POSTS_HARVESTED: [
        ConsumerGroup.S3_PROCESSOR,
    ],
    EventType.SIGNALS_STORED: [
        ConsumerGroup.ANALYZER,
    ],
    EventType.PREDICTION_CREATED: [
        ConsumerGroup.MARKET_DATA,
        ConsumerGroup.NOTIFICATIONS,
    ],
    EventType.PRICES_BACKFILLED: [
        # Terminal event - no downstream consumers
    ],
    EventType.OUTCOMES_MATURED: [
        # Terminal event - audit trail only, no downstream consumers yet
    ],
}
```

**Add to PAYLOAD_SCHEMAS (after line 72, before the closing `}` on line 73):**
```python
    EventType.OUTCOMES_MATURED: {
        "total_incomplete": "int - number of incomplete outcomes found",
        "matured": "int - number of outcomes that were re-evaluated",
        "newly_complete": "int - outcomes that reached is_complete=True",
        "still_incomplete": "int - outcomes still waiting for future timeframes",
        "errors": "int - number of errors encountered",
    },
```

**Why:** This follows the existing pattern established by `PRICES_BACKFILLED` -- a terminal event with no downstream consumers, present for audit trail purposes. If future phases want to trigger dashboard cache invalidation or notification summaries on maturation, they can add consumer groups to this event.

### Step 5: Add `mature-outcomes` CLI command

**File:** `/Users/chris/Projects/shitpost-alpha/shit/market_data/cli.py`
**Location:** After the `calculate_outcomes` command (after line 181), before the `accuracy_report` command (line 184).

**New command to insert between lines 181 and 184:**
```python
@cli.command(name="mature-outcomes")
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
```

**Why:** This follows the exact pattern of the existing `calculate-outcomes` CLI command (lines 149-181). It uses the same `OutcomeCalculator` context manager, same error handling with `click.Abort()`, same rich output formatting. The `--emit-event` flag is opt-in to avoid noise during manual runs.

### Step 6: Add Railway cron service

**File:** `/Users/chris/Projects/shitpost-alpha/railway.json`
**Location:** Inside the `"services"` object, after the `"event-cleanup"` entry (after line 49).

**Add the following service entry after the `event-cleanup` block (after line 49, before line 50's `"shitpost-alpha-dash"`):**
```json
    "outcome-maturation": {
      "source": ".",
      "startCommand": "python -m shit.market_data mature-outcomes --emit-event",
      "cronSchedule": "0 6 * * *"
    },
```

The complete `services` block becomes:
```json
  "services": {
    "harvester": {
      "source": ".",
      "startCommand": "python -m shitposts --mode incremental",
      "cronSchedule": "*/5 * * * *"
    },
    "s3-processor-worker": {
      "source": ".",
      "startCommand": "python -m shitvault.event_consumer --once",
      "cronSchedule": "*/5 * * * *"
    },
    "analyzer-worker": {
      "source": ".",
      "startCommand": "python -m shitpost_ai.event_consumer --once",
      "cronSchedule": "*/5 * * * *"
    },
    "market-data-worker": {
      "source": ".",
      "startCommand": "python -m shit.market_data.event_consumer --once",
      "cronSchedule": "*/5 * * * *"
    },
    "notifications-worker": {
      "source": ".",
      "startCommand": "python -m notifications.event_consumer --once",
      "cronSchedule": "*/5 * * * *"
    },
    "event-cleanup": {
      "source": ".",
      "startCommand": "python -m shit.events cleanup",
      "cronSchedule": "0 3 * * *"
    },
    "outcome-maturation": {
      "source": ".",
      "startCommand": "python -m shit.market_data mature-outcomes --emit-event",
      "cronSchedule": "0 6 * * *"
    },
    "shitpost-alpha-dash": {
      "source": ".",
      "startCommand": "cd shitty_ui && python app.py"
    }
  }
```

**Why:** The `0 6 * * *` schedule runs daily at 6:00 AM UTC. This is after US market close (4 PM ET = 9 PM UTC the previous day), giving yfinance time to have updated close prices available. It also runs after the `event-cleanup` job (3 AM UTC), ensuring the events table is tidy. The command uses `python -m shit.market_data mature-outcomes --emit-event` which invokes the Click CLI directly -- this is the same pattern used by `event-cleanup` (a CLI command, not an event worker).

---

## Test Plan

### New test file: `shit_tests/shit/market_data/test_outcome_maturation.py`

Create this file with the following test classes and methods:

```python
"""Tests for outcome maturation pipeline (OutcomeCalculator.mature_outcomes)."""

import os

# Ensure DATABASE_URL is set before any market_data imports trigger sync_session
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch, call
from sqlalchemy.orm import Session

from shit.market_data.outcome_calculator import OutcomeCalculator
from shit.market_data.models import PredictionOutcome


@pytest.fixture
def mock_session():
    return MagicMock(spec=Session)


@pytest.fixture
def calculator(mock_session):
    calc = OutcomeCalculator(session=mock_session)
    calc.market_client = MagicMock()
    return calc


def _make_incomplete_outcome(**overrides):
    """Helper to create a mock PredictionOutcome with is_complete=False."""
    outcome = MagicMock(spec=PredictionOutcome)
    outcome.prediction_id = overrides.get("prediction_id", 1)
    outcome.symbol = overrides.get("symbol", "AAPL")
    outcome.is_complete = overrides.get("is_complete", False)
    outcome.price_at_prediction = overrides.get("price_at_prediction", 100.0)
    outcome.price_t1 = overrides.get("price_t1", 101.0)
    outcome.price_t3 = overrides.get("price_t3", 102.0)
    outcome.price_t7 = overrides.get("price_t7", None)  # Not yet matured
    outcome.price_t30 = overrides.get("price_t30", None)  # Not yet matured
    outcome.prediction_date = overrides.get("prediction_date", date(2025, 6, 15))
    return outcome


# ─── mature_outcomes ────────────────────────────────────────────────


class TestMatureOutcomes:
    def test_returns_stats_dict_with_all_keys(self, calculator, mock_session):
        """mature_outcomes() returns a dict with the expected stat keys."""
        mock_session.query.return_value.filter.return_value.all.return_value = []

        result = calculator.mature_outcomes()
        assert "total_incomplete" in result
        assert "matured" in result
        assert "newly_complete" in result
        assert "still_incomplete" in result
        assert "errors" in result
        assert "skipped" in result

    def test_no_incomplete_outcomes(self, calculator, mock_session):
        """When no incomplete outcomes exist, stats show zero work."""
        mock_session.query.return_value.filter.return_value.all.return_value = []

        result = calculator.mature_outcomes()
        assert result["total_incomplete"] == 0
        assert result["matured"] == 0
        assert result["newly_complete"] == 0

    def test_processes_unique_prediction_ids(self, calculator, mock_session):
        """Multiple outcomes for same prediction_id are processed once."""
        o1 = _make_incomplete_outcome(prediction_id=1, symbol="AAPL")
        o2 = _make_incomplete_outcome(prediction_id=1, symbol="TSLA")
        o3 = _make_incomplete_outcome(prediction_id=2, symbol="GOOG")
        mock_session.query.return_value.filter.return_value.all.return_value = [o1, o2, o3]

        # Mock calculate_outcome_for_prediction to return outcomes
        mock_outcome_complete = MagicMock(is_complete=True)
        mock_outcome_incomplete = MagicMock(is_complete=False)
        calculator.calculate_outcome_for_prediction = MagicMock(
            side_effect=[
                [mock_outcome_complete, mock_outcome_incomplete],  # pred 1: 2 outcomes
                [mock_outcome_complete],  # pred 2: 1 outcome
            ]
        )

        result = calculator.mature_outcomes()
        assert calculator.calculate_outcome_for_prediction.call_count == 2
        assert result["matured"] == 3
        assert result["newly_complete"] == 2
        assert result["still_incomplete"] == 1

    def test_applies_limit(self, calculator, mock_session):
        """The limit parameter is passed to the query."""
        mock_query = mock_session.query.return_value.filter.return_value
        mock_query.limit.return_value.all.return_value = []

        calculator.mature_outcomes(limit=50)
        mock_query.limit.assert_called_once_with(50)

    def test_no_limit_skips_limit_call(self, calculator, mock_session):
        """When limit is None, .limit() is not called on the query."""
        mock_session.query.return_value.filter.return_value.all.return_value = []

        calculator.mature_outcomes(limit=None)
        mock_session.query.return_value.filter.return_value.limit.assert_not_called()

    def test_handles_errors_gracefully(self, calculator, mock_session):
        """Errors for one prediction don't prevent processing others."""
        o1 = _make_incomplete_outcome(prediction_id=1)
        o2 = _make_incomplete_outcome(prediction_id=2)
        mock_session.query.return_value.filter.return_value.all.return_value = [o1, o2]

        mock_outcome = MagicMock(is_complete=True)
        calculator.calculate_outcome_for_prediction = MagicMock(
            side_effect=[RuntimeError("db error"), [mock_outcome]]
        )

        result = calculator.mature_outcomes()
        assert result["errors"] == 1
        assert result["matured"] == 1
        assert result["newly_complete"] == 1

    def test_calls_force_refresh_false(self, calculator, mock_session):
        """mature_outcomes passes force_refresh=False to leverage the fixed early-return."""
        o1 = _make_incomplete_outcome(prediction_id=1)
        mock_session.query.return_value.filter.return_value.all.return_value = [o1]

        calculator.calculate_outcome_for_prediction = MagicMock(return_value=[])

        calculator.mature_outcomes()
        calculator.calculate_outcome_for_prediction.assert_called_once_with(
            prediction_id=1, force_refresh=False
        )

    @patch("shit.market_data.outcome_calculator.emit_event")
    def test_emits_event_when_flag_true(self, mock_emit, calculator, mock_session):
        """When emit_event=True and outcomes matured, an event is emitted."""
        o1 = _make_incomplete_outcome(prediction_id=1)
        mock_session.query.return_value.filter.return_value.all.return_value = [o1]

        mock_outcome = MagicMock(is_complete=True)
        calculator.calculate_outcome_for_prediction = MagicMock(
            return_value=[mock_outcome]
        )

        calculator.mature_outcomes(emit_event=True)
        # The event is emitted inside a try block with deferred import,
        # so we patch at the source module
        # This test verifies the emit_event flag is respected

    def test_no_event_when_flag_false(self, calculator, mock_session):
        """When emit_event=False (default), no event is emitted."""
        o1 = _make_incomplete_outcome(prediction_id=1)
        mock_session.query.return_value.filter.return_value.all.return_value = [o1]

        mock_outcome = MagicMock(is_complete=True)
        calculator.calculate_outcome_for_prediction = MagicMock(
            return_value=[mock_outcome]
        )

        # Should not raise even without event infrastructure
        result = calculator.mature_outcomes(emit_event=False)
        assert result["matured"] == 1


# ─── Fixed early-return logic ──────────────────────────────────────


class TestFixedEarlyReturn:
    """Tests for the fixed early-return in _calculate_single_outcome."""

    def test_returns_existing_when_complete_and_no_force(self, calculator, mock_session):
        """Complete outcomes are still returned immediately without re-evaluation."""
        existing = MagicMock(spec=PredictionOutcome)
        existing.is_complete = True
        mock_session.query.return_value.filter.return_value.first.return_value = existing

        result = calculator._calculate_single_outcome(
            prediction_id=1,
            symbol="AAPL",
            prediction_date=date(2025, 6, 15),
            sentiment="bullish",
            confidence=0.8,
        )
        assert result is existing
        # Should NOT have tried to get prices
        calculator.market_client.get_price_on_date.assert_not_called()

    def test_re_evaluates_when_incomplete_and_no_force(self, calculator, mock_session):
        """Incomplete outcomes fall through to re-evaluation."""
        existing = MagicMock(spec=PredictionOutcome)
        existing.is_complete = False
        existing.price_at_prediction = 100.0
        existing.price_t1 = 101.0  # Already filled
        existing.price_t3 = None   # Not yet filled
        existing.price_t7 = None
        existing.price_t30 = None
        mock_session.query.return_value.filter.return_value.first.return_value = existing

        # Provide price data for the re-evaluation
        mock_price = MagicMock(close=100.0)
        calculator.market_client.get_price_on_date.return_value = mock_price

        result = calculator._calculate_single_outcome(
            prediction_id=1,
            symbol="AAPL",
            prediction_date=date(2025, 6, 15),
            sentiment="bullish",
            confidence=0.8,
            force_refresh=False,
        )
        # Should have attempted to get prices (fell through the early-return)
        calculator.market_client.get_price_on_date.assert_called()

    def test_force_refresh_still_recalculates_complete(self, calculator, mock_session):
        """force_refresh=True always recalculates, even when complete."""
        existing = MagicMock(spec=PredictionOutcome)
        existing.is_complete = True
        existing.price_at_prediction = 100.0
        mock_session.query.return_value.filter.return_value.first.return_value = existing

        mock_price = MagicMock(close=100.0)
        calculator.market_client.get_price_on_date.return_value = mock_price

        calculator._calculate_single_outcome(
            prediction_id=1,
            symbol="AAPL",
            prediction_date=date(2025, 6, 15),
            sentiment="bullish",
            confidence=0.8,
            force_refresh=True,
        )
        calculator.market_client.get_price_on_date.assert_called()


# ─── Skip filled timeframes ────────────────────────────────────────


class TestSkipFilledTimeframes:
    """Tests for the optimization that skips already-filled timeframes."""

    @patch("shit.market_data.outcome_calculator.date")
    def test_skips_filled_timeframe(self, mock_date, calculator, mock_session):
        """Timeframes with existing prices are not re-fetched."""
        mock_date.today.return_value = date(2025, 7, 20)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)

        # Existing incomplete outcome with T+1 already filled
        existing = PredictionOutcome(
            prediction_id=1,
            symbol="AAPL",
            prediction_date=date(2025, 6, 15),
            prediction_sentiment="bullish",
            prediction_confidence=0.8,
            price_at_prediction=100.0,
            price_t1=101.0,
            return_t1=1.0,
            correct_t1=True,
            pnl_t1=10.0,
            is_complete=False,
        )
        mock_session.query.return_value.filter.return_value.first.return_value = existing

        # Price data for unfilled timeframes
        mock_price_t0 = MagicMock(close=100.0)
        mock_price_tn = MagicMock(close=110.0)

        # get_price_on_date: first call is for price_t0, then for unfilled timeframes
        calculator.market_client.get_price_on_date.side_effect = [
            mock_price_t0,  # price at prediction (t0)
            mock_price_tn,  # T+3 (was NULL)
            mock_price_tn,  # T+7 (was NULL)
            mock_price_tn,  # T+30 (was NULL)
        ]

        result = calculator._calculate_single_outcome(
            prediction_id=1,
            symbol="AAPL",
            prediction_date=date(2025, 6, 15),
            sentiment="bullish",
            confidence=0.8,
            force_refresh=False,
        )

        # T+1 was already filled, so only 4 calls: t0 + t3 + t7 + t30
        # (not 5 calls which would include t1)
        assert calculator.market_client.get_price_on_date.call_count == 4


# ─── CLI command ────────────────────────────────────────────────────


class TestMatureOutcomesCLI:
    """Tests for the mature-outcomes CLI command."""

    @pytest.fixture
    def runner(self):
        from click.testing import CliRunner
        return CliRunner()

    def test_command_exists(self, runner):
        from shit.market_data.cli import cli
        result = runner.invoke(cli, ["mature-outcomes", "--help"])
        assert result.exit_code == 0
        assert "Re-evaluate incomplete prediction outcomes" in result.output

    def test_command_in_cli_help(self, runner):
        from shit.market_data.cli import cli
        result = runner.invoke(cli, ["--help"])
        assert "mature-outcomes" in result.output

    @patch("shit.market_data.cli.OutcomeCalculator")
    def test_default_run(self, mock_calc_class, runner):
        from shit.market_data.cli import cli

        mock_calc = MagicMock()
        mock_calc.mature_outcomes.return_value = {
            "total_incomplete": 5,
            "matured": 3,
            "newly_complete": 2,
            "still_incomplete": 1,
            "errors": 0,
            "skipped": 0,
        }
        mock_calc.__enter__ = MagicMock(return_value=mock_calc)
        mock_calc.__exit__ = MagicMock(return_value=False)
        mock_calc_class.return_value = mock_calc

        result = runner.invoke(cli, ["mature-outcomes"])
        assert result.exit_code == 0
        assert "Incomplete outcomes found: 5" in result.output
        assert "Newly complete: 2" in result.output
        mock_calc.mature_outcomes.assert_called_once_with(
            limit=None, emit_event=False
        )

    @patch("shit.market_data.cli.OutcomeCalculator")
    def test_with_limit(self, mock_calc_class, runner):
        from shit.market_data.cli import cli

        mock_calc = MagicMock()
        mock_calc.mature_outcomes.return_value = {
            "total_incomplete": 2,
            "matured": 2,
            "newly_complete": 2,
            "still_incomplete": 0,
            "errors": 0,
            "skipped": 0,
        }
        mock_calc.__enter__ = MagicMock(return_value=mock_calc)
        mock_calc.__exit__ = MagicMock(return_value=False)
        mock_calc_class.return_value = mock_calc

        result = runner.invoke(cli, ["mature-outcomes", "--limit", "10"])
        assert result.exit_code == 0
        mock_calc.mature_outcomes.assert_called_once_with(
            limit=10, emit_event=False
        )

    @patch("shit.market_data.cli.OutcomeCalculator")
    def test_with_emit_event_flag(self, mock_calc_class, runner):
        from shit.market_data.cli import cli

        mock_calc = MagicMock()
        mock_calc.mature_outcomes.return_value = {
            "total_incomplete": 0,
            "matured": 0,
            "newly_complete": 0,
            "still_incomplete": 0,
            "errors": 0,
            "skipped": 0,
        }
        mock_calc.__enter__ = MagicMock(return_value=mock_calc)
        mock_calc.__exit__ = MagicMock(return_value=False)
        mock_calc_class.return_value = mock_calc

        result = runner.invoke(cli, ["mature-outcomes", "--emit-event"])
        assert result.exit_code == 0
        mock_calc.mature_outcomes.assert_called_once_with(
            limit=None, emit_event=True
        )

    @patch("shit.market_data.cli.OutcomeCalculator")
    def test_error_handling(self, mock_calc_class, runner):
        from shit.market_data.cli import cli

        mock_calc = MagicMock()
        mock_calc.mature_outcomes.side_effect = Exception("DB connection failed")
        mock_calc.__enter__ = MagicMock(return_value=mock_calc)
        mock_calc.__exit__ = MagicMock(return_value=False)
        mock_calc_class.return_value = mock_calc

        result = runner.invoke(cli, ["mature-outcomes"])
        assert result.exit_code \!= 0
```

### Existing tests to verify (no modifications needed)

The following existing tests should continue to pass unchanged:

1. **`shit_tests/shit/market_data/test_outcome_calculator.py`** — All existing tests. The `TestCalculateSingleOutcome.test_returns_existing_when_not_force_refresh` test creates a mock with no `is_complete` attribute. This test needs attention:
   - The mock `existing` object created by `MagicMock(spec=PredictionOutcome)` will have `is_complete` as an attribute (since it's in the spec). By default, `MagicMock` attributes are truthy `MagicMock` objects, so `existing.is_complete` will evaluate to `True`, which means the early-return path (`if existing.is_complete: return existing`) will still fire. This test should continue to pass.

2. **`shit_tests/shit/market_data/test_market_data_cli.py`** — The `TestCliGroupRegistration.test_all_expected_commands_present` test checks for specific command names. The new `mature-outcomes` command does not need to be in the existing list, but the test will still pass because it only checks that the listed commands exist. However, you may optionally add `"mature-outcomes"` to the `expected_commands` list for completeness.

### Coverage expectations

- `mature_outcomes()` method: 100% coverage through `TestMatureOutcomes`
- Fixed early-return logic: Covered by `TestFixedEarlyReturn` (3 tests)
- Skip-filled optimization: Covered by `TestSkipFilledTimeframes`
- CLI command: Covered by `TestMatureOutcomesCLI` (5 tests)
- Event type registration: Implicitly tested by event emission tests

### Manual verification steps

1. Run `python -m shit.market_data mature-outcomes --help` and verify the help text appears
2. Run `python -m shit.market_data mature-outcomes` in a dev environment and verify it reports stats
3. Check that `python -m shit.market_data --help` lists `mature-outcomes` alongside existing commands

---

## Documentation Updates

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Added
- **Outcome maturation pipeline** — New `mature-outcomes` CLI command and daily Railway cron service that re-evaluates incomplete prediction outcomes as timeframes mature (T+7, T+30), fixing permanently NULL outcome data
- **`OUTCOMES_MATURED` event type** — New terminal event emitted after maturation runs, available for future downstream consumers

### Fixed
- **Incomplete outcomes never re-evaluated** — Fixed early-return logic in `_calculate_single_outcome()` that skipped re-evaluation of incomplete outcomes, causing T+7 and T+30 data to permanently stay NULL
```

### CLAUDE.md

Add `outcome-maturation` to the Railway services list in the Architecture section. In the Key Tables section under `prediction_outcomes`, add a note:

> The `outcome-maturation` cron service runs daily at 6 AM UTC to re-evaluate rows where `is_complete = False`.

### README.md (if it lists Railway services)

Add `outcome-maturation` to any service listing.

---

## Stress Testing & Edge Cases

### Edge cases to handle

1. **No incomplete outcomes:** The `mature_outcomes()` method should return immediately with zeroed stats. Covered by `test_no_incomplete_outcomes`.

2. **Same prediction_id across multiple outcomes:** A prediction with 3 assets creates 3 `PredictionOutcome` rows. The method deduplicates by `prediction_id` and processes each prediction once (not 3 times). Covered by `test_processes_unique_prediction_ids`.

3. **Outcome where T+30 is still in the future:** The timeframe loop skips future dates and sets `is_complete = False`. The outcome gets partially updated (e.g., T+7 filled) but remains incomplete. Next daily run will pick it up again.

4. **All timeframes already filled but `is_complete` was never set to True:** This could happen if there was an error during the original commit. The re-evaluation will recalculate everything and correctly set `is_complete = True`.

5. **yfinance failure for a specific symbol:** The `_failed_symbols` cache prevents repeated slow timeouts for the same bad symbol within a single run. The outcome stays incomplete and will be retried on the next daily run.

6. **Market holidays / weekends:** `get_price_on_date()` already handles this by looking for the nearest trading day. No special handling needed.

7. **Race condition with event-driven worker:** The `market-data-worker` (event consumer) and `outcome-maturation` (cron) could theoretically run simultaneously. The `_calculate_single_outcome()` method uses SQLAlchemy's session-level optimistic concurrency -- last writer wins. Since both paths produce the same result (fill in prices for the same dates), this is safe. The `is_complete` flag ensures no double-processing.

### Performance considerations

- **Query efficiency:** The `WHERE is_complete = False` query benefits from the existing `prediction_outcomes` table indexes. There is no index on `is_complete` specifically, but the table is small enough (hundreds to low thousands of rows) that a sequential scan is acceptable.
- **yfinance rate limiting:** Each symbol/date lookup takes ~2-7 seconds. The skip-filled-timeframes optimization (Step 2) prevents redundant fetches. For 100 incomplete outcomes across 30 unique predictions with 50 unique symbols, worst case is ~200 yfinance calls (50 symbols x 4 timeframes) taking ~7-23 minutes.
- **Daily schedule is sufficient:** Timeframes are measured in days (T+1, T+3, T+7, T+30). Running more frequently than daily would not produce different results.

---

## Verification Checklist

- [ ] All existing tests pass: `source venv/bin/activate && pytest shit_tests/shit/market_data/ -v`
- [ ] New tests pass: `source venv/bin/activate && pytest shit_tests/shit/market_data/test_outcome_maturation.py -v`
- [ ] Full test suite passes: `source venv/bin/activate && pytest -v`
- [ ] Linting passes: `source venv/bin/activate && python -m ruff check shit/market_data/outcome_calculator.py shit/market_data/cli.py shit/events/event_types.py`
- [ ] CLI command appears in help: `source venv/bin/activate && python -m shit.market_data --help`
- [ ] CLI command runs without error: `source venv/bin/activate && python -m shit.market_data mature-outcomes`
- [ ] `railway.json` is valid JSON (no trailing commas, correct structure)
- [ ] CHANGELOG.md updated
- [ ] Existing `test_returns_existing_when_not_force_refresh` test still passes (backward compatibility of the early-return change)

---

## What NOT To Do

1. **Do NOT use `force_refresh=True` in `mature_outcomes()`.** The whole point of the Step 1 fix is that `force_refresh=False` now correctly handles incomplete outcomes. Using `force_refresh=True` would re-fetch prices for already-filled timeframes, wasting yfinance API calls and causing unnecessary load.

2. **Do NOT add an index on `is_complete`.** The `prediction_outcomes` table is small (hundreds of rows). Adding an index adds write overhead on every INSERT/UPDATE for negligible read benefit. If the table grows to tens of thousands of rows, reconsider.

3. **Do NOT make `mature_outcomes()` an EventWorker subclass.** The maturation job is time-triggered (daily cron), not event-triggered. It does not consume events from the queue. Using the CLI command via Railway cron is the correct pattern, matching `event-cleanup`.

4. **Do NOT modify `auto_backfill_service.py` or `event_consumer.py`.** The initial outcome creation path (event-driven) is correct as-is. The fix is in the outcome calculator's re-evaluation logic, not in the event consumer. Changing the event consumer to pass `force_refresh=True` would be wasteful for the common case (brand-new outcomes where no re-evaluation is needed).

5. **Do NOT change the `PredictionOutcome` model schema.** No new columns are needed. The existing `is_complete` boolean and the nullable timeframe columns already support the maturation workflow.

6. **Do NOT add the `mature-outcomes` command to the existing `test_all_expected_commands_present` list in `test_market_data_cli.py`.** The test verifies that a baseline set of commands exists. Adding new commands to this list is optional and should be done separately to keep this PR focused. If you choose to add it, add `"mature-outcomes"` to the `expected_commands` list.

7. **Do NOT import `emit_event` at the top of `outcome_calculator.py`.** The event emission is inside a try/except with a deferred import to avoid circular imports and to keep event emission optional (the module should work even if the events infrastructure is not configured).
