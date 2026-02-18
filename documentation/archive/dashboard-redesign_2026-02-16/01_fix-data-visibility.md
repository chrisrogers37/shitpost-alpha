# Phase 01: Fix Data Visibility

**Status**: ✅ COMPLETE
**Started**: 2026-02-16
**Completed**: 2026-02-16
**PR**: #72
**PR Title**: fix: smart time fallback & surface evaluated outcomes
**Risk Level**: Low
**Estimated Effort**: Medium (2-3 hours)
**Dependencies**: None
**Unlocks**: Phase 03 (Empty States), Phase 05 (Merge Sections)

## Files Modified

| File | Action |
|------|--------|
| `shitty_ui/data.py` | Add `get_dashboard_kpis_with_fallback()`, `get_active_signals_with_fallback()`; modify signal feed sort order; add "evaluated" filter |
| `shitty_ui/pages/dashboard.py` | Wire fallback KPIs, fix accuracy chart threshold, use hero fallback |
| `shitty_ui/pages/signals.py` | Add "Evaluated (has outcome)" dropdown option |
| `shitty_ui/components/cards.py` | Extend `create_metric_card()` with `note` parameter |
| `shit_tests/shitty_ui/test_data.py` | Add tests for all new functions and changed behavior |
| `CHANGELOG.md` | Add entry |

## Context

The dashboard shows **all zeros** for KPI metrics and **all predictions as "Pending"** despite having 74+ evaluated trades visible on the /performance page. The root cause is a `WHERE correct_t7 IS NOT NULL` filter in `get_dashboard_kpis()` combined with the 7D default period -- no recent predictions have been evaluated yet (takes 7+ trading days).

Additionally:
- Signal feed orders by `timestamp DESC`, burying evaluated outcomes below hundreds of pending signals
- Accuracy chart requires `len(acc_df) > 1` (2+ weeks), showing "Not enough data" even with 1 week
- Hero signals use a strict 72h window with 0.75 confidence minimum, often returning empty

**Screenshots**: See `/tmp/design-review/dashboard-desktop.png` -- all KPI cards show "0", hero section empty, all signals show "Pending" badges.

## Detailed Implementation

### Change A: KPI Cards -- Smart Fallback to All-Time Data

#### Step A1: Add `get_dashboard_kpis_with_fallback()` to data.py

**File**: `shitty_ui/data.py`
**Location**: After `get_dashboard_kpis()` function (after approximately line 520)

```python
def get_dashboard_kpis_with_fallback(days: int | None = 90) -> dict:
    """Get dashboard KPIs with automatic fallback to all-time data.

    When the selected time period has no evaluated predictions (total_signals == 0),
    falls back to all-time data and marks the result so the UI can display a note.

    Args:
        days: Number of days to filter. None = all time.

    Returns:
        Dict with KPI values plus is_fallback (bool) and fallback_label (str).
    """
    kpis = get_dashboard_kpis(days=days)

    # If period has evaluated signals, return as-is
    if kpis["total_signals"] > 0 or days is None:
        kpis["is_fallback"] = False
        kpis["fallback_label"] = ""
        return kpis

    # Fall back to all-time
    kpis = get_dashboard_kpis(days=None)
    kpis["is_fallback"] = True
    kpis["fallback_label"] = "All-time"
    return kpis
```

#### Step A2: Add `note` parameter to `create_metric_card()`

**File**: `shitty_ui/components/cards.py`
**Location**: Find the `create_metric_card()` function signature

Add `note=""` parameter to the function signature. Then add a conditional note display element at the bottom of the card. The note should render in `COLORS["warning"]` at `FONT_SIZES["xs"]` when non-empty.

Example -- if current signature is:
```python
def create_metric_card(title, value, subtitle, icon, color):
```

Change to:
```python
def create_metric_card(title, value, subtitle, icon, color, note=""):
```

Then at the bottom of the card layout (before the closing `html.Div`), add:
```python
html.Div(
    note,
    style={
        "color": COLORS["warning"],
        "fontSize": FONT_SIZES["small"],
        "marginTop": "4px",
    },
) if note else None,
```

The `note=""` default ensures all 20+ existing callers are unaffected.

#### Step A3: Wire fallback in dashboard.py callback

**File**: `shitty_ui/pages/dashboard.py`
**Location**: Line 633 (inside `update_dashboard()`, the "Performance Metrics" section)

Change:
```python
            kpis = get_dashboard_kpis(days=days)
```

To:
```python
            kpis = get_dashboard_kpis_with_fallback(days=days)
            fallback_note = kpis["fallback_label"] if kpis["is_fallback"] else ""
```

Then update each of the 4 `create_metric_card()` calls to pass `note=fallback_note`. Example for the first card:

```python
                    dbc.Col(
                        create_metric_card(
                            "Total Signals",
                            f"{kpis['total_signals']}",
                            "evaluated predictions",
                            "signal",
                            COLORS["accent"],
                            note=fallback_note,
                        ),
```

Apply the same `note=fallback_note` addition to all 4 metric cards (Total Signals, Accuracy, Avg 7-Day Return, Total P&L).

---

### Change B: Signal Feed -- Surface Evaluated Outcomes First

#### Step B1: Modify sort order in `get_signal_feed()`

**File**: `shitty_ui/data.py`
**Location**: Line 1795

Change:
```python
    base_query += " ORDER BY tss.timestamp DESC LIMIT :limit OFFSET :offset"
```

To:
```python
    base_query += """
        ORDER BY
            CASE WHEN po.correct_t7 IS NOT NULL THEN 0 ELSE 1 END,
            tss.timestamp DESC
        LIMIT :limit OFFSET :offset
    """
```

This sorts evaluated signals (Correct/Incorrect) above pending ones, then within each group by newest first.

#### Step B2: Add "Evaluated" option to outcome filter dropdown

**File**: `shitty_ui/pages/signals.py`
**Location**: Lines 192-214 (the outcome filter dropdown options list)

Add a new option after "All Outcomes":
```python
                                                    {
                                                        "label": "Evaluated (has outcome)",
                                                        "value": "evaluated",
                                                    },
```

#### Step B3: Wire the "evaluated" filter in both query functions

**File**: `shitty_ui/data.py`
**Location**: Lines 1788-1793 in `get_signal_feed()` AND lines 1855-1859 in `get_signal_feed_count()`

In both functions, add a new `elif` case:

```python
    if outcome_filter == "correct":
        base_query += " AND po.correct_t7 = true"
    elif outcome_filter == "incorrect":
        base_query += " AND po.correct_t7 = false"
    elif outcome_filter == "evaluated":
        base_query += " AND po.correct_t7 IS NOT NULL"
    elif outcome_filter == "pending":
        base_query += " AND po.correct_t7 IS NULL"
```

Must be done in **both** `get_signal_feed()` and `get_signal_feed_count()`.

---

### Change C: Accuracy Over Time Chart -- Remove Overly Strict Threshold

#### Step C1: Fix the threshold

**File**: `shitty_ui/pages/dashboard.py`
**Location**: Line 705

Change:
```python
            if not acc_df.empty and len(acc_df) > 1:
```

To:
```python
            if not acc_df.empty and len(acc_df) >= 1:
```

#### Step C2: Add fallback to all-time when period has no data

**File**: `shitty_ui/pages/dashboard.py`
**Location**: Lines 702-757 (the entire accuracy-over-time section)

Replace the existing accuracy over time block with:

```python
        # ===== Accuracy Over Time Chart =====
        try:
            acc_df = get_accuracy_over_time(days=days)

            # If period has no data and we're not already showing all-time, fall back
            if acc_df.empty and days is not None:
                acc_df = get_accuracy_over_time(days=None)
                acc_chart_note = "Showing all-time data (no evaluated predictions in selected period)"
            else:
                acc_chart_note = ""

            if not acc_df.empty and len(acc_df) >= 1:
                acc_fig = go.Figure()
                acc_fig.add_trace(
                    go.Scatter(
                        x=acc_df["week"],
                        y=acc_df["accuracy"],
                        mode="lines+markers",
                        name="Weekly Accuracy",
                        line=dict(color=COLORS["accent"], width=2),
                        marker=dict(size=6, color=COLORS["accent"]),
                        fill="tozeroy",
                        fillcolor="rgba(59, 130, 246, 0.1)",
                        hovertemplate=(
                            "<b>%{x|%b %d, %Y}</b><br>"
                            "Accuracy: %{y:.1f}%<br>"
                            "<extra></extra>"
                        ),
                    )
                )
                # Add 50% reference line
                acc_fig.add_hline(
                    y=50,
                    line_dash="dash",
                    line_color=COLORS["text_muted"],
                    opacity=0.3,
                    annotation_text="50% baseline",
                    annotation_position="bottom right",
                    annotation_font_color=COLORS["text_muted"],
                    annotation_font_size=10,
                )
                # Add fallback note as subtitle annotation if applicable
                if acc_chart_note:
                    acc_fig.add_annotation(
                        text=acc_chart_note,
                        showarrow=False,
                        font=dict(color=COLORS["warning"], size=10),
                        xref="paper",
                        yref="paper",
                        x=0.5,
                        y=1.05,
                    )
                acc_fig.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    font_color=COLORS["text"],
                    margin=dict(l=40, r=40, t=20 if not acc_chart_note else 35, b=40),
                    yaxis=dict(
                        range=[0, 105],
                        title="Accuracy %",
                        gridcolor=COLORS["border"],
                    ),
                    xaxis=dict(gridcolor=COLORS["border"]),
                    height=280,
                    showlegend=False,
                )
            else:
                acc_fig = create_empty_state_chart(
                    message="No evaluated predictions yet",
                    hint="Predictions need 7+ trading days to mature before accuracy is measured",
                )
        except Exception as e:
            errors.append(f"Accuracy over time: {e}")
            print(f"Error loading accuracy over time: {traceback.format_exc()}")
            acc_fig = create_empty_chart(f"Error: {str(e)[:50]}")
```

Key differences from original:
1. `len(acc_df) > 1` changed to `len(acc_df) >= 1`
2. Added fallback to all-time when period has no data
3. Added warning annotation at top of chart when showing fallback data
4. Adjusted top margin when annotation is present
5. Changed empty state message to be more informative

---

### Change D: Hero Signals -- Smarter Fallback with Expanding Time Windows

#### Step D1: Add `get_active_signals_with_fallback()` to data.py

**File**: `shitty_ui/data.py`
**Location**: After `get_active_signals()` (after line 1449)

```python
def get_active_signals_with_fallback() -> tuple:
    """Get hero signals with progressive fallback for wider time windows.

    Tries these strategies in order:
    1. High confidence (>=0.75) in last 72 hours
    2. High confidence (>=0.75) in last 7 days
    3. High confidence (>=0.75) in last 30 days
    4. Medium confidence (>=0.60) in last 30 days

    Returns:
        Tuple of (DataFrame, label_str) where label_str describes the data shown.
    """
    # Strategy 1: Last 72 hours, high confidence
    df = get_active_signals(min_confidence=0.75, hours=72)
    if not df.empty:
        return df, "High confidence predictions in last 72h"

    # Strategy 2: Last 7 days, high confidence
    df = get_active_signals(min_confidence=0.75, hours=168)
    if not df.empty:
        return df, "Top signals this week"

    # Strategy 3: Last 30 days, high confidence
    df = get_active_signals(min_confidence=0.75, hours=720)
    if not df.empty:
        return df, "Top signals this month"

    # Strategy 4: Last 30 days, medium confidence
    df = get_active_signals(min_confidence=0.60, hours=720)
    if not df.empty:
        return df, "Recent signals (30d, confidence >= 60%)"

    # Nothing at all
    return pd.DataFrame(), ""
```

#### Step D2: Update hero section callback in dashboard.py

**File**: `shitty_ui/pages/dashboard.py`
**Location**: Lines 554-629 (hero section inside `update_dashboard()`)

Add import:
```python
from data import (
    ...
    get_active_signals_with_fallback,
)
```

Replace the hero section with a version that:
1. Uses `get_active_signals_with_fallback()` instead of `get_active_signals()`
2. Shows the dynamic `hero_label` as subtitle text
3. Shows a meaningful empty state ("No signals with confidence >= 60% in the last 30 days") only when all 4 fallbacks fail

---

## Test Plan

### New Tests for `get_dashboard_kpis_with_fallback()`

**File**: `shit_tests/shitty_ui/test_data.py`

```python
class TestGetDashboardKpisWithFallback:
    @patch("data.get_dashboard_kpis")
    def test_returns_period_data_when_available(self, mock_kpis):
        """When period has evaluated signals, return without fallback."""
        mock_kpis.return_value = {
            "total_signals": 10, "accuracy_pct": 60.0,
            "avg_return_t7": 1.5, "total_pnl": 500.0,
        }
        result = get_dashboard_kpis_with_fallback(days=7)
        assert result["total_signals"] == 10
        assert result["is_fallback"] is False

    @patch("data.get_dashboard_kpis")
    def test_falls_back_to_alltime_when_period_empty(self, mock_kpis):
        """When period returns zero signals, fall back to all-time."""
        mock_kpis.side_effect = [
            {"total_signals": 0, "accuracy_pct": 0.0, "avg_return_t7": 0.0, "total_pnl": 0.0},
            {"total_signals": 80, "accuracy_pct": 55.0, "avg_return_t7": 1.2, "total_pnl": 1000.0},
        ]
        result = get_dashboard_kpis_with_fallback(days=7)
        assert result["total_signals"] == 80
        assert result["is_fallback"] is True
        assert result["fallback_label"] == "All-time"

    @patch("data.get_dashboard_kpis")
    def test_no_fallback_when_days_is_none(self, mock_kpis):
        """When days=None (already all-time), never fall back."""
        mock_kpis.return_value = {
            "total_signals": 0, "accuracy_pct": 0.0,
            "avg_return_t7": 0.0, "total_pnl": 0.0,
        }
        result = get_dashboard_kpis_with_fallback(days=None)
        assert result["is_fallback"] is False
        mock_kpis.assert_called_once_with(days=None)
```

### New Tests for `get_active_signals_with_fallback()`

Tests for progressive fallback: 72h -> 7d -> 30d -> lower confidence -> empty.

### New Tests for Signal Feed Sort Order and Evaluated Filter

Tests verifying the SQL contains `CASE WHEN po.correct_t7 IS NOT NULL` ordering and `IS NOT NULL` filter clause.

---

## Verification Checklist

- [ ] KPI cards show real numbers on 90D (not zeros); show "All-time" label if period has no evaluated data
- [ ] Signal feed on /signals shows Correct/Incorrect badges first, Pending after
- [ ] "Evaluated (has outcome)" dropdown option works on /signals
- [ ] Accuracy chart shows data with 1 week; falls back to all-time with warning annotation
- [ ] Hero signals show results; label changes based on which fallback triggered
- [ ] All existing tests pass: `source venv/bin/activate && pytest shit_tests/shitty_ui/ -v`
- [ ] /performance page unaffected (regression check)
- [ ] CHANGELOG.md updated

## What NOT To Do

1. **Do NOT change `get_dashboard_kpis()` itself.** It has 6 existing tests. Wrap it instead.
2. **Do NOT remove the `WHERE correct_t7 IS NOT NULL` filter.** Showing pending predictions would inflate counts and make accuracy meaningless. The fix is fallback, not removing the filter.
3. **Do NOT change the default period from 90D.** The fallback mechanism handles the empty-period case.
4. **Do NOT add a new database table or column.** This is purely display/query logic.
5. **Do NOT modify `get_active_signals()` signature.** The wrapper calls it with different parameters.
6. **Do NOT break signal feed pagination.** Sort order change applies before LIMIT/OFFSET.
7. **Do NOT add caching to new wrapper functions.** They call cached functions internally.
8. **Do NOT modify `create_metric_card` in a way that breaks existing callers.** The `note` param must default to `""`.
9. **Do NOT forget to update CHANGELOG.md.**

## CHANGELOG Entry

```markdown
### Fixed
- **Dashboard KPIs show zeros** -- Added smart fallback to all-time data when selected time period has no evaluated predictions, with visual indicator
- **Signal feed buries evaluated outcomes** -- Changed sort order to show Correct/Incorrect signals before Pending ones; added "Evaluated" filter option
- **Accuracy chart requires 2+ weeks** -- Lowered threshold to 1 week; added all-time fallback when period has no data
- **Hero signals often empty** -- Added progressive time window fallback (72h -> 7d -> 30d -> lower confidence) with dynamic labels
```
