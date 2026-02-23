# Phase 05: Information Architecture Consolidation (4 Pages to 2 Views)

**Status:** ✅ COMPLETE
**Started:** 2026-02-23
**Completed:** 2026-02-23

**PR Title:** refactor: consolidate 4-page IA into 2-view architecture (Screener + Asset Detail)
**Risk Level:** High
**Estimated Effort:** High (3-5 days)
**Dependencies:** Phase 03 (Asset Screener Table), Phase 04 (Annotated Price Chart)

### Files Modified (7)
| File | Action |
|------|--------|
| `shitty_ui/layout.py` | **Modify** — remove `/signals`, `/trends`, `/performance` routes; remove nav highlighting callback; remove signal/trends callback registrations |
| `shitty_ui/components/header.py` | **Modify** — remove 4 nav links, simplify to logo-only navigation |
| `shitty_ui/pages/dashboard.py` | **Modify** — remove `create_performance_page()` and its callback; clean up unused imports |
| `shitty_ui/pages/assets.py` | **Modify** — update back link text ("Dashboard" → "Screener"), remove Performance link |
| `shitty_ui/pages/signals.py` | **Delete** — signal data accessible via asset detail prediction timeline |
| `shitty_ui/pages/trends.py` | **Delete** — replaced entirely by annotated chart on asset detail (Phase 04) |
| `shit_tests/shitty_ui/test_layout.py` | **Modify** — remove tests for deleted pages/nav-links, update route assertions |

### Files Deleted (1)
| File | Reason |
|------|--------|
| `shit_tests/shitty_ui/test_trends.py` | Page no longer exists |

### Files Created (1)
| File | Purpose |
|------|---------|
| `shit_tests/shitty_ui/test_information_architecture.py` | New test file covering the 2-view routing, header simplification, and back link |

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
| `/signals` | Filtered signal card feed, CSV export, "Load More" pagination | Asset Detail already has Prediction Timeline with same data. CSV export and pagination dropped (low-value). |
| `/trends` | Signal-over-trend chart, signal summary stats | Asset Detail page (replaced by Phase 04 annotated chart + signal summary stats) |
| `/performance` | Backtest KPI row (5 cards), Accuracy by Confidence chart, Sentiment donut, Per-Asset performance table | Per-Asset table → replaced by screener table. Confidence/Sentiment charts → removed (data accessible via screener sort). Backtest KPI → removed (screener surfaces per-asset P&L/win rate). |

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
                           + Latest Posts feed (existing)
                           + Collapsible raw data table (existing)
                           + Footer

/assets/<symbol>        -> Back breadcrumb ("< Screener")
                           + Asset stat cards (existing 4-card row)
                           + Annotated Price Chart (Phase 04) + Performance Summary sidebar
                           + Signal summary stats (existing, Phase 04)
                           + Prediction Timeline (existing, consolidated view)
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

#### ~~4c. Add a Backtest Summary Strip to the Home Page~~

**REMOVED** (challenge round decision): The screener table already surfaces per-asset P&L and win rate. A separate backtest simulation query on every page load adds latency without enough value. Removed from scope.

**Clean up unused imports in `dashboard.py`:** After deleting `create_performance_page()` and `update_performance_page()`, remove any imports that are no longer used (e.g., `get_backtest_simulation`, `get_sentiment_accuracy`, `get_accuracy_by_confidence`, `get_accuracy_by_asset`, `go`, etc.). Run ruff to confirm.

### ~~Step 5: Integrate Signal Feed into Asset Detail~~

**REMOVED** (challenge round decision): The asset detail page already has a "Prediction Timeline" section that shows all predictions for this asset with sentiment, confidence, outcome, and returns. Adding a second signal feed using `create_feed_signal_card` would duplicate the same data in a different card format. The existing prediction timeline is the single consolidated view for per-asset prediction data. No changes needed to `assets.py` beyond what Steps 2 and 6 cover.

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

### Step 7: Dead CSS in `layout.py` index_string

Several CSS classes are now unused (`.nav-link-custom`, `.nav-links-row`, their responsive rules). These are harmless dead code — leave them as-is. No TODO comments needed. A future CSS cleanup pass can identify and remove dead rules through inspection.

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


class TestAssetDetailBackLink:
    """Test the back link on the asset detail page."""

    def test_asset_page_back_link_says_screener(self):
        """Back link should say 'Screener' not 'Dashboard'."""
        from pages.assets import create_asset_header
        header = create_asset_header("XLE")
        # Search for text "Screener"
        pass

    def test_asset_page_no_performance_link(self):
        """Back link row should not have a Performance link."""
        from pages.assets import create_asset_header
        header = create_asset_header("XLE")
        # Should not contain "Performance" text or /performance href
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
- [ ] Navigate to `/` -- shows Screener home page with KPI row, screener table, posts feed
- [ ] Navigate to `/assets/XLE` -- shows asset detail with chart, stat cards, prediction timeline, related assets
- [ ] Navigate to `/signals` -- gracefully shows home page (not a 404)
- [ ] Navigate to `/trends` -- gracefully shows home page (not a 404)
- [ ] Navigate to `/performance` -- gracefully shows home page (not a 404)
- [ ] Header shows only logo, alert bell, refresh indicator (no nav links)
- [ ] Logo click from asset detail returns to home
- [ ] Back breadcrumb on asset detail says "Screener" and links to `/`
- [ ] Alert bell opens alert config offcanvas (unchanged behavior)
- [ ] Refresh countdown timer still works
- [ ] Prediction timeline on asset detail still loads cards correctly
- [ ] Mobile (375px): header doesn't clip, content stacks properly
- [ ] `source venv/bin/activate && pytest shit_tests/shitty_ui/ -v` -- all tests pass
- [ ] `ruff check shitty_ui/` -- no lint errors

---

## "What NOT To Do" Section

### DO NOT delete components/cards.py functions or data.py functions
Even though `signals.py` is deleted, the card components and data functions remain in place. They are not called by any current page, but removing them from the module would be a separate cleanup task. This phase is a front-end route restructuring — the data layer and component library are untouched.

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
