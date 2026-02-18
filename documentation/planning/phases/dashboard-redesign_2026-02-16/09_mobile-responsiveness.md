# Phase 09: Mobile Responsiveness

**PR Title**: fix: mobile layout at 375px viewport
**Risk Level**: Low
**Estimated Effort**: Small (1-2 hours)
**Status**: ✅ COMPLETE
**Started**: 2026-02-17
**Completed**: 2026-02-17
**Dependencies**: Phase 08 (visual hierarchy)
**Unlocks**: None (leaf node)

## Files Modified

| File | Action |
|------|--------|
| `shitty_ui/layout.py` | Replace existing `@media (max-width: 768px)` block with comprehensive mobile-first media queries for 375px, 480px, and 768px breakpoints; add viewport meta tag |
| `shitty_ui/components/header.py` | Restructure `create_header()` to stack logo/nav vertically on mobile; make nav links scrollable-horizontal; increase touch target sizes to 48px; hide refresh indicator text on small screens |
| `shitty_ui/pages/dashboard.py` | Add `className` props to KPI card columns for CSS-driven stacking; set chart `config.responsive: True`; constrain main content padding on mobile |
| `shitty_ui/constants.py` | Add `"responsive": True` to `CHART_CONFIG` dict |
| `shit_tests/shitty_ui/test_layout.py` | Add tests for new CSS classes, breakpoint constants, viewport meta tag, touch target dimensions |
| `shit_tests/shitty_ui/test_cards.py` | Add tests for `hero-signal-card` minimum width on mobile |
| `CHANGELOG.md` | Add entry |

## Context

The dashboard breaks on mobile viewports (375px iPhone SE / 390px iPhone 14). Specific problems observed:

1. **KPI cards overflow horizontally** -- The 4-column `dbc.Row` with `xs=6` collapses to 2x2 grid, but the card padding and font sizes still overflow the narrow viewport, causing horizontal scroll.
2. **Charts don't scale** -- Plotly charts have fixed `height: 280` / `height: 250` and `displayModeBar: False`, but `config.responsive` is not set, so they render at their initial width and don't shrink below the viewport.
3. **Text gets cut off** -- Page title at `1.75rem` (28px) and card values at `h3` default size are too large for 375px. Section headers and card text clip.
4. **Navigation tabs too small to tap** -- Nav links have `padding: 8px 16px` (about 32px total height), below the 48px minimum recommended by WCAG 2.5.8 / Apple HIG.
5. **Header doesn't adapt** -- The `.header-container` flex row puts logo, nav, and refresh indicator side-by-side. At 375px, items wrap unpredictably and the refresh countdown overlaps the nav links.
6. **Hero signal cards overflow** -- `minWidth: 280px` on hero cards forces horizontal scrolling on 375px viewports (375 - 40px padding = 335px usable).
7. **No viewport meta tag** -- The `index_string` has `{%metas%}` which Dash populates, but there is no explicit `<meta name="viewport" ...>` to prevent mobile browsers from rendering at desktop width.

The existing `@media (max-width: 768px)` block in `layout.py` (lines 152-186) addresses some issues but is insufficient: it only handles basic flex-direction changes and metric card padding. It does not address touch targets, chart responsiveness, font scaling, or the 375px breakpoint.

**Target viewports**:
- 375px (iPhone SE) -- primary constraint
- 390px (iPhone 14) -- secondary constraint
- 768px (iPad portrait) -- tablet breakpoint

## Detailed Implementation

### Change A: Add `responsive: True` to CHART_CONFIG

#### Step A1: Update `CHART_CONFIG` in constants.py

**File**: `shitty_ui/constants.py`
**Location**: The `CHART_CONFIG` dict

Add `"responsive": True` to the existing `CHART_CONFIG` dict. This fixes all charts globally with a single change instead of modifying 5 individual `dcc.Graph` calls.

---

### Change B: Comprehensive Mobile CSS in layout.py

#### Step B1: Add viewport meta tag to index_string

**File**: `shitty_ui/layout.py`
**Location**: Line 78, inside the `<head>` tag, immediately after `{%metas%}`

Add a viewport meta tag so mobile browsers do not render the page at desktop width:

Change:
```html
        {%metas%}
        <title>{%title%}</title>
```

To:
```html
        {%metas%}
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5">
        <title>{%title%}</title>
```

#### Step B2: Replace the existing mobile CSS block with comprehensive responsive rules

**File**: `shitty_ui/layout.py`
**Location**: Lines 151-186 (the entire `@media (max-width: 768px)` block)

Replace the existing block:
```css
            /* Mobile-specific styles */
            @media (max-width: 768px) {
                .metric-card {
                    margin-bottom: 10px;
                }
                .metric-card .card-body {
                    padding: 10px !important;
                }
                .metric-card h3 {
                    font-size: 1.25rem !important;
                }
                .chart-container {
                    height: 200px !important;
                }
                .signal-card {
                    padding: 8px !important;
                }
                h1 {
                    font-size: 1.5rem !important;
                }
                .header-container {
                    flex-direction: column !important;
                    text-align: center !important;
                }
                .header-right {
                    margin-top: 10px !important;
                    flex-direction: column !important;
                    gap: 8px !important;
                }
                .period-selector {
                    justify-content: center !important;
                }
                .hero-signals-container {
                    flex-direction: column !important;
                }
            }
```

With:
```css
            /* ======================================
               Responsive: Tablet (max-width: 768px)
               ====================================== */
            @media (max-width: 768px) {
                /* Header: stack logo and nav vertically */
                .header-container {
                    flex-direction: column !important;
                    text-align: center !important;
                    padding: 12px 16px !important;
                }
                .header-right {
                    margin-top: 10px !important;
                    width: 100% !important;
                    justify-content: center !important;
                }

                /* Navigation: horizontal scroll instead of wrapping */
                .nav-links-row {
                    overflow-x: auto !important;
                    -webkit-overflow-scrolling: touch;
                    scrollbar-width: none;
                    flex-wrap: nowrap !important;
                    justify-content: flex-start !important;
                    width: 100% !important;
                    padding-bottom: 4px;
                }
                .nav-links-row::-webkit-scrollbar {
                    display: none;
                }

                /* Touch targets: minimum 48px height for tap */
                .nav-link-custom {
                    min-height: 48px !important;
                    display: inline-flex !important;
                    align-items: center !important;
                    padding: 12px 16px !important;
                    white-space: nowrap !important;
                    font-size: 0.85rem !important;
                }

                /* KPI metric cards */
                .metric-card {
                    margin-bottom: 8px;
                }
                .metric-card .card-body {
                    padding: 10px !important;
                }
                .metric-card h3 {
                    font-size: 1.25rem !important;
                }

                /* Charts: cap height */
                .chart-container {
                    height: 220px !important;
                }
                .js-plotly-plot .plotly .main-svg {
                    max-width: 100% !important;
                }

                /* Signal cards */
                .signal-card {
                    padding: 10px !important;
                }

                /* Page title */
                .page-title {
                    font-size: 1.4rem !important;
                }

                /* Period selector: center */
                .period-selector {
                    justify-content: center !important;
                }

                /* Hero signals: stack vertically */
                .hero-signals-container {
                    flex-direction: column !important;
                }
                .hero-signal-card {
                    min-width: unset !important;
                    width: 100% !important;
                }

                /* Content container: reduce side padding */
                .main-content-container {
                    padding: 16px 12px !important;
                }

                /* Analytics tabs: smaller text */
                .analytics-tabs .nav-link {
                    padding: 10px 14px !important;
                    font-size: 0.82rem !important;
                }

                /* Data table: allow horizontal scroll */
                .dash-spreadsheet-container {
                    overflow-x: auto !important;
                }
            }

            /* ======================================
               Responsive: Large phone (max-width: 480px)
               ====================================== */
            @media (max-width: 480px) {
                /* Tighter padding on cards */
                .metric-card .card-body {
                    padding: 8px !important;
                }
                .metric-card h3 {
                    font-size: 1.1rem !important;
                }

                /* Reduce chart height further */
                .chart-container {
                    height: 200px !important;
                }

                /* Section headers */
                .section-header {
                    font-size: 1rem !important;
                }

                /* Card headers */
                .card-header {
                    font-size: 0.85rem !important;
                    padding: 10px 12px !important;
                }

                /* Hide refresh countdown text to save space */
                .refresh-detail {
                    display: none !important;
                }

                /* Signal feed cards: reduce padding */
                .feed-signal-card {
                    padding: 12px !important;
                }
            }

            /* ======================================
               Responsive: Small phone (max-width: 375px)
               ====================================== */
            @media (max-width: 375px) {
                /* Header: minimal padding */
                .header-container {
                    padding: 10px 12px !important;
                }

                /* Logo: smaller */
                .header-logo h1 {
                    font-size: 1.3rem !important;
                }
                .header-logo p {
                    font-size: 0.7rem !important;
                }

                /* KPI cards: full width at 375px */
                .kpi-col-mobile {
                    flex: 0 0 50% !important;
                    max-width: 50% !important;
                }
                .metric-card h3 {
                    font-size: 1rem !important;
                    word-break: break-all;
                }
                .metric-card .card-body {
                    padding: 6px !important;
                }

                /* Icon size reduction */
                .metric-card .fas {
                    font-size: 1.1rem !important;
                }

                /* Period selector buttons: smaller */
                .period-selector .btn {
                    font-size: 0.75rem !important;
                    padding: 4px 8px !important;
                    min-height: 36px;
                }

                /* Chart height: compact */
                .chart-container {
                    height: 180px !important;
                }

                /* Post/signal text: smaller line height */
                .signal-card p, .feed-signal-card p {
                    font-size: 0.82rem !important;
                    line-height: 1.35 !important;
                }

                /* Engagement icons row */
                .engagement-row {
                    font-size: 0.7rem !important;
                }

                /* Analytics tabs: compress further */
                .analytics-tabs .nav-link {
                    padding: 8px 10px !important;
                    font-size: 0.78rem !important;
                }

                /* Sentiment badges: smaller */
                .sentiment-badge {
                    font-size: 0.65rem !important;
                    padding: 2px 6px !important;
                }

                /* Footer: smaller text */
                footer p {
                    font-size: 0.7rem !important;
                }
            }
```

---

### Change C: Header Component -- Mobile-Friendly Navigation

#### Step C1: Add CSS class names for responsive targeting

**File**: `shitty_ui/components/header.py`
**Location**: Lines 46-84 (the navigation links div)

Change the navigation container `style` dict to also include a `className`:

Change:
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
                        style={"display": "flex", "gap": "8px", "alignItems": "center"},
                    ),
```

To:
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

#### Step C2: Add `className="header-logo"` to the logo wrapper div

**File**: `shitty_ui/components/header.py`
**Location**: Lines 15-45 (the logo + subtitle wrapper div)

Change:
```python
                    html.Div(
                        [
                            dcc.Link(
                                html.H1(
                                    [
                                        html.Span(
                                            "Shitpost Alpha",
                                            style={"color": COLORS["accent"]},
                                        ),
                                    ],
                                    style={
                                        "fontSize": "1.75rem",
                                        "fontWeight": "bold",
                                        "margin": 0,
                                    },
                                ),
                                href="/",
                                style={"textDecoration": "none"},
                            ),
                            html.P(
                                "Trading Intelligence Dashboard",
                                style={
                                    "color": COLORS["text_muted"],
                                    "margin": 0,
                                    "fontSize": "0.8rem",
                                },
                            ),
                        ],
                        style={"marginRight": "30px"},
                    ),
```

To:
```python
                    html.Div(
                        [
                            dcc.Link(
                                html.H1(
                                    [
                                        html.Span(
                                            "Shitpost Alpha",
                                            style={"color": COLORS["accent"]},
                                        ),
                                    ],
                                    style={
                                        "fontSize": "1.75rem",
                                        "fontWeight": "bold",
                                        "margin": 0,
                                    },
                                ),
                                href="/",
                                style={"textDecoration": "none"},
                            ),
                            html.P(
                                "Trading Intelligence Dashboard",
                                style={
                                    "color": COLORS["text_muted"],
                                    "margin": 0,
                                    "fontSize": "0.8rem",
                                },
                            ),
                        ],
                        className="header-logo",
                        style={"marginRight": "30px"},
                    ),
```

#### Step C3: Add `className="refresh-detail"` to the refresh countdown rows

**File**: `shitty_ui/components/header.py`
**Location**: Lines 112-161 (the refresh indicator div)

Change the inner wrapper of "Last updated" and "Next refresh" rows:

Change:
```python
                    # Refresh indicator
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.I(
                                        className="fas fa-sync-alt me-2",
                                        style={"color": COLORS["accent"]},
                                    ),
                                    html.Span(
                                        "Last updated ",
                                        style={
                                            "color": COLORS["text_muted"],
                                            "fontSize": "0.7rem",
                                        },
                                    ),
                                    html.Span(
                                        id="last-update-time",
                                        children="--:--",
                                        style={"color": COLORS["text"]},
                                    ),
                                ],
                                style={"marginBottom": "2px"},
                            ),
                            html.Div(
                                [
                                    html.Span(
                                        "Next refresh ",
                                        style={
                                            "color": COLORS["text_muted"],
                                            "fontSize": "0.7rem",
                                        },
                                    ),
                                    html.Span(
                                        id="next-update-countdown",
                                        children="5:00",
                                        style={
                                            "color": COLORS["accent"],
                                            "fontWeight": "bold",
                                            "fontSize": "0.75rem",
                                        },
                                    ),
                                ]
                            ),
                        ],
                        style={
                            "fontSize": "0.8rem",
                            "textAlign": "right",
                        },
                    ),
```

To:
```python
                    # Refresh indicator
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.I(
                                        className="fas fa-sync-alt me-2",
                                        style={"color": COLORS["accent"]},
                                    ),
                                    html.Span(
                                        "Last updated ",
                                        className="refresh-detail",
                                        style={
                                            "color": COLORS["text_muted"],
                                            "fontSize": "0.7rem",
                                        },
                                    ),
                                    html.Span(
                                        id="last-update-time",
                                        children="--:--",
                                        style={"color": COLORS["text"]},
                                    ),
                                ],
                                style={"marginBottom": "2px"},
                            ),
                            html.Div(
                                [
                                    html.Span(
                                        "Next refresh ",
                                        className="refresh-detail",
                                        style={
                                            "color": COLORS["text_muted"],
                                            "fontSize": "0.7rem",
                                        },
                                    ),
                                    html.Span(
                                        id="next-update-countdown",
                                        children="5:00",
                                        style={
                                            "color": COLORS["accent"],
                                            "fontWeight": "bold",
                                            "fontSize": "0.75rem",
                                        },
                                    ),
                                ]
                            ),
                        ],
                        style={
                            "fontSize": "0.8rem",
                            "textAlign": "right",
                        },
                    ),
```

---

### Change D: Dashboard Page -- Responsive Charts and KPI Layout

#### Step D1: Add `className="main-content-container"` to the main content wrapper

**File**: `shitty_ui/pages/dashboard.py`
**Location**: Line 327 (the inner content `html.Div` style dict)

Change:
```python
                style={"padding": "20px", "maxWidth": "1400px", "margin": "0 auto"},
```

To:
```python
                className="main-content-container",
                style={"padding": "20px", "maxWidth": "1400px", "margin": "0 auto"},
```

#### Step D2: Add `className="kpi-col-mobile"` to each KPI column

**File**: `shitty_ui/pages/dashboard.py`
**Location**: Lines 638-692 (inside the `update_dashboard()` callback, the 4 `dbc.Col` wrapping metric cards)

For each of the 4 `dbc.Col` elements wrapping KPI `create_metric_card()` calls, add `className="kpi-col-mobile"`.

Example for the first card (Total Signals):

Change:
```python
                    dbc.Col(
                        create_metric_card(
                            "Total Signals",
                            f"{kpis['total_signals']}",
                            "evaluated predictions",
                            "signal",
                            COLORS["accent"],
                        ),
                        xs=6,
                        sm=6,
                        md=3,
                    ),
```

To:
```python
                    dbc.Col(
                        create_metric_card(
                            "Total Signals",
                            f"{kpis['total_signals']}",
                            "evaluated predictions",
                            "signal",
                            COLORS["accent"],
                        ),
                        xs=6,
                        sm=6,
                        md=3,
                        className="kpi-col-mobile",
                    ),
```

Apply the same `className="kpi-col-mobile"` addition to all 4 `dbc.Col` wrappers: Total Signals, Accuracy, Avg 7-Day Return, and Total P&L.

#### Step D3: Chart responsiveness

Charts already use `config=CHART_CONFIG` from constants.py. The `"responsive": True` flag was added to `CHART_CONFIG` in Change A. No per-graph changes needed in dashboard.py.

#### Step D4: Apply same main-content-container class to /performance page

**File**: `shitty_ui/pages/dashboard.py`
**Location**: Line 452 (the performance page inner div style)

Change:
```python
                style={"padding": "20px", "maxWidth": "1400px", "margin": "0 auto"},
```

To:
```python
                className="main-content-container",
                style={"padding": "20px", "maxWidth": "1400px", "margin": "0 auto"},
```

---

### Change E: Hero Signal Card -- Remove min-width Overflow

This is handled entirely by CSS in Change B (the `@media (max-width: 768px)` rule sets `.hero-signal-card { min-width: unset !important; width: 100% !important; }`). No Python code change is needed beyond the CSS already specified in Step B2.

The inline style `"minWidth": "280px"` on `create_hero_signal_card()` in `cards.py` (line 339) is NOT modified directly. The CSS `!important` override handles mobile without breaking the desktop 280px minimum. This is safer than touching a function used by many call sites.

---

## Test Plan

### New Tests in `shit_tests/shitty_ui/test_layout.py`

#### Test Class: `TestChartConfigResponsive`

```python
class TestChartConfigResponsive:
    """Tests for chart config responsive flag."""

    def test_chart_config_has_responsive_true(self):
        """Test that CHART_CONFIG includes responsive: True."""
        from constants import CHART_CONFIG

        assert CHART_CONFIG.get("responsive") is True
```

#### Test Class: `TestViewportMetaTag`

```python
class TestViewportMetaTag:
    """Tests for the viewport meta tag in the app index string."""

    @patch("data.get_prediction_stats")
    @patch("layout.get_performance_metrics")
    @patch("layout.get_accuracy_by_confidence")
    @patch("layout.get_accuracy_by_asset")
    @patch("layout.get_recent_signals")
    @patch("layout.get_active_assets_from_db")
    def test_index_string_contains_viewport_meta(
        self, mock_assets, mock_signals, mock_asset_acc, mock_conf_acc, mock_perf, mock_stats,
    ):
        """Test that app index_string contains viewport meta tag for mobile."""
        mock_stats.return_value = {"total_posts": 0, "analyzed_posts": 0, "completed_analyses": 0, "bypassed_posts": 0, "avg_confidence": 0.0, "high_confidence_predictions": 0}
        mock_perf.return_value = {"total_outcomes": 0, "evaluated_predictions": 0, "correct_predictions": 0, "incorrect_predictions": 0, "accuracy_t7": 0.0, "avg_return_t7": 0.0, "total_pnl_t7": 0.0, "avg_confidence": 0.0}
        mock_conf_acc.return_value = pd.DataFrame()
        mock_asset_acc.return_value = pd.DataFrame()
        mock_signals.return_value = pd.DataFrame()
        mock_assets.return_value = []

        from layout import create_app
        app = create_app()

        assert 'name="viewport"' in app.index_string
        assert "width=device-width" in app.index_string
```

#### Test Class: `TestMobileCSS`

```python
class TestMobileCSS:
    """Tests for mobile-responsive CSS rules in the app index string."""

    @patch("data.get_prediction_stats")
    @patch("layout.get_performance_metrics")
    @patch("layout.get_accuracy_by_confidence")
    @patch("layout.get_accuracy_by_asset")
    @patch("layout.get_recent_signals")
    @patch("layout.get_active_assets_from_db")
    def _get_app(self, mock_assets, mock_signals, mock_asset_acc, mock_conf_acc, mock_perf, mock_stats):
        """Helper to create the app with mocked data functions."""
        mock_stats.return_value = {"total_posts": 0, "analyzed_posts": 0, "completed_analyses": 0, "bypassed_posts": 0, "avg_confidence": 0.0, "high_confidence_predictions": 0}
        mock_perf.return_value = {"total_outcomes": 0, "evaluated_predictions": 0, "correct_predictions": 0, "incorrect_predictions": 0, "accuracy_t7": 0.0, "avg_return_t7": 0.0, "total_pnl_t7": 0.0, "avg_confidence": 0.0}
        mock_conf_acc.return_value = pd.DataFrame()
        mock_asset_acc.return_value = pd.DataFrame()
        mock_signals.return_value = pd.DataFrame()
        mock_assets.return_value = []
        from layout import create_app
        return create_app()

    def test_has_375px_breakpoint(self):
        """Test that CSS includes a 375px media query."""
        app = self._get_app()
        assert "@media (max-width: 375px)" in app.index_string

    def test_has_480px_breakpoint(self):
        """Test that CSS includes a 480px media query."""
        app = self._get_app()
        assert "@media (max-width: 480px)" in app.index_string

    def test_has_768px_breakpoint(self):
        """Test that CSS includes a 768px media query."""
        app = self._get_app()
        assert "@media (max-width: 768px)" in app.index_string

    def test_touch_target_min_height(self):
        """Test that nav links have min-height: 48px for touch targets."""
        app = self._get_app()
        assert "min-height: 48px" in app.index_string

    def test_hero_card_unset_min_width_on_mobile(self):
        """Test that hero cards have min-width: unset on mobile."""
        app = self._get_app()
        assert "min-width: unset" in app.index_string

    def test_nav_links_row_horizontal_scroll(self):
        """Test that nav-links-row gets overflow-x: auto on mobile."""
        app = self._get_app()
        assert ".nav-links-row" in app.index_string
        assert "overflow-x: auto" in app.index_string

    def test_refresh_detail_hidden_on_small_screens(self):
        """Test that .refresh-detail is hidden below 480px."""
        app = self._get_app()
        assert ".refresh-detail" in app.index_string

    def test_main_content_container_padding_mobile(self):
        """Test that .main-content-container has reduced padding on mobile."""
        app = self._get_app()
        assert ".main-content-container" in app.index_string
```

#### Test Class: `TestHeaderResponsiveClasses`

```python
class TestHeaderResponsiveClasses:
    """Tests for responsive CSS class names on header components."""

    def test_nav_links_have_nav_links_row_class(self):
        """Test that the nav links wrapper has nav-links-row className."""
        from components.header import create_header

        header = create_header()
        # Find the nav links container by looking for a component with className="nav-links-row"
        found = _find_components_with_class(header, "nav-links-row")
        assert len(found) > 0, "nav-links-row className not found in header"

    def test_logo_has_header_logo_class(self):
        """Test that the logo wrapper has header-logo className."""
        from components.header import create_header

        header = create_header()
        found = _find_components_with_class(header, "header-logo")
        assert len(found) > 0, "header-logo className not found in header"

    def test_refresh_labels_have_refresh_detail_class(self):
        """Test that refresh indicator labels have refresh-detail className."""
        from components.header import create_header

        header = create_header()
        found = _find_components_with_class(header, "refresh-detail")
        assert len(found) >= 2, "Expected at least 2 elements with refresh-detail class"
```

Add this helper function to the top of `test_layout.py` (after the existing helpers):

```python
def _find_components_with_class(component, class_name):
    """Recursively find all components with a given className."""
    found = []
    comp_class = getattr(component, "className", None)
    if comp_class and class_name in str(comp_class):
        found.append(component)

    children = getattr(component, "children", None)
    if children is None:
        return found
    if isinstance(children, (list, tuple)):
        for child in children:
            if hasattr(child, "children") or hasattr(child, "className"):
                found.extend(_find_components_with_class(child, class_name))
    elif hasattr(children, "children") or hasattr(children, "className"):
        found.extend(_find_components_with_class(children, class_name))
    return found
```

#### Test Class: `TestDashboardResponsiveProps`

```python
class TestDashboardResponsiveProps:
    """Tests for responsive properties on dashboard page components."""

    def test_main_content_has_responsive_class(self):
        """Test that dashboard main content div has main-content-container class."""
        from pages.dashboard import create_dashboard_page

        page = create_dashboard_page()
        found = _find_components_with_class(page, "main-content-container")
        assert len(found) > 0, "main-content-container className not found in dashboard"

    def test_performance_page_has_responsive_class(self):
        """Test that performance page main content div has main-content-container class."""
        from pages.dashboard import create_performance_page

        page = create_performance_page()
        found = _find_components_with_class(page, "main-content-container")
        assert len(found) > 0, "main-content-container className not found in performance page"

    def test_charts_use_chart_config(self):
        """Test that chart dcc.Graph components use the shared CHART_CONFIG."""
        from pages.dashboard import create_dashboard_page
        from constants import CHART_CONFIG
        from dash import dcc

        page = create_dashboard_page()
        graphs = _find_components_by_type(page, dcc.Graph)
        chart_ids = {"accuracy-over-time-chart", "confidence-accuracy-chart", "asset-accuracy-chart"}
        for graph in graphs:
            if hasattr(graph, "id") and graph.id in chart_ids:
                config = getattr(graph, "config", {}) or {}
                assert config == CHART_CONFIG, (
                    f"Graph '{graph.id}' should use CHART_CONFIG"
                )
```

### New Test in `shit_tests/shitty_ui/test_cards.py`

#### Additions to `TestSentimentLeftBorder` or new class:

```python
class TestHeroCardMobileWidth:
    """Tests that hero signal cards have correct inline min-width for desktop."""

    def test_hero_card_has_280_min_width(self):
        """Test that the desktop inline style still sets minWidth to 280px."""
        card = create_hero_signal_card(_make_row())
        assert card.style.get("minWidth") == "280px"

    def test_hero_card_flex_allows_shrink(self):
        """Test that hero card flex property allows shrinking (flex-basis 0)."""
        card = create_hero_signal_card(_make_row())
        assert "1 1 0" in card.style.get("flex", "")
```

---

## Verification Checklist

- [ ] At 375px viewport: KPI cards render as 2x2 grid without horizontal overflow
- [ ] At 375px viewport: Charts render within viewport width (no horizontal scroll)
- [ ] At 375px viewport: Navigation links are horizontally scrollable, each link at least 48px tall
- [ ] At 375px viewport: Hero signal cards stack vertically at full width
- [ ] At 375px viewport: Page title and card values fit without clipping
- [ ] At 375px viewport: Refresh indicator labels hidden (only times shown)
- [ ] At 390px viewport: Same behavior as 375px, slightly more breathing room
- [ ] At 768px viewport: Header stacks logo and nav vertically; nav links still scrollable
- [ ] At 768px viewport: Analytics tabs text is readable and tappable
- [ ] At desktop (1200px+): Layout is unchanged from pre-Phase-09 state
- [ ] Plotly charts have `config.responsive: True` and resize on viewport change
- [ ] Viewport meta tag present in HTML head
- [ ] All existing tests pass: `source venv/bin/activate && pytest shit_tests/shitty_ui/ -v`
- [ ] New responsive tests pass
- [ ] No horizontal scrollbar on any page at 375px viewport
- [ ] CHANGELOG.md updated

## What NOT To Do

1. **Do NOT use JavaScript-based responsive logic.** All responsiveness must be CSS-only via media queries. Dash clientside_callbacks should not handle layout shifting -- CSS handles it natively and more performantly.

2. **Do NOT modify `create_hero_signal_card()` in `cards.py` to remove `minWidth: 280px`.** The desktop layout depends on this value to prevent cards from being too narrow in flex layouts. The CSS `!important` override at `@media (max-width: 768px)` handles mobile without breaking desktop. Changing the Python inline style would affect all viewports.

3. **Do NOT add a hamburger menu with JavaScript toggling.** A hamburger menu requires a toggle callback, state management, and animation -- excessive complexity for 4 nav links. Horizontal scroll is simpler, standard on mobile, and requires zero JS.

4. **Do NOT use Bootstrap's responsive utility classes (d-none, d-md-block) in place of CSS media queries for the header.** The header is built with raw `html.Div` and `dcc.Link` (not Bootstrap `dbc.NavItem`), so Bootstrap display utilities would not integrate cleanly. Custom CSS classes are more maintainable here.

5. **Do NOT set Plotly chart heights to percentage values.** Plotly requires pixel-based heights. Use CSS class overrides with `!important` to reduce fixed heights at each breakpoint.

6. **Do NOT change the `dbc.Col` `xs`, `sm`, `md` props on KPI columns.** The current `xs=6, sm=6, md=3` grid is correct (2 per row on mobile, 4 per row on desktop). The fix is font/padding reduction via CSS, not column width changes.

7. **Do NOT add a separate mobile stylesheet or external CSS file.** All styles belong in `index_string` to keep the single-file pattern consistent. Adding a separate CSS file would require `assets/` directory configuration.

8. **Do NOT forget to add `className` props needed for CSS targeting.** The CSS rules target `.nav-links-row`, `.header-logo`, `.refresh-detail`, `.main-content-container`, and `.kpi-col-mobile`. Each of these must exist as `className` on the corresponding Python component or the CSS will have no effect.

## CHANGELOG Entry

```markdown
### Fixed
- **Mobile layout at 375px viewport** -- Added comprehensive responsive CSS with three breakpoints (375px, 480px, 768px)
  - KPI cards: reduced padding and font sizes to prevent horizontal overflow on small screens
  - Charts: added `responsive: True` to shared `CHART_CONFIG`; CSS caps chart height per breakpoint
  - Navigation: horizontal-scroll nav links with 48px minimum touch targets (WCAG 2.5.8)
  - Header: stacks vertically on mobile; refresh labels hidden below 480px to save space
  - Hero cards: `min-width` unset on mobile, cards stack vertically at full width
  - Viewport meta tag added to prevent mobile browsers from rendering at desktop width
```
