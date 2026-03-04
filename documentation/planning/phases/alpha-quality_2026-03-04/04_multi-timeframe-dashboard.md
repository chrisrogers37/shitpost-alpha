# Phase 04: Multi-Timeframe Dashboard

**PR Title:** feat: add timeframe selector and thread T+1/T+3/T+7/T+30 through all dashboard layers

**Risk Level:** Medium — touches every query file and several UI components; regressions possible if column name substitution is inconsistent.

**Estimated Effort:** High (3-4 days)

**Files Created:** 2
**Files Modified:** 13
**Files Deleted:** 0

---

## Context

The `PredictionOutcome` model (`shit/market_data/models.py:51-108`) stores four timeframes — T+1, T+3, T+7, T+30 — for returns, correctness, and P&L. Despite this, the entire dashboard exclusively queries `correct_t7`, `return_t7`, and `pnl_t7`. Users have no way to see shorter-horizon (T+1, T+3) or longer-horizon (T+30) performance.

This phase adds a **Timeframe Selector** button group to the dashboard, creates a column-mapping helper, and threads the selected timeframe through all query functions, display components, and callbacks.

---

## Dependencies

- **None** — This phase can be implemented independently. No other phase modifies the same files.

## Unlocks

- **None** — Standalone enhancement.

---

## Detailed Implementation Plan

### Step 1: Create the timeframe column mapping helper

**New file:** `shitty_ui/data/timeframe.py`

This module provides a single source of truth for mapping a timeframe string to the correct database column names. Every query function will import from here instead of hardcoding column names.

```python
"""Timeframe column mapping for multi-timeframe queries.

Provides a helper that maps a timeframe key (e.g., "t7") to the
corresponding database column names in the prediction_outcomes table.

Valid timeframe keys: "t1", "t3", "t7", "t30".
"""

from typing import Dict, Literal

TimeframeKey = Literal["t1", "t3", "t7", "t30"]

# Canonical timeframe definitions
TIMEFRAME_OPTIONS: Dict[str, Dict[str, str]] = {
    "t1": {
        "correct_col": "correct_t1",
        "return_col": "return_t1",
        "pnl_col": "pnl_t1",
        "price_col": "price_t1",
        "label_short": "1D",
        "label_long": "1-Day",
        "label_days": "1",
    },
    "t3": {
        "correct_col": "correct_t3",
        "return_col": "return_t3",
        "pnl_col": "pnl_t3",
        "price_col": "price_t3",
        "label_short": "3D",
        "label_long": "3-Day",
        "label_days": "3",
    },
    "t7": {
        "correct_col": "correct_t7",
        "return_col": "return_t7",
        "pnl_col": "pnl_t7",
        "price_col": "price_t7",
        "label_short": "7D",
        "label_long": "7-Day",
        "label_days": "7",
    },
    "t30": {
        "correct_col": "correct_t30",
        "return_col": "return_t30",
        "pnl_col": "pnl_t30",
        "price_col": "price_t30",
        "label_short": "30D",
        "label_long": "30-Day",
        "label_days": "30",
    },
}

# All valid keys, for validation
VALID_TIMEFRAMES = tuple(TIMEFRAME_OPTIONS.keys())
DEFAULT_TIMEFRAME: TimeframeKey = "t7"


def get_tf_columns(timeframe: str = "t7") -> Dict[str, str]:
    """Get column names and labels for a given timeframe key.

    Args:
        timeframe: One of "t1", "t3", "t7", "t30". Defaults to "t7".

    Returns:
        Dict with keys: correct_col, return_col, pnl_col, price_col,
        label_short, label_long, label_days.

    Raises:
        ValueError: If timeframe is not a valid key.
    """
    if timeframe not in TIMEFRAME_OPTIONS:
        raise ValueError(
            f"Invalid timeframe '{timeframe}'. "
            f"Valid options: {VALID_TIMEFRAMES}"
        )
    return TIMEFRAME_OPTIONS[timeframe]
```

**Why a separate module:** All four query files (`performance_queries.py`, `asset_queries.py`, `insight_queries.py`, `signal_queries.py`) need this mapping. Putting it in `base.py` would muddy the concern boundary; a dedicated file keeps things clean and testable.

---

### Step 2: Register the helper in `data/__init__.py`

**File:** `shitty_ui/data/__init__.py`

Add these imports at the top of the file (after the existing base imports, around line 22):

**Before (lines 15-22):**
```python
# --- Base infrastructure ---
from data.base import (  # noqa: F401
    execute_query,
    ttl_cache,
    logger,
    SIGNALS_TABLE,
    DATABASE_URL,
)
```

**After:**
```python
# --- Base infrastructure ---
from data.base import (  # noqa: F401
    execute_query,
    ttl_cache,
    logger,
    SIGNALS_TABLE,
    DATABASE_URL,
)

# --- Timeframe helpers ---
from data.timeframe import (  # noqa: F401
    get_tf_columns,
    TIMEFRAME_OPTIONS,
    VALID_TIMEFRAMES,
    DEFAULT_TIMEFRAME,
)
```

Also add to the `__all__` list (after line 116):

```python
    # Timeframe
    "get_tf_columns",
    "TIMEFRAME_OPTIONS",
    "VALID_TIMEFRAMES",
    "DEFAULT_TIMEFRAME",
```

---

### Step 3: Parameterize `performance_queries.py` — all 15 functions

**File:** `shitty_ui/data/performance_queries.py`

**3a. Add import at top (after line 4):**

```python
from data.timeframe import get_tf_columns, DEFAULT_TIMEFRAME
```

**3b. Parameterize each function.** The pattern is identical for every function: add a `timeframe: str = "t7"` parameter, call `get_tf_columns(timeframe)`, then substitute the column names into the SQL string.

Below are the exact before/after for every function that references T+7 columns. Functions that do NOT reference T+7 columns (`get_available_assets`, `get_prediction_stats`, `get_sentiment_distribution`, `get_active_assets_from_db`, `get_top_predicted_asset`) are **not modified**.

---

#### `get_performance_metrics()` (line 116)

**Before signature:**
```python
def get_performance_metrics(days: int = None) -> Dict[str, Any]:
```

**After signature:**
```python
def get_performance_metrics(days: int = None, timeframe: str = DEFAULT_TIMEFRAME) -> Dict[str, Any]:
```

**Before SQL (lines 131-142):**
```python
    query = text(f"""
        SELECT
            COUNT(*) as total_outcomes,
            COUNT(CASE WHEN correct_t7 = true THEN 1 END) as correct_t7,
            COUNT(CASE WHEN correct_t7 = false THEN 1 END) as incorrect_t7,
            COUNT(CASE WHEN correct_t7 IS NOT NULL THEN 1 END) as evaluated_t7,
            AVG(CASE WHEN correct_t7 IS NOT NULL THEN return_t7 END) as avg_return_t7,
            SUM(CASE WHEN pnl_t7 IS NOT NULL THEN pnl_t7 ELSE 0 END) as total_pnl_t7,
            AVG(prediction_confidence) as avg_confidence
        FROM prediction_outcomes
        {date_filter}
    """)
```

**After SQL:**
```python
    tf = get_tf_columns(timeframe)
    correct_col = tf["correct_col"]
    return_col = tf["return_col"]
    pnl_col = tf["pnl_col"]

    query = text(f"""
        SELECT
            COUNT(*) as total_outcomes,
            COUNT(CASE WHEN {correct_col} = true THEN 1 END) as correct_count,
            COUNT(CASE WHEN {correct_col} = false THEN 1 END) as incorrect_count,
            COUNT(CASE WHEN {correct_col} IS NOT NULL THEN 1 END) as evaluated_count,
            AVG(CASE WHEN {correct_col} IS NOT NULL THEN {return_col} END) as avg_return,
            SUM(CASE WHEN {pnl_col} IS NOT NULL THEN {pnl_col} ELSE 0 END) as total_pnl,
            AVG(prediction_confidence) as avg_confidence
        FROM prediction_outcomes
        {date_filter}
    """)
```

**Also update the return dict key names** (lines 152-161) — replace `accuracy_t7`, `avg_return_t7`, `total_pnl_t7` with `accuracy`, `avg_return`, `total_pnl` (generic names):

```python
            return {
                "total_outcomes": row[0] or 0,
                "evaluated_predictions": total,
                "correct_predictions": correct,
                "incorrect_predictions": row[2] or 0,
                "accuracy": round(accuracy, 1),
                "avg_return": round(float(row[4]), 2) if row[4] else 0.0,
                "total_pnl": round(float(row[5]), 2) if row[5] else 0.0,
                "avg_confidence": round(float(row[6]), 2) if row[6] else 0.0,
            }
```

And the fallback dict (lines 165-174):

```python
    return {
        "total_outcomes": 0,
        "evaluated_predictions": 0,
        "correct_predictions": 0,
        "incorrect_predictions": 0,
        "accuracy": 0.0,
        "avg_return": 0.0,
        "total_pnl": 0.0,
        "avg_confidence": 0.0,
    }
```

**Note:** The existing keys `accuracy_t7` and `avg_return_t7` are used by `get_performance_metrics()` only. They are NOT used by the dashboard content callback (that uses `get_dashboard_kpis`). Renaming them to generic names is safe. Search for consumers to verify — see "What NOT To Do" section below.

---

#### `get_dashboard_kpis()` (line 178)

**Before signature:**
```python
def get_dashboard_kpis(days: int = None) -> Dict[str, Any]:
```

**After signature:**
```python
def get_dashboard_kpis(days: int = None, timeframe: str = DEFAULT_TIMEFRAME) -> Dict[str, Any]:
```

**Before SQL (lines 205-214):**
```python
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
```

**After SQL:**
```python
    tf = get_tf_columns(timeframe)
    correct_col = tf["correct_col"]
    return_col = tf["return_col"]
    pnl_col = tf["pnl_col"]

    query = text(f"""
        SELECT
            COUNT(*) as total_signals,
            COUNT(CASE WHEN {correct_col} = true THEN 1 END) as correct_count,
            AVG({return_col}) as avg_return,
            SUM(CASE WHEN {pnl_col} IS NOT NULL THEN {pnl_col} ELSE 0 END) as total_pnl
        FROM prediction_outcomes
        WHERE {correct_col} IS NOT NULL
        {date_filter}
    """)
```

**Return dict keys stay the same** (`total_signals`, `accuracy_pct`, `avg_return_t7`, `total_pnl`). Rename `avg_return_t7` to `avg_return` for consistency:

**Before (line 228):**
```python
                "avg_return_t7": round(float(row[2]), 2) if row[2] else 0.0,
```

**After:**
```python
                "avg_return": round(float(row[2]), 2) if row[2] else 0.0,
```

And in the fallback dict (line 236):
```python
                "avg_return": 0.0,
```

**IMPORTANT:** This key rename from `avg_return_t7` to `avg_return` means updating every consumer. See Step 7 for the content callback update.

---

#### `get_dashboard_kpis_with_fallback()` (line 241)

**Before signature:**
```python
def get_dashboard_kpis_with_fallback(days: int | None = 90) -> dict:
```

**After signature:**
```python
def get_dashboard_kpis_with_fallback(days: int | None = 90, timeframe: str = DEFAULT_TIMEFRAME) -> dict:
```

**Before (lines 253-262):**
```python
    kpis = get_dashboard_kpis(days=days)
    ...
    kpis = get_dashboard_kpis(days=None)
```

**After:**
```python
    kpis = get_dashboard_kpis(days=days, timeframe=timeframe)
    ...
    kpis = get_dashboard_kpis(days=None, timeframe=timeframe)
```

---

#### `get_accuracy_by_confidence()` (line 269)

**Before signature:**
```python
def get_accuracy_by_confidence(days: int = None) -> pd.DataFrame:
```

**After signature:**
```python
def get_accuracy_by_confidence(days: int = None, timeframe: str = DEFAULT_TIMEFRAME) -> pd.DataFrame:
```

Add at the start of the function body:
```python
    tf = get_tf_columns(timeframe)
    correct_col = tf["correct_col"]
    return_col = tf["return_col"]
    pnl_col = tf["pnl_col"]
```

Then replace all `correct_t7` with `{correct_col}`, `return_t7` with `{return_col}`, `pnl_t7` with `{pnl_col}` in the SQL string (lines 284-311).

---

#### `get_accuracy_by_asset()` (line 325)

Same pattern: add `timeframe: str = DEFAULT_TIMEFRAME` parameter, call `get_tf_columns()`, substitute into SQL (lines 341-356).

---

#### `get_cumulative_pnl()` (line 457)

**Before signature:**
```python
def get_cumulative_pnl(days: int = None) -> pd.DataFrame:
```

**After signature:**
```python
def get_cumulative_pnl(days: int = None, timeframe: str = DEFAULT_TIMEFRAME) -> pd.DataFrame:
```

Substitute `pnl_t7` -> `{pnl_col}` and `correct_t7` -> `{correct_col}` in the SQL (lines 475-485).

---

#### `get_rolling_accuracy()` (line 498)

Add `timeframe` parameter, substitute `correct_t7` -> `{correct_col}` in SQL (lines 517-527).

---

#### `get_win_loss_streaks()` (line 548)

**Before signature:**
```python
def get_win_loss_streaks() -> Dict[str, int]:
```

**After signature:**
```python
def get_win_loss_streaks(timeframe: str = DEFAULT_TIMEFRAME) -> Dict[str, int]:
```

Substitute `correct_t7` -> `{correct_col}` in SQL (lines 558-564).

---

#### `get_confidence_calibration()` (line 603)

Add `timeframe` parameter, substitute `correct_t7` -> `{correct_col}` in SQL (lines 620-631).

---

#### `get_monthly_performance()` (line 648)

Add `timeframe` parameter, substitute `correct_t7` / `return_t7` / `pnl_t7` in SQL (lines 659-672).

---

#### `get_high_confidence_metrics()` (line 687)

Add `timeframe` parameter, substitute `correct_t7` -> `{correct_col}` in SQL (lines 704-713).

---

#### `get_empty_state_context()` (line 734)

Add `timeframe` parameter, substitute `correct_t7` -> `{correct_col}` in SQL (lines 746-752).

---

#### `get_best_performing_asset()` (line 773)

Add `timeframe` parameter, substitute `correct_t7` / `pnl_t7` in SQL (lines 790-802).

---

#### `get_accuracy_over_time()` (line 822)

Add `timeframe` parameter, substitute `correct_t7` -> `{correct_col}` in SQL (lines 839-850).

---

#### `get_backtest_simulation()` (line 865)

Add `timeframe` parameter, substitute `return_t7` / `correct_t7` / `pnl_t7` in SQL (lines 890-900).

---

#### `get_sentiment_accuracy()` (line 951)

Add `timeframe` parameter, substitute `correct_t7` -> `{correct_col}` in SQL (lines 968-979).

---

### Step 4: Parameterize `asset_queries.py`

**File:** `shitty_ui/data/asset_queries.py`

**4a. Add import (after line 6):**
```python
from data.timeframe import get_tf_columns, DEFAULT_TIMEFRAME
```

**4b. `get_asset_screener_data()` (line 18)**

**Before signature:**
```python
def get_asset_screener_data(days: int = None) -> pd.DataFrame:
```

**After signature:**
```python
def get_asset_screener_data(days: int = None, timeframe: str = DEFAULT_TIMEFRAME) -> pd.DataFrame:
```

Add `tf = get_tf_columns(timeframe)` at the start, then replace `correct_t7` / `return_t7` / `pnl_t7` in the SQL (lines 40-79).

**4c. `get_asset_stats()` (line 489)**

Add `timeframe` parameter. Substitute `correct_t7` / `return_t7` / `pnl_t7` in both the `asset_stats` and `overall_stats` CTEs (lines 516-557).

Rename returned keys from `accuracy_t7` / `avg_return_t7` / `total_pnl_t7` / `best_return_t7` / `worst_return_t7` / `overall_accuracy_t7` / `overall_avg_return_t7` to generic equivalents: `accuracy` / `avg_return` / `total_pnl` / `best_return` / `worst_return` / `overall_accuracy` / `overall_avg_return`.

**4d. `get_related_assets()` (line 612)**

Add `timeframe` parameter. Replace `return_t7` -> `{return_col}` in the SQL (line 641-652). Rename `avg_return_t7` in the returned DataFrame column to `avg_return`.

---

### Step 5: Parameterize `insight_queries.py`

**File:** `shitty_ui/data/insight_queries.py`

**5a. Add import (after line 5):**
```python
from data.timeframe import get_tf_columns, DEFAULT_TIMEFRAME
```

**5b. `get_dynamic_insights()` (line 17)**

**Before signature:**
```python
def get_dynamic_insights(days: int = None) -> List[Dict[str, Any]]:
```

**After signature:**
```python
def get_dynamic_insights(days: int = None, timeframe: str = DEFAULT_TIMEFRAME) -> List[Dict[str, Any]]:
```

Add `tf = get_tf_columns(timeframe)` at the start.

Substitute in all five insight queries:
- **Insight 1** (line 49-66): `return_t7` -> `{return_col}`, `correct_t7` -> `{correct_col}`, `pnl_t7` -> `{pnl_col}` in SQL and also update the headline text from "7 days" to `{tf['label_long'].lower()}` (e.g., "1 day", "3 days", "7 days", "30 days").
- **Insight 2** (lines 108-126): `return_t7` -> `{return_col}`, `correct_t7` -> `{correct_col}`.
- **Insight 3** (lines 159-166): `correct_t7` -> `{correct_col}`.
- **Insight 4** (lines 208-219): `return_t7` -> `{return_col}`, `correct_t7` -> `{correct_col}`.
- **Insight 5** (lines 259-273): `correct_t7` -> `{correct_col}`, `return_t7` -> `{return_col}`.

Also update the headline text in insights 1 and 5 to use `tf["label_long"]` instead of hardcoded "7 days" / "7d":

**Before (line 78):**
```python
                    headline = f"Trump mentioned {symbol} -- it's {ret_str} in 7 days."
```
**After:**
```python
                    tf_label = tf["label_long"].lower()
                    headline = f"Trump mentioned {symbol} -- it's {ret_str} in {tf_label}."
```

Similarly for lines 83, 289, 295 — replace "7d" / "7 days" with the dynamic label.

---

### Step 6: Add Timeframe Selector to Dashboard Layout

**File:** `shitty_ui/pages/dashboard.py`

**6a. Add Store and ButtonGroup**

In `create_dashboard_page()` (line 12-234), add a `dcc.Store` for the selected timeframe and a new ButtonGroup next to the existing Time Period selector.

**After the existing period selector row (ending around line 72), insert the timeframe selector INSIDE the same parent `html.Div`.**

Replace the current period selector container (lines 22-72) with a combined row:

```python
                    # Time Period + Timeframe Selector Row
                    html.Div(
                        [
                            # Time Period (left side)
                            html.Div(
                                [
                                    html.Span(
                                        "Time Period: ",
                                        style={
                                            "color": COLORS["text_muted"],
                                            "marginRight": "10px",
                                            "fontSize": "0.9rem",
                                        },
                                    ),
                                    dbc.ButtonGroup(
                                        [
                                            dbc.Button("7D", id="period-7d", color="secondary", outline=True, size="sm"),
                                            dbc.Button("30D", id="period-30d", color="secondary", outline=True, size="sm"),
                                            dbc.Button("90D", id="period-90d", color="primary", size="sm"),
                                            dbc.Button("All", id="period-all", color="secondary", outline=True, size="sm"),
                                        ],
                                        size="sm",
                                    ),
                                ],
                                style={"display": "flex", "alignItems": "center"},
                            ),
                            # Timeframe Selector (right side)
                            html.Div(
                                [
                                    html.Span(
                                        "Timeframe: ",
                                        style={
                                            "color": COLORS["text_muted"],
                                            "marginRight": "10px",
                                            "fontSize": "0.9rem",
                                        },
                                    ),
                                    dbc.ButtonGroup(
                                        [
                                            dbc.Button("T+1", id="tf-t1", color="secondary", outline=True, size="sm"),
                                            dbc.Button("T+3", id="tf-t3", color="secondary", outline=True, size="sm"),
                                            dbc.Button("T+7", id="tf-t7", color="primary", size="sm"),
                                            dbc.Button("T+30", id="tf-t30", color="secondary", outline=True, size="sm"),
                                        ],
                                        size="sm",
                                    ),
                                ],
                                style={"display": "flex", "alignItems": "center"},
                            ),
                        ],
                        className="period-selector",
                        style={
                            "marginBottom": "20px",
                            "display": "flex",
                            "alignItems": "center",
                            "justifyContent": "space-between",
                            "flexWrap": "wrap",
                            "gap": "12px",
                        },
                    ),
```

**6b. Add Store to app layout**

**File:** `shitty_ui/layout.py`

Add a new `dcc.Store` for the selected timeframe (after the `selected-period` store, around line 110):

```python
            # Store for selected timeframe (default: t7)
            dcc.Store(id="selected-timeframe", data="t7"),
```

---

### Step 7: Add Timeframe Selection Callback

**File:** `shitty_ui/pages/dashboard_callbacks/period.py`

Add a new callback for the timeframe buttons. This follows the exact same pattern as the existing period callback.

**After the existing `update_period_selection` callback (line 49), add:**

```python
    @app.callback(
        [
            Output("selected-timeframe", "data"),
            Output("tf-t1", "color"),
            Output("tf-t1", "outline"),
            Output("tf-t3", "color"),
            Output("tf-t3", "outline"),
            Output("tf-t7", "color"),
            Output("tf-t7", "outline"),
            Output("tf-t30", "color"),
            Output("tf-t30", "outline"),
        ],
        [
            Input("tf-t1", "n_clicks"),
            Input("tf-t3", "n_clicks"),
            Input("tf-t7", "n_clicks"),
            Input("tf-t30", "n_clicks"),
        ],
        prevent_initial_call=True,
    )
    def update_timeframe_selection(n_t1, n_t3, n_t7, n_t30):
        """Update selected timeframe based on button clicks."""
        ctx = callback_context
        if not ctx.triggered:
            return "t7", *_get_tf_button_styles("t7")

        button_id = ctx.triggered[0]["prop_id"].split(".")[0]
        tf_map = {
            "tf-t1": "t1",
            "tf-t3": "t3",
            "tf-t7": "t7",
            "tf-t30": "t30",
        }
        selected = tf_map.get(button_id, "t7")
        return selected, *_get_tf_button_styles(selected)
```

Also add the helper function at the module level (before `register_period_callbacks`):

```python
def _get_tf_button_styles(selected: str):
    """Return button colors/outlines for each timeframe button."""
    timeframes = ["t1", "t3", "t7", "t30"]
    styles = []
    for tf in timeframes:
        if tf == selected:
            styles.extend(["primary", False])  # color, outline
        else:
            styles.extend(["secondary", True])
    return styles
```

---

### Step 8: Thread Timeframe Through Content Callback

**File:** `shitty_ui/pages/dashboard_callbacks/content.py`

**8a. Update the `update_dashboard` callback to accept the timeframe input.**

**Before (lines 38-48):**
```python
    @app.callback(
        [
            Output("insight-cards-container", "children"),
            Output("screener-table-container", "children"),
            Output("performance-metrics", "children"),
            Output("last-update-timestamp", "data"),
        ],
        [
            Input("refresh-interval", "n_intervals"),
            Input("selected-period", "data"),
        ],
    )
    def update_dashboard(n_intervals, period):
```

**After:**
```python
    @app.callback(
        [
            Output("insight-cards-container", "children"),
            Output("screener-table-container", "children"),
            Output("performance-metrics", "children"),
            Output("last-update-timestamp", "data"),
        ],
        [
            Input("refresh-interval", "n_intervals"),
            Input("selected-period", "data"),
            Input("selected-timeframe", "data"),
        ],
    )
    def update_dashboard(n_intervals, period, timeframe):
```

**8b. Add timeframe import and defaulting** at the top of `update_dashboard`:

```python
        from data.timeframe import get_tf_columns, DEFAULT_TIMEFRAME, VALID_TIMEFRAMES

        # Validate timeframe, fall back to default
        if timeframe not in VALID_TIMEFRAMES:
            timeframe = DEFAULT_TIMEFRAME
        tf = get_tf_columns(timeframe)
```

**8c. Pass timeframe to query functions:**

**Before (line 63):**
```python
            insight_pool = get_dynamic_insights(days=days)
```
**After:**
```python
            insight_pool = get_dynamic_insights(days=days, timeframe=timeframe)
```

**Before (line 72):**
```python
            screener_df = get_asset_screener_data(days=days)
```
**After:**
```python
            screener_df = get_asset_screener_data(days=days, timeframe=timeframe)
```

**Before (line 91):**
```python
            kpis = get_dashboard_kpis_with_fallback(days=days)
```
**After:**
```python
            kpis = get_dashboard_kpis_with_fallback(days=days, timeframe=timeframe)
```

**8d. Update KPI card titles dynamically**

Add an import for `get_tf_columns` at the top of the file:
```python
from data.timeframe import get_tf_columns, DEFAULT_TIMEFRAME, VALID_TIMEFRAMES
```

And replace the hardcoded COPY references with dynamic labels.

**Before (lines 95-158) — the metrics_row section:**

Replace the KPI title and subtitle references:

```python
            # Dynamic KPI labels based on timeframe
            tf_label_long = tf["label_long"]
            tf_label_days = tf["label_days"]
```

Then in the KPI cards:

- **Accuracy card** — Change subtitle from `COPY["kpi_accuracy_subtitle"]` (which says "correct after 7 days (coin flip is 50%)") to:
  ```python
  f"correct after {tf_label_days} days (coin flip is 50%)",
  ```

- **Avg Return card** — Change title from `COPY["kpi_avg_return_title"]` (which says "Avg 7-Day Return") to:
  ```python
  f"Avg {tf_label_long} Return",
  ```
  And subtitle from `COPY["kpi_avg_return_subtitle"]` to:
  ```python
  f"mean {tf_label_days}-day return per signal",
  ```

- **P&L card** — Change subtitle from `COPY["kpi_pnl_subtitle"]` to:
  ```python
  f"simulated $1k trades ({tf_label_days}-day horizon)",
  ```

- **Avg return value** — Update key access from `kpis['avg_return_t7']` to `kpis['avg_return']` (two occurrences at lines 130 and 135):

  **Before:**
  ```python
  f"{kpis['avg_return_t7']:+.2f}%",
  ```
  **After:**
  ```python
  f"{kpis['avg_return']:+.2f}%",
  ```

  And the color conditional:
  **Before:**
  ```python
  COLORS["success"] if kpis["avg_return_t7"] > 0 else COLORS["danger"],
  ```
  **After:**
  ```python
  COLORS["success"] if kpis["avg_return"] > 0 else COLORS["danger"],
  ```

---

### Step 9: Update Screener Table Headers

**File:** `shitty_ui/components/screener.py`

The screener table currently has a hardcoded "7d Return" header (line 270). Make this dynamic.

**9a. Update `build_screener_table()` signature (line 197):**

**Before:**
```python
def build_screener_table(
    screener_df: pd.DataFrame,
    sparkline_data: Dict[str, pd.DataFrame],
    sort_column: str = "total_predictions",
    sort_ascending: bool = False,
) -> html.Div:
```

**After:**
```python
def build_screener_table(
    screener_df: pd.DataFrame,
    sparkline_data: Dict[str, pd.DataFrame],
    sort_column: str = "total_predictions",
    sort_ascending: bool = False,
    timeframe: str = "t7",
) -> html.Div:
```

**9b. Replace the hardcoded header (line 270):**

Add import at top:
```python
from data.timeframe import get_tf_columns
```

In `build_screener_table`, before the header row:
```python
    tf = get_tf_columns(timeframe)
    return_header = f"{tf['label_short']} Return"
```

Then change line 270 from:
```python
                _sort_header("7d Return", "avg_return", "right"),
```
to:
```python
                _sort_header(return_header, "avg_return", "right"),
```

**9c. Pass timeframe from the content callback:**

**File:** `shitty_ui/pages/dashboard_callbacks/content.py`

**Before (lines 78-83):**
```python
            screener_table = build_screener_table(
                screener_df=screener_df,
                sparkline_data=sparkline_data,
                sort_column="total_predictions",
                sort_ascending=False,
            )
```

**After:**
```python
            screener_table = build_screener_table(
                screener_df=screener_df,
                sparkline_data=sparkline_data,
                sort_column="total_predictions",
                sort_ascending=False,
                timeframe=timeframe,
            )
```

---

### Step 10: Update Asset Detail Page

**File:** `shitty_ui/pages/assets.py`

The asset page does not currently receive the timeframe selector value (it has no period selector either). The approach here is to show a **multi-timeframe outcome table** on the asset detail page's prediction timeline, displaying T+1, T+3, T+7, T+30 side by side. This gives the user the full picture without needing another selector.

**10a. Update stat cards in `update_asset_page` callback (lines 314-375).**

The stat cards currently show "Total P&L (7-day)" and "Avg 7-Day Return" with hardcoded keys `total_pnl_t7` and `avg_return_t7`.

Since `get_asset_stats()` now returns generic keys (`total_pnl`, `avg_return`, `accuracy`, etc.), update the references.

**But wait** — on the asset page, we want to show the default T+7 unless we also thread timeframe here. For now, keep the asset page at T+7 (the detail page already shows multi-timeframe data in the timeline). Simply update the dict key references:

**Before (line 346):**
```python
                            "Total P&L (7-day)",
                            f"${stats['total_pnl_t7']:,.0f}",
```
**After:**
```python
                            "Total P&L (7-day)",
                            f"${stats['total_pnl']:,.0f}",
```

**Before (line 360):**
```python
                            "Avg 7-Day Return",
                            f"{stats['avg_return_t7']:+.2f}%",
```
**After:**
```python
                            "Avg 7-Day Return",
                            f"{stats['avg_return']:+.2f}%",
```

And the color conditionals:
```python
# Line 353 (was total_pnl_t7):
COLORS["success"] if stats["total_pnl"] > 0 else COLORS["danger"],
# Line 366 (was avg_return_t7):
COLORS["success"] if stats["avg_return"] > 0 else COLORS["danger"],
```

**Before (line 319):**
```python
                            f"{stats['accuracy_t7']:.1f}%",
```
**After:**
```python
                            f"{stats['accuracy']:.1f}%",
```

And line 325:
```python
COLORS["success"] if stats["accuracy"] > 60 else COLORS["danger"],
```

**10b. Update `_build_asset_signal_summary` (line 552).**

The mini stat card at line 649 says "total P&L (7d)" with data from `pnl_t7`. This data comes from the DataFrame, not the stats dict, so leave it unchanged since the DataFrame column name hasn't changed.

**10c. Update `create_performance_summary` in `components/cards/metrics.py` (line 124).**

This function reads `accuracy_t7`, `avg_return_t7`, `overall_accuracy_t7`, `overall_avg_return_t7`, `best_return_t7`, `worst_return_t7` from the stats dict. Update all references to the new generic keys:

**Before (line 134):**
```python
    asset_accuracy = stats.get("accuracy_t7", 0)
    overall_accuracy = stats.get("overall_accuracy_t7", 0)
```
**After:**
```python
    asset_accuracy = stats.get("accuracy", 0)
    overall_accuracy = stats.get("overall_accuracy", 0)
```

**Before (line 138):**
```python
    asset_return = stats.get("avg_return_t7", 0)
    overall_return = stats.get("overall_avg_return_t7", 0)
```
**After:**
```python
    asset_return = stats.get("avg_return", 0)
    overall_return = stats.get("overall_avg_return", 0)
```

**Before (line 142):**
```python
    best = stats.get("best_return_t7")
    worst = stats.get("worst_return_t7")
```
**After:**
```python
    best = stats.get("best_return")
    worst = stats.get("worst_return")
```

---

### Step 11: Update Timeline Card for Multi-Timeframe Display

**File:** `shitty_ui/components/cards/timeline.py`

Currently `create_prediction_timeline_card()` only shows `return_t7` and `pnl_t7`. Since the `get_asset_predictions()` query already fetches T+1, T+3, T+7, T+30 data, we can display all timeframes as a compact row.

**Replace the metrics row section (lines 176-215) with a multi-timeframe display:**

```python
            # Multi-timeframe outcome row
            html.Div(
                _build_multi_tf_row(row),
                style={"marginBottom": "4px"},
            ),
```

Add the helper function at module level (before `create_prediction_timeline_card`):

```python
_TF_DEFS = [
    ("return_t1", "correct_t1", "1D"),
    ("return_t3", "correct_t3", "3D"),
    ("return_t7", "correct_t7", "7D"),
    ("return_t30", "correct_t30", "30D"),
]


def _build_multi_tf_row(row: dict) -> list:
    """Build a compact row of T+1/T+3/T+7/T+30 outcome cells."""
    cells = []
    for return_key, correct_key, label in _TF_DEFS:
        ret_val = row.get(return_key)
        correct_val = row.get(correct_key)

        if ret_val is not None:
            ret_str = f"{ret_val:+.2f}%"
            color = (
                COLORS["success"] if ret_val > 0
                else COLORS["danger"] if ret_val < 0
                else COLORS["text_muted"]
            )
        else:
            ret_str = "--"
            color = COLORS["text_muted"]

        # Status indicator
        if correct_val is True:
            icon = html.I(className="fas fa-check", style={"color": COLORS["success"], "fontSize": "0.7rem", "marginRight": "3px"})
        elif correct_val is False:
            icon = html.I(className="fas fa-times", style={"color": COLORS["danger"], "fontSize": "0.7rem", "marginRight": "3px"})
        elif correct_val is None and ret_val is None:
            icon = html.I(className="fas fa-clock", style={"color": COLORS["warning"], "fontSize": "0.7rem", "marginRight": "3px"})
        else:
            icon = None

        cell = html.Span(
            [
                html.Span(f"{label}: ", style={"color": COLORS["text_muted"], "fontSize": "0.75rem", "fontWeight": "600"}),
                icon,
                html.Span(ret_str, style={"color": color, "fontSize": "0.85rem", "fontWeight": "bold"}),
            ] if icon else [
                html.Span(f"{label}: ", style={"color": COLORS["text_muted"], "fontSize": "0.75rem", "fontWeight": "600"}),
                html.Span(ret_str, style={"color": color, "fontSize": "0.85rem", "fontWeight": "bold"}),
            ],
            style={"marginRight": "16px"},
        )
        cells.append(cell)

    # Also add P&L for T+7 (the primary reference)
    pnl_t7 = row.get("pnl_t7")
    if pnl_t7 is not None:
        pnl_color = COLORS["success"] if pnl_t7 > 0 else COLORS["danger"]
        cells.append(
            html.Span(
                [
                    html.Span("P&L: ", style={"color": COLORS["text_muted"], "fontSize": "0.75rem", "fontWeight": "600"}),
                    html.Span(f"${pnl_t7:+,.0f}", style={"color": pnl_color, "fontSize": "0.85rem", "fontWeight": "bold"}),
                ],
                style={"marginRight": "16px"},
            )
        )

    # Price info
    price_at = row.get("price_at_prediction")
    price_after = row.get("price_t7")
    if price_at is not None:
        cells.append(
            html.Span(
                f"Entry: ${price_at:,.2f}",
                style={"color": COLORS["text_muted"], "fontSize": "0.8rem"},
            )
        )
    if price_after is not None:
        cells.append(
            html.Span(
                f" -> ${price_after:,.2f}",
                style={"color": COLORS["text_muted"], "fontSize": "0.8rem"},
            )
        )

    return cells
```

---

### Step 12: Update `signal_queries.py` — outcome filter

**File:** `shitty_ui/data/signal_queries.py`

The `_build_signal_feed_filters()` function (line 426) uses `correct_t7` for outcome filtering. Since the signal feed always displays T+7 outcomes in its table and is primarily for browsing (not metric aggregation), we keep the signal feed at T+7 for now. **No changes needed** — the feed already fetches all timeframes in its SELECT.

However, if the outcome filter should also respect the selected timeframe in a future iteration, the pattern would be to add a `timeframe` parameter to `_build_signal_feed_filters()`.

---

### Step 13: Update `helpers.py` — `create_outcome_badge`

**File:** `shitty_ui/components/helpers.py`

The `create_outcome_badge` function (line 68) takes `correct_t7` as parameter. Rename the parameter to `correct` for clarity since it is now timeframe-agnostic:

**Before (line 68):**
```python
def create_outcome_badge(
    correct_t7: Optional[bool],
    pnl_display: Optional[float] = None,
    font_size: str = "0.75rem",
) -> html.Span:
```

**After:**
```python
def create_outcome_badge(
    correct: Optional[bool],
    pnl_display: Optional[float] = None,
    font_size: str = "0.75rem",
) -> html.Span:
```

Update the function body to use `correct` instead of `correct_t7` (lines 89, 101). All existing callers pass this positionally, so the rename is backward-compatible.

---

## Summary of All File Changes

| File | Action | What Changes |
|------|--------|-------------|
| `shitty_ui/data/timeframe.py` | **CREATE** | Timeframe column mapping helper |
| `shitty_ui/data/__init__.py` | MODIFY | Import and re-export timeframe helpers |
| `shitty_ui/data/performance_queries.py` | MODIFY | Add `timeframe` param to 15 functions |
| `shitty_ui/data/asset_queries.py` | MODIFY | Add `timeframe` param to 3 functions, rename dict keys |
| `shitty_ui/data/insight_queries.py` | MODIFY | Add `timeframe` param, dynamic labels |
| `shitty_ui/layout.py` | MODIFY | Add `selected-timeframe` Store |
| `shitty_ui/pages/dashboard.py` | MODIFY | Add timeframe ButtonGroup to layout |
| `shitty_ui/pages/dashboard_callbacks/period.py` | MODIFY | Add timeframe selection callback |
| `shitty_ui/pages/dashboard_callbacks/content.py` | MODIFY | Thread timeframe through queries and KPI labels |
| `shitty_ui/components/screener.py` | MODIFY | Dynamic return column header |
| `shitty_ui/components/cards/metrics.py` | MODIFY | Generic stat dict keys |
| `shitty_ui/components/cards/timeline.py` | MODIFY | Multi-timeframe outcome row |
| `shitty_ui/components/helpers.py` | MODIFY | Rename `correct_t7` param to `correct` |
| `shitty_ui/pages/assets.py` | MODIFY | Update stat dict key references |

---

## Test Plan

### New Test File: `shit_tests/shitty_ui/test_timeframe.py`

```python
"""Tests for the timeframe column mapping helper."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))


class TestGetTfColumns:
    """Tests for get_tf_columns()."""

    def test_returns_correct_columns_for_t7(self):
        from data.timeframe import get_tf_columns
        tf = get_tf_columns("t7")
        assert tf["correct_col"] == "correct_t7"
        assert tf["return_col"] == "return_t7"
        assert tf["pnl_col"] == "pnl_t7"
        assert tf["price_col"] == "price_t7"

    def test_returns_correct_columns_for_t1(self):
        from data.timeframe import get_tf_columns
        tf = get_tf_columns("t1")
        assert tf["correct_col"] == "correct_t1"
        assert tf["return_col"] == "return_t1"
        assert tf["label_short"] == "1D"
        assert tf["label_long"] == "1-Day"

    def test_returns_correct_columns_for_t3(self):
        from data.timeframe import get_tf_columns
        tf = get_tf_columns("t3")
        assert tf["correct_col"] == "correct_t3"

    def test_returns_correct_columns_for_t30(self):
        from data.timeframe import get_tf_columns
        tf = get_tf_columns("t30")
        assert tf["correct_col"] == "correct_t30"
        assert tf["label_short"] == "30D"

    def test_raises_on_invalid_timeframe(self):
        from data.timeframe import get_tf_columns
        with pytest.raises(ValueError, match="Invalid timeframe"):
            get_tf_columns("t14")

    def test_raises_on_empty_string(self):
        from data.timeframe import get_tf_columns
        with pytest.raises(ValueError):
            get_tf_columns("")

    def test_default_timeframe_is_t7(self):
        from data.timeframe import DEFAULT_TIMEFRAME
        assert DEFAULT_TIMEFRAME == "t7"

    def test_valid_timeframes_tuple(self):
        from data.timeframe import VALID_TIMEFRAMES
        assert set(VALID_TIMEFRAMES) == {"t1", "t3", "t7", "t30"}
```

### Existing Test Updates

**File:** `shit_tests/shitty_ui/test_data.py`

All existing tests mock `data.base.execute_query` and call query functions without the `timeframe` parameter. Since `timeframe` defaults to `"t7"`, **existing tests should pass unchanged**. This is by design -- the default parameter provides backward compatibility.

Add new tests for the timeframe parameter:

```python
class TestDashboardKpisTimeframe:
    """Tests for timeframe parameter on get_dashboard_kpis."""

    @patch("data.base.execute_query")
    def test_t1_uses_correct_columns(self, mock_execute):
        from data import get_dashboard_kpis
        mock_execute.return_value = ([(10, 5, 0.5, 100.0)], ["total_signals", "correct_count", "avg_return", "total_pnl"])
        result = get_dashboard_kpis(days=None, timeframe="t1")
        # Verify the SQL contains correct_t1 not correct_t7
        call_args = mock_execute.call_args
        sql_str = str(call_args[0][0])
        assert "correct_t1" in sql_str
        assert "return_t1" in sql_str
        assert "pnl_t1" in sql_str

    @patch("data.base.execute_query")
    def test_default_uses_t7(self, mock_execute):
        from data import get_dashboard_kpis
        mock_execute.return_value = ([(10, 5, 0.5, 100.0)], ["total_signals", "correct_count", "avg_return", "total_pnl"])
        result = get_dashboard_kpis(days=None)
        sql_str = str(mock_execute.call_args[0][0])
        assert "correct_t7" in sql_str

    @patch("data.base.execute_query")
    def test_invalid_timeframe_raises(self, mock_execute):
        from data import get_dashboard_kpis
        with pytest.raises(ValueError):
            get_dashboard_kpis(days=None, timeframe="t14")
```

**File:** `shit_tests/shitty_ui/test_screener.py`

Update any tests that call `build_screener_table()` to pass the `timeframe` parameter (or rely on the default). Add a test verifying the dynamic header:

```python
def test_screener_header_reflects_timeframe(self):
    """Verify the return column header changes with timeframe."""
    # ... set up a non-empty screener_df ...
    table_t1 = build_screener_table(screener_df, {}, timeframe="t1")
    # Extract the header row and check for "1D Return"
    # (inspect the html.Th elements in the table's header)
```

**File:** `shit_tests/shitty_ui/test_insights.py`

Add a test verifying dynamic headline labels:

```python
@patch("data.base.execute_query")
def test_insight_headline_uses_timeframe_label(self, mock_execute):
    """Verify insight headlines say '1 day' when timeframe=t1."""
    # ... mock a latest_call insight result ...
    from data import get_dynamic_insights
    insights = get_dynamic_insights(days=None, timeframe="t1")
    # Assert "1-day" or "1 day" appears in the headline text
```

### Manual Verification

1. Run `source venv/bin/activate && pytest shit_tests/shitty_ui/ -v` -- all existing tests pass.
2. Start the dashboard locally: `cd shitty_ui && python app.py`.
3. Verify the timeframe selector buttons appear next to the time period selector.
4. Click T+1, T+3, T+30 -- KPI values, screener data, and insight cards update.
5. Navigate to an asset detail page -- verify multi-timeframe outcome row shows all four timeframes.
6. Verify T+7 is selected by default and renders identically to the pre-change dashboard.

---

## Documentation Updates

### `brand_copy.py`

The hardcoded COPY strings for KPI titles/subtitles (`kpi_accuracy_subtitle`, `kpi_avg_return_title`, etc.) are now partially bypassed in favor of dynamic labels. Add a comment to `brand_copy.py` explaining this:

```python
    # NOTE: kpi_accuracy_subtitle and kpi_avg_return_title/subtitle are
    # overridden dynamically by the timeframe selector in content.py.
    # These COPY entries remain as defaults for the T+7 case.
```

### `CHANGELOG.md`

Add under `## [Unreleased]`:

```markdown
### Added
- **Multi-Timeframe Dashboard** - Timeframe selector (T+1, T+3, T+7, T+30) on the main dashboard
  - All KPIs, screener, and insight cards update based on selected timeframe
  - Asset detail page shows multi-timeframe outcome row (T+1/T+3/T+7/T+30 side by side)
  - Timeframe column mapping helper (`data/timeframe.py`) for consistent column substitution
  - Dynamic KPI labels reflect the selected timeframe horizon
```

---

## Stress Testing & Edge Cases

1. **T+1 and T+3 data may be sparse for older predictions.** The `prediction_outcomes` table has `correct_t1` and `correct_t3` that are NULL for predictions that haven't matured at shorter horizons. The queries already handle NULLs with `WHERE correct_{tf} IS NOT NULL`, so this is safe. However, the dashboard may show "0 signals evaluated" for T+1 on recent predictions that haven't had 1 day yet. The fallback mechanism in `get_dashboard_kpis_with_fallback` handles this.

2. **T+30 data is very sparse.** Most predictions won't have T+30 outcomes yet (requires 30+ days). The KPI cards will show 0 or fall back to all-time. The fallback note ("All-time") will appear. This is correct behavior.

3. **Cache key collision.** The `@ttl_cache` decorator uses function name + args as the cache key. Adding `timeframe` as a parameter changes the args tuple, so `get_dashboard_kpis(days=90, timeframe="t1")` and `get_dashboard_kpis(days=90, timeframe="t7")` will have different cache keys. This is correct -- no collision.

4. **SQL injection risk.** The column names come from `get_tf_columns()` which only returns predefined strings from `TIMEFRAME_OPTIONS`. The `timeframe` parameter is validated against `VALID_TIMEFRAMES`. There is no user-controlled string interpolation into SQL.

5. **Backward compatibility.** All functions default to `timeframe="t7"`, so existing callers (tests, scripts, other modules) continue to work without changes.

---

## Verification Checklist

- [ ] `source venv/bin/activate && pytest shit_tests/shitty_ui/ -v` passes
- [ ] `source venv/bin/activate && pytest -v` (full suite) passes
- [ ] New file `shitty_ui/data/timeframe.py` exists with all 4 timeframes
- [ ] New test file `shit_tests/shitty_ui/test_timeframe.py` exists
- [ ] Dashboard loads at `http://localhost:8050/` with timeframe selector visible
- [ ] Clicking T+1 updates KPI cards (titles say "1-Day")
- [ ] Clicking T+30 may show fallback "All-time" note (expected for sparse data)
- [ ] Screener table header changes from "7D Return" to "1D Return" etc.
- [ ] Asset detail page shows 4-column outcome row (T+1, T+3, T+7, T+30)
- [ ] Default (T+7) renders identically to pre-change dashboard
- [ ] `ruff check shitty_ui/` passes
- [ ] `ruff format shitty_ui/` makes no changes
- [ ] CHANGELOG.md updated

---

## What NOT To Do

1. **Do NOT rename dict keys without updating ALL consumers.** When renaming `avg_return_t7` to `avg_return` in `get_dashboard_kpis()`, every place that accesses `kpis['avg_return_t7']` must be updated. Grep for `avg_return_t7` across the entire `shitty_ui/` directory before marking this complete. Same for `accuracy_t7`, `total_pnl_t7`, `best_return_t7`, `worst_return_t7`, `overall_accuracy_t7`, `overall_avg_return_t7`.

2. **Do NOT use f-strings for SQL column names in a way that could accept user input.** The timeframe parameter must always be validated through `get_tf_columns()` before any string interpolation into SQL. Never pass the raw `timeframe` string directly into a query.

3. **Do NOT add the timeframe parameter to functions that don't use T+7 columns.** Functions like `get_prediction_stats()`, `get_sentiment_distribution()`, `get_active_assets_from_db()`, and `get_top_predicted_asset()` do not reference any timeframe-specific columns. Adding a `timeframe` parameter to them would be misleading.

4. **Do NOT change the signal feed queries to use the timeframe selector.** The signal feed (`get_signal_feed`, `get_unified_feed`, etc.) displays raw post data with all timeframe columns visible. The timeframe selector controls aggregated metrics, not individual post display.

5. **Do NOT change `_build_signal_feed_filters()` outcome filtering.** The `correct_t7` references in the filter builder (for "correct"/"incorrect"/"pending" outcome filters) should remain as-is for this phase. Threading timeframe through the signal feed filter is a separate concern.

6. **Do NOT break the `@ttl_cache` decorator behavior.** The cache uses `(func.__name__, args, tuple(sorted(kwargs.items())))` as its key. Since `timeframe` is a keyword argument, passing it changes the cache key correctly. But if you pass it as a positional arg in some places and kwarg in others, you'll get cache misses. Always use `timeframe=value` (keyword) for consistency.

7. **Do NOT add separate timeframe selectors to every page.** The asset detail page uses multi-timeframe display (all 4 in columns). Only the main dashboard has the selector. This keeps the UI simple.
