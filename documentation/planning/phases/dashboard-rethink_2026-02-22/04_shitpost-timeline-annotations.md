# Phase 04: Shitpost Timeline Annotations

✅ COMPLETE
**Started**: 2026-02-22
**Completed**: 2026-02-22

**PR Title**: feat(charts): replace candlestick with annotated line chart showing shitpost timeline
**Risk Level**: Medium
**Estimated Effort**: Medium (3-4 hours)
**Files Modified**: 2 (`shitty_ui/components/charts.py`, `shitty_ui/pages/assets.py`)
**Files Created**: 0
**Files Deleted**: 0

---

## Context

This phase addresses the single most important visualization gap in the entire product. The core promise of Shitpost Alpha is: **"Trump posted, then the market moved."** Today, that correlation is invisible. The Trends page shows a candlestick chart with tiny triangle/circle markers floating above random candles (see `/tmp/design-review-2026-02-22_120000/trends-desktop.png`). The user's exact words:

> "I have no idea what the primary graph showing candlesticks is"

> "Small multiple charts. Clicking in, we can annotate over the x axis timeline a vertical line that represents the posts."

The candlestick chart is a professional finance visualization that means nothing to this audience. The signal markers are small, positioned at arbitrary y-values above candle highs, and offer no visual connection between "a post happened" and "the price changed."

This phase replaces the candlestick chart with a clean **line chart** overlaid with **full-height vertical annotation lines** at each shitpost date. Each vertical line is color-coded by predicted sentiment (green/red/gray), extends the full height of the chart, and is hoverable with a rich tooltip showing the post snippet, predicted sentiment, confidence, and actual 7-day return. The result makes the Trump-post-to-market-move correlation immediately visible at a glance.

This chart is used on the **asset detail page** (`/assets/<symbol>`), which is the drill-down target from the screener table (Phase 03). The Trends page (`/trends`) will be retired/redirected in a later phase -- this phase does NOT touch trends.py.

---

## Visual Specification

### Before

**Current state** (`trends-desktop.png`, and identical logic in `assets.py`):
- Candlestick OHLCV chart (green/red candles)
- Signal markers as small scatter points (triangle-up for bullish, triangle-down for bearish, circle for neutral)
- Markers positioned at `high * 1.03` y-value -- floating above candle tops with no connection to the timeline
- Hover tooltip shows date, sentiment, confidence, outcome, return, P&L, thesis preview
- Tiny markers are hard to spot; candle patterns are meaningless to non-traders
- No visual connection between "when a post happened" and "how the price moved after"

### After

**New annotated line chart**:

1. **Price line**: A single smooth line tracing `close` price over time
   - Line color: `CHART_COLORS["line_accent"]` (`#3b82f6`, blue)
   - Line width: 2px
   - Fill under curve: `CHART_COLORS["line_accent_fill"]` (`rgba(59, 130, 246, 0.08)`)
   - No candles, no OHLC -- just the closing price as a clean line

2. **Vertical annotation lines**: One per shitpost prediction, extending the full chart height
   - Color-coded by sentiment:
     - Bullish: `SENTIMENT_COLORS["bullish"]` (`#10b981`, emerald)
     - Bearish: `SENTIMENT_COLORS["bearish"]` (`#ef4444`, red)
     - Neutral: `SENTIMENT_COLORS["neutral"]` (`#94a3b8`, slate gray)
   - Opacity: 0.4 (subtle enough not to overwhelm, visible enough to notice)
   - Line style: solid, width 1.5px
   - Extends from `y0=0` to `y1=1` in paper coordinates (full chart height)

3. **Marker dots at line tops**: Small circular markers at the top of each vertical line
   - Positioned at `yref="paper"`, `y=0.95` (near chart top, in paper coords)
   - Size: 8px
   - Color: matches the vertical line's sentiment color
   - Border: 1.5px white (`COLORS["text"]`) for contrast
   - Shape: circle (not triangles -- simpler, cleaner)

4. **Hover tooltips on markers**: Rich hover data when user mouses over a marker dot
   - Post snippet (first 80 chars of `post_text`)
   - Predicted sentiment (BULLISH / BEARISH / NEUTRAL)
   - Confidence (e.g., "72%")
   - 7-day return (e.g., "+3.45%" or "PENDING")
   - Outcome (CORRECT / INCORRECT / PENDING)
   - P&L if available (e.g., "$+34")

5. **Summary panel below chart**: A row of mini-stat cards summarizing prediction activity
   - "X posts about {symbol}" -- total prediction count
   - "Y% predicted bullish" -- bullish percentage
   - "Z% accuracy (7d)" -- evaluated accuracy
   - Avg confidence
   - Total P&L

6. **Grid and axes**:
   - X-axis: dates, standard Plotly date formatting
   - Y-axis: "Price ($)" label
   - Grid: existing `CHART_LAYOUT` grid styling (subtle `rgba(51, 65, 85, 0.5)` lines)
   - Background: transparent (inherits card background)

### Plotly Implementation Details

**Vertical lines** use `fig.add_shape()` with `type="line"`:

```python
fig.add_shape(
    type="line",
    x0=pred_date,
    x1=pred_date,
    y0=0,
    y1=1,
    yref="paper",
    line=dict(
        color=sentiment_color,
        width=1.5,
        dash="solid",
    ),
    opacity=0.4,
    layer="below",  # Draw behind the price line
)
```

**Marker dots** use a single `go.Scatter` trace with all markers batched (NOT one trace per signal -- avoids trace explosion):

```python
fig.add_trace(
    go.Scatter(
        x=marker_dates,        # List of prediction dates
        y=marker_y_positions,  # All set to a fixed y near chart top
        mode="markers",
        marker=dict(
            size=8,
            color=marker_colors,   # List of sentiment colors per marker
            line=dict(width=1.5, color=COLORS["text"]),
            symbol="circle",
        ),
        customdata=customdata_array,  # 2D array: [[snippet, sentiment, conf, return, outcome, pnl], ...]
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Sentiment: <b>%{customdata[1]}</b><br>"
            "Confidence: <b>%{customdata[2]}</b><br>"
            "7d Return: <b>%{customdata[3]}</b><br>"
            "Outcome: <b>%{customdata[4]}</b><br>"
            "P&L: <b>%{customdata[5]}</b>"
            "<extra></extra>"
        ),
        showlegend=False,
        name="Shitpost Signals",
    )
)
```

**Key design decision -- marker y-positioning**: The markers cannot use data coordinates for y-position because they need to be at the top of the chart regardless of the price scale. However, `go.Scatter` traces do not support `yref="paper"`. The solution is to compute a y-value in data coordinates that sits near the top of the visible price range:

```python
y_top = prices_df["close"].max() * 1.04  # 4% above the highest close price
marker_y_positions = [y_top] * len(signals_df)
```

Then set `yaxis.range` to include headroom:

```python
y_min = prices_df["close"].min() * 0.97
y_max = prices_df["close"].max() * 1.07  # Extra headroom for markers
```

---

## Dependencies

- **Phase 02** (Theme & Design Tokens): This phase uses `SENTIMENT_COLORS`, `CHART_COLORS`, and `CHART_LAYOUT` from `constants.py`. Phase 02 may update these color values for the new "hyper-American money" theme. The vertical line colors come from `SENTIMENT_COLORS`, which Phase 02 may change. This phase should use the constants by reference (not hardcoded hex values), so it automatically picks up Phase 02's changes.
- **No dependency on Phase 03** (Screener Table): The asset page already exists and is independently accessible via `/assets/<symbol>`. Phase 03 adds click-to-drill from the table, but this phase works without it.

**Unlocks**:
- **Phase 05**: Can build on this chart for additional overlays (volume bars, moving averages, etc.)

---

## Detailed Implementation Plan

### Step 1: Add `build_annotated_price_chart()` to `shitty_ui/components/charts.py`

Add a new function at the **end of the file** (after `build_empty_signal_chart`, currently line 255). The existing `build_signal_over_trend_chart` is NOT modified or removed -- it is still used by `trends.py` until that page is retired.

**New function to add at the end of `charts.py`**:

```python
def build_annotated_price_chart(
    prices_df: pd.DataFrame,
    signals_df: pd.DataFrame,
    symbol: str = "",
    chart_height: int = 450,
) -> go.Figure:
    """
    Build a line chart of closing prices with vertical annotation lines
    marking each shitpost prediction date.

    This replaces the candlestick chart for the asset detail page. The
    design prioritizes the "Trump posted, then the market moved" correlation
    by drawing full-height vertical lines at each prediction date, color-coded
    by predicted sentiment.

    Args:
        prices_df: DataFrame with columns: date, open, high, low, close, volume.
            Must be sorted by date ascending.
        signals_df: DataFrame with columns: prediction_date, prediction_sentiment,
            prediction_confidence, thesis, correct_t7, return_t7, pnl_t7, post_text,
            price_at_prediction. Can be empty.
        symbol: Ticker symbol for axis labeling.
        chart_height: Height of the chart in pixels.

    Returns:
        go.Figure ready to be rendered by dcc.Graph.
    """
    fig = go.Figure()

    if prices_df.empty:
        return build_empty_signal_chart(f"No price data for {symbol}")

    # --- Trace 1: Price Line ---
    fig.add_trace(
        go.Scatter(
            x=prices_df["date"],
            y=prices_df["close"],
            mode="lines",
            line=dict(
                color=CHART_COLORS["line_accent"],
                width=2,
            ),
            fill="tozeroy",
            fillcolor=CHART_COLORS["line_accent_fill"],
            name=f"{symbol} Close",
            showlegend=False,
            hovertemplate=(
                "<b>%{x|%b %d, %Y}</b><br>"
                "Close: <b>$%{y:,.2f}</b>"
                "<extra></extra>"
            ),
        )
    )

    # --- Compute y-axis range with headroom for markers ---
    y_min = float(prices_df["close"].min()) * 0.97
    y_max = float(prices_df["close"].max()) * 1.07
    y_marker = float(prices_df["close"].max()) * 1.04  # Marker y-position

    # --- Vertical lines + marker dots for signals ---
    if not signals_df.empty:
        marker_dates = []
        marker_colors = []
        customdata_rows = []

        for _, signal in signals_df.iterrows():
            pred_date = signal["prediction_date"]
            sentiment = (signal.get("prediction_sentiment") or "neutral").lower()
            confidence = signal.get("prediction_confidence") or 0.5
            thesis = signal.get("thesis") or ""
            correct_t7 = signal.get("correct_t7")
            return_t7 = signal.get("return_t7")
            pnl_t7 = signal.get("pnl_t7")
            post_text = signal.get("post_text") or ""

            # Sentiment color
            sentiment_color = SENTIMENT_COLORS.get(
                sentiment, SENTIMENT_COLORS["neutral"]
            )

            # --- Vertical annotation line ---
            fig.add_shape(
                type="line",
                x0=pred_date,
                x1=pred_date,
                y0=0,
                y1=1,
                yref="paper",
                line=dict(
                    color=sentiment_color,
                    width=1.5,
                    dash="solid",
                ),
                opacity=0.4,
                layer="below",
            )

            # --- Collect marker data ---
            marker_dates.append(pred_date)
            marker_colors.append(sentiment_color)

            # Build customdata row for hover
            post_snippet = (post_text[:80] + "...") if len(post_text) > 80 else post_text
            conf_str = f"{confidence:.0%}"

            if correct_t7 is True:
                outcome_str = "CORRECT"
            elif correct_t7 is False:
                outcome_str = "INCORRECT"
            else:
                outcome_str = "PENDING"

            return_str = f"{return_t7:+.2f}%" if return_t7 is not None else "PENDING"
            pnl_str = f"${pnl_t7:+,.0f}" if pnl_t7 is not None else "N/A"

            customdata_rows.append([
                post_snippet,
                sentiment.upper(),
                conf_str,
                return_str,
                outcome_str,
                pnl_str,
            ])

        # --- Trace 2: Marker dots (single batched trace) ---
        if marker_dates:
            fig.add_trace(
                go.Scatter(
                    x=marker_dates,
                    y=[y_marker] * len(marker_dates),
                    mode="markers",
                    marker=dict(
                        size=8,
                        color=marker_colors,
                        symbol="circle",
                        line=dict(
                            width=1.5,
                            color=COLORS["text"],
                        ),
                    ),
                    customdata=customdata_rows,
                    hovertemplate=(
                        "<b>%{customdata[0]}</b><br>"
                        "Sentiment: <b>%{customdata[1]}</b><br>"
                        "Confidence: <b>%{customdata[2]}</b><br>"
                        "7d Return: <b>%{customdata[3]}</b><br>"
                        "Outcome: <b>%{customdata[4]}</b><br>"
                        "P&L: <b>%{customdata[5]}</b>"
                        "<extra></extra>"
                    ),
                    showlegend=False,
                    name="Shitpost Signals",
                )
            )

    # --- Layout ---
    apply_chart_layout(
        fig,
        height=chart_height,
        show_legend=False,
        hovermode="closest",
        margin={"l": 50, "r": 20, "t": 30, "b": 40},
        yaxis={
            "title": "Price ($)",
            "range": [y_min, y_max],
        },
    )

    # --- Sentiment legend ---
    _add_annotation_legend(fig)

    return fig


def _add_annotation_legend(fig: go.Figure) -> None:
    """Add invisible scatter traces as a legend for annotation line colors."""
    for sentiment, color in SENTIMENT_COLORS.items():
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker=dict(size=8, color=color, symbol="circle"),
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
```

**New import needed**: None -- all imports already present at top of `charts.py`.

### Step 2: Update `shitty_ui/pages/assets.py` to use the new chart

#### 2a. Update the import statement

**File**: `shitty_ui/pages/assets.py`, line 11

**Before** (line 11):
```python
from components.charts import build_signal_over_trend_chart, build_empty_signal_chart
```

**After**:
```python
from components.charts import build_annotated_price_chart, build_empty_signal_chart
```

Note: `build_signal_over_trend_chart` is no longer needed in this file.

#### 2b. Replace the chart call in `update_asset_price_chart` callback

**File**: `shitty_ui/pages/assets.py`, lines 480-486

**Before** (lines 480-486):
```python
            return build_signal_over_trend_chart(
                prices_df=data["prices"],
                signals_df=data["signals"],
                symbol=symbol,
                show_timeframe_windows=False,
                chart_height=400,
            )
```

**After**:
```python
            return build_annotated_price_chart(
                prices_df=data["prices"],
                signals_df=data["signals"],
                symbol=symbol,
                chart_height=400,
            )
```

Note: `show_timeframe_windows` parameter is dropped -- the new chart does not support timeframe windows (they were a candlestick-specific concept).

#### 2c. Add the summary panel below the chart

**File**: `shitty_ui/pages/assets.py`

Add a new output to the `update_asset_page` callback and a new container in the layout.

**Layout change**: In `create_asset_page()`, add a summary row container between the price chart row and the prediction timeline card.

**Before** (lines 176-178, inside `create_asset_page`):
```python
                    className="mb-4",
                ),
                # Prediction timeline
```

**After**:
```python
                    className="mb-4",
                ),
                # Signal summary stats for this asset
                dcc.Loading(
                    type="default",
                    color=COLORS["accent"],
                    children=html.Div(id="asset-signal-summary", className="mb-4"),
                ),
                # Prediction timeline
```

**Callback change**: Add `Output("asset-signal-summary", "children")` to the `update_asset_page` callback and populate it.

**Before** (lines 300-308, callback decorator):
```python
    @app.callback(
        [
            Output("asset-stat-cards", "children"),
            Output("asset-current-price", "children"),
            Output("asset-performance-summary", "children"),
            Output("asset-prediction-timeline", "children"),
            Output("asset-related-assets", "children"),
        ],
        [Input("asset-page-symbol", "data")],
    )
```

**After**:
```python
    @app.callback(
        [
            Output("asset-stat-cards", "children"),
            Output("asset-current-price", "children"),
            Output("asset-performance-summary", "children"),
            Output("asset-signal-summary", "children"),
            Output("asset-prediction-timeline", "children"),
            Output("asset-related-assets", "children"),
        ],
        [Input("asset-page-symbol", "data")],
    )
```

**Before** -- empty/error returns (line 317):
```python
            empty = html.P("No asset selected.", style={"color": COLORS["text_muted"]})
            return empty, "", empty, empty, empty
```

**After**:
```python
            empty = html.P("No asset selected.", style={"color": COLORS["text_muted"]})
            return empty, "", empty, empty, empty, empty
```

**Before** -- error return (line 444):
```python
            return error_card, "", error_card, error_card, error_card
```

**After**:
```python
            return error_card, "", error_card, error_card, error_card, error_card
```

**Add summary panel builder**: Between the prediction timeline and related assets sections in the `update_asset_page` callback body, add signal summary computation. Insert after the `predictions_df` fetching block (after line 412) and before the related assets block:

```python
            # --- SIGNAL SUMMARY ---
            signal_summary = _build_asset_signal_summary(symbol, predictions_df)
```

And update the return tuple. **Before** (lines 433-439):
```python
            return (
                stat_cards,
                current_price_text,
                performance_summary,
                timeline_cards,
                related_links,
            )
```

**After**:
```python
            return (
                stat_cards,
                current_price_text,
                performance_summary,
                signal_summary,
                timeline_cards,
                related_links,
            )
```

**Add the `_build_asset_signal_summary` helper function** at the bottom of `assets.py` (after `register_asset_callbacks`):

```python
def _build_asset_signal_summary(symbol: str, predictions_df) -> html.Div:
    """Build a summary stats row for shitpost signals on this asset.

    Shows total post count, bullish %, accuracy, avg confidence, and total P&L
    as a compact stat row below the price chart.

    Args:
        symbol: Ticker symbol.
        predictions_df: DataFrame from get_asset_predictions() with columns
            prediction_sentiment, prediction_confidence, correct_t7, pnl_t7.

    Returns:
        html.Div containing a dbc.Row of mini stat cards, or an empty Div.
    """
    if predictions_df.empty:
        return html.Div(
            html.P(
                f"No predictions found for {symbol}.",
                style={
                    "color": COLORS["text_muted"],
                    "textAlign": "center",
                    "padding": "15px",
                },
            )
        )

    total = len(predictions_df)

    bullish = 0
    if "prediction_sentiment" in predictions_df.columns:
        bullish = (
            predictions_df["prediction_sentiment"].str.lower() == "bullish"
        ).sum()
    bullish_pct = (bullish / total * 100) if total > 0 else 0

    avg_conf = 0.0
    if "prediction_confidence" in predictions_df.columns:
        avg_conf = predictions_df["prediction_confidence"].mean() or 0.0

    evaluated = 0
    correct = 0
    accuracy = 0.0
    if "correct_t7" in predictions_df.columns:
        correct_col = predictions_df["correct_t7"]
        evaluated = correct_col.notna().sum()
        correct = (correct_col == True).sum()  # noqa: E712
        accuracy = (correct / evaluated * 100) if evaluated > 0 else 0.0

    total_pnl = 0.0
    if "pnl_t7" in predictions_df.columns:
        total_pnl = predictions_df["pnl_t7"].sum() or 0.0

    return dbc.Row(
        [
            dbc.Col(
                _mini_stat_card(
                    f"{total} posts",
                    f"mentioning {symbol}",
                    COLORS["accent"],
                ),
                md=2, sm=4, xs=6,
            ),
            dbc.Col(
                _mini_stat_card(
                    f"{bullish_pct:.0f}%",
                    "predicted bullish",
                    COLORS["success"],
                ),
                md=2, sm=4, xs=6,
            ),
            dbc.Col(
                _mini_stat_card(
                    f"{accuracy:.0f}%",
                    f"accuracy ({correct}/{evaluated})",
                    COLORS["success"] if accuracy > 50 else COLORS["danger"],
                ),
                md=2, sm=4, xs=6,
            ),
            dbc.Col(
                _mini_stat_card(
                    f"{avg_conf:.0%}",
                    "avg confidence",
                    COLORS["warning"],
                ),
                md=2, sm=4, xs=6,
            ),
            dbc.Col(
                _mini_stat_card(
                    f"${total_pnl:+,.0f}",
                    "total P&L (7d)",
                    COLORS["success"] if total_pnl > 0 else COLORS["danger"],
                ),
                md=2, sm=4, xs=6,
            ),
        ],
        className="g-2",
    )


def _mini_stat_card(value: str, label: str, color: str) -> html.Div:
    """Compact stat display for the signal summary row.

    Args:
        value: The prominent value text (e.g., "12 posts", "67%").
        label: Descriptive label below the value.
        color: CSS color for the value text.

    Returns:
        html.Div styled as a small stat card.
    """
    return html.Div(
        [
            html.Div(
                value,
                style={
                    "fontSize": "1.1rem",
                    "fontWeight": "bold",
                    "color": color,
                },
            ),
            html.Div(
                label,
                style={
                    "fontSize": "0.75rem",
                    "color": COLORS["text_muted"],
                },
            ),
        ],
        style={
            "textAlign": "center",
            "padding": "10px",
            "backgroundColor": COLORS["secondary"],
            "borderRadius": "8px",
            "border": f"1px solid {COLORS['border']}",
        },
    )
```

**New import needed in `assets.py`**: Add `import dash_bootstrap_components as dbc` -- already imported on line 7, so no change needed.

### Step 3: Update the chart card header icon

**File**: `shitty_ui/pages/assets.py`, line 70

The chart card currently uses `fas fa-chart-line` icon. This is fine -- keep it. No change needed. The header text `f"{symbol} Price History"` is also appropriate. No change.

---

## Responsive Behavior

### Desktop (>768px)
- Full chart with vertical lines, colored marker dots with white borders, and hover tooltips
- Legend row ("Bullish / Bearish / Neutral") displayed horizontally above chart
- Summary panel: 5 stat cards in a single row (each `md=2`)

### Tablet (768px)
- Chart resizes responsively (Plotly `responsive: true` in `CHART_CONFIG`)
- Vertical lines and markers render identically (they are relative to chart width)
- Summary panel: stat cards wrap to 2 rows (each `sm=4`, so 3 per row)

### Mobile (<480px)
- Chart at full container width, reduced height is handled by Plotly's responsive behavior
- Vertical annotation lines remain visible but narrower due to chart compression
- Marker dots remain at 8px (still tappable on touch)
- Hover tooltips: On mobile, Plotly shows tooltips on tap (not hover) -- this works natively
- Summary panel: stat cards wrap to 2 per row (`xs=6`) + 1 orphan on third row
- Legend text remains legible at 11px

### No special mobile simplification needed
The vertical line approach is inherently responsive -- lines scale with the chart, and marker dots are absolutely positioned relative to the price range. Unlike the candlestick markers (which required careful y-placement relative to candle highs), the vertical lines simply extend full height regardless of viewport.

---

## Accessibility Checklist

- [ ] **Color is not the only indicator**: Sentiment is communicated via both color AND the hover tooltip text ("BULLISH", "BEARISH", "NEUTRAL"). The legend labels also spell out the sentiment.
- [ ] **Contrast ratios**: Green (`#10b981`) on dark background (`#1E293B`) = 4.6:1 (passes AA). Red (`#ef4444`) = 4.3:1 (passes AA). Gray (`#94a3b8`) = 4.1:1 (passes AA for large text; markers are supplementary, not the sole data carrier).
- [ ] **Hover tooltips are keyboard-inaccessible in Plotly**: This is a known Plotly limitation. The prediction timeline card below the chart provides the same information in an accessible HTML format (already implemented in the existing page).
- [ ] **Chart has descriptive axis labels**: y-axis "Price ($)", x-axis auto-labeled with dates.
- [ ] **No animation or auto-play**: Chart is static on load, no flashing or motion.
- [ ] **Alt text**: The `dcc.Graph` component does not support `alt` attributes natively. The summary panel below provides a text-based equivalent of the chart's key information.

---

## Test Plan

### New Tests to Write

All new tests go in `shit_tests/shitty_ui/test_charts.py` (existing file — append new test classes).

**Test 1: `test_build_annotated_price_chart_basic`**
- Verifies the function returns a `go.Figure` with at least one trace (the price line)
- Input: a simple `prices_df` with 10 rows, empty `signals_df`
- Assert: `len(fig.data) >= 1`, first trace is `go.Scatter` with `mode="lines"`

**Test 2: `test_build_annotated_price_chart_with_signals`**
- Input: `prices_df` with 30 rows, `signals_df` with 3 rows (one bullish, one bearish, one neutral)
- Assert: `len(fig.data) >= 2` (price line + marker trace)
- Assert: `len(fig.layout.shapes) == 3` (3 vertical lines)
- Assert: marker trace has `len(fig.data[1].x) == 3`

**Test 3: `test_build_annotated_price_chart_empty_prices`**
- Input: empty `prices_df`, non-empty `signals_df`
- Assert: returns a figure with a centered annotation (empty chart message)
- Assert: no shapes added

**Test 4: `test_build_annotated_price_chart_vertical_line_colors`**
- Input: signals with known sentiments
- Assert: shapes have correct line colors matching `SENTIMENT_COLORS`
- Check `fig.layout.shapes[0].line.color == SENTIMENT_COLORS["bullish"]`

**Test 5: `test_build_annotated_price_chart_hover_customdata`**
- Input: signal with known thesis, confidence, return_t7
- Assert: marker trace's `customdata[0]` contains expected values
- Assert: `customdata[0][1] == "BULLISH"`, `customdata[0][2] == "70%"`, etc.

**Test 6: `test_build_annotated_price_chart_marker_y_position`**
- Input: prices with max close of $100
- Assert: marker y-values are approximately `$104` (100 * 1.04)
- Assert: y-axis range upper bound is approximately `$107` (100 * 1.07)

**Test 7: `test_build_annotated_price_chart_legend_traces`**
- Assert: legend traces exist for Bullish, Bearish, Neutral
- Assert: `fig.layout.showlegend is True`

**Test 8: `test_build_asset_signal_summary_empty`**
- Call `_build_asset_signal_summary("XLE", pd.DataFrame())`
- Assert: returns a Div containing "No predictions found"

**Test 9: `test_build_asset_signal_summary_with_data`**
- Input: DataFrame with 10 predictions, 6 bullish, 4 bearish, 7 evaluated, 4 correct
- Assert: summary contains "10 posts", "60%", "57%" accuracy, P&L value

### Existing Tests to Verify

- Run the full `shit_tests/shitty_ui/` suite to ensure no regressions
- The existing `build_signal_over_trend_chart` tests (if any) should still pass since that function is unchanged
- The asset page callback tests may need updating if they assert on the number of callback outputs (now 6 instead of 5)

### Manual Verification

1. Start the dashboard: `source venv/bin/activate && python -m shitty_ui.app`
2. Navigate to `/assets/XLE` (or any tracked asset)
3. Verify: clean line chart (no candlesticks)
4. Verify: vertical green/red/gray lines at prediction dates
5. Verify: hovering over marker dots shows post snippet, sentiment, confidence, return
6. Verify: summary panel below chart shows post count, bullish %, accuracy
7. Verify: date range buttons (30D/90D/180D/1Y) still work
8. Verify: mobile view at 375px shows chart and summary without overflow
9. Verify: `/trends` page still works with the old candlestick chart (unchanged)

---

## Verification Checklist

- [ ] `build_annotated_price_chart()` exists in `shitty_ui/components/charts.py`
- [ ] `build_signal_over_trend_chart()` still exists and is unchanged (used by trends.py)
- [ ] `assets.py` imports `build_annotated_price_chart` instead of `build_signal_over_trend_chart`
- [ ] `update_asset_price_chart` callback calls `build_annotated_price_chart`
- [ ] `asset-signal-summary` div exists in asset page layout
- [ ] `update_asset_page` callback returns 6 outputs (was 5)
- [ ] All error/empty returns also return 6 values
- [ ] `_build_asset_signal_summary()` and `_mini_stat_card()` exist at bottom of `assets.py`
- [ ] `pytest shit_tests/shitty_ui/` passes
- [ ] `ruff check shitty_ui/components/charts.py shitty_ui/pages/assets.py` passes
- [ ] `ruff format shitty_ui/components/charts.py shitty_ui/pages/assets.py` passes
- [ ] Manual: line chart visible on `/assets/XLE` with vertical annotation lines
- [ ] Manual: hover tooltips work on marker dots
- [ ] Manual: summary panel shows below chart
- [ ] Manual: `/trends` page still renders correctly (regression check)

---

## What NOT To Do

1. **Do NOT use candlestick charts.** The entire point of this phase is to replace the candlestick visualization. Even if you think candlesticks look better, the user explicitly said they don't understand them. Use a line chart.

2. **Do NOT create one Plotly trace per signal.** The existing `build_signal_over_trend_chart` creates a separate `go.Scatter` trace for each signal marker (line 155-173, inside a `for` loop). With 50+ predictions, this creates 50+ traces, which degrades performance and bloats the legend. The new function batches all markers into a SINGLE `go.Scatter` trace using list-valued `x`, `y`, `color`, and `customdata`.

3. **Do NOT use `fig.add_annotation()` for the vertical lines.** Annotations in Plotly are text labels, not visual lines. Use `fig.add_shape(type="line")` for the vertical lines. Annotations would add unwanted text labels to the chart.

4. **Do NOT modify `build_signal_over_trend_chart`.** That function is still used by `trends.py`. Leave it completely unchanged. The new function is additive.

5. **Do NOT modify `trends.py`.** The trends page retirement is a separate phase. This phase only touches `charts.py` and `assets.py`.

6. **Do NOT hardcode color hex values.** Always reference `SENTIMENT_COLORS["bullish"]`, `CHART_COLORS["line_accent"]`, `COLORS["text"]`, etc. from `constants.py`. Phase 02 may change these values.

7. **Do NOT make the hover tooltips too large.** Keep post snippets to 80 characters max. Don't include the full thesis in the hover -- it's already in the prediction timeline cards below. The hover is a quick glance, not a full read.

8. **Do NOT crowd the chart with too many annotation elements.** Stick to: vertical lines + small dots + hover. No inline text labels on the chart. No flags, banners, or icons embedded in the chart area. The vertical lines at 0.4 opacity are intentionally subtle.

9. **Do NOT use `yref="paper"` on `go.Scatter` traces.** Plotly's `go.Scatter` does not support paper-coordinate y-axis. Use a computed data-coordinate y-value (`close.max() * 1.04`) for marker placement. Only `fig.add_shape()` supports `yref="paper"`.

10. **Do NOT forget to update ALL return tuples in `update_asset_page`.** There are three return points: the empty case (line 317), the success case (line 433), and the error case (line 444). All three must return 6 values (was 5). Missing one will cause a Dash callback error.
