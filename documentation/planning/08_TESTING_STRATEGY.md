# Testing Strategy Specification

## Overview

This document defines the testing strategy for the shitty_ui dashboard. The goal is to achieve 80%+ code coverage with a mix of unit tests, integration tests, and visual regression tests.

**Priority**: P0 (Must Have)
**Ongoing**: Tests should be added with every feature

---

## Current Test Coverage

### Existing Tests (49 total)

```
shit_tests/shitty_ui/
├── __init__.py
├── conftest.py         # Mock configuration
├── test_data.py        # 28 data layer tests
└── test_layout.py      # 21 layout component tests
```

### Coverage Gaps

| Area | Current | Target | Gap |
|------|---------|--------|-----|
| Data layer functions | ~70% | 90% | Edge cases, error paths |
| Layout components | ~50% | 80% | Callback logic, conditional rendering |
| Callback interactions | ~5% | 60% | Callback chains, state management |
| Integration | 0% | 30% | End-to-end flows |
| Error handling | ~20% | 80% | All error paths |

---

## Test Infrastructure

### conftest.py

The test conftest at `shit_tests/shitty_ui/conftest.py` sets up mocks before any imports:

```python
"""
Conftest for shitty_ui tests.
Provides fixtures and mocks for dashboard testing.
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Mock the settings import before any shitty_ui modules are loaded
mock_settings = MagicMock()
mock_settings.DATABASE_URL = "sqlite:///test.db"
sys.modules['shit.config.shitpost_settings'] = MagicMock()
sys.modules['shit.config.shitpost_settings'].settings = mock_settings

# Set DATABASE_URL environment variable as fallback
os.environ['DATABASE_URL'] = 'sqlite:///test.db'
```

**Why this exists**: The data layer imports `shit.config.shitpost_settings` which requires the full project configuration. We mock this to isolate tests from the database.

### Running Tests

```bash
# From the test directory
cd shit_tests/shitty_ui
python3 -m pytest . -v

# With coverage
python3 -m pytest . -v --cov=../../shitty_ui --cov-report=html

# Specific test class
python3 -m pytest test_data.py::TestGetPerformanceMetrics -v

# Specific test
python3 -m pytest test_data.py::TestGetPerformanceMetrics::test_calculates_accuracy_correctly -v
```

---

## Test Patterns

### Pattern 1: Mocking Database Queries

All data layer tests should mock `execute_query` to avoid database dependencies:

```python
from unittest.mock import patch

class TestMyFunction:
    @patch('data.execute_query')
    def test_normal_case(self, mock_execute):
        """Test normal case with valid data."""
        from data import my_function

        # Set up mock return value matching query columns
        mock_execute.return_value = (
            [
                (value1, value2, value3),  # Row 1
                (value4, value5, value6),  # Row 2
            ],
            ['column1', 'column2', 'column3']  # Column names
        )

        result = my_function()

        # Assert on result
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2

        # Verify query was called with expected params
        mock_execute.assert_called_once()
```

### Pattern 2: Testing Error Handling

Every function that catches exceptions should be tested for error behavior:

```python
class TestMyFunction:
    @patch('data.execute_query')
    def test_returns_default_on_error(self, mock_execute):
        """Test that function returns safe default on database error."""
        from data import my_function

        mock_execute.side_effect = Exception("Connection refused")

        result = my_function()

        # Should return default, not raise
        assert result == expected_default
```

### Pattern 3: Testing Layout Components

Layout tests verify that components are created without errors and have expected structure:

```python
class TestMyComponent:
    def test_returns_expected_type(self):
        """Test that component returns correct Dash type."""
        from layout import my_component
        from dash import html
        import dash_bootstrap_components as dbc

        component = my_component(param="value")

        assert isinstance(component, dbc.Card)  # Or html.Div, etc.

    def test_handles_edge_case(self):
        """Test with unusual but valid input."""
        from layout import my_component

        component = my_component(param="")
        assert component is not None

    def test_handles_none_values(self):
        """Test with None values."""
        from layout import my_component

        component = my_component(param=None)
        assert component is not None
```

### Pattern 4: Testing Callbacks

Callbacks are harder to test because they're registered on the app. Use this pattern:

```python
class TestCallbacks:
    @patch('layout.get_performance_metrics')
    @patch('layout.get_prediction_stats')
    @patch('layout.get_accuracy_by_confidence')
    @patch('layout.get_accuracy_by_asset')
    @patch('layout.get_recent_signals')
    @patch('layout.get_active_assets_from_db')
    def test_update_dashboard_callback(
        self, mock_assets, mock_signals, mock_asset_acc,
        mock_conf_acc, mock_perf, mock_stats
    ):
        """Test the main dashboard update callback."""
        from layout import create_app, register_callbacks

        # Set up mocks
        mock_stats.return_value = {
            "total_posts": 100,
            "analyzed_posts": 80,
            "completed_analyses": 60,
            "bypassed_posts": 20,
            "avg_confidence": 0.7,
            "high_confidence_predictions": 40
        }
        mock_perf.return_value = {
            "total_outcomes": 50,
            "evaluated_predictions": 50,
            "correct_predictions": 30,
            "incorrect_predictions": 20,
            "accuracy_t7": 60.0,
            "avg_return_t7": 1.5,
            "total_pnl_t7": 1500.0,
            "avg_confidence": 0.7
        }
        mock_conf_acc.return_value = pd.DataFrame()
        mock_asset_acc.return_value = pd.DataFrame()
        mock_signals.return_value = pd.DataFrame()
        mock_assets.return_value = ['AAPL', 'GOOGL']

        app = create_app()
        register_callbacks(app)

        # The callback is registered - verify it exists
        assert 'performance-metrics.children' in str(app.callback_map)
```

### Pattern 5: Testing with Dash Test Client (Integration)

For integration testing, use the Dash testing framework:

```python
import pytest
from dash.testing.application_runners import import_app

# NOTE: This requires selenium and a browser driver
# Only use for critical integration tests

@pytest.mark.integration
class TestDashboardIntegration:
    def test_dashboard_loads(self, dash_duo):
        """Test that dashboard loads without errors."""
        app = import_app("shitty_ui.app")
        dash_duo.start_server(app)

        # Wait for page to load
        dash_duo.wait_for_element("#performance-metrics", timeout=10)

        # Verify no errors
        assert dash_duo.get_logs() == []
```

---

## Test Coverage Plan

### Data Layer (data.py) - Target: 90%

#### Existing Coverage

| Function | Tests | Status |
|----------|-------|--------|
| `execute_query` | 0 | Tested indirectly |
| `load_recent_posts` | 0 | Needs tests |
| `load_filtered_posts` | 3 | Needs edge cases |
| `get_available_assets` | 0 | Static, low priority |
| `get_prediction_stats` | 3 | Complete |
| `get_recent_signals` | 3 | Complete |
| `get_performance_metrics` | 4 | Complete |
| `get_accuracy_by_confidence` | 3 | Complete |
| `get_accuracy_by_asset` | 2 | Needs edge cases |
| `get_similar_predictions` | 3 | Complete |
| `get_predictions_with_outcomes` | 2 | Complete |
| `get_sentiment_distribution` | 2 | Complete |
| `get_active_assets_from_db` | 3 | Complete |

#### Tests to Add

```python
# test_data.py additions

class TestLoadRecentPosts:
    """Tests for load_recent_posts function."""

    @patch('data.execute_query')
    def test_returns_dataframe(self, mock_execute):
        from data import load_recent_posts
        mock_execute.return_value = (
            [(datetime.now(), 'text', 'id1', 5, 3, 10, None, None, None, None, None, None)],
            ['timestamp', 'text', 'shitpost_id', 'replies_count', 'reblogs_count',
             'favourites_count', 'assets', 'market_impact', 'thesis', 'confidence',
             'analysis_status', 'analysis_comment']
        )
        result = load_recent_posts(limit=10)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1

    @patch('data.execute_query')
    def test_respects_limit(self, mock_execute):
        from data import load_recent_posts
        mock_execute.return_value = ([], [])
        load_recent_posts(limit=25)
        call_args = mock_execute.call_args[0]
        assert call_args[1]['limit'] == 25


class TestExecuteQuery:
    """Tests for execute_query function."""

    @patch('data.SessionLocal')
    def test_executes_and_returns(self, mock_session_class):
        from data import execute_query
        from sqlalchemy import text

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [('a', 1)]
        mock_result.keys.return_value = ['col1', 'col2']
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.execute.return_value = mock_result
        mock_session_class.return_value = mock_session

        rows, cols = execute_query(text("SELECT 1"), {})
        assert rows == [('a', 1)]

    @patch('data.SessionLocal')
    def test_raises_on_error(self, mock_session_class):
        from data import execute_query
        from sqlalchemy import text

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.execute.side_effect = Exception("Connection error")
        mock_session_class.return_value = mock_session

        with pytest.raises(Exception, match="Connection error"):
            execute_query(text("SELECT 1"), {})


class TestAccuracyByAssetEdgeCases:
    """Edge case tests for get_accuracy_by_asset."""

    @patch('data.execute_query')
    def test_handles_single_asset(self, mock_execute):
        from data import get_accuracy_by_asset
        mock_execute.return_value = (
            [('AAPL', 5, 3, 2, 1.5, 500.0)],
            ['symbol', 'total_predictions', 'correct', 'incorrect', 'avg_return', 'total_pnl']
        )
        result = get_accuracy_by_asset(limit=1)
        assert len(result) == 1
        assert result['accuracy'].iloc[0] == 60.0

    @patch('data.execute_query')
    def test_handles_zero_correct(self, mock_execute):
        from data import get_accuracy_by_asset
        mock_execute.return_value = (
            [('AAPL', 5, 0, 5, -2.0, -1000.0)],
            ['symbol', 'total_predictions', 'correct', 'incorrect', 'avg_return', 'total_pnl']
        )
        result = get_accuracy_by_asset()
        assert result['accuracy'].iloc[0] == 0.0
```

### Layout Layer (layout.py) - Target: 80%

#### Tests to Add

```python
# test_layout.py additions

class TestCreateSignalCardEdgeCases:
    """Additional edge cases for signal card."""

    def test_handles_empty_market_impact(self):
        """Test with empty market_impact dict."""
        from layout import create_signal_card
        row = {
            'timestamp': datetime.now(),
            'text': 'Test',
            'confidence': 0.5,
            'assets': [],
            'market_impact': {},
            'return_t7': None,
            'correct_t7': None
        }
        card = create_signal_card(row)
        assert card is not None

    def test_handles_missing_keys(self):
        """Test with minimal row data."""
        from layout import create_signal_card
        row = {
            'timestamp': datetime.now(),
            'text': '',
            'confidence': 0,
            'assets': [],
            'market_impact': None,
            'return_t7': None,
            'correct_t7': None
        }
        card = create_signal_card(row)
        assert card is not None

    def test_handles_zero_return(self):
        """Test with zero return."""
        from layout import create_signal_card
        row = {
            'timestamp': datetime.now(),
            'text': 'Flat market',
            'confidence': 0.5,
            'assets': ['SPY'],
            'market_impact': {'SPY': 'neutral'},
            'return_t7': 0.0,
            'correct_t7': True
        }
        card = create_signal_card(row)
        assert card is not None


class TestMetricCardEdgeCases:
    """Edge cases for metric card."""

    def test_handles_negative_value(self):
        from layout import create_metric_card
        card = create_metric_card("Loss", "-$500", "Bad day", "chart-line", "#ef4444")
        assert card is not None

    def test_handles_zero_value(self):
        from layout import create_metric_card
        card = create_metric_card("Nothing", "0", "", "minus")
        assert card is not None

    def test_handles_large_value(self):
        from layout import create_metric_card
        card = create_metric_card("Big number", "$1,234,567", "Wow", "dollar-sign")
        assert card is not None

    def test_handles_empty_subtitle(self):
        from layout import create_metric_card
        card = create_metric_card("Title", "Value")
        assert card is not None
```

---

## Test Categories

### Unit Tests (must run fast, no external deps)

Every function gets:
1. **Happy path test** - Normal expected input
2. **Edge case test** - Empty data, None values, zero values
3. **Error test** - Database errors, malformed data
4. **Parameter test** - Verify parameters are passed correctly

### Integration Tests (slower, may need mocks)

Critical flows to test:
1. **Dashboard loads** - All components render
2. **Asset selection** - Selecting asset updates drilldown
3. **Table toggle** - Expand/collapse works
4. **Filter changes** - Filters affect displayed data

### Naming Conventions

```
test_<function_name>                      # Happy path
test_<function_name>_handles_<edge_case>  # Edge case
test_<function_name>_returns_default_on_<error>  # Error case
test_<function_name>_respects_<parameter>  # Parameter test
```

---

## CI Pipeline Setup

### GitHub Actions Configuration

Create `.github/workflows/test-dashboard.yml`:

```yaml
name: Dashboard Tests

on:
  push:
    paths:
      - 'shitty_ui/**'
      - 'shit_tests/shitty_ui/**'
  pull_request:
    paths:
      - 'shitty_ui/**'
      - 'shit_tests/shitty_ui/**'

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install pytest pytest-cov pandas dash dash-bootstrap-components \
                     plotly sqlalchemy pydantic pydantic-settings python-dotenv

      - name: Run tests
        run: |
          cd shit_tests/shitty_ui
          python -m pytest . -v --cov=../../shitty_ui --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: shit_tests/shitty_ui/coverage.xml
```

---

## Checklist

- [ ] Data Layer Test Gaps
  - [ ] Add `TestLoadRecentPosts` (2 tests)
  - [ ] Add `TestExecuteQuery` (2 tests)
  - [ ] Add edge case tests for `get_accuracy_by_asset` (2 tests)
  - [ ] Add tests for each new function from 07_DATA_LAYER_EXPANSION.md
  - [ ] Verify error handling returns safe defaults

- [ ] Layout Test Gaps
  - [ ] Add `TestCreateSignalCardEdgeCases` (3+ tests)
  - [ ] Add `TestMetricCardEdgeCases` (4 tests)
  - [ ] Add callback chain tests
  - [ ] Add error boundary tests

- [ ] New Feature Tests
  - [ ] Write tests alongside every new feature
  - [ ] Each new data function: 3+ tests minimum
  - [ ] Each new layout component: 2+ tests minimum
  - [ ] Each new callback: 1+ test minimum

- [ ] CI Pipeline
  - [ ] Create GitHub Actions workflow
  - [ ] Configure coverage reporting
  - [ ] Set coverage threshold (80%)

---

## Definition of Done (Testing)

For any new feature to be considered complete:
- [ ] Unit tests pass
- [ ] Test coverage for new code > 80%
- [ ] Edge cases documented and tested
- [ ] Error paths tested
- [ ] No existing tests broken
- [ ] Tests run in < 5 seconds total
