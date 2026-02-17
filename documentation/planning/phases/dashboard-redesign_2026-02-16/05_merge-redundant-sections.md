# Phase 05: Merge Redundant Sections

**Status**: ✅ COMPLETE
**Started**: 2026-02-17
**Completed**: 2026-02-17

**PR Title**: refactor: unified prediction feed replacing dual columns
**Risk Level**: Medium
**Estimated Effort**: Medium (3-4 hours)
**Dependencies**: Phase 01 (data visibility), Phase 04 (expandable thesis)
**Unlocks**: Phase 06 (Inline Sparklines), Phase 08 (Visual Hierarchy), Phase 10 (Brand Identity)

## Files Modified

| File | Action |
|------|--------|
| `shitty_ui/data.py` | Add `get_unified_feed()` combining active+recent signal logic; deprecate call sites |
| `shitty_ui/pages/dashboard.py` | Replace hero section + recent signals column with single unified feed; remove `recent-signals-list` output; update callback outputs |
| `shitty_ui/components/cards.py` | Add `create_unified_signal_card()` merging hero and signal card designs; keep old functions for /signals page |
| `shitty_ui/layout.py` | Remove `create_signal_card` from re-exports (unused after refactor); remove hero CSS hover rule if unused |
| `shit_tests/shitty_ui/test_data.py` | Add `TestGetUnifiedFeed` class; update tests referencing removed callback outputs |
| `shit_tests/shitty_ui/test_cards.py` | Add `TestCreateUnifiedSignalCard` class |
| `shit_tests/shitty_ui/test_layout.py` | Update `test_dashboard_contains_recent_signals` and `test_dashboard_preserves_hero_signals_section` to check for new `unified-feed-container` ID |
| `CHANGELOG.md` | Add entry |

## Context

The dashboard currently shows predictions in **three redundant places**:

1. **Hero Signals** (`hero-signals-section`, lines 102-107 in `dashboard.py` layout; lines 554-629 in callback) -- Top of dashboard, shows up to 5 high-confidence signals from the last 72 hours using `get_active_signals(min_confidence=0.75, hours=72)`. Renders via `create_hero_signal_card()` (cards.py lines 170-341). These cards are displayed in a horizontal flex row.

2. **Recent Predictions** (`recent-signals-list`, lines 238-278 in `dashboard.py` layout; lines 844-865 in callback) -- Right column of a two-column layout alongside "Latest Posts". Shows the last 10 predictions using `get_recent_signals(limit=10, days=days)`. Renders via `create_signal_card()` (cards.py lines 392-535). These cards are displayed in a scrollable vertical list.

3. **/signals page** (signals.py) -- Separate page with full filtering, pagination, and CSV export using `get_signal_feed()`. Renders via `create_feed_signal_card()` (cards.py lines 1206-1508).

**The problem**: Hero and Recent show essentially the same data in different formats. Hero signals are a subset of recent signals (high confidence, recent). Users see the same predictions twice when scrolling. The two-column layout (Posts | Recent Predictions) wastes horizontal space because the "Recent Predictions" column only shows 5-column-width of compact cards while the "Latest Posts" column is 7-columns wide.

**Screenshots**: See `/tmp/design-review/dashboard-desktop.png` -- hero signals at top, then identical predictions appear again in the "Recent Predictions" sidebar.

**The solution**: Replace both sections with a single **Unified Prediction Feed** that:
- Uses the full page width (no more two-column split)
- Combines the hero card's rich layout (aggregated outcomes, time-ago, sentiment badges) with the signal card's compact vertical format
- Displays up to 15 predictions sorted by a smart ranking: evaluated outcomes first, then by timestamp
- Integrates the expandable thesis from Phase 04 naturally
- Pushes "Latest Posts" into its own full-width section below

---

## Detailed Implementation

### Change A: New Unified Feed Data Function

#### Step A1: Add `get_unified_feed()` to data.py

**File**: `shitty_ui/data.py`
**Location**: After `get_active_signals()` (after line 1449)

This function merges the queries behind `get_active_signals()` and `get_recent_signals()` into one. It uses the same deduplicated, aggregated query from `get_active_signals()` but relaxes the time/confidence constraints and adds the smart sort order (evaluated first, then by timestamp).

```python
def get_unified_feed(
    limit: int = 15,
    days: int | None = 90,
    min_confidence: float = 0.5,
) -> pd.DataFrame:
    """
    Get a unified prediction feed for the dashboard, replacing both hero and recent sections.

    Combines the deduplication logic of get_active_signals() (one row per post,
    aggregated outcomes) with the time-period filtering of get_recent_signals().

    Sort order: evaluated predictions first (correct/incorrect), then pending,
    within each group ordered by timestamp descending.

    Args:
        limit: Maximum number of predictions to return.
        days: Number of days to look back (None = all time).
        min_confidence: Minimum confidence threshold.

    Returns:
        DataFrame with one row per unique post, with aggregated outcome data.
    """
    date_filter = ""
    params: Dict[str, Any] = {
        "limit": limit,
        "min_confidence": min_confidence,
    }

    if days is not None:
        date_filter = "AND tss.timestamp >= :start_date"
        params["start_date"] = datetime.now() - timedelta(days=days)

    query = text(f"""
        SELECT
            tss.timestamp,
            tss.text,
            tss.shitpost_id,
            p.id as prediction_id,
            p.assets,
            p.market_impact,
            p.confidence,
            p.thesis,
            p.analysis_status,
            COUNT(po.id) AS outcome_count,
            COUNT(CASE WHEN po.correct_t7 = true THEN 1 END) AS correct_count,
            COUNT(CASE WHEN po.correct_t7 = false THEN 1 END) AS incorrect_count,
            AVG(po.return_t7) AS avg_return_t7,
            SUM(po.pnl_t7) AS total_pnl_t7,
            BOOL_AND(po.is_complete) AS is_complete
        FROM truth_social_shitposts tss
        INNER JOIN predictions p ON tss.shitpost_id = p.shitpost_id
        LEFT JOIN prediction_outcomes po ON p.id = po.prediction_id
        WHERE p.analysis_status = 'completed'
            AND p.confidence IS NOT NULL
            AND p.confidence >= :min_confidence
            AND p.assets IS NOT NULL
            AND p.assets::jsonb <> '[]'::jsonb
            {date_filter}
        GROUP BY tss.timestamp, tss.text, tss.shitpost_id,
                 p.id, p.assets, p.market_impact, p.confidence,
                 p.thesis, p.analysis_status
        ORDER BY
            CASE
                WHEN COUNT(CASE WHEN po.correct_t7 IS NOT NULL THEN 1 END) > 0
                THEN 0
                ELSE 1
            END,
            tss.timestamp DESC
        LIMIT :limit
    """)

    try:
        rows, columns = execute_query(query, params)
        df = pd.DataFrame(rows, columns=columns)
        return df
    except Exception as e:
        logger.error(f"Error loading unified feed: {e}")
        return pd.DataFrame()
```

**Key design decisions**:
- Reuses the `GROUP BY` deduplication from `get_active_signals()` so multi-ticker posts produce one card
- Adds the evaluated-first sort order from Phase 01's `get_signal_feed()` changes (the `CASE WHEN` in ORDER BY)
- Accepts `days` parameter like `get_recent_signals()` to respect the time period selector
- Default `min_confidence=0.5` is the same as `get_recent_signals()`
- Includes `analysis_status` and `thesis` for Phase 04's expandable cards
- Returns aggregated outcome columns (`outcome_count`, `correct_count`, `incorrect_count`, `total_pnl_t7`) like `get_active_signals()`

#### Step A2: Do NOT remove `get_active_signals()` or `get_recent_signals()`

Both functions remain in `data.py` unchanged. They are still actively used:
- `get_active_signals()`: wrapped by `get_active_signals_with_fallback()` (line 1479)
- `get_recent_signals()`: re-exported from `layout.py` line 49

No docstring changes needed — these are not deprecated, just no longer called from the dashboard callback.

---

### Change B: New Unified Signal Card Component

#### Step B1: Add `create_unified_signal_card()` to cards.py

**File**: `shitty_ui/components/cards.py`
**Location**: After `create_signal_card()` (after line 535)

This card merges the best of `create_hero_signal_card()` (aggregated outcomes, total P&L) and `create_signal_card()` (compact vertical layout, weeks-ago format). It is designed to work with the DataFrame rows returned by `get_unified_feed()`.

```python
def create_unified_signal_card(row) -> html.Div:
    """Create a card for the unified prediction feed on the dashboard.

    Combines the aggregated outcome logic from hero cards with the compact
    vertical layout of signal cards. Designed for the unified feed that
    replaces both the hero section and the recent predictions sidebar.

    Args:
        row: Dict-like object with columns from get_unified_feed().

    Returns:
        html.Div containing the rendered card.
    """
    timestamp = row.get("timestamp")
    text_content = row.get("text", "")
    text_content = strip_urls(text_content)
    preview = text_content[:200] + "..." if len(text_content) > 200 else text_content
    confidence = row.get("confidence", 0)
    assets = row.get("assets", [])
    market_impact = row.get("market_impact", {})
    thesis = row.get("thesis", "")

    # Aggregated outcome data (from GROUP BY query)
    outcome_count = row.get("outcome_count", 0) or 0
    correct_count = row.get("correct_count", 0) or 0
    incorrect_count = row.get("incorrect_count", 0) or 0
    total_pnl_t7 = row.get("total_pnl_t7")

    # Derive overall correctness from aggregated counts
    if outcome_count > 0 and correct_count + incorrect_count > 0:
        correct_t7 = correct_count > incorrect_count
    else:
        correct_t7 = None  # Pending

    # Determine sentiment
    sentiment = "neutral"
    if isinstance(market_impact, dict) and market_impact:
        first_sentiment = list(market_impact.values())[0]
        if isinstance(first_sentiment, str):
            sentiment = first_sentiment.lower()

    # Format time ago (supports weeks for older posts)
    if isinstance(timestamp, datetime):
        delta = datetime.now() - timestamp
        if delta.days > 7:
            time_ago = f"{delta.days // 7}w ago"
        elif delta.days > 0:
            time_ago = f"{delta.days}d ago"
        elif delta.seconds >= 3600:
            time_ago = f"{delta.seconds // 3600}h ago"
        else:
            time_ago = f"{max(1, delta.seconds // 60)}m ago"
    else:
        time_ago = str(timestamp)[:16] if timestamp else ""

    # Asset string
    asset_str = ", ".join(assets[:4]) if isinstance(assets, list) else str(assets)
    if isinstance(assets, list) and len(assets) > 4:
        asset_str += f" +{len(assets) - 4}"

    # Sentiment styling
    s_style = get_sentiment_style(sentiment)
    s_color = s_style["color"]
    s_bg = s_style["bg_color"]
    s_icon = s_style["icon"]

    # Outcome badge -- uses aggregated P&L
    pnl_display = total_pnl_t7
    if correct_t7 is True:
        outcome_badge = html.Span(
            [
                html.I(className="fas fa-check me-1"),
                f"+${pnl_display:,.0f}" if pnl_display else "Correct",
            ],
            style={
                "color": COLORS["success"],
                "fontWeight": "600",
                "fontSize": "0.8rem",
            },
        )
    elif correct_t7 is False:
        outcome_badge = html.Span(
            [
                html.I(className="fas fa-times me-1"),
                f"${pnl_display:,.0f}" if pnl_display else "Incorrect",
            ],
            style={
                "color": COLORS["danger"],
                "fontWeight": "600",
                "fontSize": "0.8rem",
            },
        )
    else:
        outcome_badge = html.Span(
            [html.I(className="fas fa-clock me-1"), "Pending"],
            style={
                "color": COLORS["warning"],
                "fontWeight": "600",
                "fontSize": "0.8rem",
            },
        )

    # Build card children
    children = [
        # Row 1: time ago + outcome badge
        html.Div(
            [
                html.Span(
                    time_ago,
                    style={"color": COLORS["text_muted"], "fontSize": "0.75rem"},
                ),
                outcome_badge,
            ],
            style={
                "display": "flex",
                "justifyContent": "space-between",
                "alignItems": "center",
                "marginBottom": "8px",
            },
        ),
        # Row 2: Post preview
        html.P(
            preview,
            style={
                "fontSize": "0.85rem",
                "margin": "0 0 10px 0",
                "lineHeight": "1.5",
                "color": COLORS["text"],
            },
        ),
        # Row 3: sentiment badge + assets + confidence
        html.Div(
            [
                html.Span(
                    [
                        html.I(className=f"fas fa-{s_icon} me-1"),
                        sentiment.upper(),
                    ],
                    className="sentiment-badge",
                    style={
                        "backgroundColor": s_bg,
                        "color": s_color,
                    },
                ),
                html.Span(
                    asset_str,
                    style={
                        "color": COLORS["accent"],
                        "fontSize": "0.8rem",
                        "fontWeight": "600",
                    },
                ),
                html.Span(
                    f"{confidence:.0%}",
                    style={
                        "color": COLORS["text_muted"],
                        "fontSize": "0.8rem",
                    },
                ),
            ],
            style={
                "display": "flex",
                "alignItems": "center",
                "gap": "12px",
                "flexWrap": "wrap",
            },
        ),
    ]

    # Row 4: Thesis preview (truncated -- Phase 04 adds expand)
    if thesis:
        children.append(
            html.P(
                thesis[:150] + "..." if len(thesis) > 150 else thesis,
                style={
                    "fontSize": "0.8rem",
                    "color": COLORS["text_muted"],
                    "margin": "8px 0 0 0",
                    "fontStyle": "italic",
                    "lineHeight": "1.4",
                },
            )
        )

    return html.Div(
        children,
        className="unified-signal-card",
        style={
            "padding": "16px",
            "backgroundColor": COLORS["secondary"],
            "border": f"1px solid {COLORS['border']}",
            "borderLeft": f"3px solid {s_color}",
            "borderRadius": "8px",
            "marginBottom": "12px",
        },
    )
```

**Key design decisions**:
- Uses `className="unified-signal-card"` (not `hero-signal-card` or `signal-card`) so existing CSS hover effects remain isolated
- Includes thesis preview (row 4) so Phase 04's expandable thesis can hook into this card
- Uses weeks-ago format (`5w ago`) for older posts, matching `create_signal_card()` behavior
- Shows aggregated P&L from `total_pnl_t7`, matching `create_hero_signal_card()` behavior
- Vertical stacked layout (not horizontal flex) so cards can use full page width

#### Step B2: Add unified card CSS hover effect

**File**: `shitty_ui/layout.py`
**Location**: After the `.hero-signal-card:hover` block (around line 106 in the index_string CSS)

```css
/* Unified signal card hover effect */
.unified-signal-card {
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.unified-signal-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 20px rgba(59, 130, 246, 0.15);
}
```

---

### Change C: Replace Dashboard Layout (Two Sections Become One)

#### Step C1: Remove hero section and replace two-column layout

**File**: `shitty_ui/pages/dashboard.py`
**Location**: Lines 102-281 (from `# Hero Section` through the end of the two-column `dbc.Row`)

Replace these ~180 lines with a single unified feed section. The new layout structure is:

```
[Time Period Selector]       (unchanged)
[KPI Metrics Row]            (unchanged, moved up)
[Analytics Tabs]             (unchanged)
[Unified Prediction Feed]    (NEW - replaces hero + recent)
[Latest Posts]               (moved from left column to full-width)
[Collapsible Data Table]     (unchanged)
[Footer]                     (unchanged)
```

**Replace** the entire block from line 102 (`# Hero Section: Active High-Confidence Signals`) through line 281 (end of two-column `dbc.Row`) with:

```python
                    # ========== Unified Prediction Feed ==========
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                [
                                    html.I(className="fas fa-bolt me-2"),
                                    "Predictions",
                                    html.Small(
                                        " - LLM signals with tracked outcomes",
                                        style={
                                            "color": COLORS["text_muted"],
                                            "fontWeight": "normal",
                                        },
                                    ),
                                ],
                                className="fw-bold",
                                style={"backgroundColor": COLORS["secondary"]},
                            ),
                            dbc.CardBody(
                                [
                                    dcc.Loading(
                                        type="circle",
                                        color=COLORS["accent"],
                                        children=html.Div(
                                            id="unified-feed-container",
                                            style={
                                                "maxHeight": "700px",
                                                "overflowY": "auto",
                                            },
                                        ),
                                    )
                                ],
                                style={"backgroundColor": COLORS["secondary"]},
                            ),
                        ],
                        className="mb-4",
                        style={"backgroundColor": COLORS["secondary"]},
                    ),
                    # ========== Latest Posts (full width) ==========
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                [
                                    html.I(className="fas fa-rss me-2"),
                                    "Latest Posts",
                                    html.Small(
                                        " - Trump's posts with LLM analysis",
                                        style={
                                            "color": COLORS["text_muted"],
                                            "fontWeight": "normal",
                                        },
                                    ),
                                ],
                                className="fw-bold",
                            ),
                            dbc.CardBody(
                                [
                                    dcc.Loading(
                                        type="circle",
                                        color=COLORS["accent"],
                                        children=html.Div(
                                            id="post-feed-container",
                                            style={
                                                "maxHeight": "600px",
                                                "overflowY": "auto",
                                            },
                                        ),
                                    )
                                ]
                            ),
                        ],
                        className="mb-4",
                        style={"backgroundColor": COLORS["secondary"]},
                    ),
```

**What was removed**:
- `html.Div(id="hero-signals-section")` (line 106) -- hero section container
- The entire two-column `dbc.Row` (lines 186-281) containing "Latest Posts" (left, 7-col) and "Recent Predictions" (right, 5-col)
- `html.Div(id="recent-signals-list")` (line 258) -- recent signals container

**What was added**:
- `html.Div(id="unified-feed-container")` -- single unified feed
- "Latest Posts" section is now full-width (no longer in a two-column split)
- `html.Div(id="post-feed-container")` is preserved (unchanged ID, just moved)

**What moved up**:
- KPI metrics row (`id="performance-metrics"`) stays where it was (line 108-114 area, above analytics tabs)

#### Step C2: Move the KPI loading section above the unified feed

The KPI metrics section (lines 108-114) already sits between hero and analytics. After removing the hero section, the layout order becomes:

```
Time Period Selector
Performance Metrics (KPI cards)     ← stays here
Analytics Tabs                       ← stays here
Unified Prediction Feed              ← NEW (replaces hero + recent)
Latest Posts                         ← moved from column to full-width
Collapsible Data Table
Footer
```

No code change needed for KPIs -- they are already between the period selector and analytics tabs.

---

### Change D: Update Callback Outputs

#### Step D1: Remove `hero-signals-section` and `recent-signals-list` outputs

**File**: `shitty_ui/pages/dashboard.py`
**Location**: Lines 528-537 (the `@app.callback` Output list for `update_dashboard`)

**Current outputs** (7 outputs):
```python
        [
            Output("hero-signals-section", "children"),     # index 0
            Output("performance-metrics", "children"),       # index 1
            Output("accuracy-over-time-chart", "figure"),    # index 2
            Output("confidence-accuracy-chart", "figure"),   # index 3
            Output("asset-accuracy-chart", "figure"),        # index 4
            Output("recent-signals-list", "children"),       # index 5
            Output("last-update-timestamp", "data"),         # index 6
        ],
```

**New outputs** (6 outputs -- hero removed, recent replaced with unified):
```python
        [
            Output("unified-feed-container", "children"),    # index 0
            Output("performance-metrics", "children"),       # index 1
            Output("accuracy-over-time-chart", "figure"),    # index 2
            Output("confidence-accuracy-chart", "figure"),   # index 3
            Output("asset-accuracy-chart", "figure"),        # index 4
            Output("last-update-timestamp", "data"),         # index 5
        ],
```

**Changes**:
- Output index 0: `hero-signals-section` replaced by `unified-feed-container`
- Output index 5: `recent-signals-list` removed entirely
- Output index 6 → 5: `last-update-timestamp` shifts down
- Total outputs: 7 → 6

#### Step D2: Replace hero section callback logic with unified feed logic

**File**: `shitty_ui/pages/dashboard.py`
**Location**: Lines 554-629 (hero section inside `update_dashboard()`)

Replace the entire hero section block (lines 554-629) with:

```python
        # ===== Unified Prediction Feed =====
        try:
            feed_df = get_unified_feed(limit=15, days=days)
            if not feed_df.empty:
                feed_cards = [
                    create_unified_signal_card(row) for _, row in feed_df.iterrows()
                ]
            else:
                feed_cards = [
                    html.P(
                        "No predictions for this period",
                        style={
                            "color": COLORS["text_muted"],
                            "textAlign": "center",
                            "padding": "20px",
                        },
                    )
                ]
        except Exception as e:
            errors.append(f"Unified feed: {e}")
            print(f"Error loading unified feed: {traceback.format_exc()}")
            feed_cards = [create_error_card("Unable to load predictions", str(e))]
```

#### Step D3: Remove recent signals callback logic

**File**: `shitty_ui/pages/dashboard.py`
**Location**: Lines 844-865 (the `# ===== Recent Signals with error handling =====` block)

Delete this entire block. The `signal_cards` variable is no longer needed.

#### Step D4: Update the return tuple

**File**: `shitty_ui/pages/dashboard.py`
**Location**: Lines 871-879 (the `return` statement at the end of `update_dashboard()`)

**Current**:
```python
        return (
            hero_section,
            metrics_row,
            acc_fig,
            conf_fig,
            asset_fig,
            signal_cards,
            current_time,
        )
```

**New**:
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

#### Step D5: Update imports in dashboard.py

**File**: `shitty_ui/pages/dashboard.py`
**Location**: Lines 12-38 (imports at top of file)

Remove from imports:
```python
# Remove these from the components.cards import:
    create_hero_signal_card,
    create_signal_card,

# Remove from the data import:
    get_recent_signals,
    get_active_signals,
```

Add to imports:
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
from data import (
    get_unified_feed,
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

Note: `get_active_signals`, `get_active_signals_with_fallback`, and `get_recent_signals` are removed from dashboard.py imports. They remain in `data.py` and are still used by `layout.py` and `get_active_signals_with_fallback()`. `create_empty_state_html` and `get_empty_state_context` are kept (added by Phase 03, still used in empty state for the unified feed). All imports are top-level — no lazy imports inside callbacks.

---

### Change E: Update layout.py Imports and CSS

#### Step E1: Remove unused re-exports from layout.py

**File**: `shitty_ui/layout.py`
**Location**: Line 48-55 (the re-export block)

The `get_recent_signals` re-export on line 49 should remain for now (test backward compatibility). However, ensure the import list in `layout.py` lines 16-29 still works after `dashboard.py` no longer imports `create_hero_signal_card` or `create_signal_card`.

Check: `layout.py` imports these from `components.cards` on lines 21 and 24. These imports are used by `layout.py` itself (not just passed through). Since `create_hero_signal_card` and `create_signal_card` are still used by the `/signals` page and test files, keep them in `layout.py` imports.

Add `create_unified_signal_card` to the import list in `layout.py` line 16-29:

```python
from components.cards import (
    create_error_card,
    create_empty_chart,
    create_empty_state_chart,
    create_feed_signal_card,
    create_hero_signal_card,
    create_metric_card,
    create_new_signals_banner,
    create_signal_card,
    create_post_card,
    create_prediction_timeline_card,
    create_related_asset_link,
    create_performance_summary,
    create_unified_signal_card,
)
```

#### Step E2: Add unified card CSS

**File**: `shitty_ui/layout.py`
**Location**: After the `.hero-signal-card:hover` block (line 106)

Add the following CSS inside the `<style>` block:

```css
            /* Unified signal card hover effect */
            .unified-signal-card {
                transition: transform 0.15s ease, box-shadow 0.15s ease;
                border-radius: 8px;
            }
            .unified-signal-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 20px rgba(59, 130, 246, 0.15);
            }
```

Keep the existing `.hero-signal-card` CSS -- it may still be used by the `/signals` page or future features.

---

## Test Plan

### New Tests: `TestGetUnifiedFeed`

**File**: `shit_tests/shitty_ui/test_data.py`
**Location**: After `TestGetActiveSignals` class (after approximately line 1900)

```python
class TestGetUnifiedFeed:
    """Tests for get_unified_feed function."""

    @patch("data.execute_query")
    def test_returns_dataframe_with_aggregated_columns(self, mock_execute):
        """Test that unified feed returns DataFrame with expected columns."""
        from data import get_unified_feed

        mock_execute.return_value = (
            [
                (
                    datetime.now(),
                    "tariff announcement",
                    "post123",
                    1,
                    ["AAPL", "TSLA"],
                    {"AAPL": "bullish"},
                    0.85,
                    "thesis text",
                    "completed",
                    2,       # outcome_count
                    2,       # correct_count
                    0,       # incorrect_count
                    3.5,     # avg_return_t7
                    70.0,    # total_pnl_t7
                    True,    # is_complete
                )
            ],
            [
                "timestamp", "text", "shitpost_id", "prediction_id",
                "assets", "market_impact", "confidence", "thesis",
                "analysis_status", "outcome_count", "correct_count",
                "incorrect_count", "avg_return_t7", "total_pnl_t7",
                "is_complete",
            ],
        )

        result = get_unified_feed(limit=15, days=90)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert result.iloc[0]["confidence"] == 0.85
        assert result.iloc[0]["outcome_count"] == 2
        assert "thesis" in result.columns
        assert "analysis_status" in result.columns

    @patch("data.execute_query")
    def test_respects_days_parameter(self, mock_execute):
        """Test that days parameter adds date filter to query."""
        from data import get_unified_feed

        mock_execute.return_value = ([], [])

        get_unified_feed(limit=10, days=7)

        call_args = mock_execute.call_args[0]
        params = call_args[1]
        assert "start_date" in params
        assert params["limit"] == 10

    @patch("data.execute_query")
    def test_no_date_filter_when_days_is_none(self, mock_execute):
        """Test that days=None omits date filter."""
        from data import get_unified_feed

        mock_execute.return_value = ([], [])

        get_unified_feed(limit=15, days=None)

        call_args = mock_execute.call_args[0]
        params = call_args[1]
        assert "start_date" not in params

    @patch("data.execute_query")
    def test_respects_min_confidence(self, mock_execute):
        """Test that min_confidence is passed as query parameter."""
        from data import get_unified_feed

        mock_execute.return_value = ([], [])

        get_unified_feed(min_confidence=0.7)

        call_args = mock_execute.call_args[0]
        params = call_args[1]
        assert params["min_confidence"] == 0.7

    @patch("data.execute_query")
    def test_returns_empty_dataframe_on_error(self, mock_execute):
        """Test graceful degradation on database error."""
        from data import get_unified_feed

        mock_execute.side_effect = Exception("Database error")

        result = get_unified_feed()

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch("data.execute_query")
    def test_returns_empty_dataframe_on_no_results(self, mock_execute):
        """Test that empty result set returns empty DataFrame, not error."""
        from data import get_unified_feed

        mock_execute.return_value = ([], [])

        result = get_unified_feed()

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch("data.execute_query")
    def test_query_contains_group_by(self, mock_execute):
        """Test that query uses GROUP BY for deduplication."""
        from data import get_unified_feed

        mock_execute.return_value = ([], [])

        get_unified_feed()

        call_args = mock_execute.call_args[0]
        query_text = str(call_args[0])
        assert "GROUP BY" in query_text

    @patch("data.execute_query")
    def test_query_sorts_evaluated_first(self, mock_execute):
        """Test that query sorts evaluated predictions before pending."""
        from data import get_unified_feed

        mock_execute.return_value = ([], [])

        get_unified_feed()

        call_args = mock_execute.call_args[0]
        query_text = str(call_args[0])
        assert "CASE" in query_text
        assert "ORDER BY" in query_text
```

### Prerequisite: Extend `_make_row` helper

**File**: `shit_tests/shitty_ui/test_cards.py`
**Location**: Line 44 (`_make_row` function)

Add new default keys to the base dict so unified card tests can use `_make_row()` with aggregated columns:

```python
def _make_row(**overrides):
    base = {
        ...existing keys...,
        "outcome_count": 0,
        "correct_count": 0,
        "incorrect_count": 0,
        "total_pnl_t7": None,
        "avg_return_t7": None,
        "is_complete": False,
        "shitpost_id": "post123",
        "prediction_id": 1,
    }
```

These defaults are safe — existing tests that don't use these keys are unaffected since `_make_row` uses `dict.update(overrides)`.

### New Tests: `TestCreateUnifiedSignalCard`

**File**: `shit_tests/shitty_ui/test_cards.py`
**Location**: After the existing test classes (at end of file)

```python
class TestCreateUnifiedSignalCard:
    """Tests for the unified signal card component."""

    def test_renders_without_error(self):
        """Test basic rendering with standard row data."""
        from components.cards import create_unified_signal_card

        card = create_unified_signal_card(_make_row(
            outcome_count=2,
            correct_count=2,
            incorrect_count=0,
            total_pnl_t7=50.0,
        ))
        assert card is not None

    def test_has_unified_signal_card_class(self):
        """Test that className is 'unified-signal-card'."""
        from components.cards import create_unified_signal_card

        card = create_unified_signal_card(_make_row(
            outcome_count=0, correct_count=0, incorrect_count=0,
            total_pnl_t7=None,
        ))
        assert card.className == "unified-signal-card"

    def test_has_sentiment_left_border(self):
        """Test that card has a sentiment-colored left border."""
        from components.cards import create_unified_signal_card

        card = create_unified_signal_card(_make_row(
            market_impact={"AAPL": "bullish"},
            outcome_count=0, correct_count=0, incorrect_count=0,
            total_pnl_t7=None,
        ))
        assert "borderLeft" in card.style
        assert SENTIMENT_COLORS["bullish"] in card.style["borderLeft"]

    def test_shows_correct_badge_with_pnl(self):
        """Test aggregated correct outcome shows P&L."""
        from components.cards import create_unified_signal_card

        card = create_unified_signal_card(_make_row(
            outcome_count=3,
            correct_count=2,
            incorrect_count=1,
            total_pnl_t7=120.0,
        ))
        text = _extract_text(card)
        assert "+$120" in text

    def test_shows_pending_when_no_outcomes(self):
        """Test pending badge when outcome_count is 0."""
        from components.cards import create_unified_signal_card

        card = create_unified_signal_card(_make_row(
            outcome_count=0,
            correct_count=0,
            incorrect_count=0,
            total_pnl_t7=None,
        ))
        text = _extract_text(card)
        assert "Pending" in text

    def test_shows_thesis_preview(self):
        """Test that thesis is shown as a preview."""
        from components.cards import create_unified_signal_card

        card = create_unified_signal_card(_make_row(
            thesis="Tariffs will boost domestic steel production",
            outcome_count=0, correct_count=0, incorrect_count=0,
            total_pnl_t7=None,
        ))
        text = _extract_text(card)
        assert "Tariffs will boost" in text

    def test_no_thesis_section_when_empty(self):
        """Test that thesis section is omitted when thesis is empty."""
        from components.cards import create_unified_signal_card

        card = create_unified_signal_card(_make_row(
            thesis="",
            outcome_count=0, correct_count=0, incorrect_count=0,
            total_pnl_t7=None,
        ))
        # Card should have exactly 3 children (time, preview, sentiment row)
        assert len(card.children) == 3

    def test_confidence_displayed_as_percentage(self):
        """Test confidence shows as bare percentage."""
        from components.cards import create_unified_signal_card

        card = create_unified_signal_card(_make_row(
            confidence=0.85,
            outcome_count=0, correct_count=0, incorrect_count=0,
            total_pnl_t7=None,
        ))
        text = _extract_text(card)
        assert "85%" in text
        assert "Confidence:" not in text
```

### Updated Tests: Layout Structure

**File**: `shit_tests/shitty_ui/test_layout.py`
**Location**: Lines 1636-1670 (tests that assert old IDs exist)

Update these tests:

```python
    def test_dashboard_contains_unified_feed(self):
        """Test that unified-feed-container is present in the dashboard."""
        from pages.dashboard import create_dashboard_page

        page = create_dashboard_page()
        found_ids = _find_component_ids(page)
        assert "unified-feed-container" in found_ids

    def test_dashboard_no_longer_has_hero_section(self):
        """Test that hero-signals-section has been removed."""
        from pages.dashboard import create_dashboard_page

        page = create_dashboard_page()
        found_ids = _find_component_ids(page)
        assert "hero-signals-section" not in found_ids

    def test_dashboard_no_longer_has_recent_signals_list(self):
        """Test that recent-signals-list has been removed."""
        from pages.dashboard import create_dashboard_page

        page = create_dashboard_page()
        found_ids = _find_component_ids(page)
        assert "recent-signals-list" not in found_ids
```

**Replace** the following old tests:
- `test_dashboard_contains_recent_signals` (line 1636) -- replace with `test_dashboard_no_longer_has_recent_signals_list`
- `test_dashboard_preserves_hero_signals_section` (line 1664) -- replace with `test_dashboard_no_longer_has_hero_section`

**Add** the new `test_dashboard_contains_unified_feed` test.

### Regression Tests

Ensure these existing tests still pass unchanged:
- `TestGetActiveSignals` (test_data.py line 1676) -- function not modified, only docstring updated
- `TestGetRecentSignals` (test_data.py line 93) -- function not modified, only docstring updated
- `TestGetSignalFeed` (test_data.py line 2223) -- /signals page unaffected
- `TestConfidenceDisplayConsistency` (test_cards.py line 170) -- old card functions unchanged
- `TestSentimentLeftBorder` (test_cards.py line 276) -- old card functions unchanged
- `TestSentimentBadgeBackground` (test_cards.py line 344) -- old card functions unchanged
- `TestHeroSignalCardDedup` (test_layout.py line 1271) -- `create_hero_signal_card` still exists in cards.py
- All `/performance` page tests -- completely disjoint from this change

---

## Verification Checklist

- [ ] Dashboard shows a single "Predictions" section with up to 15 cards
- [ ] Cards show aggregated outcomes (correct/incorrect with P&L) like hero cards did
- [ ] Cards show thesis preview like signal cards did
- [ ] Evaluated predictions appear before pending ones
- [ ] Time period selector (7D/30D/90D/All) filters the unified feed
- [ ] "Latest Posts" section is now full-width below the feed
- [ ] No `hero-signals-section` or `recent-signals-list` IDs in the DOM
- [ ] `/signals` page is completely unaffected (still uses `get_signal_feed` + `create_feed_signal_card`)
- [ ] `/performance` page is completely unaffected
- [ ] All existing tests pass: `source venv/bin/activate && pytest shit_tests/shitty_ui/ -v`
- [ ] New tests pass: `source venv/bin/activate && pytest shit_tests/shitty_ui/test_data.py::TestGetUnifiedFeed -v`
- [ ] New tests pass: `source venv/bin/activate && pytest shit_tests/shitty_ui/test_cards.py::TestCreateUnifiedSignalCard -v`
- [ ] Post-feed callback (`update_post_feed`) still works -- `post-feed-container` ID is preserved
- [ ] Collapse table callback still works -- `collapse-table` and `predictions-table-container` IDs preserved
- [ ] CHANGELOG.md updated

---

## What NOT To Do

1. **Do NOT delete `create_hero_signal_card()` or `create_signal_card()`.** These functions are still imported by `layout.py`, tested in `test_cards.py` and `test_layout.py`, and may be used by the `/signals` page in the future. Mark them as deprecated in docstrings, but do not remove them.

2. **Do NOT delete `get_active_signals()` or `get_recent_signals()`.** These are still used in tests, re-exported from `layout.py`, and Phase 01's `get_active_signals_with_fallback()` wraps `get_active_signals()`. Remove only the dashboard call sites.

3. **Do NOT modify the `/signals` page at all.** It uses a completely separate data function (`get_signal_feed`) and card component (`create_feed_signal_card`). This phase only touches the dashboard (`/`).

4. **Do NOT change the `update_post_feed` callback.** The post feed is separate from the prediction feed. It must continue to work with the same `post-feed-container` ID, just inside a new full-width layout.

5. **Do NOT change the callback output count without updating the return tuple.** Dash requires the number of outputs to exactly match the number of return values. If you remove an output, you must also remove the corresponding return value.

6. **Do NOT add filtering/pagination to the unified feed.** That is what the `/signals` page is for. The dashboard unified feed is a simple top-N summary. Adding filters here would duplicate the `/signals` page and defeat the purpose of merging.

7. **Do NOT change the `selected-period` store or time period buttons.** They are shared across multiple callbacks (KPIs, charts, feed). Only the `days` parameter passed to `get_unified_feed()` connects the period to the feed.

8. **Do NOT break the collapsible data table.** The `collapse-table`, `collapse-table-button`, and `predictions-table-container` IDs must remain in the layout and their callbacks must remain functional.

---

## Impact on Downstream Phases

### Phase 06 (Inline Sparklines) -- Soft dependency
Phase 06 adds mini price charts to signal cards. With this phase complete, Phase 06 should target `create_unified_signal_card()` instead of `create_signal_card()`. The unified card already has the `assets` field exposed, so Phase 06 can add a sparkline row between the sentiment row and thesis preview.

### Phase 08 (Visual Hierarchy) -- Hard dependency
Phase 08 redesigns section differentiation and data density. It depends on the unified feed being in place because it adds section headers, spacing tokens, and visual breaks between the feed and the posts section. Phase 08 should reference `unified-feed-container` and the new full-width "Latest Posts" card.

### Phase 10 (Brand Identity) -- Soft dependency
Phase 10 adds self-deprecating copy to section headers. It should update the "Predictions" card header text and the "Latest Posts" subtitle. The new section names from this phase ("Predictions" and "Latest Posts") are the targets for Phase 10's copy rewrite.

---

## CHANGELOG Entry

```markdown
### Changed
- **Dashboard: unified prediction feed** -- Replaced the redundant "Hero Signals" section and "Recent Predictions" sidebar with a single full-width prediction feed showing up to 15 signals with aggregated outcomes, thesis previews, and evaluated-first sort order
- **Dashboard: full-width Latest Posts** -- Moved "Latest Posts" from a 7-column split layout to full-width, giving post content more room to breathe
- **Dashboard: callback simplification** -- Reduced main dashboard callback from 7 outputs to 6, removing redundant data fetches

### Added
- **`get_unified_feed()`** -- New data function combining deduplication logic from `get_active_signals()` with time-period filtering from `get_recent_signals()`, with evaluated-first sort order
- **`create_unified_signal_card()`** -- New card component merging hero card's aggregated outcomes with signal card's compact layout and thesis preview
```
