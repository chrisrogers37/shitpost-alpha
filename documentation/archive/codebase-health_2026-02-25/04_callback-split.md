# Phase 04 -- Split Monolithic Dashboard Callbacks

## Header

| Field | Value |
|---|---|
| **PR Title** | refactor: split monolithic callback registration into focused modules |
| **Risk** | Medium -- Dash callback registration is sensitive to import order and `app` reference threading |
| **Effort** | High (~8 hours) |
| **Files Created** | 5 |
| **Files Modified** | 3 |
| **Files Deleted** | 0 |

## Context

Two callback registration functions dominate the codebase in terms of size and complexity:

- `register_alert_callbacks()` in `/Users/chris/Projects/shitpost-alpha/shitty_ui/callbacks/alerts.py` (lines 322-801, 479 LOC) bundles 17 nested callbacks spanning preference management, history rendering, and browser notification logic.
- `register_dashboard_callbacks()` in `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard.py` (lines 267-726, 460 LOC) bundles 7 main callbacks spanning period selection, KPI rendering, screener management, and data table filtering.

Both functions are impossible to test in isolation, difficult to navigate, and create merge conflicts when multiple developers touch the same file. This phase extracts each into focused sub-modules following the pattern already established by `alert_components.py` (which successfully extracted UI builders into testable functions).

This is **purely structural** -- no callback behavior changes.

## Dependencies

| Relationship | Phase | Description |
|---|---|---|
| **Depends on** | None | No prerequisites |
| **Blocks** | Phase 05 | Tests for the newly extracted modules |
| **Blocks** | Phase 08 | Dash 4 migration (smaller modules are easier to migrate) |

---

## Detailed Implementation Plan

### Part A: Split `register_alert_callbacks()` (alerts.py)

#### Step A1: Create the AlertPreferences Pydantic model

**New file:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/callbacks/alert_models.py`

This replaces the two paired functions `build_preferences_dict()` (lines 134-185) and `extract_preferences_tuple()` (lines 188-216) with a type-safe Pydantic model.

```python
"""Pydantic model for alert preferences.

Replaces the paired build_preferences_dict() / extract_preferences_tuple()
functions with a single type-safe model that handles serialization
in both directions.
"""

from pydantic import BaseModel, Field


class AlertPreferences(BaseModel):
    """Alert preferences as stored in localStorage.

    This is the canonical shape of the preferences object.
    Use from_form_fields() to build from Dash form values,
    and to_form_tuple() to extract back to the 12-element
    tuple expected by load_preferences_into_form().
    """

    enabled: bool = False
    min_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    assets_of_interest: list[str] = Field(default_factory=list)
    sentiment_filter: str = "all"
    browser_notifications: bool = True
    email_enabled: bool = False
    email_address: str = ""
    sms_enabled: bool = False
    sms_phone_number: str = ""
    quiet_hours_enabled: bool = False
    quiet_hours_start: str = "22:00"
    quiet_hours_end: str = "08:00"
    max_alerts_per_hour: int = 10

    @classmethod
    def from_form_fields(
        cls,
        enabled: bool,
        min_confidence: float,
        assets: list,
        sentiment: str,
        browser_on: bool,
        email_on: bool,
        email_addr: str,
        sms_on: bool,
        sms_phone: str,
        quiet_on: bool,
        quiet_start: str,
        quiet_end: str,
    ) -> "AlertPreferences":
        """Build from individual Dash form field values.

        Applies safe defaults for None values, matching the
        original build_preferences_dict() behavior exactly.
        """
        return cls(
            enabled=bool(enabled),
            min_confidence=float(min_confidence or 0.7),
            assets_of_interest=assets or [],
            sentiment_filter=sentiment or "all",
            browser_notifications=bool(browser_on),
            email_enabled=bool(email_on),
            email_address=email_addr or "",
            sms_enabled=bool(sms_on),
            sms_phone_number=sms_phone or "",
            quiet_hours_enabled=bool(quiet_on),
            quiet_hours_start=quiet_start or "22:00",
            quiet_hours_end=quiet_end or "08:00",
        )

    def to_form_tuple(self) -> tuple:
        """Extract to the 12-element tuple matching Output order
        of load_preferences_into_form().

        Returns:
            Tuple of (enabled, min_confidence, assets, sentiment,
            browser_on, email_on, email_addr, sms_on, sms_phone,
            quiet_on, quiet_start, quiet_end).
        """
        return (
            self.enabled,
            self.min_confidence,
            self.assets_of_interest,
            self.sentiment_filter,
            self.browser_notifications,
            self.email_enabled,
            self.email_address,
            self.sms_enabled,
            self.sms_phone_number,
            self.quiet_hours_enabled,
            self.quiet_hours_start,
            self.quiet_hours_end,
        )

    def to_dict(self) -> dict:
        """Serialize to the dict shape expected by localStorage.

        Equivalent to the original build_preferences_dict() output.
        """
        return self.model_dump()

    @classmethod
    def from_stored(cls, prefs: dict) -> "AlertPreferences":
        """Construct from a localStorage dict, filling defaults for missing keys.

        Equivalent to the original extract_preferences_tuple() input handling.
        """
        return cls(**{k: v for k, v in (prefs or {}).items() if k in cls.model_fields})
```

#### Step A2: Create `alert_preferences.py` -- preference management callbacks

**New file:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/callbacks/alert_preferences.py`

This extracts 7 callbacks that deal with preference form fields.

```python
"""Preference management callbacks for the alert system.

Handles:
- Opening/closing the alert config panel
- Showing/hiding conditional inputs (email, SMS, quiet hours)
- Confidence threshold display
- Saving preferences to localStorage
- Loading preferences from localStorage into form
"""

from dash import Dash, Input, Output, State, no_update

from callbacks.alert_models import AlertPreferences
from data import get_available_assets


def register_alert_preference_callbacks(app: Dash) -> None:
    """Register all preference-management alert callbacks.

    Args:
        app: The Dash application instance.
    """

    @app.callback(
        Output("alert-config-offcanvas", "is_open"),
        [Input("open-alert-config-button", "n_clicks")],
        [State("alert-config-offcanvas", "is_open")],
        prevent_initial_call=True,
    )
    def toggle_alert_config(n_clicks: int, is_open: bool) -> bool:
        """Toggle the alert configuration panel open/closed."""
        if n_clicks:
            return not is_open
        return is_open

    @app.callback(
        Output("email-input-collapse", "is_open"),
        [Input("alert-email-toggle", "value")],
    )
    def toggle_email_input(email_enabled: bool) -> bool:
        """Show email input when email alerts are enabled."""
        return bool(email_enabled)

    @app.callback(
        Output("sms-input-collapse", "is_open"),
        [Input("alert-sms-toggle", "value")],
    )
    def toggle_sms_input(sms_enabled: bool) -> bool:
        """Show SMS input when SMS alerts are enabled."""
        return bool(sms_enabled)

    @app.callback(
        Output("quiet-hours-collapse", "is_open"),
        [Input("alert-quiet-hours-toggle", "value")],
    )
    def toggle_quiet_hours(quiet_enabled: bool) -> bool:
        """Show quiet hours time inputs when quiet hours are enabled."""
        return bool(quiet_enabled)

    @app.callback(
        Output("confidence-threshold-display", "children"),
        [Input("alert-confidence-slider", "value")],
    )
    def update_confidence_display(value: float) -> str:
        """Display the confidence slider value as a percentage."""
        return f"{int(value * 100)}%"

    @app.callback(
        Output("alert-assets-dropdown", "options"),
        [Input("alert-config-offcanvas", "is_open")],
    )
    def populate_alert_assets(is_open: bool):
        """Populate the assets dropdown when the panel opens."""
        if not is_open:
            return no_update
        available_assets = get_available_assets()
        return [{"label": asset, "value": asset} for asset in available_assets]

    @app.callback(
        [
            Output("alert-preferences-store", "data"),
            Output("alert-save-toast", "is_open"),
        ],
        [Input("save-alert-prefs-button", "n_clicks")],
        [
            State("alert-master-toggle", "value"),
            State("alert-confidence-slider", "value"),
            State("alert-assets-dropdown", "value"),
            State("alert-sentiment-radio", "value"),
            State("alert-browser-toggle", "value"),
            State("alert-email-toggle", "value"),
            State("alert-email-input", "value"),
            State("alert-sms-toggle", "value"),
            State("alert-sms-input", "value"),
            State("alert-quiet-hours-toggle", "value"),
            State("quiet-hours-start", "value"),
            State("quiet-hours-end", "value"),
        ],
        prevent_initial_call=True,
    )
    def save_alert_preferences(
        n_clicks: int,
        enabled: bool,
        min_confidence: float,
        assets: list,
        sentiment: str,
        browser_on: bool,
        email_on: bool,
        email_addr: str,
        sms_on: bool,
        sms_phone: str,
        quiet_on: bool,
        quiet_start: str,
        quiet_end: str,
    ):
        """Gather all form values and write them to the localStorage-backed store."""
        preferences = AlertPreferences.from_form_fields(
            enabled, min_confidence, assets, sentiment,
            browser_on, email_on, email_addr,
            sms_on, sms_phone,
            quiet_on, quiet_start, quiet_end,
        )
        return preferences.to_dict(), True

    @app.callback(
        [
            Output("alert-master-toggle", "value"),
            Output("alert-confidence-slider", "value"),
            Output("alert-assets-dropdown", "value"),
            Output("alert-sentiment-radio", "value"),
            Output("alert-browser-toggle", "value"),
            Output("alert-email-toggle", "value"),
            Output("alert-email-input", "value"),
            Output("alert-sms-toggle", "value"),
            Output("alert-sms-input", "value"),
            Output("alert-quiet-hours-toggle", "value"),
            Output("quiet-hours-start", "value"),
            Output("quiet-hours-end", "value"),
        ],
        [Input("alert-config-offcanvas", "is_open")],
        [State("alert-preferences-store", "data")],
    )
    def load_preferences_into_form(is_open: bool, prefs: dict):
        """When the offcanvas opens, populate form fields from stored preferences."""
        if not is_open or not prefs:
            return (no_update,) * 12
        return AlertPreferences.from_stored(prefs).to_form_tuple()
```

#### Step A3: Create `alert_history.py` -- history rendering callbacks

**New file:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/callbacks/alert_history.py`

This extracts 4 callbacks for alert history management plus the `run_alert_check` main loop.

```python
"""Alert history and periodic check callbacks.

Handles:
- Toggling alert history collapse
- Rendering alert history cards
- Clearing alert history
- The main periodic alert check (run_alert_check)
"""

from datetime import datetime

from dash import Dash, html, Input, Output, State, no_update

from constants import COLORS
from alerts import (
    check_for_new_alerts,
    is_in_quiet_hours,
    dispatch_server_notifications,
)
from callbacks.alerts import build_alert_history_card


def register_alert_history_callbacks(app: Dash) -> None:
    """Register all alert-history-related callbacks.

    Args:
        app: The Dash application instance.
    """

    @app.callback(
        [
            Output("alert-notification-store", "data"),
            Output("alert-history-store", "data"),
            Output("last-alert-check-store", "data"),
        ],
        [Input("alert-check-interval", "n_intervals")],
        [
            State("alert-preferences-store", "data"),
            State("last-alert-check-store", "data"),
            State("alert-history-store", "data"),
        ],
        prevent_initial_call=True,
    )
    def run_alert_check(
        n_intervals: int,
        preferences: dict,
        last_check: str,
        alert_history: list,
    ):
        """Periodically check for new predictions that match alert preferences."""
        if not preferences or not preferences.get("enabled", False):
            return no_update, no_update, no_update

        if is_in_quiet_hours(preferences):
            return None, alert_history, datetime.utcnow().isoformat()

        result = check_for_new_alerts(preferences, last_check)
        matched_alerts = result["matched_alerts"]
        new_last_check = result["last_check"]

        if not matched_alerts:
            return None, alert_history, new_last_check

        updated_history = (alert_history or []) + matched_alerts
        updated_history = updated_history[-100:]

        for alert in matched_alerts:
            dispatch_server_notifications(alert, preferences)

        notification_data = matched_alerts[0] if matched_alerts else None
        return notification_data, updated_history, new_last_check

    @app.callback(
        Output("collapse-alert-history", "is_open"),
        [Input("collapse-alert-history-button", "n_clicks")],
        [State("collapse-alert-history", "is_open")],
        prevent_initial_call=True,
    )
    def toggle_alert_history(n_clicks: int, is_open: bool) -> bool:
        """Toggle the alert history panel open/closed."""
        if n_clicks:
            return not is_open
        return is_open

    @app.callback(
        [
            Output("alert-history-content", "children"),
            Output("alert-history-count-badge", "children"),
        ],
        [
            Input("collapse-alert-history", "is_open"),
            Input("alert-history-store", "data"),
        ],
    )
    def render_alert_history(is_open: bool, history: list):
        """Render the alert history list from localStorage data."""
        if not history:
            return (
                html.P(
                    "No alerts triggered yet. Enable alerts and set your preferences.",
                    style={
                        "color": COLORS["text_muted"],
                        "textAlign": "center",
                        "padding": "20px",
                    },
                ),
                "0",
            )

        count = len(history)
        alert_cards = [
            build_alert_history_card(alert) for alert in reversed(history[-50:])
        ]
        return alert_cards, str(count)

    @app.callback(
        Output("alert-history-store", "data", allow_duplicate=True),
        [Input("clear-alert-history-button", "n_clicks")],
        prevent_initial_call=True,
    )
    def clear_alert_history(n_clicks: int) -> list:
        """Clear all alert history from localStorage."""
        if n_clicks:
            return []
        return no_update
```

#### Step A4: Create `alert_notifications.py` -- browser notification callbacks

**New file:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/callbacks/alert_notifications.py`

This extracts the alert status indicator callback plus all 5 clientside callbacks.

```python
"""Browser notification and status callbacks for the alert system.

Handles:
- Alert status indicator (active/disabled)
- Interval enable/disable based on master toggle
- Browser notification permission request
- Firing browser notifications
- Test alert
- Bell icon badge updates
"""

from dash import Dash, html, Input, Output

from constants import COLORS


def register_alert_notification_callbacks(app: Dash) -> None:
    """Register all notification and status indicator callbacks.

    Args:
        app: The Dash application instance.
    """

    @app.callback(
        Output("alert-status-indicator", "children"),
        [Input("alert-master-toggle", "value")],
    )
    def update_alert_status(enabled: bool):
        """Update the status indicator when alerts are toggled."""
        if enabled:
            return [
                html.I(
                    className="fas fa-circle me-2",
                    style={"color": COLORS["success"], "fontSize": "0.6rem"},
                ),
                html.Span(
                    "Alerts active - checking every 2 minutes",
                    style={"color": COLORS["success"], "fontSize": "0.85rem"},
                ),
            ]
        return [
            html.I(
                className="fas fa-circle me-2",
                style={"color": COLORS["danger"], "fontSize": "0.6rem"},
            ),
            html.Span(
                "Alerts disabled",
                style={"color": COLORS["text_muted"], "fontSize": "0.85rem"},
            ),
        ]

    # --- Enable/disable alert check interval based on master toggle ---
    app.clientside_callback(
        """
        function(prefs) {
            if (prefs && prefs.enabled) {
                return false;  // disabled=false means interval IS running
            }
            return true;  // disabled=true means interval is NOT running
        }
        """,
        Output("alert-check-interval", "disabled"),
        Input("alert-preferences-store", "data"),
    )

    # --- Request browser notification permission ---
    app.clientside_callback(
        """
        function(browserToggle) {
            if (!browserToggle) {
                return "Browser notifications disabled.";
            }

            if (!("Notification" in window)) {
                return "Browser does not support notifications.";
            }

            if (Notification.permission === "granted") {
                return "Permission granted. Notifications active.";
            }

            if (Notification.permission === "denied") {
                return "Permission denied. Enable in browser settings.";
            }

            // Permission is "default" - request it
            Notification.requestPermission().then(function(permission) {
                console.log("Notification permission:", permission);
            });

            return "Requesting permission...";
        }
        """,
        Output("browser-notification-status", "children"),
        Input("alert-browser-toggle", "value"),
    )

    # --- Show browser notification when alert fires ---
    app.clientside_callback(
        """
        function(notificationData) {
            if (!notificationData) {
                return window.dash_clientside.no_update;
            }

            // Check if browser notifications are supported and permitted
            if (!("Notification" in window)) {
                console.warn("Browser does not support notifications");
                return window.dash_clientside.no_update;
            }

            if (Notification.permission !== "granted") {
                console.warn("Notification permission not granted:", Notification.permission);
                return window.dash_clientside.no_update;
            }

            // Build notification content
            var sentiment = (notificationData.sentiment || "neutral").toUpperCase();
            var confidence = notificationData.confidence
                ? (notificationData.confidence * 100).toFixed(0) + "%"
                : "N/A";
            var assets = Array.isArray(notificationData.assets)
                ? notificationData.assets.slice(0, 3).join(", ")
                : "Unknown";
            var text = notificationData.text || "";
            var body = sentiment + " (" + confidence + " confidence)\\n"
                     + "Assets: " + assets + "\\n"
                     + text.substring(0, 100) + "...";

            // Create the notification
            try {
                var notification = new Notification("Shitpost Alpha Alert", {
                    body: body,
                    icon: "/assets/favicon.ico",
                    badge: "/assets/favicon.ico",
                    tag: "shitpost-alert-" + (notificationData.prediction_id || Date.now()),
                    requireInteraction: false,
                    silent: false,
                });

                // Close after 10 seconds
                setTimeout(function() {
                    notification.close();
                }, 10000);

                // Focus dashboard on click
                notification.onclick = function(event) {
                    event.preventDefault();
                    window.focus();
                    notification.close();
                };

                console.log("Notification sent:", notificationData.prediction_id);
            } catch (err) {
                console.error("Failed to create notification:", err);
            }

            return window.dash_clientside.no_update;
        }
        """,
        Output("alert-notification-store", "data", allow_duplicate=True),
        Input("alert-notification-store", "data"),
        prevent_initial_call=True,
    )

    # --- Send test alert ---
    app.clientside_callback(
        """
        function(n_clicks) {
            if (!n_clicks) {
                return window.dash_clientside.no_update;
            }

            if (!("Notification" in window)) {
                alert("Browser does not support notifications.");
                return window.dash_clientside.no_update;
            }

            if (Notification.permission !== "granted") {
                Notification.requestPermission();
                return window.dash_clientside.no_update;
            }

            var notification = new Notification("Shitpost Alpha - Test Alert", {
                body: "BULLISH (85% confidence)\\nAssets: AAPL, TSLA\\nThis is a test notification. Your alerts are working!",
                icon: "/assets/favicon.ico",
                tag: "shitpost-test-alert",
            });

            setTimeout(function() { notification.close(); }, 8000);

            return window.dash_clientside.no_update;
        }
        """,
        Output("alert-notification-store", "data", allow_duplicate=True),
        Input("test-alert-button", "n_clicks"),
        prevent_initial_call=True,
    )

    # --- Update bell icon badge count ---
    app.clientside_callback(
        """
        function(history) {
            if (!history || history.length === 0) {
                return {"display": "none"};
            }
            // Show count of alerts in last 24 hours
            var now = new Date();
            var oneDayAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);
            var recentCount = 0;
            for (var i = 0; i < history.length; i++) {
                var alertTime = new Date(history[i].alert_triggered_at);
                if (alertTime > oneDayAgo) {
                    recentCount++;
                }
            }
            if (recentCount === 0) {
                return {"display": "none"};
            }
            return {"display": "inline", "fontSize": "0.6rem"};
        }
        """,
        Output("alert-badge", "style"),
        Input("alert-history-store", "data"),
    )

    app.clientside_callback(
        """
        function(history) {
            if (!history || history.length === 0) {
                return "";
            }
            var now = new Date();
            var oneDayAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);
            var recentCount = 0;
            for (var i = 0; i < history.length; i++) {
                var alertTime = new Date(history[i].alert_triggered_at);
                if (alertTime > oneDayAgo) {
                    recentCount++;
                }
            }
            return recentCount > 0 ? String(recentCount) : "";
        }
        """,
        Output("alert-badge", "children"),
        Input("alert-history-store", "data"),
    )
```

#### Step A5: Refactor `alerts.py` into thin orchestrator with backward-compatible re-exports

**Modified file:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/callbacks/alerts.py`

**BEFORE** (lines 1-801 -- full current file):
The file contains `create_alert_config_panel()`, `create_alert_history_panel()`, `build_preferences_dict()`, `extract_preferences_tuple()`, `build_alert_history_card()`, and the 479-LOC `register_alert_callbacks()`.

**AFTER:**
The file retains `create_alert_config_panel()`, `create_alert_history_panel()`, and `build_alert_history_card()` (which are layout/rendering functions, not callbacks). The helper functions `build_preferences_dict()` and `extract_preferences_tuple()` become thin wrappers around `AlertPreferences` for backward compatibility. The registration function becomes a thin orchestrator.

```python
"""Alert system callbacks and alert panel components."""

from datetime import datetime

from dash import Dash, html, dcc, Input, Output, State, no_update
import dash_bootstrap_components as dbc

from constants import COLORS
from data import get_available_assets
from alerts import (
    check_for_new_alerts,
    is_in_quiet_hours,
    dispatch_server_notifications,
)
from callbacks.alert_components import (
    build_master_toggle_section,
    build_status_indicator,
    build_confidence_threshold_section,
    build_asset_selection_section,
    build_sentiment_filter_section,
    build_notification_channels_section,
    build_quiet_hours_section,
    build_action_buttons_section,
)
from callbacks.alert_models import AlertPreferences


def create_alert_config_panel():
    """
    Create the alert configuration slide-out panel.

    Returns a dbc.Offcanvas component that slides in from the right
    when the user clicks the bell icon in the header. Each section
    is built by a dedicated function in alert_components.py.
    """
    # ... (unchanged -- lines 35-89 of current file, keep verbatim)
    notification_channels = build_notification_channels_section()
    action_buttons = build_action_buttons_section()

    return dbc.Offcanvas(
        id="alert-config-offcanvas",
        title="Alert Configuration",
        placement="end",
        is_open=False,
        backdrop=True,
        scrollable=True,
        style={
            "backgroundColor": COLORS["primary"],
            "color": COLORS["text"],
            "width": "400px",
        },
        children=[
            build_master_toggle_section(),
            build_status_indicator(),
            html.Hr(style={"borderColor": COLORS["border"]}),
            html.H6(
                [
                    html.I(className="fas fa-filter me-2"),
                    "Filter Settings",
                ],
                style={"color": COLORS["accent"], "marginBottom": "15px"},
            ),
            build_confidence_threshold_section(),
            build_asset_selection_section(),
            build_sentiment_filter_section(),
            html.Hr(style={"borderColor": COLORS["border"]}),
            html.H6(
                [
                    html.I(className="fas fa-paper-plane me-2"),
                    "Notification Channels",
                ],
                style={"color": COLORS["accent"], "marginBottom": "15px"},
            ),
            *notification_channels,
            html.Hr(style={"borderColor": COLORS["border"]}),
            html.H6(
                [
                    html.I(className="fas fa-moon me-2"),
                    "Quiet Hours",
                ],
                style={"color": COLORS["accent"], "marginBottom": "15px"},
            ),
            build_quiet_hours_section(),
            html.Hr(style={"borderColor": COLORS["border"]}),
            *action_buttons,
        ],
    )


def create_alert_history_panel():
    """
    Create the alert history card for the main dashboard.
    """
    # ... (unchanged -- lines 92-131 of current file, keep verbatim)
    return dbc.Card(
        [
            dbc.CardHeader(
                [
                    dbc.Button(
                        [
                            html.I(className="fas fa-history me-2"),
                            "Alert History",
                            html.Span(
                                id="alert-history-count-badge",
                                className="badge bg-primary ms-2",
                                children="0",
                            ),
                        ],
                        id="collapse-alert-history-button",
                        color="link",
                        className="text-white fw-bold p-0",
                    ),
                ],
                className="fw-bold",
            ),
            dbc.Collapse(
                dbc.CardBody(
                    id="alert-history-content",
                    style={"maxHeight": "400px", "overflowY": "auto"},
                ),
                id="collapse-alert-history",
                is_open=False,
            ),
        ],
        className="mt-4",
        style={"backgroundColor": COLORS["secondary"]},
    )


# --- Backward-compatible wrappers ---
# These delegate to AlertPreferences but preserve the old function signatures
# so that existing tests and imports continue to work without changes.

def build_preferences_dict(
    enabled: bool,
    min_confidence: float,
    assets: list,
    sentiment: str,
    browser_on: bool,
    email_on: bool,
    email_addr: str,
    sms_on: bool,
    sms_phone: str,
    quiet_on: bool,
    quiet_start: str,
    quiet_end: str,
) -> dict:
    """Assemble a preferences dict from individual form field values.

    Delegates to AlertPreferences.from_form_fields().to_dict().
    Kept for backward compatibility with existing tests.
    """
    return AlertPreferences.from_form_fields(
        enabled, min_confidence, assets, sentiment,
        browser_on, email_on, email_addr,
        sms_on, sms_phone,
        quiet_on, quiet_start, quiet_end,
    ).to_dict()


def extract_preferences_tuple(prefs: dict) -> tuple:
    """Extract form field values from a preferences dict.

    Delegates to AlertPreferences.from_stored().to_form_tuple().
    Kept for backward compatibility with existing tests.
    """
    return AlertPreferences.from_stored(prefs).to_form_tuple()


def build_alert_history_card(alert: dict) -> html.Div:
    """Build a single alert history card from an alert dict.

    Handles sentiment coloring, timestamp formatting, text truncation,
    and asset display.
    """
    # ... (unchanged -- lines 219-319 of current file, keep verbatim)
    sentiment = alert.get("sentiment", "neutral")
    confidence = alert.get("confidence", 0)
    assets = alert.get("assets", [])
    text = alert.get("text", "")[:120]
    triggered_at = alert.get("alert_triggered_at", "")

    if sentiment == "bullish":
        sentiment_color = COLORS["success"]
        sentiment_icon = "arrow-up"
    elif sentiment == "bearish":
        sentiment_color = COLORS["danger"]
        sentiment_icon = "arrow-down"
    else:
        sentiment_color = COLORS["text_muted"]
        sentiment_icon = "minus"

    try:
        ts = datetime.fromisoformat(triggered_at.replace("Z", "+00:00"))
        time_str = ts.strftime("%b %d, %H:%M")
    except (ValueError, TypeError, AttributeError):
        time_str = str(triggered_at)[:16]

    asset_str = (
        ", ".join(assets[:3]) if isinstance(assets, list) else str(assets)
    )

    return html.Div(
        [
            html.Div(
                [
                    html.Span(
                        time_str,
                        style={
                            "color": COLORS["text_muted"],
                            "fontSize": "0.75rem",
                        },
                    ),
                    html.Span(
                        [
                            html.I(className=f"fas fa-{sentiment_icon} me-1"),
                            sentiment.upper(),
                        ],
                        style={
                            "color": sentiment_color,
                            "fontSize": "0.75rem",
                            "fontWeight": "bold",
                        },
                        className="ms-2",
                    ),
                    html.Span(
                        f" | {confidence:.0%}" if confidence else "",
                        style={
                            "color": COLORS["text_muted"],
                            "fontSize": "0.75rem",
                        },
                    ),
                ],
                className="d-flex align-items-center mb-1",
            ),
            html.P(
                text + "..." if len(text) >= 120 else text,
                style={
                    "fontSize": "0.8rem",
                    "margin": "3px 0",
                    "lineHeight": "1.3",
                    "color": COLORS["text"],
                },
            ),
            html.Div(
                [
                    html.Span(
                        f"Assets: {asset_str}",
                        style={
                            "color": COLORS["text_muted"],
                            "fontSize": "0.75rem",
                        },
                    ),
                ]
            ),
        ],
        style={
            "padding": "10px",
            "borderBottom": f"1px solid {COLORS['border']}",
        },
    )


def register_alert_callbacks(app: Dash):
    """Register all alert-related callbacks.

    Delegates to focused sub-modules. This function is the single
    entry point called by layout.register_callbacks().
    """
    from callbacks.alert_preferences import register_alert_preference_callbacks
    from callbacks.alert_history import register_alert_history_callbacks
    from callbacks.alert_notifications import register_alert_notification_callbacks

    register_alert_preference_callbacks(app)
    register_alert_history_callbacks(app)
    register_alert_notification_callbacks(app)
```

**Key change summary for `alerts.py`:**
- Lines 134-216 (build_preferences_dict, extract_preferences_tuple): replaced with thin wrappers delegating to `AlertPreferences`
- Lines 219-319 (build_alert_history_card): **unchanged** -- stays in this file
- Lines 322-801 (register_alert_callbacks): replaced with 3-line orchestrator calling sub-modules
- Lines 27-131 (create_alert_config_panel, create_alert_history_panel): **unchanged**

---

### Part B: Split `register_dashboard_callbacks()` (dashboard.py)

#### Step B1: Create `dashboard_callbacks/` subpackage

**New file:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard_callbacks/__init__.py`

```python
"""Dashboard callback sub-modules.

Each module registers a focused group of callbacks:
- period: Time period selection and countdown
- content: Main dashboard content (KPIs, screener, insights, post feed)
- table: Data table management (collapse, filtering, row clicks, thesis expand)
"""

from pages.dashboard_callbacks.period import register_period_callbacks
from pages.dashboard_callbacks.content import register_content_callbacks
from pages.dashboard_callbacks.table import register_table_callbacks

__all__ = [
    "register_period_callbacks",
    "register_content_callbacks",
    "register_table_callbacks",
]
```

#### Step B2: Create `period.py` -- period selection callbacks

**New file:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard_callbacks/period.py`

```python
"""Time period selection and refresh countdown callbacks."""

from dash import Dash, Input, Output, State, callback_context

from components.controls import get_period_button_styles


def register_period_callbacks(app: Dash) -> None:
    """Register period selection and countdown callbacks.

    Args:
        app: The Dash application instance.
    """

    @app.callback(
        [
            Output("selected-period", "data"),
            Output("period-7d", "color"),
            Output("period-7d", "outline"),
            Output("period-30d", "color"),
            Output("period-30d", "outline"),
            Output("period-90d", "color"),
            Output("period-90d", "outline"),
            Output("period-all", "color"),
            Output("period-all", "outline"),
        ],
        [
            Input("period-7d", "n_clicks"),
            Input("period-30d", "n_clicks"),
            Input("period-90d", "n_clicks"),
            Input("period-all", "n_clicks"),
        ],
        prevent_initial_call=True,
    )
    def update_period_selection(n7, n30, n90, nall):
        """Update selected time period based on button clicks."""
        ctx = callback_context
        if not ctx.triggered:
            return "90d", *get_period_button_styles("90d")

        button_id = ctx.triggered[0]["prop_id"].split(".")[0]
        period_map = {
            "period-7d": "7d",
            "period-30d": "30d",
            "period-90d": "90d",
            "period-all": "all",
        }
        selected = period_map.get(button_id, "90d")
        return selected, *get_period_button_styles(selected)

    # Refresh countdown clientside callback
    app.clientside_callback(
        """
        function(n, lastUpdate) {
            if (!lastUpdate) return ["--:--", "5:00"];

            const last = new Date(lastUpdate);
            const now = new Date();
            const nextRefresh = new Date(last.getTime() + 5 * 60 * 1000);
            const remaining = Math.max(0, (nextRefresh - now) / 1000);

            const mins = Math.floor(remaining / 60);
            const secs = Math.floor(remaining % 60);
            const countdown = `${mins}:${secs.toString().padStart(2, '0')}`;

            const timeStr = last.toLocaleTimeString();

            return [timeStr, countdown];
        }
        """,
        [
            Output("last-update-time", "children"),
            Output("next-update-countdown", "children"),
        ],
        [Input("countdown-interval", "n_intervals")],
        [State("last-update-timestamp", "data")],
    )
```

#### Step B3: Create `content.py` -- main dashboard content callbacks

**New file:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard_callbacks/content.py`

```python
"""Main dashboard content rendering callbacks.

Handles the primary dashboard update (insights, screener, KPIs)
and the post feed update.
"""

import traceback
from datetime import datetime

from dash import Dash, html, Input, Output
import dash_bootstrap_components as dbc

from constants import COLORS
from components.cards import (
    create_error_card,
    create_metric_card,
    create_post_card,
)
from brand_copy import COPY
from data import (
    get_asset_screener_data,
    get_screener_sparkline_prices,
    load_recent_posts,
    get_dashboard_kpis_with_fallback,
    get_dynamic_insights,
)
from components.screener import build_screener_table
from components.insights import create_insight_cards


def register_content_callbacks(app: Dash) -> None:
    """Register main dashboard content callbacks.

    Args:
        app: The Dash application instance.
    """

    @app.callback(
        [
            Output("insight-cards-container", "children"),
            Output("screener-table-container", "children"),
            Output("performance-metrics", "children"),
            Output("last-update-timestamp", "data"),
        ],
        [
            Input("refresh-interval", "n_intervals"),
            Input("selected-period", "data"),
        ],
    )
    def update_dashboard(n_intervals, period):
        """Update main dashboard components with error boundaries."""
        errors = []

        days_map = {"7d": 7, "30d": 30, "90d": 90, "all": None}
        days = days_map.get(period, 90)

        current_time = datetime.now().isoformat()

        # ===== Dynamic Insight Cards =====
        try:
            insight_pool = get_dynamic_insights(days=days)
            insight_cards = create_insight_cards(insight_pool, max_cards=3)
        except Exception as e:
            errors.append(f"Insight cards: {e}")
            print(f"Error loading insight cards: {traceback.format_exc()}")
            insight_cards = html.Div()

        # ===== Asset Screener Table =====
        try:
            screener_df = get_asset_screener_data(days=days)
            sparkline_data = {}
            if not screener_df.empty:
                symbols = tuple(screener_df["symbol"].tolist())
                sparkline_data = get_screener_sparkline_prices(symbols=symbols)

            screener_table = build_screener_table(
                screener_df=screener_df,
                sparkline_data=sparkline_data,
                sort_column="total_predictions",
                sort_ascending=False,
            )
        except Exception as e:
            errors.append(f"Asset screener: {e}")
            print(f"Error loading asset screener: {traceback.format_exc()}")
            screener_table = create_error_card("Unable to load asset screener", str(e))

        # ===== Performance Metrics =====
        try:
            kpis = get_dashboard_kpis_with_fallback(days=days)
            fallback_note = kpis["fallback_label"] if kpis["is_fallback"] else ""

            metrics_row = dbc.Row(
                [
                    dbc.Col(
                        create_metric_card(
                            COPY["kpi_total_signals_title"],
                            f"{kpis['total_signals']}",
                            COPY["kpi_total_signals_subtitle"],
                            "signal",
                            COLORS["accent"],
                            note=fallback_note,
                        ),
                        xs=6, sm=6, md=3,
                        className="kpi-col-mobile",
                    ),
                    dbc.Col(
                        create_metric_card(
                            COPY["kpi_accuracy_title"],
                            f"{kpis['accuracy_pct']:.1f}%",
                            COPY["kpi_accuracy_subtitle"],
                            "bullseye",
                            COLORS["success"]
                            if kpis["accuracy_pct"] > 50
                            else COLORS["danger"],
                            note=fallback_note,
                        ),
                        xs=6, sm=6, md=3,
                        className="kpi-col-mobile",
                    ),
                    dbc.Col(
                        create_metric_card(
                            COPY["kpi_avg_return_title"],
                            f"{kpis['avg_return_t7']:+.2f}%",
                            COPY["kpi_avg_return_subtitle"],
                            "chart-line",
                            COLORS["success"]
                            if kpis["avg_return_t7"] > 0
                            else COLORS["danger"],
                            note=fallback_note,
                        ),
                        xs=6, sm=6, md=3,
                        className="kpi-col-mobile",
                    ),
                    dbc.Col(
                        create_metric_card(
                            COPY["kpi_pnl_title"],
                            f"${kpis['total_pnl']:+,.0f}",
                            COPY["kpi_pnl_subtitle"],
                            "dollar-sign",
                            COLORS["success"]
                            if kpis["total_pnl"] > 0
                            else COLORS["danger"],
                            note=fallback_note,
                        ),
                        xs=6, sm=6, md=3,
                        className="kpi-col-mobile",
                    ),
                ],
                className="g-2 g-md-2",
            )
        except Exception as e:
            errors.append(f"Performance metrics: {e}")
            print(f"Error loading performance metrics: {traceback.format_exc()}")
            metrics_row = create_error_card(
                "Unable to load performance metrics", str(e)
            )

        if errors:
            print(f"Dashboard update completed with errors: {errors}")

        return (
            insight_cards,
            screener_table,
            metrics_row,
            current_time,
        )

    @app.callback(
        Output("post-feed-container", "children"),
        [
            Input("refresh-interval", "n_intervals"),
            Input("selected-period", "data"),
        ],
    )
    def update_post_feed(n_intervals, period):
        """Update the Latest Posts feed with posts and their LLM analysis."""
        try:
            df = load_recent_posts(limit=20)

            if df.empty:
                return html.P(
                    COPY["empty_posts"],
                    style={
                        "color": COLORS["text_muted"],
                        "textAlign": "center",
                        "padding": "20px",
                    },
                )

            post_cards = [
                create_post_card(row, card_index=idx)
                for idx, (_, row) in enumerate(df.iterrows())
            ]
            return post_cards

        except Exception as e:
            print(f"Error loading post feed: {traceback.format_exc()}")
            return create_error_card("Unable to load post feed", str(e))
```

#### Step B4: Create `table.py` -- data table management callbacks

**New file:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard_callbacks/table.py`

```python
"""Data table management callbacks.

Handles screener row clicks, collapse toggling, predictions table
filtering, and thesis expand/collapse.
"""

import traceback

import dash
from dash import (
    Dash,
    html,
    dash_table,
    Input,
    Output,
    State,
    callback_context,
    MATCH,
    no_update,
)
import pandas as pd

from constants import COLORS
from components.cards import create_error_card
from brand_copy import COPY
from data import get_predictions_with_outcomes


def register_table_callbacks(app: Dash) -> None:
    """Register data table management callbacks.

    Args:
        app: The Dash application instance.
    """

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        [Input({"type": "screener-row", "index": dash.ALL}, "n_clicks")],
        prevent_initial_call=True,
    )
    def handle_screener_row_click(n_clicks_list):
        """Navigate to asset page when a screener row is clicked."""
        import json

        if not any(n_clicks_list):
            return no_update

        ctx = callback_context
        if not ctx.triggered:
            return no_update

        triggered_id = ctx.triggered[0]["prop_id"]
        try:
            id_str = triggered_id.split(".")[0]
            id_dict = json.loads(id_str)
            symbol = id_dict["index"]
            return f"/assets/{symbol}"
        except (json.JSONDecodeError, KeyError):
            return no_update

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

    @app.callback(
        Output("predictions-table-container", "children"),
        [
            Input("collapse-table", "is_open"),
            Input("confidence-slider", "value"),
            Input("date-range-picker", "start_date"),
            Input("date-range-picker", "end_date"),
            Input("limit-selector", "value"),
        ],
    )
    def update_predictions_table(
        is_open, confidence_range, start_date, end_date, limit
    ):
        """Update the predictions data table with error handling."""
        if not is_open:
            return None

        try:
            conf_min = confidence_range[0] if confidence_range else None
            conf_max = confidence_range[1] if confidence_range else None

            if conf_min == 0:
                conf_min = None
            if conf_max == 1:
                conf_max = None

            df = get_predictions_with_outcomes(
                limit=limit or 50,
                confidence_min=conf_min,
                confidence_max=conf_max,
                start_date=start_date,
                end_date=end_date,
            )

            if df.empty:
                return html.P(
                    COPY["empty_predictions_table"],
                    style={
                        "color": COLORS["text_muted"],
                        "textAlign": "center",
                        "padding": "20px",
                    },
                )

            display_df = df.copy()

            if "timestamp" in display_df.columns:
                display_df["timestamp"] = pd.to_datetime(
                    display_df["timestamp"]
                ).dt.strftime("%Y-%m-%d %H:%M")

            if "assets" in display_df.columns:
                display_df["assets"] = display_df["assets"].apply(
                    lambda x: (
                        ", ".join(x[:3]) + (f" +{len(x) - 3}" if len(x) > 3 else "")
                        if isinstance(x, list)
                        else str(x)
                    )
                )

            for col in ["return_t1", "return_t3", "return_t7"]:
                if col in display_df.columns:
                    display_df[col] = display_df[col].apply(
                        lambda x: f"{x:+.2f}%" if pd.notna(x) else "-"
                    )

            if "correct_t7" in display_df.columns:
                display_df["outcome"] = display_df["correct_t7"].apply(
                    lambda x: (
                        "Correct"
                        if x is True
                        else "Incorrect"
                        if x is False
                        else "Pending"
                    )
                )

            display_cols = ["timestamp", "assets", "confidence", "return_t7", "outcome"]
            display_cols = [c for c in display_cols if c in display_df.columns]

            return dash_table.DataTable(
                data=display_df[display_cols].to_dict("records"),
                columns=[
                    {"name": c.replace("_", " ").title(), "id": c} for c in display_cols
                ],
                style_table={"overflowX": "auto"},
                style_cell={
                    "textAlign": "left",
                    "padding": "10px",
                    "backgroundColor": COLORS["primary"],
                    "color": COLORS["text"],
                    "border": f"1px solid {COLORS['border']}",
                    "fontSize": "0.85rem",
                },
                style_header={
                    "backgroundColor": COLORS["secondary"],
                    "fontWeight": "bold",
                    "border": f"1px solid {COLORS['border']}",
                },
                style_data_conditional=[
                    {
                        "if": {"filter_query": "{outcome} = 'Correct'"},
                        "backgroundColor": "rgba(16, 185, 129, 0.1)",
                    },
                    {
                        "if": {"filter_query": "{outcome} = 'Incorrect'"},
                        "backgroundColor": "rgba(239, 68, 68, 0.1)",
                    },
                ],
                page_size=15,
                sort_action="native",
                filter_action="native",
            )

        except Exception as e:
            print(f"Error loading predictions table: {traceback.format_exc()}")
            return create_error_card("Unable to load prediction data", str(e))

    # Post-card thesis expand/collapse -- clientside callback
    app.clientside_callback(
        """
        function(n_clicks) {
            if (!n_clicks || n_clicks === 0) {
                return [
                    {"display": "block"},
                    {"display": "none"},
                    "Show full thesis",
                    {"fontSize": "0.65rem", "transition": "transform 0.2s ease", "transform": "rotate(0deg)"}
                ];
            }
            var isExpanded = (n_clicks % 2) === 1;
            if (isExpanded) {
                return [
                    {"display": "none"},
                    {"display": "block"},
                    "Hide thesis",
                    {"fontSize": "0.65rem", "transition": "transform 0.2s ease", "transform": "rotate(180deg)"}
                ];
            } else {
                return [
                    {"display": "block"},
                    {"display": "none"},
                    "Show full thesis",
                    {"fontSize": "0.65rem", "transition": "transform 0.2s ease", "transform": "rotate(0deg)"}
                ];
            }
        }
        """,
        [
            Output({"type": "post-thesis-preview", "index": MATCH}, "style"),
            Output({"type": "post-thesis-full", "index": MATCH}, "style"),
            Output({"type": "post-thesis-toggle-text", "index": MATCH}, "children"),
            Output({"type": "post-thesis-chevron", "index": MATCH}, "style"),
        ],
        [Input({"type": "post-thesis-toggle", "index": MATCH}, "n_clicks")],
    )
```

#### Step B5: Refactor `dashboard.py` into thin orchestrator

**Modified file:** `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard.py`

**BEFORE** (lines 1-727): Contains 17 imports, `create_dashboard_page()` (lines 42-264), and `register_dashboard_callbacks()` (lines 267-726).

**AFTER:** Contains only `create_dashboard_page()` and a thin `register_dashboard_callbacks()` orchestrator. Most imports are removed since the callback logic moves to sub-modules.

```python
"""Dashboard page layout and callbacks."""

from dash import Dash, html, dcc
import dash_bootstrap_components as dbc

from constants import COLORS, HIERARCHY
from components.controls import create_filter_controls
from components.header import create_header, create_footer
from brand_copy import COPY


def create_dashboard_page() -> html.Div:
    """Create the main dashboard page layout (shown at /)."""
    # ... (unchanged -- lines 42-264 of current file, keep verbatim)
    return html.Div(
        [
            create_header(),
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
                    dcc.Loading(
                        id="insight-cards-loading",
                        type="default",
                        color=COLORS["accent"],
                        children=html.Div(
                            id="insight-cards-container",
                            style={"marginBottom": "16px"},
                        ),
                    ),
                    dcc.Loading(
                        id="performance-metrics-loading",
                        type="default",
                        color=COLORS["accent"],
                        children=html.Div(
                            id="performance-metrics",
                            style={"marginBottom": "32px"},
                        ),
                    ),
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                [
                                    html.I(className="fas fa-th-list me-2"),
                                    "Asset Screener",
                                    html.Small(
                                        " - performance by ticker, sorted"
                                        " & heat-mapped",
                                        style={
                                            "color": COLORS["text_muted"],
                                            "fontWeight": "normal",
                                        },
                                    ),
                                ],
                                className="fw-bold",
                                style={
                                    "backgroundColor": HIERARCHY["secondary"][
                                        "background"
                                    ]
                                },
                            ),
                            dbc.CardBody(
                                [
                                    dcc.Loading(
                                        type="circle",
                                        color=COLORS["accent"],
                                        children=html.Div(
                                            id="screener-table-container",
                                        ),
                                    ),
                                ],
                                style={
                                    "backgroundColor": HIERARCHY["secondary"][
                                        "background"
                                    ],
                                    "padding": "12px",
                                },
                            ),
                        ],
                        className="mb-4",
                        style={
                            "backgroundColor": HIERARCHY["secondary"]["background"],
                            "borderTop": HIERARCHY["secondary"]["accent_top"],
                            "boxShadow": HIERARCHY["secondary"]["shadow"],
                        },
                    ),
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                [
                                    html.I(className="fas fa-rss me-2"),
                                    COPY["latest_posts_header"],
                                    html.Small(
                                        f" - {COPY['latest_posts_subtitle']}",
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
                        className="section-tertiary mb-4",
                        style={
                            "backgroundColor": HIERARCHY["tertiary"]["background"],
                            "border": HIERARCHY["tertiary"]["border"],
                            "boxShadow": HIERARCHY["tertiary"]["shadow"],
                        },
                    ),
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
                                            COPY["data_table_header"],
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
                        className="section-tertiary mb-4",
                        style={
                            "backgroundColor": HIERARCHY["tertiary"]["background"],
                            "border": HIERARCHY["tertiary"]["border"],
                            "boxShadow": HIERARCHY["tertiary"]["shadow"],
                        },
                    ),
                    create_footer(),
                ],
                className="main-content-container",
                style={"padding": "20px", "maxWidth": "1400px", "margin": "0 auto"},
            ),
        ]
    )


def register_dashboard_callbacks(app: Dash):
    """Register all dashboard-specific callbacks.

    Delegates to focused sub-modules. This function is the single
    entry point called by layout.register_callbacks().
    """
    from pages.dashboard_callbacks import (
        register_period_callbacks,
        register_content_callbacks,
        register_table_callbacks,
    )

    register_period_callbacks(app)
    register_content_callbacks(app)
    register_table_callbacks(app)
```

**Key change summary for `dashboard.py`:**
- Imports reduced from 17 to 6 (only what `create_dashboard_page()` needs)
- Lines 42-264 (`create_dashboard_page()`): **unchanged**
- Lines 267-726 (`register_dashboard_callbacks()`): replaced with 3-line orchestrator
- Removed imports: `datetime`, `traceback`, `dash`, `Input`, `Output`, `State`, `callback_context`, `MATCH`, `dash_table`, `pd`, `create_error_card`, `create_metric_card`, `create_post_card`, `get_period_button_styles`, data functions, `build_screener_table`, `create_insight_cards`

---

## Test Plan

### Existing tests that must pass unchanged

All existing tests depend on the public API of `alerts.py` and `dashboard.py`. Because we maintain backward-compatible re-exports, **zero existing tests need modification.**

Key test files to verify:
1. `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_alert_callbacks.py` -- 69+ tests importing `build_preferences_dict`, `extract_preferences_tuple`, `build_alert_history_card`, `create_alert_config_panel` from `callbacks.alerts`
2. `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_alerts.py` -- 29+ tests importing from `alerts` (the service module, not `callbacks/alerts`)
3. `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_layout.py` -- 49+ tests importing `create_dashboard_page` from `pages.dashboard`
4. `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_brand_identity.py` -- imports `create_dashboard_page`
5. `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_information_architecture.py` -- imports `create_dashboard_page` and `pages.dashboard`

### New tests (Phase 05 scope)

This phase does NOT add new tests. Phase 05 will add tests for:
- `AlertPreferences` model (round-trip, validation, edge cases)
- Import verification for new sub-modules
- Registration function smoke tests

### Manual verification steps

1. Run full test suite: `./venv/bin/python -m pytest shit_tests/shitty_ui/ -v`
2. Run linting: `./venv/bin/python -m ruff check shitty_ui/`
3. Run formatting: `./venv/bin/python -m ruff format --check shitty_ui/`
4. Start the dashboard locally and verify:
   - Alert config panel opens/closes
   - Preferences save and load correctly
   - Period selection works
   - KPI cards render
   - Screener table renders with clickable rows
   - Data table expand/collapse works
   - Post feed loads
   - Thesis expand/collapse works

---

## Documentation Updates

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Changed
- **Alert callbacks** - Split monolithic `register_alert_callbacks()` (479 LOC) into 3 focused sub-modules: `alert_preferences.py`, `alert_history.py`, `alert_notifications.py`
- **Dashboard callbacks** - Split monolithic `register_dashboard_callbacks()` (460 LOC) into 3 focused sub-modules: `period.py`, `content.py`, `table.py`
- **Alert preferences** - Replaced `build_preferences_dict()`/`extract_preferences_tuple()` pair with `AlertPreferences` Pydantic model (backward-compatible wrappers retained)
```

### CLAUDE.md

Update the directory tree in the "Themed Directory Structure" section. Under `shitty_ui/callbacks/`:
```
├── callbacks/          # Callback groups (alerts, navigation, clientside)
│   ├── alerts.py           # Alert system orchestrator + panel components
│   ├── alert_components.py # Alert config panel UI builders
│   ├── alert_models.py     # AlertPreferences Pydantic model
│   ├── alert_preferences.py # Preference management callbacks
│   ├── alert_history.py    # History rendering callbacks
│   └── alert_notifications.py # Browser notification callbacks
```

Under `shitty_ui/pages/`:
```
├── pages/              # Page modules (dashboard, assets)
│   ├── dashboard.py        # Dashboard layout + callback orchestrator
│   ├── dashboard_callbacks/ # Dashboard callback sub-modules
│   │   ├── period.py       # Period selection + countdown
│   │   ├── content.py      # KPI, screener, insights, post feed
│   │   └── table.py        # Data table, row clicks, thesis expand
│   └── assets.py           # Asset detail page layout + callbacks
```

---

## Stress Testing & Edge Cases

1. **Import order sensitivity:** Dash registers callbacks at import time when using decorators. Our approach uses `@app.callback()` inside functions called at registration time, which is the existing pattern. The `app` reference is passed through explicitly. No circular imports are possible because sub-modules only import from `data`, `constants`, `components`, `brand_copy`, and `alerts` (the service module), never from `layout.py` or each other.

2. **Duplicate Output IDs:** Dash disallows registering the same `Output` twice (except with `allow_duplicate=True`). We must ensure no two sub-modules register the same output. The split carefully assigns each callback to exactly one sub-module. The `allow_duplicate=True` outputs (`alert-notification-store`, `alert-history-store`, `url`) each appear in exactly one sub-module.

3. **`suppress_callback_exceptions=True`:** The app already sets this in `layout.py:66`. This means callbacks can reference component IDs not yet in the layout (important for page routing). This setting stays unchanged.

4. **`prevent_initial_call` preservation:** Every callback that has `prevent_initial_call=True` in the original code must retain it in the extracted version. All extractions preserve this flag exactly.

5. **Clientside callback registration order:** `app.clientside_callback()` calls are not order-sensitive in Dash -- they register independently. Safe to split across modules.

---

## Verification Checklist

- [ ] All 5 new files created with correct content
- [ ] `alerts.py` modified to thin orchestrator with backward-compatible re-exports
- [ ] `dashboard.py` modified to thin orchestrator
- [ ] `layout.py` remains **completely unchanged** (no modifications needed)
- [ ] Run: `./venv/bin/python -m pytest shit_tests/shitty_ui/test_alert_callbacks.py -v` -- all pass
- [ ] Run: `./venv/bin/python -m pytest shit_tests/shitty_ui/test_alerts.py -v` -- all pass
- [ ] Run: `./venv/bin/python -m pytest shit_tests/shitty_ui/test_layout.py -v` -- all pass
- [ ] Run: `./venv/bin/python -m pytest shit_tests/shitty_ui/ -v` -- all pass
- [ ] Run: `./venv/bin/python -m ruff check shitty_ui/callbacks/ shitty_ui/pages/` -- no errors
- [ ] Verify `build_preferences_dict` import still works: `from callbacks.alerts import build_preferences_dict`
- [ ] Verify `extract_preferences_tuple` import still works: `from callbacks.alerts import extract_preferences_tuple`
- [ ] Verify `register_dashboard_callbacks` import still works: `from pages.dashboard import register_dashboard_callbacks`
- [ ] CHANGELOG.md updated
- [ ] CLAUDE.md directory tree updated

---

## What NOT To Do

1. **Do NOT change `layout.py`.** It imports `register_alert_callbacks` from `callbacks.alerts` and `register_dashboard_callbacks` from `pages.dashboard`. Both remain exactly where they are, just internally delegating to sub-modules. `layout.py` is NOT touched in this PR.

2. **Do NOT move `build_alert_history_card()` out of `alerts.py`.** It is imported by `alert_history.py` via `from callbacks.alerts import build_alert_history_card`. Moving it would break the existing test imports. It is a rendering function, not a callback, so it belongs in the component file.

3. **Do NOT change any callback IDs, Output/Input/State component references, or `prevent_initial_call` flags.** This is a purely structural refactor. Every callback must produce identical behavior.

4. **Do NOT use relative imports.** All existing code uses absolute imports from the `shitty_ui/` root (e.g., `from callbacks.alerts import ...`, `from data import ...`). New modules must follow the same pattern.

5. **Do NOT import the new sub-modules at module level in `alerts.py` or `dashboard.py`.** Use lazy imports inside `register_*_callbacks()` to avoid circular import issues. The sub-modules import from `callbacks.alerts` (for `build_alert_history_card`), so `alerts.py` must not import from the sub-modules at the top level.

6. **Do NOT remove the `build_preferences_dict()` or `extract_preferences_tuple()` functions from `alerts.py`.** They must remain as backward-compatible wrappers because `test_alert_callbacks.py` imports them directly: `from callbacks.alerts import build_preferences_dict, extract_preferences_tuple`.

7. **Do NOT create an `__init__.py` for `shitty_ui/callbacks/` that imports from sub-modules.** The existing `__init__.py` is empty and should stay empty. Tests import directly from `callbacks.alerts`, not from `callbacks`.

8. **Do NOT add `pydantic` to `requirements.txt`.** Pydantic is already a dependency (used by `shit/config/shitpost_settings.py`).

---

- Wrote: /Users/chris/Projects/shitpost-alpha/documentation/planning/tech_debt/codebase-health_2026-02-25/04_callback-split.md
- PR title: refactor: split monolithic callback registration into focused modules
- Effort: High (~8 hours)
- Risk: Medium
- Files modified: 3 | Files created: 5
- Dependencies: None
- Unlocks: Phase 05 (tests), Phase 08 (Dash 4 migration)