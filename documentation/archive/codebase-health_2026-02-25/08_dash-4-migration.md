# Phase 08 — Dash 4 Migration

| Field | Value |
|---|---|
| **PR Title** | `chore: migrate dashboard from Dash 2.x to Dash 4.0` |
| **Risk** | High — production dashboard, visual breaking changes, dependency chain |
| **Effort** | High (~8 hours) |
| **Files Modified** | 5 |
| **Files Created** | 1 |
| **Dependencies** | Phase 04 (callback split) recommended but not blocking |
| **Unlocks** | None (terminal improvement) |

---

## Context

The dashboard currently pins `dash>=2.14.0` in `/Users/chris/Projects/shitpost-alpha/requirements.txt` (line 52). Dash 4.0.0 was released as a stable version on February 3, 2025, bringing redesigned core components built on Radix, improved default behaviors, and modernized styling. The app also uses `dash-bootstrap-components>=1.5.0` (line 54), which is a major version behind the current `dbc 2.0.4`.

Upgrading is necessary because:
1. The current Dash 2.x line is two major versions behind and will stop receiving security patches.
2. Dash 4.0 brings improved slider, dropdown, date picker, and loading components with better mobile responsiveness (aligning with the project's mobile-first design).
3. The `dbc 2.0.x` series requires `dash>=3.0.3`, so any dbc upgrade also requires at minimum Dash 3.x.

**Key Dash 4.0 characteristics from official sources:**
- **API backward compatible**: Python property APIs are unchanged. No import path changes. `dcc.Slider`, `dcc.Dropdown`, `dcc.Input`, `dcc.RangeSlider`, `dcc.DatePickerRange`, `dcc.Loading`, `dcc.Checklist`, `dcc.RadioItems`, `dcc.Tabs`, `dcc.TextArea`, `dcc.Tooltip` all received visual redesigns.
- **CSS selectors changed**: Apps with custom CSS targeting DCC component internals (e.g., `rc-slider-*` classes) need updates. Dash 4 uses Radix-based components with different DOM structures.
- **Default property changes**: `dcc.Slider.step` now only defaults to `1` when min and max are both integers; `dcc.Dropdown.optionHeight` defaults to `'auto'`; `dcc.Dropdown.closeOnSelect` defaults to `True` for single-select, `False` for multi-select.
- **`dash-bootstrap-components`**: Version 2.0.4 requires `dash>=3.0.3`. No dbc version explicitly declares Dash 4.0 support yet, but since Dash 4.0 maintains API backward compatibility, dbc 2.0.4 should work. This is a risk that must be verified.

---

## Dependencies

- **Phase 04** (callback split) — Recommended to complete first, as it makes the callback files smaller and easier to verify after migration. However, Phase 08 can proceed independently since the migration does not change callback logic, only dependency versions and potentially CSS.
- **No phases are blocked by this one.**

---

## Detailed Implementation Plan

### Step 1: Update `requirements.txt` dependency versions

**File**: `/Users/chris/Projects/shitpost-alpha/requirements.txt`

**Current** (lines 52-54):
```python
dash>=2.14.0
plotly>=5.15.0
dash-bootstrap-components>=1.5.0
```

**After**:
```python
dash>=4.0.0,<5.0.0
plotly>=5.15.0
dash-bootstrap-components>=2.0.0,<3.0.0
```

**Why**: Pin to `dash>=4.0.0,<5.0.0` to stay on the 4.x line. Pin `dbc>=2.0.0,<3.0.0` because dbc 2.x is the line that supports Dash 3+/4+. Plotly stays unchanged — it is a separate package from Dash and 5.x is compatible with Dash 4.

### Step 2: Audit and fix `dcc.Slider` and `dcc.RangeSlider` step behavior

Dash 4.0 changed the default `step` behavior: it only defaults to `1` when both `min` and `max` are integers. If they are floats, `step` is dynamically computed. The app has two slider usages that could be affected.

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/callbacks/alert_components.py` (lines 109-133)

The `dcc.Slider` at line 109 already has `step=0.05` explicitly set, and `min=0.0`, `max=1.0` are floats. Since `step` is already explicit, **no change needed**. However, verify visually after upgrade that slider renders correctly.

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/controls.py` (lines 30-37)

The `dcc.RangeSlider` at line 30 already has `step=0.05` explicitly set, and `min=0`, `max=1` are integers. Since `step` is already explicit, **no change needed**. However, note that `marks={0: "0", 0.5: "0.5", 1: "1"}` uses a simplified marks format. In Dash 4, marks still accept this format. Verify visually.

**Verdict**: Both sliders have explicit `step` props. No code change required for step behavior, but visual verification is mandatory.

### Step 3: Audit `dcc.Dropdown` default behavior changes

Dash 4.0 changes:
- `optionHeight` defaults to `'auto'` (was fixed pixel) — enables text wrapping
- `closeOnSelect` defaults to `True` for single-select, `False` for multi-select

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/callbacks/alert_components.py` (line 162)

The alert assets dropdown at line 162 is `multi=True`. In Dash 4, `closeOnSelect` defaults to `False` for multi-select dropdowns, which matches the expected behavior (keep dropdown open while selecting multiple assets). **No change needed.**

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/controls.py` (line 58)

The limit selector dropdown at line 58 is single-select (`multi` not set, defaults to `False`). In Dash 4, `closeOnSelect` defaults to `True` for single-select, which is correct behavior. **No change needed.**

**Verdict**: No dropdown code changes required. The new defaults match expected behavior.

### Step 4: Audit `dcc.DatePickerRange` for changes

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/controls.py` (lines 45-50)

The `dcc.DatePickerRange` at line 45 uses `start_date`, `end_date`, `display_format`. Dash 4.0 redesigned date pickers but preserved API compatibility. The `display_format` prop remains valid. **No code change needed**, but visual verification required since the date picker UI will look different.

### Step 5: Audit and update custom CSS for Dash 4 compatibility

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/assets/custom.css`

The custom CSS targets several classes that may be affected by Dash 4's component redesign:

**Line 383-385 — Loading spinner styling**:
```css
._dash-loading {
    margin: 20px auto;
}
```
The `._dash-loading` class is a Dash internal class. Dash 4's redesigned `dcc.Loading` component may use different class names. **Action**: After installing Dash 4, inspect the Loading component DOM in browser dev tools. If the `._dash-loading` class no longer exists, update or remove this rule. The rule is cosmetic (just centers the spinner) so removing it has low impact.

**Line 180-182 — DataTable horizontal scroll**:
```css
.dash-spreadsheet-container {
    overflow-x: auto !important;
}
```
The `dash_table.DataTable` component uses `.dash-spreadsheet-container`. This class name is part of `dash-table` which is bundled with Dash. It was not specifically called out as changed in Dash 4 release notes, but verify after upgrade.

**Line 377-380 — Plotly chart resize**:
```css
.js-plotly-plot {
    width: 100% !important;
}
```
This targets Plotly's own DOM class, not a Dash component class. **No change expected**.

**Line 138 — Plotly SVG sizing**:
```css
.js-plotly-plot .plotly .main-svg {
    max-width: 100% !important;
}
```
Same as above — Plotly DOM class. **No change expected**.

**Lines 483-508 — Analytics tabs styling**:
```css
.analytics-tabs .nav-tabs { ... }
.analytics-tabs .nav-link { ... }
.analytics-tabs .nav-link.active { ... }
```
These target dbc Bootstrap classes, not dcc classes. The `dcc.Tabs` component was redesigned in Dash 4, but this app does NOT use `dcc.Tabs` — it uses `dbc.Tabs` via Bootstrap styling. **No change needed**.

**Overall CSS verdict**: The custom CSS does not target any `rc-slider-*` or other DCC-internal CSS classes directly. The only risky selector is `._dash-loading`. The migration should preserve CSS compatibility for all other rules.

**Action for `custom.css`**: If `._dash-loading` is no longer valid after testing, update lines 383-385. If `dcc.Loading` no longer emits a wrapper class, this rule can be safely deleted since it only adds centering margin.

### Step 6: Audit `app.index_string` template compatibility

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/layout.py` (lines 71-88)

The app uses a custom `index_string` template with Jinja2-style template tags: `{%metas%}`, `{%title%}`, `{%favicon%}`, `{%css%}`, `{%app_entry%}`, `{%config%}`, `{%scripts%}`, `{%renderer%}`. These template tags are core Dash functionality and remain unchanged in Dash 4. **No change needed.**

### Step 7: Audit `app.server` Flask usage

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/app.py` (lines 20-100)

The app accesses `app.server` (the underlying Flask instance) to register webhook routes and client-side routing hooks. `app.server` is a stable public API in Dash. **No change needed.**

### Step 8: Verify `dash_table.DataTable` compatibility

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard.py` (line 651)

`dash_table` was integrated into the main `dash` package in Dash 2.0 and is imported as `from dash import dash_table`. Dash 4 continues to ship `dash_table` as a submodule. **No change needed** to the import or usage.

### Step 9: Verify `dash.ALL` and `dash.MATCH` pattern matching

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard.py` (lines 514, 720-725)

Pattern-matching callbacks using `dash.ALL` (line 514) and `MATCH` (lines 720-725) are core Dash features. These are unchanged in Dash 4. **No change needed.**

### Step 10: Verify `clientside_callback` compatibility

The app uses `app.clientside_callback(...)` in three files:
- `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard.py` — 3 clientside callbacks (countdown, chevron, thesis toggle)
- `/Users/chris/Projects/shitpost-alpha/shitty_ui/callbacks/alerts.py` — 5 clientside callbacks (interval toggle, notification permission, browser notification, test alert, badge count/style)

Clientside callbacks use `window.dash_clientside.no_update` which is a stable API. Dash 4 adds `Patch` support for clientside callbacks but does not remove existing functionality. **No change needed.**

### Step 11: Verify `allow_duplicate=True` callback outputs

**Files**:
- `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard.py` line 513: `Output("url", "pathname", allow_duplicate=True)`
- `/Users/chris/Projects/shitpost-alpha/shitty_ui/callbacks/alerts.py` lines 601, 635, 743: `Output("alert-notification-store", "data", allow_duplicate=True)` and `Output("alert-history-store", "data", allow_duplicate=True)`

`allow_duplicate` was introduced in Dash 2.9 and remains supported in Dash 4. **No change needed.**

### Step 12: Create a migration verification script

**New file**: `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_dash4_migration.py`

Create a focused test file that verifies Dash 4 compatibility:

```python
"""
Dash 4.0 migration verification tests.

Ensures all Dash components used in the dashboard are compatible with
Dash 4.x and dash-bootstrap-components 2.x.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))


class TestDash4Version:
    """Verify Dash 4.x and dbc 2.x are installed."""

    def test_dash_version_is_4x(self):
        """Dash version must be 4.x after migration."""
        import dash
        major = int(dash.__version__.split(".")[0])
        assert major == 4, f"Expected Dash 4.x, got {dash.__version__}"

    def test_dbc_version_is_2x(self):
        """dash-bootstrap-components version must be 2.x after migration."""
        import dash_bootstrap_components as dbc
        major = int(dbc.__version__.split(".")[0])
        assert major == 2, f"Expected dbc 2.x, got {dbc.__version__}"


class TestDash4ComponentInstantiation:
    """Verify all DCC components used in the app instantiate without error."""

    def test_dcc_slider(self):
        from dash import dcc
        slider = dcc.Slider(id="test-slider", min=0.0, max=1.0, step=0.05, value=0.7,
                           marks={0.0: "0%", 0.5: "50%", 1.0: "100%"})
        assert slider.id == "test-slider"
        assert slider.step == 0.05

    def test_dcc_range_slider(self):
        from dash import dcc
        slider = dcc.RangeSlider(id="test-range", min=0, max=1, step=0.05, value=[0, 1],
                                marks={0: "0", 0.5: "0.5", 1: "1"})
        assert slider.id == "test-range"
        assert slider.step == 0.05

    def test_dcc_dropdown_single(self):
        from dash import dcc
        dd = dcc.Dropdown(id="test-dropdown", options=[{"label": "25", "value": 25}],
                         value=25, clearable=False)
        assert dd.id == "test-dropdown"

    def test_dcc_dropdown_multi(self):
        from dash import dcc
        dd = dcc.Dropdown(id="test-multi-dd", options=[], value=[], multi=True,
                         placeholder="All assets")
        assert dd.id == "test-multi-dd"

    def test_dcc_datepicker_range(self):
        from dash import dcc
        from datetime import datetime, timedelta
        dp = dcc.DatePickerRange(id="test-datepicker",
                                start_date=(datetime.now() - timedelta(days=90)).date(),
                                end_date=datetime.now().date(), display_format="YYYY-MM-DD")
        assert dp.id == "test-datepicker"

    def test_dcc_loading(self):
        from dash import dcc, html
        loading = dcc.Loading(id="test-loading", type="default", color="#85BB65",
                             children=html.Div(id="test-child"))
        assert loading.id == "test-loading"

    def test_dcc_store(self):
        from dash import dcc
        store = dcc.Store(id="test-store", storage_type="local", data={"key": "value"})
        assert store.id == "test-store"

    def test_dcc_interval(self):
        from dash import dcc
        interval = dcc.Interval(id="test-interval", interval=5000, n_intervals=0)
        assert interval.id == "test-interval"

    def test_dcc_location(self):
        from dash import dcc
        loc = dcc.Location(id="test-url", refresh=False)
        assert loc.id == "test-url"

    def test_dash_table(self):
        from dash import dash_table
        table = dash_table.DataTable(data=[{"col": "value"}],
                                    columns=[{"name": "col", "id": "col"}],
                                    page_size=15, sort_action="native")
        assert table.page_size == 15


class TestDash4DashBootstrap:
    """Verify dbc components used in the app work with dbc 2.x."""

    def test_dbc_card(self):
        import dash_bootstrap_components as dbc
        card = dbc.Card(id="test-card")
        assert card.id == "test-card"

    def test_dbc_button(self):
        import dash_bootstrap_components as dbc
        btn = dbc.Button("Test", id="test-btn", color="primary")
        assert btn.id == "test-btn"

    def test_dbc_offcanvas(self):
        import dash_bootstrap_components as dbc
        oc = dbc.Offcanvas(id="test-offcanvas", title="Test", placement="end", is_open=False)
        assert oc.id == "test-offcanvas"

    def test_dbc_switch(self):
        import dash_bootstrap_components as dbc
        sw = dbc.Switch(id="test-switch", value=False)
        assert sw.id == "test-switch"

    def test_dbc_collapse(self):
        import dash_bootstrap_components as dbc
        col = dbc.Collapse(id="test-collapse", is_open=False)
        assert col.id == "test-collapse"

    def test_dbc_toast(self):
        import dash_bootstrap_components as dbc
        toast = dbc.Toast(id="test-toast", header="Test", is_open=False, icon="success")
        assert toast.id == "test-toast"

    def test_dbc_radio_items(self):
        import dash_bootstrap_components as dbc
        radio = dbc.RadioItems(id="test-radio", options=[{"label": "A", "value": "a"}], value="a")
        assert radio.id == "test-radio"
```

### Step 13: Install, run tests, and visually verify

After making the changes, the implementer must:

1. Activate the venv and install updated dependencies:
   ```bash
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. Run the full test suite:
   ```bash
   source venv/bin/activate && pytest -v
   ```

3. Run the new migration tests:
   ```bash
   source venv/bin/activate && pytest shit_tests/shitty_ui/test_dash4_migration.py -v
   ```

4. Start the dashboard locally and perform manual visual verification:
   ```bash
   cd shitty_ui && ../venv/bin/python app.py
   ```

5. Open `http://localhost:8050` in Chrome and visually verify:
   - Home page loads with KPI cards, screener table, posts feed
   - Period selector buttons (7D/30D/90D/All) work correctly
   - Screener row click navigates to `/assets/<SYMBOL>`
   - Asset page loads with price chart, stat cards, timeline
   - Alert bell opens the Offcanvas panel
   - Confidence slider in alert config renders and slides correctly
   - Range slider in data table filters renders correctly
   - Date picker in data table filters opens and selects dates
   - Loading spinners show during data fetches
   - Collapse/expand works for data table and thesis sections
   - Mobile view (resize to 375px width) — verify no layout breakage

---

## Test Plan

### New Tests

**File**: `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_dash4_migration.py`
- `TestDash4Version` (2 tests) — verify installed Dash and dbc versions
- `TestDash4ComponentInstantiation` (10 tests) — verify all DCC components instantiate
- `TestDash4DashBootstrap` (7 tests) — verify all DBC components instantiate
- Total: **19 new tests**

### Existing Tests to Verify

All 49 existing tests in `shit_tests/shitty_ui/` must pass without modification. The upgrade is API-backward-compatible, so existing tests that create Dash component instances, build layouts, and test callback logic should all pass. If any tests target CSS class names or component DOM internals, they may need updates — but based on the existing test code (which tests component structure via `getattr(component, 'id')` and `getattr(component, 'children')` patterns), no existing tests should break.

### Manual Verification

Required because the primary breaking changes are visual:
1. Dashboard homepage — all sections render
2. Slider/RangeSlider — visual appearance, dragging behavior
3. Dropdown — opens, closes, multi-select works
4. DatePickerRange — opens calendar, date selection
5. dcc.Loading — spinner displays during data load
6. Mobile responsiveness at 375px, 480px, 768px breakpoints
7. Alert config Offcanvas — opens, form controls work
8. Asset detail page — chart, stats, timeline render

---

## Documentation Updates

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Changed
- **Dash 4.0 Migration** - Upgraded dashboard framework from Dash 2.x to Dash 4.0
  - Updated `dash` from `>=2.14.0` to `>=4.0.0,<5.0.0`
  - Updated `dash-bootstrap-components` from `>=1.5.0` to `>=2.0.0,<3.0.0`
  - DCC components (sliders, dropdowns, date pickers, loading) now use Dash 4 Radix-based redesign
  - All existing functionality preserved (API backward compatible)
```

---

## Stress Testing and Edge Cases

### Edge Case 1: `dbc` compatibility with Dash 4

`dash-bootstrap-components 2.0.4` declares `dash>=3.0.3` as its minimum. Dash 4.0 satisfies `>=3.0.3`. However, dbc was not explicitly tested against Dash 4. If dbc breaks:
- **Symptom**: Component rendering errors, missing Bootstrap classes, import errors.
- **Mitigation**: Pin to `dash>=3.0.3,<4.0.0` as a fallback (Dash 3.x is still a major upgrade from 2.x). File an issue on the dbc GitHub tracker.

### Edge Case 2: Custom CSS `._dash-loading` class

If Dash 4 renames or removes the `._dash-loading` CSS class:
- **Symptom**: Loading spinner loses centering.
- **Mitigation**: Remove the CSS rule. The centering is cosmetic and the spinner will still function.

### Edge Case 3: `dash_table.DataTable` CSS classes

If `.dash-spreadsheet-container` class changes in Dash 4:
- **Symptom**: Data table loses horizontal scroll on mobile.
- **Mitigation**: Inspect the new DOM, find the replacement class, update `custom.css` line 181.

### Edge Case 4: Railway deployment

Railway serves the app via `cd shitty_ui && python app.py`. Dash 4 should not affect this deployment pattern since `app.run(host="0.0.0.0", port=port)` is the standard Dash serve method.
- **Risk**: Dependency installation on Railway might fail if Dash 4 has new system-level dependencies.
- **Mitigation**: Railway builds from `requirements.txt`. Dash 4 has no new system dependencies. If build fails, check Railway build logs.

### Edge Case 5: Existing slider `marks` format

Both sliders use simple `marks` dicts with numeric keys and string values. Dash 4 supports this format unchanged, but verify the mark labels render in the correct positions.

---

## Verification Checklist

1. [ ] `requirements.txt` updated with Dash 4.0 and dbc 2.0 pins
2. [ ] `pip install -r requirements.txt` completes without errors
3. [ ] `pytest -v` — all existing tests pass (49 shitty_ui tests + others)
4. [ ] `pytest shit_tests/shitty_ui/test_dash4_migration.py -v` — all 19 new tests pass
5. [ ] `ruff check shitty_ui/` — no lint errors
6. [ ] Dashboard starts locally: `cd shitty_ui && python app.py`
7. [ ] Visual check: homepage loads, KPI cards display
8. [ ] Visual check: screener table renders with sparklines
9. [ ] Visual check: period selector buttons work
10. [ ] Visual check: alert config Offcanvas opens, confidence slider works
11. [ ] Visual check: data table collapse/expand works, filters render
12. [ ] Visual check: asset detail page loads with chart
13. [ ] Visual check: mobile layout at 375px width is not broken
14. [ ] Visual check: Loading spinners appear during refresh
15. [ ] CSS rule `._dash-loading` — verify it still targets the correct element
16. [ ] CSS rule `.dash-spreadsheet-container` — verify horizontal scroll on mobile
17. [ ] CHANGELOG.md updated
18. [ ] Deploy to Railway staging (if available) or production and verify

---

## What NOT To Do

1. **Do NOT change any callback logic.** This migration is about framework version and visual refresh only. Do not refactor callbacks, change component IDs, or modify data flows.

2. **Do NOT pin to `dash==4.0.0` (exact version).** Use `>=4.0.0,<5.0.0` to receive bugfix releases. Dash 4.1.0 is already in RC.

3. **Do NOT remove `suppress_callback_exceptions=True`** from the Dash app constructor (line 65 of `layout.py`). This is required for the multi-page routing pattern where callback targets are dynamically created.

4. **Do NOT upgrade Plotly independently.** `plotly>=5.15.0` is compatible with Dash 4. Upgrading Plotly to 6.x (if available) is a separate concern and should be a separate PR.

5. **Do NOT attempt to use new Dash 4 features** (like `dcc.Button`, folder upload, callback `api_endpoint`, or `hidden` parameter) in this PR. The scope is purely migration, not feature adoption.

6. **Do NOT change the `index_string` template.** The Jinja2-style template tags are stable across Dash versions.

7. **Do NOT remove the `custom.css` loading spinner rule** without first verifying whether the class still exists. It may still work in Dash 4.

8. **Do NOT assume dbc 2.0.4 works perfectly with Dash 4.** Test explicitly. If it breaks, the fallback is `dash>=3.0.3,<4.0.0` plus `dbc>=2.0.0`.

9. **Do NOT merge without manual visual verification.** Automated tests cannot catch visual regressions from the component redesign. A human must look at the dashboard in a browser.

10. **Do NOT skip mobile testing.** Dash 4's redesigned components may have different default dimensions that break the carefully tuned responsive CSS.

---

## Rollback Plan

If the migration causes issues after deployment:

1. **Revert `requirements.txt`** to the previous Dash/dbc pins:
   ```
   dash>=2.14.0
   dash-bootstrap-components>=1.5.0
   ```
2. **Reinstall**: `pip install -r requirements.txt`
3. **Redeploy** to Railway.

The test file `test_dash4_migration.py` will fail after rollback (version assertions), but all other tests should pass since no functional code was changed.
