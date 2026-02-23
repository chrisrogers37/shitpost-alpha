# Phase 05: Information Architecture Consolidation (4 Pages to 2 Views)

**PR Title:** refactor: consolidate 4-page IA into 2-view architecture (Screener + Asset Detail)
**Risk Level:** High
**Estimated Effort:** High (3-5 days)
**Dependencies:** Phase 03 (Asset Screener Table), Phase 04 (Annotated Price Chart)

### Files Modified (8)
| File | Action |
|------|--------|
| `shitty_ui/layout.py` | **Modify** — remove `/signals`, `/trends`, `/performance` routes; simplify stores; update nav highlighting callback |
| `shitty_ui/components/header.py` | **Modify** — remove 4 nav links, simplify to logo-only navigation |
| `shitty_ui/pages/dashboard.py` | **Modify** — remove `create_performance_page()` and its callback; integrate backtest KPI summary into homepage |
| `shitty_ui/pages/assets.py` | **Modify** — integrate signal feed (from signals.py), signal summary stats (from trends.py), and per-asset performance data into the asset detail page |
| `shitty_ui/pages/signals.py` | **Delete** — signal feed moves into asset detail page |
| `shitty_ui/pages/trends.py` | **Delete** — replaced entirely by annotated chart on asset detail (Phase 04) |
| `shit_tests/shitty_ui/test_layout.py` | **Modify** — update route tests, remove old route assertions |
| `shit_tests/shitty_ui/test_trends.py` | **Delete** — page no longer exists |

### Files Created (1)
| File | Purpose |
|------|---------|
| `shit_tests/shitty_ui/test_information_architecture.py` | New test file covering the 2-view routing, redirects, and consolidated layout |

---

## Context

### Why This Matters

The user's #1 pain point is: *"The order and arrangement of the system"* (Gap 6 from gap-analysis.md). Today the app has 4 pages (Dashboard, Signals, Trends, Performance) with no clear narrative flow. Users must navigate between pages to piece together the story of "what happened" -> "so what" -> "do what."

This phase collapses the information architecture into 2 clear views:

1. **Home (`/`)** -- the Asset Screener built in Phase 03, plus a simplified KPI row and the backtest summary from Performance. This is the "scan" view.
2. **Asset Detail (`/assets/<symbol>`)** -- the annotated price chart from Phase 04, plus signal history for this asset (best of Signals page), asset-specific performance stats (best of Performance page), and related assets. This is the "drill-in" view.

The narrative becomes linear: **scan -> spot -> drill in -> understand**. No more hopping between 4 tabs. Every piece of data lives in exactly one place along this flow.

### What Gets Removed vs. Folded In

Nothing is deleted without its best parts being relocated:

| Removed Route | Best Elements | New Home |
|---------------|---------------|----------|
| `/signals` | Filtered signal card feed, CSV export, "Load More" pagination | Asset Detail page (pre-filtered to that symbol) |
| `/trends` | Signal-over-trend chart, signal summary stats | Asset Detail page (replaced by Phase 04 annotated chart) |
| `/performance` | Backtest KPI row (5 cards), Accuracy by Confidence chart, Sentiment donut, Per-Asset performance table | Backtest KPI summary -> Home page below screener; Confidence/Sentiment charts -> removed (data accessible via screener sort); Per-Asset table -> replaced by screener table itself |

---

## Visual Specification

### Before (Current State)

```
Header: [Logo] [Dashboard] [Signals] [Trends] [Performance] [Bell] [Refresh]

/ (Dashboard)           -> 4 KPI cards + tabbed charts + prediction feed + post feed + data table
/signals                -> Filter bar + paginated signal card feed + CSV export
/trends                 -> Asset dropdown + candlestick chart + signal summary stats
/performance            -> 5 KPI cards + confidence chart + sentiment donut + asset table
/assets/<symbol>        -> Back link + stat cards + price chart + performance summary + timeline + related
```

### After (Redesigned)

```
Header: [Logo (links /)] [Bell] [Refresh]

/ (Home = Screener)     -> Simplified KPI row (4 cards) + Asset Screener Table (Phase 03)
                           + Backtest Summary strip below screener
                           + Collapsible raw data table (existing)
                           + Footer

/assets/<symbol>        -> Back breadcrumb ("< Screener")
                           + Asset stat cards (existing 4-card row)
                           + Annotated Price Chart (Phase 04, full-width)
                           + Signal History feed (from signals.py, pre-filtered to this asset)
                           + Performance Summary sidebar (existing, enhanced)
                           + Related Assets (existing)
                           + Footer
```

### Navigation Changes

- **Remove:** Dashboard, Signals, Trends, Performance nav links
- **Keep:** Logo (clickable, links to `/`), alert bell, refresh countdown
- **Add:** Nothing new in the header -- simplicity is the goal
- **Asset Detail breadcrumb:** The existing `create_asset_header()` already has a "< Dashboard" back link; rename to "< Screener"

---

## Dependencies

- **Phase 03 (Asset Screener Table)** must be complete -- it provides the `create_screener_table()` component that replaces the dashboard's current tabbed analytics section and the Performance page's asset table
- **Phase 04 (Annotated Price Chart)** must be complete -- it provides the annotated chart component that replaces both the Trends page and the current asset detail price chart
- **This phase unlocks:** Phase 06 (Insight Cards) which attaches dynamic callouts to the new 2-view layout

---

## Detailed Implementation Plan

### Step 1: Simplify the Header (`shitty_ui/components/header.py`)

Remove all 4 nav links. The header becomes logo + alert bell + refresh indicator.

**Current code (lines 48-91):**
```python
                    # Navigation links
                    html.Div(
                        [
                            dcc.Link(
                                [html.I(className="fas fa-home me-1"), "Dashboard"],
                                href="/",
                                className="nav-link-custom",
                                id="nav-link-dashboard",
                            ),
                            dcc.Link(
                                [
                                    html.I(className="fas fa-rss me-1"),
                                    "Signals",
                                ],
                                href="/signals",
                                className="nav-link-custom",
                                id="nav-link-signals",
                            ),
                            dcc.Link(
                                [
                                    html.I(className="fas fa-chart-area me-1"),
                                    "Trends",
                                ],
                                href="/trends",
                                className="nav-link-custom",
                                id="nav-link-trends",
                            ),
                            dcc.Link(
                                [
                                    html.I(className="fas fa-chart-pie me-1"),
                                    "Performance",
                                ],
                                href="/performance",
                                className="nav-link-custom",
                                id="nav-link-performance",
                            ),
                        ],
                        className="nav-links-row",
                        style={
                            "display": "flex",
                            "gap": "8px",
                            "alignItems": "center",
                        },
                    ),
```

**Replace with:**
```python
                    # Navigation is simplified -- logo IS the nav
                    # (No nav links needed with only 2 views: Home and Asset Detail)
```

This means removing the entire `html.Div` with `className="nav-links-row"` and its contents. The logo already links to `/` via `dcc.Link(href="/")` at line 19-35, so clicking the logo returns home.

**Important:** The nav link IDs (`nav-link-dashboard`, `nav-link-signals`, `nav-link-trends`, `nav-link-performance`) are referenced by a `clientside_callback` in `layout.py`. That callback must also be removed (see Step 3).

### Step 2: Update the Asset Detail Back Link (`shitty_ui/pages/assets.py`)

**Current code in `create_asset_header()` (lines 224-243):**
```python
                    dcc.Link(
                        [html.I(className="fas fa-arrow-left me-2"), "Dashboard"],
                        href="/",
                        style={
                            "color": COLORS["accent"],
                            "textDecoration": "none",
                            "fontSize": "0.85rem",
                            "marginRight": "16px",
                        },
                    ),
                    dcc.Link(
                        [html.I(className="fas fa-chart-pie me-2"), "Performance"],
                        href="/performance",
                        style={
                            "color": COLORS["text_muted"],
                            "textDecoration": "none",
                            "fontSize": "0.85rem",
                        },
                    ),
```

**Replace with:**
```python
                    dcc.Link(
                        [html.I(className="fas fa-arrow-left me-2"), "Screener"],
                        href="/",
                        style={
                            "color": COLORS["accent"],
                            "textDecoration": "none",
                            "fontSize": "0.85rem",
                        },
                    ),
```

Remove the Performance link entirely (the route no longer exists).

### Step 3: Update Router and Stores (`shitty_ui/layout.py`)

#### 3a. Remove old route imports

**Current imports (lines 33-40):**
```python
from pages.dashboard import (
    create_dashboard_page,
    create_performance_page,
    register_dashboard_callbacks,
)
from pages.assets import create_asset_page, create_asset_header, register_asset_callbacks
from pages.signals import create_signal_feed_page, register_signal_callbacks
from pages.trends import create_trends_page, register_trends_callbacks
```

**Replace with:**
```python
from pages.dashboard import (
    create_dashboard_page,
    register_dashboard_callbacks,
)
from pages.assets import create_asset_page, create_asset_header, register_asset_callbacks
```

Remove `create_performance_page` from the dashboard import, and remove the `signals` and `trends` imports entirely.

#### 3b. Update the `route_page` callback

**Current (lines 660-680):**
```python
    @app.callback(
        Output("page-content", "children"),
        [Input("url", "pathname")],
    )
    def route_page(pathname: str):
        """Route to the correct page based on URL pathname."""
        if pathname and pathname.startswith("/assets/"):
            symbol = pathname.split("/assets/")[-1].strip("/").upper()
            if symbol:
                return create_asset_page(symbol)

        if pathname == "/performance":
            return create_performance_page()

        if pathname == "/signals":
            return create_signal_feed_page()

        if pathname == "/trends":
            return create_trends_page()

        return create_dashboard_page()
```

**Replace with:**
```python
    @app.callback(
        Output("page-content", "children"),
        [Input("url", "pathname")],
    )
    def route_page(pathname: str):
        """Route to the correct page based on URL pathname.

        Only 2 views exist:
        - / (Home = Screener)
        - /assets/<symbol> (Asset Detail)

        Old routes (/signals, /trends, /performance) redirect to home.
        """
        if pathname and pathname.startswith("/assets/"):
            symbol = pathname.split("/assets/")[-1].strip("/").upper()
            if symbol:
                return create_asset_page(symbol)

        # All other paths (including legacy /signals, /trends, /performance) -> home
        return create_dashboard_page()
```

#### 3c. Remove the nav-link highlighting clientside callback

**Current (lines 682-708):**
```python
    # Active nav link highlighting
    app.clientside_callback(
        """
        function(pathname) {
            var links = {
                '/': 'nav-link-dashboard',
                '/signals': 'nav-link-signals',
                '/trends': 'nav-link-trends',
                '/performance': 'nav-link-performance'
            };
            var classes = [];
            for (var path in links) {
                var isActive = (pathname === path) ||
                    (path === '/' && (pathname === '' || pathname === null));
                classes.push(isActive ? 'nav-link-custom active' : 'nav-link-custom');
            }
            return classes;
        }
        """,
        [
            Output("nav-link-dashboard", "className"),
            Output("nav-link-signals", "className"),
            Output("nav-link-trends", "className"),
            Output("nav-link-performance", "className"),
        ],
        [Input("url", "pathname")],
    )
```

**Delete this entire block.** The nav links no longer exist, so there is nothing to highlight.

#### 3d. Remove old callback registrations

**Current (lines 710-715):**
```python
    # Delegate to page/callback modules
    register_dashboard_callbacks(app)
    register_asset_callbacks(app)
    register_signal_callbacks(app)
    register_trends_callbacks(app)
    register_alert_callbacks(app)
```

**Replace with:**
```python
    # Delegate to page/callback modules
    register_dashboard_callbacks(app)
    register_asset_callbacks(app)
    register_alert_callbacks(app)
```

Remove `register_signal_callbacks(app)` and `register_trends_callbacks(app)`.

#### 3e. Clean up unused re-exports

**Current (lines 48-56):**
```python
# Re-export data functions for backwards compatibility with test patches
from data import (  # noqa: F401
    get_recent_signals,
    get_performance_metrics,
    get_accuracy_by_confidence,
    get_accuracy_by_asset,
    get_active_assets_from_db,
    get_available_assets,
)
```

Keep this block as-is for now. Some tests may still patch these. We will clean up in a separate pass after verifying test coverage.

### Step 4: Remove the Performance Page from Dashboard (`shitty_ui/pages/dashboard.py`)

#### 4a. Remove `create_performance_page()` function

Delete the entire `create_performance_page()` function (lines 322-441). This is a standalone function that returns the `/performance` layout. It is no longer routed to.

#### 4b. Remove Performance page callback from `register_dashboard_callbacks()`

Delete the entire `update_performance_page` callback (lines 1100-1443), which starts at:
```python
    # ========== Performance Page Callbacks ==========
    @app.callback(
        [
            Output("backtest-header", "children"),
            Output("perf-confidence-chart", "figure"),
            Output("perf-sentiment-chart", "figure"),
            Output("perf-asset-table", "children"),
        ],
        [Input("url", "pathname")],
    )
    def update_performance_page(pathname):
```

This callback populated the backtest header, confidence chart, sentiment chart, and asset table on `/performance`. All of this data is now accessed via the screener table (Phase 03) and the asset detail page.

#### 4c. Add a Backtest Summary Strip to the Home Page

After removing the Performance page, the backtest KPI data (Starting Capital, Final Value, Trades, Win Rate, P&L) should appear as a compact summary on the home page, below the screener table. This gives users the "so what" context without needing a separate page.

**In `create_dashboard_page()`, after the existing "Collapsible Full Data Table" section (ends around line 311) and before the Footer, add:**

```python
                    # ========== Backtest Summary Strip ==========
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                [
                                    html.I(className="fas fa-flask me-2"),
                                    COPY["backtest_title"],
                                    html.Small(
                                        " - Simulated $10K portfolio, high-confidence trades only",
                                        style={
                                            "color": COLORS["text_muted"],
                                            "fontWeight": "normal",
                                        },
                                    ),
                                ],
                                className="fw-bold",
                            ),
                            dbc.CardBody(
                                dcc.Loading(
                                    type="default",
                                    color=COLORS["accent"],
                                    children=html.Div(id="home-backtest-summary"),
                                ),
                            ),
                        ],
                        className="mb-4",
                        style={
                            "backgroundColor": COLORS["secondary"],
                            "borderTop": f"2px solid {COLORS['accent']}",
                        },
                    ),
```

**Add a new callback in `register_dashboard_callbacks()` to populate it:**

```python
    @app.callback(
        Output("home-backtest-summary", "children"),
        [Input("refresh-interval", "n_intervals")],
    )
    def update_home_backtest_summary(n_intervals):
        """Populate the backtest summary strip on the home page."""
        try:
            bt = get_backtest_simulation(
                initial_capital=10000, min_confidence=0.75, days=90
            )
            pnl_color = (
                COLORS["success"] if bt["total_return_pct"] >= 0 else COLORS["danger"]
            )

            return dbc.Row(
                [
                    dbc.Col(
                        create_metric_card(
                            "Starting Capital",
                            f"${bt['initial_capital']:,.0f}",
                            "",
                            "wallet",
                            COLORS["text_muted"],
                        ),
                        md=2, sm=4, xs=6,
                    ),
                    dbc.Col(
                        create_metric_card(
                            "Final Value",
                            f"${bt['final_value']:,.0f}",
                            f"{bt['total_return_pct']:+.1f}%",
                            "sack-dollar",
                            pnl_color,
                        ),
                        md=2, sm=4, xs=6,
                    ),
                    dbc.Col(
                        create_metric_card(
                            "Trades",
                            f"{bt['trade_count']}",
                            f"{bt['wins']}W / {bt['losses']}L",
                            "exchange-alt",
                            COLORS["accent"],
                        ),
                        md=2, sm=4, xs=6,
                    ),
                    dbc.Col(
                        create_metric_card(
                            "Win Rate",
                            f"{bt['win_rate']:.1f}%",
                            "high-confidence trades",
                            "chart-line",
                            COLORS["success"] if bt["win_rate"] > 50 else COLORS["danger"],
                        ),
                        md=2, sm=4, xs=6,
                    ),
                    dbc.Col(
                        create_metric_card(
                            "P&L",
                            f"${bt['final_value'] - bt['initial_capital']:+,.0f}",
                            "net profit/loss",
                            "dollar-sign",
                            pnl_color,
                        ),
                        md=2, sm=4, xs=6,
                    ),
                ],
                className="g-2",
            )
        except Exception as e:
            return create_error_card("Unable to load backtest summary", str(e))
```

**Add the import for `get_backtest_simulation`** to the top of `dashboard.py` (it's already imported for the Performance page callback, but verify it survives the deletion of that callback):

In the `from data import (...)` block at the top of `dashboard.py`, ensure `get_backtest_simulation` remains listed.

### Step 5: Integrate Signal Feed into Asset Detail (`shitty_ui/pages/assets.py`)

The Signal Feed page (`signals.py`) has a filtered, paginated card feed with export CSV. We fold a simplified version into the asset detail page, pre-filtered to the current symbol.

#### 5a. Add imports to `assets.py`

Add these imports at the top of `shitty_ui/pages/assets.py`:

```python
from components.cards import (
    create_error_card,
    create_empty_chart,
    create_metric_card,
    create_prediction_timeline_card,
    create_related_asset_link,
    create_performance_summary,
    create_feed_signal_card,        # NEW: for signal feed cards
)
from data import (
    get_asset_price_history,
    get_asset_predictions,
    get_asset_stats,
    get_price_with_signals,
    get_related_assets,
    get_signal_feed,                # NEW: for signal feed on asset detail
    get_signal_feed_count,          # NEW: for signal feed count
    get_sparkline_prices,           # NEW: for sparkline in signal cards
)
```

#### 5b. Add Signal History section to `create_asset_page()` layout

In `create_asset_page()`, after the existing "Prediction timeline" card (lines 178-193) and before the Footer (line 195), insert a new section:

```python
                    # ========== Signal History Feed (for this asset) ==========
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                [
                                    html.I(className="fas fa-rss me-2"),
                                    f"Signal Feed for {symbol}",
                                    html.Small(
                                        " - All predictions mentioning this asset",
                                        style={
                                            "color": COLORS["text_muted"],
                                            "fontWeight": "normal",
                                        },
                                    ),
                                ],
                                className="fw-bold d-flex justify-content-between align-items-center",
                            ),
                            dbc.CardBody(
                                [
                                    # Inline filter row: sentiment + outcome only
                                    dbc.Row(
                                        [
                                            dbc.Col(
                                                [
                                                    html.Label(
                                                        "Sentiment",
                                                        className="small",
                                                        style={"color": COLORS["text_muted"]},
                                                    ),
                                                    dcc.Dropdown(
                                                        id="asset-signal-sentiment-filter",
                                                        options=[
                                                            {"label": "All", "value": "all"},
                                                            {"label": "Bullish", "value": "bullish"},
                                                            {"label": "Bearish", "value": "bearish"},
                                                        ],
                                                        value="all",
                                                        clearable=False,
                                                        style={"fontSize": "0.85rem"},
                                                    ),
                                                ],
                                                sm=6, xs=12,
                                            ),
                                            dbc.Col(
                                                [
                                                    html.Label(
                                                        "Outcome",
                                                        className="small",
                                                        style={"color": COLORS["text_muted"]},
                                                    ),
                                                    dcc.Dropdown(
                                                        id="asset-signal-outcome-filter",
                                                        options=[
                                                            {"label": "All", "value": "all"},
                                                            {"label": "Correct", "value": "correct"},
                                                            {"label": "Incorrect", "value": "incorrect"},
                                                            {"label": "Pending", "value": "pending"},
                                                        ],
                                                        value="all",
                                                        clearable=False,
                                                        style={"fontSize": "0.85rem"},
                                                    ),
                                                ],
                                                sm=6, xs=12,
                                            ),
                                        ],
                                        className="g-2 mb-3",
                                    ),
                                    # Signal cards container
                                    dcc.Loading(
                                        type="circle",
                                        color=COLORS["accent"],
                                        children=html.Div(
                                            id="asset-signal-feed-container",
                                            style={
                                                "maxHeight": "700px",
                                                "overflowY": "auto",
                                            },
                                        ),
                                    ),
                                    # Signal count label
                                    html.Div(
                                        id="asset-signal-feed-count",
                                        style={
                                            "color": COLORS["text_muted"],
                                            "fontSize": "0.8rem",
                                            "marginTop": "8px",
                                            "textAlign": "center",
                                        },
                                    ),
                                ],
                            ),
                        ],
                        style={
                            "backgroundColor": COLORS["secondary"],
                            "marginTop": "24px",
                            "marginBottom": "24px",
                        },
                    ),
```

#### 5c. Add callback to populate the signal feed

In `register_asset_callbacks()`, add a new callback:

```python
    @app.callback(
        [
            Output("asset-signal-feed-container", "children"),
            Output("asset-signal-feed-count", "children"),
        ],
        [
            Input("asset-page-symbol", "data"),
            Input("asset-signal-sentiment-filter", "value"),
            Input("asset-signal-outcome-filter", "value"),
        ],
    )
    def update_asset_signal_feed(symbol, sentiment, outcome):
        """Populate the signal feed for this asset."""
        if not symbol:
            return [], ""

        try:
            sentiment_val = sentiment if sentiment != "all" else None
            outcome_val = outcome if outcome != "all" else None

            df = get_signal_feed(
                limit=30,
                offset=0,
                asset_filter=symbol,
                sentiment_filter=sentiment_val,
                outcome_filter=outcome_val,
            )

            total = get_signal_feed_count(
                asset_filter=symbol,
                sentiment_filter=sentiment_val,
                outcome_filter=outcome_val,
            )

            if df.empty:
                empty_msg = html.P(
                    f"No signals found for {symbol} with these filters.",
                    style={
                        "color": COLORS["text_muted"],
                        "textAlign": "center",
                        "padding": "20px",
                    },
                )
                return [empty_msg], ""

            # Batch-fetch sparkline prices
            sparkline_prices = {}
            if "symbol" in df.columns:
                unique_symbols = df["symbol"].dropna().unique().tolist()
                if unique_symbols:
                    center_ts = pd.to_datetime(df["timestamp"]).median()
                    center_date = (
                        center_ts.strftime("%Y-%m-%d")
                        if pd.notna(center_ts)
                        else None
                    )
                    if center_date:
                        sparkline_prices = get_sparkline_prices(
                            symbols=tuple(sorted(unique_symbols)),
                            center_date=center_date,
                        )

            cards = [
                create_feed_signal_card(
                    row, card_index=idx, sparkline_prices=sparkline_prices
                )
                for idx, (_, row) in enumerate(df.iterrows())
            ]

            count_label = f"Showing {len(df)} of {total} signals for {symbol}"
            return cards, count_label

        except Exception as e:
            import traceback as tb
            print(f"Error loading signal feed for {symbol}: {tb.format_exc()}")
            return [create_error_card(f"Unable to load signal feed for {symbol}", str(e))], ""
```

**Add the necessary import** at the top of `assets.py`:
```python
import pandas as pd
```

(It is not currently imported in assets.py.)

### Step 6: Delete Removed Page Files

#### 6a. Delete `shitty_ui/pages/signals.py`

This file is 712 lines. All its functionality is now:
- **Signal feed cards** -> folded into asset detail page (Step 5)
- **CSV export** -> not preserved in this phase (can be re-added to the asset detail feed later if requested; low-priority feature)
- **New-signals polling** -> not preserved (asset detail page will be refreshed by existing `refresh-interval` timer)

**Important: Do NOT delete the file until all tests pass without it.** Use `git rm shitty_ui/pages/signals.py` to track the deletion.

#### 6b. Delete `shitty_ui/pages/trends.py`

This file is 350 lines. All its functionality is now:
- **Signal-over-trend chart** -> replaced by Phase 04 annotated chart on asset detail page
- **Signal summary stats** -> the mini-stat row (`_build_signal_summary`, `_mini_stat`) is useful. Port the `_build_signal_summary()` function to `assets.py` if the asset detail page does not already show equivalent stats. (The existing `asset-stat-cards` callback at line 310-382 of assets.py already shows accuracy, total predictions, P&L, and avg return -- which covers the same data. So no porting is needed.)

**Use `git rm shitty_ui/pages/trends.py`.**

### Step 7: Clean Up CSS in `layout.py` index_string

Several CSS classes are now unused:

- `.nav-link-custom` and all its states (`:hover`, `.active`, `.active::after`) -- nav links are gone
- `.nav-links-row` responsive rules -- nav links are gone

**Do NOT delete these CSS rules yet.** They do no harm staying in the stylesheet, and removing them risks accidentally breaking something. Mark them with a `/* TODO: remove after Phase 05 verification */` comment. They can be cleaned up in a separate CSS-cleanup PR.

### Step 8: Update the Existing `index_string` Responsive Rules

The `@media (max-width: 768px)` section has rules for `.nav-links-row` (horizontal scroll). These are now dead code but harmless. Leave them with a TODO comment.

---

## Responsive Behavior

The 2-view architecture simplifies responsive design:

### Home (Screener) at Mobile
- KPI row: existing 2x2 grid at 375px (already works)
- Screener table: Phase 03 handles its own responsiveness (horizontal scroll)
- Backtest summary strip: same `dbc.Row` with `xs=6` columns -- stacks into 3 rows of 2 at mobile

### Asset Detail at Mobile
- Back breadcrumb: single line, no wrapping issues
- Stat cards: existing 2x2 grid at `xs=6`
- Annotated chart: Phase 04 handles its own responsiveness
- Signal feed cards: already responsive (from `create_feed_signal_card`)
- Filters: stack vertically at `xs=12`

### Header at Mobile
- With nav links removed, the header is dramatically simpler
- Logo + alert bell + refresh indicator in a single row
- No horizontal scroll needed
- Touch targets: alert bell is already 48px min-height

---

## Accessibility Checklist

- [ ] All interactive elements (logo link, alert bell) have ARIA labels or visible text
- [ ] Back breadcrumb on asset detail is a proper `dcc.Link` (keyboard navigable)
- [ ] Signal feed filter dropdowns have associated `html.Label` elements
- [ ] Color is not the sole indicator of state (sentiment badges use text + color)
- [ ] Removed pages return graceful fallback (home page) instead of 404
- [ ] Focus order remains logical: header -> main content -> footer
- [ ] Chart components maintain existing `config` options (responsive, displayModeBar)

---

## Test Plan

### Tests to Delete

**`shit_tests/shitty_ui/test_trends.py`** -- this entire file tests the trends page which no longer exists. Delete it.

### Tests to Modify

**`shit_tests/shitty_ui/test_layout.py`** -- any tests that:
1. Assert the existence of `/signals`, `/trends`, or `/performance` routes
2. Test the nav-link highlighting clientside callback
3. Test `create_performance_page()` layout
4. Import `create_signal_feed_page`, `register_signal_callbacks`, `create_trends_page`, `register_trends_callbacks`

For each of these, either remove the test or update it to verify the new behavior (old routes redirect to home).

### New Tests to Write

Create `shit_tests/shitty_ui/test_information_architecture.py`:

```python
"""Tests for the 2-view information architecture after Phase 05 consolidation."""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))


class TestRouting:
    """Test that the router correctly handles all URL patterns."""

    def test_root_returns_dashboard(self):
        """GET / should return the screener home page."""
        from layout import create_app, register_callbacks
        app = create_app()
        register_callbacks(app)
        # Verify route_page("/") returns create_dashboard_page() result

    def test_asset_route_returns_asset_page(self):
        """GET /assets/AAPL should return the asset detail page for AAPL."""
        pass  # Verify route_page("/assets/AAPL") calls create_asset_page("AAPL")

    def test_legacy_signals_route_redirects_home(self):
        """GET /signals should gracefully fall through to home page."""
        pass  # Verify route_page("/signals") returns create_dashboard_page()

    def test_legacy_trends_route_redirects_home(self):
        """GET /trends should gracefully fall through to home page."""
        pass  # Verify route_page("/trends") returns create_dashboard_page()

    def test_legacy_performance_route_redirects_home(self):
        """GET /performance should gracefully fall through to home page."""
        pass  # Verify route_page("/performance") returns create_dashboard_page()

    def test_unknown_route_returns_home(self):
        """GET /unknown should fall through to home page."""
        pass


class TestHeaderSimplification:
    """Test that the header no longer contains nav links."""

    def test_header_has_no_nav_links(self):
        """Header should not contain Dashboard/Signals/Trends/Performance links."""
        from components.header import create_header
        header = create_header()
        # Recursively search for nav-link IDs -- should find none
        pass

    def test_header_logo_links_home(self):
        """Logo should link to /."""
        from components.header import create_header
        header = create_header()
        # Find the dcc.Link with href="/" -- should exist
        pass

    def test_header_has_alert_bell(self):
        """Alert bell button should still be present."""
        from components.header import create_header
        header = create_header()
        # Find component with id="open-alert-config-button"
        pass


class TestAssetDetailSignalFeed:
    """Test the signal feed integration on the asset detail page."""

    def test_asset_page_has_signal_feed_section(self):
        """Asset page should contain a signal feed container."""
        from pages.assets import create_asset_page
        page = create_asset_page("XLE")
        # Find component with id="asset-signal-feed-container"
        pass

    def test_asset_page_has_sentiment_filter(self):
        """Asset page should have sentiment filter for signals."""
        from pages.assets import create_asset_page
        page = create_asset_page("XLE")
        # Find component with id="asset-signal-sentiment-filter"
        pass

    def test_asset_page_back_link_says_screener(self):
        """Back link should say 'Screener' not 'Dashboard'."""
        from pages.assets import create_asset_header
        header = create_asset_header("XLE")
        # Search for text "Screener"
        pass


class TestBacktestSummaryOnHome:
    """Test the backtest summary strip on the home page."""

    def test_home_page_has_backtest_section(self):
        """Home page should contain backtest summary container."""
        from pages.dashboard import create_dashboard_page
        page = create_dashboard_page()
        # Find component with id="home-backtest-summary"
        pass
```

### Existing Tests to Verify

Run the full test suite after implementation:
```bash
source venv/bin/activate && pytest shit_tests/shitty_ui/ -v
```

Expected outcomes:
- `test_layout.py` -- some tests will fail until updated (route tests, nav-link tests)
- `test_alerts.py` -- should pass unchanged (alert system is untouched)
- `test_charts.py` -- should pass unchanged
- `test_cards.py` -- should pass unchanged
- `test_data.py` -- should pass unchanged
- `test_sparkline.py` -- should pass unchanged
- `test_copy.py` -- should pass unchanged
- `test_brand_identity.py` -- should pass unchanged

---

## Verification Checklist

- [ ] `python -c "from shitty_ui.layout import create_app, register_callbacks; app = create_app(); register_callbacks(app)"` succeeds without import errors
- [ ] Navigate to `/` -- shows Screener home page with KPI row, screener table, backtest summary
- [ ] Navigate to `/assets/XLE` -- shows asset detail with chart, stat cards, signal feed, related assets
- [ ] Navigate to `/signals` -- gracefully shows home page (not a 404)
- [ ] Navigate to `/trends` -- gracefully shows home page (not a 404)
- [ ] Navigate to `/performance` -- gracefully shows home page (not a 404)
- [ ] Header shows only logo, alert bell, refresh indicator (no nav links)
- [ ] Logo click from asset detail returns to home
- [ ] Back breadcrumb on asset detail says "Screener" and links to `/`
- [ ] Alert bell opens alert config offcanvas (unchanged behavior)
- [ ] Refresh countdown timer still works
- [ ] Signal feed on asset detail loads cards and responds to filter changes
- [ ] Backtest summary strip on home page shows 5 KPI cards
- [ ] Mobile (375px): header doesn't clip, content stacks properly
- [ ] `source venv/bin/activate && pytest shit_tests/shitty_ui/ -v` -- all tests pass
- [ ] `ruff check shitty_ui/` -- no lint errors

---

## "What NOT To Do" Section

### DO NOT delete the signal card components
`create_feed_signal_card()` in `components/cards.py` is still used by the asset detail signal feed. Only the *page-level layout* (`signals.py`) and its *callbacks* are removed. The card component stays.

### DO NOT delete `get_signal_feed()` or `get_signal_feed_count()` from `data.py`
These data functions are now called from `assets.py` instead of `signals.py`. The data layer is untouched.

### DO NOT remove `create_feed_signal_card` from the cards.py exports
It's used by the new asset detail signal feed.

### DO NOT remove the alert system stores or callbacks
The alert system (`callbacks/alerts.py`, `dcc.Store` objects for alerts, `alert-check-interval`) is completely independent of the page structure. It attaches to the offcanvas panel which lives in the root layout, not in any page.

### DO NOT remove the `suppress_callback_exceptions=True` setting
With the new routing, some callbacks (e.g., `asset-signal-sentiment-filter`) only exist when the asset page is rendered. `suppress_callback_exceptions=True` is required to prevent Dash from erroring when those components are not in the DOM.

### DO NOT remove CSS classes that might seem unused
The `.nav-link-custom` CSS, `.nav-links-row` responsive rules, etc. -- just add a TODO comment. Do not delete them in this PR. A separate CSS cleanup PR is safer.

### DO NOT break the `create_asset_page` function signature
It takes `symbol: str` as a parameter. The router passes the extracted symbol from the URL. Do not change this contract.

### DO NOT try to preserve the CSV export from signals.py
The CSV export was a nice-to-have on the standalone signals page. On the asset detail page, with a pre-filtered feed, it adds complexity. Skip it for now. If needed later, it can be added as a single button in the signal feed card header.

### DO NOT change `data.py`
This phase is purely a front-end restructuring. All data-fetching functions remain exactly as they are. No new queries, no query modifications, no schema changes.
