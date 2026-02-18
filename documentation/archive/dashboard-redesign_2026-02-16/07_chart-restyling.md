# Phase 07: Chart Restyling

**Status**: 🔧 IN PROGRESS
**Started**: 2026-02-16
**PR Title**: style: polished candlestick & analytics charts
**Risk Level**: Low
**Estimated Effort**: Small (1-2 hours)
**Dependencies**: None
**Unlocks**: Nothing (standalone visual polish)

## Files Modified

| File | Action |
|------|--------|
| `shitty_ui/constants.py` | Add `CHART_LAYOUT` base config dict, `CHART_COLORS` palette, `CHART_HOVER` template config |
| `shitty_ui/components/charts.py` | Refactor `build_signal_over_trend_chart()` and `build_empty_signal_chart()` to use shared layout; add `apply_chart_layout()` helper |
| `shitty_ui/pages/dashboard.py` | Replace all inline `fig.update_layout(...)` blocks with `apply_chart_layout()` calls; add custom hover templates to all 3 analytics charts |
| `shitty_ui/pages/trends.py` | No code changes (consumes charts.py which handles it) |
| `shitty_ui/pages/assets.py` | No code changes (consumes charts.py which handles it) |
| `shit_tests/shitty_ui/test_charts.py` | Add tests for `apply_chart_layout()`, verify modebar config, verify new hover templates |
| `CHANGELOG.md` | Add entry |

## Context

Every chart in the dashboard uses ad-hoc, copy-pasted Plotly layout configuration. Each chart independently sets `plot_bgcolor`, `paper_bgcolor`, `font_color`, `margin`, and `gridcolor` -- resulting in subtle inconsistencies and the generic "AI-generated" look the user complained about. Specific problems:

1. **Candlestick chart** (trends page, asset page): Uses default Plotly green/red which clash with the app's emerald/red palette. No custom hover template on the candlestick trace itself (only on signal markers). The range slider is hidden but the modebar still appears on hover in some contexts.

2. **Accuracy Over Time** (dashboard, lines 702-757): Hardcoded layout dict with `margin=dict(l=40, r=40, t=10, b=40)`. No consistent font family. Hover template is good but style differs from other charts.

3. **Confidence Distribution** (dashboard, lines 759-798): Bar chart uses a raw 3-color list `[danger, warning, success]`. No rounded bar corners. Text labels positioned "outside" can clip at chart edges.

4. **Asset Accuracy** (dashboard, lines 800-842): Same issues as confidence chart. Uses `hovermode="x unified"` which differs from other charts' `"closest"`.

5. **Sentiment Donut** (performance page, lines 1258-1321): Custom hover template is good, but font sizes and legend placement differ from other charts.

6. **Empty charts** (`build_empty_signal_chart`): Missing modebar suppression. Annotation font size (14) differs from the app's type scale.

7. **Modebar inconsistency**: Some `dcc.Graph` components set `config={"displayModeBar": False}`, others set `config={"displayModeBar": "hover", "displaylogo": False}` (trends page line 127), and the chart builder functions don't enforce this.

The fix: Create a single `CHART_LAYOUT` base configuration in `constants.py`, a reusable `apply_chart_layout()` helper in `charts.py`, and apply it everywhere.

## Detailed Implementation

### Change A: Add Chart Constants to constants.py

**File**: `shitty_ui/constants.py`
**Location**: After `SECTION_ACCENT` dict (after line 89)

Add three new constant dicts:

```python
# ============================================================
# Chart configuration — shared base for all Plotly figures
# ============================================================

# Base layout applied to every chart via apply_chart_layout()
CHART_LAYOUT = {
    "plot_bgcolor": "rgba(0,0,0,0)",
    "paper_bgcolor": "rgba(0,0,0,0)",
    "font": {
        "family": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        "color": "#f1f5f9",  # COLORS["text"]
        "size": 12,
    },
    "margin": {"l": 48, "r": 16, "t": 24, "b": 40},
    "xaxis": {
        "gridcolor": "rgba(51, 65, 85, 0.5)",  # COLORS["border"] at 50%
        "gridwidth": 1,
        "zeroline": False,
        "showline": False,
    },
    "yaxis": {
        "gridcolor": "rgba(51, 65, 85, 0.5)",
        "gridwidth": 1,
        "zeroline": False,
        "showline": False,
    },
    "hoverlabel": {
        "bgcolor": "#1e293b",  # COLORS["secondary"]
        "bordercolor": "#334155",  # COLORS["border"]
        "font": {
            "family": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
            "color": "#f1f5f9",
            "size": 13,
        },
    },
    "showlegend": False,
}

# Standardized dcc.Graph config dict — suppresses modebar & Plotly logo
CHART_CONFIG = {
    "displayModeBar": False,
    "displaylogo": False,
    "scrollZoom": False,
}

# Extended candlestick-specific colors (override Plotly defaults)
CHART_COLORS = {
    "candle_up": "#10b981",       # Emerald 500 — matches COLORS["success"]
    "candle_down": "#ef4444",     # Red 500 — matches COLORS["danger"]
    "candle_up_fill": "#10b981",  # Solid fill for up candles
    "candle_down_fill": "#ef4444",
    "volume_up": "rgba(16, 185, 129, 0.3)",   # Emerald at 30%
    "volume_down": "rgba(239, 68, 68, 0.3)",  # Red at 30%
    "line_accent": "#3b82f6",     # Blue 500 — COLORS["accent"]
    "line_accent_fill": "rgba(59, 130, 246, 0.08)",  # Subtler area fill
    "bar_palette": [              # Ordered palette for multi-bar charts
        "#3b82f6",  # Blue 500
        "#10b981",  # Emerald 500
        "#f59e0b",  # Amber 500
        "#ef4444",  # Red 500
        "#8b5cf6",  # Violet 500
        "#ec4899",  # Pink 500
    ],
    "reference_line": "rgba(148, 163, 184, 0.3)",  # Slate 400 at 30%
}
```

**Why three separate dicts?**

- `CHART_LAYOUT` is the Plotly `fig.update_layout(**CHART_LAYOUT)` base -- applied to every figure.
- `CHART_CONFIG` is the `dcc.Graph(config=...)` prop -- controls the Plotly modebar.
- `CHART_COLORS` holds semantic color tokens specific to chart traces.

---

### Change B: Add `apply_chart_layout()` Helper to charts.py

**File**: `shitty_ui/components/charts.py`
**Location**: After the existing imports (line 8), add the new imports and helper function before `build_signal_over_trend_chart`.

#### Step B1: Update imports

Change:
```python
from constants import COLORS, SENTIMENT_COLORS, MARKER_CONFIG, TIMEFRAME_COLORS
```

To:
```python
from constants import (
    COLORS,
    SENTIMENT_COLORS,
    MARKER_CONFIG,
    TIMEFRAME_COLORS,
    CHART_LAYOUT,
    CHART_COLORS,
)
```

#### Step B2: Add `apply_chart_layout()` function

Insert after the imports, before `build_signal_over_trend_chart`:

```python
def apply_chart_layout(
    fig: go.Figure,
    height: int = 300,
    show_legend: bool = False,
    **overrides,
) -> go.Figure:
    """Apply the shared chart layout to a Plotly figure.

    Merges CHART_LAYOUT base with caller-specific overrides.
    Always call this LAST, after adding traces, so it can override
    any trace-level defaults that Plotly might have set on the layout.

    Args:
        fig: The Plotly figure to style.
        height: Chart height in pixels.
        show_legend: Whether to show the legend.
        **overrides: Additional layout keys to override (e.g.,
            yaxis=dict(title="Accuracy %", range=[0, 105])).

    Returns:
        The same figure, mutated in place (also returned for chaining).
    """
    # Start with base layout
    layout = {**CHART_LAYOUT}
    layout["height"] = height
    layout["showlegend"] = show_legend

    # Deep-merge axis overrides so callers can add title/range without
    # losing gridcolor from the base layout
    for axis_key in ("xaxis", "yaxis"):
        if axis_key in overrides:
            base_axis = {**layout.get(axis_key, {})}
            base_axis.update(overrides.pop(axis_key))
            layout[axis_key] = base_axis

    # Merge remaining overrides
    layout.update(overrides)

    fig.update_layout(**layout)
    return fig
```

#### Step B3: Refactor `build_signal_over_trend_chart()` layout section

**File**: `shitty_ui/components/charts.py`
**Location**: Lines 34-151 (the existing function)

Replace the `# --- Layout ---` section (lines 134-151) with:

```python
    # --- Layout ---
    apply_chart_layout(
        fig,
        height=chart_height,
        show_legend=False,
        hovermode="closest",
        margin={"l": 50, "r": 20, "t": 30, "b": 40},
        xaxis={"rangeslider": {"visible": False}},
        yaxis={"title": "Price ($)"},
    )

    # Add a custom legend for sentiment markers
    _add_sentiment_legend(fig)
```

This replaces the raw `fig.update_layout(...)` call at lines 135-151 with the helper.

#### Step B4: Update candlestick trace colors

**File**: `shitty_ui/components/charts.py`
**Location**: Lines 37-49 (candlestick trace)

Change:
```python
        fig.add_trace(
            go.Candlestick(
                x=prices_df["date"],
                open=prices_df["open"],
                high=prices_df["high"],
                low=prices_df["low"],
                close=prices_df["close"],
                name=symbol or "Price",
                increasing_line_color=COLORS["success"],
                decreasing_line_color=COLORS["danger"],
                showlegend=False,
            )
        )
```

To:
```python
        fig.add_trace(
            go.Candlestick(
                x=prices_df["date"],
                open=prices_df["open"],
                high=prices_df["high"],
                low=prices_df["low"],
                close=prices_df["close"],
                name=symbol or "Price",
                increasing_line_color=CHART_COLORS["candle_up"],
                decreasing_line_color=CHART_COLORS["candle_down"],
                increasing_fillcolor=CHART_COLORS["candle_up_fill"],
                decreasing_fillcolor=CHART_COLORS["candle_down_fill"],
                showlegend=False,
            )
        )
```

This explicitly sets fill colors (previously Plotly would half-fill them with a lighter shade by default).

#### Step B5: Add candlestick hover template

**File**: `shitty_ui/components/charts.py`
**Location**: Inside the candlestick trace (Step B4), after `showlegend=False,`

The candlestick trace in Plotly does not support `hovertemplate` directly. Instead, set `hoverinfo` to customize what appears. Since Plotly's `go.Candlestick` has limited hover customization, we override it post-creation:

After `fig.add_trace(go.Candlestick(...))`, add:

```python
        # Improve candlestick hover display
        fig.data[-1].update(
            hoverinfo="x+y",
        )
```

This is minimal -- candlestick hover already shows OHLC by default. The key improvement is the `hoverlabel` styling from `CHART_LAYOUT` which gives it the dark background and consistent font.

#### Step B6: Refactor `build_empty_signal_chart()`

**File**: `shitty_ui/components/charts.py`
**Location**: Lines 202-218 (the existing function)

Replace with:
```python
def build_empty_signal_chart(message: str = "No data available") -> go.Figure:
    """Build an empty chart with a centered message."""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        showarrow=False,
        font=dict(color=COLORS["text_muted"], size=14),
    )
    apply_chart_layout(
        fig,
        height=400,
        xaxis={"showgrid": False, "showticklabels": False, "zeroline": False},
        yaxis={"showgrid": False, "showticklabels": False, "zeroline": False},
    )
    return fig
```

The key change: `build_empty_signal_chart` now uses `apply_chart_layout` instead of a raw `fig.update_layout(...)`. This ensures hoverlabel config and font family are consistent even for empty states.

---

### Change C: Restyle Analytics Charts in dashboard.py

All three analytics charts in `update_dashboard()` currently have inline `fig.update_layout(...)` blocks. Replace each with an `apply_chart_layout()` call.

#### Step C0: Update imports

**File**: `shitty_ui/pages/dashboard.py`
**Location**: Line 8

Add import:
```python
from components.charts import apply_chart_layout
```

Add to the constants import:
```python
from constants import COLORS, CHART_COLORS
```

#### Step C1: Restyle Accuracy Over Time chart

**File**: `shitty_ui/pages/dashboard.py`
**Location**: Lines 702-757 (inside `update_dashboard()`)

Replace the accuracy over time section with:

```python
        # ===== Accuracy Over Time Chart =====
        try:
            acc_df = get_accuracy_over_time(days=days)
            if not acc_df.empty and len(acc_df) > 1:
                acc_fig = go.Figure()
                acc_fig.add_trace(
                    go.Scatter(
                        x=acc_df["week"],
                        y=acc_df["accuracy"],
                        mode="lines+markers",
                        name="Weekly Accuracy",
                        line=dict(
                            color=CHART_COLORS["line_accent"],
                            width=2.5,
                            shape="spline",
                        ),
                        marker=dict(
                            size=7,
                            color=CHART_COLORS["line_accent"],
                            line=dict(width=1.5, color=COLORS["bg"]),
                        ),
                        fill="tozeroy",
                        fillcolor=CHART_COLORS["line_accent_fill"],
                        hovertemplate=(
                            "<b>Week of %{x|%b %d, %Y}</b><br>"
                            "Accuracy: <b>%{y:.1f}%</b><br>"
                            "<extra></extra>"
                        ),
                    )
                )
                # 50% reference line
                acc_fig.add_hline(
                    y=50,
                    line_dash="dot",
                    line_color=CHART_COLORS["reference_line"],
                    line_width=1,
                    annotation_text="50% baseline",
                    annotation_position="bottom right",
                    annotation_font_color=COLORS["text_muted"],
                    annotation_font_size=10,
                )
                apply_chart_layout(
                    acc_fig,
                    height=280,
                    yaxis={"range": [0, 105], "title": "Accuracy %"},
                )
            else:
                acc_fig = create_empty_state_chart(
                    message="Not enough weekly data to chart accuracy trend",
                    hint="Requires 2+ weeks of evaluated predictions",
                )
        except Exception as e:
            errors.append(f"Accuracy over time: {e}")
            print(f"Error loading accuracy over time: {traceback.format_exc()}")
            acc_fig = create_empty_chart(f"Error: {str(e)[:50]}")
```

Key differences from original:
1. Line shape changed from default to `"spline"` for smoother curves
2. Line width increased from 2 to 2.5
3. Marker gets a contrasting border (`color=COLORS["bg"]`) for visual separation from the line
4. Fill color uses `CHART_COLORS["line_accent_fill"]` (subtler at 8%) instead of hardcoded `rgba(59, 130, 246, 0.1)`
5. Reference line changed from `"dash"` to `"dot"` for less visual weight, width reduced to 1
6. `apply_chart_layout()` replaces inline layout dict
7. Hover template adds "Week of" prefix for clarity

#### Step C2: Restyle Confidence Distribution chart

**File**: `shitty_ui/pages/dashboard.py`
**Location**: Lines 759-798 (inside `update_dashboard()`)

Replace the confidence chart section with:

```python
        # ===== Confidence Chart with error handling =====
        try:
            conf_df = get_accuracy_by_confidence(days=days)
            if not conf_df.empty:
                conf_fig = go.Figure()
                conf_fig.add_trace(
                    go.Bar(
                        x=conf_df["confidence_level"],
                        y=conf_df["accuracy"],
                        text=conf_df["accuracy"].apply(lambda x: f"{x:.1f}%"),
                        textposition="outside",
                        textfont=dict(
                            color=COLORS["text"],
                            size=12,
                        ),
                        marker=dict(
                            color=[
                                COLORS["danger"],
                                COLORS["warning"],
                                COLORS["success"],
                            ],
                            line=dict(width=0),
                        ),
                        hovertemplate=(
                            "<b>%{x}</b><br>"
                            "Accuracy: <b>%{y:.1f}%</b><br>"
                            "Predictions: <b>%{customdata}</b>"
                            "<extra></extra>"
                        ),
                        customdata=conf_df["total"],
                    )
                )
                apply_chart_layout(
                    conf_fig,
                    height=250,
                    yaxis={"range": [0, 100], "title": "Accuracy %"},
                    xaxis={"title": ""},
                    bargap=0.35,
                )
            else:
                conf_fig = create_empty_state_chart(
                    message="No accuracy data for this period",
                    hint="Predictions need 7+ trading days to mature before accuracy is measured",
                )
        except Exception as e:
            errors.append(f"Confidence chart: {e}")
            print(f"Error loading confidence chart: {traceback.format_exc()}")
            conf_fig = create_empty_chart(f"Error: {str(e)[:50]}")
```

Key differences from original:
1. `marker_color` replaced with `marker=dict(color=[...], line=dict(width=0))` -- explicit zero border for cleaner bars
2. `textfont` added to control label color and size explicitly
3. `bargap=0.35` added for wider spacing between bars (less cramped)
4. Hover template reformatted with `<b>` tags for emphasis and cleaner layout (removed `Total:` prefix, uses `Predictions:`)
5. `apply_chart_layout()` replaces inline layout dict

#### Step C3: Restyle Asset Accuracy chart

**File**: `shitty_ui/pages/dashboard.py`
**Location**: Lines 800-842 (inside `update_dashboard()`)

Replace the asset chart section with:

```python
        # ===== Asset Chart with error handling =====
        try:
            asset_df = get_accuracy_by_asset(limit=10, days=days)
            if not asset_df.empty:
                asset_fig = go.Figure()
                colors = [
                    COLORS["success"] if x >= 60 else COLORS["danger"]
                    for x in asset_df["accuracy"]
                ]
                asset_fig.add_trace(
                    go.Bar(
                        x=asset_df["symbol"],
                        y=asset_df["accuracy"],
                        text=asset_df["accuracy"].apply(lambda x: f"{x:.0f}%"),
                        textposition="outside",
                        textfont=dict(
                            color=COLORS["text"],
                            size=12,
                        ),
                        marker=dict(
                            color=colors,
                            line=dict(width=0),
                        ),
                        hovertemplate=(
                            "<b>%{x}</b><br>"
                            "Accuracy: <b>%{y:.1f}%</b><br>"
                            "Predictions: <b>%{customdata[0]}</b><br>"
                            "Total P&L: <b>$%{customdata[1]:,.0f}</b><br>"
                            "<i>Click to drill down</i>"
                            "<extra></extra>"
                        ),
                        customdata=list(
                            zip(asset_df["total_predictions"], asset_df["total_pnl"])
                        ),
                    )
                )
                apply_chart_layout(
                    asset_fig,
                    height=250,
                    yaxis={"range": [0, 100], "title": "Accuracy %"},
                    xaxis={"title": ""},
                    hovermode="closest",
                    bargap=0.3,
                )
            else:
                asset_fig = create_empty_state_chart(
                    message="No asset performance data for this period",
                    hint="Asset accuracy appears after prediction outcomes are evaluated",
                )
        except Exception as e:
            errors.append(f"Asset chart: {e}")
            print(f"Error loading asset chart: {traceback.format_exc()}")
            asset_fig = create_empty_chart(f"Error: {str(e)[:50]}")
```

Key differences from original:
1. `marker_color=colors` replaced with `marker=dict(color=colors, line=dict(width=0))`
2. `textfont` added for consistent label styling
3. `hovermode` changed from `"x unified"` to `"closest"` to match all other charts
4. Hover template reformatted with `<b>` tags and line breaks for readability
5. `bargap=0.3` added for cleaner spacing
6. `apply_chart_layout()` replaces inline layout dict

---

### Change D: Restyle Performance Page Charts in dashboard.py

The performance page callback `update_performance_page()` has its own chart construction code. Apply the same treatment.

#### Step D1: Restyle Performance Confidence chart

**File**: `shitty_ui/pages/dashboard.py`
**Location**: Lines 1213-1256 (inside `update_performance_page()`)

Replace the confidence chart section with:

```python
        # ===== Accuracy by Confidence Bar Chart =====
        try:
            conf_df = get_accuracy_by_confidence()
            if not conf_df.empty:
                conf_fig = go.Figure()
                colors = [COLORS["danger"], COLORS["warning"], COLORS["success"]]
                conf_fig.add_trace(
                    go.Bar(
                        x=conf_df["confidence_level"],
                        y=conf_df["accuracy"],
                        text=conf_df["accuracy"].apply(lambda x: f"{x:.1f}%"),
                        textposition="outside",
                        textfont=dict(
                            color=COLORS["text"],
                            size=12,
                        ),
                        marker=dict(
                            color=colors[: len(conf_df)],
                            line=dict(width=0),
                        ),
                        hovertemplate=(
                            "<b>%{x}</b><br>"
                            "Accuracy: <b>%{y:.1f}%</b><br>"
                            "Predictions: <b>%{customdata[0]}</b><br>"
                            "Correct: <b>%{customdata[1]}</b>"
                            "<extra></extra>"
                        ),
                        customdata=list(zip(conf_df["total"], conf_df["correct"])),
                    )
                )
                apply_chart_layout(
                    conf_fig,
                    height=300,
                    yaxis={"range": [0, 100], "title": "Accuracy %"},
                    xaxis={"title": ""},
                    bargap=0.35,
                )
            else:
                conf_fig = create_empty_state_chart(
                    message="No confidence breakdown available yet",
                    hint="Appears after predictions have evaluated outcomes",
                )
        except Exception as e:
            errors.append(f"Confidence chart: {e}")
            conf_fig = create_empty_chart(f"Error: {str(e)[:50]}")
```

Key differences from original:
1. Uses `marker=dict(...)` instead of `marker_color=`
2. Added `textfont` for consistent styling
3. Hover template uses `<b>` tags and cleaner labels
4. `apply_chart_layout()` replaces inline layout dict
5. `bargap=0.35` added

#### Step D2: Restyle Sentiment Donut chart

**File**: `shitty_ui/pages/dashboard.py`
**Location**: Lines 1258-1321 (inside `update_performance_page()`)

Replace the sentiment chart section with:

```python
        # ===== Sentiment Donut Chart =====
        try:
            sent_df = get_sentiment_accuracy()
            if not sent_df.empty:
                color_map = {
                    "bullish": COLORS["success"],
                    "bearish": COLORS["danger"],
                    "neutral": COLORS["text_muted"],
                }
                colors_list = [
                    color_map.get(s, COLORS["text_muted"]) for s in sent_df["sentiment"]
                ]

                sent_fig = go.Figure()
                sent_fig.add_trace(
                    go.Pie(
                        labels=sent_df["sentiment"].str.capitalize(),
                        values=sent_df["total"],
                        hole=0.55,
                        marker=dict(
                            colors=colors_list,
                            line=dict(color=COLORS["bg"], width=2),
                        ),
                        textinfo="label+percent",
                        textfont=dict(color=COLORS["text"], size=12),
                        hovertemplate=(
                            "<b>%{label}</b><br>"
                            "Count: <b>%{value}</b><br>"
                            "Share: <b>%{percent}</b><br>"
                            "Accuracy: <b>%{customdata:.1f}%</b>"
                            "<extra></extra>"
                        ),
                        customdata=sent_df["accuracy"],
                    )
                )
                # Center annotation
                total_count = sent_df["total"].sum()
                total_correct = sent_df["correct"].sum()
                total_acc = round(total_correct / total_count * 100, 1) if total_count > 0 else 0.0
                sent_fig.add_annotation(
                    text=f"<b>{total_acc:.0f}%</b><br><span style='font-size:11px'>Overall</span>",
                    showarrow=False,
                    font=dict(size=18, color=COLORS["text"]),
                )
                apply_chart_layout(
                    sent_fig,
                    height=300,
                    show_legend=True,
                    margin={"l": 20, "r": 20, "t": 20, "b": 20},
                    legend=dict(
                        font=dict(color=COLORS["text"], size=12),
                        orientation="h",
                        y=-0.1,
                    ),
                )
            else:
                sent_fig = create_empty_state_chart(
                    message="No sentiment breakdown available yet",
                    hint="Appears after predictions with sentiment labels are evaluated",
                )
        except Exception as e:
            errors.append(f"Sentiment chart: {e}")
            sent_fig = create_empty_chart(f"Error: {str(e)[:50]}")
```

Key differences from original:
1. Donut slices get a `line=dict(color=COLORS["bg"], width=2)` separator for visual definition between slices
2. Center annotation font size increased from 16 to 18 for the number, with "Overall" label rendered smaller via inline style
3. `textfont` explicitly set for pie slice labels
4. Hover template adds `<b>` emphasis tags
5. `apply_chart_layout()` replaces inline layout dict, with `show_legend=True` override
6. Removed `total_acc = 0.0` initializer -- consolidated into single conditional expression

---

### Change E: Standardize dcc.Graph Config Props

The `CHART_CONFIG` constant replaces the various inline `config=` dicts on `dcc.Graph` components. However, changing the `dcc.Graph` `config` props requires touching layout files (dashboard.py, trends.py) where the graphs are declared. Since Phase 07 scope limits to chart styling and those layout declarations are set in `create_dashboard_page()` / `create_trends_page()`, we make the following targeted changes.

#### Step E1: Update trends.py dcc.Graph config

**File**: `shitty_ui/pages/trends.py`
**Location**: Line 125-127

Change:
```python
                            children=dcc.Graph(
                                id="trends-signal-chart",
                                config={"displayModeBar": "hover", "displaylogo": False},
                            ),
```

To:
```python
                            children=dcc.Graph(
                                id="trends-signal-chart",
                                config=CHART_CONFIG,
                            ),
```

And add the import at the top of trends.py:
```python
from constants import COLORS, CHART_CONFIG
```

(Replace the existing `from constants import COLORS` line.)

#### Step E2: Update dashboard.py dcc.Graph configs

**File**: `shitty_ui/pages/dashboard.py`
**Location**: Multiple `dcc.Graph` declarations in `create_dashboard_page()` and `create_performance_page()`

The dashboard page already has `config={"displayModeBar": False}` on all its `dcc.Graph` components (lines 136, 150, 164, 370, 400). These should be switched to `CHART_CONFIG` for consistency.

Replace all instances of:
```python
config={"displayModeBar": False},
```

With:
```python
config=CHART_CONFIG,
```

There are **5 instances** in dashboard.py (lines 136-138, 150-152, 164-166, 370-372, 400-402).

And update the constants import:
```python
from constants import COLORS, CHART_COLORS, CHART_CONFIG
```

#### Step E3: Update assets.py dcc.Graph config

**File**: `shitty_ui/pages/assets.py`
**Location**: Line 120-122

Change:
```python
                                                            config={
                                                                "displayModeBar": False
                                                            },
```

To:
```python
                                                            config=CHART_CONFIG,
```

And add the import:
```python
from constants import COLORS, CHART_CONFIG
```

(Replace the existing `from constants import COLORS` line.)

---

## Complete Final State of charts.py

After all changes, `shitty_ui/components/charts.py` should look like:

```python
"""Reusable Plotly chart builders for the Shitty UI dashboard."""

from datetime import timedelta

import pandas as pd
import plotly.graph_objects as go

from constants import (
    COLORS,
    SENTIMENT_COLORS,
    MARKER_CONFIG,
    TIMEFRAME_COLORS,
    CHART_LAYOUT,
    CHART_COLORS,
)


def apply_chart_layout(
    fig: go.Figure,
    height: int = 300,
    show_legend: bool = False,
    **overrides,
) -> go.Figure:
    """Apply the shared chart layout to a Plotly figure.

    Merges CHART_LAYOUT base with caller-specific overrides.
    Always call this LAST, after adding traces, so it can override
    any trace-level defaults that Plotly might have set on the layout.

    Args:
        fig: The Plotly figure to style.
        height: Chart height in pixels.
        show_legend: Whether to show the legend.
        **overrides: Additional layout keys to override (e.g.,
            yaxis=dict(title="Accuracy %", range=[0, 105])).

    Returns:
        The same figure, mutated in place (also returned for chaining).
    """
    layout = {**CHART_LAYOUT}
    layout["height"] = height
    layout["showlegend"] = show_legend

    for axis_key in ("xaxis", "yaxis"):
        if axis_key in overrides:
            base_axis = {**layout.get(axis_key, {})}
            base_axis.update(overrides.pop(axis_key))
            layout[axis_key] = base_axis

    layout.update(overrides)
    fig.update_layout(**layout)
    return fig


def build_signal_over_trend_chart(
    prices_df: pd.DataFrame,
    signals_df: pd.DataFrame,
    symbol: str = "",
    show_timeframe_windows: bool = False,
    chart_height: int = 500,
) -> go.Figure:
    """
    Build a candlestick chart with prediction signal markers overlaid.

    Args:
        prices_df: DataFrame with columns: date, open, high, low, close, volume
        signals_df: DataFrame with columns: prediction_date, prediction_sentiment,
                    prediction_confidence, thesis, correct_t7, return_t7, pnl_t7,
                    post_text, price_at_prediction
        symbol: Ticker symbol for chart title
        show_timeframe_windows: If True, draw shaded regions for t7 windows
        chart_height: Height of the chart in pixels

    Returns:
        go.Figure ready to be rendered by dcc.Graph
    """
    fig = go.Figure()

    # --- Trace 1: Candlestick ---
    if not prices_df.empty:
        fig.add_trace(
            go.Candlestick(
                x=prices_df["date"],
                open=prices_df["open"],
                high=prices_df["high"],
                low=prices_df["low"],
                close=prices_df["close"],
                name=symbol or "Price",
                increasing_line_color=CHART_COLORS["candle_up"],
                decreasing_line_color=CHART_COLORS["candle_down"],
                increasing_fillcolor=CHART_COLORS["candle_up_fill"],
                decreasing_fillcolor=CHART_COLORS["candle_down_fill"],
                showlegend=False,
            )
        )

    # --- Trace 2: Signal Markers ---
    if not signals_df.empty and not prices_df.empty:
        for _, signal in signals_df.iterrows():
            pred_date = signal["prediction_date"]
            sentiment = (signal.get("prediction_sentiment") or "neutral").lower()
            confidence = signal.get("prediction_confidence") or 0.5
            thesis = signal.get("thesis") or ""
            correct_t7 = signal.get("correct_t7")
            return_t7 = signal.get("return_t7")
            pnl_t7 = signal.get("pnl_t7")
            post_text = signal.get("post_text") or ""

            # Find the price at this date for y-placement
            price_row = prices_df[prices_df["date"].dt.date == pred_date.date()]
            if price_row.empty:
                continue

            y_val = float(price_row.iloc[0]["high"]) * 1.03

            # Color from sentiment
            marker_color = SENTIMENT_COLORS.get(sentiment, SENTIMENT_COLORS["neutral"])

            # Size from confidence (scale min_size to max_size)
            size_range = MARKER_CONFIG["max_size"] - MARKER_CONFIG["min_size"]
            marker_size = MARKER_CONFIG["min_size"] + (confidence * size_range)

            # Shape from sentiment
            marker_symbol = MARKER_CONFIG["symbols"].get(
                sentiment, MARKER_CONFIG["symbols"]["neutral"]
            )

            # Outcome text for tooltip
            if correct_t7 is True:
                outcome_text = "CORRECT"
            elif correct_t7 is False:
                outcome_text = "INCORRECT"
            else:
                outcome_text = "PENDING"

            # Build hover text
            thesis_preview = (thesis[:100] + "...") if len(thesis) > 100 else thesis
            post_preview = (post_text[:80] + "...") if len(post_text) > 80 else post_text

            hover_parts = [
                f"<b>{pred_date.strftime('%Y-%m-%d')}</b>",
                f"Sentiment: <b>{sentiment.upper()}</b>",
                f"Confidence: <b>{confidence:.0%}</b>",
                f"Outcome: <b>{outcome_text}</b>",
            ]
            if return_t7 is not None:
                hover_parts.append(f"7d Return: <b>{return_t7:+.2f}%</b>")
            if pnl_t7 is not None:
                hover_parts.append(f"P&L: <b>${pnl_t7:+,.0f}</b>")
            if thesis_preview:
                hover_parts.append(f"<br><i>{thesis_preview}</i>")

            hover_text = "<br>".join(hover_parts)

            fig.add_trace(
                go.Scatter(
                    x=[pred_date],
                    y=[y_val],
                    mode="markers",
                    marker=dict(
                        size=marker_size,
                        color=marker_color,
                        symbol=marker_symbol,
                        opacity=MARKER_CONFIG["opacity"],
                        line=dict(
                            width=MARKER_CONFIG["border_width"],
                            color=COLORS["text"],
                        ),
                    ),
                    hovertemplate=hover_text + "<extra></extra>",
                    showlegend=False,
                    name=f"{sentiment} signal",
                )
            )

            # --- Optional: Timeframe windows ---
            if show_timeframe_windows and not price_row.empty:
                _add_timeframe_window(fig, pred_date)

    # --- Layout ---
    apply_chart_layout(
        fig,
        height=chart_height,
        show_legend=False,
        hovermode="closest",
        margin={"l": 50, "r": 20, "t": 30, "b": 40},
        xaxis={"rangeslider": {"visible": False}},
        yaxis={"title": "Price ($)"},
    )

    # Add a custom legend for sentiment markers
    _add_sentiment_legend(fig)

    return fig


def _add_timeframe_window(
    fig: go.Figure,
    pred_date: pd.Timestamp,
) -> None:
    """Add a shaded rectangle for the 7-day evaluation window."""
    t7_end = pred_date + timedelta(days=7)
    fig.add_vrect(
        x0=pred_date,
        x1=t7_end,
        fillcolor=TIMEFRAME_COLORS["t7"],
        layer="below",
        line_width=0,
    )


def _add_sentiment_legend(fig: go.Figure) -> None:
    """Add invisible traces to serve as a sentiment color legend."""
    for sentiment, color in SENTIMENT_COLORS.items():
        symbol = MARKER_CONFIG["symbols"][sentiment]
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker=dict(size=10, color=color, symbol=symbol),
                name=sentiment.capitalize(),
                showlegend=True,
            )
        )

    fig.update_layout(
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color=COLORS["text_muted"], size=11),
        ),
    )


def build_empty_signal_chart(message: str = "No data available") -> go.Figure:
    """Build an empty chart with a centered message."""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        showarrow=False,
        font=dict(color=COLORS["text_muted"], size=14),
    )
    apply_chart_layout(
        fig,
        height=400,
        xaxis={"showgrid": False, "showticklabels": False, "zeroline": False},
        yaxis={"showgrid": False, "showticklabels": False, "zeroline": False},
    )
    return fig
```

---

## Test Plan

### New Tests

**File**: `shit_tests/shitty_ui/test_charts.py`

Add the following test classes/methods to the existing file:

```python
from constants import CHART_LAYOUT, CHART_COLORS, CHART_CONFIG
from components.charts import apply_chart_layout


class TestApplyChartLayout:
    """Tests for the shared apply_chart_layout() helper."""

    def test_sets_transparent_backgrounds(self):
        """Base layout must set transparent plot and paper backgrounds."""
        fig = go.Figure()
        apply_chart_layout(fig)
        assert fig.layout.plot_bgcolor == "rgba(0,0,0,0)"
        assert fig.layout.paper_bgcolor == "rgba(0,0,0,0)"

    def test_sets_height(self):
        """Height parameter is applied to the figure layout."""
        fig = go.Figure()
        apply_chart_layout(fig, height=450)
        assert fig.layout.height == 450

    def test_default_height_is_300(self):
        """Default height should be 300 if not specified."""
        fig = go.Figure()
        apply_chart_layout(fig)
        assert fig.layout.height == 300

    def test_show_legend_false_by_default(self):
        """Legend should be hidden by default."""
        fig = go.Figure()
        apply_chart_layout(fig)
        assert fig.layout.showlegend is False

    def test_show_legend_override(self):
        """show_legend=True enables the legend."""
        fig = go.Figure()
        apply_chart_layout(fig, show_legend=True)
        assert fig.layout.showlegend is True

    def test_yaxis_override_preserves_gridcolor(self):
        """Overriding yaxis title should not lose gridcolor from base."""
        fig = go.Figure()
        apply_chart_layout(fig, yaxis={"title": "Accuracy %"})
        assert fig.layout.yaxis.title.text == "Accuracy %"
        assert fig.layout.yaxis.gridcolor is not None
        assert "51, 65, 85" in fig.layout.yaxis.gridcolor

    def test_xaxis_override_preserves_gridcolor(self):
        """Overriding xaxis should not lose gridcolor from base."""
        fig = go.Figure()
        apply_chart_layout(fig, xaxis={"rangeslider": {"visible": False}})
        assert fig.layout.xaxis.gridcolor is not None

    def test_hoverlabel_styling(self):
        """Base layout must set dark hoverlabel with matching font."""
        fig = go.Figure()
        apply_chart_layout(fig)
        assert fig.layout.hoverlabel.bgcolor == "#1e293b"
        assert fig.layout.hoverlabel.bordercolor == "#334155"
        assert fig.layout.hoverlabel.font.color == "#f1f5f9"

    def test_font_family_set(self):
        """Base layout must set system font stack."""
        fig = go.Figure()
        apply_chart_layout(fig)
        assert "apple-system" in fig.layout.font.family

    def test_arbitrary_overrides(self):
        """Extra kwargs are passed through to update_layout."""
        fig = go.Figure()
        apply_chart_layout(fig, hovermode="closest", bargap=0.3)
        assert fig.layout.hovermode == "closest"
        assert fig.layout.bargap == 0.3

    def test_returns_same_figure(self):
        """Function returns the same figure object for chaining."""
        fig = go.Figure()
        result = apply_chart_layout(fig)
        assert result is fig


class TestChartConstants:
    """Tests for the chart constant dicts in constants.py."""

    def test_chart_layout_has_required_keys(self):
        """CHART_LAYOUT must contain all essential layout keys."""
        required = [
            "plot_bgcolor", "paper_bgcolor", "font", "margin",
            "xaxis", "yaxis", "hoverlabel", "showlegend",
        ]
        for key in required:
            assert key in CHART_LAYOUT, f"Missing key: {key}"

    def test_chart_config_disables_modebar(self):
        """CHART_CONFIG must suppress the modebar."""
        assert CHART_CONFIG["displayModeBar"] is False
        assert CHART_CONFIG["displaylogo"] is False

    def test_chart_colors_has_candle_colors(self):
        """CHART_COLORS must have candlestick color keys."""
        for key in ["candle_up", "candle_down", "candle_up_fill", "candle_down_fill"]:
            assert key in CHART_COLORS, f"Missing key: {key}"

    def test_chart_colors_match_app_palette(self):
        """Candle colors must match COLORS success/danger."""
        assert CHART_COLORS["candle_up"] == COLORS["success"]
        assert CHART_COLORS["candle_down"] == COLORS["danger"]

    def test_bar_palette_has_minimum_colors(self):
        """Bar palette must have at least 4 colors for multi-series charts."""
        assert len(CHART_COLORS["bar_palette"]) >= 4


class TestCandlestickChartRestyled:
    """Tests that build_signal_over_trend_chart uses new chart colors."""

    def test_candlestick_uses_chart_colors(self):
        """Candlestick trace must use CHART_COLORS instead of COLORS."""
        fig = build_signal_over_trend_chart(
            prices_df=_make_prices_df(),
            signals_df=pd.DataFrame(),
            symbol="TEST",
        )
        candle_trace = [t for t in fig.data if isinstance(t, go.Candlestick)]
        assert len(candle_trace) == 1
        assert candle_trace[0].increasing.line.color == CHART_COLORS["candle_up"]
        assert candle_trace[0].decreasing.line.color == CHART_COLORS["candle_down"]

    def test_candlestick_has_explicit_fill_colors(self):
        """Candlestick fill colors must be explicitly set (not Plotly defaults)."""
        fig = build_signal_over_trend_chart(
            prices_df=_make_prices_df(),
            signals_df=pd.DataFrame(),
            symbol="TEST",
        )
        candle_trace = [t for t in fig.data if isinstance(t, go.Candlestick)][0]
        assert candle_trace.increasing.fillcolor == CHART_COLORS["candle_up_fill"]
        assert candle_trace.decreasing.fillcolor == CHART_COLORS["candle_down_fill"]

    def test_layout_uses_apply_chart_layout(self):
        """Chart layout must have hoverlabel styling from shared base."""
        fig = build_signal_over_trend_chart(
            prices_df=_make_prices_df(),
            signals_df=pd.DataFrame(),
            symbol="TEST",
        )
        # Verify hoverlabel comes from CHART_LAYOUT (proof apply_chart_layout was used)
        assert fig.layout.hoverlabel.bgcolor == "#1e293b"

    def test_rangeslider_hidden(self):
        """Candlestick range slider must be hidden."""
        fig = build_signal_over_trend_chart(
            prices_df=_make_prices_df(),
            signals_df=pd.DataFrame(),
            symbol="TEST",
        )
        assert fig.layout.xaxis.rangeslider.visible is False


class TestEmptyChartRestyled:
    """Tests that build_empty_signal_chart uses apply_chart_layout."""

    def test_empty_chart_has_hoverlabel(self):
        """Empty chart must have hoverlabel styling from shared base."""
        fig = build_empty_signal_chart("test message")
        assert fig.layout.hoverlabel.bgcolor == "#1e293b"

    def test_empty_chart_hides_gridlines(self):
        """Empty chart must hide all gridlines and tick labels."""
        fig = build_empty_signal_chart()
        assert fig.layout.xaxis.showgrid is False
        assert fig.layout.yaxis.showgrid is False
        assert fig.layout.xaxis.showticklabels is False
        assert fig.layout.yaxis.showticklabels is False
```

### Updated Existing Tests

The existing tests in `TestBuildSignalOverTrendChart` and `TestBuildEmptySignalChart` should continue to pass without modification. The changes preserve all existing behavior:
- Marker colors still come from `SENTIMENT_COLORS` (unchanged)
- Marker sizes still scale from `MARKER_CONFIG` (unchanged)
- Hover templates on signal markers are unchanged
- Timeframe windows still use `TIMEFRAME_COLORS` (unchanged)
- Legend traces are still added via `_add_sentiment_legend` (unchanged)
- Empty chart annotation text/font is unchanged

The only risk is `test_returns_figure_with_empty_prices` -- verify that `apply_chart_layout` does not error when the figure has no traces. It should not, since `fig.update_layout()` works on empty figures.

---

## Verification Checklist

- [ ] All existing chart tests pass: `source venv/bin/activate && pytest shit_tests/shitty_ui/test_charts.py -v`
- [ ] New `TestApplyChartLayout` tests pass (11 tests)
- [ ] New `TestChartConstants` tests pass (5 tests)
- [ ] New `TestCandlestickChartRestyled` tests pass (4 tests)
- [ ] New `TestEmptyChartRestyled` tests pass (2 tests)
- [ ] Full test suite passes: `source venv/bin/activate && pytest shit_tests/shitty_ui/ -v`
- [ ] Candlestick chart on /trends page uses CHART_COLORS (solid green/red candles)
- [ ] Candlestick chart on /assets/{symbol} page uses CHART_COLORS
- [ ] Accuracy Over Time chart uses spline lines, subtler fill, dot reference line
- [ ] Confidence Distribution chart has wider bar gaps, explicit text styling
- [ ] Asset Accuracy chart uses `hovermode="closest"` (not "x unified")
- [ ] Sentiment Donut has slice separators, larger center annotation
- [ ] ALL `dcc.Graph` components use `config=CHART_CONFIG` (no more inline dicts)
- [ ] Modebar is hidden on ALL charts (no Plotly logo visible)
- [ ] Hoverlabel on ALL charts has dark background with matching font
- [ ] No regressions on /performance page charts
- [ ] Linting passes: `source venv/bin/activate && python3 -m ruff check shitty_ui/`
- [ ] CHANGELOG.md updated

---

## What NOT To Do

1. **Do NOT change the data query functions.** This phase is purely visual. No changes to `data.py`, no changes to database queries.

2. **Do NOT modify signal marker behavior.** Marker colors, sizes, symbols, and hover text on signal overlay dots are already well-designed. They use `SENTIMENT_COLORS` and `MARKER_CONFIG` which are fine. Only the candlestick trace and layout wrapper change.

3. **Do NOT add new chart types or new traces.** This is restyling, not new features. Do not add volume bars, moving averages, or Bollinger bands -- that's future work.

4. **Do NOT change chart heights.** Keep the existing heights (500 for candlestick, 280 for accuracy, 250 for bar charts, 300 for performance charts, 400 for empty). These were tuned for the existing card layout.

5. **Do NOT use Plotly templates (`pio.templates`).** Plotly's template system is global and can leak between tests. The `apply_chart_layout()` helper is explicit, testable, and doesn't affect global state.

6. **Do NOT remove the `_add_sentiment_legend()` function.** It is still needed for the candlestick chart's legend. The fact that `apply_chart_layout` sets `showlegend=False` is intentional -- the legend function overrides it after.

7. **Do NOT change the `dcc.Graph` `id` props.** Callback wiring depends on these IDs. Changing them would break every callback that targets these charts.

8. **Do NOT add animation or transitions.** Plotly transitions look smooth in isolation but cause jank with Dash's callback-driven re-rendering. Keep `transition` unset.

---

## CHANGELOG Entry

```markdown
### Changed
- **Chart restyling** -- Unified all Plotly chart styling through shared `CHART_LAYOUT` base config and `apply_chart_layout()` helper
  - Consistent dark hoverlabel styling, system font stack, and transparent backgrounds across all charts
  - Candlestick charts use solid fill colors matching the app's emerald/red palette (no more default Plotly half-fills)
  - Accuracy line chart uses spline curves, subtler area fill, and dot-style reference line
  - Bar charts get wider gaps (`bargap`) and explicit text label styling
  - Sentiment donut gets slice separators and enlarged center annotation
  - All `dcc.Graph` components use standardized `CHART_CONFIG` (modebar hidden everywhere, no Plotly logo)
```
