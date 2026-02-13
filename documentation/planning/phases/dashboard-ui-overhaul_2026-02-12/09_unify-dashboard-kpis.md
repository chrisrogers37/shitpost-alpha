# Phase 09: Unify Dashboard KPIs with Performance Data

## Header

| Field | Value |
|---|---|
| **PR Title** | `fix(ui): unify dashboard KPIs with performance data source to show real metrics` |
| **Risk Level** | Low |
| **Estimated Effort** | Small-Medium (half day) |
| **Files Modified** | `shitty_ui/data.py`, `shitty_ui/pages/dashboard.py`, `shit_tests/shitty_ui/test_data.py`, `CHANGELOG.md` |
| **Files Created** | None |
| **Files Deleted** | None |

---

## Context: Why the Dashboard Looks Broken

The main dashboard (`/`) is the landing page. It has a row of four KPI cards at the top that are supposed to summarize system performance. Currently, these cards display values like `0.0%`, `0`, `0.0%`, and `N/A` -- making the dashboard look dead, even though the system has been running in production and has real prediction outcomes.

### Current State

The dashboard callback `update_dashboard()` at `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard.py` line 692 calls `get_performance_metrics(days=days)`. When `days=7` (the 7D period button), this function queries `prediction_outcomes WHERE prediction_date >= (now - 7 days)`. The problem is twofold:

1. **Prediction outcomes take 7+ days to mature.** The `prediction_date` column records when the prediction was made, and `correct_t7` is only populated after 7 trading days have elapsed. A 7-day lookback window therefore catches only predictions that were made 0-7 days ago -- but those predictions have not yet been evaluated (their `correct_t7` is NULL). The `COUNT(CASE WHEN correct_t7 IS NOT NULL THEN 1 END)` at line 403 returns 0, producing `accuracy_t7 = 0.0` and `total_pnl_t7 = 0.0`.

2. **The KPIs do not match what users expect.** Even at 90D, the current cards show "Overall Accuracy," "Signals This Week," "High-Conf Win Rate," and "Best Asset." These are four different data sources combined in a way that does not tell a cohesive story. Meanwhile, the Performance page (`/performance`) uses `get_backtest_simulation()` to show clear, correct metrics: trade count, win rate, total P&L, and final portfolio value. Users see discordant numbers between the two pages.

### Desired State

The four KPI cards on the main dashboard should show:

| Card | Metric | Data Source |
|---|---|---|
| Total Signals | Count of evaluated prediction outcomes in the period | `prediction_outcomes` where `correct_t7 IS NOT NULL` |
| Accuracy | Percentage of correct predictions at t7 | `correct_t7 = true / total evaluated` |
| Avg 7-Day Return | Mean return across all evaluated predictions | `AVG(return_t7)` |
| Total P&L | Sum of P&L across all evaluated predictions | `SUM(pnl_t7)` |

These metrics are already computed by `get_performance_metrics()` but the function needs to work correctly at all time periods. Additionally, the dashboard callback must be updated to use the correct keys from this function and to display the four desired cards.

### Why Not Reuse `get_backtest_simulation()`?

`get_backtest_simulation()` filters by `min_confidence >= 0.75`, which excludes lower-confidence predictions. The dashboard KPIs should show system-wide performance across all confidence levels, giving users the full picture. The existing `get_performance_metrics()` already queries all confidence levels -- it just needs the dashboard to use its output correctly and to present the right four KPI cards.

---

## Dependencies

| Dependency | Status | Required? |
|---|---|---|
| Phase 04 (Fix Duplicate Signals) | Batch 2 | **Yes -- Phase 04 modifies `dashboard.py` and `data.py`** |
| Phases 01-03, 05-06 | Batch 1-2 | No (modify different functions or files) |
| `prediction_outcomes` table with data | Already populated in production | **Required** |

**Batch**: 3 (must wait for Phase 04 to complete since both modify `dashboard.py` lines 690-756 and `data.py`).

**Ordering note**: Phase 04 changes `get_active_signals()` and `create_hero_signal_card()`. Phase 09 changes the KPI metrics section (lines 690-756 of `dashboard.py`) and potentially `get_performance_metrics()` in `data.py`. The line numbers referenced in this plan assume Phase 04 has already been merged. If Phase 04 shifts line numbers in `dashboard.py`, adjust the line references below accordingly. The function names and structure remain the same regardless.

---

## Detailed Implementation Plan

### Step 1: Create `get_dashboard_kpis()` in `data.py`

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/data.py`

Rather than modifying `get_performance_metrics()` (which is also used by other callers and already works correctly for its purpose), create a new dedicated function that is specifically designed for the dashboard KPI cards. This function queries `prediction_outcomes` with a `correct_t7 IS NOT NULL` filter, ensuring only evaluated predictions are counted, and does not filter by confidence level.

**Insert location**: After `get_performance_metrics()` (after line 440), before `get_accuracy_by_confidence()` (which starts at line 443).

**Code to add**:

```python
@ttl_cache(ttl_seconds=300)  # Cache for 5 minutes
def get_dashboard_kpis(days: int = None) -> Dict[str, Any]:
    """
    Get the four key metrics for the main dashboard KPI cards.

    Returns only evaluated predictions (where correct_t7 is not NULL),
    which ensures metrics reflect real outcomes, not pending predictions.
    Matches the same data source used by the Performance page.

    Args:
        days: Number of days to look back (None = all time).
              Note: uses prediction_date, so a 7-day window returns
              predictions made 7 days ago that have since been evaluated.

    Returns:
        Dict with keys:
            total_signals: int - count of evaluated prediction-outcome rows
            accuracy_pct: float - percentage of correct_t7 = true
            avg_return_t7: float - mean 7-day return (percentage)
            total_pnl: float - sum of pnl_t7 (dollar amount)
    """
    date_filter = ""
    params: Dict[str, Any] = {}

    if days is not None:
        date_filter = "AND prediction_date >= :start_date"
        params["start_date"] = (datetime.now() - timedelta(days=days)).date()

    query = text(f"""
        SELECT
            COUNT(*) as total_signals,
            COUNT(CASE WHEN correct_t7 = true THEN 1 END) as correct_count,
            AVG(return_t7) as avg_return_t7,
            SUM(CASE WHEN pnl_t7 IS NOT NULL THEN pnl_t7 ELSE 0 END) as total_pnl
        FROM prediction_outcomes
        WHERE correct_t7 IS NOT NULL
        {date_filter}
    """)

    try:
        rows, columns = execute_query(query, params)
        if rows and rows[0]:
            row = rows[0]
            total = row[0] or 0
            correct = row[1] or 0
            accuracy = (correct / total * 100) if total > 0 else 0.0

            return {
                "total_signals": total,
                "accuracy_pct": round(accuracy, 1),
                "avg_return_t7": round(float(row[2]), 2) if row[2] else 0.0,
                "total_pnl": round(float(row[3]), 2) if row[3] else 0.0,
            }
    except Exception as e:
        logger.error(f"Error loading dashboard KPIs: {e}")

    return {
        "total_signals": 0,
        "accuracy_pct": 0.0,
        "avg_return_t7": 0.0,
        "total_pnl": 0.0,
    }
```

**Key design decisions**:
- The `WHERE correct_t7 IS NOT NULL` filter is the critical fix. This ensures only predictions with actual outcomes are counted. Predictions still in their 7-day evaluation window are excluded, preventing the zeros problem.
- No confidence filter. The backtest page filters by `min_confidence >= 0.75`, but the dashboard KPIs should reflect system-wide performance.
- Uses `prediction_date` for the date filter (same as `get_performance_metrics()`).
- Returns a flat dict with exactly the four values needed by the KPI cards.

### Step 2: Register `get_dashboard_kpis` in `clear_all_caches()`

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/data.py`

**Location**: `clear_all_caches()` function, lines 994-1006.

**BEFORE** (line 1006):

```python
    get_backtest_simulation.clear_cache()  # type: ignore
```

**AFTER** (add one line after line 1006):

```python
    get_backtest_simulation.clear_cache()  # type: ignore
    get_dashboard_kpis.clear_cache()  # type: ignore
```

### Step 3: Add `get_dashboard_kpis` to dashboard.py imports

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard.py`

**BEFORE** (lines 23-39, the import block from `data`):

```python
from data import (
    get_recent_signals,
    get_performance_metrics,
    get_accuracy_by_confidence,
    get_accuracy_by_asset,
    get_similar_predictions,
    get_predictions_with_outcomes,
    get_active_assets_from_db,
    load_recent_posts,
    get_active_signals,
    get_weekly_signal_count,
    get_high_confidence_metrics,
    get_best_performing_asset,
    get_accuracy_over_time,
    get_backtest_simulation,
    get_sentiment_accuracy,
)
```

**AFTER** (add `get_dashboard_kpis` and remove unused imports):

```python
from data import (
    get_recent_signals,
    get_performance_metrics,
    get_accuracy_by_confidence,
    get_accuracy_by_asset,
    get_similar_predictions,
    get_predictions_with_outcomes,
    get_active_assets_from_db,
    load_recent_posts,
    get_active_signals,
    get_weekly_signal_count,
    get_high_confidence_metrics,
    get_best_performing_asset,
    get_accuracy_over_time,
    get_backtest_simulation,
    get_sentiment_accuracy,
    get_dashboard_kpis,
)
```

**Note**: `get_performance_metrics`, `get_weekly_signal_count`, `get_high_confidence_metrics`, and `get_best_performing_asset` remain imported because they may be used by other parts of the dashboard or by the Performance page callback. Do NOT remove them even though the KPI section no longer calls them directly. The Performance page callback at line 1346 uses `get_backtest_simulation`, and other dashboard sections may reference them.

### Step 4: Rewrite the KPI Metrics Section in `update_dashboard()`

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard.py`

**Location**: The `update_dashboard()` callback, the "Performance Metrics" section starting at line 690.

**BEFORE** (lines 690-756):

```python
        # ===== Performance Metrics with error handling =====
        try:
            perf = get_performance_metrics(days=days)
            weekly_count = get_weekly_signal_count()
            hc_metrics = get_high_confidence_metrics(days=days)
            best_asset = get_best_performing_asset(days=days)

            # Create redesigned metrics row
            metrics_row = dbc.Row(
                [
                    dbc.Col(
                        create_metric_card(
                            "Overall Accuracy",
                            f"{perf['accuracy_t7']:.1f}%",
                            f"{perf['correct_predictions']}/{perf['evaluated_predictions']} correct",
                            "bullseye",
                            COLORS["success"]
                            if perf["accuracy_t7"] > 60
                            else COLORS["danger"],
                        ),
                        xs=6,
                        sm=6,
                        md=3,
                    ),
                    dbc.Col(
                        create_metric_card(
                            "Signals This Week",
                            f"{weekly_count}",
                            "completed predictions",
                            "signal",
                            COLORS["accent"],
                        ),
                        xs=6,
                        sm=6,
                        md=3,
                    ),
                    dbc.Col(
                        create_metric_card(
                            "High-Conf Win Rate",
                            f"{hc_metrics['win_rate']:.1f}%",
                            f"{hc_metrics['correct']}/{hc_metrics['total']} trades",
                            "trophy",
                            COLORS["success"]
                            if hc_metrics["win_rate"] > 60
                            else COLORS["danger"],
                        ),
                        xs=6,
                        sm=6,
                        md=3,
                    ),
                    dbc.Col(
                        create_metric_card(
                            "Best Asset",
                            f"{best_asset['symbol']}",
                            f"${best_asset['total_pnl']:,.0f} P&L",
                            "crown",
                            COLORS["success"]
                            if best_asset["total_pnl"] > 0
                            else COLORS["text_muted"],
                        ),
                        xs=6,
                        sm=6,
                        md=3,
                    ),
                ],
                className="g-2 g-md-3",
            )
        except Exception as e:
            errors.append(f"Performance metrics: {e}")
            print(f"Error loading performance metrics: {traceback.format_exc()}")
            metrics_row = create_error_card(
                "Unable to load performance metrics", str(e)
            )
```

**AFTER**:

```python
        # ===== Performance Metrics with error handling =====
        try:
            kpis = get_dashboard_kpis(days=days)

            # Create KPI metrics row
            metrics_row = dbc.Row(
                [
                    dbc.Col(
                        create_metric_card(
                            "Total Signals",
                            f"{kpis['total_signals']}",
                            "evaluated predictions",
                            "signal",
                            COLORS["accent"],
                        ),
                        xs=6,
                        sm=6,
                        md=3,
                    ),
                    dbc.Col(
                        create_metric_card(
                            "Accuracy",
                            f"{kpis['accuracy_pct']:.1f}%",
                            "correct at 7 days",
                            "bullseye",
                            COLORS["success"]
                            if kpis["accuracy_pct"] > 50
                            else COLORS["danger"],
                        ),
                        xs=6,
                        sm=6,
                        md=3,
                    ),
                    dbc.Col(
                        create_metric_card(
                            "Avg 7-Day Return",
                            f"{kpis['avg_return_t7']:+.2f}%",
                            "mean return per signal",
                            "chart-line",
                            COLORS["success"]
                            if kpis["avg_return_t7"] > 0
                            else COLORS["danger"],
                        ),
                        xs=6,
                        sm=6,
                        md=3,
                    ),
                    dbc.Col(
                        create_metric_card(
                            "Total P&L",
                            f"${kpis['total_pnl']:+,.0f}",
                            "simulated $1,000 trades",
                            "dollar-sign",
                            COLORS["success"]
                            if kpis["total_pnl"] > 0
                            else COLORS["danger"],
                        ),
                        xs=6,
                        sm=6,
                        md=3,
                    ),
                ],
                className="g-2 g-md-3",
            )
        except Exception as e:
            errors.append(f"Performance metrics: {e}")
            print(f"Error loading performance metrics: {traceback.format_exc()}")
            metrics_row = create_error_card(
                "Unable to load performance metrics", str(e)
            )
```

**Key changes**:
1. Replaced four separate data-fetch calls (`get_performance_metrics`, `get_weekly_signal_count`, `get_high_confidence_metrics`, `get_best_performing_asset`) with a single call to `get_dashboard_kpis(days=days)`. This reduces from 4 database queries to 1.
2. Changed the four KPI cards from (Overall Accuracy, Signals This Week, High-Conf Win Rate, Best Asset) to (Total Signals, Accuracy, Avg 7-Day Return, Total P&L).
3. The accuracy threshold for green/red coloring is changed from `> 60` to `> 50` (50% is the random baseline for directional predictions).
4. The P&L card uses `+` sign formatting and `$` prefix to make gains/losses immediately obvious.
5. The subtitle for Total P&L says "simulated $1,000 trades" to match the existing pnl_t7 calculation in the database (each prediction outcome's pnl_t7 is based on a $1,000 position).

---

## Test Plan

### New Tests for `get_dashboard_kpis`

**File**: `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_data.py`

**Insert location**: After the `TestGetPerformanceMetrics` class (after line 265), before `TestGetAccuracyByConfidence` (line 267).

```python
class TestGetDashboardKpis:
    """Tests for get_dashboard_kpis function."""

    @patch("data.execute_query")
    def test_returns_kpis_dict(self, mock_execute):
        """Test that function returns a dict with all four KPI values."""
        from data import get_dashboard_kpis

        mock_execute.return_value = (
            [(80, 48, 2.15, 1720.0)],
            ["total_signals", "correct_count", "avg_return_t7", "total_pnl"],
        )

        get_dashboard_kpis.clear_cache()
        result = get_dashboard_kpis()

        assert isinstance(result, dict)
        assert result["total_signals"] == 80
        assert result["accuracy_pct"] == 60.0  # 48/80 = 60%
        assert result["avg_return_t7"] == 2.15
        assert result["total_pnl"] == 1720.0

    @patch("data.execute_query")
    def test_accuracy_calculated_correctly(self, mock_execute):
        """Test that accuracy percentage is correct."""
        from data import get_dashboard_kpis

        mock_execute.return_value = (
            [(200, 130, 1.8, 3200.0)],
            ["total_signals", "correct_count", "avg_return_t7", "total_pnl"],
        )

        get_dashboard_kpis.clear_cache()
        result = get_dashboard_kpis()

        assert result["accuracy_pct"] == 65.0  # 130/200 = 65%

    @patch("data.execute_query")
    def test_handles_zero_signals(self, mock_execute):
        """Test that function handles zero evaluated predictions gracefully."""
        from data import get_dashboard_kpis

        mock_execute.return_value = (
            [(0, 0, None, 0.0)],
            ["total_signals", "correct_count", "avg_return_t7", "total_pnl"],
        )

        get_dashboard_kpis.clear_cache()
        result = get_dashboard_kpis()

        assert result["total_signals"] == 0
        assert result["accuracy_pct"] == 0.0
        assert result["avg_return_t7"] == 0.0
        assert result["total_pnl"] == 0.0

    @patch("data.execute_query")
    def test_returns_defaults_on_error(self, mock_execute):
        """Test that function returns default zeros on database error."""
        from data import get_dashboard_kpis

        mock_execute.side_effect = Exception("Database error")

        get_dashboard_kpis.clear_cache()
        result = get_dashboard_kpis()

        assert result["total_signals"] == 0
        assert result["accuracy_pct"] == 0.0
        assert result["avg_return_t7"] == 0.0
        assert result["total_pnl"] == 0.0

    @patch("data.execute_query")
    def test_passes_date_filter_when_days_specified(self, mock_execute):
        """Test that the days parameter creates a date filter in the query."""
        from data import get_dashboard_kpis

        mock_execute.return_value = (
            [(10, 6, 1.5, 600.0)],
            ["total_signals", "correct_count", "avg_return_t7", "total_pnl"],
        )

        get_dashboard_kpis.clear_cache()
        get_dashboard_kpis(days=30)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        params = call_args[1]
        assert "start_date" in params

    @patch("data.execute_query")
    def test_no_date_filter_when_days_is_none(self, mock_execute):
        """Test that no date filter is applied when days is None (all time)."""
        from data import get_dashboard_kpis

        mock_execute.return_value = (
            [(500, 300, 2.0, 15000.0)],
            ["total_signals", "correct_count", "avg_return_t7", "total_pnl"],
        )

        get_dashboard_kpis.clear_cache()
        get_dashboard_kpis(days=None)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        params = call_args[1]
        assert "start_date" not in params

    @patch("data.execute_query")
    def test_negative_pnl_returned_correctly(self, mock_execute):
        """Test that negative P&L values are returned without modification."""
        from data import get_dashboard_kpis

        mock_execute.return_value = (
            [(50, 20, -1.5, -750.0)],
            ["total_signals", "correct_count", "avg_return_t7", "total_pnl"],
        )

        get_dashboard_kpis.clear_cache()
        result = get_dashboard_kpis()

        assert result["total_pnl"] == -750.0
        assert result["avg_return_t7"] == -1.5
        assert result["accuracy_pct"] == 40.0  # 20/50 = 40%

    @patch("data.execute_query")
    def test_handles_null_avg_return(self, mock_execute):
        """Test that NULL avg_return from database is returned as 0.0."""
        from data import get_dashboard_kpis

        mock_execute.return_value = (
            [(0, 0, None, None)],
            ["total_signals", "correct_count", "avg_return_t7", "total_pnl"],
        )

        get_dashboard_kpis.clear_cache()
        result = get_dashboard_kpis()

        assert result["avg_return_t7"] == 0.0
        assert result["total_pnl"] == 0.0
```

### How to Run Tests

```bash
source venv/bin/activate && pytest shit_tests/shitty_ui/test_data.py::TestGetDashboardKpis -v
```

### Existing Tests That Must Still Pass

The following test classes must not regress:
- `TestGetPerformanceMetrics` (lines 180-265) -- `get_performance_metrics()` is unchanged
- `TestGetBacktestSimulation` (lines 1806+) -- `get_backtest_simulation()` is unchanged
- All other test classes in `test_data.py` -- no other functions are modified

Full UI test suite:

```bash
source venv/bin/activate && pytest shit_tests/shitty_ui/ -v
```

---

## Documentation Updates

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Fixed
- **Dashboard KPIs showing all zeros** - Main dashboard KPI cards now pull from the same `prediction_outcomes` data source as the Performance page
  - New `get_dashboard_kpis()` function queries only evaluated predictions (`correct_t7 IS NOT NULL`), preventing zeros from unevaluated predictions
  - KPI cards changed to: Total Signals, Accuracy (7-day), Avg 7-Day Return, Total P&L
  - Reduced dashboard KPI queries from 4 database calls to 1
```

---

## Edge Cases

| # | Scenario | Expected Behavior | Why It Works |
|---|----------|-------------------|-------------|
| 1 | **Zero evaluated predictions in time window** | All four KPIs show `0`, `0.0%`, `+0.00%`, `$+0`. Cards use `COLORS["danger"]` for accuracy and return, `COLORS["accent"]` for signal count. | The `WHERE correct_t7 IS NOT NULL` filter returns 0 rows. `COUNT(*)` returns 0. The function returns default zeros. The card rendering handles zeros gracefully. |
| 2 | **7-day period selected but outcomes not yet matured** | Shows 0 signals (correct behavior, not a bug). The 7D window captures predictions made 0-7 days ago, which have not yet been evaluated. | This is actually correct -- there are genuinely no evaluated outcomes in this window. Users see this as "no data yet for this period" which is accurate. |
| 3 | **All predictions are incorrect** | `accuracy_pct = 0.0`, `total_pnl` is negative. Cards render in red. | `correct_count = 0`, `total = N`. Division produces 0.0%. P&L sum of all negative values produces a negative total. |
| 4 | **All predictions are correct** | `accuracy_pct = 100.0`, `total_pnl` is positive. Cards render in green. | `correct_count = total`. Division produces 100.0%. |
| 5 | **"All" time period selected (days=None)** | No date filter applied. Shows lifetime performance. | The `if days is not None` guard at the start of `get_dashboard_kpis` skips the `date_filter` clause entirely. |
| 6 | **Database connection error** | All four KPIs show zeros. An error card is displayed. | The `try/except` in `get_dashboard_kpis` returns default zeros. The `try/except` in `update_dashboard` renders `create_error_card()`. |
| 7 | **Very large P&L values (>$100,000)** | Card displays `$+100,000` with comma formatting. | The f-string `f"${kpis['total_pnl']:+,.0f}"` handles comma grouping and sign. |
| 8 | **Negative average return** | Card displays `-0.50%` with red coloring. | The f-string `f"{kpis['avg_return_t7']:+.2f}%"` handles sign. The conditional `if kpis['avg_return_t7'] > 0` evaluates False, triggering `COLORS["danger"]`. |

---

## Verification Checklist

- [ ] `data.py` contains new function `get_dashboard_kpis()` with `@ttl_cache(ttl_seconds=300)` decorator
- [ ] `get_dashboard_kpis()` SQL query includes `WHERE correct_t7 IS NOT NULL` filter
- [ ] `get_dashboard_kpis()` does NOT filter by confidence level (no `min_confidence` parameter)
- [ ] `get_dashboard_kpis()` returns dict with keys: `total_signals`, `accuracy_pct`, `avg_return_t7`, `total_pnl`
- [ ] `clear_all_caches()` includes `get_dashboard_kpis.clear_cache()`
- [ ] `dashboard.py` imports `get_dashboard_kpis` from `data`
- [ ] `update_dashboard()` callback calls `get_dashboard_kpis(days=days)` instead of four separate functions
- [ ] Four KPI cards are: Total Signals, Accuracy, Avg 7-Day Return, Total P&L
- [ ] P&L card subtitle says "simulated $1,000 trades"
- [ ] Accuracy card subtitle says "correct at 7 days"
- [ ] `source venv/bin/activate && pytest shit_tests/shitty_ui/test_data.py::TestGetDashboardKpis -v` passes (8 tests)
- [ ] `source venv/bin/activate && pytest shit_tests/shitty_ui/test_data.py::TestGetPerformanceMetrics -v` passes (unchanged, no regression)
- [ ] `source venv/bin/activate && pytest shit_tests/shitty_ui/ -v` passes (full UI test suite)
- [ ] `python3 -m ruff check shitty_ui/data.py shitty_ui/pages/dashboard.py` passes
- [ ] `python3 -m ruff format shitty_ui/data.py shitty_ui/pages/dashboard.py` passes
- [ ] CHANGELOG.md updated under `[Unreleased]`
- [ ] Visual check: load dashboard at `/`, confirm KPI cards show non-zero values with 90D period selected
- [ ] Visual check: switch to "All" period, confirm KPI values are equal to or greater than 90D values
- [ ] Visual check: switch to "7D" period, confirm cards show `0` or valid values (not broken)
- [ ] Visual check: navigate to `/performance`, confirm backtest KPIs still work independently

---

## What NOT To Do

1. **Do NOT modify `get_performance_metrics()`.** This function is used by other parts of the codebase and already works correctly for its purpose. It returns a broader set of metrics (including `evaluated_predictions`, `correct_predictions`, `incorrect_predictions`, `avg_confidence`) that are used elsewhere. Creating a new `get_dashboard_kpis()` function keeps concerns separated and avoids breaking existing callers.

2. **Do NOT filter by confidence level in `get_dashboard_kpis()`.** The dashboard KPIs should show system-wide performance. The Performance page already has a confidence-filtered view via `get_backtest_simulation(min_confidence=0.75)`. Adding a confidence filter to the dashboard KPIs would make both pages show the same data, defeating the purpose of having two views.

3. **Do NOT remove the old import of `get_performance_metrics` from `dashboard.py`.** Even though the KPI section no longer calls it directly, the Performance page callback at line 1346 (`update_performance_page`) is in the same file and may reference it indirectly. Other dashboard sections or future features may also use it. Keep it imported.

4. **Do NOT remove `get_weekly_signal_count`, `get_high_confidence_metrics`, or `get_best_performing_asset` imports.** These functions remain valid and may be used by the Performance page callback or re-introduced in future dashboard sections. Removing them risks import errors if other callbacks reference them.

5. **Do NOT change the Performance page callback (`update_performance_page`).** That callback uses `get_backtest_simulation()` and `get_accuracy_by_confidence()` and `get_sentiment_accuracy()`. It is working correctly and is out of scope for this phase.

6. **Do NOT use `get_backtest_simulation()` for the dashboard KPIs.** While the Performance page uses it successfully, it filters by `min_confidence >= 0.75` and returns a different data shape (trade-level simulation results, not aggregate KPIs). The dashboard needs aggregate metrics across all confidence levels.

7. **Do NOT modify `components/cards.py`, `constants.py`, `layout.py`, or `components/header.py`.** These files are modified by other phases in this overhaul batch. The existing `create_metric_card()` function in `cards.py` already supports all the parameters needed (title, value, subtitle, icon, color).

8. **Do NOT add a `days` parameter validation or minimum.** If the user selects 7D and sees zero signals, that is correct behavior. Adding artificial minimum lookback windows would mask the reality that 7-day predictions need 7+ days to evaluate.

---

### Critical Files for Implementation
- `/Users/chris/Projects/shitpost-alpha/shitty_ui/data.py` - Add `get_dashboard_kpis()` function (new query), register in `clear_all_caches()`
- `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard.py` - Rewrite KPI section in `update_dashboard()` to use `get_dashboard_kpis()` and display the four desired cards
- `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_data.py` - Add `TestGetDashboardKpis` test class with 8 tests
- `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/cards.py` - Reference only: verify `create_metric_card()` signature supports the required parameters (no changes needed)
- `/Users/chris/Projects/shitpost-alpha/CHANGELOG.md` - Document the fix