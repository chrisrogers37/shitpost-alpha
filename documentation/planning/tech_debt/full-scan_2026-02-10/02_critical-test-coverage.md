# Plan 02: Critical Test Coverage

**Status**: ✅ COMPLETE
**Started**: 2026-02-10
**Completed**: 2026-02-10

**PR Title**: `test: add test coverage for outcome_calculator, market_data client, and sync_session`
**Risk Level**: Low (test-only changes, no production code modified)
**Effort**: 2-3 days
**Findings Addressed**: #4, #5, #6

---

## Context

Three production-critical modules have **zero test coverage**. These modules handle the core data pipeline — fetching market prices, calculating prediction outcomes, and managing database sessions for all synchronous operations. A bug in any of these would silently corrupt the dashboard.

---

## Finding #4: Zero Coverage on `outcome_calculator.py`

### Location

`shit/market_data/outcome_calculator.py` (full file, ~200+ lines)

### Why This Matters

The `OutcomeCalculator` is responsible for:
- Looking up predictions and their associated assets
- Fetching actual market prices at T+1, T+3, T+7, T+30
- Calculating returns and determining if predictions were correct
- Writing `PredictionOutcome` records to the database

If this code has a bug, the entire dashboard shows wrong accuracy numbers.

### Required Tests

Create `shit_tests/market_data/test_outcome_calculator.py`:

```python
"""Tests for prediction outcome calculator."""

import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from shit.market_data.outcome_calculator import OutcomeCalculator
from shit.market_data.models import PredictionOutcome, MarketPrice


@pytest.fixture
def mock_session():
    """Create a mock SQLAlchemy session."""
    session = MagicMock(spec=Session)
    return session


@pytest.fixture
def calculator(mock_session):
    """Create OutcomeCalculator with mocked session."""
    calc = OutcomeCalculator(session=mock_session)
    calc.session = mock_session
    calc.market_client = MagicMock()
    return calc


class TestOutcomeCalculatorInit:
    """Test OutcomeCalculator initialization."""

    def test_init_with_session(self, mock_session):
        calc = OutcomeCalculator(session=mock_session)
        assert calc.session == mock_session
        assert calc._own_session is False

    def test_init_without_session(self):
        calc = OutcomeCalculator()
        assert calc.session is None
        assert calc._own_session is True

    def test_context_manager_with_external_session(self, mock_session):
        calc = OutcomeCalculator(session=mock_session)
        with calc as c:
            assert c.session == mock_session


class TestCalculateOutcome:
    """Test outcome calculation for predictions."""

    def test_missing_prediction_returns_empty(self, calculator, mock_session):
        """Prediction not found should return empty list."""
        mock_session.query.return_value.filter.return_value.first.return_value = None
        result = calculator.calculate_outcome_for_prediction(999)
        assert result == []

    def test_bypassed_prediction_returns_empty(self, calculator, mock_session):
        """Bypassed predictions should be skipped."""
        mock_pred = MagicMock()
        mock_pred.analysis_status = "bypassed"
        mock_session.query.return_value.filter.return_value.first.return_value = mock_pred
        result = calculator.calculate_outcome_for_prediction(1)
        assert result == []

    def test_prediction_with_no_assets_returns_empty(self, calculator, mock_session):
        """Prediction with no assets should return empty list."""
        mock_pred = MagicMock()
        mock_pred.analysis_status = "completed"
        mock_pred.assets = None
        mock_session.query.return_value.filter.return_value.first.return_value = mock_pred
        result = calculator.calculate_outcome_for_prediction(1)
        assert result == []

    def test_bullish_prediction_correct_when_price_rises(self, calculator, mock_session):
        """A bullish prediction should be marked correct when price goes up."""
        mock_pred = MagicMock()
        mock_pred.analysis_status = "completed"
        mock_pred.assets = ["AAPL"]
        mock_pred.market_impact = {"AAPL": "bullish"}
        mock_pred.confidence = 0.8
        mock_pred.created_at = date(2026, 1, 1)

        mock_session.query.return_value.filter.return_value.first.return_value = mock_pred
        mock_session.query.return_value.filter.return_value.all.return_value = []

        # Mock market client to return rising prices
        calculator.market_client.get_price_at_date = MagicMock(
            side_effect=lambda symbol, d: MagicMock(close=100 + (d - date(2026, 1, 1)).days)
        )

        # Test should verify correct_t7 is True for bullish + rising price
        # (Implementation details depend on actual calculate_outcome_for_prediction logic)

    def test_bearish_prediction_correct_when_price_falls(self, calculator, mock_session):
        """A bearish prediction should be marked correct when price drops."""
        # Similar structure to bullish test but with falling prices
        pass  # TODO: Implement based on actual method signature

    def test_outcome_already_exists_skips_recalculation(self, calculator, mock_session):
        """Existing outcomes should not be recalculated unless force_refresh."""
        mock_pred = MagicMock()
        mock_pred.analysis_status = "completed"
        mock_pred.assets = ["AAPL"]
        existing_outcome = MagicMock(spec=PredictionOutcome)
        mock_session.query.return_value.filter.return_value.first.return_value = mock_pred
        mock_session.query.return_value.filter.return_value.all.return_value = [existing_outcome]

        # Should skip when not force_refresh (depends on implementation)


class TestReturnCalculation:
    """Test return percentage calculations."""

    def test_positive_return_calculated_correctly(self):
        """Return should be (price_later - price_at_prediction) / price_at_prediction."""
        # price_at_prediction = 100, price_t7 = 110
        # expected return = 0.10 (10%)
        pass  # TODO: Test the specific return calculation method

    def test_zero_price_at_prediction_handled(self):
        """Division by zero should be handled when price_at_prediction is 0."""
        pass  # TODO: Edge case test

    def test_pnl_calculation_for_bullish(self):
        """P&L for bullish = return * confidence."""
        pass  # TODO: Test P&L formula

    def test_pnl_calculation_for_bearish(self):
        """P&L for bearish = -return * confidence (profit when price falls)."""
        pass  # TODO: Test P&L formula for bearish
```

**Minimum test count**: 10-15 tests covering init, calculation, edge cases, and error handling.

---

## Finding #5: Zero Coverage on `market_data/client.py`

### Location

`shit/market_data/client.py` (full file, ~200+ lines)

### Why This Matters

The `MarketDataClient` fetches real stock prices via `yfinance` and stores them in the `market_prices` table. It's the data foundation for all outcome calculations and dashboard price charts.

### Required Tests

Create `shit_tests/market_data/test_client.py`:

```python
"""Tests for market data client."""

import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch, PropertyMock
from sqlalchemy.orm import Session

from shit.market_data.client import MarketDataClient
from shit.market_data.models import MarketPrice


@pytest.fixture
def mock_session():
    session = MagicMock(spec=Session)
    return session


@pytest.fixture
def client(mock_session):
    c = MarketDataClient(session=mock_session)
    c.session = mock_session
    return c


class TestMarketDataClientInit:
    def test_init_with_session(self, mock_session):
        client = MarketDataClient(session=mock_session)
        assert client.session == mock_session
        assert client._own_session is False

    def test_init_without_session(self):
        client = MarketDataClient()
        assert client.session is None
        assert client._own_session is True


class TestFetchPriceHistory:
    def test_returns_existing_prices_when_cached(self, client, mock_session):
        """Should return cached prices instead of re-fetching."""
        existing = [MagicMock(spec=MarketPrice)]
        mock_session.query.return_value.filter.return_value.all.return_value = existing

        result = client.fetch_price_history("AAPL", date(2026, 1, 1))
        assert len(result) > 0
        # yfinance should NOT have been called

    @patch("shit.market_data.client.yf")
    def test_fetches_from_yfinance_when_no_cache(self, mock_yf, client, mock_session):
        """Should call yfinance when no cached data exists."""
        mock_session.query.return_value.filter.return_value.all.return_value = []

        mock_ticker = MagicMock()
        mock_yf.Ticker.return_value = mock_ticker
        mock_ticker.history.return_value = MagicMock()  # Empty DataFrame-like

        client.fetch_price_history("AAPL", date(2026, 1, 1), force_refresh=True)
        # Verify yfinance was called

    def test_force_refresh_bypasses_cache(self, client, mock_session):
        """force_refresh=True should skip the cache check."""
        pass  # TODO

    def test_end_date_defaults_to_today(self, client):
        """When end_date is None, should default to date.today()."""
        pass  # TODO

    def test_invalid_symbol_handled_gracefully(self, client, mock_session):
        """Invalid ticker symbols should not crash."""
        pass  # TODO


class TestGetExistingPrices:
    def test_queries_correct_date_range(self, client, mock_session):
        """Should filter by symbol and date range."""
        client._get_existing_prices("AAPL", date(2026, 1, 1), date(2026, 1, 31))
        # Verify the query was called with correct filters

    def test_empty_result_returns_empty_list(self, client, mock_session):
        mock_session.query.return_value.filter.return_value.all.return_value = []
        result = client._get_existing_prices("AAPL", date(2026, 1, 1), date(2026, 1, 31))
        assert result == []
```

**Minimum test count**: 8-12 tests.

---

## Finding #6: Zero Coverage on `sync_session.py`

### Location

`shit/db/sync_session.py` (72 lines)

### Why This Matters

`get_session()` is imported by:
- `notifications/db.py` (all subscription queries)
- `shit/market_data/cli.py`
- `shit/market_data/client.py`
- `shit/market_data/outcome_calculator.py`

If the session context manager has a bug (e.g., doesn't roll back on error, doesn't close properly), every consumer silently leaks connections or corrupts data.

### Required Tests

Create `shit_tests/db/test_sync_session.py`:

```python
"""Tests for synchronous session management."""

import pytest
from unittest.mock import patch, MagicMock

from shit.db.sync_session import get_session, SessionLocal


class TestGetSession:
    def test_yields_session(self):
        """get_session() should yield a valid session object."""
        with patch.object(SessionLocal, '__call__', return_value=MagicMock()) as mock:
            with get_session() as session:
                assert session is not None

    def test_commits_on_success(self):
        """Session should be committed when no exception occurs."""
        mock_session = MagicMock()
        with patch.object(SessionLocal, '__call__', return_value=mock_session):
            with get_session() as session:
                pass  # No error
            mock_session.commit.assert_called_once()
            mock_session.rollback.assert_not_called()

    def test_rolls_back_on_exception(self):
        """Session should be rolled back when an exception occurs."""
        mock_session = MagicMock()
        with patch.object(SessionLocal, '__call__', return_value=mock_session):
            with pytest.raises(ValueError):
                with get_session() as session:
                    raise ValueError("test error")
            mock_session.rollback.assert_called_once()
            mock_session.commit.assert_not_called()

    def test_closes_session_on_success(self):
        """Session should always be closed, even on success."""
        mock_session = MagicMock()
        with patch.object(SessionLocal, '__call__', return_value=mock_session):
            with get_session() as session:
                pass
            mock_session.close.assert_called_once()

    def test_closes_session_on_exception(self):
        """Session should always be closed, even on exception."""
        mock_session = MagicMock()
        with patch.object(SessionLocal, '__call__', return_value=mock_session):
            with pytest.raises(ValueError):
                with get_session() as session:
                    raise ValueError("test error")
            mock_session.close.assert_called_once()


class TestCreateTables:
    @patch("shit.db.sync_session.engine")
    def test_creates_all_tables(self, mock_engine):
        """create_tables() should call Base.metadata.create_all."""
        from shit.db.sync_session import create_tables
        with patch("shit.db.data_models.Base") as mock_base:
            create_tables()
            mock_base.metadata.create_all.assert_called_once_with(mock_engine)
```

**Minimum test count**: 6-8 tests.

---

## File Structure

```
shit_tests/shit/
├── market_data/                              # EXISTS (has test_market_data_cli.py)
│   ├── test_outcome_calculator.py            # NEW (~20 tests)
│   ├── test_client.py                        # NEW (~15 tests)
│   └── test_models.py                        # NEW (~12 tests, PredictionOutcome model)
└── db/                                       # EXISTS (has other db test files)
    └── test_sync_session.py                  # NEW (~8 tests)
```

Test directories already exist with other test files — no `__init__.py` needed (pytest discovers without them).

---

## Expanded Scope (Challenge Round Additions)

The original plan only covered ~40% of the public API. The following methods are now in scope:

**OutcomeCalculator** (Finding #4):
- `calculate_outcome_for_prediction()` (original)
- `calculate_outcomes_for_all_predictions()` (added)
- `get_accuracy_stats()` (added)
- `_extract_sentiment()` (added — critical helper)
- `_calculate_single_outcome()` (added — core logic)

**MarketDataClient** (Finding #5):
- `fetch_price_history()` (original)
- `get_price_on_date()` (added — used by outcome calculator)
- `get_latest_price()` (added)
- `update_prices_for_symbols()` (added)
- `get_price_stats()` (added)
- `_get_existing_prices()` (original)

**PredictionOutcome model** (new scope):
- `calculate_return()` — core financial math
- `is_correct()` — prediction accuracy logic
- `calculate_pnl()` — P&L simulation

---

## Verification Checklist

- [ ] `pytest shit_tests/shit/market_data/test_outcome_calculator.py -v` — all tests pass
- [ ] `pytest shit_tests/shit/market_data/test_client.py -v` — all tests pass
- [ ] `pytest shit_tests/shit/market_data/test_models.py -v` — all tests pass
- [ ] `pytest shit_tests/shit/db/test_sync_session.py -v` — all tests pass
- [ ] `pytest shit_tests/ -v` — full suite still passes (no regressions)
- [ ] Coverage for `outcome_calculator.py` > 70%: `pytest --cov=shit.market_data.outcome_calculator shit_tests/shit/market_data/test_outcome_calculator.py`
- [ ] Coverage for `client.py` > 60%: `pytest --cov=shit.market_data.client shit_tests/shit/market_data/test_client.py`
- [ ] Coverage for `sync_session.py` > 80%: `pytest --cov=shit.db.sync_session shit_tests/shit/db/test_sync_session.py`

---

## What NOT To Do

1. **Do NOT test against the real database.** All tests must use mocked sessions. Integration tests are a separate concern.
2. **Do NOT modify production code in this PR.** This is a test-only PR. If you discover bugs while writing tests, document them but fix them in a separate PR.
3. **Do NOT mock at too high a level.** Mock the session and external APIs (yfinance), but let the actual business logic execute.
4. **Do NOT write tests that depend on test execution order.** Each test must be independent.
5. **Do NOT skip the `pass # TODO` tests.** The placeholders above are scaffolding — every `pass # TODO` must be replaced with a real implementation based on reading the actual source code.
