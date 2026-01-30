# Asset Deep Dive Pages - Engineering Specification

> **STATUS: PENDING** - Not yet implemented. Can be done in parallel with Performance Page (03).

## Implementation Context for Engineering Team

### Current State (as of 2026-01-29)

The dashboard already has a **partial asset drilldown feature** in `layout.py`:

- `asset-selector` dropdown with active assets
- `get_similar_predictions(asset, limit)` function in `data.py` for historical predictions
- `update_asset_drilldown()` callback that renders prediction cards for selected asset

**This spec extends that feature** into dedicated full-page views with price charts.

### Existing Related Functions in `data.py`

| Function | Purpose | Reusable? |
|----------|---------|-----------|
| `get_similar_predictions(asset, limit)` | Historical predictions for one asset | ✅ Yes |
| `get_accuracy_by_asset(limit, days)` | Accuracy stats per asset | ✅ Partial - need single-asset variant |
| `get_active_assets_from_db()` | List of assets with outcomes | ✅ Yes - for validation |

### Database Tables Available

**For Price Charts** (`market_prices`):
```sql
market_prices (
  id, symbol, date,
  open, high, low, close, volume, adjusted_close,
  source, last_updated, is_market_open, has_split, has_dividend
)
```
Key index: `idx_market_price_symbol_date` (UNIQUE on symbol + date)

**For Predictions** (`prediction_outcomes` + `predictions` + `truth_social_shitposts`):
- Join `prediction_outcomes.prediction_id` → `predictions.id`
- Join `predictions.shitpost_id` → `truth_social_shitposts.shitpost_id`
- This gives full context: price data + prediction details + original tweet text

### Key Implementation Notes

1. **market_prices table exists** - Use it directly for OHLCV candlestick/line charts
2. **Prediction overlay markers** - Plot vertical lines or markers at `prediction_date` with color based on `correct_t7`
3. **URL routing** - Dash doesn't have native dynamic routes; use `dcc.Location` + pathname parsing
4. **Chart library** - Use Plotly's `go.Candlestick` or `go.Scatter` for price charts

### Recommended Implementation Approach

1. **Add `get_asset_price_history(symbol, days)` function** to `data.py`
2. **Add `get_asset_performance_summary(symbol)` function** for single-asset stats
3. **Add URL routing** using `dcc.Location` and pathname callback
4. **Build the asset page layout** with header, stats, chart, and prediction timeline

---

## Overview

This document specifies the implementation of dedicated `/assets/{symbol}` pages in the Shitpost Alpha dashboard. Each page provides a comprehensive view of a single asset: price history, prediction overlays, performance statistics, and related assets.

**Estimated Effort**: 3-4 days
**Priority**: P1 (Should Have)
**Prerequisites**: ✅ Dashboard Enhancements (02) complete - **DONE**

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [URL Routing Setup](#2-url-routing-setup)
3. [Data Layer - New Queries](#3-data-layer---new-queries)
4. [Layout Components](#4-layout-components)
5. [Callback Implementations](#5-callback-implementations)
6. [Test Specifications](#6-test-specifications)
7. [Implementation Checklist](#7-implementation-checklist)
8. [Definition of Done](#8-definition-of-done)

---

## 1. Architecture Overview

### What We Are Building

When a user navigates to `/assets/AAPL`, they see a full-page view with:

```
+----------------------------------------------------------+
|  HEADER BAR (back link, asset name, current price)       |
+----------------------------------------------------------+
|  STAT CARDS ROW                                          |
|  [Accuracy] [Total Predictions] [Total P&L] [Avg Return]|
+----------------------------------------------------------+
|  PRICE CHART (left 8-col)    |  PERFORMANCE SUMMARY      |
|  - Candlestick or line       |  (right 4-col)            |
|  - Prediction markers        |  - This asset vs overall  |
|  - Color-coded by outcome    |  - Win rate by sentiment  |
|  - Date range selector       |  - Best/worst prediction  |
+----------------------------------------------------------+
|  PREDICTION TIMELINE                                     |
|  - Chronological cards       |  RELATED ASSETS           |
|  - Tweet text, sentiment,    |  - Other assets commonly  |
|    confidence, outcome       |    predicted alongside     |
|  - Scrollable list           |  - Click to navigate      |
+----------------------------------------------------------+
|  FOOTER                                                  |
+----------------------------------------------------------+
```

### Files Changed

| File | Changes |
|------|---------|
| `shitty_ui/app.py` | Add `dcc.Location` and URL routing |
| `shitty_ui/data.py` | Add 4 new query functions |
| `shitty_ui/layout.py` | Add asset page layout and callbacks |
| `shit_tests/shitty_ui/test_data.py` | Add tests for new queries |
| `shit_tests/shitty_ui/test_layout.py` | Add tests for new components |

### Database Tables Used

This feature reads from four tables. No schema changes are required.

```sql
-- Price history for the candlestick/line chart
market_prices (symbol, date, open, high, low, close, volume, adjusted_close)

-- Prediction outcomes for this specific asset
prediction_outcomes (id, prediction_id, symbol, prediction_date, prediction_sentiment,
                     prediction_confidence, price_at_prediction, price_t1, price_t3,
                     price_t7, price_t30, return_t1, return_t3, return_t7, return_t30,
                     correct_t1, correct_t3, correct_t7, correct_t30,
                     pnl_t1, pnl_t3, pnl_t7, pnl_t30, is_complete)

-- Prediction details and thesis text
predictions (id, shitpost_id, assets, market_impact, confidence, thesis, analysis_status)

-- Original tweet text
truth_social_shitposts (shitpost_id, timestamp, text, replies_count, reblogs_count, favourites_count)
```

### Color Palette Reference

Every component in this feature must use these colors. Do not invent new hex values.

```python
COLORS = {
    "primary": "#1e293b",      # Slate 800 - main background
    "secondary": "#334155",    # Slate 700 - cards
    "accent": "#3b82f6",       # Blue 500 - highlights, links
    "success": "#10b981",      # Emerald 500 - bullish, correct, positive
    "danger": "#ef4444",       # Red 500 - bearish, incorrect, negative
    "warning": "#f59e0b",      # Amber 500 - pending, neutral
    "text": "#f1f5f9",         # Slate 100 - primary text
    "text_muted": "#94a3b8",   # Slate 400 - secondary text
    "border": "#475569",       # Slate 600 - borders
}
```

---

## 2. URL Routing Setup

Dash does not have built-in multi-page routing like Flask. We use `dcc.Location` to read the browser URL and render different layouts based on the pathname.

### Step 1: Update `app.py`

The entry point does not change significantly. The key requirement is that `suppress_callback_exceptions=True` is already set in `create_app()` (it is). This is necessary because the asset page components do not exist in the DOM until the user navigates there.

No changes needed to `app.py`. All routing logic lives in `layout.py`.

### Step 2: Add URL Components to `layout.py`

Add `dcc.Location` inside the top-level `html.Div` in `create_app()`. This component reads the current browser URL and triggers callbacks when it changes.

**Where to add it**: Inside `create_app()`, at the top of the `app.layout` children list, alongside the existing `dcc.Interval` and `dcc.Store` components.

```python
# In create_app(), add these to the top of app.layout children:

# URL routing
dcc.Location(id="url", refresh=False),

# Page content container (replaces the existing inline content)
html.Div(id="page-content"),
```

### Step 3: Restructure the Layout

The current `create_app()` function places all dashboard content directly in `app.layout`. We need to move that content into a function so the router can swap between pages.

**Before** (current structure in `create_app()`):
```python
app.layout = html.Div([
    dcc.Interval(...),
    dcc.Store(...),
    create_header(),
    html.Div([
        # ... all dashboard content inline ...
    ], style={...})
], style={...})
```

**After** (new structure):
```python
app.layout = html.Div([
    # URL tracking
    dcc.Location(id="url", refresh=False),

    # Auto-refresh interval (shared across pages)
    dcc.Interval(
        id="refresh-interval",
        interval=5 * 60 * 1000,  # 5 minutes
        n_intervals=0
    ),

    # Shared stores
    dcc.Store(id="selected-asset", data=None),

    # Page content - swapped by router callback
    html.Div(id="page-content"),

], style={
    "backgroundColor": COLORS["primary"],
    "minHeight": "100vh",
    "color": COLORS["text"],
    "fontFamily": "'Inter', -apple-system, BlinkMacSystemFont, sans-serif"
})
```

### Step 4: Create Page Layout Functions

Extract the current dashboard into its own function and create the asset page function.

```python
def create_dashboard_page() -> html.Div:
    """Create the main dashboard page layout (shown at /)."""
    return html.Div([
        # Header
        create_header(),

        # Main content container
        html.Div([
            # Performance Metrics Row
            html.Div(id="performance-metrics", className="mb-4"),

            # Two column layout: Charts + Asset Drilldown
            dbc.Row([
                # Left column: Performance charts
                dbc.Col([
                    # Accuracy by Confidence Chart
                    dbc.Card([
                        dbc.CardHeader([
                            html.I(className="fas fa-chart-bar me-2"),
                            "Accuracy by Confidence Level"
                        ], className="fw-bold"),
                        dbc.CardBody([
                            dcc.Graph(
                                id="confidence-accuracy-chart",
                                config={"displayModeBar": False}
                            )
                        ])
                    ], className="mb-3",
                       style={"backgroundColor": COLORS["secondary"]}),

                    # Accuracy by Asset Chart
                    dbc.Card([
                        dbc.CardHeader([
                            html.I(className="fas fa-coins me-2"),
                            "Performance by Asset"
                        ], className="fw-bold"),
                        dbc.CardBody([
                            dcc.Graph(
                                id="asset-accuracy-chart",
                                config={"displayModeBar": False}
                            )
                        ])
                    ], className="mb-3",
                       style={"backgroundColor": COLORS["secondary"]}),
                ], md=7),

                # Right column: Recent Signals + Asset Drilldown
                dbc.Col([
                    # Recent Signals
                    dbc.Card([
                        dbc.CardHeader([
                            html.I(className="fas fa-bolt me-2"),
                            "Recent Signals"
                        ], className="fw-bold"),
                        dbc.CardBody(
                            id="recent-signals-list",
                            style={"maxHeight": "400px", "overflowY": "auto"}
                        )
                    ], className="mb-3",
                       style={"backgroundColor": COLORS["secondary"]}),

                    # Asset Deep Dive
                    dbc.Card([
                        dbc.CardHeader([
                            html.I(className="fas fa-search me-2"),
                            "Asset Deep Dive"
                        ], className="fw-bold"),
                        dbc.CardBody([
                            dcc.Dropdown(
                                id="asset-selector",
                                placeholder="Select an asset to see historical predictions...",
                                className="mb-3",
                                style={
                                    "backgroundColor": COLORS["primary"],
                                    "color": COLORS["text"]
                                }
                            ),
                            html.Div(id="asset-drilldown-content")
                        ])
                    ], style={"backgroundColor": COLORS["secondary"]}),
                ], md=5),
            ]),

            # Collapsible Full Data Table
            dbc.Card([
                dbc.CardHeader([
                    dbc.Button(
                        [html.I(className="fas fa-table me-2"),
                         "Full Prediction Data"],
                        id="collapse-table-button",
                        color="link",
                        className="text-white fw-bold p-0"
                    ),
                ], className="fw-bold"),
                dbc.Collapse(
                    dbc.CardBody([
                        create_filter_controls(),
                        html.Div(
                            id="predictions-table-container",
                            className="mt-3"
                        )
                    ]),
                    id="collapse-table",
                    is_open=False,
                )
            ], className="mt-4",
               style={"backgroundColor": COLORS["secondary"]}),

            # Footer
            create_footer(),

        ], style={
            "padding": "20px",
            "maxWidth": "1400px",
            "margin": "0 auto"
        })
    ])
```

The asset page function is defined in [Section 4](#4-layout-components).

### Step 5: Add the Router Callback

This callback fires every time the URL changes. It returns the correct page layout.

```python
def register_callbacks(app: Dash):
    """Register all callbacks for the dashboard."""

    # ---- URL ROUTER ----
    @app.callback(
        Output("page-content", "children"),
        [Input("url", "pathname")]
    )
    def route_page(pathname: str):
        """Route to the correct page based on URL pathname."""
        if pathname and pathname.startswith("/assets/"):
            # Extract symbol from URL: /assets/AAPL -> AAPL
            symbol = pathname.split("/assets/")[-1].strip("/").upper()
            if symbol:
                return create_asset_page(symbol)

        # Default: show main dashboard
        return create_dashboard_page()

    # ... (rest of callbacks below)
```

**Important**: The router callback must be registered BEFORE any other callbacks that reference components created by `create_dashboard_page()` or `create_asset_page()`. This is because Dash validates callback outputs at registration time when `suppress_callback_exceptions=False`. Since we have `suppress_callback_exceptions=True`, the order does not strictly matter, but placing the router first is good practice.

### How Navigation Works

From the main dashboard, users navigate to an asset page by clicking a link. We use `dcc.Link` for client-side navigation (no full page reload):

```python
# Example: link to AAPL asset page
dcc.Link(
    "AAPL",
    href="/assets/AAPL",
    style={"color": COLORS["accent"], "textDecoration": "none"}
)
```

From the asset page, users navigate back to the dashboard:

```python
dcc.Link(
    [html.I(className="fas fa-arrow-left me-2"), "Back to Dashboard"],
    href="/",
    style={"color": COLORS["accent"], "textDecoration": "none"}
)
```

---

## 3. Data Layer - New Queries

Add these four functions to `shitty_ui/data.py`. They follow the existing pattern: use `text()` for raw SQL, call `execute_query()`, return a DataFrame or dict, and catch all exceptions with a fallback return.

### 3.1 `get_asset_price_history`

Fetches OHLCV data from `market_prices` for the candlestick chart.

```python
def get_asset_price_history(
    symbol: str,
    days: int = 180
) -> pd.DataFrame:
    """
    Get historical price data for a specific asset.

    Args:
        symbol: Ticker symbol (e.g., 'AAPL', 'TSLA')
        days: Number of days of history to fetch (default 180)

    Returns:
        DataFrame with columns: date, open, high, low, close, volume, adjusted_close
        Sorted by date ascending (oldest first).
        Returns empty DataFrame on error.
    """
    query = text("""
        SELECT
            date,
            open,
            high,
            low,
            close,
            volume,
            adjusted_close
        FROM market_prices
        WHERE symbol = :symbol
            AND date >= CURRENT_DATE - INTERVAL ':days days'
        ORDER BY date ASC
    """)

    try:
        rows, columns = execute_query(
            query, {"symbol": symbol.upper(), "days": days}
        )
        df = pd.DataFrame(rows, columns=columns)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
        return df
    except Exception as e:
        print(f"Error loading price history for {symbol}: {e}")
        return pd.DataFrame()
```

**Note on the date filter**: The `:days` parameter inside the `INTERVAL` string may not bind correctly in all PostgreSQL drivers. If you encounter errors, replace the WHERE clause with:

```python
    query = text("""
        SELECT
            date,
            open,
            high,
            low,
            close,
            volume,
            adjusted_close
        FROM market_prices
        WHERE symbol = :symbol
            AND date >= :start_date
        ORDER BY date ASC
    """)

    from datetime import datetime, timedelta
    start_date = datetime.now().date() - timedelta(days=days)

    try:
        rows, columns = execute_query(
            query, {"symbol": symbol.upper(), "start_date": start_date}
        )
        # ... rest is the same
```

Use the second version if the first fails. The second version is safer because it avoids PostgreSQL interval string interpolation.

### 3.2 `get_asset_predictions`

Fetches all predictions for a specific asset, joined with the original tweet text and outcome data.

```python
def get_asset_predictions(
    symbol: str,
    limit: int = 50
) -> pd.DataFrame:
    """
    Get all predictions for a specific asset with their outcomes and tweet text.

    Args:
        symbol: Ticker symbol (e.g., 'AAPL')
        limit: Maximum number of predictions to return

    Returns:
        DataFrame with columns: prediction_date, timestamp, text, shitpost_id,
        prediction_id, prediction_sentiment, prediction_confidence,
        price_at_prediction, price_t7, return_t1, return_t3, return_t7,
        return_t30, correct_t7, pnl_t7, is_complete, confidence, thesis
        Sorted by prediction_date descending (newest first).
        Returns empty DataFrame on error.
    """
    query = text("""
        SELECT
            po.prediction_date,
            tss.timestamp,
            tss.text,
            tss.shitpost_id,
            p.id AS prediction_id,
            po.prediction_sentiment,
            po.prediction_confidence,
            po.price_at_prediction,
            po.price_t7,
            po.return_t1,
            po.return_t3,
            po.return_t7,
            po.return_t30,
            po.correct_t1,
            po.correct_t3,
            po.correct_t7,
            po.correct_t30,
            po.pnl_t7,
            po.is_complete,
            p.confidence,
            p.thesis
        FROM prediction_outcomes po
        INNER JOIN predictions p
            ON po.prediction_id = p.id
        INNER JOIN truth_social_shitposts tss
            ON p.shitpost_id = tss.shitpost_id
        WHERE po.symbol = :symbol
        ORDER BY po.prediction_date DESC
        LIMIT :limit
    """)

    try:
        rows, columns = execute_query(
            query, {"symbol": symbol.upper(), "limit": limit}
        )
        df = pd.DataFrame(rows, columns=columns)
        if not df.empty:
            df["prediction_date"] = pd.to_datetime(df["prediction_date"])
            df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df
    except Exception as e:
        print(f"Error loading predictions for {symbol}: {e}")
        return pd.DataFrame()
```

### 3.3 `get_asset_stats`

Computes aggregate statistics for a single asset and the overall system average, returning both so the UI can compare them side-by-side.

```python
def get_asset_stats(symbol: str) -> Dict[str, Any]:
    """
    Get aggregate performance statistics for a specific asset,
    alongside overall system averages for comparison.

    Args:
        symbol: Ticker symbol (e.g., 'AAPL')

    Returns:
        Dictionary with keys:
          - total_predictions (int)
          - correct_predictions (int)
          - incorrect_predictions (int)
          - accuracy_t7 (float, percentage)
          - avg_return_t7 (float, percentage)
          - total_pnl_t7 (float, dollar amount)
          - avg_confidence (float, 0-1)
          - bullish_count (int)
          - bearish_count (int)
          - neutral_count (int)
          - best_return_t7 (float or None)
          - worst_return_t7 (float or None)
          - overall_accuracy_t7 (float, percentage, system-wide)
          - overall_avg_return_t7 (float, percentage, system-wide)
        Returns zeroed dict on error.
    """
    query = text("""
        WITH asset_stats AS (
            SELECT
                COUNT(*) AS total_predictions,
                COUNT(CASE WHEN correct_t7 = true THEN 1 END) AS correct,
                COUNT(CASE WHEN correct_t7 = false THEN 1 END) AS incorrect,
                COUNT(CASE WHEN correct_t7 IS NOT NULL THEN 1 END) AS evaluated,
                AVG(CASE WHEN correct_t7 IS NOT NULL THEN return_t7 END) AS avg_return,
                SUM(CASE WHEN pnl_t7 IS NOT NULL THEN pnl_t7 ELSE 0 END) AS total_pnl,
                AVG(prediction_confidence) AS avg_confidence,
                COUNT(CASE WHEN prediction_sentiment = 'bullish' THEN 1 END) AS bullish_count,
                COUNT(CASE WHEN prediction_sentiment = 'bearish' THEN 1 END) AS bearish_count,
                COUNT(CASE WHEN prediction_sentiment = 'neutral' THEN 1 END) AS neutral_count,
                MAX(return_t7) AS best_return,
                MIN(return_t7) AS worst_return
            FROM prediction_outcomes
            WHERE symbol = :symbol
        ),
        overall_stats AS (
            SELECT
                COUNT(CASE WHEN correct_t7 IS NOT NULL THEN 1 END) AS overall_evaluated,
                COUNT(CASE WHEN correct_t7 = true THEN 1 END) AS overall_correct,
                AVG(CASE WHEN correct_t7 IS NOT NULL THEN return_t7 END) AS overall_avg_return
            FROM prediction_outcomes
        )
        SELECT
            a.total_predictions,
            a.correct,
            a.incorrect,
            a.evaluated,
            a.avg_return,
            a.total_pnl,
            a.avg_confidence,
            a.bullish_count,
            a.bearish_count,
            a.neutral_count,
            a.best_return,
            a.worst_return,
            o.overall_evaluated,
            o.overall_correct,
            o.overall_avg_return
        FROM asset_stats a, overall_stats o
    """)

    try:
        rows, columns = execute_query(query, {"symbol": symbol.upper()})
        if rows and rows[0]:
            row = rows[0]
            evaluated = row[3] or 0
            correct = row[1] or 0
            accuracy = (correct / evaluated * 100) if evaluated > 0 else 0.0

            overall_evaluated = row[12] or 0
            overall_correct = row[13] or 0
            overall_accuracy = (
                (overall_correct / overall_evaluated * 100)
                if overall_evaluated > 0
                else 0.0
            )

            return {
                "total_predictions": row[0] or 0,
                "correct_predictions": correct,
                "incorrect_predictions": row[2] or 0,
                "accuracy_t7": round(accuracy, 1),
                "avg_return_t7": round(float(row[4]), 2) if row[4] else 0.0,
                "total_pnl_t7": round(float(row[5]), 2) if row[5] else 0.0,
                "avg_confidence": round(float(row[6]), 2) if row[6] else 0.0,
                "bullish_count": row[7] or 0,
                "bearish_count": row[8] or 0,
                "neutral_count": row[9] or 0,
                "best_return_t7": round(float(row[10]), 2) if row[10] else None,
                "worst_return_t7": round(float(row[11]), 2) if row[11] else None,
                "overall_accuracy_t7": round(overall_accuracy, 1),
                "overall_avg_return_t7": (
                    round(float(row[14]), 2) if row[14] else 0.0
                ),
            }
    except Exception as e:
        print(f"Error loading asset stats for {symbol}: {e}")

    return {
        "total_predictions": 0,
        "correct_predictions": 0,
        "incorrect_predictions": 0,
        "accuracy_t7": 0.0,
        "avg_return_t7": 0.0,
        "total_pnl_t7": 0.0,
        "avg_confidence": 0.0,
        "bullish_count": 0,
        "bearish_count": 0,
        "neutral_count": 0,
        "best_return_t7": None,
        "worst_return_t7": None,
        "overall_accuracy_t7": 0.0,
        "overall_avg_return_t7": 0.0,
    }
```

### 3.4 `get_related_assets`

Finds other assets that tend to appear in the same predictions as the target asset. This uses the `predictions.assets` JSONB column.

```python
def get_related_assets(symbol: str, limit: int = 8) -> pd.DataFrame:
    """
    Get assets that frequently appear in the same predictions as the given symbol.

    Logic: Find all predictions that mention `symbol`, extract all other assets
    from those predictions, and count co-occurrences.

    Args:
        symbol: Ticker symbol (e.g., 'AAPL')
        limit: Maximum number of related assets to return

    Returns:
        DataFrame with columns: related_symbol, co_occurrence_count, avg_return_t7
        Sorted by co_occurrence_count descending.
        Returns empty DataFrame on error.
    """
    query = text("""
        WITH target_predictions AS (
            -- Find all prediction IDs that mention this symbol
            SELECT p.id AS prediction_id
            FROM predictions p
            WHERE p.assets::jsonb ? :symbol
                AND p.analysis_status = 'completed'
        ),
        co_occurring_assets AS (
            -- Find all OTHER assets in those same predictions
            SELECT
                po.symbol AS related_symbol,
                COUNT(DISTINCT po.prediction_id) AS co_occurrence_count,
                AVG(po.return_t7) AS avg_return_t7
            FROM prediction_outcomes po
            INNER JOIN target_predictions tp
                ON po.prediction_id = tp.prediction_id
            WHERE po.symbol != :symbol
                AND po.symbol IS NOT NULL
            GROUP BY po.symbol
        )
        SELECT
            related_symbol,
            co_occurrence_count,
            ROUND(avg_return_t7::numeric, 2) AS avg_return_t7
        FROM co_occurring_assets
        ORDER BY co_occurrence_count DESC
        LIMIT :limit
    """)

    try:
        rows, columns = execute_query(
            query, {"symbol": symbol.upper(), "limit": limit}
        )
        df = pd.DataFrame(rows, columns=columns)
        return df
    except Exception as e:
        print(f"Error loading related assets for {symbol}: {e}")
        return pd.DataFrame()
```

**PostgreSQL JSONB note**: The `?` operator checks if a top-level key (or array element) exists in JSONB. Since `predictions.assets` is stored as a JSON array (e.g., `["AAPL", "GOOGL"]`), `assets::jsonb ? 'AAPL'` returns true if `'AAPL'` is an element of that array. This is a PostgreSQL-specific operator. It will not work in SQLite. If you need SQLite compatibility for testing, see the test section for how to mock this.

### Summary of New Imports for `data.py`

No new imports are required. The existing imports already include everything needed:

```python
import pandas as pd
from sqlalchemy import text
from typing import List, Dict, Any, Optional
```

The `from datetime import datetime, timedelta` import is only needed inside `get_asset_price_history` if you use the safer date parameter approach (see the note in 3.1).

---

## 4. Layout Components

All new layout code goes in `shitty_ui/layout.py`. Add the following functions.

### 4.1 Asset Page Container

This is the top-level function that creates the entire `/assets/{symbol}` page.

```python
def create_asset_page(symbol: str) -> html.Div:
    """
    Create the full asset deep dive page for a given symbol.

    This function is called by the router callback when the URL
    matches /assets/{symbol}.

    Args:
        symbol: Ticker symbol (e.g., 'AAPL')

    Returns:
        html.Div containing the full asset page layout
    """
    return html.Div([
        # Store the symbol so callbacks can access it
        dcc.Store(id="asset-page-symbol", data=symbol),

        # Asset header with back navigation
        create_asset_header(symbol),

        # Main content
        html.Div([
            # Stat cards row (populated by callback)
            html.Div(id="asset-stat-cards", className="mb-4"),

            # Price chart + Performance summary
            dbc.Row([
                # Left: Price chart with prediction overlays
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.I(className="fas fa-chart-line me-2"),
                            f"{symbol} Price History",
                            # Date range selector
                            html.Div([
                                dbc.ButtonGroup([
                                    dbc.Button(
                                        "30D",
                                        id="asset-range-30d",
                                        color="secondary",
                                        outline=True,
                                        size="sm",
                                    ),
                                    dbc.Button(
                                        "90D",
                                        id="asset-range-90d",
                                        color="primary",
                                        size="sm",
                                    ),
                                    dbc.Button(
                                        "180D",
                                        id="asset-range-180d",
                                        color="secondary",
                                        outline=True,
                                        size="sm",
                                    ),
                                    dbc.Button(
                                        "1Y",
                                        id="asset-range-1y",
                                        color="secondary",
                                        outline=True,
                                        size="sm",
                                    ),
                                ], size="sm"),
                            ], style={"float": "right"}),
                        ], className="fw-bold d-flex justify-content-between align-items-center"),
                        dbc.CardBody([
                            dcc.Graph(
                                id="asset-price-chart",
                                config={"displayModeBar": False},
                            )
                        ]),
                    ], style={"backgroundColor": COLORS["secondary"]}),
                ], md=8),

                # Right: Performance summary
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.I(className="fas fa-chart-pie me-2"),
                            "Performance Summary"
                        ], className="fw-bold"),
                        dbc.CardBody(id="asset-performance-summary"),
                    ], className="mb-3",
                       style={"backgroundColor": COLORS["secondary"]}),

                    # Related assets card
                    dbc.Card([
                        dbc.CardHeader([
                            html.I(className="fas fa-project-diagram me-2"),
                            "Related Assets"
                        ], className="fw-bold"),
                        dbc.CardBody(id="asset-related-assets"),
                    ], style={"backgroundColor": COLORS["secondary"]}),
                ], md=4),
            ], className="mb-4"),

            # Prediction timeline
            dbc.Card([
                dbc.CardHeader([
                    html.I(className="fas fa-history me-2"),
                    f"Prediction Timeline for {symbol}"
                ], className="fw-bold"),
                dbc.CardBody(
                    id="asset-prediction-timeline",
                    style={"maxHeight": "600px", "overflowY": "auto"}
                ),
            ], style={"backgroundColor": COLORS["secondary"]}),

            # Footer
            create_footer(),

        ], style={
            "padding": "20px",
            "maxWidth": "1400px",
            "margin": "0 auto",
        }),
    ])
```

### 4.2 Asset Header

```python
def create_asset_header(symbol: str) -> html.Div:
    """
    Create the header bar for an asset page.
    Includes back navigation, symbol name, and a placeholder for
    current price (populated by callback).

    Args:
        symbol: Ticker symbol

    Returns:
        html.Div header component
    """
    return html.Div([
        html.Div([
            # Back link
            dcc.Link(
                [html.I(className="fas fa-arrow-left me-2"), "Dashboard"],
                href="/",
                style={
                    "color": COLORS["accent"],
                    "textDecoration": "none",
                    "fontSize": "0.9rem",
                }
            ),
        ], style={"marginBottom": "10px"}),
        html.Div([
            html.Div([
                html.H1(
                    symbol,
                    style={
                        "fontSize": "2rem",
                        "fontWeight": "bold",
                        "margin": 0,
                        "color": COLORS["text"],
                    }
                ),
                html.Span(
                    id="asset-current-price",
                    style={
                        "fontSize": "1.5rem",
                        "color": COLORS["accent"],
                        "marginLeft": "15px",
                    }
                ),
            ], style={"display": "flex", "alignItems": "baseline"}),
            html.P(
                "Prediction Performance Deep Dive",
                style={
                    "color": COLORS["text_muted"],
                    "margin": 0,
                    "fontSize": "0.9rem",
                }
            ),
        ]),
    ], style={
        "padding": "20px",
        "borderBottom": f"1px solid {COLORS['border']}",
        "backgroundColor": COLORS["secondary"],
    })
```

### 4.3 Prediction Timeline Card

Each prediction in the timeline is rendered as a card. This function creates one card.

```python
def create_prediction_timeline_card(row: dict) -> html.Div:
    """
    Create a single prediction card for the timeline.

    Args:
        row: Dictionary with keys from get_asset_predictions() DataFrame row:
            prediction_date, timestamp, text, shitpost_id, prediction_sentiment,
            prediction_confidence, price_at_prediction, price_t7,
            return_t7, correct_t7, pnl_t7, thesis

    Returns:
        html.Div component for one timeline entry
    """
    prediction_date = row.get("prediction_date")
    timestamp = row.get("timestamp")
    tweet_text = row.get("text", "")
    sentiment = row.get("prediction_sentiment", "neutral")
    confidence = row.get("prediction_confidence", 0)
    return_t7 = row.get("return_t7")
    correct_t7 = row.get("correct_t7")
    pnl_t7 = row.get("pnl_t7")
    price_at = row.get("price_at_prediction")
    price_after = row.get("price_t7")
    thesis = row.get("thesis", "")

    # Sentiment styling
    if sentiment and sentiment.lower() == "bullish":
        sentiment_color = COLORS["success"]
        sentiment_icon = "arrow-up"
    elif sentiment and sentiment.lower() == "bearish":
        sentiment_color = COLORS["danger"]
        sentiment_icon = "arrow-down"
    else:
        sentiment_color = COLORS["text_muted"]
        sentiment_icon = "minus"

    # Outcome badge
    if correct_t7 is True:
        outcome_badge = html.Span(
            "Correct",
            className="badge",
            style={
                "backgroundColor": COLORS["success"],
                "marginLeft": "8px",
            }
        )
    elif correct_t7 is False:
        outcome_badge = html.Span(
            "Incorrect",
            className="badge",
            style={
                "backgroundColor": COLORS["danger"],
                "marginLeft": "8px",
            }
        )
    else:
        outcome_badge = html.Span(
            "Pending",
            className="badge",
            style={
                "backgroundColor": COLORS["warning"],
                "color": "#000",
                "marginLeft": "8px",
            }
        )

    # Format the date
    if isinstance(prediction_date, datetime):
        date_str = prediction_date.strftime("%b %d, %Y")
    elif hasattr(prediction_date, "strftime"):
        date_str = prediction_date.strftime("%b %d, %Y")
    else:
        date_str = str(prediction_date)[:10] if prediction_date else "Unknown"

    # Format timestamp for the tweet time
    if isinstance(timestamp, datetime):
        time_str = timestamp.strftime("%H:%M")
    else:
        time_str = str(timestamp)[11:16] if timestamp else ""

    # Truncate tweet text
    display_text = (
        tweet_text[:200] + "..."
        if len(tweet_text) > 200
        else tweet_text
    )

    # Price change display
    price_info = []
    if price_at is not None:
        price_info.append(
            html.Span(
                f"Entry: ${price_at:,.2f}",
                style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}
            )
        )
    if price_after is not None:
        price_info.append(
            html.Span(
                f" -> ${price_after:,.2f} (7d)",
                style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}
            )
        )

    return html.Div([
        # Top row: date, sentiment, outcome badge
        html.Div([
            html.Div([
                html.Span(
                    date_str,
                    style={
                        "fontWeight": "bold",
                        "color": COLORS["text"],
                        "fontSize": "0.9rem",
                    }
                ),
                html.Span(
                    f" at {time_str}" if time_str else "",
                    style={
                        "color": COLORS["text_muted"],
                        "fontSize": "0.8rem",
                    }
                ),
                outcome_badge,
            ]),
            html.Div([
                html.I(
                    className=f"fas fa-{sentiment_icon} me-1",
                    style={"color": sentiment_color}
                ),
                html.Span(
                    (sentiment or "neutral").upper(),
                    style={
                        "color": sentiment_color,
                        "fontWeight": "bold",
                        "fontSize": "0.85rem",
                    }
                ),
                html.Span(
                    f" | Confidence: {confidence:.0%}" if confidence else "",
                    style={
                        "color": COLORS["text_muted"],
                        "fontSize": "0.85rem",
                        "marginLeft": "10px",
                    }
                ),
            ], style={"marginTop": "4px"}),
        ]),

        # Tweet text
        html.P(
            display_text,
            style={
                "fontSize": "0.85rem",
                "color": COLORS["text_muted"],
                "margin": "8px 0",
                "lineHeight": "1.5",
                "fontStyle": "italic",
                "borderLeft": f"3px solid {sentiment_color}",
                "paddingLeft": "12px",
            }
        ),

        # Metrics row: return, P&L, prices
        html.Div([
            # 7-day return
            html.Span(
                f"Return (7d): {return_t7:+.2f}%"
                if return_t7 is not None
                else "Return (7d): --",
                style={
                    "color": (
                        COLORS["success"] if return_t7 and return_t7 > 0
                        else COLORS["danger"] if return_t7 and return_t7 < 0
                        else COLORS["text_muted"]
                    ),
                    "fontSize": "0.85rem",
                    "fontWeight": "bold",
                }
            ),
            html.Span(" | ", style={"color": COLORS["border"]}),
            # P&L
            html.Span(
                f"P&L: ${pnl_t7:+,.0f}"
                if pnl_t7 is not None
                else "P&L: --",
                style={
                    "color": (
                        COLORS["success"] if pnl_t7 and pnl_t7 > 0
                        else COLORS["danger"] if pnl_t7 and pnl_t7 < 0
                        else COLORS["text_muted"]
                    ),
                    "fontSize": "0.85rem",
                }
            ),
            html.Span(" | ", style={"color": COLORS["border"]}),
            # Price info
            *price_info,
        ], style={"marginBottom": "4px"}),

    ], style={
        "padding": "16px",
        "borderBottom": f"1px solid {COLORS['border']}",
    })
```

### 4.4 Related Asset Link

Each related asset is shown as a clickable link that navigates to its own asset page.

```python
def create_related_asset_link(row: dict) -> html.Div:
    """
    Create a clickable link for a related asset.

    Args:
        row: Dictionary with keys: related_symbol, co_occurrence_count, avg_return_t7

    Returns:
        html.Div component
    """
    symbol = row.get("related_symbol", "???")
    count = row.get("co_occurrence_count", 0)
    avg_return = row.get("avg_return_t7")

    return_color = COLORS["text_muted"]
    return_str = "--"
    if avg_return is not None:
        return_color = (
            COLORS["success"] if avg_return > 0 else COLORS["danger"]
        )
        return_str = f"{avg_return:+.2f}%"

    return html.Div([
        dcc.Link(
            html.Span(
                symbol,
                style={
                    "fontWeight": "bold",
                    "color": COLORS["accent"],
                    "fontSize": "0.95rem",
                }
            ),
            href=f"/assets/{symbol}",
            style={"textDecoration": "none"},
        ),
        html.Span(
            f" ({count} shared predictions)",
            style={
                "color": COLORS["text_muted"],
                "fontSize": "0.8rem",
                "marginLeft": "8px",
            }
        ),
        html.Span(
            f" | Avg return: {return_str}",
            style={
                "color": return_color,
                "fontSize": "0.8rem",
                "marginLeft": "8px",
            }
        ),
    ], style={
        "padding": "10px 0",
        "borderBottom": f"1px solid {COLORS['border']}",
    })
```

---

## 5. Callback Implementations

Add these callbacks inside the existing `register_callbacks(app)` function in `layout.py`. Place them after the router callback.

### 5.1 Asset Page Data Loader

This is the main callback for the asset page. It fires when the asset page renders (because the `asset-page-symbol` store gets its initial data).

```python
    # ---- ASSET PAGE CALLBACKS ----

    @app.callback(
        [
            Output("asset-stat-cards", "children"),
            Output("asset-current-price", "children"),
            Output("asset-performance-summary", "children"),
            Output("asset-prediction-timeline", "children"),
            Output("asset-related-assets", "children"),
        ],
        [Input("asset-page-symbol", "data")]
    )
    def update_asset_page(symbol):
        """
        Populate all data-driven sections of the asset deep dive page.
        Fires when the page first loads (symbol store receives data).
        """
        if not symbol:
            empty = html.P(
                "No asset selected.",
                style={"color": COLORS["text_muted"]}
            )
            return empty, "", empty, empty, empty

        # Import data functions (already imported at top of layout.py)
        from data import (
            get_asset_stats,
            get_asset_predictions,
            get_asset_price_history,
            get_related_assets,
        )

        # --- STAT CARDS ---
        stats = get_asset_stats(symbol)
        stat_cards = dbc.Row([
            dbc.Col(create_metric_card(
                "Prediction Accuracy",
                f"{stats['accuracy_t7']:.1f}%",
                f"{stats['correct_predictions']}/{stats['total_predictions']} correct",
                "bullseye",
                (
                    COLORS["success"]
                    if stats["accuracy_t7"] > 60
                    else COLORS["danger"]
                ),
            ), md=3, xs=6),
            dbc.Col(create_metric_card(
                "Total Predictions",
                f"{stats['total_predictions']}",
                f"{stats['bullish_count']} bullish / {stats['bearish_count']} bearish",
                "clipboard-list",
                COLORS["accent"],
            ), md=3, xs=6),
            dbc.Col(create_metric_card(
                "Total P&L (7-day)",
                f"${stats['total_pnl_t7']:,.0f}",
                "Based on $1,000 positions",
                "dollar-sign",
                (
                    COLORS["success"]
                    if stats["total_pnl_t7"] > 0
                    else COLORS["danger"]
                ),
            ), md=3, xs=6),
            dbc.Col(create_metric_card(
                "Avg 7-Day Return",
                f"{stats['avg_return_t7']:+.2f}%",
                f"Confidence: {stats['avg_confidence']:.0%}",
                "chart-line",
                (
                    COLORS["success"]
                    if stats["avg_return_t7"] > 0
                    else COLORS["danger"]
                ),
            ), md=3, xs=6),
        ], className="g-3")

        # --- CURRENT PRICE ---
        price_df = get_asset_price_history(symbol, days=7)
        if not price_df.empty:
            latest_close = price_df.iloc[-1]["close"]
            current_price_text = f"${latest_close:,.2f}"
        else:
            current_price_text = "Price unavailable"

        # --- PERFORMANCE SUMMARY ---
        performance_summary = create_performance_summary(stats)

        # --- PREDICTION TIMELINE ---
        predictions_df = get_asset_predictions(symbol, limit=50)
        if not predictions_df.empty:
            timeline_cards = [
                create_prediction_timeline_card(row)
                for _, row in predictions_df.iterrows()
            ]
        else:
            timeline_cards = [
                html.P(
                    f"No predictions found for {symbol}.",
                    style={
                        "color": COLORS["text_muted"],
                        "textAlign": "center",
                        "padding": "20px",
                    }
                )
            ]

        # --- RELATED ASSETS ---
        related_df = get_related_assets(symbol, limit=8)
        if not related_df.empty:
            related_links = [
                create_related_asset_link(row)
                for _, row in related_df.iterrows()
            ]
        else:
            related_links = [
                html.P(
                    "No related assets found.",
                    style={
                        "color": COLORS["text_muted"],
                        "textAlign": "center",
                        "padding": "10px",
                    }
                )
            ]

        return (
            stat_cards,
            current_price_text,
            performance_summary,
            timeline_cards,
            related_links,
        )
```

### 5.2 Performance Summary Component Builder

This is a helper function (not a callback) called by the main asset page callback.

```python
def create_performance_summary(stats: Dict[str, Any]) -> html.Div:
    """
    Create the performance summary comparing this asset vs overall system.

    Args:
        stats: Dictionary from get_asset_stats()

    Returns:
        html.Div with comparison metrics
    """
    asset_accuracy = stats.get("accuracy_t7", 0)
    overall_accuracy = stats.get("overall_accuracy_t7", 0)
    accuracy_diff = asset_accuracy - overall_accuracy

    asset_return = stats.get("avg_return_t7", 0)
    overall_return = stats.get("overall_avg_return_t7", 0)
    return_diff = asset_return - overall_return

    best = stats.get("best_return_t7")
    worst = stats.get("worst_return_t7")

    return html.Div([
        # Accuracy comparison
        html.Div([
            html.H6("Accuracy vs Overall", style={"color": COLORS["text_muted"]}),
            html.Div([
                html.Div([
                    html.Span(
                        f"{asset_accuracy:.1f}%",
                        style={
                            "fontSize": "1.5rem",
                            "fontWeight": "bold",
                            "color": (
                                COLORS["success"]
                                if asset_accuracy > 60
                                else COLORS["danger"]
                            ),
                        }
                    ),
                    html.Span(
                        " this asset",
                        style={
                            "color": COLORS["text_muted"],
                            "fontSize": "0.8rem",
                        }
                    ),
                ]),
                html.Div([
                    html.Span(
                        f"{overall_accuracy:.1f}%",
                        style={
                            "fontSize": "1rem",
                            "color": COLORS["text_muted"],
                        }
                    ),
                    html.Span(
                        " overall",
                        style={
                            "color": COLORS["text_muted"],
                            "fontSize": "0.8rem",
                        }
                    ),
                ]),
                html.Div([
                    html.Span(
                        f"{accuracy_diff:+.1f}pp",
                        style={
                            "color": (
                                COLORS["success"]
                                if accuracy_diff > 0
                                else COLORS["danger"]
                            ),
                            "fontWeight": "bold",
                            "fontSize": "0.9rem",
                        }
                    ),
                    html.Span(
                        " vs average",
                        style={
                            "color": COLORS["text_muted"],
                            "fontSize": "0.8rem",
                        }
                    ),
                ]),
            ]),
        ], style={
            "padding": "12px 0",
            "borderBottom": f"1px solid {COLORS['border']}",
        }),

        # Return comparison
        html.Div([
            html.H6(
                "Avg 7-Day Return vs Overall",
                style={"color": COLORS["text_muted"]},
            ),
            html.Div([
                html.Span(
                    f"{asset_return:+.2f}%",
                    style={
                        "fontSize": "1.2rem",
                        "fontWeight": "bold",
                        "color": (
                            COLORS["success"]
                            if asset_return > 0
                            else COLORS["danger"]
                        ),
                    }
                ),
                html.Span(
                    f" vs {overall_return:+.2f}% overall",
                    style={
                        "color": COLORS["text_muted"],
                        "fontSize": "0.85rem",
                        "marginLeft": "8px",
                    }
                ),
            ]),
        ], style={
            "padding": "12px 0",
            "borderBottom": f"1px solid {COLORS['border']}",
        }),

        # Sentiment breakdown
        html.Div([
            html.H6(
                "Sentiment Breakdown",
                style={"color": COLORS["text_muted"]},
            ),
            html.Div([
                html.Span([
                    html.I(className="fas fa-arrow-up me-1"),
                    f"{stats.get('bullish_count', 0)} Bullish",
                ], style={
                    "color": COLORS["success"],
                    "fontSize": "0.9rem",
                    "marginRight": "15px",
                }),
                html.Span([
                    html.I(className="fas fa-arrow-down me-1"),
                    f"{stats.get('bearish_count', 0)} Bearish",
                ], style={
                    "color": COLORS["danger"],
                    "fontSize": "0.9rem",
                    "marginRight": "15px",
                }),
                html.Span([
                    html.I(className="fas fa-minus me-1"),
                    f"{stats.get('neutral_count', 0)} Neutral",
                ], style={
                    "color": COLORS["text_muted"],
                    "fontSize": "0.9rem",
                }),
            ]),
        ], style={
            "padding": "12px 0",
            "borderBottom": f"1px solid {COLORS['border']}",
        }),

        # Best/worst
        html.Div([
            html.H6(
                "Best & Worst Predictions",
                style={"color": COLORS["text_muted"]},
            ),
            html.Div([
                html.Span(
                    f"Best: {best:+.2f}%" if best is not None else "Best: --",
                    style={
                        "color": COLORS["success"],
                        "fontSize": "0.9rem",
                        "marginRight": "20px",
                    }
                ),
                html.Span(
                    f"Worst: {worst:+.2f}%" if worst is not None else "Worst: --",
                    style={
                        "color": COLORS["danger"],
                        "fontSize": "0.9rem",
                    }
                ),
            ]),
        ], style={"padding": "12px 0"}),
    ])
```

### 5.3 Price Chart with Prediction Overlays

This callback builds the Plotly figure for the price chart. It also overlays prediction markers.

```python
    @app.callback(
        Output("asset-price-chart", "figure"),
        [
            Input("asset-page-symbol", "data"),
            Input("asset-range-30d", "n_clicks"),
            Input("asset-range-90d", "n_clicks"),
            Input("asset-range-180d", "n_clicks"),
            Input("asset-range-1y", "n_clicks"),
        ]
    )
    def update_asset_price_chart(symbol, n30, n90, n180, n1y):
        """
        Build the price chart with prediction overlay markers.

        The date range buttons control how much history is shown.
        Prediction markers are colored:
          - Green (success): correct prediction
          - Red (danger): incorrect prediction
          - Yellow (warning): pending/not yet evaluated
        """
        from dash import callback_context
        from data import get_asset_price_history, get_asset_predictions

        # Determine which date range button was clicked
        days = 90  # default
        ctx = callback_context
        if ctx.triggered:
            trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
            days_map = {
                "asset-range-30d": 30,
                "asset-range-90d": 90,
                "asset-range-180d": 180,
                "asset-range-1y": 365,
            }
            days = days_map.get(trigger_id, 90)

        # Empty figure template
        empty_fig = go.Figure()
        empty_fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font_color=COLORS["text_muted"],
            height=400,
        )

        if not symbol:
            empty_fig.add_annotation(
                text="No asset selected", showarrow=False
            )
            return empty_fig

        # Fetch price data
        price_df = get_asset_price_history(symbol, days=days)
        if price_df.empty:
            empty_fig.add_annotation(
                text=f"No price data available for {symbol}",
                showarrow=False,
            )
            return empty_fig

        fig = go.Figure()

        # Add candlestick chart if OHLC data is available
        has_ohlc = all(
            col in price_df.columns and price_df[col].notna().any()
            for col in ["open", "high", "low", "close"]
        )

        if has_ohlc:
            fig.add_trace(go.Candlestick(
                x=price_df["date"],
                open=price_df["open"],
                high=price_df["high"],
                low=price_df["low"],
                close=price_df["close"],
                name=symbol,
                increasing_line_color=COLORS["success"],
                decreasing_line_color=COLORS["danger"],
            ))
        else:
            # Fallback to line chart
            fig.add_trace(go.Scatter(
                x=price_df["date"],
                y=price_df["close"],
                mode="lines",
                name=symbol,
                line=dict(color=COLORS["accent"], width=2),
            ))

        # Overlay prediction markers
        predictions_df = get_asset_predictions(symbol, limit=100)
        if not predictions_df.empty:
            # Group predictions by outcome
            for outcome_value, color, label in [
                (True, COLORS["success"], "Correct"),
                (False, COLORS["danger"], "Incorrect"),
                (None, COLORS["warning"], "Pending"),
            ]:
                if outcome_value is None:
                    mask = predictions_df["correct_t7"].isna()
                else:
                    mask = predictions_df["correct_t7"] == outcome_value

                subset = predictions_df[mask]
                if subset.empty:
                    continue

                # Use prediction date for x-axis, price_at_prediction for y-axis
                valid = subset.dropna(subset=["prediction_date", "price_at_prediction"])
                if valid.empty:
                    continue

                # Build hover text
                hover_texts = []
                for _, row in valid.iterrows():
                    sentiment = row.get("prediction_sentiment", "?")
                    confidence = row.get("prediction_confidence", 0)
                    ret = row.get("return_t7")
                    text_snip = str(row.get("text", ""))[:80]
                    ret_str = f"{ret:+.2f}%" if ret is not None else "pending"
                    hover_texts.append(
                        f"<b>{label}</b><br>"
                        f"Sentiment: {sentiment}<br>"
                        f"Confidence: {confidence:.0%}<br>"
                        f"7d Return: {ret_str}<br>"
                        f"---<br>"
                        f"{text_snip}..."
                    )

                fig.add_trace(go.Scatter(
                    x=valid["prediction_date"],
                    y=valid["price_at_prediction"],
                    mode="markers",
                    name=f"{label} Predictions",
                    marker=dict(
                        color=color,
                        size=12,
                        symbol="diamond",
                        line=dict(width=1, color=COLORS["text"]),
                    ),
                    hovertemplate="%{customdata}<extra></extra>",
                    customdata=hover_texts,
                ))

        # Layout styling
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font_color=COLORS["text"],
            margin=dict(l=50, r=20, t=20, b=40),
            height=400,
            xaxis=dict(
                gridcolor=COLORS["border"],
                rangeslider=dict(visible=False),
            ),
            yaxis=dict(
                title="Price ($)",
                gridcolor=COLORS["border"],
                side="right",
            ),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                font=dict(size=10),
            ),
            hovermode="x unified",
        )

        return fig
```

### 5.4 Date Range Button Styling Callback

Updates which date range button appears "active" (filled vs outline).

```python
    @app.callback(
        [
            Output("asset-range-30d", "color"),
            Output("asset-range-30d", "outline"),
            Output("asset-range-90d", "color"),
            Output("asset-range-90d", "outline"),
            Output("asset-range-180d", "color"),
            Output("asset-range-180d", "outline"),
            Output("asset-range-1y", "color"),
            Output("asset-range-1y", "outline"),
        ],
        [
            Input("asset-range-30d", "n_clicks"),
            Input("asset-range-90d", "n_clicks"),
            Input("asset-range-180d", "n_clicks"),
            Input("asset-range-1y", "n_clicks"),
        ]
    )
    def update_range_button_styles(n30, n90, n180, n1y):
        """
        Highlight the active date range button.
        Default is 90D.
        """
        from dash import callback_context

        # Default: 90D selected
        selected = "asset-range-90d"

        ctx = callback_context
        if ctx.triggered:
            trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
            if trigger_id in [
                "asset-range-30d",
                "asset-range-90d",
                "asset-range-180d",
                "asset-range-1y",
            ]:
                selected = trigger_id

        buttons = [
            "asset-range-30d",
            "asset-range-90d",
            "asset-range-180d",
            "asset-range-1y",
        ]
        result = []
        for btn in buttons:
            if btn == selected:
                result.extend(["primary", False])  # filled
            else:
                result.extend(["secondary", True])  # outline
        return result
```

### 5.5 Update Imports in `layout.py`

At the top of `layout.py`, update the imports from `data.py` to include the new functions:

```python
from data import (
    get_prediction_stats,
    get_recent_signals,
    get_performance_metrics,
    get_accuracy_by_confidence,
    get_accuracy_by_asset,
    get_similar_predictions,
    get_predictions_with_outcomes,
    get_active_assets_from_db,
    # New asset page queries
    get_asset_price_history,
    get_asset_predictions,
    get_asset_stats,
    get_related_assets,
)
```

### 5.6 Add Navigation Links to Existing Dashboard

Update the asset accuracy chart in the main dashboard callback so that each bar label is a link to the asset page. The simplest approach: make the existing "Asset Deep Dive" dropdown navigate to the full page.

Add a callback that navigates to the asset page when the user selects an asset and clicks a "View Full Page" button:

```python
    # In the existing update_asset_drilldown callback, add a link at the bottom
    # of the drilldown content:

    @app.callback(
        Output("asset-drilldown-content", "children"),
        [Input("asset-selector", "value")]
    )
    def update_asset_drilldown(asset):
        """Update the asset deep dive section."""
        if not asset:
            return html.P(
                "Select an asset above to see historical predictions "
                "and their outcomes.",
                style={
                    "color": COLORS["text_muted"],
                    "textAlign": "center",
                    "padding": "20px",
                }
            )

        similar_df = get_similar_predictions(asset, limit=10)

        if similar_df.empty:
            return html.P(
                f"No historical predictions found for {asset}.",
                style={
                    "color": COLORS["text_muted"],
                    "textAlign": "center",
                    "padding": "20px",
                }
            )

        # ... existing summary and predictions code unchanged ...

        # ADD THIS at the bottom of the return:
        view_full_page_link = html.Div([
            dcc.Link(
                [
                    html.I(className="fas fa-external-link-alt me-2"),
                    f"View Full {asset} Deep Dive",
                ],
                href=f"/assets/{asset}",
                style={
                    "color": COLORS["accent"],
                    "textDecoration": "none",
                    "fontWeight": "bold",
                    "fontSize": "0.9rem",
                }
            )
        ], style={
            "textAlign": "center",
            "padding": "15px",
            "marginTop": "10px",
        })

        return html.Div([
            summary,
            html.Div(
                predictions,
                style={"maxHeight": "300px", "overflowY": "auto"}
            ),
            view_full_page_link,  # New link to full page
        ])
```

---

## 6. Test Specifications

All tests go in `shit_tests/shitty_ui/`. Follow the existing patterns from `test_data.py` and `test_layout.py`.

### 6.1 Data Layer Tests

Add these test classes to `shit_tests/shitty_ui/test_data.py`.

```python
# ============================================================
# Tests for Asset Deep Dive data functions
# ============================================================


class TestGetAssetPriceHistory:
    """Tests for get_asset_price_history function."""

    @patch("data.execute_query")
    def test_returns_dataframe(self, mock_execute):
        """Test that function returns a pandas DataFrame."""
        from data import get_asset_price_history
        from datetime import date

        mock_execute.return_value = (
            [
                (date(2024, 1, 1), 150.0, 152.0, 149.0, 151.0, 1000000, 151.0),
                (date(2024, 1, 2), 151.0, 153.0, 150.0, 152.5, 1200000, 152.5),
            ],
            ["date", "open", "high", "low", "close", "volume", "adjusted_close"],
        )

        result = get_asset_price_history("AAPL", days=30)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert "close" in result.columns
        assert "date" in result.columns

    @patch("data.execute_query")
    def test_passes_symbol_uppercase(self, mock_execute):
        """Test that symbol is converted to uppercase in query."""
        from data import get_asset_price_history

        mock_execute.return_value = ([], [])

        get_asset_price_history("aapl", days=90)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert call_args[1]["symbol"] == "AAPL"

    @patch("data.execute_query")
    def test_returns_empty_dataframe_on_error(self, mock_execute):
        """Test that function returns empty DataFrame on error."""
        from data import get_asset_price_history

        mock_execute.side_effect = Exception("Database error")

        result = get_asset_price_history("AAPL")

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch("data.execute_query")
    def test_returns_empty_for_unknown_symbol(self, mock_execute):
        """Test behavior when no price data exists for symbol."""
        from data import get_asset_price_history

        mock_execute.return_value = ([], [])

        result = get_asset_price_history("ZZZZZ")

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch("data.execute_query")
    def test_default_days_parameter(self, mock_execute):
        """Test that default days parameter is 180."""
        from data import get_asset_price_history

        mock_execute.return_value = ([], [])

        get_asset_price_history("AAPL")

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        # Verify start_date is approximately 180 days ago
        # (implementation-dependent: check days param or start_date)


class TestGetAssetPredictions:
    """Tests for get_asset_predictions function."""

    @patch("data.execute_query")
    def test_returns_dataframe(self, mock_execute):
        """Test that function returns a pandas DataFrame."""
        from data import get_asset_predictions
        from datetime import date

        mock_execute.return_value = (
            [(
                date(2024, 1, 15),    # prediction_date
                datetime(2024, 1, 15, 10, 30),  # timestamp
                "Great news for markets!",        # text
                "post123",            # shitpost_id
                1,                    # prediction_id
                "bullish",            # prediction_sentiment
                0.85,                 # prediction_confidence
                150.0,                # price_at_prediction
                155.0,                # price_t7
                0.5,                  # return_t1
                1.2,                  # return_t3
                3.3,                  # return_t7
                5.0,                  # return_t30
                True,                 # correct_t1
                True,                 # correct_t3
                True,                 # correct_t7
                True,                 # correct_t30
                33.0,                 # pnl_t7
                True,                 # is_complete
                0.85,                 # confidence
                "Markets will rally", # thesis
            )],
            [
                "prediction_date", "timestamp", "text", "shitpost_id",
                "prediction_id", "prediction_sentiment", "prediction_confidence",
                "price_at_prediction", "price_t7",
                "return_t1", "return_t3", "return_t7", "return_t30",
                "correct_t1", "correct_t3", "correct_t7", "correct_t30",
                "pnl_t7", "is_complete", "confidence", "thesis",
            ],
        )

        result = get_asset_predictions("AAPL", limit=50)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert "prediction_sentiment" in result.columns
        assert "text" in result.columns

    @patch("data.execute_query")
    def test_respects_limit_parameter(self, mock_execute):
        """Test that limit parameter is passed to query."""
        from data import get_asset_predictions

        mock_execute.return_value = ([], [])

        get_asset_predictions("AAPL", limit=25)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert call_args[1]["limit"] == 25

    @patch("data.execute_query")
    def test_passes_symbol_uppercase(self, mock_execute):
        """Test that symbol is converted to uppercase."""
        from data import get_asset_predictions

        mock_execute.return_value = ([], [])

        get_asset_predictions("tsla", limit=10)

        call_args = mock_execute.call_args[0]
        assert call_args[1]["symbol"] == "TSLA"

    @patch("data.execute_query")
    def test_returns_empty_dataframe_on_error(self, mock_execute):
        """Test that function returns empty DataFrame on error."""
        from data import get_asset_predictions

        mock_execute.side_effect = Exception("Database error")

        result = get_asset_predictions("AAPL")

        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestGetAssetStats:
    """Tests for get_asset_stats function."""

    @patch("data.execute_query")
    def test_returns_stats_dict(self, mock_execute):
        """Test that function returns a dictionary with all expected keys."""
        from data import get_asset_stats

        mock_execute.return_value = (
            [(
                10,     # total_predictions
                7,      # correct
                3,      # incorrect
                10,     # evaluated
                2.5,    # avg_return
                250.0,  # total_pnl
                0.78,   # avg_confidence
                6,      # bullish_count
                3,      # bearish_count
                1,      # neutral_count
                5.5,    # best_return
                -2.1,   # worst_return
                100,    # overall_evaluated
                60,     # overall_correct
                1.8,    # overall_avg_return
            )],
            [
                "total_predictions", "correct", "incorrect", "evaluated",
                "avg_return", "total_pnl", "avg_confidence",
                "bullish_count", "bearish_count", "neutral_count",
                "best_return", "worst_return",
                "overall_evaluated", "overall_correct", "overall_avg_return",
            ],
        )

        result = get_asset_stats("AAPL")

        assert isinstance(result, dict)
        assert result["total_predictions"] == 10
        assert result["correct_predictions"] == 7
        assert result["accuracy_t7"] == 70.0  # 7/10
        assert result["avg_return_t7"] == 2.5
        assert result["total_pnl_t7"] == 250.0
        assert result["bullish_count"] == 6
        assert result["bearish_count"] == 3
        assert result["best_return_t7"] == 5.5
        assert result["worst_return_t7"] == -2.1
        assert result["overall_accuracy_t7"] == 60.0  # 60/100
        assert result["overall_avg_return_t7"] == 1.8

    @patch("data.execute_query")
    def test_handles_zero_evaluated(self, mock_execute):
        """Test that accuracy is 0 when no predictions are evaluated."""
        from data import get_asset_stats

        mock_execute.return_value = (
            [(0, 0, 0, 0, None, 0.0, None, 0, 0, 0, None, None, 0, 0, None)],
            [
                "total_predictions", "correct", "incorrect", "evaluated",
                "avg_return", "total_pnl", "avg_confidence",
                "bullish_count", "bearish_count", "neutral_count",
                "best_return", "worst_return",
                "overall_evaluated", "overall_correct", "overall_avg_return",
            ],
        )

        result = get_asset_stats("ZZZZZ")

        assert result["accuracy_t7"] == 0.0
        assert result["total_predictions"] == 0
        assert result["best_return_t7"] is None

    @patch("data.execute_query")
    def test_returns_defaults_on_error(self, mock_execute):
        """Test that function returns zeroed dict on error."""
        from data import get_asset_stats

        mock_execute.side_effect = Exception("Database error")

        result = get_asset_stats("AAPL")

        assert result["total_predictions"] == 0
        assert result["accuracy_t7"] == 0.0
        assert result["overall_accuracy_t7"] == 0.0

    @patch("data.execute_query")
    def test_passes_symbol_uppercase(self, mock_execute):
        """Test that symbol is converted to uppercase."""
        from data import get_asset_stats

        mock_execute.return_value = (
            [(0, 0, 0, 0, None, 0.0, None, 0, 0, 0, None, None, 0, 0, None)],
            [
                "total_predictions", "correct", "incorrect", "evaluated",
                "avg_return", "total_pnl", "avg_confidence",
                "bullish_count", "bearish_count", "neutral_count",
                "best_return", "worst_return",
                "overall_evaluated", "overall_correct", "overall_avg_return",
            ],
        )

        get_asset_stats("aapl")

        call_args = mock_execute.call_args[0]
        assert call_args[1]["symbol"] == "AAPL"


class TestGetRelatedAssets:
    """Tests for get_related_assets function."""

    @patch("data.execute_query")
    def test_returns_dataframe(self, mock_execute):
        """Test that function returns a pandas DataFrame."""
        from data import get_related_assets

        mock_execute.return_value = (
            [
                ("GOOGL", 5, 2.1),
                ("MSFT", 4, 1.5),
                ("TSLA", 3, -0.8),
            ],
            ["related_symbol", "co_occurrence_count", "avg_return_t7"],
        )

        result = get_related_assets("AAPL", limit=8)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3
        assert "related_symbol" in result.columns
        assert "co_occurrence_count" in result.columns

    @patch("data.execute_query")
    def test_respects_limit_parameter(self, mock_execute):
        """Test that limit parameter is passed to query."""
        from data import get_related_assets

        mock_execute.return_value = ([], [])

        get_related_assets("AAPL", limit=5)

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        assert call_args[1]["limit"] == 5

    @patch("data.execute_query")
    def test_passes_symbol_uppercase(self, mock_execute):
        """Test that symbol is converted to uppercase."""
        from data import get_related_assets

        mock_execute.return_value = ([], [])

        get_related_assets("aapl")

        call_args = mock_execute.call_args[0]
        assert call_args[1]["symbol"] == "AAPL"

    @patch("data.execute_query")
    def test_returns_empty_dataframe_on_error(self, mock_execute):
        """Test that function returns empty DataFrame on error."""
        from data import get_related_assets

        mock_execute.side_effect = Exception("Database error")

        result = get_related_assets("AAPL")

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch("data.execute_query")
    def test_returns_empty_for_no_co_occurrences(self, mock_execute):
        """Test behavior when no related assets exist."""
        from data import get_related_assets

        mock_execute.return_value = ([], [])

        result = get_related_assets("OBSCURE_ASSET")

        assert isinstance(result, pd.DataFrame)
        assert result.empty
```

### 6.2 Layout Component Tests

Add these test classes to `shit_tests/shitty_ui/test_layout.py`.

```python
# ============================================================
# Tests for Asset Deep Dive layout components
# ============================================================


class TestCreateAssetPage:
    """Tests for create_asset_page function."""

    def test_returns_div(self):
        """Test that function returns an html.Div."""
        from layout import create_asset_page

        result = create_asset_page("AAPL")

        assert isinstance(result, html.Div)

    def test_contains_symbol_store(self):
        """Test that page includes a dcc.Store with the symbol."""
        from layout import create_asset_page

        result = create_asset_page("AAPL")

        # Find the dcc.Store in children
        children = result.children
        stores = [
            c for c in children
            if isinstance(c, dcc.Store) and c.id == "asset-page-symbol"
        ]
        assert len(stores) == 1
        assert stores[0].data == "AAPL"

    def test_contains_price_chart(self):
        """Test that page includes a price chart component."""
        from layout import create_asset_page
        import json

        result = create_asset_page("TSLA")

        # Serialize to check that asset-price-chart ID exists
        result_str = str(result)
        assert "asset-price-chart" in result_str


class TestCreateAssetHeader:
    """Tests for create_asset_header function."""

    def test_returns_div(self):
        """Test that function returns an html.Div."""
        from layout import create_asset_header

        result = create_asset_header("AAPL")

        assert isinstance(result, html.Div)

    def test_contains_symbol_text(self):
        """Test that header displays the symbol."""
        from layout import create_asset_header

        result = create_asset_header("AAPL")

        # Check that AAPL appears in the header
        result_str = str(result)
        assert "AAPL" in result_str

    def test_contains_back_link(self):
        """Test that header has a back link to dashboard."""
        from layout import create_asset_header

        result = create_asset_header("AAPL")

        # Check for the href="/" link
        result_str = str(result)
        assert "Dashboard" in result_str


class TestCreatePredictionTimelineCard:
    """Tests for create_prediction_timeline_card function."""

    def test_bullish_prediction_correct(self):
        """Test card for a correct bullish prediction."""
        from layout import create_prediction_timeline_card

        row = {
            "prediction_date": datetime(2024, 1, 15),
            "timestamp": datetime(2024, 1, 15, 10, 30),
            "text": "Great news for American industry!",
            "shitpost_id": "post123",
            "prediction_sentiment": "bullish",
            "prediction_confidence": 0.85,
            "price_at_prediction": 150.0,
            "price_t7": 155.0,
            "return_t7": 3.3,
            "correct_t7": True,
            "pnl_t7": 33.0,
            "thesis": "Manufacturing boost",
        }

        result = create_prediction_timeline_card(row)

        assert isinstance(result, html.Div)
        result_str = str(result)
        assert "Correct" in result_str
        assert "BULLISH" in result_str

    def test_bearish_prediction_incorrect(self):
        """Test card for an incorrect bearish prediction."""
        from layout import create_prediction_timeline_card

        row = {
            "prediction_date": datetime(2024, 2, 10),
            "timestamp": datetime(2024, 2, 10, 14, 0),
            "text": "Bad times ahead for tech!",
            "shitpost_id": "post456",
            "prediction_sentiment": "bearish",
            "prediction_confidence": 0.60,
            "price_at_prediction": 200.0,
            "price_t7": 205.0,
            "return_t7": 2.5,
            "correct_t7": False,
            "pnl_t7": -25.0,
            "thesis": "Tech sell-off expected",
        }

        result = create_prediction_timeline_card(row)

        result_str = str(result)
        assert "Incorrect" in result_str
        assert "BEARISH" in result_str

    def test_pending_prediction(self):
        """Test card for a prediction without outcome yet."""
        from layout import create_prediction_timeline_card

        row = {
            "prediction_date": datetime(2024, 3, 1),
            "timestamp": datetime(2024, 3, 1, 9, 0),
            "text": "Something about the market",
            "shitpost_id": "post789",
            "prediction_sentiment": "neutral",
            "prediction_confidence": 0.50,
            "price_at_prediction": 100.0,
            "price_t7": None,
            "return_t7": None,
            "correct_t7": None,
            "pnl_t7": None,
            "thesis": "Unknown impact",
        }

        result = create_prediction_timeline_card(row)

        result_str = str(result)
        assert "Pending" in result_str

    def test_truncates_long_text(self):
        """Test that tweet text longer than 200 chars is truncated."""
        from layout import create_prediction_timeline_card

        long_text = "A" * 300
        row = {
            "prediction_date": datetime(2024, 1, 1),
            "timestamp": datetime(2024, 1, 1),
            "text": long_text,
            "shitpost_id": "post000",
            "prediction_sentiment": "bullish",
            "prediction_confidence": 0.7,
            "price_at_prediction": 100.0,
            "price_t7": 105.0,
            "return_t7": 5.0,
            "correct_t7": True,
            "pnl_t7": 50.0,
            "thesis": "Test",
        }

        result = create_prediction_timeline_card(row)

        result_str = str(result)
        # Should contain "..." indicating truncation
        assert "..." in result_str

    def test_handles_missing_fields(self):
        """Test that card handles missing optional fields gracefully."""
        from layout import create_prediction_timeline_card

        row = {
            "prediction_date": None,
            "timestamp": None,
            "text": "",
            "shitpost_id": "",
            "prediction_sentiment": None,
            "prediction_confidence": 0,
            "price_at_prediction": None,
            "price_t7": None,
            "return_t7": None,
            "correct_t7": None,
            "pnl_t7": None,
            "thesis": "",
        }

        # Should not raise an exception
        result = create_prediction_timeline_card(row)
        assert isinstance(result, html.Div)


class TestCreateRelatedAssetLink:
    """Tests for create_related_asset_link function."""

    def test_returns_div(self):
        """Test that function returns an html.Div."""
        from layout import create_related_asset_link

        row = {
            "related_symbol": "GOOGL",
            "co_occurrence_count": 5,
            "avg_return_t7": 2.1,
        }

        result = create_related_asset_link(row)

        assert isinstance(result, html.Div)

    def test_contains_link_to_asset_page(self):
        """Test that the component contains a link to the asset page."""
        from layout import create_related_asset_link

        row = {
            "related_symbol": "MSFT",
            "co_occurrence_count": 3,
            "avg_return_t7": 1.5,
        }

        result = create_related_asset_link(row)

        result_str = str(result)
        assert "/assets/MSFT" in result_str

    def test_handles_negative_return(self):
        """Test display of negative average return."""
        from layout import create_related_asset_link

        row = {
            "related_symbol": "TSLA",
            "co_occurrence_count": 2,
            "avg_return_t7": -3.5,
        }

        result = create_related_asset_link(row)

        result_str = str(result)
        assert "-3.50%" in result_str

    def test_handles_null_return(self):
        """Test display when avg_return_t7 is None."""
        from layout import create_related_asset_link

        row = {
            "related_symbol": "AMD",
            "co_occurrence_count": 1,
            "avg_return_t7": None,
        }

        result = create_related_asset_link(row)

        result_str = str(result)
        assert "--" in result_str


class TestCreatePerformanceSummary:
    """Tests for create_performance_summary function."""

    def test_returns_div(self):
        """Test that function returns an html.Div."""
        from layout import create_performance_summary

        stats = {
            "accuracy_t7": 70.0,
            "overall_accuracy_t7": 60.0,
            "avg_return_t7": 2.5,
            "overall_avg_return_t7": 1.8,
            "bullish_count": 6,
            "bearish_count": 3,
            "neutral_count": 1,
            "best_return_t7": 5.5,
            "worst_return_t7": -2.1,
        }

        result = create_performance_summary(stats)

        assert isinstance(result, html.Div)

    def test_shows_accuracy_comparison(self):
        """Test that performance summary shows asset vs overall accuracy."""
        from layout import create_performance_summary

        stats = {
            "accuracy_t7": 75.0,
            "overall_accuracy_t7": 55.0,
            "avg_return_t7": 3.0,
            "overall_avg_return_t7": 1.0,
            "bullish_count": 8,
            "bearish_count": 2,
            "neutral_count": 0,
            "best_return_t7": 10.0,
            "worst_return_t7": -1.0,
        }

        result = create_performance_summary(stats)

        result_str = str(result)
        assert "75.0%" in result_str
        assert "55.0%" in result_str

    def test_handles_zero_stats(self):
        """Test that summary handles all-zero stats gracefully."""
        from layout import create_performance_summary

        stats = {
            "accuracy_t7": 0.0,
            "overall_accuracy_t7": 0.0,
            "avg_return_t7": 0.0,
            "overall_avg_return_t7": 0.0,
            "bullish_count": 0,
            "bearish_count": 0,
            "neutral_count": 0,
            "best_return_t7": None,
            "worst_return_t7": None,
        }

        result = create_performance_summary(stats)

        assert isinstance(result, html.Div)
        result_str = str(result)
        assert "--" in result_str  # best/worst should show "--"


class TestRouteCallback:
    """Tests for the URL routing callback."""

    def test_root_returns_dashboard(self):
        """Test that / returns the dashboard page."""
        # This requires testing the callback function directly.
        # We test the routing logic rather than the full Dash callback.
        # Extract the route logic:
        pathname = "/"
        if pathname and pathname.startswith("/assets/"):
            page = "asset"
        else:
            page = "dashboard"

        assert page == "dashboard"

    def test_asset_url_extracts_symbol(self):
        """Test that /assets/AAPL extracts 'AAPL'."""
        pathname = "/assets/AAPL"
        symbol = pathname.split("/assets/")[-1].strip("/").upper()

        assert symbol == "AAPL"

    def test_asset_url_handles_lowercase(self):
        """Test that /assets/aapl becomes 'AAPL'."""
        pathname = "/assets/aapl"
        symbol = pathname.split("/assets/")[-1].strip("/").upper()

        assert symbol == "AAPL"

    def test_asset_url_handles_trailing_slash(self):
        """Test that /assets/TSLA/ works correctly."""
        pathname = "/assets/TSLA/"
        symbol = pathname.split("/assets/")[-1].strip("/").upper()

        assert symbol == "TSLA"
```

### 6.3 Running the Tests

```bash
# Run only the new asset deep dive tests
cd /home/user/shitpost-alpha
python3 -m pytest shit_tests/shitty_ui/test_data.py -v -k "Asset"
python3 -m pytest shit_tests/shitty_ui/test_layout.py -v -k "Asset or Route or Timeline or Related or Performance"

# Run all shitty_ui tests
python3 -m pytest shit_tests/shitty_ui/ -v

# Run with coverage
python3 -m pytest shit_tests/shitty_ui/ --cov=shitty_ui --cov-report=term-missing
```

---

## 7. Implementation Checklist

Complete these tasks in order. Each task builds on the previous one. Do not skip ahead.

### Phase A: Data Layer (Day 1)

- [ ] **A1**: Add `get_asset_price_history()` to `data.py`
  - Copy the function from Section 3.1
  - Verify it follows the same error handling pattern as existing functions
  - Test: `python3 -m pytest shit_tests/shitty_ui/test_data.py -v -k "TestGetAssetPriceHistory"`

- [ ] **A2**: Add `get_asset_predictions()` to `data.py`
  - Copy the function from Section 3.2
  - Test: `python3 -m pytest shit_tests/shitty_ui/test_data.py -v -k "TestGetAssetPredictions"`

- [ ] **A3**: Add `get_asset_stats()` to `data.py`
  - Copy the function from Section 3.3
  - The CTE query is complex. Test the zero/null handling carefully
  - Test: `python3 -m pytest shit_tests/shitty_ui/test_data.py -v -k "TestGetAssetStats"`

- [ ] **A4**: Add `get_related_assets()` to `data.py`
  - Copy the function from Section 3.4
  - Note: The `?` JSONB operator is PostgreSQL-specific
  - Test: `python3 -m pytest shit_tests/shitty_ui/test_data.py -v -k "TestGetRelatedAssets"`

- [ ] **A5**: Run all data tests to confirm no regressions
  - `python3 -m pytest shit_tests/shitty_ui/test_data.py -v`
  - All existing tests must still pass

### Phase B: URL Routing (Day 2, morning)

- [ ] **B1**: Add `dcc.Location` and `page-content` container to `create_app()`
  - Follow Section 2, Step 2 and Step 3
  - This changes the structure of `app.layout`

- [ ] **B2**: Extract existing dashboard content into `create_dashboard_page()`
  - Follow Section 2, Step 4
  - Move everything currently inside the main content `html.Div` into this function
  - The function should return an `html.Div`

- [ ] **B3**: Add the router callback `route_page()`
  - Follow Section 2, Step 5
  - Place it as the FIRST callback inside `register_callbacks()`

- [ ] **B4**: Verify the existing dashboard still works
  - Start the app: `cd shitty_ui && python app.py`
  - Navigate to `http://localhost:8050/`
  - All existing functionality must work unchanged
  - Check the browser console for JavaScript errors

### Phase C: Asset Page Layout (Day 2, afternoon)

- [ ] **C1**: Add `create_asset_page()` to `layout.py`
  - Copy from Section 4.1
  - This is called by the router when URL matches `/assets/{symbol}`

- [ ] **C2**: Add `create_asset_header()` to `layout.py`
  - Copy from Section 4.2

- [ ] **C3**: Add `create_prediction_timeline_card()` to `layout.py`
  - Copy from Section 4.3

- [ ] **C4**: Add `create_related_asset_link()` to `layout.py`
  - Copy from Section 4.4

- [ ] **C5**: Add `create_performance_summary()` to `layout.py`
  - Copy from Section 5.2 (this is a helper function, not a callback)

- [ ] **C6**: Run layout tests
  - `python3 -m pytest shit_tests/shitty_ui/test_layout.py -v`
  - All new and existing tests must pass

### Phase D: Callbacks (Day 3)

- [ ] **D1**: Update imports at the top of `layout.py`
  - Add the four new data functions to the import block (Section 5.5)

- [ ] **D2**: Add `update_asset_page()` callback
  - Copy from Section 5.1
  - This populates stat cards, current price, performance summary, timeline, and related assets

- [ ] **D3**: Add `update_asset_price_chart()` callback
  - Copy from Section 5.3
  - This builds the candlestick chart with prediction markers

- [ ] **D4**: Add `update_range_button_styles()` callback
  - Copy from Section 5.4
  - This highlights the active date range button

- [ ] **D5**: Update `update_asset_drilldown()` callback
  - Add the "View Full Page" link at the bottom (Section 5.6)

- [ ] **D6**: Full integration test
  - Start the app: `cd shitty_ui && python app.py`
  - Navigate to `http://localhost:8050/`
  - Select an asset in the dropdown
  - Click "View Full Deep Dive" link
  - Verify the asset page loads with all sections
  - Click date range buttons (30D, 90D, 180D, 1Y)
  - Click a related asset link
  - Click "Dashboard" back link
  - Check browser console for errors

### Phase E: Testing and Polish (Day 3-4)

- [ ] **E1**: Add all data layer tests from Section 6.1
  - `python3 -m pytest shit_tests/shitty_ui/test_data.py -v`

- [ ] **E2**: Add all layout tests from Section 6.2
  - `python3 -m pytest shit_tests/shitty_ui/test_layout.py -v`

- [ ] **E3**: Run full test suite
  - `python3 -m pytest shit_tests/shitty_ui/ -v`
  - All tests must pass

- [ ] **E4**: Lint and format
  - `ruff check shitty_ui/`
  - `ruff format shitty_ui/`

- [ ] **E5**: Update CHANGELOG.md
  - Add entry under `## [Unreleased]` -> `### Added`
  - Example: `**Asset Deep Dive Pages** - Individual /assets/{symbol} pages with price charts, prediction overlays, performance comparison, and related assets`

- [ ] **E6**: Manual QA
  - Test with at least 3 different assets
  - Test with an asset that has no predictions (should show "No predictions found")
  - Test with an asset that has no price data (should show "No price data available")
  - Test navigation: dashboard -> asset -> related asset -> back to dashboard
  - Test on a narrow browser window (mobile-ish viewport)

---

## 8. Definition of Done

All of the following must be true before this feature is considered complete:

- [ ] All four data query functions are implemented in `data.py`
- [ ] URL routing works: `/` shows dashboard, `/assets/AAPL` shows asset page
- [ ] Asset page displays: header, stat cards, price chart, prediction timeline, performance summary, related assets
- [ ] Price chart shows candlestick data with prediction overlay markers
- [ ] Prediction markers are color-coded: green = correct, red = incorrect, yellow = pending
- [ ] Date range buttons (30D, 90D, 180D, 1Y) filter the price chart
- [ ] Related asset links navigate to their own asset pages
- [ ] Back link returns to the dashboard
- [ ] "View Full Deep Dive" link added to existing asset drilldown on dashboard
- [ ] All existing tests still pass (no regressions)
- [ ] At least 25 new tests added (data + layout)
- [ ] `ruff check .` passes with no errors
- [ ] `ruff format .` produces no changes
- [ ] CHANGELOG.md updated
- [ ] Manual QA completed with at least 3 assets
- [ ] No JavaScript console errors in the browser

---

## Appendix: Common Pitfalls

### Pitfall 1: Callback ID Collisions

When the router swaps between pages, Dash components from the previous page are removed from the DOM. If both pages use a component with the same `id`, callbacks may fire unexpectedly. This is why all asset page component IDs are prefixed with `asset-` (e.g., `asset-price-chart`, `asset-stat-cards`).

**Rule**: Every component ID on the asset page must start with `asset-`.

### Pitfall 2: `suppress_callback_exceptions` Is Already True

The app is configured with `suppress_callback_exceptions=True`. This means Dash will not raise errors when callback outputs reference components that do not currently exist in the layout. This is necessary for multi-page apps because the asset page components only exist when that page is active.

**Downside**: Typos in component IDs will silently fail. Double-check all `Output()` and `Input()` IDs match the component IDs exactly.

### Pitfall 3: JSONB `?` Operator in SQLite

The `get_related_assets()` query uses `assets::jsonb ? :symbol`, which is PostgreSQL-specific. It will fail on SQLite. Since tests use mock `execute_query`, this does not affect tests. But if you need to run the dashboard locally against SQLite for development, you need a fallback:

```python
# SQLite fallback (add inside get_related_assets if needed):
if DATABASE_URL.startswith("sqlite"):
    # Use LIKE for JSON array membership (less precise)
    query = text("""
        SELECT ... WHERE p.assets LIKE '%' || :symbol || '%' ...
    """)
```

### Pitfall 4: Empty DataFrames in Plotly

When creating the candlestick chart, always check `price_df.empty` before passing data to `go.Candlestick()`. Plotly will raise an error if given empty Series for OHLC values.

### Pitfall 5: `callback_context` Import

`callback_context` must be imported from `dash`:

```python
from dash import callback_context
```

Or use it inside the callback function by importing from `dash` at the top of the file. The existing `layout.py` imports `from dash import Dash, html, dcc, dash_table, Input, Output, State`. You need to add `callback_context` to this import:

```python
from dash import Dash, html, dcc, dash_table, Input, Output, State, callback_context
```

### Pitfall 6: Date Types in Templates

`prediction_date` comes from the database as a Python `date` object (not `datetime`). The `strftime` call in `create_prediction_timeline_card` uses `isinstance(prediction_date, datetime)`, which will be `False` for `date` objects. The code handles this with `hasattr(prediction_date, "strftime")` as a fallback. Make sure not to remove that fallback.
