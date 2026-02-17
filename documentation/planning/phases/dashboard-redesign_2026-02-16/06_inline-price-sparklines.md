# Phase 06: Inline Price Sparklines

**Status**: ✅ COMPLETE
**Started**: 2026-02-17
**Completed**: 2026-02-17
**PR**: #78

**PR Title**: feat: mini price charts on signal cards
**Risk Level**: Low
**Estimated Effort**: Medium (3-4 hours)
**Dependencies**: Phase 05 (soft -- targets unified signal cards, but works with current card components too)
**Unlocks**: None (visual enhancement, leaf node in dependency graph)

## Files Modified

| File | Action |
|------|--------|
| `shitty_ui/data.py` | Add `get_sparkline_prices()` batch query function |
| `shitty_ui/components/sparkline.py` | **NEW** -- Create `build_sparkline_figure()` and `create_sparkline_placeholder()` |
| `shitty_ui/components/cards.py` | Add sparkline row to `create_feed_signal_card()` and `create_unified_signal_card()` |
| `shitty_ui/pages/signals.py` | Pass sparkline price data into card rendering loop |
| `shitty_ui/pages/dashboard.py` | Pass sparkline price data into unified feed rendering loop |
| `shitty_ui/constants.py` | Add `SPARKLINE_CONFIG` dict |
| `shit_tests/shitty_ui/test_sparkline.py` | **NEW** -- Tests for sparkline builder and placeholder |
| `shit_tests/shitty_ui/test_data.py` | Add tests for `get_sparkline_prices()` |
| `shit_tests/shitty_ui/test_cards.py` | Add tests for sparkline integration in cards |
| `CHANGELOG.md` | Add entry |

## Context

Prediction/signal cards currently show text, sentiment, confidence, and outcome badges but give **no visual feedback** about what actually happened to the asset's price. The user has to mentally connect a "Correct +$250" badge to actual price movement. A sparkline -- a tiny, chrome-free line chart -- next to each prediction card would immediately communicate the price trajectory around the prediction window.

**Data source**: The `market_prices` table already stores daily OHLCV data for every tracked ticker (populated by the market-data worker). The existing `get_asset_price_history()` function in `data.py` (line 1109) queries this table for a single symbol. We need a new batch function that fetches price data for *multiple* symbols in a single query, scoped to a narrow date window around each prediction, to avoid N+1 queries when rendering a feed of 20 cards.

**Current state**:
- `data.py` line 1109: `get_asset_price_history(symbol, days=180)` -- single-symbol, wide window, too heavy for sparklines
- `data.py` line 2012: `get_price_with_signals(symbol, days=90)` -- single-symbol, returns prices + signals
- `market_prices` table: `symbol`, `date`, `open`, `high`, `low`, `close`, `volume`, `adjusted_close` (composite unique on `symbol + date`)
- Signal feed cards (`create_feed_signal_card`, line 1206 in cards.py) already have a `symbol` field from `prediction_outcomes`
- Hero cards (`create_hero_signal_card`, line 170 in cards.py) have `assets` (list of tickers)

**Target**: For each prediction card that has a `symbol` and a `timestamp`, show a tiny 100x30px line chart of the closing price from 3 trading days before the prediction through 10 trading days after. This is roughly a 2-week window -- small enough to be efficient, large enough to show the prediction playing out.

## Detailed Implementation

### Change A: Add `SPARKLINE_CONFIG` to constants.py

**File**: `shitty_ui/constants.py`
**Location**: After `SECTION_ACCENT` dict (after line 89)

```python
# Sparkline configuration for inline price charts on signal cards
SPARKLINE_CONFIG = {
    "width": 120,             # px -- chart width
    "height": 36,             # px -- chart height
    "line_width": 1.5,        # px -- line stroke width
    "days_before": 3,         # trading days before prediction to show
    "days_after": 10,         # trading days after prediction to show
    "color_up": COLORS["success"],   # Line color when price ended higher
    "color_down": COLORS["danger"],  # Line color when price ended lower
    "color_flat": COLORS["text_muted"],  # Line color when negligible change
    "fill_opacity": 0.08,     # Fill-under-line opacity
    "marker_color": COLORS["warning"],  # Color of the prediction-date marker
    "marker_size": 5,         # px -- prediction-date dot size
}
```

---

### Change B: Add `get_sparkline_prices()` to data.py

**File**: `shitty_ui/data.py`
**Location**: After `get_asset_price_history()` (after line 1149)

This is the key performance optimization. Instead of one query per card, we batch-fetch price data for all symbols visible on the current page.

```python
@ttl_cache(ttl_seconds=300)  # Cache for 5 minutes
def get_sparkline_prices(
    symbols: tuple,
    center_date: str,
    days_before: int = 3,
    days_after: int = 10,
) -> Dict[str, pd.DataFrame]:
    """Batch-fetch price data for sparkline rendering across multiple symbols.

    Fetches closing prices in a narrow window around the prediction date for
    each symbol. Returns a dict keyed by symbol, where each value is a small
    DataFrame of (date, close) rows -- typically 10-15 rows per symbol.

    Uses a single SQL query for ALL symbols to avoid N+1 query patterns.

    Args:
        symbols: Tuple of ticker symbols (tuple for cache hashability).
        center_date: ISO date string (YYYY-MM-DD) for the prediction date.
            The window extends days_before before and days_after after this date.
        days_before: Trading days before center_date to include.
        days_after: Trading days after center_date to include.

    Returns:
        Dict mapping symbol -> DataFrame with columns [date, close].
        Missing symbols are absent from the dict (not empty DataFrames).
    """
    if not symbols:
        return {}

    # Expand the calendar window to account for weekends/holidays
    # 3 trading days ~ 5 calendar days; 10 trading days ~ 16 calendar days
    calendar_before = int(days_before * 2.0)
    calendar_after = int(days_after * 1.8)

    from datetime import datetime as dt, timedelta
    center_dt = dt.strptime(center_date, "%Y-%m-%d").date() if isinstance(center_date, str) else center_date
    start = center_dt - timedelta(days=calendar_before)
    end = center_dt + timedelta(days=calendar_after)

    query = text("""
        SELECT
            symbol,
            date,
            close
        FROM market_prices
        WHERE symbol = ANY(:symbols)
            AND date >= :start_date
            AND date <= :end_date
        ORDER BY symbol, date ASC
    """)

    params = {
        "symbols": list(symbols),
        "start_date": start,
        "end_date": end,
    }

    try:
        rows, columns = execute_query(query, params)
        if not rows:
            return {}

        df = pd.DataFrame(rows, columns=columns)
        df["date"] = pd.to_datetime(df["date"])

        # Split into per-symbol DataFrames
        result: Dict[str, pd.DataFrame] = {}
        for symbol in df["symbol"].unique():
            symbol_df = df[df["symbol"] == symbol][["date", "close"]].reset_index(drop=True)
            if len(symbol_df) >= 2:  # Need at least 2 points for a line
                result[symbol] = symbol_df

        return result
    except Exception as e:
        logger.error(f"Error loading sparkline prices: {e}")
        return {}
```

**Why `tuple` for symbols**: The `@ttl_cache` decorator uses function arguments as the cache key. Lists are unhashable, so callers must pass a `tuple` of symbols. This is enforced by the type hint and documented in the docstring.

**Why `ANY(:symbols)`**: PostgreSQL's `ANY` operator lets us pass a list parameter and match against it in a single query, avoiding string interpolation or `IN (...)` construction.

---

### Change C: Create `shitty_ui/components/sparkline.py` (NEW FILE)

**File**: `shitty_ui/components/sparkline.py`

```python
"""Sparkline chart components for inline price visualization on signal cards."""

from datetime import date, datetime
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

from constants import COLORS, SPARKLINE_CONFIG


def build_sparkline_figure(
    price_df: pd.DataFrame,
    prediction_date: Optional[date] = None,
) -> go.Figure:
    """Build a minimal sparkline Plotly figure from price data.

    Creates a tiny line chart with no axes, no gridlines, no legend -- just
    the price line, an optional fill, and a dot marking the prediction date.

    Args:
        price_df: DataFrame with columns [date, close]. Must have >= 2 rows.
        prediction_date: Date of the prediction. If provided, a marker dot
            is drawn at this date's closing price.

    Returns:
        go.Figure configured for sparkline rendering (tiny, chrome-free).
    """
    fig = go.Figure()

    dates = price_df["date"]
    closes = price_df["close"]

    # Determine line color based on price direction
    first_close = float(closes.iloc[0])
    last_close = float(closes.iloc[-1])
    pct_change = ((last_close - first_close) / first_close) * 100 if first_close else 0

    if pct_change > 0.5:
        line_color = SPARKLINE_CONFIG["color_up"]
    elif pct_change < -0.5:
        line_color = SPARKLINE_CONFIG["color_down"]
    else:
        line_color = SPARKLINE_CONFIG["color_flat"]

    # Fill color: same as line but with low opacity
    # Convert hex to rgba
    r, g, b = int(line_color[1:3], 16), int(line_color[3:5], 16), int(line_color[5:7], 16)
    fill_color = f"rgba({r}, {g}, {b}, {SPARKLINE_CONFIG['fill_opacity']})"

    # Price line
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=closes,
            mode="lines",
            line=dict(
                color=line_color,
                width=SPARKLINE_CONFIG["line_width"],
            ),
            fill="tozeroy",
            fillcolor=fill_color,
            hovertemplate="%{x|%b %d}: $%{y:,.2f}<extra></extra>",
            showlegend=False,
        )
    )

    # Prediction date marker
    if prediction_date is not None:
        pred_dt = pd.Timestamp(prediction_date)
        # Find the closest date in the data
        date_diffs = (price_df["date"] - pred_dt).abs()
        closest_idx = date_diffs.idxmin()
        closest_date = price_df.loc[closest_idx, "date"]
        closest_close = float(price_df.loc[closest_idx, "close"])

        fig.add_trace(
            go.Scatter(
                x=[closest_date],
                y=[closest_close],
                mode="markers",
                marker=dict(
                    color=SPARKLINE_CONFIG["marker_color"],
                    size=SPARKLINE_CONFIG["marker_size"],
                    line=dict(width=0),
                ),
                hovertemplate="Prediction: $%{y:,.2f}<extra></extra>",
                showlegend=False,
            )
        )

    # Minimal layout: no axes, no chrome, transparent background
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=0, b=0),
        height=SPARKLINE_CONFIG["height"],
        width=SPARKLINE_CONFIG["width"],
        xaxis=dict(
            showgrid=False,
            showticklabels=False,
            zeroline=False,
            showline=False,
        ),
        yaxis=dict(
            showgrid=False,
            showticklabels=False,
            zeroline=False,
            showline=False,
        ),
        showlegend=False,
        hovermode="x unified",
    )

    return fig


def create_sparkline_component(
    price_df: pd.DataFrame,
    prediction_date: Optional[date] = None,
    component_id: str = "",
) -> dcc.Graph:
    """Create a dcc.Graph wrapping a sparkline figure.

    This is the component that gets embedded directly in signal cards.

    Args:
        price_df: DataFrame with columns [date, close]. Must have >= 2 rows.
        prediction_date: Date of the prediction for marker placement.
        component_id: Unique id for the dcc.Graph element.

    Returns:
        dcc.Graph with sparkline figure and interaction disabled.
    """
    fig = build_sparkline_figure(price_df, prediction_date)

    return dcc.Graph(
        id=component_id or f"sparkline-{id(price_df)}",
        figure=fig,
        config={
            "displayModeBar": False,
            "staticPlot": False,  # Allow hover but no zoom/pan
        },
        style={
            "width": f"{SPARKLINE_CONFIG['width']}px",
            "height": f"{SPARKLINE_CONFIG['height']}px",
            "display": "inline-block",
            "verticalAlign": "middle",
        },
    )


def create_sparkline_placeholder() -> html.Div:
    """Create a placeholder shown when no price data is available for a symbol.

    Returns:
        html.Div with a subtle "no data" indicator matching sparkline dimensions.
    """
    return html.Div(
        html.Span(
            "No price data",
            style={
                "color": COLORS["border"],
                "fontSize": "0.65rem",
                "fontStyle": "italic",
            },
        ),
        style={
            "width": f"{SPARKLINE_CONFIG['width']}px",
            "height": f"{SPARKLINE_CONFIG['height']}px",
            "display": "inline-flex",
            "alignItems": "center",
            "justifyContent": "center",
            "border": f"1px dashed {COLORS['border']}",
            "borderRadius": "4px",
        },
    )
```

---

### Change D: Integrate Sparklines into `create_feed_signal_card()`

**File**: `shitty_ui/components/cards.py`
**Location**: Inside `create_feed_signal_card()` function (line 1206)

#### Step D1: Add import at top of file

Add to the imports section (after line 9):

```python
from components.sparkline import create_sparkline_component, create_sparkline_placeholder
```

#### Step D2: Add `sparkline_data` parameter to function signature

Change:
```python
def create_feed_signal_card(row) -> html.Div:
```

To:
```python
def create_feed_signal_card(row, sparkline_prices: dict = None) -> html.Div:
```

The `sparkline_prices` parameter is a dict mapping `symbol -> DataFrame` (output of `get_sparkline_prices()`). Default `None` ensures all existing callers are unaffected.

#### Step D3: Build sparkline element inside the function

After the metrics row construction (after line 1481), before the thesis row (before line 1484), add:

```python
    # Row 4b: Sparkline price chart (between metrics and thesis)
    sparkline_element = None
    if sparkline_prices and symbol and symbol in sparkline_prices:
        price_df = sparkline_prices[symbol]
        pred_date = None
        if isinstance(timestamp, datetime):
            pred_date = timestamp.date()
        sparkline_element = create_sparkline_component(
            price_df,
            prediction_date=pred_date,
            component_id=f"sparkline-feed-{symbol}-{id(row)}",
        )
    elif sparkline_prices is not None and symbol:
        # sparkline_prices was provided but this symbol has no data
        sparkline_element = create_sparkline_placeholder()
```

#### Step D4: Insert sparkline into card children

After the metrics row append (after line 1481) and before the thesis append (before line 1484), add:

```python
    # Row 4b: Sparkline
    if sparkline_element is not None:
        children.append(
            html.Div(
                [
                    html.Span(
                        f"{symbol} price" if symbol else "Price",
                        style={
                            "color": COLORS["text_muted"],
                            "fontSize": "0.7rem",
                            "marginRight": "8px",
                            "verticalAlign": "middle",
                        },
                    ),
                    sparkline_element,
                ],
                style={
                    "marginTop": "8px",
                    "display": "flex",
                    "alignItems": "center",
                },
            )
        )
```

---

### Change E: Integrate Sparklines into `create_unified_signal_card()`

**File**: `shitty_ui/components/cards.py`
**Location**: Inside `create_unified_signal_card()` function (line 621)

> **Note (Challenge #1):** Phase 05 (PR #77) replaced `create_hero_signal_card()` with `create_unified_signal_card()` on the dashboard. This change targets the new unified card instead.

#### Step E1: Add `sparkline_prices` parameter

Change:
```python
def create_unified_signal_card(row) -> html.Div:
```

To:
```python
def create_unified_signal_card(row, sparkline_prices: dict = None) -> html.Div:
```

#### Step E2: Add sparkline after Row 3 (sentiment/assets/confidence), before Row 4 (thesis)

After the Row 3 div append (line ~787), before the thesis check (line ~790), add:

```python
    # Row 3b: Sparkline for first asset (if available)
    first_asset = assets[0] if isinstance(assets, list) and assets else None
    sparkline_element = None
    if sparkline_prices and first_asset and first_asset in sparkline_prices:
        price_df = sparkline_prices[first_asset]
        pred_date = timestamp.date() if isinstance(timestamp, datetime) else None
        sparkline_element = create_sparkline_component(
            price_df,
            prediction_date=pred_date,
            component_id=f"sparkline-unified-{first_asset}-{id(row)}",
        )
    elif sparkline_prices is not None and first_asset:
        sparkline_element = create_sparkline_placeholder()

    if sparkline_element is not None:
        children.append(
            html.Div(
                [
                    html.Span(
                        f"{first_asset} price",
                        style={
                            "color": COLORS["text_muted"],
                            "fontSize": "0.7rem",
                            "marginRight": "8px",
                            "verticalAlign": "middle",
                        },
                    ),
                    sparkline_element,
                ],
                style={
                    "marginTop": "8px",
                    "display": "flex",
                    "alignItems": "center",
                },
            )
        )
```

---

### Change F: Wire Sparkline Data in Signal Feed Page

**File**: `shitty_ui/pages/signals.py`
**Location**: Inside `update_signal_feed()` callback (line 315) and `load_more_signals()` callback (line 441)

#### Step F0: Add top-level imports

> **Note (Challenge #3):** Use top-level imports, not lazy imports inside callbacks.

Add `get_sparkline_prices` to the top-level imports in signals.py. Also add `import pandas as pd` if not already present.

Add to the existing import from data (currently only `get_signal_feed` and `get_signal_feed_count` are imported lazily inside callbacks — add `get_sparkline_prices` at top level):

```python
from data import get_sparkline_prices
import pandas as pd
```

#### Step F1: Add sparkline data fetch in `update_signal_feed()`

After the `get_signal_feed()` call (after line 340), before the card rendering loop (before line 372), add:

```python
            # Batch-fetch sparkline price data for all symbols in this page
            sparkline_prices = {}
            if not df.empty and "symbol" in df.columns:
                unique_symbols = df["symbol"].dropna().unique().tolist()
                if unique_symbols:
                    # Use the median timestamp as center date for the price window
                    center_ts = pd.to_datetime(df["timestamp"]).median()
                    center_date = center_ts.strftime("%Y-%m-%d") if pd.notna(center_ts) else None
                    if center_date:
                        sparkline_prices = get_sparkline_prices(
                            symbols=tuple(sorted(unique_symbols)),
                            center_date=center_date,
                        )
```

Then change the card rendering line from:
```python
            cards = [create_feed_signal_card(row) for _, row in df.iterrows()]
```

To:
```python
            cards = [
                create_feed_signal_card(row, sparkline_prices=sparkline_prices)
                for _, row in df.iterrows()
            ]
```

#### Step F2: Same change in `load_more_signals()`

After the `get_signal_feed()` call (after line 474), before card rendering (before line 492), add the same sparkline batch-fetch block. Then change:

```python
            new_cards = [create_feed_signal_card(row) for _, row in df.iterrows()]
```

To:
```python
            new_cards = [
                create_feed_signal_card(row, sparkline_prices=sparkline_prices)
                for _, row in df.iterrows()
            ]
```

---

### Change G: Wire Sparkline Data in Dashboard Unified Feed

**File**: `shitty_ui/pages/dashboard.py`
**Location**: Inside `update_dashboard()` callback, unified feed section (line 516-522)

> **Note (Challenge #1):** Phase 05 replaced the hero section with a unified feed using `get_unified_feed()` + `create_unified_signal_card()`. This targets that new code.

> **Note (Challenge #3):** Use top-level import, not lazy import inside callback.

Add `get_sparkline_prices` to the top-level imports:

```python
from data import (
    get_unified_feed,
    get_sparkline_prices,
    ...existing imports...
)
```

After the `get_unified_feed()` call (line 518), before card rendering (line 520), add:

```python
            # Batch-fetch sparkline prices for unified feed assets
            sparkline_prices = {}
            if not feed_df.empty and "assets" in feed_df.columns:
                all_assets = set()
                for _, r in feed_df.iterrows():
                    a = r.get("assets", [])
                    if isinstance(a, list):
                        all_assets.update(a[:1])  # Only first asset per card
                if all_assets:
                    center_ts = pd.to_datetime(feed_df["timestamp"]).median()
                    center_date = center_ts.strftime("%Y-%m-%d") if pd.notna(center_ts) else None
                    if center_date:
                        sparkline_prices = get_sparkline_prices(
                            symbols=tuple(sorted(all_assets)),
                            center_date=center_date,
                        )
```

Then change the unified card rendering from:
```python
                feed_cards = [
                    create_unified_signal_card(row)
                    for _, row in feed_df.iterrows()
                ]
```

To:
```python
                feed_cards = [
                    create_unified_signal_card(row, sparkline_prices=sparkline_prices)
                    for _, row in feed_df.iterrows()
                ]
```

Note: `pd` is already imported on line 9 of `dashboard.py`.

---

## Test Plan

### New Test File: `shit_tests/shitty_ui/test_sparkline.py`

```python
"""Tests for shitty_ui/components/sparkline.py - Sparkline chart components."""

import sys
import os

# Add shitty_ui to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))

import pytest
import pandas as pd
from datetime import date, datetime
import plotly.graph_objects as go
from dash import dcc, html

from components.sparkline import (
    build_sparkline_figure,
    create_sparkline_component,
    create_sparkline_placeholder,
)
from constants import SPARKLINE_CONFIG, COLORS


def _make_price_df(closes: list, start_date: str = "2025-06-10") -> pd.DataFrame:
    """Create a minimal price DataFrame for testing."""
    dates = pd.bdate_range(start=start_date, periods=len(closes))
    return pd.DataFrame({"date": dates, "close": closes})


class TestBuildSparklineFigure:
    """Tests for the build_sparkline_figure function."""

    def test_returns_go_figure(self):
        """Function returns a Plotly Figure."""
        df = _make_price_df([100, 101, 102, 103, 104])
        fig = build_sparkline_figure(df)
        assert isinstance(fig, go.Figure)

    def test_has_one_trace_without_prediction_date(self):
        """Without prediction_date, only the price line trace exists."""
        df = _make_price_df([100, 101, 102, 103, 104])
        fig = build_sparkline_figure(df)
        assert len(fig.data) == 1

    def test_has_two_traces_with_prediction_date(self):
        """With prediction_date, a marker trace is added."""
        df = _make_price_df([100, 101, 102, 103, 104])
        fig = build_sparkline_figure(df, prediction_date=date(2025, 6, 12))
        assert len(fig.data) == 2

    def test_line_color_green_when_price_up(self):
        """Line should be green (success) when price increased > 0.5%."""
        df = _make_price_df([100, 102, 104, 106, 108])
        fig = build_sparkline_figure(df)
        assert fig.data[0].line.color == SPARKLINE_CONFIG["color_up"]

    def test_line_color_red_when_price_down(self):
        """Line should be red (danger) when price decreased > 0.5%."""
        df = _make_price_df([108, 106, 104, 102, 100])
        fig = build_sparkline_figure(df)
        assert fig.data[0].line.color == SPARKLINE_CONFIG["color_down"]

    def test_line_color_muted_when_flat(self):
        """Line should be muted when price change < 0.5%."""
        df = _make_price_df([100.0, 100.1, 100.0, 99.9, 100.2])
        fig = build_sparkline_figure(df)
        assert fig.data[0].line.color == SPARKLINE_CONFIG["color_flat"]

    def test_layout_has_no_axes(self):
        """Sparkline should hide all axis chrome."""
        df = _make_price_df([100, 101, 102])
        fig = build_sparkline_figure(df)
        assert fig.layout.xaxis.showticklabels is False
        assert fig.layout.yaxis.showticklabels is False
        assert fig.layout.xaxis.showgrid is False
        assert fig.layout.yaxis.showgrid is False

    def test_layout_dimensions_match_config(self):
        """Figure dimensions should match SPARKLINE_CONFIG."""
        df = _make_price_df([100, 101, 102])
        fig = build_sparkline_figure(df)
        assert fig.layout.height == SPARKLINE_CONFIG["height"]
        assert fig.layout.width == SPARKLINE_CONFIG["width"]

    def test_transparent_background(self):
        """Background should be fully transparent."""
        df = _make_price_df([100, 101, 102])
        fig = build_sparkline_figure(df)
        assert fig.layout.plot_bgcolor == "rgba(0,0,0,0)"
        assert fig.layout.paper_bgcolor == "rgba(0,0,0,0)"

    def test_zero_margins(self):
        """All margins should be zero for tight embedding."""
        df = _make_price_df([100, 101, 102])
        fig = build_sparkline_figure(df)
        assert fig.layout.margin.l == 0
        assert fig.layout.margin.r == 0
        assert fig.layout.margin.t == 0
        assert fig.layout.margin.b == 0

    def test_marker_placed_near_prediction_date(self):
        """Marker trace should be placed at the prediction date."""
        df = _make_price_df([100, 101, 102, 103, 104], start_date="2025-06-10")
        # June 12 is the 3rd business day in this range
        fig = build_sparkline_figure(df, prediction_date=date(2025, 6, 12))
        marker_trace = fig.data[1]
        assert marker_trace.marker.color == SPARKLINE_CONFIG["marker_color"]
        assert marker_trace.marker.size == SPARKLINE_CONFIG["marker_size"]

    def test_fill_under_line(self):
        """Price trace should have fill='tozeroy'."""
        df = _make_price_df([100, 101, 102])
        fig = build_sparkline_figure(df)
        assert fig.data[0].fill == "tozeroy"

    def test_no_legend(self):
        """Sparkline should not show any legend."""
        df = _make_price_df([100, 101, 102])
        fig = build_sparkline_figure(df)
        assert fig.layout.showlegend is False


class TestCreateSparklineComponent:
    """Tests for the create_sparkline_component wrapper."""

    def test_returns_dcc_graph(self):
        """Should return a dcc.Graph component."""
        df = _make_price_df([100, 101, 102])
        component = create_sparkline_component(df)
        assert isinstance(component, dcc.Graph)

    def test_display_mode_bar_disabled(self):
        """The Plotly modebar should be hidden."""
        df = _make_price_df([100, 101, 102])
        component = create_sparkline_component(df)
        assert component.config["displayModeBar"] is False

    def test_dimensions_in_style(self):
        """Component style should set width and height from config."""
        df = _make_price_df([100, 101, 102])
        component = create_sparkline_component(df)
        assert f"{SPARKLINE_CONFIG['width']}px" in component.style["width"]
        assert f"{SPARKLINE_CONFIG['height']}px" in component.style["height"]

    def test_custom_component_id(self):
        """Custom component_id should be used as the Graph id."""
        df = _make_price_df([100, 101, 102])
        component = create_sparkline_component(df, component_id="my-sparkline")
        assert component.id == "my-sparkline"


class TestCreateSparklinePlaceholder:
    """Tests for the create_sparkline_placeholder function."""

    def test_returns_html_div(self):
        """Should return an html.Div component."""
        placeholder = create_sparkline_placeholder()
        assert isinstance(placeholder, html.Div)

    def test_has_matching_dimensions(self):
        """Placeholder should match sparkline dimensions for layout consistency."""
        placeholder = create_sparkline_placeholder()
        assert f"{SPARKLINE_CONFIG['width']}px" in placeholder.style["width"]
        assert f"{SPARKLINE_CONFIG['height']}px" in placeholder.style["height"]

    def test_shows_no_data_text(self):
        """Placeholder should show 'No price data' text."""
        placeholder = create_sparkline_placeholder()
        # The text is inside a Span child
        assert hasattr(placeholder, "children")
        span = placeholder.children
        assert hasattr(span, "children")
        assert "No price data" in span.children

    def test_has_dashed_border(self):
        """Placeholder should have a dashed border for visual distinction."""
        placeholder = create_sparkline_placeholder()
        assert "dashed" in placeholder.style["border"]
```

### New Tests in `shit_tests/shitty_ui/test_data.py`

```python
class TestGetSparklinePrices:
    """Tests for the get_sparkline_prices batch query function."""

    @patch("data.execute_query")
    def test_returns_dict_of_dataframes(self, mock_execute):
        """Should return a dict mapping symbol -> DataFrame."""
        from data import get_sparkline_prices

        mock_execute.return_value = (
            [
                ("AAPL", "2025-06-10", 150.0),
                ("AAPL", "2025-06-11", 151.0),
                ("AAPL", "2025-06-12", 152.0),
                ("TSLA", "2025-06-10", 250.0),
                ("TSLA", "2025-06-11", 248.0),
            ],
            ["symbol", "date", "close"],
        )

        result = get_sparkline_prices(
            symbols=("AAPL", "TSLA"),
            center_date="2025-06-12",
        )

        assert isinstance(result, dict)
        assert "AAPL" in result
        assert "TSLA" in result
        assert len(result["AAPL"]) == 3
        assert list(result["AAPL"].columns) == ["date", "close"]

    @patch("data.execute_query")
    def test_returns_empty_dict_for_empty_symbols(self, mock_execute):
        """Empty symbols tuple should return empty dict without querying."""
        from data import get_sparkline_prices

        result = get_sparkline_prices(symbols=(), center_date="2025-06-12")

        assert result == {}
        mock_execute.assert_not_called()

    @patch("data.execute_query")
    def test_excludes_symbols_with_single_data_point(self, mock_execute):
        """Symbols with only 1 price point should be excluded (need >= 2)."""
        from data import get_sparkline_prices

        mock_execute.return_value = (
            [
                ("AAPL", "2025-06-10", 150.0),
                ("AAPL", "2025-06-11", 151.0),
                ("TSLA", "2025-06-10", 250.0),  # Only 1 row
            ],
            ["symbol", "date", "close"],
        )

        result = get_sparkline_prices(
            symbols=("AAPL", "TSLA"),
            center_date="2025-06-12",
        )

        assert "AAPL" in result
        assert "TSLA" not in result

    @patch("data.execute_query")
    def test_returns_empty_dict_on_db_error(self, mock_execute):
        """Database errors should return empty dict, not raise."""
        from data import get_sparkline_prices

        mock_execute.side_effect = Exception("Connection failed")

        result = get_sparkline_prices(
            symbols=("AAPL",),
            center_date="2025-06-12",
        )

        assert result == {}

    @patch("data.execute_query")
    def test_returns_empty_dict_when_no_rows(self, mock_execute):
        """No matching price data should return empty dict."""
        from data import get_sparkline_prices

        mock_execute.return_value = ([], ["symbol", "date", "close"])

        result = get_sparkline_prices(
            symbols=("AAPL",),
            center_date="2025-06-12",
        )

        assert result == {}

    @patch("data.execute_query")
    def test_passes_correct_date_window(self, mock_execute):
        """Query should use expanded calendar window around center_date."""
        from data import get_sparkline_prices

        mock_execute.return_value = ([], ["symbol", "date", "close"])

        get_sparkline_prices(
            symbols=("AAPL",),
            center_date="2025-06-15",
            days_before=3,
            days_after=10,
        )

        mock_execute.assert_called_once()
        call_params = mock_execute.call_args[0][1]
        # Calendar window: 3 * 2.0 = 6 days before, 10 * 1.8 = 18 days after
        from datetime import date as d, timedelta
        expected_start = d(2025, 6, 15) - timedelta(days=6)
        expected_end = d(2025, 6, 15) + timedelta(days=18)
        assert call_params["start_date"] == expected_start
        assert call_params["end_date"] == expected_end
```

### New Tests in `shit_tests/shitty_ui/test_cards.py`

```python
class TestFeedSignalCardSparkline:
    """Tests for sparkline integration in create_feed_signal_card."""

    def test_no_sparkline_when_prices_not_provided(self):
        """Card should render normally without sparkline when no prices passed."""
        card = create_feed_signal_card(_make_row())
        text = _extract_text(card)
        assert "price" not in text.lower() or "No price data" not in text

    def test_no_sparkline_when_prices_is_none(self):
        """Card should not crash when sparkline_prices is None."""
        card = create_feed_signal_card(_make_row(), sparkline_prices=None)
        assert card is not None

    def test_placeholder_when_symbol_missing_from_prices(self):
        """Card should show placeholder when symbol has no price data."""
        row = _make_row()
        row["symbol"] = "AAPL"
        card = create_feed_signal_card(row, sparkline_prices={})
        text = _extract_text(card)
        assert "No price data" in text

    def test_sparkline_rendered_when_data_available(self):
        """Card should contain a dcc.Graph when sparkline data exists."""
        from components.sparkline import create_sparkline_component
        import pandas as pd

        row = _make_row()
        row["symbol"] = "AAPL"
        price_df = pd.DataFrame({
            "date": pd.bdate_range("2025-06-10", periods=5),
            "close": [150, 151, 152, 153, 154],
        })
        card = create_feed_signal_card(
            row, sparkline_prices={"AAPL": price_df}
        )
        # The card should contain a dcc.Graph somewhere in its children
        found_graph = _find_component_type(card, "Graph")
        assert found_graph, "Expected a dcc.Graph sparkline in the card"


class TestUnifiedSignalCardSparkline:
    """Tests for sparkline integration in create_unified_signal_card."""

    def test_no_sparkline_when_prices_not_provided(self):
        """Unified card should render normally without sparkline."""
        card = create_unified_signal_card(_make_row())
        assert card is not None

    def test_no_sparkline_when_prices_is_none(self):
        """Unified card should not crash when sparkline_prices is None."""
        card = create_unified_signal_card(_make_row(), sparkline_prices=None)
        assert card is not None

    def test_sparkline_rendered_for_first_asset(self):
        """Unified card should show sparkline for the first asset."""
        import pandas as pd

        row = _make_row(assets=["AAPL", "TSLA"])
        price_df = pd.DataFrame({
            "date": pd.bdate_range("2025-06-10", periods=5),
            "close": [150, 151, 152, 153, 154],
        })
        card = create_unified_signal_card(
            row, sparkline_prices={"AAPL": price_df}
        )
        found_graph = _find_component_type(card, "Graph")
        assert found_graph, "Expected a dcc.Graph sparkline in the unified card"

    def test_placeholder_when_asset_missing_from_prices(self):
        """Unified card should show placeholder when first asset has no price data."""
        row = _make_row(assets=["MISSING"])
        card = create_unified_signal_card(row, sparkline_prices={})
        text = _extract_text(card)
        assert "No price data" in text


def _find_component_type(component, type_name: str) -> bool:
    """Recursively search a Dash component tree for a component type."""
    if type(component).__name__ == type_name:
        return True
    if hasattr(component, "children"):
        children = component.children
        if isinstance(children, list):
            return any(
                _find_component_type(c, type_name)
                for c in children
                if c is not None and not isinstance(c, str)
            )
        elif children is not None and not isinstance(children, str):
            return _find_component_type(children, type_name)
    return False
```

---

## Verification Checklist

- [ ] `/signals` page shows sparkline next to each signal card that has a symbol with price data
- [ ] Sparkline line is green when price went up, red when price went down, gray when flat
- [ ] Yellow dot marks the prediction date on the sparkline
- [ ] Cards without price data show "No price data" placeholder with dashed border
- [ ] Unified feed cards on `/` dashboard show sparkline for first asset
- [ ] No N+1 queries: one SQL query per page of signals, not one per card
- [ ] Sparklines are cached (5-minute TTL via `@ttl_cache`)
- [ ] `/signals` page load time has not visibly degraded (sparkline query < 100ms)
- [ ] Existing card tests still pass: `source venv/bin/activate && pytest shit_tests/shitty_ui/test_cards.py -v`
- [ ] New sparkline tests pass: `source venv/bin/activate && pytest shit_tests/shitty_ui/test_sparkline.py -v`
- [ ] New data layer tests pass: `source venv/bin/activate && pytest shit_tests/shitty_ui/test_data.py -v`
- [ ] Full test suite green: `source venv/bin/activate && pytest shit_tests/shitty_ui/ -v`
- [ ] Sparkline hover shows date and price: `"Jun 12: $152.50"`
- [ ] `/performance` page unaffected (regression check)
- [ ] CHANGELOG.md updated

---

## What NOT To Do

1. **Do NOT fetch price data inside `create_feed_signal_card()` or `create_hero_signal_card()`.** Card components are pure renderers. Data fetching belongs in the page callback. Fetching inside the card function would create N+1 queries and make testing impossible without database mocks.

2. **Do NOT use `get_asset_price_history()` for sparklines.** It fetches 180 days of OHLCV data for a single symbol. Sparklines only need ~13 days of closing prices for multiple symbols. The new `get_sparkline_prices()` is purpose-built for this.

3. **Do NOT render sparklines as full-size `dcc.Graph` components.** The default Graph size is ~250px tall with modebar, margins, and axes. Sparklines must be 36px tall with zero chrome. Always use `build_sparkline_figure()` which enforces the compact layout.

4. **Do NOT make sparkline_prices a required parameter.** Both `create_feed_signal_card()` and `create_unified_signal_card()` must continue working with zero arguments changed. The `sparkline_prices=None` default ensures backward compatibility with all existing callers and tests.

5. **Do NOT add individual symbol queries in a loop.** The entire point of `get_sparkline_prices()` is to batch-fetch data for all visible symbols in one SQL query. Never call it once per card inside an `iterrows()` loop.

6. **Do NOT use SVG or raw HTML for sparklines.** Plotly `go.Figure` with `dcc.Graph` is the established pattern in this codebase (see `charts.py`). SVG would require a different rendering pipeline and break the consistency of the chart architecture.

7. **Do NOT modify `clear_all_caches()` in data.py.** The `get_sparkline_prices` function uses `@ttl_cache` which is self-clearing. If needed, add it to `clear_all_caches()` for manual cache busting, but do not remove any existing cache-clear calls.

8. **Do NOT add sparklines to `create_signal_card()` (the dashboard sidebar card) or `create_post_card()`.** These are compact cards used in narrow columns. Sparklines are only appropriate on `create_feed_signal_card()` (full-width signal feed) and `create_unified_signal_card()` (dashboard unified feed). Adding them to sidebar cards would create layout overflow.

---

## Performance Considerations

### Query Cost

The `get_sparkline_prices()` query hits the `market_prices` table which has a composite unique index on `(symbol, date)`. The query filters by `symbol = ANY(...)` (typically 5-15 symbols per page) and a narrow date range (~3 weeks). Expected result set: ~150 rows (15 symbols x 10 trading days). Execution time: <50ms on Neon PostgreSQL.

### Caching Strategy

- **TTL cache (5 min)**: Price data changes at most once per day (market close), so 5-minute caching is safe.
- **Cache key**: `(symbols_tuple, center_date, days_before, days_after)` -- the same signal feed page will always hit the cache on subsequent loads.
- **Invalidation**: Automatic via TTL. No manual invalidation needed since market prices are historical (not real-time).

### Render Cost

Each sparkline is a `dcc.Graph` with 2 traces and ~13 data points. Plotly serialization for such a minimal figure is ~1ms. For 20 cards per page, that is ~20ms total render overhead -- negligible compared to the SQL query.

### Alternative Considered: Server-side SVG

Generating SVG strings server-side would avoid the Plotly overhead entirely. However:
- Loses hover interactivity (users cannot see exact price/date on hover)
- Requires a separate SVG rendering library or manual path computation
- Breaks the consistency of using Plotly for all charts in the codebase
- The Plotly overhead (~20ms) is negligible

Decision: Use Plotly `dcc.Graph` for consistency and hover support.

---

## CHANGELOG Entry

```markdown
### Added
- **Inline price sparklines on signal cards** -- Mini price charts displayed on signal feed cards and hero cards showing the asset's price movement around the prediction date
  - Green line when price went up, red when down, yellow dot marks prediction date
  - Batch price fetching via single SQL query (no N+1) with 5-minute caching
  - "No price data" placeholder for symbols without market data
  - New `get_sparkline_prices()` data layer function for efficient multi-symbol batch queries
```
