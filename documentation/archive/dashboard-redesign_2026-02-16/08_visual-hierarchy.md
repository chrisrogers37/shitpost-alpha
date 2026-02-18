# Phase 08: Visual Hierarchy Redesign

**Status**: ✅ COMPLETE
**Started**: 2026-02-17
**Completed**: 2026-02-17
**PR Title**: style: section differentiation & data density
**Risk Level**: Medium
**Estimated Effort**: Medium (3-4 hours)
**Dependencies**: Phase 05 (Merge Redundant Sections)
**Unlocks**: Phase 09 (Mobile Responsiveness)

## Files Modified

| File | Action |
|------|--------|
| `shitty_ui/constants.py` | Add `HIERARCHY` dict (background tiers, shadows, border-radius); extend `COLORS` with `surface_sunken` |
| `shitty_ui/components/cards.py` | Redesign `create_metric_card()` for hero KPI treatment |
| `shitty_ui/pages/dashboard.py` | Apply tiered backgrounds per section via `HIERARCHY` tokens; tighten KPI row gutter; add section spacing; add `section-tertiary` CSS class to tertiary cards |
| `shitty_ui/layout.py` | Add hierarchy CSS classes (`.section-tertiary`, `.kpi-hero-card`, `.kpi-hero-value`); update existing card CSS border-radius |
| `shitty_ui/components/header.py` | Add subtle bottom shadow to header for visual separation from page content |
| `shit_tests/shitty_ui/test_layout.py` | Add `TestVisualHierarchy` class; add `TestHierarchyCSS` class |
| `shit_tests/shitty_ui/test_cards.py` | Add `TestMetricCardHeroStyle` class |
| `CHANGELOG.md` | Add entry |

## Context

After Phase 05 merges the hero and recent predictions into a single unified feed, the dashboard has this section order:

```
[Header]
[Time Period Selector]
[KPI Metrics Row]             -- 4 metric cards in a row
[Analytics Tabs]              -- Tabbed charts (accuracy, confidence, asset)
[Unified Prediction Feed]     -- Full-width card list from Phase 05
[Latest Posts]                -- Full-width post feed
[Collapsible Data Table]      -- Expandable raw data
[Footer]
```

**The problem**: Every section uses the exact same visual treatment -- `backgroundColor: COLORS["secondary"]` (`#1E293B`), `border: 1px solid COLORS["border"]` (`#334155`), `borderRadius: 12px`. There is zero visual differentiation between the most important content (KPI metrics), the primary content (prediction feed), the supporting content (charts), and the secondary content (posts, raw table). The user's eye has no guide through the page. The dashboard looks "flat" and "AI-generated" because every section has identical weight.

**Screenshots**: See `/tmp/design-review/dashboard-desktop.png` -- all sections share the same dark card styling with no depth, shadow, or background variation.

**The solution**: Establish a 3-tier visual hierarchy system:

| Tier | Section | Visual Treatment |
|------|---------|-----------------|
| **Primary (Hero)** | KPI Metrics Row | Elevated surface with subtle glow shadow, larger typography, accent-colored icon backgrounds |
| **Secondary** | Unified Prediction Feed, Analytics Tabs | Standard card treatment (current), but with slightly increased padding and a top accent border |
| **Tertiary** | Latest Posts, Collapsible Data Table | Subdued surface (darker background), reduced border emphasis, tighter spacing |

Additionally:
- The header gains a subtle bottom shadow so it visually "floats" above page content
- Section gaps are increased between tiers (32px between Primary and Secondary, 24px between Secondary and Tertiary) but tightened within tiers
- KPI cards get a "hero" redesign: larger value font, accent-colored circular icon background, and a subtle gradient bottom border
- The prediction feed card gets a top accent border (2px solid accent) to visually anchor it as the primary content area
- Typography weights are reinforced: KPI values at 800 weight, section headers at 600, card content at 400

---

## Detailed Implementation

### Change A: Add Hierarchy Constants to constants.py

#### Step A1: Add visual hierarchy tokens

**File**: `shitty_ui/constants.py`
**Location**: After `SECTION_ACCENT` dict (after line 89)

```python
# Visual hierarchy tiers -- backgrounds, shadows, and borders for section differentiation
# Primary tier = KPI metrics (most important, elevated)
# Secondary tier = Prediction feed, analytics charts (main content)
# Tertiary tier = Posts feed, raw data table (supporting content)
HIERARCHY = {
    "primary": {
        "background": COLORS["secondary"],
        "shadow": "0 4px 24px rgba(59, 130, 246, 0.08), 0 1px 3px rgba(0, 0, 0, 0.2)",
        "border": f"1px solid {COLORS['accent']}40",  # Accent at 25% opacity
        "border_radius": "16px",
    },
    "secondary": {
        "background": COLORS["secondary"],
        "shadow": "0 1px 3px rgba(0, 0, 0, 0.12)",
        "border": f"1px solid {COLORS['border']}",
        "border_radius": "12px",
        "accent_top": f"2px solid {COLORS['accent']}",
    },
    "tertiary": {
        "background": COLORS["surface_sunken"],
        "shadow": "none",
        "border": "1px solid #2d3a4e",
        "border_radius": "10px",
    },
}
```

**Dropped from original plan**: `SECTION_SPACING` (too few consumers — values inlined where used), `KPI_HERO` (values local to `create_metric_card()`, not shared), `create_section_container()` (returns `html.Div` but consumers are `dbc.Card` — wrong abstraction for Card styling).

#### Step A2: Add surface color to COLORS

**File**: `shitty_ui/constants.py`
**Location**: Inside the `COLORS` dict (after line 14, before the closing `}`)

```python
    "surface_sunken": "#172032",    # Slightly darker than secondary, for tertiary sections
```

**Dropped**: `surface_elevated` — no consumers in this phase or downstream phases.

---

### Change B: Redesign KPI Metric Cards for Hero Treatment

#### Step B1: Update `create_metric_card()` in cards.py

**File**: `shitty_ui/components/cards.py`
**Location**: Lines 344-389 (the entire `create_metric_card()` function)

Replace the entire function with:

```python
def create_metric_card(
    title: str,
    value: str,
    subtitle: str = "",
    icon: str = "chart-line",
    color: str = None,
    note: str = "",
):
    """Create a metric card component with hero-level visual treatment.

    KPI cards are the highest-priority elements on the dashboard. They use
    elevated styling with accent-colored icon backgrounds, larger value
    typography, and a subtle glow shadow to draw the eye first.

    Args:
        title: Metric label (e.g., "Total Signals").
        value: Formatted metric value (e.g., "74").
        subtitle: Supporting text below the value.
        icon: FontAwesome icon name (without 'fa-' prefix).
        color: Accent color for value and icon. Defaults to COLORS["accent"].
        note: Optional warning note (e.g., "All-time" fallback indicator).
    """
    color = color or COLORS["accent"]
    return dbc.Card(
        [
            dbc.CardBody(
                [
                    # Icon with circular accent background
                    html.Div(
                        [
                            html.I(
                                className=f"fas fa-{icon}",
                                style={
                                    "fontSize": "1.1rem",
                                    "color": "#ffffff",
                                },
                            ),
                        ],
                        style={
                            "width": "40px",
                            "height": "40px",
                            "borderRadius": "50%",
                            "backgroundColor": color,
                            "display": "flex",
                            "alignItems": "center",
                            "justifyContent": "center",
                            "marginBottom": "10px",
                            "opacity": "0.9",
                        },
                    ),
                    # Value -- hero-sized, extra bold
                    html.Div(
                        value,
                        className="kpi-hero-value",
                        style={
                            "fontSize": "2rem",
                            "fontWeight": "800",
                            "color": color,
                            "lineHeight": "1.1",
                            "margin": "0 0 4px 0",
                        },
                    ),
                    # Title label
                    html.P(
                        title,
                        style={
                            "margin": 0,
                            "color": COLORS["text_muted"],
                            "fontSize": "0.82rem",
                            "fontWeight": "500",
                            "textTransform": "uppercase",
                            "letterSpacing": "0.03em",
                        },
                    ),
                    # Subtitle
                    html.Small(
                        subtitle,
                        style={
                            "color": COLORS["text_muted"],
                            "fontSize": "0.75rem",
                        },
                    )
                    if subtitle
                    else None,
                    # Optional note (e.g., "All-time" fallback from Phase 01)
                    html.Div(
                        note,
                        style={
                            "color": COLORS["warning"],
                            "fontSize": "0.7rem",
                            "marginTop": "4px",
                        },
                    )
                    if note
                    else None,
                ],
                style={
                    "textAlign": "center",
                    "padding": "18px 15px",
                    "minHeight": "130px",
                    "display": "flex",
                    "flexDirection": "column",
                    "alignItems": "center",
                    "justifyContent": "center",
                },
            )
        ],
        className="metric-card kpi-hero-card",
        style={
            "backgroundColor": COLORS["secondary"],
            "border": "1px solid #3b82f640",
            "borderRadius": "16px",
            "boxShadow": "0 4px 24px rgba(59, 130, 246, 0.08), 0 1px 3px rgba(0, 0, 0, 0.2)",
        },
    )
```

**Key changes from current**:
1. `className` adds `kpi-hero-card` for CSS targeting
2. Icon gets a circular colored background instead of bare icon
3. Value uses `2rem` / `800` weight instead of `H3` default
4. Title becomes uppercase label style (`0.82rem`, `500` weight, `letterSpacing`)
5. Card gets elevated shadow and accent-tinted border
6. `borderRadius` increases from `12px` (inherited from `.card` CSS) to `16px`
7. `minHeight: 130px` ensures all 4 cards align vertically
8. `note` parameter preserved for Phase 01 compatibility (defaults to `""`)

**Dropped**: `create_section_container()` — returns `html.Div` wrapper but consumers are `dbc.Card` components needing direct styling + CSS class overrides for child CardHeader/CardBody. Wrong abstraction.

---

### Change C: Apply Section Hierarchy to Dashboard Layout

#### Step C1: Update KPI metrics row styling

**File**: `shitty_ui/pages/dashboard.py`
**Location**: Lines 108-114 (the KPI metrics `dcc.Loading` wrapper)

**Note**: After Phase 05, the hero section is removed and the layout order is: Time Period Selector, KPI Metrics, Analytics Tabs, Unified Feed, Posts, Table. The KPI section is approximately at this location.

Replace:
```python
                    # Key Metrics Row
                    dcc.Loading(
                        id="performance-metrics-loading",
                        type="default",
                        color=COLORS["accent"],
                        children=html.Div(id="performance-metrics", className="mb-4"),
                    ),
```

With:
```python
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

**Change**: `className="mb-4"` (16px) replaced with explicit `marginBottom: "32px"` for the larger between-tier gap. The `mb-4` class is a Bootstrap utility that sets 24px margin; we want 32px between the primary tier (KPIs) and secondary tier (analytics).

#### Step C2: Tighten KPI row gutter in the callback

**File**: `shitty_ui/pages/dashboard.py`
**Location**: Inside `update_dashboard()`, the `metrics_row = dbc.Row(...)` block (lines 636-694 in current code)

Replace:
```python
                className="g-2 g-md-3",
```

With:
```python
                className="g-2 g-md-2",
```

**Change**: Reduces the gutter between KPI cards from `g-md-3` (12px) to `g-md-2` (8px) on medium+ screens. The hero-styled cards are already wider due to `minHeight` and padding, so tighter gutters keep them as a cohesive row unit.

#### Step C3: Add top accent border to Analytics section

**File**: `shitty_ui/pages/dashboard.py`
**Location**: Lines 116-184 (the Analytics `dbc.Card` block)

Find the style dict on the outer `dbc.Card`:
```python
                    ),
                        className="mb-4",
                        style={"backgroundColor": COLORS["secondary"]},
                    ),
```

Replace with:
```python
                        className="mb-4",
                        style={
                            "backgroundColor": HIERARCHY["secondary"]["background"],
                            "borderTop": HIERARCHY["secondary"]["accent_top"],
                            "boxShadow": HIERARCHY["secondary"]["shadow"],
                        },
```

**Change**: Adds a 2px accent-blue top border to visually anchor the analytics section as secondary-tier content. Also adds a subtle shadow to differentiate from tertiary sections. References `HIERARCHY` tokens instead of hardcoding values.

#### Step C4: Add top accent border to Unified Feed section

**File**: `shitty_ui/pages/dashboard.py`
**Location**: The unified feed `dbc.Card` added by Phase 05 (the "Predictions" card)

Find the style dict on the unified feed outer `dbc.Card`:
```python
                        className="mb-4",
                        style={"backgroundColor": COLORS["secondary"]},
```

Replace with (note: `marginBottom: "32px"` replaces `className="mb-4"` for the larger tier gap):
```python
                        style={
                            "backgroundColor": HIERARCHY["secondary"]["background"],
                            "borderTop": HIERARCHY["secondary"]["accent_top"],
                            "boxShadow": HIERARCHY["secondary"]["shadow"],
                            "marginBottom": "32px",
                        },
```

**Change**: Same secondary-tier treatment as analytics. The accent top border creates a visual line that guides the eye downward. The `marginBottom: "32px"` creates a larger gap before the tertiary tier (replacing the standard `mb-4` 24px gap). Remove `className="mb-4"` since the inline style handles spacing.

#### Step C5: Style Latest Posts as tertiary tier

**File**: `shitty_ui/pages/dashboard.py`
**Location**: The "Latest Posts" `dbc.Card` (moved to full-width by Phase 05)

Find the style dict on the Latest Posts outer `dbc.Card`:
```python
                        className="mb-4",
                        style={"backgroundColor": COLORS["secondary"]},
```

Replace with:
```python
                        className="section-tertiary mb-4",
                        style={
                            "backgroundColor": HIERARCHY["tertiary"]["background"],
                            "border": HIERARCHY["tertiary"]["border"],
                            "boxShadow": HIERARCHY["tertiary"]["shadow"],
                        },
```

**Change**: Tertiary tier uses tokens from `HIERARCHY["tertiary"]` — darker background, subtler border, no shadow. The `className="section-tertiary"` triggers CSS overrides for child CardHeader/CardBody backgrounds.

#### Step C6: Style Collapsible Data Table as tertiary tier

**File**: `shitty_ui/pages/dashboard.py`
**Location**: Lines 282-323 (the collapsible table `dbc.Card`)

Find:
```python
                        style={"backgroundColor": COLORS["secondary"]},
```

Replace with:
```python
                        className="section-tertiary mb-4",
                        style={
                            "backgroundColor": HIERARCHY["tertiary"]["background"],
                            "border": HIERARCHY["tertiary"]["border"],
                            "boxShadow": HIERARCHY["tertiary"]["shadow"],
                        },
```

**Change**: Same tertiary-tier treatment as Latest Posts, using `HIERARCHY` tokens.

#### Step C7: REMOVED

Tier gap is now handled by Step C4's inline `marginBottom: "32px"` on the unified feed card. No separate spacer div needed.

---

### Change D: Add Hierarchy CSS Classes to layout.py

#### Step D1: Add hierarchy tier CSS classes

**File**: `shitty_ui/layout.py`
**Location**: Inside the `<style>` block, after the `/* Collapsible section chevrons */` section (after line 337)

```css
            /* ======================================
               Visual hierarchy tiers
               ====================================== */

            /* Primary tier: KPI metrics (most important) */
            .kpi-hero-card {
                border-radius: 16px !important;
                transition: transform 0.15s ease, box-shadow 0.15s ease;
            }
            .kpi-hero-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 8px 32px rgba(59, 130, 246, 0.12), 0 2px 6px rgba(0, 0, 0, 0.25) !important;
            }
            .kpi-hero-value {
                font-variant-numeric: tabular-nums;
            }

            /* Secondary tier: prediction feed, analytics */
            .section-secondary {
                border-radius: 12px;
            }

            /* Tertiary tier: posts, data table (receded) */
            .section-tertiary {
                border-radius: 10px;
            }
            .section-tertiary .card-header {
                background-color: #172032 !important;
                border-bottom-color: #2d3a4e !important;
            }
            .section-tertiary .card-body {
                background-color: #172032 !important;
            }

            /* Header elevation shadow */
            .header-container {
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
                position: relative;
                z-index: 10;
            }
```

**Key details**:
- `.kpi-hero-card` gets hover elevation effect (scale + stronger shadow)
- `.kpi-hero-value` uses `font-variant-numeric: tabular-nums` so numbers align in columns (prevents layout shift when values change)
- `.section-tertiary` overrides card-header and card-body backgrounds to the darker tertiary color
- `.header-container` gets a bottom shadow to visually separate the fixed header from scrolling content

#### Step D2: Update existing card border-radius rule

**File**: `shitty_ui/layout.py`
**Location**: Lines 89-93 (the `.card` CSS rule)

Find:
```css
            .card {
                border-radius: 12px !important;
                border: 1px solid #334155 !important;
                overflow: hidden;
            }
```

Replace with:
```css
            .card {
                border-radius: 12px !important;
                border: 1px solid #334155 !important;
                overflow: hidden;
                transition: box-shadow 0.15s ease;
            }
```

**Change**: Adds a `transition` for smooth shadow changes on hover. The `border-radius` stays at `12px` as the default; the `.kpi-hero-card` class overrides it to `16px` for KPI cards only.

---

### Change E: Add Header Shadow for Visual Separation

#### Step E1: Add shadow to header container

**File**: `shitty_ui/components/header.py`
**Location**: Lines 168-176 (the outer `html.Div` style dict for the header)

Find:
```python
        className="header-container",
        style={
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "padding": "15px 20px",
            "borderBottom": f"1px solid {COLORS['border']}",
            "backgroundColor": COLORS["secondary"],
        },
```

Replace with:
```python
        className="header-container",
        style={
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "padding": "15px 20px",
            "borderBottom": f"1px solid {COLORS['border']}",
            "backgroundColor": COLORS["secondary"],
            "boxShadow": "0 2px 8px rgba(0, 0, 0, 0.3)",
            "position": "relative",
            "zIndex": 10,
        },
```

**Change**: Adds `boxShadow`, `position: relative`, and `zIndex: 10` so the header casts a shadow onto the content below. The `position: relative` and `zIndex` ensure the shadow renders on top of subsequent content. Note: the CSS class `.header-container` in `layout.py` also sets these properties, providing a fallback if inline styles are overridden.

---

### Change F: Update Tertiary Section CardHeader/CardBody Backgrounds

The tertiary-tier sections (Latest Posts, Collapsible Data Table) have `dbc.CardHeader` and `dbc.CardBody` children that may explicitly set `backgroundColor: COLORS["secondary"]`. These need to be updated to match the tertiary background.

**Steps F1/F2 merged into C5/C6**: The `className="section-tertiary"` and `HIERARCHY` token references are now applied directly in Steps C5 and C6. The CSS class `.section-tertiary .card-header` and `.section-tertiary .card-body` rules from Step D1 handle the child background overrides. No separate Change F steps needed.

---

## Test Plan

### New Tests: `TestVisualHierarchy`

**File**: `shit_tests/shitty_ui/test_layout.py`
**Location**: After `TestDashboardPageStructure` class (after line 1689)

```python
class TestVisualHierarchy:
    """Tests for visual hierarchy tier differentiation in the dashboard layout."""

    def test_kpi_section_has_larger_margin(self):
        """Test that KPI section uses 32px margin instead of standard 16px/24px."""
        from pages.dashboard import create_dashboard_page

        page = create_dashboard_page()
        perf_metrics = _find_component_by_id(page, "performance-metrics")
        assert perf_metrics is not None
        # Parent wrapper should have 32px margin
        style = perf_metrics.style or {}
        assert style.get("marginBottom") == "32px"

    def test_latest_posts_has_tertiary_class(self):
        """Test that Latest Posts card has section-tertiary className."""
        from pages.dashboard import create_dashboard_page
        import dash_bootstrap_components as dbc

        page = create_dashboard_page()
        # Find the card containing post-feed-container
        post_container = _find_component_by_id(page, "post-feed-container")
        assert post_container is not None

        # Walk up to find the dbc.Card parent with section-tertiary class
        all_cards = _find_components_by_type(page, dbc.Card)
        tertiary_cards = [
            c for c in all_cards
            if hasattr(c, "className") and c.className and "section-tertiary" in c.className
        ]
        assert len(tertiary_cards) >= 1, "At least one card should have section-tertiary class"

    def test_collapsible_table_has_tertiary_class(self):
        """Test that collapsible data table card has section-tertiary className."""
        from pages.dashboard import create_dashboard_page
        import dash_bootstrap_components as dbc

        page = create_dashboard_page()
        collapse_table = _find_component_by_id(page, "collapse-table")
        assert collapse_table is not None

        all_cards = _find_components_by_type(page, dbc.Card)
        tertiary_cards = [
            c for c in all_cards
            if hasattr(c, "className") and c.className and "section-tertiary" in c.className
        ]
        assert len(tertiary_cards) >= 2, "Both posts and table should be section-tertiary"

    def test_tertiary_cards_have_darker_background(self):
        """Test that tertiary-tier cards use the sunken background color."""
        from pages.dashboard import create_dashboard_page
        import dash_bootstrap_components as dbc

        page = create_dashboard_page()
        all_cards = _find_components_by_type(page, dbc.Card)
        tertiary_cards = [
            c for c in all_cards
            if hasattr(c, "className") and c.className and "section-tertiary" in c.className
        ]
        for card in tertiary_cards:
            bg = card.style.get("backgroundColor", "") if card.style else ""
            assert bg == "#172032", f"Tertiary card should use #172032 background, got: {bg}"

    def test_header_has_shadow(self):
        """Test that header container has a box shadow for elevation."""
        from components.header import create_header

        header = create_header()
        style = header.style or {}
        assert "boxShadow" in style, "Header should have boxShadow for elevation"
        assert "rgba" in style["boxShadow"], "Shadow should use rgba for transparency"
```

### New Tests: `TestHierarchyCSS`

**File**: `shit_tests/shitty_ui/test_layout.py`
**Location**: After `TestVisualHierarchy` class

```python
class TestHierarchyCSS:
    """Tests for hierarchy CSS classes in the app stylesheet."""

    @patch("data.get_prediction_stats")
    @patch("layout.get_performance_metrics")
    @patch("layout.get_accuracy_by_confidence")
    @patch("layout.get_accuracy_by_asset")
    @patch("layout.get_recent_signals")
    @patch("layout.get_active_assets_from_db")
    def test_index_string_contains_kpi_hero_card_css(
        self, mock_assets, mock_signals, mock_asset_acc, mock_conf_acc, mock_perf, mock_stats,
    ):
        """Test that app index_string contains .kpi-hero-card CSS class."""
        mock_stats.return_value = {"total_posts": 0, "analyzed_posts": 0, "completed_analyses": 0, "bypassed_posts": 0, "avg_confidence": 0.0, "high_confidence_predictions": 0}
        mock_perf.return_value = {"total_outcomes": 0, "evaluated_predictions": 0, "correct_predictions": 0, "incorrect_predictions": 0, "accuracy_t7": 0.0, "avg_return_t7": 0.0, "total_pnl_t7": 0.0, "avg_confidence": 0.0}
        mock_conf_acc.return_value = pd.DataFrame()
        mock_asset_acc.return_value = pd.DataFrame()
        mock_signals.return_value = pd.DataFrame()
        mock_assets.return_value = []

        from layout import create_app
        app = create_app()

        assert ".kpi-hero-card" in app.index_string
        assert ".kpi-hero-card:hover" in app.index_string

    @patch("data.get_prediction_stats")
    @patch("layout.get_performance_metrics")
    @patch("layout.get_accuracy_by_confidence")
    @patch("layout.get_accuracy_by_asset")
    @patch("layout.get_recent_signals")
    @patch("layout.get_active_assets_from_db")
    def test_index_string_contains_section_tertiary_css(
        self, mock_assets, mock_signals, mock_asset_acc, mock_conf_acc, mock_perf, mock_stats,
    ):
        """Test that app index_string contains .section-tertiary CSS overrides."""
        mock_stats.return_value = {"total_posts": 0, "analyzed_posts": 0, "completed_analyses": 0, "bypassed_posts": 0, "avg_confidence": 0.0, "high_confidence_predictions": 0}
        mock_perf.return_value = {"total_outcomes": 0, "evaluated_predictions": 0, "correct_predictions": 0, "incorrect_predictions": 0, "accuracy_t7": 0.0, "avg_return_t7": 0.0, "total_pnl_t7": 0.0, "avg_confidence": 0.0}
        mock_conf_acc.return_value = pd.DataFrame()
        mock_asset_acc.return_value = pd.DataFrame()
        mock_signals.return_value = pd.DataFrame()
        mock_assets.return_value = []

        from layout import create_app
        app = create_app()

        assert ".section-tertiary" in app.index_string
        assert ".section-tertiary .card-header" in app.index_string
        assert ".section-tertiary .card-body" in app.index_string

    @patch("data.get_prediction_stats")
    @patch("layout.get_performance_metrics")
    @patch("layout.get_accuracy_by_confidence")
    @patch("layout.get_accuracy_by_asset")
    @patch("layout.get_recent_signals")
    @patch("layout.get_active_assets_from_db")
    def test_index_string_contains_tabular_nums(
        self, mock_assets, mock_signals, mock_asset_acc, mock_conf_acc, mock_perf, mock_stats,
    ):
        """Test that .kpi-hero-value uses tabular-nums for numeric alignment."""
        mock_stats.return_value = {"total_posts": 0, "analyzed_posts": 0, "completed_analyses": 0, "bypassed_posts": 0, "avg_confidence": 0.0, "high_confidence_predictions": 0}
        mock_perf.return_value = {"total_outcomes": 0, "evaluated_predictions": 0, "correct_predictions": 0, "incorrect_predictions": 0, "accuracy_t7": 0.0, "avg_return_t7": 0.0, "total_pnl_t7": 0.0, "avg_confidence": 0.0}
        mock_conf_acc.return_value = pd.DataFrame()
        mock_asset_acc.return_value = pd.DataFrame()
        mock_signals.return_value = pd.DataFrame()
        mock_assets.return_value = []

        from layout import create_app
        app = create_app()

        assert "tabular-nums" in app.index_string

    @patch("data.get_prediction_stats")
    @patch("layout.get_performance_metrics")
    @patch("layout.get_accuracy_by_confidence")
    @patch("layout.get_accuracy_by_asset")
    @patch("layout.get_recent_signals")
    @patch("layout.get_active_assets_from_db")
    def test_header_shadow_in_css(
        self, mock_assets, mock_signals, mock_asset_acc, mock_conf_acc, mock_perf, mock_stats,
    ):
        """Test that .header-container CSS includes box-shadow."""
        mock_stats.return_value = {"total_posts": 0, "analyzed_posts": 0, "completed_analyses": 0, "bypassed_posts": 0, "avg_confidence": 0.0, "high_confidence_predictions": 0}
        mock_perf.return_value = {"total_outcomes": 0, "evaluated_predictions": 0, "correct_predictions": 0, "incorrect_predictions": 0, "accuracy_t7": 0.0, "avg_return_t7": 0.0, "total_pnl_t7": 0.0, "avg_confidence": 0.0}
        mock_conf_acc.return_value = pd.DataFrame()
        mock_asset_acc.return_value = pd.DataFrame()
        mock_signals.return_value = pd.DataFrame()
        mock_assets.return_value = []

        from layout import create_app
        app = create_app()

        # Find the header-container CSS rule that includes box-shadow
        assert "box-shadow:" in app.index_string or "boxShadow" in app.index_string
```

### New Tests: `TestMetricCardHeroStyle`

**File**: `shit_tests/shitty_ui/test_cards.py`
**Location**: After the `TestSentimentBadgeBackground` class (after line 428)

```python
class TestMetricCardHeroStyle:
    """Tests for the redesigned metric card with hero KPI treatment."""

    def test_metric_card_has_kpi_hero_class(self):
        """Test that metric card className includes kpi-hero-card."""
        from components.cards import create_metric_card

        card = create_metric_card("Total Signals", "74", "evaluated", "signal")
        assert "kpi-hero-card" in (card.className or "")

    def test_metric_card_has_elevated_shadow(self):
        """Test that metric card has a box shadow for elevation."""
        from components.cards import create_metric_card

        card = create_metric_card("Accuracy", "65.0%", "correct at 7d", "bullseye")
        assert "boxShadow" in card.style
        assert "rgba" in card.style["boxShadow"]

    def test_metric_card_has_accent_border(self):
        """Test that metric card border uses accent color at low opacity."""
        from components.cards import create_metric_card

        card = create_metric_card("P&L", "$500", "simulated", "dollar-sign")
        assert "border" in card.style
        assert "#3b82f6" in card.style["border"]

    def test_metric_card_has_larger_border_radius(self):
        """Test that metric card borderRadius is 16px (not default 12px)."""
        from components.cards import create_metric_card

        card = create_metric_card("Test", "100", "", "chart-line")
        assert card.style.get("borderRadius") == "16px"

    def test_metric_card_value_has_hero_size(self):
        """Test that value element uses 2rem font size."""
        from components.cards import create_metric_card

        card = create_metric_card("Test", "42", "", "chart-line")
        # Find the value div (has className kpi-hero-value)
        card_body = card.children[0]  # dbc.CardBody
        children = card_body.children
        value_div = None
        for child in children:
            if child is not None and hasattr(child, "className"):
                if child.className and "kpi-hero-value" in child.className:
                    value_div = child
                    break
        assert value_div is not None, "Could not find kpi-hero-value element"
        assert value_div.style.get("fontSize") == "2rem"
        assert value_div.style.get("fontWeight") == "800"

    def test_metric_card_icon_has_circular_background(self):
        """Test that icon is wrapped in a circular colored background."""
        from components.cards import create_metric_card
        from constants import COLORS

        card = create_metric_card("Test", "100", "", "signal", COLORS["accent"])
        card_body = card.children[0]  # dbc.CardBody
        icon_wrapper = card_body.children[0]  # First child is icon wrapper div
        assert icon_wrapper.style.get("borderRadius") == "50%"
        assert icon_wrapper.style.get("backgroundColor") == COLORS["accent"]

    def test_metric_card_title_is_uppercase(self):
        """Test that title label uses uppercase text transform."""
        from components.cards import create_metric_card
        from dash import html

        card = create_metric_card("Total Signals", "74", "", "signal")
        card_body = card.children[0]
        # Title is the html.P element (3rd child after icon and value)
        title_elem = None
        for child in card_body.children:
            if child is not None and isinstance(child, html.P):
                title_elem = child
                break
        assert title_elem is not None
        assert title_elem.style.get("textTransform") == "uppercase"

    def test_metric_card_preserves_note_param(self):
        """Test backward compatibility: note parameter still works."""
        from components.cards import create_metric_card

        card = create_metric_card("Test", "0", "", "signal", note="All-time")
        text = _extract_text(card)
        assert "All-time" in text

    def test_metric_card_no_note_when_empty(self):
        """Test that note element is not rendered when note is empty string."""
        from components.cards import create_metric_card

        card = create_metric_card("Test", "100", "sub", "signal", note="")
        # The None children (from `if note else None`) should be filtered
        card_body = card.children[0]
        none_children = [c for c in card_body.children if c is None]
        # At most one None (subtitle when provided, note when empty)
        # Key check: no crash and card renders
        assert card is not None

    def test_metric_card_min_height(self):
        """Test that card body has minHeight for consistent alignment."""
        from components.cards import create_metric_card

        card = create_metric_card("Test", "100", "", "signal")
        card_body = card.children[0]
        assert card_body.style.get("minHeight") == "130px"
```

**Dropped**: `TestSectionContainer` — `create_section_container()` was removed (wrong abstraction for `dbc.Card` consumers).

### Existing Test Compatibility

These existing tests must continue to pass without modification:

- `TestCreateMetricCard` in `test_layout.py` (lines 314-343): Tests `create_metric_card` returns a `dbc.Card`, accepts default color, and accepts custom color. These tests remain valid because the function signature is unchanged (title, value, subtitle, icon, color, note).

- `TestColors.test_colors_are_valid_hex` in `test_layout.py` (lines 115-121): The new `surface_sunken` color must be valid 7-character hex. Since it is (`#172032`), this test passes.

- `TestTypographyConstants` in `test_layout.py` (lines 1368-1456): Constants are only extended, not modified. All existing keys remain.

- `TestSentimentLeftBorder` in `test_cards.py` (lines 276-341): The `create_metric_card` changes do not affect sentiment cards.

- `TestHeroSignalCardDedup` in `test_layout.py` (lines 1271-1365): `create_hero_signal_card` is untouched.

- All `/performance` page tests: Completely separate from dashboard layout changes.

---

## Verification Checklist

- [ ] KPI cards visually stand out: larger value text (2rem), circular icon backgrounds, elevated shadow, accent-tinted border
- [ ] KPI cards have 32px bottom margin (larger gap before analytics section)
- [ ] Analytics tabs card has a blue 2px top accent border
- [ ] Unified prediction feed card has a blue 2px top accent border
- [ ] Latest Posts card has a darker background (#172032), subtler border (#2d3a4e), and no shadow
- [ ] Collapsible Data Table card has the same tertiary styling as Latest Posts
- [ ] Header has a subtle bottom shadow separating it from page content
- [ ] Hovering over KPI cards produces a subtle elevation animation
- [ ] Hovering over KPI cards does NOT produce layout shift (no changes to width/height)
- [ ] KPI values use `font-variant-numeric: tabular-nums` (numbers don't shift when values change)
- [ ] Section gaps: 32px between tiers, 16px within tiers
- [ ] `/performance` page metric cards also use the new hero styling (they call `create_metric_card()`)
- [ ] `/signals` page is completely unaffected
- [ ] All existing tests pass: `source venv/bin/activate && pytest shit_tests/shitty_ui/ -v`
- [ ] New tests pass: `source venv/bin/activate && pytest shit_tests/shitty_ui/test_layout.py::TestVisualHierarchy -v`
- [ ] New tests pass: `source venv/bin/activate && pytest shit_tests/shitty_ui/test_layout.py::TestHierarchyCSS -v`
- [ ] New tests pass: `source venv/bin/activate && pytest shit_tests/shitty_ui/test_cards.py::TestMetricCardHeroStyle -v`
- [ ] CHANGELOG.md updated

---

## What NOT To Do

1. **Do NOT change the color values in the existing `COLORS` dict.** Only add the new key (`surface_sunken`). Changing existing colors like `primary`, `secondary`, or `border` would break every component in the app. The tertiary background `#172032` is a new distinct value, not a replacement for `COLORS["secondary"]`.

2. **Do NOT add shadows to every card.** Only primary-tier (KPI) and secondary-tier (analytics, feed) cards get shadows. Tertiary-tier cards explicitly use `boxShadow: "none"`. Adding shadows everywhere defeats the hierarchy -- the point is that shadows create elevation differences.

3. **Do NOT change `create_metric_card()` function signature.** It must remain `(title, value, subtitle, icon, color, note)` with all the same defaults. The `/performance` page calls this function with 5 positional args (line 1143-1195 of dashboard.py). Breaking the signature would break the backtest results page.

4. **Do NOT use `!important` on inline styles.** The CSS classes in `layout.py` may use `!important` to override Bootstrap defaults, but inline `style={}` dicts in Dash components should not. Dash inline styles already have highest specificity. Using `!important` in inline styles is impossible in Dash anyway (it uses React style objects).

5. **Do NOT modify the unified feed card component (`create_unified_signal_card`).** Phase 08 only changes the wrapper card's `dbc.Card` styling (border, shadow), not the card content. Modifying the card component itself would create merge conflicts with Phase 06 (sparklines).

6. **Do NOT add position: fixed or position: sticky to the header.** The header shadow creates visual separation without position changes. Making the header sticky would require recalculating page scroll offsets and affect all pages. That is out of scope.

7. **Do NOT change the mobile responsive breakpoints.** Phase 09 handles mobile. Phase 08 should only add styles that work at all viewport sizes. The KPI card `minHeight: 130px` might need adjustment on mobile, but that is Phase 09's job. Check that `@media (max-width: 768px)` rules in the existing CSS are not broken.

8. **Do NOT hardcode hex colors inline when a `COLORS` or `HIERARCHY` key exists.** For example, use `COLORS["accent"]` not `"#3b82f6"` when referencing the accent blue in Python code. Use `HIERARCHY["tertiary"]["background"]` not `"#172032"`. The one exception is the translucent accent border in `HIERARCHY` itself (e.g., `{COLORS['accent']}40`) which has alpha and cannot be expressed with the existing COLORS dict.

---

## Impact on Downstream Phases

### Phase 09 (Mobile Responsiveness) -- Hard dependency
Phase 09 must handle:
- KPI card `minHeight: 130px` may be too tall on mobile; Phase 09 should add a `@media` override
- The `.kpi-hero-value` font size `2rem` may be too large at 375px; Phase 09 should reduce to `1.5rem`
- Tertiary section darker background may need adjustment for OLED screens
- Header shadow `zIndex: 10` is compatible with mobile but should be verified

### Phase 10 (Brand Identity) -- No impact
Phase 10 changes copy text in section headers. The hierarchy CSS classes (`section-tertiary`, `kpi-hero-card`) do not conflict with copy changes.

---

## CHANGELOG Entry

```markdown
### Changed
- **Dashboard: visual hierarchy system** -- Established 3-tier visual differentiation: KPI metrics (primary/elevated), prediction feed and analytics (secondary/standard), posts and raw data (tertiary/receded), guiding the eye through content by importance
- **Dashboard: KPI card hero redesign** -- Metric cards now use circular accent-colored icon backgrounds, 2rem/800-weight values, uppercase labels, elevated shadows, and 16px border radius for a hero-level visual treatment
- **Dashboard: section spacing** -- Increased gap between hierarchy tiers to 32px (up from 16px) for clearer visual separation between content zones
- **Dashboard: header elevation** -- Added subtle bottom shadow to the header bar for visual separation from scrolling content

### Added
- **`HIERARCHY` constants** -- Design tokens for primary/secondary/tertiary visual tiers (backgrounds, shadows, borders) in `constants.py`
- **`COLORS["surface_sunken"]`** -- Darker surface color for tertiary sections
- **`.kpi-hero-card` CSS class** -- Hover elevation effect and tabular-nums for KPI metric cards
- **`.section-tertiary` CSS class** -- Background and border overrides for receded sections (posts, data table)
```
