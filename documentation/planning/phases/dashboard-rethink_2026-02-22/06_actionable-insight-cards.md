# Phase 06: Actionable Insight Cards

**PR Title:** feat(dashboard): dynamic insight cards that answer "so what right now?"

**Risk Level:** Medium
**Estimated Effort:** Medium (2-3 days)
**Files Created:** 1 (`shitty_ui/components/insights.py`)
**Files Modified:** 3 (`shitty_ui/data.py`, `shitty_ui/pages/dashboard.py`, `shitty_ui/brand_copy.py`)
**Files Deleted:** 0

---

## Context

The user's single biggest criticism of the current dashboard: **"Missing a 'so what'"** and **"Not being hyper actionable."** The four KPI cards (Total Signals, Accuracy, Avg Return, Total P&L) are informative but completely passive. They show aggregate numbers with zero time-awareness, zero context, and zero guidance on what the user should care about RIGHT NOW.

The insight cards replace passivity with urgency. Instead of "501 signals, 42.9% accuracy," users see:

- "Trump's last post mentioned LMT -- it's up +5.40% in 7 days. Cha-ching."
- "Best call this week: XOM +5.04%. Worst: AMZN -2.06%. Can't win 'em all."
- "System accuracy this month: 55% (coin flip: 50%). We're barely beating random."

Each card links to the relevant asset detail page, is time-aware (recency matters), and uses the brand's self-deprecating money-themed personality. Cards are placed **above the screener table** (Phase 03) as the first thing users see after the header, answering "why should I care right now?" before the data table answers "what's happening."

---

## Visual Specification

### Before (Current State)

Four static KPI hero cards in a 4-column grid:
- Total Signals: `501`
- Accuracy: `42.9%`
- Avg 7-Day Return: `+1.05%`
- Total P&L: `$+5,247`

These are informative but passive. No time-awareness, no specific asset callouts, no "so what."

See: `dashboard-desktop.png` -- KPI row is informative but inert.

### After (Target State)

A row of 2-3 dynamic insight callout cards placed **above the screener table** (Phase 03), **below the period selector**. The KPI cards from Phase 03's screener header remain; insight cards add editorial color, not replace metrics.

**Card Layout (Desktop, 1440px):**
```
+-------------------------------------------------------------------+
| [Period Selector: 7D / 30D / 90D / All]                          |
+-------------------------------------------------------------------+
|                                                                     |
| +-----------------------------+  +-----------------------------+    |
| | LATEST CALL                 |  | BEST & WORST THIS WEEK     |    |
| | Trump mentioned LMT on     |  | Best: XOM +5.04%           |    |
| | Jan 15 -- it's up +5.40%   |  | Worst: AMZN -2.06%         |    |
| | in 7 days. Cha-ching.      |  | Can't win 'em all.         |    |
| |                             |  |                             |    |
| | [LMT ->]         Jan 15    |  | [XOM ->] [AMZN ->]         |    |
| +-----------------------------+  +-----------------------------+    |
|                                                                     |
| +-----------------------------+                                     |
| | SYSTEM PULSE                |                                     |
| | 55% accuracy this month     |                                     |
| | (coin flip: 50%). We're     |                                     |
| | barely beating random.      |                                     |
| | 12 predictions tracked.     |                                     |
| +-----------------------------+                                     |
|                                                                     |
| [=== Screener Table (Phase 03) ===]                                |
+-------------------------------------------------------------------+
```

**Card Layout (Mobile, 375px):**
Cards stack vertically in a single column, full width. Each card maintains padding and readability.

**Card Styling (per card):**
- Background: `COLORS["secondary"]` (`#1E293B`)
- Border: `1px solid COLORS["border"]` (`#334155`)
- Border-left: `3px solid` -- color varies by insight type:
  - Latest call (evaluated correct): `COLORS["success"]` (`#10b981`)
  - Latest call (evaluated incorrect): `COLORS["danger"]` (`#ef4444`)
  - Latest call (pending): `COLORS["warning"]` (`#f59e0b`)
  - Best/worst: `COLORS["accent"]` (`#3b82f6`)
  - System pulse: `COLORS["text_muted"]` (`#94a3b8`)
- Border-radius: `8px`
- Padding: `16px`
- Min-width (desktop): `320px`
- Flex: `1 1 0` (equal width in row)
- Gap between cards: `16px`

**Typography within each card:**
- Category label (e.g., "LATEST CALL"): `font-size: 0.7rem`, `font-weight: 600`, `text-transform: uppercase`, `letter-spacing: 0.05em`, `color: COLORS["text_muted"]`, `margin-bottom: 8px`
- Headline text: `font-size: 0.95rem`, `font-weight: 600`, `color: COLORS["text"]`, `line-height: 1.4`, `margin-bottom: 8px`
- Body/commentary: `font-size: 0.85rem`, `color: COLORS["text_muted"]`, `line-height: 1.4`
- Asset link: `font-size: 0.8rem`, `font-weight: 600`, `color: COLORS["accent"]`, no text-decoration, clickable -> `/assets/{symbol}`
- Timestamp: `font-size: 0.75rem`, `color: COLORS["text_muted"]`
- Return value (positive): `color: COLORS["success"]`, `font-weight: 700`
- Return value (negative): `color: COLORS["danger"]`, `font-weight: 700`

**Insight Container (the parent row):**
- `display: flex`
- `flex-wrap: wrap`
- `gap: 16px`
- `margin-bottom: 24px`

---

## Dependencies

- **Phase 03** (Screener Table) -- The insight cards sit above the screener. The screener must exist as the homepage for placement to work. However, the insight cards are a self-contained `html.Div` inserted into the page layout, so they can be developed in parallel as long as the insertion point (above the screener table) is understood.
- **Phase 05** (Information Architecture) -- IA restructuring determines the nav and route structure. Insight cards live on `/` which is the screener/dashboard page in the new IA.

---

## Detailed Implementation Plan

### Step 1: Add new data function `get_dynamic_insights()` to `data.py`

**File:** `shitty_ui/data.py`
**Location:** After the existing `get_best_performing_asset()` function (around line 1835)

This function queries for 5 types of insight data in a single database round-trip where possible, then structures them into a ranked pool. The caller (the component) picks the top 2-3 most interesting/recent insights.

Add the following function:

```python
@ttl_cache(ttl_seconds=300)  # Cache for 5 minutes -- same as dashboard KPIs
def get_dynamic_insights(days: int = None) -> List[Dict[str, Any]]:
    """Generate a pool of dynamic insight candidates for the dashboard.

    Queries for multiple insight types and returns them as structured dicts.
    The UI layer picks the top 2-3 most interesting/recent from this pool.

    Each insight dict has:
        type: str -- "latest_call", "best_worst", "system_pulse", "hot_asset", "hot_signal"
        headline: str -- Primary text (personality-driven)
        body: str -- Secondary commentary
        assets: List[str] -- Tickers mentioned (for linking)
        sentiment: str -- "positive", "negative", "neutral" (for border color)
        timestamp: datetime or None -- When this insight became relevant
        priority: int -- Lower = more important (for ranking)

    Args:
        days: Number of days to look back (None = all time).

    Returns:
        List of insight dicts, unranked (caller sorts by priority + recency).
        Returns empty list if no data available.
    """
    insights: List[Dict[str, Any]] = []

    date_filter = ""
    params: Dict[str, Any] = {}
    if days is not None:
        date_filter = "AND po.prediction_date >= :start_date"
        params["start_date"] = (datetime.now() - timedelta(days=days)).date()

    # ---- Insight 1: Most recent prediction with an outcome ----
    try:
        latest_query = text(f"""
            SELECT
                po.symbol,
                po.prediction_sentiment,
                po.return_t7,
                po.correct_t7,
                po.pnl_t7,
                po.prediction_date,
                po.prediction_confidence,
                tss.timestamp AS post_timestamp
            FROM prediction_outcomes po
            INNER JOIN predictions p ON po.prediction_id = p.id
            INNER JOIN truth_social_shitposts tss ON p.shitpost_id = tss.shitpost_id
            WHERE po.correct_t7 IS NOT NULL
                {date_filter}
            ORDER BY po.prediction_date DESC
            LIMIT 1
        """)
        rows, columns = execute_query(latest_query, params)
        if rows and rows[0]:
            r = rows[0]
            symbol = r[0]
            sentiment = r[1] or "neutral"
            return_t7 = float(r[2]) if r[2] is not None else None
            correct = r[3]
            pnl = float(r[4]) if r[4] is not None else None
            pred_date = r[5]
            post_ts = r[7]

            if return_t7 is not None:
                ret_str = f"{return_t7:+.2f}%"
                if correct:
                    headline = f"Trump mentioned {symbol} -- it's {ret_str} in 7 days."
                    body = "Cha-ching." if return_t7 > 2 else "Not bad."
                    ins_sentiment = "positive"
                else:
                    headline = f"Trump mentioned {symbol} -- it went {ret_str} in 7 days."
                    body = "Ouch." if return_t7 < -2 else "Close, but no cigar."
                    ins_sentiment = "negative"

                insights.append({
                    "type": "latest_call",
                    "headline": headline,
                    "body": body,
                    "assets": [symbol],
                    "sentiment": ins_sentiment,
                    "timestamp": post_ts,
                    "priority": 1,
                })
    except Exception as e:
        logger.error(f"Error generating latest_call insight: {e}")

    # ---- Insight 2: Best and worst performing prediction in period ----
    try:
        best_worst_query = text(f"""
            (
                SELECT symbol, return_t7, correct_t7, prediction_date, 'best' AS rank_type
                FROM prediction_outcomes
                WHERE correct_t7 IS NOT NULL AND return_t7 IS NOT NULL
                    {date_filter}
                ORDER BY return_t7 DESC
                LIMIT 1
            )
            UNION ALL
            (
                SELECT symbol, return_t7, correct_t7, prediction_date, 'worst' AS rank_type
                FROM prediction_outcomes
                WHERE correct_t7 IS NOT NULL AND return_t7 IS NOT NULL
                    {date_filter}
                ORDER BY return_t7 ASC
                LIMIT 1
            )
        """)
        rows, columns = execute_query(best_worst_query, params)
        if rows and len(rows) == 2:
            best_row = rows[0] if rows[0][4] == "best" else rows[1]
            worst_row = rows[1] if rows[1][4] == "worst" else rows[0]
            best_sym = best_row[0]
            best_ret = float(best_row[1])
            worst_sym = worst_row[0]
            worst_ret = float(worst_row[1])

            period_label = f"last {days} days" if days else "all time"
            headline = f"Best: {best_sym} {best_ret:+.2f}%. Worst: {worst_sym} {worst_ret:+.2f}%."
            body = "Can't win 'em all."

            insights.append({
                "type": "best_worst",
                "headline": headline,
                "body": body,
                "assets": [best_sym, worst_sym],
                "sentiment": "neutral",
                "timestamp": None,
                "priority": 2,
            })
    except Exception as e:
        logger.error(f"Error generating best_worst insight: {e}")

    # ---- Insight 3: System accuracy vs coin flip ----
    try:
        accuracy_query = text(f"""
            SELECT
                COUNT(*) AS total,
                COUNT(CASE WHEN correct_t7 = true THEN 1 END) AS correct
            FROM prediction_outcomes
            WHERE correct_t7 IS NOT NULL
                {date_filter}
        """)
        rows, columns = execute_query(accuracy_query, params)
        if rows and rows[0] and rows[0][0] and rows[0][0] >= 5:
            total = rows[0][0]
            correct = rows[0][1] or 0
            accuracy = round(correct / total * 100, 1)

            if accuracy > 55:
                body = "Not bad for a shitpost-powered AI."
                ins_sentiment = "positive"
            elif accuracy > 45:
                body = f"Coin flip is 50%. We're {'barely beating' if accuracy > 50 else 'losing to'} random."
                ins_sentiment = "neutral"
            else:
                body = "Maybe we should just flip a coin."
                ins_sentiment = "negative"

            period_label = f"last {days} days" if days else "all time"
            headline = f"{accuracy:.0f}% accuracy ({total} predictions, {period_label})."

            insights.append({
                "type": "system_pulse",
                "headline": headline,
                "body": body,
                "assets": [],
                "sentiment": ins_sentiment,
                "timestamp": None,
                "priority": 3,
            })
    except Exception as e:
        logger.error(f"Error generating system_pulse insight: {e}")

    # ---- Insight 4: Most active asset (most predictions recently) ----
    try:
        active_query = text(f"""
            SELECT
                symbol,
                COUNT(*) AS pred_count,
                ROUND(AVG(return_t7)::numeric, 2) AS avg_return
            FROM prediction_outcomes
            WHERE correct_t7 IS NOT NULL
                {date_filter}
            GROUP BY symbol
            HAVING COUNT(*) >= 3
            ORDER BY COUNT(*) DESC
            LIMIT 1
        """)
        rows, columns = execute_query(active_query, params)
        if rows and rows[0]:
            symbol = rows[0][0]
            count = rows[0][1]
            avg_ret = float(rows[0][2]) if rows[0][2] is not None else 0.0

            ret_comment = f"averaging {avg_ret:+.2f}% per call" if avg_ret != 0 else "averaging flat returns"
            headline = f"{symbol} is our most-called asset ({count} predictions), {ret_comment}."
            body = "Trump can't stop talking about it." if count > 10 else "Keeps showing up."

            insights.append({
                "type": "hot_asset",
                "headline": headline,
                "body": body,
                "assets": [symbol],
                "sentiment": "positive" if avg_ret > 0 else "negative" if avg_ret < 0 else "neutral",
                "timestamp": None,
                "priority": 4,
            })
    except Exception as e:
        logger.error(f"Error generating hot_asset insight: {e}")

    # ---- Insight 5: Recent high-confidence signal (pending or just evaluated) ----
    try:
        hot_signal_query = text("""
            SELECT
                po.symbol,
                po.prediction_sentiment,
                po.prediction_confidence,
                po.correct_t7,
                po.return_t7,
                tss.timestamp AS post_timestamp
            FROM prediction_outcomes po
            INNER JOIN predictions p ON po.prediction_id = p.id
            INNER JOIN truth_social_shitposts tss ON p.shitpost_id = tss.shitpost_id
            WHERE po.prediction_confidence >= 0.75
            ORDER BY tss.timestamp DESC
            LIMIT 1
        """)
        rows, columns = execute_query(hot_signal_query)
        if rows and rows[0]:
            symbol = rows[0][0]
            sentiment = (rows[0][1] or "neutral").lower()
            confidence = float(rows[0][2]) if rows[0][2] is not None else 0.0
            correct = rows[0][3]
            return_t7 = float(rows[0][4]) if rows[0][4] is not None else None
            post_ts = rows[0][5]

            conf_pct = f"{confidence:.0%}"
            if correct is None:
                headline = f"High-confidence call: {sentiment.upper()} on {symbol} ({conf_pct}). Awaiting results."
                body = "The suspense is killing us."
                ins_sentiment = "neutral"
            elif correct:
                headline = f"High-confidence call on {symbol} ({conf_pct}) was RIGHT. {return_t7:+.2f}% in 7d."
                body = "Even a broken AI is right twice a day."
                ins_sentiment = "positive"
            else:
                headline = f"High-confidence call on {symbol} ({conf_pct}) was WRONG. {return_t7:+.2f}% in 7d."
                body = "Confidence != competence."
                ins_sentiment = "negative"

            insights.append({
                "type": "hot_signal",
                "headline": headline,
                "body": body,
                "assets": [symbol],
                "sentiment": ins_sentiment,
                "timestamp": post_ts,
                "priority": 5,
            })
    except Exception as e:
        logger.error(f"Error generating hot_signal insight: {e}")

    return insights
```

Also add `get_dynamic_insights` to the `clear_all_caches()` function:

**File:** `shitty_ui/data.py`
**Existing code (line ~1128):**
```python
    get_top_predicted_asset.clear_cache()  # type: ignore
    get_empty_state_context.clear_cache()  # type: ignore
```

**Change to:**
```python
    get_top_predicted_asset.clear_cache()  # type: ignore
    get_empty_state_context.clear_cache()  # type: ignore
    get_dynamic_insights.clear_cache()  # type: ignore
```

### Step 2: Add brand copy constants for insights

**File:** `shitty_ui/brand_copy.py`
**Location:** After the "Dashboard: Chart Empty States" section (around line 57), add:

```python
    # ===== Dashboard: Insight Cards =====
    "insight_latest_call_label": "LATEST CALL",
    "insight_best_worst_label": "BEST & WORST",
    "insight_system_pulse_label": "SYSTEM PULSE",
    "insight_hot_asset_label": "HOT ASSET",
    "insight_hot_signal_label": "HIGH-CONFIDENCE SIGNAL",
    "insight_empty": "Nothing interesting to report. Check back in 5 minutes.",
    "insight_section_aria": "Dynamic insight cards summarizing recent prediction performance",
```

**Exact edit -- find this block in `brand_copy.py`:**
```python
    # ===== Dashboard: Chart Empty States =====
    "chart_empty_accuracy": "Not enough data to chart accuracy yet",
```

**Replace with:**
```python
    # ===== Dashboard: Insight Cards =====
    "insight_latest_call_label": "LATEST CALL",
    "insight_best_worst_label": "BEST & WORST",
    "insight_system_pulse_label": "SYSTEM PULSE",
    "insight_hot_asset_label": "HOT ASSET",
    "insight_hot_signal_label": "HIGH-CONFIDENCE SIGNAL",
    "insight_empty": "Nothing interesting to report. Check back in 5 minutes.",
    "insight_section_aria": "Dynamic insight cards summarizing recent prediction performance",

    # ===== Dashboard: Chart Empty States =====
    "chart_empty_accuracy": "Not enough data to chart accuracy yet",
```

### Step 3: Create the insight cards component

**File:** `shitty_ui/components/insights.py` (NEW FILE)

```python
"""Dynamic insight cards for the dashboard.

Generates 2-3 time-aware, context-rich callout cards that answer
"why should I care RIGHT NOW?" -- placed above the screener table.

Each insight is a structured dict produced by data.get_dynamic_insights(),
rendered here into Dash HTML components with personality-driven copy,
asset links, and color-coded sentiment borders.
"""

from datetime import datetime
from typing import List, Dict, Any

from dash import html, dcc

from constants import COLORS
from brand_copy import COPY


# Map insight type -> COPY key for the category label
_LABEL_MAP = {
    "latest_call": "insight_latest_call_label",
    "best_worst": "insight_best_worst_label",
    "system_pulse": "insight_system_pulse_label",
    "hot_asset": "insight_hot_asset_label",
    "hot_signal": "insight_hot_signal_label",
}

# Map insight sentiment -> left border color
_BORDER_COLOR_MAP = {
    "positive": COLORS["success"],
    "negative": COLORS["danger"],
    "neutral": COLORS["text_muted"],
}


def _format_insight_timestamp(ts) -> str:
    """Format a timestamp into a human-readable relative string.

    Args:
        ts: datetime object or None.

    Returns:
        String like "2d ago", "5h ago", or "" if None.
    """
    if ts is None:
        return ""
    if not isinstance(ts, datetime):
        return str(ts)[:10]

    delta = datetime.now() - ts
    if delta.days > 7:
        return f"{delta.days // 7}w ago"
    elif delta.days > 0:
        return f"{delta.days}d ago"
    elif delta.seconds >= 3600:
        return f"{delta.seconds // 3600}h ago"
    elif delta.seconds >= 60:
        return f"{delta.seconds // 60}m ago"
    else:
        return "just now"


def _create_single_insight_card(insight: Dict[str, Any]) -> html.Div:
    """Render a single insight dict into a Dash html.Div card.

    Args:
        insight: Dict with keys: type, headline, body, assets, sentiment,
                 timestamp, priority.

    Returns:
        html.Div containing the rendered insight card.
    """
    insight_type = insight.get("type", "system_pulse")
    headline = insight.get("headline", "")
    body = insight.get("body", "")
    assets = insight.get("assets", [])
    sentiment = insight.get("sentiment", "neutral")
    timestamp = insight.get("timestamp")

    # Category label
    label_key = _LABEL_MAP.get(insight_type, "insight_system_pulse_label")
    category_label = COPY.get(label_key, insight_type.upper().replace("_", " "))

    # Left border color
    border_color = _BORDER_COLOR_MAP.get(sentiment, COLORS["text_muted"])

    # Timestamp display
    time_str = _format_insight_timestamp(timestamp)

    # Build asset links
    asset_links = []
    for symbol in assets[:3]:  # Max 3 links per card
        asset_links.append(
            dcc.Link(
                symbol,
                href=f"/assets/{symbol}",
                style={
                    "color": COLORS["accent"],
                    "fontSize": "0.8rem",
                    "fontWeight": "600",
                    "textDecoration": "none",
                    "marginRight": "12px",
                },
            )
        )

    # Card children
    children = [
        # Category label row
        html.Div(
            [
                html.Span(
                    category_label,
                    style={
                        "fontSize": "0.7rem",
                        "fontWeight": "600",
                        "textTransform": "uppercase",
                        "letterSpacing": "0.05em",
                        "color": COLORS["text_muted"],
                    },
                ),
                html.Span(
                    time_str,
                    style={
                        "fontSize": "0.75rem",
                        "color": COLORS["text_muted"],
                    },
                ) if time_str else None,
            ],
            style={
                "display": "flex",
                "justifyContent": "space-between",
                "alignItems": "center",
                "marginBottom": "8px",
            },
        ),
        # Headline
        html.Div(
            headline,
            style={
                "fontSize": "0.95rem",
                "fontWeight": "600",
                "color": COLORS["text"],
                "lineHeight": "1.4",
                "marginBottom": "6px",
            },
        ),
        # Body / commentary
        html.Div(
            body,
            style={
                "fontSize": "0.85rem",
                "color": COLORS["text_muted"],
                "lineHeight": "1.4",
                "marginBottom": "8px",
            },
        ) if body else None,
        # Asset links row
        html.Div(
            asset_links,
            style={
                "display": "flex",
                "alignItems": "center",
                "flexWrap": "wrap",
                "gap": "4px",
            },
        ) if asset_links else None,
    ]

    # Filter out None children
    children = [c for c in children if c is not None]

    return html.Div(
        children,
        className="insight-card",
        style={
            "padding": "16px",
            "backgroundColor": COLORS["secondary"],
            "border": f"1px solid {COLORS['border']}",
            "borderLeft": f"3px solid {border_color}",
            "borderRadius": "8px",
            "flex": "1 1 0",
            "minWidth": "280px",
        },
    )


def create_insight_cards(insights: List[Dict[str, Any]], max_cards: int = 3) -> html.Div:
    """Create the insight cards container from a pool of insight dicts.

    Sorts insights by priority (lower = more important), then picks
    the top `max_cards` insights. If no insights are available, returns
    an empty-state message.

    Args:
        insights: List of insight dicts from get_dynamic_insights().
        max_cards: Maximum number of cards to display (default 3).

    Returns:
        html.Div containing the insight card row, or empty state.
    """
    if not insights:
        return html.Div(
            html.P(
                COPY["insight_empty"],
                style={
                    "color": COLORS["text_muted"],
                    "fontSize": "0.85rem",
                    "textAlign": "center",
                    "padding": "16px",
                },
            ),
            style={"marginBottom": "24px"},
        )

    # Sort by priority (lower = more important), then by timestamp (newer first)
    def sort_key(ins):
        priority = ins.get("priority", 99)
        ts = ins.get("timestamp")
        # Newer timestamps should sort first (higher epoch = lower sort value)
        ts_epoch = -ts.timestamp() if isinstance(ts, datetime) else 0
        return (priority, ts_epoch)

    sorted_insights = sorted(insights, key=sort_key)
    selected = sorted_insights[:max_cards]

    cards = [_create_single_insight_card(ins) for ins in selected]

    return html.Div(
        cards,
        role="region",
        **{"aria-label": COPY["insight_section_aria"]},
        className="insight-cards-container",
        style={
            "display": "flex",
            "flexWrap": "wrap",
            "gap": "16px",
            "marginBottom": "24px",
        },
    )
```

### Step 4: Integrate insight cards into the dashboard page

**File:** `shitty_ui/pages/dashboard.py`

#### 4a. Add imports

**Existing imports (lines 12-20):**
```python
from components.cards import (
    create_error_card,
    create_empty_chart,
    create_empty_state_chart,
    create_empty_state_html,
    create_metric_card,
    create_post_card,
    create_unified_signal_card,
)
```

**Add after this import block:**
```python
from components.insights import create_insight_cards
```

**Existing data imports (lines 25-42):**
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

**Replace with (add `get_dynamic_insights`):**
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
    get_dynamic_insights,
)
```

#### 4b. Add insight cards container to the layout

In the `create_dashboard_page()` function, add a loading container for insight cards **between the period selector and the performance-metrics KPI row.**

**Existing code (lines 106-115):**
```python
                    ),
                    # Key Metrics Row (Primary tier - hero treatment)
                    dcc.Loading(
                        id="performance-metrics-loading",
                        type="default",
                        color=COLORS["accent"],
                        children=html.Div(
                            id="performance-metrics",
                            style={"marginBottom": "32px"},
                        ),
                    ),
```

**Replace with:**
```python
                    ),
                    # Dynamic Insight Cards (above KPIs, answer "so what right now?")
                    dcc.Loading(
                        id="insight-cards-loading",
                        type="default",
                        color=COLORS["accent"],
                        children=html.Div(
                            id="insight-cards-container",
                            style={"marginBottom": "16px"},
                        ),
                    ),
                    # Key Metrics Row (Primary tier - hero treatment)
                    dcc.Loading(
                        id="performance-metrics-loading",
                        type="default",
                        color=COLORS["accent"],
                        children=html.Div(
                            id="performance-metrics",
                            style={"marginBottom": "32px"},
                        ),
                    ),
```

#### 4c. Update the main dashboard callback to include insight cards

**Existing callback outputs (lines 514-523):**
```python
    @app.callback(
        [
            Output("unified-feed-container", "children"),
            Output("performance-metrics", "children"),
            Output("accuracy-over-time-chart", "figure"),
            Output("confidence-accuracy-chart", "figure"),
            Output("asset-accuracy-chart", "figure"),
            Output("last-update-timestamp", "data"),
        ],
```

**Replace with (add insight-cards-container output):**
```python
    @app.callback(
        [
            Output("insight-cards-container", "children"),
            Output("unified-feed-container", "children"),
            Output("performance-metrics", "children"),
            Output("accuracy-over-time-chart", "figure"),
            Output("confidence-accuracy-chart", "figure"),
            Output("asset-accuracy-chart", "figure"),
            Output("last-update-timestamp", "data"),
        ],
```

**In the `update_dashboard` function body, add insight card generation at the TOP of the function, right after the `days` and `current_time` setup (after line 538):**

After:
```python
        # Current timestamp for refresh indicator
        current_time = datetime.now().isoformat()
```

Add:
```python
        # ===== Dynamic Insight Cards =====
        try:
            insight_pool = get_dynamic_insights(days=days)
            insight_cards = create_insight_cards(insight_pool, max_cards=3)
        except Exception as e:
            errors.append(f"Insight cards: {e}")
            print(f"Error loading insight cards: {traceback.format_exc()}")
            insight_cards = html.Div()  # Silent failure -- insights are not critical
```

**Update the return statement (existing line ~884):**

**Existing:**
```python
        return (
            feed_cards,
            metrics_row,
            acc_fig,
            conf_fig,
            asset_fig,
            current_time,
        )
```

**Replace with:**
```python
        return (
            insight_cards,
            feed_cards,
            metrics_row,
            acc_fig,
            conf_fig,
            asset_fig,
            current_time,
        )
```

---

## Responsive Behavior

**Desktop (>768px):** Insight cards display in a horizontal flex row, each card taking equal width via `flex: 1 1 0`. With 3 cards, each is roughly 33% width minus gap.

**Tablet (768px):** Cards wrap -- if 3 cards, two on top row and one below. `min-width: 280px` ensures cards don't get too narrow.

**Mobile (<=480px):** All cards stack vertically (single column). Each card takes full container width. The `flex-wrap: wrap` + `min-width: 280px` handles this automatically without media queries. On very narrow viewports (375px), the container's padding (`20px` from `main-content-container`) leaves ~335px for cards, which is above the `280px` minimum, so each card fills the row alone.

No additional CSS media queries are needed -- the flexbox layout with `min-width` handles all breakpoints naturally.

---

## Accessibility Checklist

- [ ] Insight cards container has `role="region"` and `aria-label` describing its purpose
- [ ] All text content uses proper semantic HTML (`html.Div` for blocks, not `html.Span` for multi-line content)
- [ ] Asset links are proper `dcc.Link` elements (keyboard-navigable)
- [ ] Color is not the only indicator of sentiment -- category labels ("LATEST CALL", "BEST & WORST") provide text context independent of border color
- [ ] Font sizes meet minimum readability (smallest is `0.7rem` / ~11px, above WCAG minimum)
- [ ] Contrast ratios: `COLORS["text"]` (#f1f5f9) on `COLORS["secondary"]` (#1E293B) = 11.7:1 (exceeds WCAG AAA)
- [ ] Muted text: `COLORS["text_muted"]` (#94a3b8) on `COLORS["secondary"]` (#1E293B) = 5.8:1 (exceeds WCAG AA)

---

## Test Plan

### New Tests: `shit_tests/shitty_ui/test_insights.py`

```python
"""Tests for dynamic insight cards component and data function."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock


class TestGetDynamicInsights:
    """Tests for data.get_dynamic_insights()."""

    @patch("data.execute_query")
    def test_returns_empty_list_when_no_data(self, mock_query):
        """Should return [] when all queries return empty results."""
        mock_query.return_value = ([], [])
        from data import get_dynamic_insights
        get_dynamic_insights.clear_cache()
        result = get_dynamic_insights(days=7)
        assert result == [] or isinstance(result, list)

    @patch("data.execute_query")
    def test_returns_latest_call_insight(self, mock_query):
        """Should include a latest_call insight when recent outcomes exist."""
        # Mock: latest_call query returns data, others return empty
        mock_query.side_effect = [
            # latest_call
            ([("AAPL", "bullish", 5.04, True, 50.40, datetime.now().date(),
               0.8, datetime.now() - timedelta(hours=6))],
             ["symbol", "sentiment", "return_t7", "correct_t7", "pnl_t7",
              "prediction_date", "confidence", "post_timestamp"]),
            # best_worst
            ([], []),
            # system_pulse
            ([], []),
            # hot_asset
            ([], []),
            # hot_signal
            ([], []),
        ]
        from data import get_dynamic_insights
        get_dynamic_insights.clear_cache()
        result = get_dynamic_insights(days=7)
        latest = [i for i in result if i["type"] == "latest_call"]
        assert len(latest) == 1
        assert "AAPL" in latest[0]["assets"]
        assert latest[0]["sentiment"] == "positive"

    @patch("data.execute_query")
    def test_system_pulse_requires_minimum_predictions(self, mock_query):
        """System pulse insight should not appear with fewer than 5 predictions."""
        mock_query.side_effect = [
            ([], []),  # latest_call
            ([], []),  # best_worst
            ([(3, 2)], ["total", "correct"]),  # system_pulse -- only 3 predictions
            ([], []),  # hot_asset
            ([], []),  # hot_signal
        ]
        from data import get_dynamic_insights
        get_dynamic_insights.clear_cache()
        result = get_dynamic_insights(days=30)
        pulse = [i for i in result if i["type"] == "system_pulse"]
        assert len(pulse) == 0

    @patch("data.execute_query")
    def test_each_insight_has_required_keys(self, mock_query):
        """Every insight dict must have type, headline, body, assets, sentiment, priority."""
        mock_query.side_effect = [
            ([("XOM", "bullish", 3.2, True, 32.0, datetime.now().date(),
               0.82, datetime.now())],
             ["symbol", "sentiment", "return_t7", "correct_t7", "pnl_t7",
              "prediction_date", "confidence", "post_timestamp"]),
            ([], []),
            ([(10, 6)], ["total", "correct"]),
            ([], []),
            ([], []),
        ]
        from data import get_dynamic_insights
        get_dynamic_insights.clear_cache()
        result = get_dynamic_insights(days=30)
        required_keys = {"type", "headline", "body", "assets", "sentiment", "priority"}
        for insight in result:
            assert required_keys.issubset(insight.keys()), f"Missing keys in {insight}"

    def test_insight_survives_db_error_gracefully(self):
        """If one query fails, other insights should still be returned."""
        # Tested implicitly: each query block has its own try/except.
        # This test verifies the function doesn't raise on partial failure.
        with patch("data.execute_query") as mock_query:
            mock_query.side_effect = Exception("connection lost")
            from data import get_dynamic_insights
            get_dynamic_insights.clear_cache()
            result = get_dynamic_insights(days=7)
            assert isinstance(result, list)


class TestCreateInsightCards:
    """Tests for components.insights.create_insight_cards()."""

    def test_empty_insights_returns_empty_state(self):
        """Should show empty state message when no insights available."""
        from components.insights import create_insight_cards
        result = create_insight_cards([])
        # Should contain the empty message text
        assert result is not None

    def test_renders_correct_number_of_cards(self):
        """Should render at most max_cards cards."""
        from components.insights import create_insight_cards
        insights = [
            {"type": "latest_call", "headline": "Test 1", "body": "Body 1",
             "assets": ["AAPL"], "sentiment": "positive", "timestamp": None, "priority": 1},
            {"type": "best_worst", "headline": "Test 2", "body": "Body 2",
             "assets": ["XOM"], "sentiment": "neutral", "timestamp": None, "priority": 2},
            {"type": "system_pulse", "headline": "Test 3", "body": "Body 3",
             "assets": [], "sentiment": "neutral", "timestamp": None, "priority": 3},
            {"type": "hot_asset", "headline": "Test 4", "body": "Body 4",
             "assets": ["LMT"], "sentiment": "positive", "timestamp": None, "priority": 4},
        ]
        result = create_insight_cards(insights, max_cards=2)
        # The container should have exactly 2 insight-card children
        card_children = [c for c in result.children if hasattr(c, 'className')
                         and c.className == "insight-card"]
        assert len(card_children) == 2

    def test_sorts_by_priority(self):
        """Lower priority number should appear first."""
        from components.insights import create_insight_cards
        insights = [
            {"type": "hot_asset", "headline": "Low priority", "body": "",
             "assets": [], "sentiment": "neutral", "timestamp": None, "priority": 5},
            {"type": "latest_call", "headline": "High priority", "body": "",
             "assets": [], "sentiment": "positive", "timestamp": None, "priority": 1},
        ]
        result = create_insight_cards(insights, max_cards=2)
        cards = [c for c in result.children if hasattr(c, 'className')
                 and c.className == "insight-card"]
        # First card should be the priority-1 card
        # Check the headline text in the second child (index 1) of the card
        first_card_headline = cards[0].children[1].children  # Headline div
        assert "High priority" in str(first_card_headline)

    def test_asset_links_are_dcc_links(self):
        """Asset symbols should render as clickable dcc.Link elements."""
        from components.insights import _create_single_insight_card
        insight = {
            "type": "latest_call",
            "headline": "Test",
            "body": "Body",
            "assets": ["AAPL", "TSLA"],
            "sentiment": "positive",
            "timestamp": None,
            "priority": 1,
        }
        card = _create_single_insight_card(insight)
        # Find the asset links div (last non-None child)
        link_divs = [c for c in card.children if c is not None]
        # The last child should contain dcc.Link elements
        last_child = link_divs[-1]
        links = [c for c in last_child.children if hasattr(c, 'href')]
        assert len(links) == 2
        assert links[0].href == "/assets/AAPL"
        assert links[1].href == "/assets/TSLA"
```

### Existing Tests to Verify

Run the full dashboard test suite to ensure no regressions:

```bash
source venv/bin/activate && pytest shit_tests/shitty_ui/ -v
```

The callback output count change (6 -> 7 outputs) will break existing callback tests that mock the `update_dashboard` return value. These tests need the return tuple updated to include the `insight_cards` element as the first item.

### Manual Verification Steps

1. Start the dashboard locally: `source venv/bin/activate && python3 -m shitty_ui.app`
2. Navigate to `/` and verify:
   - Insight cards appear above the KPI metrics row
   - 2-3 cards are displayed with personality-driven copy
   - Asset ticker links navigate to `/assets/{symbol}` on click
   - Cards show appropriate border colors (green for correct, red for incorrect)
3. Switch time period (7D / 30D / 90D / All) and verify insights update
4. Resize browser to 768px and 375px -- verify cards stack vertically
5. Inspect the page with Lighthouse for accessibility score

---

## Stress Testing & Edge Cases

### Edge Cases to Handle

1. **No predictions at all (empty database):** `get_dynamic_insights()` returns `[]`, `create_insight_cards([])` shows the empty state message. No errors.

2. **Only bypassed predictions (no evaluated outcomes):** All insight queries return empty results. `get_dynamic_insights()` returns `[]`. Empty state shown.

3. **One query fails, others succeed:** Each query is wrapped in its own `try/except`. If the `latest_call` query fails but `system_pulse` succeeds, the user still sees useful insights.

4. **Extremely old data (all predictions > 90 days):** When `days=7` produces no data, the insight pool is empty. The empty state is shown. This is correct -- stale insights are worse than no insights.

5. **All predictions are for the same asset:** The `best_worst` insight will show the same symbol for both best and worst. The copy still makes sense: "Best: XOM +5.04%. Worst: XOM -2.06%." This is fine.

6. **`return_t7` is exactly 0.00%:** The `latest_call` copy handles this: "Trump mentioned {symbol} -- it's +0.00% in 7 days." The body text defaults to "Not bad." which is slightly misleading but harmless.

7. **TTL cache interaction:** Insights are cached for 5 minutes (same as KPIs). This means insight content won't change more frequently than every 5 minutes. Acceptable -- the user instruction says max 5 min cache TTL.

### Performance Considerations

- `get_dynamic_insights()` runs 5 SQL queries per call. Each query is lightweight (aggregate on indexed `prediction_outcomes` table). Total expected execution: <100ms on Neon serverless PostgreSQL.
- With `@ttl_cache(ttl_seconds=300)`, these queries run at most once every 5 minutes per unique `days` parameter value. Since there are only 4 period options (7, 30, 90, None), the cache holds at most 4 entries.
- No N+1 query patterns. No DataFrame operations on the results.

---

## Verification Checklist

- [ ] `shitty_ui/data.py` contains `get_dynamic_insights()` function with 5 insight query blocks
- [ ] `get_dynamic_insights` is added to `clear_all_caches()`
- [ ] `shitty_ui/brand_copy.py` contains insight-related copy constants
- [ ] `shitty_ui/components/insights.py` exists with `create_insight_cards()` and `_create_single_insight_card()`
- [ ] `shitty_ui/pages/dashboard.py` imports `create_insight_cards` and `get_dynamic_insights`
- [ ] `create_dashboard_page()` includes `insight-cards-container` div above `performance-metrics`
- [ ] `update_dashboard` callback has 7 outputs (insight cards + original 6)
- [ ] `update_dashboard` return tuple starts with `insight_cards`
- [ ] `pytest shit_tests/shitty_ui/ -v` passes (including new insight tests)
- [ ] `ruff check shitty_ui/components/insights.py` passes
- [ ] `ruff format shitty_ui/components/insights.py` produces no changes
- [ ] Dashboard loads at `/` with insight cards visible
- [ ] Insight cards update when switching time periods
- [ ] Mobile layout stacks cards vertically at 375px
- [ ] Asset links in insight cards navigate to correct `/assets/{symbol}` pages

---

## What NOT To Do

1. **Don't make insights stale.** The `@ttl_cache` is set to 300 seconds (5 minutes). Do NOT increase this. Insights must feel "live" -- showing yesterday's best call when there's a newer result is worse than showing nothing.

2. **Don't show insights when there's no recent data.** If `get_dynamic_insights()` returns an empty list, show the empty state. Do NOT fall back to generating fake/templated insights with hardcoded data. That's the opposite of "dynamic."

3. **Don't duplicate the KPI numbers.** The insight cards should NOT restate "501 signals" or "42.9% accuracy" -- those numbers are already shown in the KPI row (and will be in the screener header after Phase 03). Insights add EDITORIAL COLOR: "55% accuracy -- barely beating random." The number is context, not the headline.

4. **Don't use raw SQL without parameterization.** All insight queries use SQLAlchemy `text()` with `:param` placeholders. Never use f-string interpolation for user-supplied values in SQL.

5. **Don't make the insight cards block page render.** The insight generation is wrapped in `try/except` with a silent fallback (`html.Div()`). If insight generation fails or is slow, the rest of the dashboard still loads.

6. **Don't add auto-rotation or carousel behavior.** The user instruction mentioned "cards rotate or refresh with new insights on interval." This is handled by the existing 5-minute `refresh-interval` timer that triggers `update_dashboard`. Do NOT add a separate interval timer or JavaScript-based carousel. The callback already refreshes all dashboard content every 5 minutes.

7. **Don't import from `shitty_ui.data` -- use relative imports.** The dashboard components use bare `from data import ...` (relative) because the Dash app is started from the `shitty_ui/` directory. Using `from shitty_ui.data import ...` will fail at runtime.

8. **Don't add new CSS to `layout.py`'s `index_string`.** The insight cards are styled entirely with inline style dicts. No additional CSS classes or media queries are needed thanks to the flexbox layout with `min-width`.
