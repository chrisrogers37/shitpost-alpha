# Phase 03: Asset Screener Table

**Status**: ✅ COMPLETE
**Started**: 2026-02-22
**Completed**: 2026-02-22

| Field | Value |
|---|---|
| **PR Title** | feat(dashboard): replace chart tabs with SaaS Meltdown-style asset screener table |
| **Risk** | Medium |
| **Effort** | Medium (~3-4 hours) |
| **Files Created** | 1 (`shitty_ui/components/screener.py`) |
| **Files Modified** | 3 (`shitty_ui/data.py`, `shitty_ui/pages/dashboard.py`, `shitty_ui/layout.py`) |
| **Files Deleted** | 0 |

---

## Context

The current dashboard homepage buries per-asset performance data inside a third tab ("By Asset") within the "The Numbers" analytics card. Users must click through chart tabs to find the most actionable information in the system: which assets Trump has moved, in which direction, and how much money those predictions made or lost.

SaaS Meltdown (`ref-saasmeltdown-desktop.png`) demonstrates the correct pattern: the sortable data table IS the product. Every row is a company with inline sparkline, heat-mapped percentages, and click-to-drill. The table is the homepage -- no chart tabs, no navigation required.

This phase replaces the analytics chart-tab card and the prediction feed on the dashboard with a dense, sortable asset screener table that surfaces per-asset performance as the primary view. The existing 4 KPI hero cards remain above the table (unchanged). The "Latest Shitposts" tertiary section and collapsible data table are preserved below.

**Gap Addressed**: Gap 2 (data not surfaced in scannable table), Gap 8 (asset table lacks visual punch).

**Design Reference**: `ref-saasmeltdown-desktop.png` -- sortable rows with ticker, inline sparkline, heat-mapped columns.

---

## Visual Specification

### Before (current `dashboard-desktop.png`)

```
+--------------------------------------------------+
| [KPI] 501 Signals | 42.9% Acc | +1.05% | $+5,247|
+--------------------------------------------------+
|  The Numbers                                      |
|  [Accuracy Over Time] [By Confidence] [By Asset]  |
|  ~~~~~~~~~~~~ area chart ~~~~~~~~~~~~~~            |
+--------------------------------------------------+
|  Predictions - LLM signals with tracked outcomes   |
|  [signal card] [signal card] [signal card] ...     |
+--------------------------------------------------+
|  Latest Shitposts  (tertiary)                      |
+--------------------------------------------------+
|  Full Data Table  (collapsed, tertiary)            |
+--------------------------------------------------+
```

### After (new layout)

```
+--------------------------------------------------+
| [KPI] 501 Signals | 42.9% Acc | +1.05% | $+5,247|
+--------------------------------------------------+
|  Asset Screener                                    |
|  +-Asset-+-Sparkline-+-#Posts-+-Sent-+-7dRet-+P&L-+|
|  | XLE   | ~~~chart~~|  29   | BULL | +2.48%|$719||
|  | DIS   | ~~~chart~~|  17   | BEAR | -2.58%|-438||
|  | CMCSA | ~~~chart~~|  17   | BULL | -1.53%|-259||
|  | LMT   | ~~~chart~~|  16   | BULL | +3.00%|$481||
|  | USO   | ~~~chart~~|  15   | BULL | +1.81%|$271||
|  | ...   |           |       |      |       |    ||
|  +-------+----------+-------+------+-------+----+|
+--------------------------------------------------+
|  Latest Shitposts  (tertiary, unchanged)           |
+--------------------------------------------------+
|  Full Data Table  (collapsed, tertiary, unchanged) |
+--------------------------------------------------+
```

### Column Specification

| Column | Width | Alignment | Content | Styling |
|--------|-------|-----------|---------|---------|
| **Asset** | 80px | Left | Ticker symbol (e.g., "XLE") | Bold, `COLORS["accent"]` (`#3b82f6`), clickable link |
| **30d Price** | 140px | Center | Inline sparkline via `build_sparkline_figure()` | 120x36px chart, no axes, green/red line by direction |
| **Predictions** | 90px | Right | Count of evaluated predictions | Tabular nums, `COLORS["text"]` |
| **Sentiment** | 100px | Center | Most recent prediction sentiment | Pill badge: green "BULL" / red "BEAR" / gray "NEUTRAL" |
| **7d Return** | 100px | Right | Average 7-day return (%) | Heat-mapped: green for positive, red for negative, gradient intensity |
| **Total P&L** | 100px | Right | Sum of $1k simulated P&L | Heat-mapped: green for positive, red for negative, bold for magnitude |
| **Win Rate** | 80px | Right | Accuracy percentage | Heat-mapped: green >= 50%, red < 50% |
| **Confidence** | 80px | Right | Average LLM confidence | `COLORS["text_muted"]`, 0-100 display |

**Total table width**: ~770px (fits comfortably in the 1400px max-width container with padding).

### Cell Styling Details

- **Row height**: 48px (comfortable touch target on mobile, matches SaaS Meltdown density)
- **Row hover**: `backgroundColor: "rgba(133, 187, 101, 0.06)"` (subtle green tint), `cursor: "pointer"`
- **Row border**: Bottom border `1px solid COLORS["border"]` (`#2A3A2E`)
- **Header row**: `backgroundColor: COLORS["primary"]` (`#141E22`), `fontWeight: "600"`, `fontSize: "0.75rem"`, `textTransform: "uppercase"`, `letterSpacing: "0.05em"`, `color: COLORS["text_muted"]` (`#8B9A7E`)
- **Cell padding**: `10px 12px`
- **Font**: `fontSize: "0.85rem"`, `fontVariantNumeric: "tabular-nums"` (all numeric columns)

### Heat-Map Gradient

For the 7d Return, Total P&L, and Win Rate columns, cell background color is calculated as a gradient between red and green based on value magnitude:

```python
def heat_color(value: float, is_percentage: bool = False) -> str:
    """Return rgba background color for heat-mapping a numeric cell.

    For percentage values (returns, win rate):
        - Deep red bg at <= -5% (or <= 30% for win rate)
        - No bg (transparent) at 0% (or 50% for win rate)
        - Deep green bg at >= +5% (or >= 70% for win rate)

    For dollar values (P&L):
        - Deep red bg at <= -$500
        - No bg (transparent) at $0
        - Deep green bg at >= +$500
    """
```

The rgba values are **derived from design tokens** (not hardcoded):
- **Green (positive)**: Derived from `COLORS["success"]` hex → RGB, at computed intensity
- **Red (negative)**: Derived from `COLORS["danger"]` hex → RGB, at computed intensity
- **Neutral (zero)**: `rgba(0, 0, 0, 0)` (transparent)
- Uses `_hex_to_rgb()` helper to convert hex tokens to RGB tuples, keeping heat-map colors in sync with the theme

Threshold values: returns: 5.0, P&L: 500.0, win rate: 20.0 (distance from 50%).

### Sentiment Badge

Reuses the existing `SENTIMENT_COLORS` and `SENTIMENT_BG_COLORS` from `constants.py`:

```python
# Pill badge, all-caps, compact
html.Span(
    sentiment_text,  # "BULL", "BEAR", or "NEUT"
    className="sentiment-badge",
    style={
        "backgroundColor": SENTIMENT_BG_COLORS[sentiment_lower],
        "color": SENTIMENT_COLORS[sentiment_lower],
    },
)
```

Abbreviations: "bullish" -> "BULL", "bearish" -> "BEAR", "neutral" -> "NEUT" (to save horizontal space in the table).

### Sort Behavior

- Clicking a column header sorts the table by that column
- Default sort: **Predictions** descending (most-predicted assets first, matching current `get_accuracy_by_asset` ORDER BY)
- Sort indicator: small chevron icon (up/down) appended to the active header
- Sort is client-side via a Dash callback (no server round-trip)
- Sparkline column is NOT sortable (no numeric value to sort by)

### Row Click Behavior

Clicking any cell in a row navigates to `/assets/<SYMBOL>`. This reuses the existing asset detail page at `shitty_ui/pages/assets.py` (unchanged by this phase).

---

## Dependencies

- **Phase 02** (money theme tokens): This phase uses `COLORS["accent"]`, `COLORS["success"]`, `COLORS["danger"]`, etc. from `constants.py`. If Phase 02 changes these color values to a money theme, this phase's table will automatically pick up the new palette. **However, Phase 03 can be implemented before Phase 02** -- it uses the existing color tokens by name, not by value. Phase 02 simply changes the values behind those names.

## Unlocks

- **Phase 04**: Can build on the screener table to add dynamic insight callouts above it
- **Phase 05**: Asset detail page improvements can reference the screener as the entry point
- **Phase 06**: Mobile optimization can target the screener's responsive behavior

---

## Detailed Implementation Plan

### Step 1: New Data Function in `shitty_ui/data.py`

Add `get_asset_screener_data()` that combines `get_accuracy_by_asset()` data with the latest sentiment per asset and sparkline price data into a single table-ready structure.

**Add after line 632** (after `get_accuracy_by_asset()` function ends):

```python
@ttl_cache(ttl_seconds=300)  # Cache for 5 minutes
def get_asset_screener_data(days: int = None) -> pd.DataFrame:
    """Get combined asset screener data for the dashboard table.

    Joins per-asset accuracy metrics with the latest prediction sentiment
    for each asset, plus average confidence. Returns a single DataFrame
    ready for table rendering.

    This function combines data that was previously spread across
    get_accuracy_by_asset() and the performance page table. It adds
    the latest_sentiment column (most recent prediction sentiment per asset)
    and avg_confidence, which were not previously surfaced.

    Args:
        days: Number of days to look back (None = all time).

    Returns:
        DataFrame with columns:
            symbol, total_predictions, correct, incorrect, avg_return,
            total_pnl, accuracy, latest_sentiment, avg_confidence
        Sorted by total_predictions descending.
        Returns empty DataFrame on error.
    """
    date_filter = ""
    params: Dict[str, Any] = {}

    if days is not None:
        date_filter = "AND po.prediction_date >= :start_date"
        params["start_date"] = (datetime.now() - timedelta(days=days)).date()

    query = text(f"""
        WITH asset_metrics AS (
            SELECT
                po.symbol,
                COUNT(*) as total_predictions,
                COUNT(CASE WHEN po.correct_t7 = true THEN 1 END) as correct,
                COUNT(CASE WHEN po.correct_t7 = false THEN 1 END) as incorrect,
                ROUND(AVG(CASE WHEN po.return_t7 IS NOT NULL THEN po.return_t7 END)::numeric, 2) as avg_return,
                ROUND(SUM(CASE WHEN po.pnl_t7 IS NOT NULL THEN po.pnl_t7 ELSE 0 END)::numeric, 2) as total_pnl,
                ROUND(AVG(po.prediction_confidence)::numeric, 2) as avg_confidence
            FROM prediction_outcomes po
            WHERE po.correct_t7 IS NOT NULL
            {date_filter}
            GROUP BY po.symbol
            HAVING COUNT(*) >= 2
        ),
        latest_sentiment AS (
            SELECT DISTINCT ON (po.symbol)
                po.symbol,
                po.prediction_sentiment
            FROM prediction_outcomes po
            WHERE po.correct_t7 IS NOT NULL
            {date_filter}
            ORDER BY po.symbol, po.prediction_date DESC
        )
        SELECT
            am.symbol,
            am.total_predictions,
            am.correct,
            am.incorrect,
            am.avg_return,
            am.total_pnl,
            am.avg_confidence,
            ls.prediction_sentiment as latest_sentiment
        FROM asset_metrics am
        LEFT JOIN latest_sentiment ls ON am.symbol = ls.symbol
        ORDER BY am.total_predictions DESC
    """)

    try:
        rows, columns = execute_query(query, params)
        df = pd.DataFrame(rows, columns=columns)
        if not df.empty:
            df["accuracy"] = (df["correct"] / df["total_predictions"] * 100).round(1)
        return df
    except Exception as e:
        logger.error(f"Error loading asset screener data: {e}")
        return pd.DataFrame()
```

Also add a new sparkline batch function optimized for the screener (30-day trailing window, not centered on a prediction date):

**Add after the new `get_asset_screener_data()` function:**

```python
@ttl_cache(ttl_seconds=300)  # Cache for 5 minutes
def get_screener_sparkline_prices(symbols: tuple) -> Dict[str, pd.DataFrame]:
    """Batch-fetch 30-day trailing price data for screener sparklines.

    Unlike get_sparkline_prices() which centers on a prediction date,
    this function fetches the most recent 30 calendar days of prices
    for each symbol. Used by the asset screener table on the dashboard.

    Args:
        symbols: Tuple of ticker symbols (tuple for cache hashability).

    Returns:
        Dict mapping symbol -> DataFrame with columns [date, close].
        Missing symbols are absent from the dict.
    """
    if not symbols:
        return {}

    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=45)  # 45 calendar days to cover ~30 trading days

    query = text("""
        SELECT symbol, date, close
        FROM market_prices
        WHERE symbol = ANY(:symbols)
            AND date >= :start_date
            AND date <= :end_date
        ORDER BY symbol, date ASC
    """)

    params = {
        "symbols": list(symbols),
        "start_date": start_date,
        "end_date": end_date,
    }

    try:
        rows, columns = execute_query(query, params)
        if not rows:
            return {}

        df = pd.DataFrame(rows, columns=columns)
        df["date"] = pd.to_datetime(df["date"])

        result: Dict[str, pd.DataFrame] = {}
        for symbol in df["symbol"].unique():
            symbol_df = df[df["symbol"] == symbol][["date", "close"]].reset_index(drop=True)
            if len(symbol_df) >= 2:
                result[symbol] = symbol_df

        return result
    except Exception as e:
        logger.error(f"Error loading screener sparkline prices: {e}")
        return {}
```

### Step 2: New Component `shitty_ui/components/screener.py`

Create a new file at `shitty_ui/components/screener.py` with the complete asset screener table component.

```python
"""Asset screener table component for the dashboard homepage.

Renders a SaaS Meltdown-inspired sortable data table showing per-asset
prediction performance with inline sparklines, sentiment badges, and
heat-mapped return/P&L cells.
"""

from typing import Dict, Optional

import pandas as pd
from dash import html, dcc
import dash_bootstrap_components as dbc

from constants import (
    COLORS,
    FONT_SIZES,
    HIERARCHY,
    SENTIMENT_COLORS,
    SENTIMENT_BG_COLORS,
    SPARKLINE_CONFIG,
)
from components.sparkline import build_sparkline_figure, create_sparkline_placeholder


# ── Heat-mapping helpers ──────────────────────────────────────────────

def _hex_to_rgb(hex_color: str) -> tuple:
    """Convert a hex color string to an (r, g, b) tuple."""
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


_SUCCESS_RGB = _hex_to_rgb(COLORS["success"])
_DANGER_RGB = _hex_to_rgb(COLORS["danger"])


def _heat_bg(value: float, threshold: float, center: float = 0.0) -> str:
    """Calculate heat-mapped background color for a numeric cell.

    Derives colors from COLORS["success"] and COLORS["danger"] tokens
    so heat-mapping stays in sync with the active theme.

    Args:
        value: The numeric value to heat-map.
        threshold: The distance from center at which color reaches
            maximum intensity (0.15 alpha).
        center: The neutral midpoint (default 0.0 for returns/P&L,
            set to 50.0 for win rate percentage).

    Returns:
        CSS rgba() string for the cell background.
    """
    delta = value - center
    intensity = min(abs(delta) / threshold, 1.0) * 0.15

    if delta > 0:
        r, g, b = _SUCCESS_RGB
        return f"rgba({r}, {g}, {b}, {intensity:.3f})"
    elif delta < 0:
        r, g, b = _DANGER_RGB
        return f"rgba({r}, {g}, {b}, {intensity:.3f})"
    return "rgba(0, 0, 0, 0)"


def _text_color(value: float, center: float = 0.0) -> str:
    """Return green or red text color based on value vs center."""
    if value > center:
        return COLORS["success"]
    elif value < center:
        return COLORS["danger"]
    return COLORS["text_muted"]


# ── Sentiment badge ───────────────────────────────────────────────────

_SENTIMENT_ABBREV = {
    "bullish": "BULL",
    "bearish": "BEAR",
    "neutral": "NEUT",
}


def _sentiment_badge(sentiment: Optional[str]) -> html.Span:
    """Render a compact sentiment pill badge."""
    sentiment_lower = (sentiment or "neutral").lower()
    label = _SENTIMENT_ABBREV.get(sentiment_lower, "NEUT")

    return html.Span(
        label,
        className="sentiment-badge",
        style={
            "backgroundColor": SENTIMENT_BG_COLORS.get(
                sentiment_lower, SENTIMENT_BG_COLORS["neutral"]
            ),
            "color": SENTIMENT_COLORS.get(
                sentiment_lower, SENTIMENT_COLORS["neutral"]
            ),
            "fontSize": "0.7rem",
            "padding": "2px 8px",
            "borderRadius": "9999px",
            "fontWeight": "600",
            "letterSpacing": "0.05em",
            "textTransform": "uppercase",
            "display": "inline-block",
        },
    )


# ── Sparkline cell ────────────────────────────────────────────────────

def _sparkline_cell(
    symbol: str,
    sparkline_data: Dict[str, pd.DataFrame],
    cell_index: int,
) -> html.Td:
    """Render a table cell containing an inline sparkline chart."""
    price_df = sparkline_data.get(symbol)

    if price_df is not None and len(price_df) >= 2:
        fig = build_sparkline_figure(price_df, prediction_date=None)
        chart = dcc.Graph(
            id=f"screener-spark-{cell_index}",
            figure=fig,
            config={
                "displayModeBar": False,
                "staticPlot": True,
            },
            style={
                "width": f"{SPARKLINE_CONFIG['width']}px",
                "height": f"{SPARKLINE_CONFIG['height']}px",
                "display": "inline-block",
                "verticalAlign": "middle",
            },
        )
    else:
        chart = create_sparkline_placeholder()

    return html.Td(
        chart,
        style={
            "padding": "6px 8px",
            "textAlign": "center",
            "verticalAlign": "middle",
        },
    )


# ── Table header ──────────────────────────────────────────────────────

_HEADER_STYLE = {
    "backgroundColor": COLORS["primary"],
    "color": COLORS["text_muted"],
    "fontSize": "0.75rem",
    "fontWeight": "600",
    "textTransform": "uppercase",
    "letterSpacing": "0.05em",
    "padding": "10px 12px",
    "borderBottom": f"2px solid {COLORS['border']}",
    "whiteSpace": "nowrap",
    "userSelect": "none",
}


def _sort_header(label: str, column_key: str, align: str = "right") -> html.Th:
    """Render a sortable column header.

    The actual sort logic is handled by the callback in dashboard.py.
    This just renders the header cell with a data attribute for the key.
    """
    return html.Th(
        html.Span(
            [
                label,
                html.I(
                    className="fas fa-sort ms-1",
                    style={
                        "fontSize": "0.6rem",
                        "opacity": "0.4",
                    },
                ),
            ],
            style={"cursor": "pointer"},
        ),
        style={
            **_HEADER_STYLE,
            "textAlign": align,
        },
        **{"data-sort-key": column_key},
    )


# ── Main table builder ────────────────────────────────────────────────

def build_screener_table(
    screener_df: pd.DataFrame,
    sparkline_data: Dict[str, pd.DataFrame],
    sort_column: str = "total_predictions",
    sort_ascending: bool = False,
) -> html.Div:
    """Build the full asset screener table from pre-fetched data.

    Args:
        screener_df: DataFrame from get_asset_screener_data(). Expected
            columns: symbol, total_predictions, correct, incorrect,
            avg_return, total_pnl, accuracy, latest_sentiment,
            avg_confidence.
        sparkline_data: Dict from get_screener_sparkline_prices().
            Maps symbol -> DataFrame with [date, close].
        sort_column: Column key to sort by.
        sort_ascending: Sort direction.

    Returns:
        html.Div wrapping the complete screener table with header.
    """
    if screener_df.empty:
        return html.Div(
            [
                html.Div(
                    [
                        html.I(
                            className="fas fa-chart-bar me-2",
                            style={"color": COLORS["text_muted"]},
                        ),
                        html.Span(
                            "No asset data yet. The market hasn't had time to prove us wrong.",
                            style={
                                "color": COLORS["text_muted"],
                                "fontSize": "0.9rem",
                            },
                        ),
                    ],
                    style={
                        "textAlign": "center",
                        "padding": "48px 20px",
                    },
                )
            ]
        )

    # Apply sort
    if sort_column in screener_df.columns:
        sorted_df = screener_df.sort_values(
            sort_column,
            ascending=sort_ascending,
            na_position="last",
        ).reset_index(drop=True)
    else:
        sorted_df = screener_df

    # Build header row
    header = html.Thead(
        html.Tr(
            [
                html.Th(
                    "Asset",
                    style={**_HEADER_STYLE, "textAlign": "left", "width": "80px"},
                ),
                html.Th(
                    "30d Price",
                    style={
                        **_HEADER_STYLE,
                        "textAlign": "center",
                        "width": "140px",
                    },
                ),
                _sort_header("Predictions", "total_predictions", "right"),
                html.Th(
                    "Sentiment",
                    style={**_HEADER_STYLE, "textAlign": "center", "width": "100px"},
                ),
                _sort_header("7d Return", "avg_return", "right"),
                _sort_header("Total P&L", "total_pnl", "right"),
                _sort_header("Win Rate", "accuracy", "right"),
                _sort_header("Confidence", "avg_confidence", "right"),
            ]
        ),
        style={"position": "sticky", "top": "0", "zIndex": "1"},
    )

    # Build body rows
    rows = []
    for idx, row in sorted_df.iterrows():
        symbol = row["symbol"]
        total_preds = int(row["total_predictions"])
        avg_return = float(row.get("avg_return", 0) or 0)
        total_pnl = float(row.get("total_pnl", 0) or 0)
        accuracy = float(row.get("accuracy", 0) or 0)
        avg_conf = float(row.get("avg_confidence", 0) or 0)
        sentiment = row.get("latest_sentiment", "neutral")

        row_style = {
            "borderBottom": f"1px solid {COLORS['border']}",
            "cursor": "pointer",
            "transition": "background-color 0.1s ease",
        }

        # Common numeric cell style
        num_style = {
            "padding": "10px 12px",
            "fontSize": "0.85rem",
            "fontVariantNumeric": "tabular-nums",
            "verticalAlign": "middle",
        }

        rows.append(
            html.Tr(
                [
                    # Asset ticker
                    html.Td(
                        dcc.Link(
                            symbol,
                            href=f"/assets/{symbol}",
                            style={
                                "color": COLORS["accent"],
                                "fontWeight": "700",
                                "textDecoration": "none",
                                "fontSize": "0.9rem",
                            },
                        ),
                        style={
                            "padding": "10px 12px",
                            "verticalAlign": "middle",
                        },
                    ),
                    # Sparkline
                    _sparkline_cell(symbol, sparkline_data, idx),
                    # Predictions count
                    html.Td(
                        str(total_preds),
                        style={
                            **num_style,
                            "textAlign": "right",
                            "color": COLORS["text"],
                        },
                    ),
                    # Sentiment badge
                    html.Td(
                        _sentiment_badge(sentiment),
                        style={
                            "padding": "10px 12px",
                            "textAlign": "center",
                            "verticalAlign": "middle",
                        },
                    ),
                    # 7d Return (heat-mapped)
                    html.Td(
                        f"{avg_return:+.2f}%",
                        style={
                            **num_style,
                            "textAlign": "right",
                            "color": _text_color(avg_return),
                            "backgroundColor": _heat_bg(avg_return, threshold=5.0),
                            "fontWeight": "600",
                        },
                    ),
                    # Total P&L (heat-mapped)
                    html.Td(
                        f"${total_pnl:+,.0f}",
                        style={
                            **num_style,
                            "textAlign": "right",
                            "color": _text_color(total_pnl),
                            "backgroundColor": _heat_bg(total_pnl, threshold=500.0),
                            "fontWeight": "700",
                        },
                    ),
                    # Win Rate (heat-mapped around 50%)
                    html.Td(
                        f"{accuracy:.0f}%",
                        style={
                            **num_style,
                            "textAlign": "right",
                            "color": _text_color(accuracy, center=50.0),
                            "backgroundColor": _heat_bg(accuracy, threshold=20.0, center=50.0),
                            "fontWeight": "600",
                        },
                    ),
                    # Avg Confidence
                    html.Td(
                        f"{avg_conf * 100:.0f}" if avg_conf else "-",
                        style={
                            **num_style,
                            "textAlign": "right",
                            "color": COLORS["text_muted"],
                        },
                    ),
                ],
                id={"type": "screener-row", "index": symbol},
                className="screener-row",
                style=row_style,
            )
        )

    body = html.Tbody(rows)

    # Wrap in scrollable container
    table = html.Table(
        [header, body],
        style={
            "width": "100%",
            "borderCollapse": "collapse",
            "fontSize": "0.85rem",
            "color": COLORS["text"],
        },
    )

    return html.Div(
        table,
        style={
            "overflowX": "auto",
            "overflowY": "auto",
            "maxHeight": "650px",
            "borderRadius": "8px",
        },
    )
```

### Step 3: Modify `shitty_ui/pages/dashboard.py`

This is the largest change. We replace the analytics chart-tab card (lines 117-183) and the predictions feed card (lines 184-225) with the asset screener.

#### 3a. Update imports (top of file)

**Replace lines 25-42** (the `from data import ...` block and the `from components...` block):

The current imports at lines 25-42:

```python
from data import (
    get_unified_feed,
    get_sparkline_prices,
    get_performance_metrics,
    get_accuracy_by_confidence,
    get_accuracy_by_asset,
    get_predictions_with_outcomes,
    load_recent_posts,
    get_weekly_signal_count,
    get_high_confidence_metrics,
    get_best_performing_asset,
    get_accuracy_over_time,
    get_backtest_simulation,
    get_sentiment_accuracy,
    get_dashboard_kpis,
    get_dashboard_kpis_with_fallback,
    get_empty_state_context,
)
```

Replace with:

```python
from data import (
    get_unified_feed,
    get_sparkline_prices,
    get_performance_metrics,
    get_accuracy_by_confidence,
    get_accuracy_by_asset,
    get_asset_screener_data,
    get_screener_sparkline_prices,
    get_predictions_with_outcomes,
    load_recent_posts,
    get_weekly_signal_count,
    get_high_confidence_metrics,
    get_best_performing_asset,
    get_accuracy_over_time,
    get_backtest_simulation,
    get_sentiment_accuracy,
    get_dashboard_kpis,
    get_dashboard_kpis_with_fallback,
    get_empty_state_context,
)
from components.screener import build_screener_table
```

#### 3b. Replace the analytics and predictions sections in `create_dashboard_page()`

**Remove lines 116-225** (everything from `# ========== Analytics Section` through the end of `# ========== Unified Prediction Feed`).

**Replace with:**

```python
                    # ========== Asset Screener Table (Secondary tier - hero treatment) ==========
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                [
                                    html.I(className="fas fa-th-list me-2"),
                                    "Asset Screener",
                                    html.Small(
                                        " - performance by ticker, sorted & heat-mapped",
                                        style={
                                            "color": COLORS["text_muted"],
                                            "fontWeight": "normal",
                                        },
                                    ),
                                ],
                                className="fw-bold",
                                style={"backgroundColor": HIERARCHY["secondary"]["background"]},
                            ),
                            dbc.CardBody(
                                [
                                    dcc.Loading(
                                        type="circle",
                                        color=COLORS["accent"],
                                        children=html.Div(
                                            id="screener-table-container",
                                        ),
                                    ),
                                ],
                                style={
                                    "backgroundColor": HIERARCHY["secondary"]["background"],
                                    "padding": "12px",
                                },
                            ),
                        ],
                        className="mb-4",
                        style={
                            "backgroundColor": HIERARCHY["secondary"]["background"],
                            "borderTop": HIERARCHY["secondary"]["accent_top"],
                            "boxShadow": HIERARCHY["secondary"]["shadow"],
                        },
                    ),
```

#### 3c. Update the `update_dashboard` callback (lines 514-891)

The current callback outputs 6 values:

```python
Output("unified-feed-container", "children"),
Output("performance-metrics", "children"),
Output("accuracy-over-time-chart", "figure"),
Output("confidence-accuracy-chart", "figure"),
Output("asset-accuracy-chart", "figure"),
Output("last-update-timestamp", "data"),
```

**Replace the callback outputs (lines 515-521) with:**

```python
        [
            Output("screener-table-container", "children"),
            Output("performance-metrics", "children"),
            Output("last-update-timestamp", "data"),
        ],
```

**Replace the callback inputs (lines 522-526) with:**

```python
        [
            Input("refresh-interval", "n_intervals"),
            Input("selected-period", "data"),
        ],
```

**Replace the entire `update_dashboard` function body** with:

```python
    def update_dashboard(n_intervals, period):
        """Update main dashboard components with error boundaries."""
        errors = []

        # Convert period to days
        days_map = {"7d": 7, "30d": 30, "90d": 90, "all": None}
        days = days_map.get(period, 90)

        # Current timestamp for refresh indicator
        current_time = datetime.now().isoformat()

        # ===== Asset Screener Table =====
        try:
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
        except Exception as e:
            errors.append(f"Asset screener: {e}")
            print(f"Error loading asset screener: {traceback.format_exc()}")
            screener_table = create_error_card(
                "Unable to load asset screener", str(e)
            )

        # ===== Performance Metrics with error handling =====
        try:
            kpis = get_dashboard_kpis_with_fallback(days=days)
            fallback_note = kpis["fallback_label"] if kpis["is_fallback"] else ""

            # Create KPI metrics row
            metrics_row = dbc.Row(
                [
                    dbc.Col(
                        create_metric_card(
                            COPY["kpi_total_signals_title"],
                            f"{kpis['total_signals']}",
                            COPY["kpi_total_signals_subtitle"],
                            "signal",
                            COLORS["accent"],
                            note=fallback_note,
                        ),
                        xs=6,
                        sm=6,
                        md=3,
                        className="kpi-col-mobile",
                    ),
                    dbc.Col(
                        create_metric_card(
                            COPY["kpi_accuracy_title"],
                            f"{kpis['accuracy_pct']:.1f}%",
                            COPY["kpi_accuracy_subtitle"],
                            "bullseye",
                            COLORS["success"]
                            if kpis["accuracy_pct"] > 50
                            else COLORS["danger"],
                            note=fallback_note,
                        ),
                        xs=6,
                        sm=6,
                        md=3,
                        className="kpi-col-mobile",
                    ),
                    dbc.Col(
                        create_metric_card(
                            COPY["kpi_avg_return_title"],
                            f"{kpis['avg_return_t7']:+.2f}%",
                            COPY["kpi_avg_return_subtitle"],
                            "chart-line",
                            COLORS["success"]
                            if kpis["avg_return_t7"] > 0
                            else COLORS["danger"],
                            note=fallback_note,
                        ),
                        xs=6,
                        sm=6,
                        md=3,
                        className="kpi-col-mobile",
                    ),
                    dbc.Col(
                        create_metric_card(
                            COPY["kpi_pnl_title"],
                            f"${kpis['total_pnl']:+,.0f}",
                            COPY["kpi_pnl_subtitle"],
                            "dollar-sign",
                            COLORS["success"]
                            if kpis["total_pnl"] > 0
                            else COLORS["danger"],
                            note=fallback_note,
                        ),
                        xs=6,
                        sm=6,
                        md=3,
                        className="kpi-col-mobile",
                    ),
                ],
                className="g-2 g-md-2",
            )
        except Exception as e:
            errors.append(f"Performance metrics: {e}")
            print(f"Error loading performance metrics: {traceback.format_exc()}")
            metrics_row = create_error_card(
                "Unable to load performance metrics", str(e)
            )

        # Log any errors that occurred
        if errors:
            print(f"Dashboard update completed with errors: {errors}")

        return (
            screener_table,
            metrics_row,
            current_time,
        )
```

#### 3d. Remove the chart-click-to-asset callback (lines 926-946)

Delete the `handle_asset_chart_click` callback entirely (the one with `Input("asset-accuracy-chart", "clickData")`). The screener rows now link directly to asset pages via `dcc.Link`.

#### 3e. Add screener row click callback

Add a new callback **after the `update_dashboard` function** to handle row clicks:

```python
    # ========== Screener Row Click Handler ==========
    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        [Input({"type": "screener-row", "index": dash.ALL}, "n_clicks")],
        prevent_initial_call=True,
    )
    def handle_screener_row_click(n_clicks_list):
        """Navigate to asset page when a screener row is clicked."""
        if not any(n_clicks_list):
            from dash import no_update
            return no_update

        ctx = callback_context
        if not ctx.triggered:
            from dash import no_update
            return no_update

        # Extract the symbol from the triggered row's ID
        triggered_id = ctx.triggered[0]["prop_id"]
        try:
            import json
            # Pattern: {"index":"XLE","type":"screener-row"}.n_clicks
            id_str = triggered_id.split(".")[0]
            id_dict = json.loads(id_str)
            symbol = id_dict["index"]
            return f"/assets/{symbol}"
        except (json.JSONDecodeError, KeyError):
            from dash import no_update
            return no_update
```

**Important**: Add `import dash` to the top-level imports of `dashboard.py` (it is currently only importing specific items from `dash`).

Update line 6 from:

```python
from dash import Dash, html, dcc, dash_table, Input, Output, State, callback_context, MATCH
```

to:

```python
import dash
from dash import Dash, html, dcc, dash_table, Input, Output, State, callback_context, MATCH, ALL
```

### Step 4: Update `shitty_ui/layout.py` — Add CSS for screener

Add the following CSS rules to the `<style>` block in `app.index_string` (inside `layout.py`), **before the closing `</style>` tag** (before line 576):

```css
            /* ======================================
               Asset Screener Table
               ====================================== */
            .screener-row:hover {
                background-color: rgba(133, 187, 101, 0.06) !important;
            }
            .screener-row:hover td {
                background-color: rgba(133, 187, 101, 0.06) !important;
            }

            /* Sticky header for scrollable table */
            .screener-table-header th {
                position: sticky;
                top: 0;
                z-index: 1;
                background-color: #141E22 !important;
            }

            /* ======================================
               Screener: Tablet (max-width: 768px)
               ====================================== */
            @media (max-width: 768px) {
                /* Allow horizontal scroll on screener */
                .screener-table-container {
                    overflow-x: auto !important;
                    -webkit-overflow-scrolling: touch;
                }

                /* Hide less-important columns on tablet */
                .screener-hide-tablet {
                    display: none !important;
                }
            }

            /* ======================================
               Screener: Mobile (max-width: 480px)
               ====================================== */
            @media (max-width: 480px) {
                /* Compact row height */
                .screener-row td {
                    padding: 6px 8px !important;
                    font-size: 0.8rem !important;
                }

                /* Hide sparkline and confidence on mobile */
                .screener-hide-mobile {
                    display: none !important;
                }
            }
```

Also update `layout.py` to import the new data functions. In the re-export block at line 49-56, add:

```python
from data import (  # noqa: F401
    get_recent_signals,
    get_performance_metrics,
    get_accuracy_by_confidence,
    get_accuracy_by_asset,
    get_asset_screener_data,
    get_screener_sparkline_prices,
    get_active_assets_from_db,
    get_available_assets,
)
```

---

## Responsive Behavior

### Desktop (>= 768px)
All 8 columns visible. Table fits comfortably within 1400px container. Vertical scroll kicks in after ~13 rows (650px max-height).

### Tablet (768px)
Table scrolls horizontally. All columns remain visible but the container allows swipe-scroll. Confidence column can optionally be hidden if space is tight (add `className="screener-hide-tablet"` to the Confidence `<th>` and `<td>` elements).

### Mobile (< 480px)
- Sparkline column and Confidence column hidden via CSS class `screener-hide-mobile`
- Remaining 6 columns: Asset, Predictions, Sentiment, 7d Return, Total P&L, Win Rate
- Row padding reduced to 6px
- Table still scrolls horizontally if needed
- This matches the SaaS Meltdown mobile pattern (`ref-saasmeltdown-mobile.png`): show ticker + essential metrics, hide visual chrome

### Small phone (375px)
Same as 480px mobile behavior. The reduced column set (6 columns) fits within 375px without horizontal scroll in most cases.

---

## Accessibility Checklist

- [ ] Table uses semantic `<table>`, `<thead>`, `<tbody>`, `<tr>`, `<th>`, `<td>` (Dash html elements map to these)
- [ ] Column headers use `<th>` with scope="col" implied by placement in `<thead>`
- [ ] Heat-mapped cells use BOTH color AND text (the value is always printed, color is supplementary)
- [ ] Sentiment badges show text ("BULL"/"BEAR"/"NEUT") not just color
- [ ] Clickable rows have `cursor: pointer` visual cue AND the Asset column has an explicit `dcc.Link`
- [ ] Sparklines have hover tooltips (from Plotly) showing date and price
- [ ] Sort headers have visible sort icon indicator
- [ ] Contrast ratio: all text colors meet WCAG AA against the dark backgrounds (verified: `#f1f5f9` on `#1e293b` = 11.8:1, `#94a3b8` on `#1e293b` = 5.4:1)

---

## Test Plan

### New Tests to Write

Create `shit_tests/shitty_ui/components/test_screener.py`:

```
test_build_screener_table_with_data()
    - Given: DataFrame with 5 assets, sparkline data dict with 3 of 5 symbols
    - Verify: Returns html.Div containing html.Table
    - Verify: Table has 5 body rows
    - Verify: Missing sparkline symbols get placeholder component

test_build_screener_table_empty()
    - Given: Empty DataFrame
    - Verify: Returns empty state message div
    - Verify: No html.Table in output

test_heat_bg_positive()
    - Given: value=3.0, threshold=5.0
    - Verify: Returns rgba string with green color
    - Verify: Intensity = 3/5 * 0.15 = 0.09

test_heat_bg_negative()
    - Given: value=-2.5, threshold=5.0
    - Verify: Returns rgba string with red color

test_heat_bg_zero()
    - Given: value=0.0, threshold=5.0
    - Verify: Returns transparent rgba

test_heat_bg_win_rate_above_50()
    - Given: value=65.0, threshold=20.0, center=50.0
    - Verify: Returns green rgba (delta=15, intensity=15/20*0.15)

test_heat_bg_win_rate_below_50()
    - Given: value=35.0, threshold=20.0, center=50.0
    - Verify: Returns red rgba (delta=-15)

test_sentiment_badge_bullish()
    - Verify: Returns span with text "BULL", green color
test_sentiment_badge_bearish()
    - Verify: Returns span with text "BEAR", red color
test_sentiment_badge_none()
    - Verify: Returns span with text "NEUT", muted color

test_sort_by_total_pnl_descending()
    - Given: DataFrame with varied P&L values
    - Verify: Rows are ordered by total_pnl descending

test_sort_by_accuracy_ascending()
    - Given: DataFrame with varied accuracy values
    - Verify: Rows are ordered by accuracy ascending
```

Create `shit_tests/shitty_ui/test_data_screener.py`:

```
test_get_asset_screener_data_returns_expected_columns()
    - Mock execute_query to return sample rows
    - Verify: DataFrame has all expected columns including accuracy, latest_sentiment, avg_confidence

test_get_asset_screener_data_calculates_accuracy()
    - Mock: 10 total, 6 correct
    - Verify: accuracy = 60.0

test_get_asset_screener_data_with_days_filter()
    - Verify: SQL includes date filter when days is not None

test_get_asset_screener_data_empty()
    - Mock: empty result set
    - Verify: Returns empty DataFrame

test_get_screener_sparkline_prices_returns_dict()
    - Mock execute_query with multi-symbol data
    - Verify: Returns dict keyed by symbol with DataFrames

test_get_screener_sparkline_prices_empty_symbols()
    - Verify: Returns empty dict when symbols tuple is empty
```

### Existing Tests to Verify

The dashboard callback tests in `shit_tests/shitty_ui/` will need updating because:

1. The `update_dashboard` callback now returns 3 outputs instead of 6
2. The `handle_asset_chart_click` callback is removed
3. A new `handle_screener_row_click` callback exists

Check and update any tests in:
- `shit_tests/shitty_ui/test_dashboard_callbacks.py` (if it exists)
- `shit_tests/shitty_ui/pages/test_dashboard.py` (if it exists)

### Manual Verification Steps

1. Run the dashboard locally: `source venv/bin/activate && python -m shitty_ui.app`
2. Verify the screener table loads on the homepage with data from the database
3. Verify sparklines render inline for each asset
4. Verify heat-mapping: positive returns show green bg, negative show red bg
5. Verify clicking a row navigates to `/assets/<SYMBOL>`
6. Verify time period buttons (7D/30D/90D/All) filter the screener data
7. Resize to 768px: verify horizontal scroll works
8. Resize to 375px: verify sparkline and confidence columns hide

---

## Documentation Updates

### `brand_copy.py`

No new copy constants needed. The screener header text ("Asset Screener") and subtitle are hardcoded in the card component for now. If the user wants to make them configurable, add:

```python
"screener_header": "Asset Screener",
"screener_subtitle": " - performance by ticker, sorted & heat-mapped",
"screener_empty": "No asset data yet. The market hasn't had time to prove us wrong.",
```

This is optional and can be deferred.

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Changed
- **Dashboard Homepage** - Replaced analytics chart tabs and prediction feed with SaaS Meltdown-style asset screener table
  - Per-asset rows with inline sparklines, sentiment badges, and heat-mapped returns/P&L
  - Click any row to drill into asset detail page
  - Table respects time period filter (7D/30D/90D/All)
  - KPI hero cards remain above the screener (unchanged)
```

---

## Stress Testing & Edge Cases

### Edge Cases

1. **Zero assets in period**: When `get_asset_screener_data()` returns empty (e.g., 7D period with no evaluated predictions), the table shows the empty state message. The KPI cards will already show fallback all-time data via `get_dashboard_kpis_with_fallback()`.

2. **Asset with no price data**: `get_screener_sparkline_prices()` may not return data for all symbols (e.g., delisted tickers). The `_sparkline_cell()` function handles this by rendering `create_sparkline_placeholder()` (the existing "No price data" component).

3. **NULL sentiment**: Some assets may not have a `latest_sentiment` if the join fails. The `_sentiment_badge()` function defaults to "NEUT" when sentiment is None.

4. **NULL avg_confidence**: Rendered as "-" (dash) instead of a number.

5. **Very large P&L values**: The `$+12,345` format handles up to 6 digits. Values over $99,999 still display correctly with comma separators.

6. **Single-asset dataset**: The table works with 1 row. The `HAVING COUNT(*) >= 2` filter in the SQL ensures only assets with at least 2 evaluated predictions appear.

### Performance Considerations

- **Single SQL query**: `get_asset_screener_data()` uses a CTE to join metrics + sentiment in one round-trip (not N+1)
- **Batch sparkline fetch**: `get_screener_sparkline_prices()` fetches all symbols in one query
- **TTL caching**: Both functions cache for 5 minutes (matching dashboard refresh interval)
- **Static sparklines**: Screener sparklines use `staticPlot: True` (no hover interaction) to reduce Plotly rendering overhead. This is intentionally different from the signal card sparklines which allow hover.
- **Expected row count**: ~15 rows (current production has 15 tracked tickers). This is well within DOM performance limits for Dash.

---

## Verification Checklist

- [ ] `ruff check shitty_ui/components/screener.py` passes
- [ ] `ruff check shitty_ui/data.py` passes
- [ ] `ruff check shitty_ui/pages/dashboard.py` passes
- [ ] `ruff format --check shitty_ui/` passes
- [ ] `pytest shit_tests/shitty_ui/` passes (existing tests, may need callback output count updates)
- [ ] New tests pass: `pytest shit_tests/shitty_ui/components/test_screener.py`
- [ ] New tests pass: `pytest shit_tests/shitty_ui/test_data_screener.py`
- [ ] Dashboard loads at `localhost:8050/` with screener table visible
- [ ] Each row links to correct `/assets/<SYMBOL>` page
- [ ] Time period buttons filter screener data correctly
- [ ] Heat-mapping visually distinguishes positive/negative values
- [ ] Mobile (375px) hides sparkline and confidence columns
- [ ] No JavaScript console errors

---

## What NOT To Do

1. **Do NOT remove the KPI hero cards.** They stay above the screener unchanged. The 4-card row at the top of the dashboard is kept as-is.

2. **Do NOT add client-side sorting yet.** The initial implementation sorts server-side in `build_screener_table()` via pandas. A future phase can add client-side sort callbacks if needed, but keep this PR simple. The sort headers are styled but clicking them does not yet trigger a re-sort -- that is deferred to avoid callback complexity in this PR.

3. **Do NOT delete the Performance page (`/performance`).** The screener replaces content on the Dashboard homepage only. The Performance page keeps its own asset table, confidence chart, and sentiment donut. The `create_performance_page()` and `update_performance_page()` callback remain untouched.

4. **Do NOT modify `components/sparkline.py`.** Reuse `build_sparkline_figure()` as-is. The only difference is passing `prediction_date=None` (no marker dot) for screener sparklines.

5. **Do NOT add sortable column callbacks in this PR.** The `_sort_header()` renders sort icons but they are purely decorative in Phase 03. Adding interactive sort requires a `dcc.Store` for sort state and a re-render callback, which adds complexity. Defer to a follow-up PR.

6. **Do NOT change the `get_accuracy_by_asset()` function.** Keep it for backward compatibility (the Performance page still uses it). The new `get_asset_screener_data()` is a separate function that covers the screener's broader needs.

7. **Do NOT remove the `get_unified_feed` import entirely.** Other callbacks or future phases may still reference it. Only remove it from the `update_dashboard` callback's body. Keep the import at the top of `dashboard.py`.

8. **Do NOT make sparklines interactive (hover/zoom).** Use `staticPlot: True` for screener sparklines. Interactive sparklines in a 15-row table with 120px charts create performance issues and visual noise. Hover is available on the signal card sparklines -- the screener ones are for glanceability only.

9. **Do NOT attempt to make the `<tr>` elements themselves into `dcc.Link` wrappers.** Dash does not support wrapping table rows in links. Instead, each row has an `id` pattern-match and an `n_clicks` callback, plus the Asset cell has an explicit `dcc.Link`. Both paths navigate to the asset detail page.

10. **Do NOT remove the "Latest Shitposts" section or the collapsible data table.** These tertiary sections remain below the screener. They serve different purposes (raw post feed and filtered prediction data) and are untouched by this phase.
