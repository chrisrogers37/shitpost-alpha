Now I have everything I need. Let me compose the comprehensive Phase 11 plan.

# Phase 11: Dashboard Information Architecture Redesign

## Header

| Field | Value |
|---|---|
| **PR Title** | `feat(ui): redesign dashboard IA with tabbed analytics, collapsible sections, and streamlined layout` |
| **Risk Level** | Medium (structural layout changes to the main dashboard page, callback output signature changes, new component IDs) |
| **Estimated Effort** | Medium-Large (4-6 hours implementation + tests) |
| **Files Modified** | `shitty_ui/pages/dashboard.py`, `shitty_ui/layout.py`, `shit_tests/shitty_ui/test_layout.py`, `CHANGELOG.md` |
| **Files Created** | None |
| **Files Deleted** | None |

---

## 1. Context

### The Problem: Information Overload

The main dashboard (`/`) attempts to display everything at once. From top to bottom, the current page contains:

1. Time Period Selector
2. Hero Signals Section (active high-confidence signals)
3. KPI Metrics Row (4 cards)
4. Full-width "Accuracy Over Time" chart in its own `dbc.Card`
5. Two-column layout:
   - Left (7-col): "Accuracy by Confidence" chart card + "Performance by Asset" chart card
   - Right (5-col): "Recent Predictions" sidebar card + "Asset Deep Dive" card with dropdown
6. Full-width "Latest Posts" feed card
7. Collapsible "Full Prediction Data" table card (no chevron icon, just a link-styled button)
8. Collapsible "Alert History" panel (no chevron icon)
9. Footer

This creates several user experience problems:

**Problem 1: Three chart sections occupy separate cards, creating visual noise.** The "Accuracy Over Time" chart (lines 117-143) sits in its own full-width card. The "Accuracy by Confidence" and "Performance by Asset" charts (lines 151-219) sit in a 7-column container below it. These are all analytics charts that tell related stories, yet they are presented as three disconnected sections, taking up ~800px of vertical space before the user reaches the "Latest Posts" feed.

**Problem 2: The Asset Deep Dive section is redundant.** The "Asset Deep Dive" card (lines 261-296) contains a dropdown to select an asset and view historical predictions. This functionality is fully replicated -- and better implemented -- on the dedicated `/assets/<ticker>` page, which was built specifically for this purpose. The Asset Deep Dive section on the dashboard adds UI clutter for minimal value.

**Problem 3: Collapsed sections have no visual affordance.** The "Full Prediction Data" card (lines 343-379) uses a `dbc.Button` with `color="link"` as the toggle, but there is no chevron icon or visual indicator that the section is collapsible or what state it is in (expanded vs. collapsed). The same applies to the "Alert History" panel (created by `create_alert_history_panel()` in `/Users/chris/Projects/shitpost-alpha/shitty_ui/callbacks/alerts.py` lines 607-646). Users have no visual cue that these sections can be expanded.

**Problem 4: "Latest Posts" is pushed far below the fold.** The primary content most users care about -- what Trump actually posted and what the LLM said about it -- requires scrolling past three chart sections, a sidebar, and the Asset Deep Dive to reach. On a typical 1080p screen, the Latest Posts feed starts approximately 1200-1400px below the top of the page.

**Problem 5: The alert history panel lives on the dashboard.** Alert history is a configuration/notification concern, not a dashboard analytics concern. It already has a natural home in the alert configuration offcanvas panel (the bell icon slide-out at `/Users/chris/Projects/shitpost-alpha/shitty_ui/callbacks/alerts.py` lines 17-604).

### Current Dashboard Layout (lines 42-388 of `dashboard.py`)

```
+----------------------------------------------------------+
| Header / Nav                                              |
+----------------------------------------------------------+
| Time Period: [7D] [30D] [90D] [All]                      |
+----------------------------------------------------------+
| ACTIVE SIGNALS (hero cards, horizontal flex)              |
+----------------------------------------------------------+
| [ KPI ] [ KPI ] [ KPI ] [ KPI ]                          |
+----------------------------------------------------------+
| Prediction Accuracy Over Time (full-width chart card)     |
|   [Line chart with 50% baseline]                          |
+----------------------------------------------------------+
| Accuracy by Confidence    |  Recent Predictions           |
|   [Bar chart]             |    [scrollable signal list]   |
| Performance by Asset      |  Asset Deep Dive              |
|   [Bar chart]             |    [dropdown + drilldown]     |
+----------------------------------------------------------+
| Latest Posts                                              |
|   [scrollable post feed, max-height 600px]                |
+----------------------------------------------------------+
| > Full Prediction Data  (collapsed, no chevron)           |
+----------------------------------------------------------+
| > Alert History  (collapsed, no chevron)                  |
+----------------------------------------------------------+
| Footer                                                    |
+----------------------------------------------------------+
```

### Desired Dashboard Layout

```
+----------------------------------------------------------+
| Header / Nav                                              |
+----------------------------------------------------------+
| Time Period: [7D] [30D] [90D] [All]                      |
+----------------------------------------------------------+
| ACTIVE SIGNALS (hero cards, horizontal flex)              |
+----------------------------------------------------------+
| [ KPI ] [ KPI ] [ KPI ] [ KPI ]                          |
+----------------------------------------------------------+
| Analytics                                                 |
|  [Accuracy] [By Confidence] [By Asset]   <- tab nav      |
|  +----------------------------------------------+        |
|  | <currently selected chart>                    |        |
|  +----------------------------------------------+        |
+----------------------------------------------------------+
| Recent Predictions         | Latest Posts                 |
|   [scrollable list, 5-col] |   [scrollable feed, 7-col]  |
+----------------------------------------------------------+
| v Full Prediction Data  (collapsed, with chevron)         |
+----------------------------------------------------------+
| Footer                                                    |
+----------------------------------------------------------+
```

**Key changes:**
1. Three chart cards consolidated into a single "Analytics" card with `dbc.Tabs` and three `dbc.Tab` panes
2. Asset Deep Dive section removed (users can click any asset bar in the "By Asset" tab to navigate to `/assets/<ticker>`)
3. Recent Predictions and Latest Posts placed side-by-side (swapping column order: posts get 7-col, predictions get 5-col, since posts are now the more valuable content)
4. Alert History panel removed from dashboard (it already lives in the alert config offcanvas)
5. Collapsible sections get chevron icons that rotate on expand/collapse
6. "Latest Posts" moves up from position 6 to position 5, immediately visible after the analytics tabs

### Files Modification Boundaries

This phase modifies only:
- `shitty_ui/pages/dashboard.py` -- Layout structure in `create_dashboard_page()` and callback changes in `register_dashboard_callbacks()`
- `shitty_ui/layout.py` -- Add CSS for the tab interface and chevron animation

Files **not** modified:
- `data.py` (modified by Phases 04 and 09)
- `components/cards.py` (modified by Phases 05, 06, 07)
- `constants.py` (modified by Phases 07, 10)
- `components/header.py` (modified by Phases 01, 10)
- `callbacks/alerts.py` (the alert history panel function remains, but is no longer called from the dashboard layout)

---

## 2. Dependencies

| Dependency | Status | Required? |
|---|---|---|
| Phase 01 (Label Countdown Timer) | Batch 1 | No (modifies `header.py`, not `dashboard.py` layout) |
| Phase 02 (Trends Auto-Select) | Batch 1 | No (modifies `pages/trends.py`) |
| Phase 03 (Fix Signals Page) | Batch 1 | No (modifies `pages/signals.py`) |
| Phase 04 (Fix Duplicate Signals) | Batch 2 | **Yes** -- modifies `dashboard.py` (hero section, data imports) and `data.py` |
| Phase 05 (Strip URLs from Cards) | Batch 2 | No (modifies `components/cards.py`) |
| Phase 06 (Consistent Confidence) | Batch 2 | No (modifies `components/cards.py`) |
| Phase 07 (Sentiment Visual Differentiation) | Batch 3 | No (modifies `cards.py`, `constants.py`) |
| Phase 08 (Smart Empty States) | Batch 3 | **Yes** -- modifies `dashboard.py` (empty state handling within the layout) |
| Phase 09 (Unify Dashboard KPIs) | Batch 3 | **Yes** -- modifies `dashboard.py` (KPI metrics section) and `data.py` |
| Phase 10 (Visual Hierarchy & Typography) | Batch 4 | **Yes** -- modifies `layout.py` CSS (adds typography classes used by this phase) and `header.py` |
| All prior phases | Batches 1-4 | **Required** -- This phase restructures `dashboard.py` which is touched by Phases 04, 08, and 09 |

**Batch**: 5 (must wait for ALL previous batches to complete).

**Line number note**: All line numbers in this document reference the current state of `main` (commit `6e5df67`). After Phases 04, 08, and 09 merge, line numbers in `dashboard.py` will be significantly offset. The code patterns (function names, variable names, component IDs, callback signatures) are unambiguous regardless of offset. Where possible, insertion points are described by reference to surrounding code structures rather than exact line numbers.

---

## 3. Detailed Implementation Plan

### 3.1 Add Tab and Chevron CSS to `layout.py`

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/layout.py`

**Insert location**: Inside the `<style>` block of `app.index_string`. After the typography classes added by Phase 10 (which are inserted before the `</style>` tag), append additional CSS for the tab interface and chevron animation.

If Phase 10 is not yet merged, insert after the scrollbar styling (currently lines 182-185), before the closing `</style>` tag.

**Code to add (append before `</style>`):**

```css

            /* ======================================
               Analytics tab interface
               ====================================== */
            .analytics-tabs .nav-tabs {
                border-bottom: 1px solid #334155;
                background-color: transparent;
            }
            .analytics-tabs .nav-link {
                color: #94a3b8 !important;
                border: none !important;
                border-bottom: 2px solid transparent !important;
                background-color: transparent !important;
                padding: 10px 20px;
                font-size: 0.9rem;
                font-weight: 500;
                transition: all 0.15s ease;
            }
            .analytics-tabs .nav-link:hover {
                color: #f1f5f9 !important;
                border-bottom-color: #475569 !important;
            }
            .analytics-tabs .nav-link.active {
                color: #3b82f6 !important;
                border-bottom-color: #3b82f6 !important;
                background-color: transparent !important;
            }
            .analytics-tabs .tab-content {
                padding-top: 16px;
            }

            /* ======================================
               Collapsible section chevrons
               ====================================== */
            .collapse-toggle-btn {
                display: flex;
                align-items: center;
                gap: 8px;
                width: 100%;
                text-align: left;
            }
            .collapse-chevron {
                transition: transform 0.2s ease;
                font-size: 0.8rem;
            }
            .collapse-chevron.rotated {
                transform: rotate(90deg);
            }
```

**Why these specific CSS rules:**
- The `.analytics-tabs` wrapper class scopes the tab styling to only the analytics section, preventing interference with any future `dbc.Tabs` usage elsewhere.
- Tab styling follows the dark theme: muted text by default, blue accent on active, transparent background. The `!important` overrides are necessary because Bootstrap DARKLY theme applies its own nav-tab styles with moderate specificity.
- The `.collapse-chevron.rotated` class uses a CSS transition for smooth rotation of the chevron icon when sections are expanded/collapsed. A clientside callback (section 3.5) toggles this class.

### 3.2 Add `dbc.Tabs` Import to `layout.py`

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/layout.py`

**Current imports (line 14):**
```python
import dash_bootstrap_components as dbc
```

No additional import needed -- `dbc.Tabs` and `dbc.Tab` are already available from `dash_bootstrap_components`. Confirm by checking that `dbc.Tabs` is used without any separate import in the codebase.

### 3.3 Restructure `create_dashboard_page()` Layout

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard.py`

This is the core layout change. The `create_dashboard_page()` function (currently lines 42-388) must be rewritten to implement the new information architecture.

**BEFORE (lines 42-388)** -- the full function as shown in the file read above.

**AFTER** -- replace the entire function body. The key structural changes are:

1. Keep: Time Period Selector (lines 52-102) -- unchanged
2. Keep: Hero Signals Section (lines 103-108) -- unchanged
3. Keep: KPI Metrics Row (lines 109-115) -- unchanged
4. **REPLACE**: Three separate chart sections (lines 117-305) with a single tabbed card
5. **REPLACE**: Two-column layout: swap positions, remove Asset Deep Dive, promote Latest Posts
6. **MODIFY**: Full Prediction Data collapse (lines 342-379) -- add chevron icon
7. **REMOVE**: Alert History panel call (line 381)
8. Keep: Footer (line 383) -- unchanged

```python
def create_dashboard_page() -> html.Div:
    """Create the main dashboard page layout (shown at /)."""
    return html.Div(
        [
            # Header with navigation
            create_header(),
            # Main content container
            html.Div(
                [
                    # Time Period Selector Row
                    html.Div(
                        [
                            html.Span(
                                "Time Period: ",
                                style={
                                    "color": COLORS["text_muted"],
                                    "marginRight": "10px",
                                    "fontSize": "0.9rem",
                                },
                            ),
                            dbc.ButtonGroup(
                                [
                                    dbc.Button(
                                        "7D",
                                        id="period-7d",
                                        color="secondary",
                                        outline=True,
                                        size="sm",
                                    ),
                                    dbc.Button(
                                        "30D",
                                        id="period-30d",
                                        color="secondary",
                                        outline=True,
                                        size="sm",
                                    ),
                                    dbc.Button(
                                        "90D",
                                        id="period-90d",
                                        color="primary",
                                        size="sm",
                                    ),
                                    dbc.Button(
                                        "All",
                                        id="period-all",
                                        color="secondary",
                                        outline=True,
                                        size="sm",
                                    ),
                                ],
                                size="sm",
                            ),
                        ],
                        className="period-selector",
                        style={
                            "marginBottom": "20px",
                            "display": "flex",
                            "alignItems": "center",
                            "justifyContent": "flex-end",
                        },
                    ),
                    # Hero Section: Active High-Confidence Signals
                    dcc.Loading(
                        type="default",
                        color=COLORS["accent"],
                        children=html.Div(id="hero-signals-section", className="mb-4"),
                    ),
                    # Key Metrics Row
                    dcc.Loading(
                        id="performance-metrics-loading",
                        type="default",
                        color=COLORS["accent"],
                        children=html.Div(id="performance-metrics", className="mb-4"),
                    ),
                    # ========== Analytics Section: Tabbed Charts ==========
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                [
                                    html.I(className="fas fa-chart-line me-2"),
                                    "Analytics",
                                ],
                                className="fw-bold",
                                style={"backgroundColor": COLORS["secondary"]},
                            ),
                            dbc.CardBody(
                                [
                                    dbc.Tabs(
                                        [
                                            dbc.Tab(
                                                dcc.Loading(
                                                    type="circle",
                                                    color=COLORS["accent"],
                                                    children=dcc.Graph(
                                                        id="accuracy-over-time-chart",
                                                        config={"displayModeBar": False},
                                                    ),
                                                ),
                                                label="Accuracy Over Time",
                                                tab_id="tab-accuracy",
                                            ),
                                            dbc.Tab(
                                                dcc.Loading(
                                                    type="circle",
                                                    color=COLORS["accent"],
                                                    children=dcc.Graph(
                                                        id="confidence-accuracy-chart",
                                                        config={"displayModeBar": False},
                                                    ),
                                                ),
                                                label="By Confidence",
                                                tab_id="tab-confidence",
                                            ),
                                            dbc.Tab(
                                                dcc.Loading(
                                                    type="circle",
                                                    color=COLORS["accent"],
                                                    children=dcc.Graph(
                                                        id="asset-accuracy-chart",
                                                        config={"displayModeBar": False},
                                                        style={"cursor": "pointer"},
                                                    ),
                                                ),
                                                label="By Asset",
                                                tab_id="tab-asset",
                                                children_class_name="pt-2",
                                            ),
                                        ],
                                        id="analytics-tabs",
                                        active_tab="tab-accuracy",
                                        className="analytics-tabs",
                                    ),
                                ],
                                style={"backgroundColor": COLORS["secondary"]},
                            ),
                        ],
                        className="mb-4",
                        style={"backgroundColor": COLORS["secondary"]},
                    ),
                    # ========== Two Column: Latest Posts + Recent Signals ==========
                    dbc.Row(
                        [
                            # Left column: Latest Posts (wider, primary content)
                            dbc.Col(
                                [
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
                                        style={"backgroundColor": COLORS["secondary"]},
                                    ),
                                ],
                                xs=12,
                                sm=12,
                                md=7,
                                lg=7,
                                xl=7,
                            ),
                            # Right column: Recent Predictions
                            dbc.Col(
                                [
                                    dbc.Card(
                                        [
                                            dbc.CardHeader(
                                                [
                                                    html.I(
                                                        className="fas fa-bolt me-2"
                                                    ),
                                                    "Recent Predictions",
                                                ],
                                                className="fw-bold",
                                            ),
                                            dbc.CardBody(
                                                [
                                                    dcc.Loading(
                                                        type="circle",
                                                        color=COLORS["accent"],
                                                        children=html.Div(
                                                            id="recent-signals-list",
                                                            style={
                                                                "maxHeight": "600px",
                                                                "overflowY": "auto",
                                                            },
                                                        ),
                                                    )
                                                ]
                                            ),
                                        ],
                                        style={"backgroundColor": COLORS["secondary"]},
                                    ),
                                ],
                                xs=12,
                                sm=12,
                                md=5,
                                lg=5,
                                xl=5,
                            ),
                        ],
                        className="mb-4",
                    ),
                    # ========== Collapsible Full Data Table ==========
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                [
                                    dbc.Button(
                                        [
                                            html.I(
                                                className="fas fa-chevron-right me-2 collapse-chevron",
                                                id="collapse-table-chevron",
                                            ),
                                            html.I(className="fas fa-table me-2"),
                                            "Full Prediction Data",
                                        ],
                                        id="collapse-table-button",
                                        color="link",
                                        className="text-white fw-bold p-0 collapse-toggle-btn",
                                    ),
                                ],
                                className="fw-bold",
                            ),
                            dbc.Collapse(
                                dbc.CardBody(
                                    [
                                        create_filter_controls(),
                                        dcc.Loading(
                                            type="default",
                                            color=COLORS["accent"],
                                            children=html.Div(
                                                id="predictions-table-container",
                                                className="mt-3",
                                            ),
                                        ),
                                    ]
                                ),
                                id="collapse-table",
                                is_open=False,
                            ),
                        ],
                        className="mb-4",
                        style={"backgroundColor": COLORS["secondary"]},
                    ),
                    # Footer
                    create_footer(),
                ],
                style={"padding": "20px", "maxWidth": "1400px", "margin": "0 auto"},
            ),
        ]
    )
```

**Summary of structural changes from the original:**

| Original Section | Original Lines | New State |
|---|---|---|
| Time Period Selector | 52-102 | **Unchanged** |
| Hero Signals Section | 103-108 | **Unchanged** |
| KPI Metrics Row | 109-115 | **Unchanged** |
| Accuracy Over Time chart card (full-width) | 117-143 | **Moved into** `dbc.Tab` tab_id="tab-accuracy" inside the new Analytics card |
| Two-column: Left charts + Right sidebar | 144-305 | **Removed** -- charts moved to tabs, sidebar restructured |
| Accuracy by Confidence chart card | 151-179 | **Moved into** `dbc.Tab` tab_id="tab-confidence" inside the new Analytics card |
| Performance by Asset chart card | 180-219 | **Moved into** `dbc.Tab` tab_id="tab-asset" inside the new Analytics card |
| Recent Predictions sidebar | 228-259 | **Moved** to right column (5-col) of new two-column layout below analytics |
| Asset Deep Dive card + dropdown | 260-296 | **Removed** -- users use `/assets/<ticker>` page or click bar chart |
| Latest Posts feed card | 306-341 | **Moved up** to left column (7-col) of new two-column layout, side by side with Recent Predictions |
| Full Prediction Data collapse | 342-379 | **Modified** -- added chevron icon with `id="collapse-table-chevron"`, added `collapse-toggle-btn` class |
| Alert History panel | 381 (`create_alert_history_panel()`) | **Removed** from dashboard layout |
| Footer | 383 | **Unchanged** |

**Critical IDs preserved** (these must remain for callbacks to work):
- `hero-signals-section`
- `performance-metrics`
- `accuracy-over-time-chart`
- `confidence-accuracy-chart`
- `asset-accuracy-chart`
- `recent-signals-list`
- `post-feed-container`
- `collapse-table-button`
- `collapse-table`
- `predictions-table-container`
- `collapse-table-chevron` (new)
- `analytics-tabs` (new)

**IDs removed** (callbacks referencing these must be updated or removed):
- `asset-selector` (the dropdown for Asset Deep Dive) -- callback `update_asset_drilldown` references this
- `asset-drilldown-content` (the drilldown output) -- callback `update_asset_drilldown` references this

### 3.4 Update `update_dashboard()` Callback to Remove Asset Selector Output

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard.py`

The `update_dashboard()` callback (lines 586-948) currently has 8 outputs, including `Output("asset-selector", "options")`. Since the Asset Deep Dive section is removed, this output and its data fetching must be removed.

**BEFORE (lines 586-601, callback decorator):**
```python
    @app.callback(
        [
            Output("hero-signals-section", "children"),
            Output("performance-metrics", "children"),
            Output("accuracy-over-time-chart", "figure"),
            Output("confidence-accuracy-chart", "figure"),
            Output("asset-accuracy-chart", "figure"),
            Output("recent-signals-list", "children"),
            Output("asset-selector", "options"),
            Output("last-update-timestamp", "data"),
        ],
        [
            Input("refresh-interval", "n_intervals"),
            Input("selected-period", "data"),
        ],
    )
```

**AFTER:**
```python
    @app.callback(
        [
            Output("hero-signals-section", "children"),
            Output("performance-metrics", "children"),
            Output("accuracy-over-time-chart", "figure"),
            Output("confidence-accuracy-chart", "figure"),
            Output("asset-accuracy-chart", "figure"),
            Output("recent-signals-list", "children"),
            Output("last-update-timestamp", "data"),
        ],
        [
            Input("refresh-interval", "n_intervals"),
            Input("selected-period", "data"),
        ],
    )
```

The `Output("asset-selector", "options")` is removed (7th output).

**Update the return statement** at the end of `update_dashboard()`.

**BEFORE (lines 939-948):**
```python
        return (
            hero_section,
            metrics_row,
            acc_fig,
            conf_fig,
            asset_fig,
            signal_cards,
            asset_options,
            current_time,
        )
```

**AFTER:**
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

**Also remove the asset selector data fetch block** (lines 924-933):

**BEFORE (lines 924-933):**
```python
        # ===== Asset Selector Options with error handling =====
        try:
            active_assets = get_active_assets_from_db()
            asset_options = [
                {"label": asset, "value": asset} for asset in active_assets
            ]
        except Exception as e:
            errors.append(f"Asset options: {e}")
            print(f"Error loading asset options: {traceback.format_exc()}")
            asset_options = []
```

**AFTER:** Remove this entire block. Do not replace it.

**Also remove the `get_active_assets_from_db` import** from the top of `dashboard.py` if no other code in the file references it. Check: `get_active_assets_from_db` is imported at line 30 and used only in the asset selector block. After removing the asset selector block, the import is unused.

**BEFORE (lines 23-39, import from data):**
```python
from data import (
    get_recent_signals,
    get_performance_metrics,
    get_accuracy_by_confidence,
    get_accuracy_by_asset,
    get_similar_predictions,
    get_predictions_with_outcomes,
    get_active_assets_from_db,
    load_recent_posts,
    get_active_signals,
    get_weekly_signal_count,
    get_high_confidence_metrics,
    get_best_performing_asset,
    get_accuracy_over_time,
    get_backtest_simulation,
    get_sentiment_accuracy,
)
```

**AFTER (remove `get_active_assets_from_db` and `get_similar_predictions`):**
```python
from data import (
    get_recent_signals,
    get_performance_metrics,
    get_accuracy_by_confidence,
    get_accuracy_by_asset,
    get_predictions_with_outcomes,
    load_recent_posts,
    get_active_signals,
    get_weekly_signal_count,
    get_high_confidence_metrics,
    get_best_performing_asset,
    get_accuracy_over_time,
    get_backtest_simulation,
    get_sentiment_accuracy,
)
```

Note: After Phase 09 merges, `get_dashboard_kpis` will also be in this import list. Keep it. The removals are:
- `get_active_assets_from_db` -- only used by the removed asset selector
- `get_similar_predictions` -- only used by the removed `update_asset_drilldown` callback

### 3.5 Remove the `update_asset_drilldown` Callback

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard.py`

The `update_asset_drilldown` callback (lines 1002-1206) references `asset-selector` and `asset-drilldown-content`, both of which no longer exist in the layout. This entire callback must be removed.

**BEFORE (lines 1002-1206):**
```python
    @app.callback(
        Output("asset-drilldown-content", "children"),
        [Input("asset-selector", "value")],
    )
    def update_asset_drilldown(asset):
        """Update the asset deep dive section with error handling."""
        # ... entire function body ...
```

**AFTER:** Remove the entire `update_asset_drilldown` function (approximately 204 lines).

### 3.6 Add Chevron Toggle Clientside Callback

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard.py`

**Insert location**: Inside `register_dashboard_callbacks(app)`, after the existing `toggle_collapse` callback (currently lines 1208-1217). This new callback handles the chevron rotation animation.

**Existing toggle callback (lines 1208-1217):**
```python
    @app.callback(
        Output("collapse-table", "is_open"),
        [Input("collapse-table-button", "n_clicks")],
        [State("collapse-table", "is_open")],
    )
    def toggle_collapse(n_clicks, is_open):
        """Toggle the data table collapse."""
        if n_clicks:
            return not is_open
        return is_open
```

This callback remains unchanged. Add a new clientside callback immediately after it:

```python
    # Chevron rotation for collapsible sections
    app.clientside_callback(
        """
        function(isOpen) {
            if (isOpen) {
                return 'fas fa-chevron-right me-2 collapse-chevron rotated';
            }
            return 'fas fa-chevron-right me-2 collapse-chevron';
        }
        """,
        Output("collapse-table-chevron", "className"),
        [Input("collapse-table", "is_open")],
    )
```

**How it works:** When the `collapse-table` collapse component opens or closes (triggered by the existing `toggle_collapse` callback), this clientside callback updates the chevron icon's `className` to add or remove the `rotated` class. The CSS transition (defined in section 3.1) smoothly rotates the chevron from pointing right (collapsed) to pointing down (expanded).

### 3.7 Remove `create_alert_history_panel` Import from `dashboard.py`

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard.py`

**BEFORE (line 22):**
```python
from callbacks.alerts import create_alert_history_panel
```

**AFTER:** Remove this import line entirely.

Since `create_alert_history_panel` is no longer called from `create_dashboard_page()`, the import is unused. The function itself remains in `callbacks/alerts.py` (it is not deleted, just no longer called from the dashboard layout).

**Important**: The alert history panel's collapse callbacks still exist in `callbacks/alerts.py` (lines 1044-1055: `toggle_alert_history`, lines 1057-1178: `render_alert_history`). These callbacks reference `collapse-alert-history`, `collapse-alert-history-button`, `alert-history-content`, and `alert-history-count-badge` -- all IDs that were part of the `create_alert_history_panel()` component. Since the component is no longer rendered in the dashboard layout, these callbacks will receive no triggers (the components do not exist in the DOM). The `suppress_callback_exceptions=True` setting on the app (line 67 of `layout.py`) prevents errors from missing component IDs. These alert callbacks are not harmful to keep; they simply become dormant. However, if desired, the alert history panel could be moved into the alert config offcanvas in a future cleanup -- but that is out of scope for this phase (it would require modifying `callbacks/alerts.py`, which this phase does not touch).

### 3.8 Summary of All Changes

| File | Change Type | Location | Description |
|---|---|---|---|
| `layout.py` | **Append CSS** | Before `</style>` in `app.index_string` | Add `.analytics-tabs` tab styling, `.collapse-toggle-btn` and `.collapse-chevron` CSS |
| `dashboard.py` | **Remove import** | Line 22 | Remove `from callbacks.alerts import create_alert_history_panel` |
| `dashboard.py` | **Modify imports** | Lines 23-39 | Remove `get_active_assets_from_db` and `get_similar_predictions` from data imports |
| `dashboard.py` | **Rewrite function** | `create_dashboard_page()` (lines 42-388) | Consolidate charts into tabbed card, restructure two-column layout, remove Asset Deep Dive and Alert History, add chevron to collapsed sections |
| `dashboard.py` | **Modify callback** | `update_dashboard()` outputs (lines 586-601) | Remove `Output("asset-selector", "options")` (7 outputs instead of 8) |
| `dashboard.py` | **Modify callback** | `update_dashboard()` body (lines 924-933) | Remove asset selector data fetch block |
| `dashboard.py` | **Modify callback** | `update_dashboard()` return (lines 939-948) | Remove `asset_options` from return tuple (7 values instead of 8) |
| `dashboard.py` | **Remove callback** | `update_asset_drilldown()` (lines 1002-1206) | Remove entire function (~204 lines) |
| `dashboard.py` | **Add callback** | After `toggle_collapse()` | Add clientside callback for chevron rotation |

---

## 4. Test Plan

### Tests to add in `shit_tests/shitty_ui/test_layout.py`

All new tests should be added as new test classes after the existing test classes at the end of the file.

```python
class TestDashboardPageStructure:
    """Tests for the restructured dashboard page layout."""

    def test_create_dashboard_page_returns_div(self):
        """Test that create_dashboard_page returns an html.Div."""
        from pages.dashboard import create_dashboard_page
        from dash import html

        page = create_dashboard_page()
        assert isinstance(page, html.Div)

    def test_dashboard_contains_analytics_tabs(self):
        """Test that dashboard contains dbc.Tabs with id 'analytics-tabs'."""
        from pages.dashboard import create_dashboard_page
        import dash_bootstrap_components as dbc

        page = create_dashboard_page()
        found_ids = _find_component_ids(page)
        assert "analytics-tabs" in found_ids, "analytics-tabs not found in dashboard page"

    def test_dashboard_contains_three_chart_ids(self):
        """Test that all three chart graph IDs are present in the tabbed layout."""
        from pages.dashboard import create_dashboard_page

        page = create_dashboard_page()
        found_ids = _find_component_ids(page)
        assert "accuracy-over-time-chart" in found_ids
        assert "confidence-accuracy-chart" in found_ids
        assert "asset-accuracy-chart" in found_ids

    def test_dashboard_does_not_contain_asset_selector(self):
        """Test that the Asset Deep Dive dropdown has been removed."""
        from pages.dashboard import create_dashboard_page

        page = create_dashboard_page()
        found_ids = _find_component_ids(page)
        assert "asset-selector" not in found_ids, (
            "asset-selector should be removed from dashboard"
        )

    def test_dashboard_does_not_contain_asset_drilldown(self):
        """Test that the asset drilldown content area has been removed."""
        from pages.dashboard import create_dashboard_page

        page = create_dashboard_page()
        found_ids = _find_component_ids(page)
        assert "asset-drilldown-content" not in found_ids, (
            "asset-drilldown-content should be removed from dashboard"
        )

    def test_dashboard_does_not_contain_alert_history(self):
        """Test that the alert history panel has been removed from dashboard."""
        from pages.dashboard import create_dashboard_page

        page = create_dashboard_page()
        found_ids = _find_component_ids(page)
        assert "collapse-alert-history" not in found_ids, (
            "Alert history collapse should be removed from dashboard"
        )
        assert "collapse-alert-history-button" not in found_ids, (
            "Alert history button should be removed from dashboard"
        )

    def test_dashboard_contains_post_feed(self):
        """Test that post-feed-container is present in the dashboard."""
        from pages.dashboard import create_dashboard_page

        page = create_dashboard_page()
        found_ids = _find_component_ids(page)
        assert "post-feed-container" in found_ids

    def test_dashboard_contains_recent_signals(self):
        """Test that recent-signals-list is present in the dashboard."""
        from pages.dashboard import create_dashboard_page

        page = create_dashboard_page()
        found_ids = _find_component_ids(page)
        assert "recent-signals-list" in found_ids

    def test_dashboard_contains_collapse_chevron(self):
        """Test that the collapse section has a chevron icon."""
        from pages.dashboard import create_dashboard_page

        page = create_dashboard_page()
        found_ids = _find_component_ids(page)
        assert "collapse-table-chevron" in found_ids, (
            "collapse-table-chevron not found in dashboard page"
        )

    def test_collapse_chevron_has_correct_initial_class(self):
        """Test that the chevron starts with collapse-chevron class (not rotated)."""
        from pages.dashboard import create_dashboard_page
        from dash import html

        page = create_dashboard_page()
        chevron = _find_component_by_id(page, "collapse-table-chevron")
        assert chevron is not None, "Could not find collapse-table-chevron component"
        assert "collapse-chevron" in (chevron.className or "")
        assert "rotated" not in (chevron.className or "")

    def test_dashboard_preserves_hero_signals_section(self):
        """Test that hero-signals-section is still present."""
        from pages.dashboard import create_dashboard_page

        page = create_dashboard_page()
        found_ids = _find_component_ids(page)
        assert "hero-signals-section" in found_ids

    def test_dashboard_preserves_performance_metrics(self):
        """Test that performance-metrics is still present."""
        from pages.dashboard import create_dashboard_page

        page = create_dashboard_page()
        found_ids = _find_component_ids(page)
        assert "performance-metrics" in found_ids

    def test_dashboard_preserves_collapse_table(self):
        """Test that the collapsible data table is still present."""
        from pages.dashboard import create_dashboard_page

        page = create_dashboard_page()
        found_ids = _find_component_ids(page)
        assert "collapse-table" in found_ids
        assert "collapse-table-button" in found_ids
        assert "predictions-table-container" in found_ids


class TestAnalyticsTabsCSS:
    """Tests for analytics tab CSS in the app stylesheet."""

    @patch("data.get_prediction_stats")
    @patch("layout.get_performance_metrics")
    @patch("layout.get_accuracy_by_confidence")
    @patch("layout.get_accuracy_by_asset")
    @patch("layout.get_recent_signals")
    @patch("layout.get_active_assets_from_db")
    def test_index_string_contains_analytics_tabs_css(
        self, mock_assets, mock_signals, mock_asset_acc, mock_conf_acc, mock_perf, mock_stats,
    ):
        """Test that app index_string contains .analytics-tabs CSS."""
        mock_stats.return_value = {"total_posts": 0, "analyzed_posts": 0, "completed_analyses": 0, "bypassed_posts": 0, "avg_confidence": 0.0, "high_confidence_predictions": 0}
        mock_perf.return_value = {"total_outcomes": 0, "evaluated_predictions": 0, "correct_predictions": 0, "incorrect_predictions": 0, "accuracy_t7": 0.0, "avg_return_t7": 0.0, "total_pnl_t7": 0.0, "avg_confidence": 0.0}
        mock_conf_acc.return_value = pd.DataFrame()
        mock_asset_acc.return_value = pd.DataFrame()
        mock_signals.return_value = pd.DataFrame()
        mock_assets.return_value = []

        from layout import create_app
        app = create_app()

        assert ".analytics-tabs" in app.index_string
        assert ".collapse-chevron" in app.index_string
        assert ".collapse-chevron.rotated" in app.index_string

    @patch("data.get_prediction_stats")
    @patch("layout.get_performance_metrics")
    @patch("layout.get_accuracy_by_confidence")
    @patch("layout.get_accuracy_by_asset")
    @patch("layout.get_recent_signals")
    @patch("layout.get_active_assets_from_db")
    def test_index_string_contains_collapse_toggle_css(
        self, mock_assets, mock_signals, mock_asset_acc, mock_conf_acc, mock_perf, mock_stats,
    ):
        """Test that app index_string contains .collapse-toggle-btn CSS."""
        mock_stats.return_value = {"total_posts": 0, "analyzed_posts": 0, "completed_analyses": 0, "bypassed_posts": 0, "avg_confidence": 0.0, "high_confidence_predictions": 0}
        mock_perf.return_value = {"total_outcomes": 0, "evaluated_predictions": 0, "correct_predictions": 0, "incorrect_predictions": 0, "accuracy_t7": 0.0, "avg_return_t7": 0.0, "total_pnl_t7": 0.0, "avg_confidence": 0.0}
        mock_conf_acc.return_value = pd.DataFrame()
        mock_asset_acc.return_value = pd.DataFrame()
        mock_signals.return_value = pd.DataFrame()
        mock_assets.return_value = []

        from layout import create_app
        app = create_app()

        assert ".collapse-toggle-btn" in app.index_string
```

**Helper functions to add** (at module level, near the existing helpers). The `_find_component_ids` helper may already exist if Phase 10 was merged. If not, add it:

```python
def _find_component_ids(component):
    """Recursively collect all component IDs from a Dash component tree."""
    ids = set()
    comp_id = getattr(component, "id", None)
    if comp_id:
        ids.add(comp_id)

    children = getattr(component, "children", None)
    if children is None:
        return ids
    if isinstance(children, (list, tuple)):
        for child in children:
            if hasattr(child, "children") or hasattr(child, "id"):
                ids.update(_find_component_ids(child))
    elif hasattr(children, "children") or hasattr(children, "id"):
        ids.update(_find_component_ids(children))
    return ids


def _find_component_by_id(component, target_id):
    """Recursively find a component by its ID in a Dash component tree."""
    comp_id = getattr(component, "id", None)
    if comp_id == target_id:
        return component

    children = getattr(component, "children", None)
    if children is None:
        return None
    if isinstance(children, (list, tuple)):
        for child in children:
            if hasattr(child, "children") or hasattr(child, "id"):
                result = _find_component_by_id(child, target_id)
                if result is not None:
                    return result
    elif hasattr(children, "children") or hasattr(children, "id"):
        result = _find_component_by_id(children, target_id)
        if result is not None:
            return result
    return None
```

### How to Run Tests

```bash
source venv/bin/activate && pytest shit_tests/shitty_ui/test_layout.py -v -k "DashboardPageStructure or AnalyticsTabsCSS"
```

### Existing Tests That Must Still Pass

The following existing tests must not regress:
- `TestCreateApp` -- app creation is unchanged
- `TestCreateHeader` -- header is unchanged
- `TestCreateFilterControls` -- filter controls still present in the collapse section
- `TestCreateFooter` -- footer still present
- `TestCreateMetricCard` -- metric card component unchanged
- `TestCreateSignalCard` -- signal card component unchanged
- `TestRegisterCallbacks` -- callbacks still registered (minus the removed one)
- `TestPeriodButtonStyles` -- period buttons unchanged

Full UI test suite:
```bash
source venv/bin/activate && pytest shit_tests/shitty_ui/ -v
```

---

## 5. Documentation Updates

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Changed
- **Dashboard information architecture redesign** - Streamlined the main dashboard layout for faster scanning and reduced information overload
  - Consolidated three separate chart sections (Accuracy Over Time, Accuracy by Confidence, Performance by Asset) into a single tabbed "Analytics" card with three switchable views
  - Moved "Latest Posts" feed up to a prominent side-by-side position with "Recent Predictions," visible without excessive scrolling
  - Added chevron icons with rotation animation to collapsible sections for clear expand/collapse affordance

### Removed
- **Asset Deep Dive section** from the main dashboard (functionality lives on the dedicated `/assets/<ticker>` page; users can click any asset bar chart to navigate there)
- **Alert History panel** from the main dashboard (accessible via the alert configuration bell icon panel)
```

---

## 6. Edge Cases

| # | Edge Case | Risk | Mitigation |
|---|---|---|---|
| 1 | **Tabs do not render charts until tab is selected** | Low | All three `dcc.Graph` components are present in the DOM from initial render (each inside a `dbc.Tab`). The `update_dashboard` callback populates all three figures on every refresh. `dbc.Tabs` hides non-active tabs via CSS `display: none`, but the chart data is still set. When the user clicks a tab, the pre-populated chart is instantly visible. No lazy-loading concern. |
| 2 | **Chart click handler for asset-accuracy-chart still works inside tab** | None | The `handle_asset_chart_click` callback (lines 981-1000) listens to `Input("asset-accuracy-chart", "clickData")`. The graph ID is unchanged; it is merely repositioned inside a `dbc.Tab`. Dash callbacks bind by ID regardless of DOM nesting. Click-to-navigate behavior is preserved. |
| 3 | **Alert history callbacks reference removed components** | None | `suppress_callback_exceptions=True` (line 67 of `layout.py`) handles missing component IDs gracefully. The alert history callbacks in `callbacks/alerts.py` will simply not fire since their trigger components are not in the DOM. No errors will be logged. |
| 4 | **Mobile layout with tabs** | Low | `dbc.Tabs` from dash-bootstrap-components is responsive by default. On narrow screens, tab labels will wrap or become scrollable. The `.analytics-tabs .nav-link` CSS uses `padding: 10px 20px` which is compact enough for three tabs on a 375px viewport. Test on mobile to confirm. |
| 5 | **Tests patching `update_asset_drilldown` or `asset-selector`** | Low | Search existing tests for `asset-selector` and `asset-drilldown-content`. The `test_layout.py` file does not contain tests specifically for the asset drilldown callback. If any test references `Output("asset-selector", "options")`, it will need updating. Based on reading the test file, no such test exists. |
| 6 | **Existing collapse callbacks for predictions table** | None | The `toggle_collapse` callback and `update_predictions_table` callback are unchanged. Their IDs (`collapse-table`, `collapse-table-button`, `predictions-table-container`) are preserved in the new layout. The only addition is the `collapse-table-chevron` ID inside the button, which does not affect existing callbacks. |
| 7 | **Chevron rotation not synced on page load** | None | The `collapse-table` starts with `is_open=False`. The clientside callback fires on initial value, returning the non-rotated class. The chevron starts as a right-pointing arrow, correctly indicating "click to expand." |
| 8 | **Performance page (`/performance`) unaffected** | None | The `create_performance_page()` function (lines 391-513) and `update_performance_page()` callback (lines 1346-1669) are not modified. They use separate component IDs (`perf-confidence-chart`, `perf-sentiment-chart`, `perf-asset-table`, `backtest-header`). |
| 9 | **Post feed callback still works** | None | The `update_post_feed` callback (lines 950-978) references `Output("post-feed-container", "children")`, which is preserved in the new layout. The component has simply been moved from a standalone section to the left column of the two-column layout. |
| 10 | **`dbc.Tabs` not imported** | None | `dbc.Tabs` and `dbc.Tab` are part of `dash_bootstrap_components`, already imported as `dbc` on line 7 of `dashboard.py`. No additional import needed. Verify with `import dash_bootstrap_components as dbc; dbc.Tabs`. |

---

## 7. Verification Checklist

### Structure Verification
- [ ] `create_dashboard_page()` returns a layout containing `dbc.Tabs` with `id="analytics-tabs"`
- [ ] The `dbc.Tabs` component contains exactly three `dbc.Tab` children with `tab_id` values: `"tab-accuracy"`, `"tab-confidence"`, `"tab-asset"`
- [ ] Each tab contains the correct `dcc.Graph` component: `accuracy-over-time-chart`, `confidence-accuracy-chart`, `asset-accuracy-chart`
- [ ] `active_tab` on the `dbc.Tabs` is set to `"tab-accuracy"` (Accuracy Over Time shown by default)
- [ ] The "Latest Posts" card is in a `dbc.Col` with `md=7` in the two-column `dbc.Row`
- [ ] The "Recent Predictions" card is in a `dbc.Col` with `md=5` in the two-column `dbc.Row`
- [ ] The Asset Deep Dive section (dropdown + drilldown) is completely removed from the layout
- [ ] The `create_alert_history_panel()` call is removed from the layout
- [ ] The `collapse-table-button` contains an `html.I` with `id="collapse-table-chevron"` and `className` including `"collapse-chevron"`

### Callback Verification
- [ ] `update_dashboard()` callback has 7 outputs (not 8 -- `asset-selector` options removed)
- [ ] `update_dashboard()` return tuple has 7 values (not 8 -- `asset_options` removed)
- [ ] The asset selector data fetch block is removed from `update_dashboard()`
- [ ] `update_asset_drilldown()` callback function is completely removed
- [ ] Chevron rotation clientside callback is added, targeting `Output("collapse-table-chevron", "className")`
- [ ] Chevron clientside callback input is `Input("collapse-table", "is_open")`
- [ ] `handle_asset_chart_click` callback is preserved (asset bar chart still navigates to `/assets/<ticker>`)

### Import Verification
- [ ] `from callbacks.alerts import create_alert_history_panel` is removed from `dashboard.py`
- [ ] `get_active_assets_from_db` is removed from the `data` import block in `dashboard.py`
- [ ] `get_similar_predictions` is removed from the `data` import block in `dashboard.py`
- [ ] No `import` changes in `layout.py` (no new imports needed)

### CSS Verification
- [ ] `layout.py` `app.index_string` contains `.analytics-tabs .nav-link` CSS
- [ ] `layout.py` `app.index_string` contains `.analytics-tabs .nav-link.active` CSS with blue border-bottom
- [ ] `layout.py` `app.index_string` contains `.collapse-chevron` CSS with transition
- [ ] `layout.py` `app.index_string` contains `.collapse-chevron.rotated` CSS with `transform: rotate(90deg)`
- [ ] `layout.py` `app.index_string` contains `.collapse-toggle-btn` CSS with flex layout

### Test Verification
- [ ] `source venv/bin/activate && pytest shit_tests/shitty_ui/test_layout.py -v -k "DashboardPageStructure"` passes (13 tests)
- [ ] `source venv/bin/activate && pytest shit_tests/shitty_ui/test_layout.py -v -k "AnalyticsTabsCSS"` passes (2 tests)
- [ ] `source venv/bin/activate && pytest shit_tests/shitty_ui/test_layout.py -v` passes (all existing + new tests)
- [ ] `source venv/bin/activate && pytest shit_tests/shitty_ui/ -v` passes (full UI test suite)

### Lint and Format
- [ ] `python3 -m ruff check shitty_ui/pages/dashboard.py shitty_ui/layout.py` passes
- [ ] `python3 -m ruff format shitty_ui/pages/dashboard.py shitty_ui/layout.py` passes

### Visual Verification
- [ ] Load dashboard at `/` -- analytics section shows a tabbed card with "Accuracy Over Time" as the default tab
- [ ] Click "By Confidence" tab -- chart switches instantly (no loading delay since data is pre-populated)
- [ ] Click "By Asset" tab -- chart switches, clicking a bar still navigates to `/assets/<ticker>`
- [ ] "Latest Posts" is visible without scrolling past charts (should be approximately at the 700-800px mark instead of 1200-1400px)
- [ ] "Recent Predictions" sidebar is visible alongside "Latest Posts"
- [ ] "Full Prediction Data" section shows a right-pointing chevron
- [ ] Click "Full Prediction Data" -- chevron rotates to point down, table content loads
- [ ] Click again -- chevron rotates back, content collapses
- [ ] Alert History panel is NOT visible on the dashboard
- [ ] Asset Deep Dive section with dropdown is NOT visible on the dashboard
- [ ] Navigate to `/performance` -- page still works correctly (independent of dashboard changes)
- [ ] Click bell icon -- alert configuration offcanvas still opens correctly
- [ ] CHANGELOG.md updated under `[Unreleased]`

---

## 8. What NOT To Do

1. **Do NOT modify `data.py`.** This file is modified by Phases 04 and 09. The dashboard IA changes are purely structural (layout and callbacks) with no data layer impact. All existing data functions remain valid.

2. **Do NOT modify `components/cards.py`.** This file is modified by Phases 05, 06, and 07. All card components (`create_hero_signal_card`, `create_metric_card`, `create_signal_card`, `create_post_card`) are reused as-is in the new layout.

3. **Do NOT modify `constants.py`.** This file is modified by Phases 07 and 10. The tabbed analytics card uses the existing `COLORS` dictionary for styling. No new constants are needed.

4. **Do NOT modify `components/header.py`.** This file is modified by Phases 01 and 10. The header navigation and refresh indicator are independent of the dashboard layout restructuring.

5. **Do NOT modify `callbacks/alerts.py`.** While this phase removes the alert history panel from the dashboard layout, the `create_alert_history_panel()` function and its associated callbacks should remain in `callbacks/alerts.py` for potential future use (e.g., if the panel is later integrated into the alert config offcanvas). Do not delete the function or its callbacks.

6. **Do NOT use lazy-loading for tab content.** All three chart `dcc.Graph` components must be present in the DOM at render time because the `update_dashboard()` callback outputs to all three simultaneously. Using `dbc.Tabs` with `active_tab` is CSS-based visibility toggling, not component mounting/unmounting. If you use Dash's `dcc.Tabs` (instead of `dbc.Tabs`), the behavior differs -- stick with `dbc.Tabs`.

7. **Do NOT change the chart height or styling.** The three charts (`acc_fig`, `conf_fig`, `asset_fig`) keep their existing `height` settings from the `update_dashboard()` callback (280, 250, 250). The tabbed container provides enough vertical space for any of them. Do not add `height` overrides on the `dcc.Graph` components in the layout.

8. **Do NOT create a new page for the predictions table.** The requirement says the full predictions table should remain as a collapsed section on the dashboard, not moved to a separate route. The collapsible pattern with the chevron affordance is the correct approach.

9. **Do NOT delete the `toggle_collapse` callback (lines 1208-1217).** This callback is still needed for the predictions table collapse toggle. The chevron callback is an addition, not a replacement.

10. **Do NOT add `dbc.Tabs` to the imports in `dashboard.py`.** `dbc.Tabs` and `dbc.Tab` are accessed through the existing `import dash_bootstrap_components as dbc` on line 7. They do not require a separate import.

---

### Critical Files for Implementation
- `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard.py` - Core file: rewrite layout in `create_dashboard_page()`, modify `update_dashboard()` callback signature and return, remove `update_asset_drilldown()` callback, add chevron clientside callback
- `/Users/chris/Projects/shitpost-alpha/shitty_ui/layout.py` - Add CSS for `.analytics-tabs`, `.collapse-chevron`, and `.collapse-toggle-btn` in the `app.index_string` style block
- `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_layout.py` - Add `TestDashboardPageStructure` (13 tests) and `TestAnalyticsTabsCSS` (2 tests) plus helper functions
- `/Users/chris/Projects/shitpost-alpha/shitty_ui/callbacks/alerts.py` - Reference only: verify `create_alert_history_panel()` function is not deleted (just no longer called from dashboard); understand that dormant callbacks are safe due to `suppress_callback_exceptions`
- `/Users/chris/Projects/shitpost-alpha/CHANGELOG.md` - Add changelog entries under `[Unreleased]`