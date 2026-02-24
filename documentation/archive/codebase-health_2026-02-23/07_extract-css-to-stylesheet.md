# Phase 07: Extract inline CSS to external stylesheet

**Status:** ✅ COMPLETE (PR #91)

| Field | Value |
|-------|-------|
| **PR Title** | refactor: extract 611 lines of inline CSS to external stylesheet |
| **Risk Level** | Low |
| **Effort** | Low (~1-2 hours) |
| **Files Created** | 1 (`shitty_ui/assets/custom.css`) |
| **Files Modified** | 2 (`shitty_ui/layout.py`, `shit_tests/shitty_ui/test_layout.py`) |
| **Files Deleted** | 0 |

## Context

`shitty_ui/layout.py` is 798 lines long. Of those, **611 lines (lines 80-690)** are raw CSS embedded inside the `app.index_string` HTML template. This makes `layout.py` extremely difficult to navigate: the actual Python code (app factory, layout tree, routing callback, callback registration) accounts for only ~190 lines, but is buried beneath a wall of CSS that no Python tooling can lint, format, or autocomplete.

Dash has a built-in convention for this: any CSS file placed in an `assets/` directory adjacent to the app entry point is automatically served and injected into the page. No configuration is required. The `{%css%}` placeholder in `index_string` already handles injection of both external stylesheets (Bootstrap, Font Awesome, Google Fonts) and auto-discovered asset files.

This phase extracts all 611 lines of CSS into `shitty_ui/assets/custom.css` and replaces the bloated `index_string` with a minimal 15-line HTML template. The result: `layout.py` drops from 798 lines to ~190 lines of pure Python, and the CSS gains proper syntax highlighting and linting support in any editor.

**Why this depends on Phase 01**: Phase 01 fixes the pytest conftest blocker that prevents the full test suite from running. This phase modifies 25+ existing tests that assert against `app.index_string`. Those tests must be runnable before and after modification, which requires the Phase 01 conftest fix.

## Dependencies

- **Depends on**: Phase 01 (conftest fix required to run the test suite)
- **Unlocks**: None

## Detailed Implementation Plan

### Step 1: Create `shitty_ui/assets/custom.css`

**File to create**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/assets/custom.css`

This file contains the exact CSS currently embedded in `layout.py` lines 81-689 (the content between the `<style>` and `</style>` tags). Strip the `<style>` and `</style>` wrapper tags; keep everything else verbatim.

```css
html, body {
    overflow-x: hidden;
}
body {
    background-color: #0B1215 !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

/* Card styling */
.card {
    border-radius: 12px !important;
    border: 1px solid #2A3A2E !important;
    overflow: hidden;
    transition: box-shadow 0.15s ease;
}
.card-header {
    border-bottom: 1px solid #2A3A2E !important;
}

/* Hero signal card hover effect */
.hero-signal-card {
    transition: transform 0.15s ease, box-shadow 0.15s ease;
    border-radius: 12px;
}
.hero-signal-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 20px rgba(133, 187, 101, 0.15);
}

/* Unified signal card hover effect */
.unified-signal-card {
    transition: transform 0.15s ease, box-shadow 0.15s ease;
    border-radius: 8px;
}
.unified-signal-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 20px rgba(133, 187, 101, 0.15);
}

/* Sentiment badges */
.sentiment-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 10px;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* Nav links with active state accent */
.nav-link-custom {
    color: #8B9A7E !important;
    text-decoration: none !important;
    padding: 8px 16px;
    border-radius: 8px;
    font-weight: 500;
    font-size: 0.9rem;
    transition: all 0.15s ease;
    position: relative;
}
.nav-link-custom:hover {
    color: #F5F1E8 !important;
    background-color: #2A3A2E;
}
.nav-link-custom.active {
    color: #F5F1E8 !important;
    background-color: transparent;
}
.nav-link-custom.active::after {
    content: '';
    position: absolute;
    bottom: -2px;
    left: 16px;
    right: 16px;
    height: 2px;
    background-color: #FFD700;
    border-radius: 1px;
}

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

    /* Period selector: center and allow wrapping */
    .period-selector {
        justify-content: center !important;
        flex-wrap: wrap !important;
        gap: 6px;
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
    /* Content container: tighter padding */
    .main-content-container {
        padding: 12px 8px !important;
    }

    /* Logo: smaller to prevent clipping */
    .header-logo {
        margin-right: 0 !important;
    }
    .header-logo h1 {
        font-size: 1.1rem !important;
    }
    .header-logo p {
        font-size: 0.65rem !important;
    }

    /* KPI hero values: scale down to fit 50% column */
    .kpi-hero-value {
        font-size: 1.4rem !important;
    }
    .kpi-hero-card .card-body {
        padding: 6px 4px !important;
        min-height: auto !important;
    }

    /* KPI icon circles: shrink */
    .kpi-hero-card .card-body > div:first-child {
        width: 28px !important;
        height: 28px !important;
        margin-bottom: 6px !important;
    }
    .kpi-hero-card .card-body > div:first-child .fas {
        font-size: 0.8rem !important;
    }

    /* Tighter padding on cards */
    .metric-card .card-body {
        padding: 8px !important;
    }
    .metric-card h3 {
        font-size: 1.1rem !important;
    }
    .metric-card p {
        font-size: 0.7rem !important;
    }

    /* Period selector: center and wrap */
    .period-selector {
        justify-content: center !important;
        flex-wrap: wrap !important;
        gap: 6px;
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
        padding: 10px 8px !important;
    }

    /* Logo: smaller to prevent clipping */
    .header-logo {
        margin-right: 0 !important;
    }
    .header-logo h1 {
        font-size: 1.1rem !important;
    }
    .header-logo p {
        font-size: 0.65rem !important;
    }

    /* KPI cards: full width at 375px */
    .kpi-col-mobile {
        flex: 0 0 50% !important;
        max-width: 50% !important;
    }

    /* KPI hero values: scale down to fit 50% column */
    .kpi-hero-value {
        font-size: 1.4rem !important;
    }
    .kpi-hero-card .card-body {
        padding: 6px 4px !important;
        min-height: auto !important;
    }

    /* KPI icon circles: shrink */
    .kpi-hero-card .card-body > div:first-child {
        width: 28px !important;
        height: 28px !important;
        margin-bottom: 6px !important;
    }
    .kpi-hero-card .card-body > div:first-child .fas {
        font-size: 0.8rem !important;
    }

    /* KPI title labels: tighter */
    .metric-card h3 {
        font-size: 1rem !important;
        word-break: break-all;
    }
    .metric-card .card-body {
        padding: 6px !important;
    }
    .metric-card p {
        font-size: 0.7rem !important;
    }

    /* Icon size reduction (legacy metric-card) */
    .metric-card .fas {
        font-size: 1.1rem !important;
    }

    /* Period selector: center and wrap to prevent "All" clipping */
    .period-selector {
        justify-content: center !important;
        flex-wrap: wrap !important;
        gap: 6px;
    }
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

/* Ensure charts resize properly */
.js-plotly-plot {
    width: 100% !important;
}

/* Loading spinner styling */
._dash-loading {
    margin: 20px auto;
}

/* Scrollbar styling for dark theme */
::-webkit-scrollbar { width: 8px; }
::-webkit-scrollbar-track { background: #0B1215; }
::-webkit-scrollbar-thumb { background: #2A3A2E; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #3D5440; }

/* ======================================
   Typography hierarchy classes
   ====================================== */

/* Page title - used for top-level page headers */
.page-title {
    font-size: 1.75rem;
    font-weight: 700;
    color: #F5F1E8;
    margin: 0 0 4px 0;
    line-height: 1.2;
}
.page-title .page-subtitle {
    display: block;
    font-size: 0.8rem;
    font-weight: 400;
    color: #8B9A7E;
    margin-top: 4px;
}

/* Section header - major sections within a page */
.section-header {
    font-size: 1.15rem;
    font-weight: 600;
    color: #F5F1E8;
    margin: 0;
    padding-bottom: 8px;
    border-bottom: 2px solid #85BB65;
    margin-bottom: 16px;
    display: inline-block;
}

/* Card header title override - consistent sizing for all card headers */
.card-header {
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    color: #F5F1E8 !important;
    letter-spacing: 0.01em;
}
.card-header .card-header-subtitle {
    font-size: 0.8rem;
    font-weight: 400;
    color: #8B9A7E;
    margin-left: 8px;
}

/* Body text class for standard content */
.text-body-default {
    font-size: 0.9rem;
    font-weight: 400;
    color: #F5F1E8;
    line-height: 1.5;
}

/* Label text for form labels and metadata labels */
.text-label {
    font-size: 0.8rem;
    font-weight: 500;
    color: #8B9A7E;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* Metadata text for timestamps, IDs, fine print */
.text-meta {
    font-size: 0.75rem;
    font-weight: 400;
    color: #8B9A7E;
    line-height: 1.4;
}

/* Active signals section header (uppercase label style) */
.section-label {
    font-size: 0.85rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: #F5F1E8;
}
.section-label .section-label-muted {
    font-weight: 400;
    text-transform: none;
    letter-spacing: normal;
    color: #8B9A7E;
    font-size: 0.8rem;
}

/* ======================================
   Analytics tab interface
   ====================================== */
.analytics-tabs .nav-tabs {
    border-bottom: 1px solid #2A3A2E;
    background-color: transparent;
}
.analytics-tabs .nav-link {
    color: #8B9A7E !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    background-color: transparent !important;
    padding: 10px 20px;
    font-size: 0.9rem;
    font-weight: 500;
    transition: all 0.15s ease;
}
.analytics-tabs .nav-link:hover {
    color: #F5F1E8 !important;
    border-bottom-color: #3D5440 !important;
}
.analytics-tabs .nav-link.active {
    color: #85BB65 !important;
    border-bottom-color: #85BB65 !important;
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
    box-shadow: 0 8px 32px rgba(133, 187, 101, 0.12), 0 2px 6px rgba(0, 0, 0, 0.25) !important;
}
.kpi-hero-value {
    font-variant-numeric: tabular-nums;
}

/* Tertiary tier: posts, data table (receded) */
.section-tertiary {
    border-radius: 10px;
}
.section-tertiary .card-header {
    background-color: #0E1719 !important;
    border-bottom-color: #2A3A2E !important;
}
.section-tertiary .card-body {
    background-color: #0E1719 !important;
}

/* Header elevation shadow */
.header-container {
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
    position: relative;
    z-index: 10;
}

/* ======================================
   Thesis expand/collapse
   ====================================== */
.thesis-toggle-area {
    cursor: pointer;
    user-select: none;
}
.thesis-toggle-area:hover {
    text-decoration: underline;
}

/* ======================================
   Asset Screener Table
   ====================================== */
.screener-row:hover {
    background-color: rgba(133, 187, 101, 0.06) !important;
}
.screener-row:hover td {
    background-color: rgba(133, 187, 101, 0.06) !important;
}

/* ======================================
   Screener: Tablet (max-width: 768px)
   ====================================== */
@media (max-width: 768px) {
    .screener-table-container {
        overflow-x: auto !important;
        -webkit-overflow-scrolling: touch;
    }
    .screener-hide-tablet {
        display: none !important;
    }
}

/* ======================================
   Screener: Mobile (max-width: 480px)
   ====================================== */
@media (max-width: 480px) {
    .screener-row td {
        padding: 6px 8px !important;
        font-size: 0.8rem !important;
    }
    .screener-hide-mobile {
        display: none !important;
    }
}
```

**Important**: The CSS above is an exact byte-for-byte copy of `layout.py` lines 81-689 (everything between `<style>` and `</style>`). Do not reformat, reorder, or minify it. A verbatim extraction ensures zero visual regressions.

### Step 2: Replace `app.index_string` in `layout.py`

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/layout.py`

**Lines to replace**: 70-701 (the comment `# Custom CSS for mobile responsiveness and dark theme` through the closing `"""` of `index_string`)

**Current code** (lines 70-701):

```python
    # Custom CSS for mobile responsiveness and dark theme
    app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5">
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            html, body {
                overflow-x: hidden;
            }
            ... (611 lines of CSS) ...
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
"""
```

**Replace with**:

```python
    # Custom index template — CSS lives in assets/custom.css (auto-loaded by Dash)
    app.index_string = """<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5">
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>"""
```

**Key details**:
- The `<meta name="viewport" ...>` tag is **preserved** in the template. This is the only custom addition beyond Dash's standard placeholders. It must not be lost.
- The `{%css%}` placeholder remains. Dash injects external stylesheets (Bootstrap, Font Awesome, Google Fonts from the `external_stylesheets` list) **and** any CSS files found in the `assets/` directory through this placeholder.
- The `<style>...</style>` block is completely removed. All CSS now comes from `assets/custom.css`.
- The `<footer>` wrapper around `{%config%}`, `{%scripts%}`, `{%renderer%}` is preserved (this is Dash's required structure).

### Step 3: Verify `assets/` directory compatibility with `register_client_routes`

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/app.py` (lines 75-99)

**No changes needed.** The existing `register_client_routes` function already handles the `/assets/` route conflict between Dash's static file serving and the app's `/assets/<symbol>` SPA routes. It checks for file extensions:

```python
_STATIC_EXTENSIONS = frozenset((
    ".css", ".js", ".json", ".png", ".jpg", ".jpeg", ".gif",
    ".ico", ".svg", ".woff", ".woff2", ".ttf", ".map", ".gz",
))
```

A request for `/assets/custom.css` will match `.css` in `_STATIC_EXTENSIONS` and be served as a static file by Dash. A request for `/assets/TSLA` will not match any extension and will be routed to the SPA. No conflict.

### Step 4: Update existing tests in `test_layout.py`

**File**: `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_layout.py`

There are **25+ test assertions** across 7 test classes that check `app.index_string` for the presence of CSS classes and rules. After extraction, `app.index_string` will no longer contain any CSS. These tests must be rewritten to read the CSS file directly instead.

#### Step 4a: Add a helper fixture/function to read the CSS file

Add this helper function near the top of the test file (after the existing imports, before the first test class):

```python
import os

def _read_custom_css() -> str:
    """Read the custom CSS file from the assets directory."""
    css_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "..", "shitty_ui", "assets", "custom.css",
    )
    with open(css_path) as f:
        return f.read()
```

This resolves relative to the test file location: `shit_tests/shitty_ui/test_layout.py` -> `../../shitty_ui/assets/custom.css`.

#### Step 4b: Update `TestTypographyCSS` class (around line 1492)

**Test: `test_index_string_contains_section_header_class`** (line 1492)

Current assertions (lines 1506-1510):
```python
        assert ".section-header" in app.index_string
        assert ".page-title" in app.index_string
        assert ".text-label" in app.index_string
        assert ".text-meta" in app.index_string
        assert ".section-label" in app.index_string
```

Replace the entire test method body with:
```python
    def test_custom_css_contains_section_header_class(self):
        """Test that custom.css contains .section-header CSS class."""
        css = _read_custom_css()

        assert ".section-header" in css
        assert ".page-title" in css
        assert ".text-label" in css
        assert ".text-meta" in css
        assert ".section-label" in css
```

Note: This test no longer needs the 6 `@patch` decorators or the `mock_*` parameters, since it does not create a Dash app. Remove all the `@patch` decorators and mock parameters from the method signature.

**Test: `test_index_string_contains_active_nav_pseudo_element`** (line 1518)

Current assertion (line 1532):
```python
        assert ".nav-link-custom.active::after" in app.index_string
```

Replace with:
```python
    def test_custom_css_contains_active_nav_pseudo_element(self):
        """Test that custom.css contains nav-link active ::after pseudo-element."""
        css = _read_custom_css()

        assert ".nav-link-custom.active::after" in css
```

Remove all `@patch` decorators and mock parameters.

**Test: `test_card_header_has_font_size_override`** (line 1540)

Current assertion (line 1555):
```python
        assert "0.95rem" in app.index_string
```

Replace with:
```python
    def test_custom_css_contains_card_header_font_size(self):
        """Test that .card-header CSS includes font-size override."""
        css = _read_custom_css()

        assert "0.95rem" in css
```

Remove all `@patch` decorators and mock parameters.

#### Step 4c: Update `TestAnalyticsTabCSS` class (around line 1694)

**Test: `test_index_string_contains_analytics_tabs_css`** (line 1694)

Current assertions (lines 1708-1710):
```python
        assert ".analytics-tabs" in app.index_string
        assert ".collapse-chevron" in app.index_string
        assert ".collapse-chevron.rotated" in app.index_string
```

Replace with:
```python
    def test_custom_css_contains_analytics_tabs_css(self):
        """Test that custom.css contains .analytics-tabs CSS."""
        css = _read_custom_css()

        assert ".analytics-tabs" in css
        assert ".collapse-chevron" in css
        assert ".collapse-chevron.rotated" in css
```

Remove all `@patch` decorators and mock parameters.

**Test: `test_index_string_contains_collapse_toggle_css`** (line 1718)

Current assertion (line 1732):
```python
        assert ".collapse-toggle-btn" in app.index_string
```

Replace with:
```python
    def test_custom_css_contains_collapse_toggle_css(self):
        """Test that custom.css contains .collapse-toggle-btn CSS."""
        css = _read_custom_css()

        assert ".collapse-toggle-btn" in css
```

Remove all `@patch` decorators and mock parameters.

#### Step 4d: Update thesis toggle test (around line 1831)

**Test: `test_index_string_contains_thesis_toggle_css`** (line 1831)

Current assertion (line 1845):
```python
        assert ".thesis-toggle-area" in app.index_string
```

Replace with:
```python
    def test_custom_css_contains_thesis_toggle_css(self):
        """Test that custom.css contains .thesis-toggle-area CSS class."""
        css = _read_custom_css()

        assert ".thesis-toggle-area" in css
```

Remove all `@patch` decorators and mock parameters.

#### Step 4e: Update visual hierarchy tests (around line 1924)

**Test: `test_index_string_contains_kpi_hero_card_css`** (line 1924)

Current assertions (lines 1938-1939):
```python
        assert ".kpi-hero-card" in app.index_string
        assert ".kpi-hero-card:hover" in app.index_string
```

Replace with:
```python
    def test_custom_css_contains_kpi_hero_card_css(self):
        """Test that custom.css contains .kpi-hero-card CSS class."""
        css = _read_custom_css()

        assert ".kpi-hero-card" in css
        assert ".kpi-hero-card:hover" in css
```

Remove all `@patch` decorators and mock parameters.

**Test: `test_index_string_contains_section_tertiary_css`** (line 1947)

Current assertions (lines 1961-1963):
```python
        assert ".section-tertiary" in app.index_string
        assert ".section-tertiary .card-header" in app.index_string
        assert ".section-tertiary .card-body" in app.index_string
```

Replace with:
```python
    def test_custom_css_contains_section_tertiary_css(self):
        """Test that custom.css contains .section-tertiary CSS overrides."""
        css = _read_custom_css()

        assert ".section-tertiary" in css
        assert ".section-tertiary .card-header" in css
        assert ".section-tertiary .card-body" in css
```

Remove all `@patch` decorators and mock parameters.

**Test: `test_index_string_contains_tabular_nums`** (line 1971)

Current assertion (line 1985):
```python
        assert "tabular-nums" in app.index_string
```

Replace with:
```python
    def test_custom_css_contains_tabular_nums(self):
        """Test that custom.css uses tabular-nums for KPI values."""
        css = _read_custom_css()

        assert "tabular-nums" in css
```

Remove all `@patch` decorators and mock parameters.

**Test containing `box-shadow` assertion** (around line 2007):

Current assertion (line 2007):
```python
        assert "box-shadow:" in app.index_string or "boxShadow" in app.index_string
```

Replace with:
```python
    def test_custom_css_contains_header_elevation_shadow(self):
        """Test that custom.css contains header elevation box-shadow."""
        css = _read_custom_css()

        assert "box-shadow:" in css
```

Remove all `@patch` decorators and mock parameters. Note: The `"boxShadow"` alternative (Python inline style) is no longer needed since we are checking the CSS file, not `index_string`.

#### Step 4f: Update `TestViewportMetaTag` class (around line 2020)

**Test: `test_index_string_contains_viewport_meta`** (line 2029)

This test checks the `<meta name="viewport">` tag which remains in `app.index_string`. **This test stays as-is.** The viewport meta tag is in the HTML template, not the CSS. No changes needed.

#### Step 4g: Update `TestMobileCSS` class (around line 2047)

The `_get_app` helper method (line 2056) creates a Dash app to check `app.index_string`. Replace it with a CSS-reading approach.

**Replace the `_get_app` method** (lines 2056-2065) with:

```python
    def _get_css(self):
        """Read the custom CSS file."""
        return _read_custom_css()
```

**Update all 8 test methods** in this class to use `_get_css()` instead of `_get_app()`:

- `test_has_375px_breakpoint` (line 2067): change `app = self._get_app()` to `css = self._get_css()`, then change `app.index_string` to `css`
- `test_has_480px_breakpoint` (line 2072): same pattern
- `test_has_768px_breakpoint` (line 2077): same pattern
- `test_touch_target_min_height` (line 2082): same pattern
- `test_hero_card_unset_min_width_on_mobile` (line 2087): same pattern
- `test_nav_links_row_horizontal_scroll` (line 2092): same pattern
- `test_refresh_detail_hidden_on_small_screens` (line 2098): same pattern
- `test_main_content_container_padding_mobile` (line 2103): same pattern

Example for `test_has_375px_breakpoint`:

Before:
```python
    def test_has_375px_breakpoint(self):
        """Test that CSS includes a 375px media query."""
        app = self._get_app()
        assert "@media (max-width: 375px)" in app.index_string
```

After:
```python
    def test_has_375px_breakpoint(self):
        """Test that CSS includes a 375px media query."""
        css = self._get_css()
        assert "@media (max-width: 375px)" in css
```

Apply the same pattern to all 8 tests. This also removes the need for the `_get_app` method's 6 `@patch` decorators, since `_get_css` does not instantiate a Dash app.

#### Summary of test changes

| Test class | Tests modified | Change |
|-----------|---------------|--------|
| `TestTypographyCSS` | 3 | Read `custom.css` instead of `app.index_string` |
| Analytics tabs test class | 2 | Read `custom.css` instead of `app.index_string` |
| Thesis toggle test class | 1 | Read `custom.css` instead of `app.index_string` |
| Visual hierarchy test class | 4 | Read `custom.css` instead of `app.index_string` |
| `TestViewportMetaTag` | 0 | **No change** (checks HTML, not CSS) |
| `TestMobileCSS` | 8 + helper | Read `custom.css` instead of `app.index_string` |
| **Total** | **~18 tests** | Remove mock decorators, read CSS file directly |

**Benefit of this approach**: These tests now run ~10x faster because they read a CSS file from disk instead of instantiating a full Dash app with 6 mocked database functions each.

## Test Plan

### New tests to add

Add one new test to verify the Dash app picks up the `assets/` directory. Place this in the existing `TestViewportMetaTag` class (or a new class nearby):

```python
class TestCSSExternalFile:
    """Tests verifying CSS is served from assets/custom.css."""

    def test_custom_css_file_exists(self):
        """Test that shitty_ui/assets/custom.css exists on disk."""
        css_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "..", "shitty_ui", "assets", "custom.css",
        )
        assert os.path.isfile(css_path), f"Expected CSS file at {css_path}"

    def test_custom_css_is_not_empty(self):
        """Test that custom.css has substantial content (>500 lines)."""
        css = _read_custom_css()
        line_count = len(css.strip().splitlines())
        assert line_count > 500, f"Expected 500+ lines, got {line_count}"

    def test_index_string_does_not_contain_style_tag(self):
        """Test that index_string no longer has an embedded <style> block."""
        from layout import create_app
        app = create_app()
        assert "<style>" not in app.index_string
```

Note: The third test (`test_index_string_does_not_contain_style_tag`) does need to create a Dash app and will need the standard mock decorators.

### Existing tests to modify

See Step 4 above for the complete list of ~18 tests that change from checking `app.index_string` to checking the CSS file.

### Manual verification steps

1. Run the full test suite: `./venv/bin/python -m pytest shit_tests/shitty_ui/test_layout.py -v`
2. Verify all CSS-related tests pass with the new approach
3. Start the dashboard locally: `cd shitty_ui && ../venv/bin/python app.py`
4. Open `http://localhost:8050` in a browser
5. Open DevTools > Network tab and verify `custom.css` is loaded (look for a request to `/assets/custom.css`)
6. Open DevTools > Elements tab and verify the CSS rules are applied (check any `.card` element for `border-radius: 12px`)
7. Resize the browser to 375px width and verify responsive styles still apply
8. Navigate to `/assets/TSLA` and verify it loads the asset detail page (not a 404)

## Documentation Updates

### Inline comment in `layout.py`

The existing comment on line 70:
```python
    # Custom CSS for mobile responsiveness and dark theme
```

Becomes:
```python
    # Custom index template — CSS lives in assets/custom.css (auto-loaded by Dash)
```

### CLAUDE.md

No changes needed. The `CLAUDE.md` architecture diagram already shows `shitty_ui/` as a top-level module. The `assets/` directory is a standard Dash convention and does not need explicit documentation.

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Changed
- **Dashboard CSS extraction** - Moved 611 lines of inline CSS from `layout.py` to `shitty_ui/assets/custom.css`
  - `layout.py` reduced from ~800 lines to ~190 lines of pure Python
  - CSS now gets proper syntax highlighting and linting in editors
  - Dash auto-loads CSS from the `assets/` directory (no config needed)
```

## Stress Testing & Edge Cases

### Edge case: CSS load order

Dash loads CSS in this order:
1. External stylesheets from `external_stylesheets` (Bootstrap Darkly, Font Awesome, Google Fonts)
2. CSS files from `assets/` directory (alphabetical order)

Since `custom.css` uses `!important` on virtually all overrides, load order does not matter. The existing CSS was already designed to override Bootstrap with `!important`, and that behavior is preserved.

### Edge case: `/assets/` route conflict

As documented in Step 3, the existing `register_client_routes` function in `app.py` already handles this. Requests for `/assets/custom.css` match the `.css` extension and are served as static files. Requests for `/assets/TSLA` have no extension and are routed to the SPA.

### Edge case: Railway deployment

Railway's build process runs `pip install -r requirements.txt` and then starts the app. The `assets/` directory is part of the git repository and will be deployed alongside the code. No Dockerfile or build configuration changes are needed.

### Edge case: Multiple CSS files in `assets/`

If additional CSS files are added to `assets/` in the future, Dash will load them all in alphabetical order. This is the expected behavior and does not cause conflicts. Name the file `custom.css` (not `styles.css` or `main.css`) to make its purpose clear and to sort after any future `base.css` or `components.css` files.

## Verification Checklist

- [ ] `shitty_ui/assets/custom.css` exists and contains 609 lines of CSS (the content between `<style>` and `</style>`, not including those tags)
- [ ] `shitty_ui/layout.py` `app.index_string` is ~15 lines (HTML template only, no `<style>` block)
- [ ] `shitty_ui/layout.py` `app.index_string` still contains `<meta name="viewport" ...>` tag
- [ ] `shitty_ui/layout.py` `app.index_string` still contains `{%css%}` placeholder
- [ ] `shitty_ui/layout.py` `app.index_string` still contains `{%app_entry%}`, `{%config%}`, `{%scripts%}`, `{%renderer%}` placeholders
- [ ] `shitty_ui/layout.py` total line count is under 200
- [ ] `shitty_ui/app.py` is **unchanged** (no modifications needed)
- [ ] All ~18 modified tests in `test_layout.py` pass
- [ ] New `TestCSSExternalFile` tests pass
- [ ] `TestViewportMetaTag.test_index_string_contains_viewport_meta` still passes (this one stays as-is)
- [ ] `./venv/bin/python -m pytest shit_tests/shitty_ui/ -v` passes with 0 failures
- [ ] `./venv/bin/python -m ruff check shitty_ui/layout.py` passes
- [ ] Dashboard loads at `http://localhost:8050` with correct styling
- [ ] DevTools Network tab shows `/assets/custom.css` being loaded
- [ ] Responsive layout at 375px viewport still works
- [ ] `/assets/TSLA` route still loads asset detail page (not a CSS file or 404)

## What NOT To Do

1. **Do NOT reformat, minify, or reorder the CSS.** Extract it verbatim from `layout.py`. Any reformatting risks introducing subtle CSS specificity changes or breaking media query ordering. The CSS should be a byte-for-byte copy of the content between `<style>` and `</style>`.

2. **Do NOT replace hardcoded hex colors with CSS custom properties (variables).** The research confirmed all 9 hex codes have zero Python dependencies. Converting to `var(--color-bg)` is a separate enhancement and would change the scope of this PR.

3. **Do NOT remove the `<meta name="viewport">` tag from `index_string`.** This tag is critical for mobile rendering. It is the only custom element in the HTML template beyond Dash's standard placeholders. Removing it would break responsive layout on all mobile devices.

4. **Do NOT create a `shitty_ui/assets/__init__.py` file.** The `assets/` directory is a static file directory, not a Python package. Dash serves it as a static directory. An `__init__.py` would be misleading.

5. **Do NOT modify `shitty_ui/app.py`.** The existing `register_client_routes` function already handles the `/assets/` route conflict correctly. No changes are needed.

6. **Do NOT split the CSS into multiple files** (e.g., `base.css`, `responsive.css`, `components.css`). This is a pure extraction refactor. File organization can be improved in a future PR. One file, verbatim extraction, zero risk.

7. **Do NOT add `assets_folder` configuration to the `Dash()` constructor.** Dash defaults to looking for an `assets/` directory relative to `__name__` (which is `layout` in this case, resolving to `shitty_ui/assets/`). The default behavior is correct. Adding explicit configuration is unnecessary and could break if the working directory changes.

8. **Do NOT keep the old CSS in `index_string` "just in case."** The whole point is to remove it. If both the inline CSS and external CSS exist simultaneously, every rule will be duplicated and specificity issues may arise.

9. **Do NOT delete or skip updating the test assertions.** The ~18 tests that currently check `app.index_string` for CSS classes will all fail after extraction. Every one must be updated to read `custom.css` instead. Skipping this will cause a test suite regression.

10. **Do NOT use `pathlib` for the test helper function.** The existing test file uses `os.path` throughout. Stay consistent with the codebase convention.
