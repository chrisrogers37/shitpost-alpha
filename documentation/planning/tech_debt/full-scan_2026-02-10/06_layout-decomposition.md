# Plan 06: Layout Decomposition

**Status**: ✅ COMPLETE
**Started**: 2026-02-10
**Completed**: 2026-02-10

**PR Title**: `refactor: decompose 5,066-line layout.py into page modules and callback groups`
**Risk Level**: High (restructuring the entire UI layer)
**Effort**: 2-3 days
**Findings Addressed**: #16

---

## Context

`shitty_ui/layout.py` is **5,066 lines** — a single file containing all page layouts, all 20+ callbacks, all component builders, color constants, and utility functions. This is a textbook god file that makes the dashboard nearly impossible to navigate or modify safely.

---

## Finding #16: God File Anti-Pattern

### Location

`shitty_ui/layout.py` (5,066 lines)

### Current Contents (Estimated Breakdown)

| Section | Approx Lines | Purpose |
|---------|-------------|---------|
| Constants & Colors | ~50 | `COLORS` dict, style constants |
| Component builders | ~400 | `create_metric_card()`, `create_signal_card()`, etc. |
| Dashboard page layout | ~500 | `create_dashboard_page()` |
| Asset page layout | ~400 | `create_asset_page()` |
| Alert panel layout | ~300 | `create_alert_config_panel()`, `create_alert_history_panel()` |
| Filter controls | ~150 | `create_filter_controls()`, `create_footer()` |
| App initialization | ~100 | `create_app()`, stores, intervals |
| Dashboard callbacks | ~800 | `update_dashboard()`, `update_predictions_table()`, etc. |
| Asset page callbacks | ~600 | `update_asset_page()`, `update_asset_price_chart()`, etc. |
| Alert callbacks | ~500 | Alert toggle, save, load, check callbacks |
| Clientside callbacks | ~200 | Countdown timer, browser notifications, badge count |
| Chart builders | ~400 | Chart creation within callbacks |
| Error handling | ~200 | `create_error_card()`, `create_empty_chart()` |
| Miscellaneous | ~366 | Remaining code |

### Target Structure

```
shitty_ui/
├── app.py                    # Entry point (unchanged, 25 lines)
├── constants.py              # NEW: Colors, styles, shared constants (~50 lines)
├── components/               # NEW: Reusable UI components
│   ├── __init__.py
│   ├── cards.py              # Metric cards, signal cards, error cards (~200 lines)
│   ├── charts.py             # Chart builder functions (~400 lines)
│   ├── controls.py           # Filter controls, buttons, selectors (~150 lines)
│   └── header.py             # Header, footer, navigation (~150 lines)
├── pages/                    # NEW: Page layouts
│   ├── __init__.py
│   ├── dashboard.py          # Dashboard page layout + callbacks (~1,300 lines)
│   └── assets.py             # Asset deep dive page layout + callbacks (~1,000 lines)
├── callbacks/                # NEW: Callback groups
│   ├── __init__.py
│   ├── alerts.py             # Alert panel callbacks (~500 lines)
│   └── clientside.py         # Clientside JS callbacks (~200 lines)
├── layout.py                 # REDUCED: App init, routing, store creation (~200 lines)
├── data.py                   # Database queries (unchanged)
├── alerts.py                 # Alert checking logic (unchanged)
└── telegram_bot.py           # Telegram bot (unchanged)
```

### Migration Strategy

**Phase A: Extract constants** (lowest risk)

```python
# shitty_ui/constants.py — NEW FILE
COLORS = {
    "primary": "#1e293b",
    "secondary": "#334155",
    "accent": "#3b82f6",
    "success": "#10b981",
    "danger": "#ef4444",
    "warning": "#f59e0b",
    "text": "#f1f5f9",
    "text_muted": "#94a3b8",
    "border": "#475569",
}

# Any other shared constants (refresh intervals, default limits, etc.)
```

Update `layout.py`:
```python
# Replace inline COLORS dict with:
from shitty_ui.constants import COLORS
```

**Phase B: Extract reusable components**

Move pure component-building functions (no callbacks, no state) into `components/`:

```python
# shitty_ui/components/cards.py
from shitty_ui.constants import COLORS

def create_metric_card(title, value, subtitle="", color=None, icon=None):
    """Create a single KPI metric card."""
    # ... existing implementation from layout.py ...

def create_signal_card(row):
    """Create a recent signal display card."""
    # ... existing implementation ...

def create_error_card(msg, details=None):
    """Create an error state display card."""
    # ... existing implementation ...

def create_empty_chart(msg):
    """Create an empty chart placeholder."""
    # ... existing implementation ...
```

```python
# shitty_ui/components/charts.py
from shitty_ui.constants import COLORS

def create_accuracy_by_confidence_chart(data):
    """Build the accuracy by confidence bar chart."""
    # ... extract from update_dashboard callback ...

def create_performance_by_asset_chart(data):
    """Build the performance by asset bar chart."""
    # ... extract from update_dashboard callback ...

def create_candlestick_chart(price_data, predictions=None):
    """Build a candlestick price chart with optional prediction overlays."""
    # ... extract from update_asset_price_chart callback ...
```

**Phase C: Extract page layouts**

```python
# shitty_ui/pages/dashboard.py
from shitty_ui.constants import COLORS
from shitty_ui.components.cards import create_metric_card, create_signal_card
from shitty_ui.components.controls import create_filter_controls

def create_dashboard_page():
    """Create the main dashboard page layout."""
    # ... move from layout.py ...

def register_dashboard_callbacks(app):
    """Register all dashboard-specific callbacks."""
    # Move these callbacks:
    # - update_period_selection
    # - update_dashboard
    # - handle_asset_chart_click
    # - update_asset_drilldown
    # - toggle_collapse
    # - update_predictions_table
```

```python
# shitty_ui/pages/assets.py
from shitty_ui.constants import COLORS
from shitty_ui.components.cards import create_metric_card
from shitty_ui.components.charts import create_candlestick_chart

def create_asset_page(symbol):
    """Create the asset deep dive page layout."""
    # ... move from layout.py ...

def register_asset_callbacks(app):
    """Register all asset page callbacks."""
    # Move these callbacks:
    # - update_asset_page
    # - update_asset_price_chart
    # - update_asset_range_buttons
```

**Phase D: Extract callback groups**

```python
# shitty_ui/callbacks/alerts.py
def register_alert_callbacks(app):
    """Register all alert-related callbacks."""
    # Move these callbacks:
    # - toggle_alert_config
    # - toggle_email_input
    # - toggle_sms_input
    # - toggle_quiet_hours
    # - update_confidence_display
    # - update_alert_status
    # - populate_alert_assets
    # - save_alert_preferences
    # - load_preferences_into_form
    # - run_alert_check
    # - render_alert_history
    # - clear_alert_history
```

```python
# shitty_ui/callbacks/clientside.py
def register_clientside_callbacks(app):
    """Register all clientside JavaScript callbacks."""
    # Move these callbacks:
    # - countdown timer
    # - browser notification
    # - test alert
    # - badge count
```

**Phase E: Slim down `layout.py`**

```python
# shitty_ui/layout.py — REDUCED to ~200 lines
import dash
import dash_bootstrap_components as dbc
from dash import html, dcc

from shitty_ui.constants import COLORS
from shitty_ui.pages.dashboard import create_dashboard_page, register_dashboard_callbacks
from shitty_ui.pages.assets import create_asset_page, register_asset_callbacks
from shitty_ui.callbacks.alerts import register_alert_callbacks
from shitty_ui.callbacks.clientside import register_clientside_callbacks


def create_app():
    """Initialize the Dash application."""
    app = dash.Dash(
        __name__,
        external_stylesheets=[dbc.themes.SLATE],
        suppress_callback_exceptions=True,
    )
    app.layout = _create_layout()
    return app


def _create_layout():
    """Create the root layout with routing and stores."""
    return html.Div([
        dcc.Location(id="url", refresh=False),
        # ... intervals and stores ...
        html.Div(id="page-content"),
    ])


def register_callbacks(app):
    """Register all callbacks."""
    _register_routing(app)
    register_dashboard_callbacks(app)
    register_asset_callbacks(app)
    register_alert_callbacks(app)
    register_clientside_callbacks(app)


def _register_routing(app):
    """Register the URL routing callback."""
    @app.callback(
        Output("page-content", "children"),
        Input("url", "pathname"),
    )
    def route_page(pathname):
        if pathname and pathname.startswith("/assets/"):
            symbol = pathname.split("/assets/")[-1]
            return create_asset_page(symbol)
        return create_dashboard_page()
```

---

## Step-by-Step Migration Order

| Step | Action | Files Changed | Risk |
|------|--------|---------------|------|
| 1 | Create `constants.py`, move `COLORS` | +1 new, edit `layout.py` | Very Low |
| 2 | Create `components/cards.py`, move card builders | +2 new, edit `layout.py` | Low |
| 3 | Create `components/charts.py`, move chart builders | +1 new, edit `layout.py` | Low |
| 4 | Create `components/controls.py` and `components/header.py` | +2 new, edit `layout.py` | Low |
| 5 | Create `pages/dashboard.py`, move layout + callbacks | +2 new, edit `layout.py` | Medium |
| 6 | Create `pages/assets.py`, move layout + callbacks | +1 new, edit `layout.py` | Medium |
| 7 | Create `callbacks/alerts.py`, move alert callbacks | +2 new, edit `layout.py` | Medium |
| 8 | Create `callbacks/clientside.py`, move JS callbacks | +1 new, edit `layout.py` | Low |
| 9 | Clean up `layout.py` to routing-only | edit `layout.py` | Low |

**Total new files**: ~12 (including `__init__.py` files)

Each step should be verified by running the dashboard and confirming it still works.

---

## Key Dash Patterns to Preserve

When extracting callbacks, remember:

1. **Callback registration** must receive the `app` object: `def register_*_callbacks(app)`
2. **Clientside callbacks** use `app.clientside_callback()` not decorators
3. **Shared stores** (like `selected-asset-store`) are referenced by ID across pages — make sure IDs stay consistent
4. **Circular imports** — components should NOT import from callbacks or pages; only the other way around

---

## Verification Checklist

- [ ] `wc -l shitty_ui/layout.py` returns < 300 lines
- [ ] `python shitty_ui/app.py` starts without errors
- [ ] Dashboard page loads at `/` with all sections
- [ ] Asset page loads at `/assets/AAPL` with all sections
- [ ] Alert bell opens the configuration panel
- [ ] Time period selector works (7D/30D/90D/All)
- [ ] Refresh countdown timer works
- [ ] Data table toggle works
- [ ] `pytest shit_tests/shitty_ui/ -v` — all existing tests pass
- [ ] `ruff check shitty_ui/` — no linting errors

---

## What NOT To Do

1. **Do NOT change any component's visual appearance** in this PR. This is a structural refactor only.
2. **Do NOT rename callback IDs.** The Dash callback system uses string IDs, and renaming them breaks the app.
3. **Do NOT add new features** while decomposing. If you find a bug during the refactor, document it and fix it in a separate PR.
4. **Do NOT try to do all steps in one commit.** Make a commit after each step so you can revert cleanly if something breaks.
5. **Do NOT move `data.py` or `alerts.py`.** Those files are already well-scoped. Only `layout.py` needs decomposition.
6. **Do NOT convert inline styles to CSS files** in this PR. That's a separate enhancement.
