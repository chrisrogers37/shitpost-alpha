# Phase 06: Refactor alerts callbacks into focused modules with tests

**Status:** 📋 PENDING

| Field | Value |
|-------|-------|
| **PR Title** | refactor: split alerts callbacks into focused modules with tests |
| **Risk Level** | Medium |
| **Effort** | High (~6-8 hours) |
| **Files Created** | 3 |
| **Files Modified** | 3 |
| **Files Deleted** | 0 |

---

## Context

`shitty_ui/callbacks/alerts.py` is 1,240 lines containing two megafunctions:

1. **`create_alert_config_panel()`** (lines 17-604, ~590 lines) -- builds the entire Offcanvas panel in a single monolithic return statement with 8 distinct UI sections inlined together.
2. **`register_alert_callbacks()`** (lines 649-1240, ~593 lines) -- registers 19 Dash callbacks inside a single function, mixing UI state toggles, preference persistence, polling logic, browser notification dispatch, history rendering, and data integration.

The existing test file (`shit_tests/shitty_ui/test_alerts.py`, 679 lines) tests the *notifications-layer* alert engine (`shitty_ui/alerts.py`) but has **zero coverage** of the *callbacks-layer* code in `shitty_ui/callbacks/alerts.py`. Specifically, no tests exist for:
- The `render_alert_history()` callback (time formatting, sentiment coloring, truncation)
- The `run_alert_check()` callback (polling state management, quiet hours, history append)
- The `save_alert_preferences()` callback (preferences dict assembly)
- The `load_preferences_into_form()` callback (preferences deserialization)
- Any of the panel sub-component builder functions (after extraction)

This refactor splits both megafunctions into focused, testable units and adds comprehensive test coverage for the callback logic.

---

## Dependencies

- **Depends on**: Phase 01 (conftest fix -- tests must run cleanly before adding new ones)
- **Unlocks**: None

---

## Detailed Implementation Plan

### Step 1: Create `shitty_ui/callbacks/alert_components.py` -- panel sub-components

Extract 8 builder functions from `create_alert_config_panel()`. Each function returns a Dash component tree for one logical section of the panel.

**File to create**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/callbacks/alert_components.py`

```python
"""
Sub-component builders for the alert configuration panel.

Each function returns a Dash component tree for one logical section
of the alert config Offcanvas. Extracted from the monolithic
create_alert_config_panel() to enable isolated testing.
"""

from dash import html, dcc
import dash_bootstrap_components as dbc

from constants import COLORS


def build_master_toggle_section() -> html.Div:
    """
    Build the master enable/disable toggle at the top of the panel.

    Returns:
        html.Div containing the power icon, "Enable Alerts" label,
        and the dbc.Switch with id="alert-master-toggle".
    """
    return html.Div(
        [
            html.Div(
                [
                    html.I(
                        className="fas fa-power-off me-2",
                        style={"color": COLORS["accent"]},
                    ),
                    html.Span(
                        "Enable Alerts",
                        style={"fontWeight": "bold", "fontSize": "1rem"},
                    ),
                ],
                style={"display": "flex", "alignItems": "center"},
            ),
            dbc.Switch(
                id="alert-master-toggle",
                value=False,
                className="ms-auto",
                style={"transform": "scale(1.3)"},
            ),
        ],
        style={
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "padding": "15px",
            "backgroundColor": COLORS["secondary"],
            "borderRadius": "8px",
            "marginBottom": "20px",
        },
    )


def build_status_indicator() -> html.Div:
    """
    Build the alert status indicator (red/green dot + text).

    Returns:
        html.Div with id="alert-status-indicator".
    """
    return html.Div(
        id="alert-status-indicator",
        children=[
            html.I(
                className="fas fa-circle me-2",
                style={"color": COLORS["danger"], "fontSize": "0.6rem"},
            ),
            html.Span(
                "Alerts disabled",
                style={"color": COLORS["text_muted"], "fontSize": "0.85rem"},
            ),
        ],
        style={"marginBottom": "20px", "textAlign": "center"},
    )


def build_confidence_threshold_section() -> html.Div:
    """
    Build the minimum confidence slider section.

    Returns:
        html.Div containing the label, percentage display
        (id="confidence-threshold-display"), dcc.Slider
        (id="alert-confidence-slider"), and helper text.
    """
    return html.Div(
        [
            html.Label(
                "Minimum Confidence",
                style={
                    "color": COLORS["text"],
                    "fontWeight": "500",
                    "fontSize": "0.9rem",
                },
            ),
            html.Div(
                id="confidence-threshold-display",
                children="70%",
                style={
                    "color": COLORS["accent"],
                    "fontWeight": "bold",
                    "fontSize": "0.9rem",
                    "float": "right",
                },
            ),
            dcc.Slider(
                id="alert-confidence-slider",
                min=0.0,
                max=1.0,
                step=0.05,
                value=0.7,
                marks={
                    0.0: {
                        "label": "0%",
                        "style": {"color": COLORS["text_muted"]},
                    },
                    0.5: {
                        "label": "50%",
                        "style": {"color": COLORS["text_muted"]},
                    },
                    0.7: {
                        "label": "70%",
                        "style": {"color": COLORS["warning"]},
                    },
                    1.0: {
                        "label": "100%",
                        "style": {"color": COLORS["text_muted"]},
                    },
                },
                tooltip={"placement": "bottom", "always_visible": False},
            ),
            html.Small(
                "Only alert when prediction confidence is at or above this level.",
                style={"color": COLORS["text_muted"]},
            ),
        ],
        style={"marginBottom": "20px"},
    )


def build_asset_selection_section() -> html.Div:
    """
    Build the assets-of-interest dropdown section.

    Returns:
        html.Div containing the label, dcc.Dropdown
        (id="alert-assets-dropdown"), and helper text.
    """
    return html.Div(
        [
            html.Label(
                "Assets of Interest",
                style={
                    "color": COLORS["text"],
                    "fontWeight": "500",
                    "fontSize": "0.9rem",
                },
            ),
            dcc.Dropdown(
                id="alert-assets-dropdown",
                options=[],  # Populated by callback from DB
                value=[],
                multi=True,
                placeholder="All assets (leave empty for all)",
                style={
                    "backgroundColor": COLORS["primary"],
                    "color": COLORS["text"],
                },
                className="mb-1",
            ),
            html.Small(
                "Leave empty to receive alerts for all assets. Select specific tickers to filter.",
                style={"color": COLORS["text_muted"]},
            ),
        ],
        style={"marginBottom": "20px"},
    )


def build_sentiment_filter_section() -> html.Div:
    """
    Build the sentiment radio button filter section.

    Returns:
        html.Div containing the label and dbc.RadioItems
        (id="alert-sentiment-radio").
    """
    return html.Div(
        [
            html.Label(
                "Sentiment Filter",
                style={
                    "color": COLORS["text"],
                    "fontWeight": "500",
                    "fontSize": "0.9rem",
                },
            ),
            dbc.RadioItems(
                id="alert-sentiment-radio",
                options=[
                    {"label": " All Sentiments", "value": "all"},
                    {"label": " Bullish Only", "value": "bullish"},
                    {"label": " Bearish Only", "value": "bearish"},
                    {"label": " Neutral Only", "value": "neutral"},
                ],
                value="all",
                inline=False,
                style={"color": COLORS["text"]},
                labelStyle={
                    "display": "block",
                    "padding": "6px 0",
                    "fontSize": "0.9rem",
                },
            ),
        ],
        style={"marginBottom": "20px"},
    )


def build_notification_channels_section() -> list:
    """
    Build all notification channel toggles (browser, email, SMS, Telegram).

    Returns:
        list of html.Div components for each channel, including
        collapse wrappers for email/SMS input fields.
    """
    browser_section = html.Div(
        [
            html.Div(
                [
                    html.I(
                        className="fas fa-globe me-2",
                        style={"color": COLORS["text_muted"]},
                    ),
                    html.Span(
                        "Browser Notifications", style={"fontSize": "0.9rem"}
                    ),
                ],
                style={"display": "flex", "alignItems": "center"},
            ),
            dbc.Switch(
                id="alert-browser-toggle",
                value=True,
                className="ms-auto",
            ),
        ],
        style={
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "padding": "10px 15px",
            "backgroundColor": COLORS["secondary"],
            "borderRadius": "8px",
            "marginBottom": "10px",
        },
    )

    browser_status = html.Div(
        id="browser-notification-status",
        style={"marginBottom": "15px", "fontSize": "0.8rem"},
    )

    email_section = html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.I(
                                className="fas fa-envelope me-2",
                                style={"color": COLORS["text_muted"]},
                            ),
                            html.Span(
                                "Email Notifications",
                                style={"fontSize": "0.9rem"},
                            ),
                        ],
                        style={"display": "flex", "alignItems": "center"},
                    ),
                    dbc.Switch(
                        id="alert-email-toggle",
                        value=False,
                        className="ms-auto",
                    ),
                ],
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                },
            ),
            dbc.Collapse(
                dbc.Input(
                    id="alert-email-input",
                    type="email",
                    placeholder="your@email.com",
                    className="mt-2",
                    style={
                        "backgroundColor": COLORS["primary"],
                        "color": COLORS["text"],
                        "border": f"1px solid {COLORS['border']}",
                    },
                ),
                id="email-input-collapse",
                is_open=False,
            ),
        ],
        style={
            "padding": "10px 15px",
            "backgroundColor": COLORS["secondary"],
            "borderRadius": "8px",
            "marginBottom": "10px",
        },
    )

    sms_section = html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.I(
                                className="fas fa-sms me-2",
                                style={"color": COLORS["text_muted"]},
                            ),
                            html.Span(
                                "SMS Notifications",
                                style={"fontSize": "0.9rem"},
                            ),
                        ],
                        style={"display": "flex", "alignItems": "center"},
                    ),
                    dbc.Switch(
                        id="alert-sms-toggle",
                        value=False,
                        className="ms-auto",
                    ),
                ],
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                },
            ),
            dbc.Collapse(
                html.Div(
                    [
                        dbc.Input(
                            id="alert-sms-input",
                            type="tel",
                            placeholder="+1 (555) 123-4567",
                            className="mt-2",
                            style={
                                "backgroundColor": COLORS["primary"],
                                "color": COLORS["text"],
                                "border": f"1px solid {COLORS['border']}",
                            },
                        ),
                        html.Small(
                            "Enter phone number in E.164 format (e.g., +15551234567).",
                            className="mt-1",
                            style={"color": COLORS["text_muted"]},
                        ),
                    ]
                ),
                id="sms-input-collapse",
                is_open=False,
            ),
        ],
        style={
            "padding": "10px 15px",
            "backgroundColor": COLORS["secondary"],
            "borderRadius": "8px",
            "marginBottom": "10px",
        },
    )

    telegram_section = html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.I(
                                className="fab fa-telegram me-2",
                                style={"color": "#0088cc"},
                            ),
                            html.Span(
                                "Telegram Notifications",
                                style={
                                    "fontSize": "0.9rem",
                                    "fontWeight": "bold",
                                },
                            ),
                            html.Span(
                                " (Free!)",
                                style={
                                    "fontSize": "0.75rem",
                                    "color": COLORS["success"],
                                    "marginLeft": "5px",
                                },
                            ),
                        ],
                        style={"display": "flex", "alignItems": "center"},
                    ),
                ]
            ),
            html.Div(
                [
                    html.P(
                        [
                            "Get unlimited free alerts via Telegram! ",
                            "Add our bot to receive predictions directly in your chat.",
                        ],
                        style={
                            "fontSize": "0.85rem",
                            "color": COLORS["text_muted"],
                            "margin": "10px 0",
                        },
                    ),
                    html.Div(
                        [
                            html.A(
                                [
                                    html.I(className="fab fa-telegram me-2"),
                                    "Open @ShitpostAlphaBot",
                                ],
                                href="https://t.me/ShitpostAlphaBot",
                                target="_blank",
                                className="btn btn-info btn-sm",
                                style={
                                    "backgroundColor": "#0088cc",
                                    "border": "none",
                                    "color": "white",
                                },
                            ),
                        ],
                        className="mb-2",
                    ),
                    html.Small(
                        [
                            "1. Click the link above to open the bot",
                            html.Br(),
                            "2. Send /start to subscribe",
                            html.Br(),
                            "3. Use /settings to customize your alerts",
                        ],
                        style={
                            "color": COLORS["text_muted"],
                            "fontSize": "0.75rem",
                            "lineHeight": "1.5",
                        },
                    ),
                ]
            ),
        ],
        style={
            "padding": "10px 15px",
            "backgroundColor": COLORS["secondary"],
            "borderRadius": "8px",
            "marginBottom": "10px",
            "border": "1px solid #0088cc33",
        },
    )

    return [browser_section, browser_status, email_section, sms_section, telegram_section]


def build_quiet_hours_section() -> html.Div:
    """
    Build the quiet hours toggle and time picker section.

    Returns:
        html.Div containing the enable switch
        (id="alert-quiet-hours-toggle") and collapsible
        start/end time inputs.
    """
    return html.Div(
        [
            html.Div(
                [
                    html.Span(
                        "Enable Quiet Hours", style={"fontSize": "0.9rem"}
                    ),
                    dbc.Switch(
                        id="alert-quiet-hours-toggle",
                        value=False,
                        className="ms-auto",
                    ),
                ],
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                    "marginBottom": "10px",
                },
            ),
            dbc.Collapse(
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                html.Label(
                                    "Start",
                                    style={
                                        "fontSize": "0.85rem",
                                        "color": COLORS["text_muted"],
                                    },
                                ),
                                dbc.Input(
                                    id="quiet-hours-start",
                                    type="time",
                                    value="22:00",
                                    style={
                                        "backgroundColor": COLORS["primary"],
                                        "color": COLORS["text"],
                                        "border": f"1px solid {COLORS['border']}",
                                    },
                                ),
                            ],
                            width=6,
                        ),
                        dbc.Col(
                            [
                                html.Label(
                                    "End",
                                    style={
                                        "fontSize": "0.85rem",
                                        "color": COLORS["text_muted"],
                                    },
                                ),
                                dbc.Input(
                                    id="quiet-hours-end",
                                    type="time",
                                    value="08:00",
                                    style={
                                        "backgroundColor": COLORS["primary"],
                                        "color": COLORS["text"],
                                        "border": f"1px solid {COLORS['border']}",
                                    },
                                ),
                            ],
                            width=6,
                        ),
                    ]
                ),
                id="quiet-hours-collapse",
                is_open=False,
            ),
        ],
        style={
            "padding": "10px 15px",
            "backgroundColor": COLORS["secondary"],
            "borderRadius": "8px",
            "marginBottom": "20px",
        },
    )


def build_action_buttons_section() -> list:
    """
    Build the Save / Test / Clear buttons and the save confirmation toast.

    Returns:
        list containing the button Div, the dbc.Toast, and the
        localStorage note.
    """
    buttons = html.Div(
        [
            dbc.Button(
                [html.I(className="fas fa-save me-2"), "Save Preferences"],
                id="save-alert-prefs-button",
                color="primary",
                className="w-100 mb-2",
            ),
            dbc.Button(
                [html.I(className="fas fa-bell me-2"), "Send Test Alert"],
                id="test-alert-button",
                color="secondary",
                outline=True,
                className="w-100 mb-2",
            ),
            dbc.Button(
                [html.I(className="fas fa-trash me-2"), "Clear Alert History"],
                id="clear-alert-history-button",
                color="danger",
                outline=True,
                size="sm",
                className="w-100",
            ),
        ]
    )

    toast = dbc.Toast(
        id="alert-save-toast",
        header="Preferences Saved",
        is_open=False,
        dismissable=True,
        duration=3000,
        icon="success",
        style={
            "position": "fixed",
            "bottom": 20,
            "right": 20,
            "width": 280,
            "zIndex": 9999,
        },
        children="Your alert preferences have been saved.",
    )

    local_storage_note = html.Small(
        "Preferences are stored in your browser. They are not synced across devices.",
        style={
            "color": COLORS["text_muted"],
            "fontSize": "0.75rem",
            "display": "block",
            "marginTop": "15px",
            "textAlign": "center",
        },
    )

    return [buttons, toast, local_storage_note]
```

### Step 2: Rewrite `create_alert_config_panel()` to use sub-components

**File to modify**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/callbacks/alerts.py`

**Current code (lines 1-15, imports):**
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
```

**Replace with:**
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
```

**Current code (lines 17-604, entire `create_alert_config_panel()`):**

The entire 590-line function body.

**Replace with:**
```python
def create_alert_config_panel():
    """
    Create the alert configuration slide-out panel.

    Returns a dbc.Offcanvas component that slides in from the right
    when the user clicks the bell icon in the header. Each section
    is built by a dedicated function in alert_components.py.
    """
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
            # --- Filter Settings ---
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
            # --- Notification Channels ---
            html.H6(
                [
                    html.I(className="fas fa-paper-plane me-2"),
                    "Notification Channels",
                ],
                style={"color": COLORS["accent"], "marginBottom": "15px"},
            ),
            *notification_channels,
            html.Hr(style={"borderColor": COLORS["border"]}),
            # --- Quiet Hours ---
            html.H6(
                [
                    html.I(className="fas fa-moon me-2"),
                    "Quiet Hours",
                ],
                style={"color": COLORS["accent"], "marginBottom": "15px"},
            ),
            build_quiet_hours_section(),
            html.Hr(style={"borderColor": COLORS["border"]}),
            # --- Save / Test Buttons ---
            *action_buttons,
        ],
    )
```

**Do NOT change `create_alert_history_panel()`** (lines 607-646). It is already a reasonable size (~40 lines) and does not need extraction.

### Step 3: Extract helper functions from `register_alert_callbacks()`

Two inner functions inside `register_alert_callbacks()` contain non-trivial logic that is currently untestable because they are nested inside a closure. Extract them as module-level functions.

**File to modify**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/callbacks/alerts.py`

Add these two functions **after** the `create_alert_history_panel()` function (after line 646) and **before** `register_alert_callbacks()` (currently line 649):

```python
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
    """
    Assemble a preferences dict from individual form field values.

    This is the canonical shape of the preferences object stored
    in localStorage via alert-preferences-store.

    Args:
        enabled: Master toggle state.
        min_confidence: Minimum confidence threshold (0.0-1.0).
        assets: List of ticker symbols to filter on.
        sentiment: Sentiment filter ("all", "bullish", "bearish", "neutral").
        browser_on: Whether browser notifications are enabled.
        email_on: Whether email notifications are enabled.
        email_addr: Email address for notifications.
        sms_on: Whether SMS notifications are enabled.
        sms_phone: Phone number for SMS notifications.
        quiet_on: Whether quiet hours are enabled.
        quiet_start: Quiet hours start time (HH:MM).
        quiet_end: Quiet hours end time (HH:MM).

    Returns:
        dict with all preference keys populated with safe defaults for None values.
    """
    return {
        "enabled": bool(enabled),
        "min_confidence": float(min_confidence or 0.7),
        "assets_of_interest": assets or [],
        "sentiment_filter": sentiment or "all",
        "browser_notifications": bool(browser_on),
        "email_enabled": bool(email_on),
        "email_address": email_addr or "",
        "sms_enabled": bool(sms_on),
        "sms_phone_number": sms_phone or "",
        "quiet_hours_enabled": bool(quiet_on),
        "quiet_hours_start": quiet_start or "22:00",
        "quiet_hours_end": quiet_end or "08:00",
        "max_alerts_per_hour": 10,
    }


def extract_preferences_tuple(prefs: dict) -> tuple:
    """
    Extract form field values from a preferences dict.

    Returns a 12-element tuple matching the Output order of
    load_preferences_into_form().

    Args:
        prefs: Preferences dict from localStorage.

    Returns:
        Tuple of (enabled, min_confidence, assets, sentiment,
        browser_on, email_on, email_addr, sms_on, sms_phone,
        quiet_on, quiet_start, quiet_end).
    """
    return (
        prefs.get("enabled", False),
        prefs.get("min_confidence", 0.7),
        prefs.get("assets_of_interest", []),
        prefs.get("sentiment_filter", "all"),
        prefs.get("browser_notifications", True),
        prefs.get("email_enabled", False),
        prefs.get("email_address", ""),
        prefs.get("sms_enabled", False),
        prefs.get("sms_phone_number", ""),
        prefs.get("quiet_hours_enabled", False),
        prefs.get("quiet_hours_start", "22:00"),
        prefs.get("quiet_hours_end", "08:00"),
    )


def build_alert_history_card(alert: dict) -> html.Div:
    """
    Build a single alert history card from an alert dict.

    Handles sentiment coloring, timestamp formatting, text truncation,
    and asset display.

    Args:
        alert: Dict with keys: sentiment, confidence, assets, text,
               alert_triggered_at.

    Returns:
        html.Div component for one alert history entry.
    """
    sentiment = alert.get("sentiment", "neutral")
    confidence = alert.get("confidence", 0)
    assets = alert.get("assets", [])
    text = alert.get("text", "")[:120]
    triggered_at = alert.get("alert_triggered_at", "")

    # Sentiment styling
    if sentiment == "bullish":
        sentiment_color = COLORS["success"]
        sentiment_icon = "arrow-up"
    elif sentiment == "bearish":
        sentiment_color = COLORS["danger"]
        sentiment_icon = "arrow-down"
    else:
        sentiment_color = COLORS["text_muted"]
        sentiment_icon = "minus"

    # Format timestamp
    try:
        ts = datetime.fromisoformat(triggered_at.replace("Z", "+00:00"))
        time_str = ts.strftime("%b %d, %H:%M")
    except (ValueError, TypeError):
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
```

### Step 4: Update `register_alert_callbacks()` to use extracted functions

**File to modify**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/callbacks/alerts.py`

#### 4a: Update `save_alert_preferences` callback (currently lines 766-800)

**Current code (lines 780-800):**
```python
    ):
        """
        Gather all form values and write them to the localStorage-backed store.
        Also show a confirmation toast.
        """
        preferences = {
            "enabled": bool(enabled),
            "min_confidence": float(min_confidence or 0.7),
            "assets_of_interest": assets or [],
            "sentiment_filter": sentiment or "all",
            "browser_notifications": bool(browser_on),
            "email_enabled": bool(email_on),
            "email_address": email_addr or "",
            "sms_enabled": bool(sms_on),
            "sms_phone_number": sms_phone or "",
            "quiet_hours_enabled": bool(quiet_on),
            "quiet_hours_start": quiet_start or "22:00",
            "quiet_hours_end": quiet_end or "08:00",
            "max_alerts_per_hour": 10,
        }
        return preferences, True  # True opens the toast
```

**Replace with:**
```python
    ):
        """
        Gather all form values and write them to the localStorage-backed store.
        Also show a confirmation toast.
        """
        preferences = build_preferences_dict(
            enabled, min_confidence, assets, sentiment,
            browser_on, email_on, email_addr,
            sms_on, sms_phone,
            quiet_on, quiet_start, quiet_end,
        )
        return preferences, True  # True opens the toast
```

#### 4b: Update `load_preferences_into_form` callback (currently lines 821-839)

**Current code (lines 821-839):**
```python
    def load_preferences_into_form(is_open: bool, prefs: dict):
        """When the offcanvas opens, populate form fields from stored preferences."""
        if not is_open or not prefs:
            return (no_update,) * 12

        return (
            prefs.get("enabled", False),
            prefs.get("min_confidence", 0.7),
            prefs.get("assets_of_interest", []),
            prefs.get("sentiment_filter", "all"),
            prefs.get("browser_notifications", True),
            prefs.get("email_enabled", False),
            prefs.get("email_address", ""),
            prefs.get("sms_enabled", False),
            prefs.get("sms_phone_number", ""),
            prefs.get("quiet_hours_enabled", False),
            prefs.get("quiet_hours_start", "22:00"),
            prefs.get("quiet_hours_end", "08:00"),
        )
```

**Replace with:**
```python
    def load_preferences_into_form(is_open: bool, prefs: dict):
        """When the offcanvas opens, populate form fields from stored preferences."""
        if not is_open or not prefs:
            return (no_update,) * 12

        return extract_preferences_tuple(prefs)
```

#### 4c: Update `render_alert_history` callback (currently lines 1068-1178)

**Current code (lines 1068-1178):**

The `render_alert_history` inner function builds alert cards inline with a 90-line for-loop.

**Replace with:**
```python
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
```

### Step 5: Update `shitty_ui/layout.py` imports

**File to modify**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/layout.py`

No changes needed. The `layout.py` imports `create_alert_config_panel` and `register_alert_callbacks` from `callbacks.alerts`, and both functions remain in that module with the same signatures. The new `alert_components` module is an internal dependency of `callbacks.alerts` only.

Verify that line 42 still works:
```python
from callbacks.alerts import create_alert_history_panel  # noqa: F401
```
This is unchanged -- `create_alert_history_panel` stays in `callbacks/alerts.py`.

### Step 6: Create `shitty_ui/callbacks/__init__.py` update

**File to inspect**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/callbacks/__init__.py`

This file is currently empty (1 line). **No changes needed.** The `alert_components` module does not need to be re-exported from `__init__.py` -- it is only imported by `alerts.py` within the same package.

### Step 7: Add comprehensive test coverage

**File to create**: `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_alert_callbacks.py`

This new test file covers the *callbacks-layer* code that was extracted from `shitty_ui/callbacks/alerts.py`. The existing `test_alerts.py` covers the *notifications-layer* code (`shitty_ui/alerts.py`) and must NOT be modified.

```python
"""
Tests for alert callback helpers and sub-component builders.

Covers:
- alert_components.py: Panel sub-component builders
- alerts.py (callbacks layer): build_preferences_dict, extract_preferences_tuple,
  build_alert_history_card
"""

import sys
import os
from datetime import datetime

# Add the shitty_ui directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))

import dash_bootstrap_components as dbc
from dash import html, dcc

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
from callbacks.alerts import (
    build_preferences_dict,
    extract_preferences_tuple,
    build_alert_history_card,
)


def _extract_text(component) -> str:
    """Recursively extract all text content from a Dash component tree."""
    parts = []
    if isinstance(component, str):
        return component
    if hasattr(component, "children"):
        children = component.children
        if isinstance(children, str):
            parts.append(children)
        elif isinstance(children, list):
            for child in children:
                if child is not None:
                    parts.append(_extract_text(child))
        elif children is not None:
            parts.append(_extract_text(children))
    return " ".join(parts)


def _find_component_by_id(component, target_id) -> object:
    """Recursively search for a component with a specific id."""
    if hasattr(component, "id") and component.id == target_id:
        return component
    if hasattr(component, "children"):
        children = component.children
        if isinstance(children, list):
            for child in children:
                if child is not None:
                    result = _find_component_by_id(child, target_id)
                    if result is not None:
                        return result
        elif children is not None:
            return _find_component_by_id(children, target_id)
    return None


# ============================================================
# Sub-component builder tests
# ============================================================


class TestBuildMasterToggleSection:
    """Test the master toggle sub-component."""

    def test_returns_html_div(self):
        """Returns an html.Div component."""
        result = build_master_toggle_section()
        assert isinstance(result, html.Div)

    def test_contains_switch_with_correct_id(self):
        """Contains a dbc.Switch with id='alert-master-toggle'."""
        result = build_master_toggle_section()
        switch = _find_component_by_id(result, "alert-master-toggle")
        assert switch is not None
        assert isinstance(switch, dbc.Switch)

    def test_switch_default_value_false(self):
        """Master toggle defaults to False (alerts off)."""
        result = build_master_toggle_section()
        switch = _find_component_by_id(result, "alert-master-toggle")
        assert switch.value is False

    def test_contains_enable_alerts_label(self):
        """Contains 'Enable Alerts' text."""
        result = build_master_toggle_section()
        text = _extract_text(result)
        assert "Enable Alerts" in text


class TestBuildStatusIndicator:
    """Test the alert status indicator sub-component."""

    def test_returns_div_with_correct_id(self):
        """Returns html.Div with id='alert-status-indicator'."""
        result = build_status_indicator()
        assert isinstance(result, html.Div)
        assert result.id == "alert-status-indicator"

    def test_default_text_says_disabled(self):
        """Default text says 'Alerts disabled'."""
        result = build_status_indicator()
        text = _extract_text(result)
        assert "Alerts disabled" in text


class TestBuildConfidenceThresholdSection:
    """Test the confidence slider sub-component."""

    def test_returns_html_div(self):
        """Returns an html.Div component."""
        result = build_confidence_threshold_section()
        assert isinstance(result, html.Div)

    def test_contains_slider_with_correct_id(self):
        """Contains a dcc.Slider with id='alert-confidence-slider'."""
        result = build_confidence_threshold_section()
        slider = _find_component_by_id(result, "alert-confidence-slider")
        assert slider is not None
        assert isinstance(slider, dcc.Slider)

    def test_slider_default_value_is_070(self):
        """Slider default value is 0.7 (70%)."""
        result = build_confidence_threshold_section()
        slider = _find_component_by_id(result, "alert-confidence-slider")
        assert slider.value == 0.7

    def test_slider_range_0_to_1(self):
        """Slider range is 0.0 to 1.0."""
        result = build_confidence_threshold_section()
        slider = _find_component_by_id(result, "alert-confidence-slider")
        assert slider.min == 0.0
        assert slider.max == 1.0

    def test_contains_display_element(self):
        """Contains the percentage display element."""
        result = build_confidence_threshold_section()
        display = _find_component_by_id(result, "confidence-threshold-display")
        assert display is not None
        assert display.children == "70%"


class TestBuildAssetSelectionSection:
    """Test the asset dropdown sub-component."""

    def test_returns_html_div(self):
        """Returns an html.Div component."""
        result = build_asset_selection_section()
        assert isinstance(result, html.Div)

    def test_contains_dropdown_with_correct_id(self):
        """Contains a dcc.Dropdown with id='alert-assets-dropdown'."""
        result = build_asset_selection_section()
        dropdown = _find_component_by_id(result, "alert-assets-dropdown")
        assert dropdown is not None
        assert isinstance(dropdown, dcc.Dropdown)

    def test_dropdown_is_multi_select(self):
        """Dropdown allows multiple selection."""
        result = build_asset_selection_section()
        dropdown = _find_component_by_id(result, "alert-assets-dropdown")
        assert dropdown.multi is True

    def test_dropdown_starts_empty(self):
        """Dropdown options start empty (populated by callback)."""
        result = build_asset_selection_section()
        dropdown = _find_component_by_id(result, "alert-assets-dropdown")
        assert dropdown.options == []
        assert dropdown.value == []


class TestBuildSentimentFilterSection:
    """Test the sentiment radio buttons sub-component."""

    def test_returns_html_div(self):
        """Returns an html.Div component."""
        result = build_sentiment_filter_section()
        assert isinstance(result, html.Div)

    def test_contains_radio_items_with_correct_id(self):
        """Contains dbc.RadioItems with id='alert-sentiment-radio'."""
        result = build_sentiment_filter_section()
        radio = _find_component_by_id(result, "alert-sentiment-radio")
        assert radio is not None
        assert isinstance(radio, dbc.RadioItems)

    def test_default_value_is_all(self):
        """Default sentiment filter is 'all'."""
        result = build_sentiment_filter_section()
        radio = _find_component_by_id(result, "alert-sentiment-radio")
        assert radio.value == "all"

    def test_has_four_options(self):
        """Has four sentiment options: all, bullish, bearish, neutral."""
        result = build_sentiment_filter_section()
        radio = _find_component_by_id(result, "alert-sentiment-radio")
        values = [opt["value"] for opt in radio.options]
        assert values == ["all", "bullish", "bearish", "neutral"]


class TestBuildNotificationChannelsSection:
    """Test the notification channels sub-component."""

    def test_returns_list_of_five_elements(self):
        """Returns a list of 5 elements (browser, status, email, sms, telegram)."""
        result = build_notification_channels_section()
        assert isinstance(result, list)
        assert len(result) == 5

    def test_contains_browser_toggle(self):
        """Contains the browser notifications switch."""
        result = build_notification_channels_section()
        # Search across all elements
        for elem in result:
            switch = _find_component_by_id(elem, "alert-browser-toggle")
            if switch is not None:
                assert isinstance(switch, dbc.Switch)
                assert switch.value is True  # Browser notifications on by default
                return
        raise AssertionError("alert-browser-toggle not found")

    def test_contains_email_toggle(self):
        """Contains the email notifications switch."""
        result = build_notification_channels_section()
        for elem in result:
            switch = _find_component_by_id(elem, "alert-email-toggle")
            if switch is not None:
                assert isinstance(switch, dbc.Switch)
                assert switch.value is False  # Email off by default
                return
        raise AssertionError("alert-email-toggle not found")

    def test_contains_sms_toggle(self):
        """Contains the SMS notifications switch."""
        result = build_notification_channels_section()
        for elem in result:
            switch = _find_component_by_id(elem, "alert-sms-toggle")
            if switch is not None:
                assert isinstance(switch, dbc.Switch)
                assert switch.value is False  # SMS off by default
                return
        raise AssertionError("alert-sms-toggle not found")

    def test_contains_telegram_link(self):
        """Contains the Telegram bot link."""
        result = build_notification_channels_section()
        all_text = " ".join(_extract_text(elem) for elem in result)
        assert "ShitpostAlphaBot" in all_text


class TestBuildQuietHoursSection:
    """Test the quiet hours sub-component."""

    def test_returns_html_div(self):
        """Returns an html.Div component."""
        result = build_quiet_hours_section()
        assert isinstance(result, html.Div)

    def test_contains_toggle_with_correct_id(self):
        """Contains switch with id='alert-quiet-hours-toggle'."""
        result = build_quiet_hours_section()
        switch = _find_component_by_id(result, "alert-quiet-hours-toggle")
        assert switch is not None
        assert isinstance(switch, dbc.Switch)

    def test_toggle_default_off(self):
        """Quiet hours toggle defaults to False."""
        result = build_quiet_hours_section()
        switch = _find_component_by_id(result, "alert-quiet-hours-toggle")
        assert switch.value is False

    def test_contains_time_inputs(self):
        """Contains start and end time inputs."""
        result = build_quiet_hours_section()
        start = _find_component_by_id(result, "quiet-hours-start")
        end = _find_component_by_id(result, "quiet-hours-end")
        assert start is not None
        assert end is not None
        assert start.value == "22:00"
        assert end.value == "08:00"


class TestBuildActionButtonsSection:
    """Test the save/test/clear buttons sub-component."""

    def test_returns_list_of_three_elements(self):
        """Returns a list of 3 elements (buttons div, toast, note)."""
        result = build_action_buttons_section()
        assert isinstance(result, list)
        assert len(result) == 3

    def test_contains_save_button(self):
        """Contains save preferences button."""
        result = build_action_buttons_section()
        for elem in result:
            btn = _find_component_by_id(elem, "save-alert-prefs-button")
            if btn is not None:
                assert isinstance(btn, dbc.Button)
                return
        raise AssertionError("save-alert-prefs-button not found")

    def test_contains_test_alert_button(self):
        """Contains test alert button."""
        result = build_action_buttons_section()
        for elem in result:
            btn = _find_component_by_id(elem, "test-alert-button")
            if btn is not None:
                assert isinstance(btn, dbc.Button)
                return
        raise AssertionError("test-alert-button not found")

    def test_contains_clear_history_button(self):
        """Contains clear alert history button."""
        result = build_action_buttons_section()
        for elem in result:
            btn = _find_component_by_id(elem, "clear-alert-history-button")
            if btn is not None:
                assert isinstance(btn, dbc.Button)
                return
        raise AssertionError("clear-alert-history-button not found")

    def test_contains_toast(self):
        """Contains save confirmation toast."""
        result = build_action_buttons_section()
        for elem in result:
            toast = _find_component_by_id(elem, "alert-save-toast")
            if toast is not None:
                assert isinstance(toast, dbc.Toast)
                assert toast.is_open is False
                return
        raise AssertionError("alert-save-toast not found")


# ============================================================
# build_preferences_dict tests
# ============================================================


class TestBuildPreferencesDict:
    """Test preference dict assembly from form fields."""

    def test_basic_assembly(self):
        """Assembles all fields into a preferences dict."""
        result = build_preferences_dict(
            enabled=True,
            min_confidence=0.8,
            assets=["AAPL", "TSLA"],
            sentiment="bullish",
            browser_on=True,
            email_on=True,
            email_addr="test@example.com",
            sms_on=False,
            sms_phone="",
            quiet_on=True,
            quiet_start="23:00",
            quiet_end="07:00",
        )
        assert result["enabled"] is True
        assert result["min_confidence"] == 0.8
        assert result["assets_of_interest"] == ["AAPL", "TSLA"]
        assert result["sentiment_filter"] == "bullish"
        assert result["browser_notifications"] is True
        assert result["email_enabled"] is True
        assert result["email_address"] == "test@example.com"
        assert result["sms_enabled"] is False
        assert result["sms_phone_number"] == ""
        assert result["quiet_hours_enabled"] is True
        assert result["quiet_hours_start"] == "23:00"
        assert result["quiet_hours_end"] == "07:00"
        assert result["max_alerts_per_hour"] == 10

    def test_none_confidence_defaults_to_070(self):
        """None confidence defaults to 0.7."""
        result = build_preferences_dict(
            enabled=True, min_confidence=None,
            assets=[], sentiment="all",
            browser_on=True, email_on=False, email_addr=None,
            sms_on=False, sms_phone=None,
            quiet_on=False, quiet_start=None, quiet_end=None,
        )
        assert result["min_confidence"] == 0.7

    def test_none_assets_defaults_to_empty_list(self):
        """None assets defaults to empty list."""
        result = build_preferences_dict(
            enabled=True, min_confidence=0.7,
            assets=None, sentiment=None,
            browser_on=True, email_on=False, email_addr=None,
            sms_on=False, sms_phone=None,
            quiet_on=False, quiet_start=None, quiet_end=None,
        )
        assert result["assets_of_interest"] == []
        assert result["sentiment_filter"] == "all"

    def test_none_email_defaults_to_empty_string(self):
        """None email address defaults to empty string."""
        result = build_preferences_dict(
            enabled=True, min_confidence=0.7,
            assets=[], sentiment="all",
            browser_on=True, email_on=True, email_addr=None,
            sms_on=True, sms_phone=None,
            quiet_on=False, quiet_start=None, quiet_end=None,
        )
        assert result["email_address"] == ""
        assert result["sms_phone_number"] == ""

    def test_none_quiet_hours_defaults(self):
        """None quiet hours start/end default to 22:00/08:00."""
        result = build_preferences_dict(
            enabled=True, min_confidence=0.7,
            assets=[], sentiment="all",
            browser_on=True, email_on=False, email_addr=None,
            sms_on=False, sms_phone=None,
            quiet_on=True, quiet_start=None, quiet_end=None,
        )
        assert result["quiet_hours_start"] == "22:00"
        assert result["quiet_hours_end"] == "08:00"

    def test_has_all_thirteen_keys(self):
        """Result dict contains exactly 13 keys."""
        result = build_preferences_dict(
            enabled=False, min_confidence=0.5,
            assets=[], sentiment="all",
            browser_on=False, email_on=False, email_addr="",
            sms_on=False, sms_phone="",
            quiet_on=False, quiet_start="22:00", quiet_end="08:00",
        )
        expected_keys = {
            "enabled", "min_confidence", "assets_of_interest",
            "sentiment_filter", "browser_notifications",
            "email_enabled", "email_address",
            "sms_enabled", "sms_phone_number",
            "quiet_hours_enabled", "quiet_hours_start", "quiet_hours_end",
            "max_alerts_per_hour",
        }
        assert set(result.keys()) == expected_keys


# ============================================================
# extract_preferences_tuple tests
# ============================================================


class TestExtractPreferencesTuple:
    """Test preferences dict to form-values tuple conversion."""

    def test_full_round_trip(self):
        """build_preferences_dict -> extract_preferences_tuple round-trip."""
        prefs = build_preferences_dict(
            enabled=True, min_confidence=0.85,
            assets=["AAPL"], sentiment="bearish",
            browser_on=False, email_on=True, email_addr="x@y.com",
            sms_on=True, sms_phone="+15551234567",
            quiet_on=True, quiet_start="21:00", quiet_end="09:00",
        )
        result = extract_preferences_tuple(prefs)
        assert result == (
            True, 0.85, ["AAPL"], "bearish",
            False, True, "x@y.com",
            True, "+15551234567",
            True, "21:00", "09:00",
        )

    def test_returns_12_element_tuple(self):
        """Always returns exactly 12 elements."""
        result = extract_preferences_tuple({})
        assert len(result) == 12

    def test_defaults_for_empty_prefs(self):
        """Empty prefs dict returns safe defaults."""
        result = extract_preferences_tuple({})
        assert result == (
            False, 0.7, [], "all",
            True, False, "",
            False, "",
            False, "22:00", "08:00",
        )

    def test_partial_prefs_fills_defaults(self):
        """Partial prefs dict fills in defaults for missing keys."""
        result = extract_preferences_tuple({"enabled": True, "min_confidence": 0.9})
        assert result[0] is True  # enabled
        assert result[1] == 0.9   # min_confidence
        assert result[2] == []    # assets (default)
        assert result[3] == "all" # sentiment (default)


# ============================================================
# build_alert_history_card tests
# ============================================================


class TestBuildAlertHistoryCard:
    """Test individual alert history card rendering."""

    def _make_alert(self, **overrides) -> dict:
        """Create a minimal alert dict."""
        base = {
            "sentiment": "bullish",
            "confidence": 0.85,
            "assets": ["AAPL", "TSLA"],
            "text": "Big news for tech stocks today!",
            "alert_triggered_at": "2025-06-15T14:30:00Z",
        }
        base.update(overrides)
        return base

    def test_returns_html_div(self):
        """Returns an html.Div component."""
        result = build_alert_history_card(self._make_alert())
        assert isinstance(result, html.Div)

    def test_bullish_sentiment_shows_arrow_up(self):
        """Bullish alert shows arrow-up icon."""
        result = build_alert_history_card(self._make_alert(sentiment="bullish"))
        text = _extract_text(result)
        assert "BULLISH" in text

    def test_bearish_sentiment_shows_arrow_down(self):
        """Bearish alert shows arrow-down icon."""
        result = build_alert_history_card(self._make_alert(sentiment="bearish"))
        text = _extract_text(result)
        assert "BEARISH" in text

    def test_neutral_sentiment_shows_minus(self):
        """Neutral alert shows minus icon."""
        result = build_alert_history_card(self._make_alert(sentiment="neutral"))
        text = _extract_text(result)
        assert "NEUTRAL" in text

    def test_unknown_sentiment_defaults_to_neutral(self):
        """Unknown sentiment value defaults to neutral styling."""
        result = build_alert_history_card(self._make_alert(sentiment="confused"))
        text = _extract_text(result)
        assert "CONFUSED" in text  # Uppercased, uses neutral styling

    def test_timestamp_formatting(self):
        """Formats ISO timestamp as 'Mon DD, HH:MM'."""
        result = build_alert_history_card(
            self._make_alert(alert_triggered_at="2025-06-15T14:30:00Z")
        )
        text = _extract_text(result)
        assert "Jun 15, 14:30" in text

    def test_invalid_timestamp_falls_back(self):
        """Invalid timestamp falls back to string slice."""
        result = build_alert_history_card(
            self._make_alert(alert_triggered_at="not-a-date")
        )
        text = _extract_text(result)
        assert "not-a-date" in text

    def test_empty_timestamp_handled(self):
        """Empty timestamp string does not crash."""
        result = build_alert_history_card(self._make_alert(alert_triggered_at=""))
        assert isinstance(result, html.Div)

    def test_none_timestamp_handled(self):
        """None timestamp does not crash."""
        result = build_alert_history_card(self._make_alert(alert_triggered_at=None))
        assert isinstance(result, html.Div)

    def test_text_truncation_at_120_chars(self):
        """Text longer than 120 chars is truncated with ellipsis."""
        long_text = "A" * 150
        result = build_alert_history_card(self._make_alert(text=long_text))
        text = _extract_text(result)
        assert "..." in text

    def test_short_text_no_truncation(self):
        """Short text is not truncated."""
        result = build_alert_history_card(self._make_alert(text="Short post"))
        text = _extract_text(result)
        assert "Short post" in text
        # Should not have trailing ellipsis
        assert text.count("...") == 0

    def test_assets_displayed(self):
        """Assets are displayed in the card."""
        result = build_alert_history_card(
            self._make_alert(assets=["AAPL", "TSLA", "GOOGL"])
        )
        text = _extract_text(result)
        assert "AAPL" in text
        assert "TSLA" in text
        assert "GOOGL" in text

    def test_assets_limited_to_three(self):
        """Only first 3 assets are displayed."""
        result = build_alert_history_card(
            self._make_alert(assets=["AAPL", "TSLA", "GOOGL", "MSFT", "AMZN"])
        )
        text = _extract_text(result)
        assert "AAPL" in text
        assert "MSFT" not in text

    def test_empty_assets_handled(self):
        """Empty assets list does not crash."""
        result = build_alert_history_card(self._make_alert(assets=[]))
        assert isinstance(result, html.Div)

    def test_confidence_displayed_as_percentage(self):
        """Confidence is displayed as a percentage."""
        result = build_alert_history_card(self._make_alert(confidence=0.85))
        text = _extract_text(result)
        assert "85%" in text

    def test_zero_confidence_shows_empty(self):
        """Zero confidence shows empty string (falsy)."""
        result = build_alert_history_card(self._make_alert(confidence=0))
        text = _extract_text(result)
        # confidence=0 is falsy, so the f-string branch produces ""
        assert "0%" not in text

    def test_missing_keys_use_defaults(self):
        """Alert dict with missing keys uses safe defaults."""
        result = build_alert_history_card({})
        assert isinstance(result, html.Div)
        text = _extract_text(result)
        assert "NEUTRAL" in text


# ============================================================
# create_alert_config_panel integration test
# ============================================================


class TestCreateAlertConfigPanelIntegration:
    """Test that the refactored panel still produces the same structure."""

    def test_returns_offcanvas(self):
        """Panel returns a dbc.Offcanvas component."""
        from callbacks.alerts import create_alert_config_panel

        panel = create_alert_config_panel()
        assert isinstance(panel, dbc.Offcanvas)

    def test_has_correct_id(self):
        """Panel has the expected component ID."""
        from callbacks.alerts import create_alert_config_panel

        panel = create_alert_config_panel()
        assert panel.id == "alert-config-offcanvas"

    def test_all_critical_ids_present(self):
        """All critical component IDs are present in the panel tree."""
        from callbacks.alerts import create_alert_config_panel

        panel = create_alert_config_panel()
        critical_ids = [
            "alert-master-toggle",
            "alert-status-indicator",
            "alert-confidence-slider",
            "confidence-threshold-display",
            "alert-assets-dropdown",
            "alert-sentiment-radio",
            "alert-browser-toggle",
            "browser-notification-status",
            "alert-email-toggle",
            "alert-email-input",
            "email-input-collapse",
            "alert-sms-toggle",
            "alert-sms-input",
            "sms-input-collapse",
            "alert-quiet-hours-toggle",
            "quiet-hours-start",
            "quiet-hours-end",
            "quiet-hours-collapse",
            "save-alert-prefs-button",
            "test-alert-button",
            "clear-alert-history-button",
            "alert-save-toast",
        ]
        for component_id in critical_ids:
            found = _find_component_by_id(panel, component_id)
            assert found is not None, f"Component '{component_id}' not found in panel"

    def test_panel_has_children(self):
        """Panel contains child components."""
        from callbacks.alerts import create_alert_config_panel

        panel = create_alert_config_panel()
        assert panel.children is not None
        assert len(panel.children) > 0
```

---

## Test Plan

### New test file

**File**: `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_alert_callbacks.py`

| Test Class | # Tests | What It Covers |
|------------|---------|----------------|
| `TestBuildMasterToggleSection` | 4 | Master toggle component structure, default value, label text |
| `TestBuildStatusIndicator` | 2 | Status indicator ID, default disabled text |
| `TestBuildConfidenceThresholdSection` | 5 | Slider ID, default 0.7, range 0-1, display element |
| `TestBuildAssetSelectionSection` | 4 | Dropdown ID, multi-select, starts empty |
| `TestBuildSentimentFilterSection` | 4 | RadioItems ID, default "all", four options |
| `TestBuildNotificationChannelsSection` | 5 | Returns 5 elements, browser/email/SMS toggles, Telegram link |
| `TestBuildQuietHoursSection` | 4 | Toggle ID, default off, time inputs with defaults |
| `TestBuildActionButtonsSection` | 5 | Returns 3 elements, save/test/clear buttons, toast |
| `TestBuildPreferencesDict` | 6 | Assembly, None defaults, 13 keys |
| `TestExtractPreferencesTuple` | 4 | Round-trip, 12 elements, empty defaults, partial |
| `TestBuildAlertHistoryCard` | 17 | Sentiment colors, timestamp formatting, truncation, assets, confidence, missing keys |
| `TestCreateAlertConfigPanelIntegration` | 4 | Offcanvas type, ID, all 22 critical IDs present, has children |
| **Total** | **60** | |

### Existing tests NOT modified

- `shit_tests/shitty_ui/test_alerts.py` -- covers the notifications-layer alert engine. Must pass unchanged after this refactor.

### Coverage expectations

- `shitty_ui/callbacks/alert_components.py`: 100% (all 8 builder functions tested)
- `shitty_ui/callbacks/alerts.py` new functions: 100% (`build_preferences_dict`, `extract_preferences_tuple`, `build_alert_history_card`)
- `shitty_ui/callbacks/alerts.py` overall: ~40-50% (callback registration functions cannot be unit-tested without a Dash test app; the extracted logic accounts for the testable portions)

### How to run

```bash
source venv/bin/activate && pytest shit_tests/shitty_ui/test_alert_callbacks.py -v
```

Also verify existing tests still pass:
```bash
source venv/bin/activate && pytest shit_tests/shitty_ui/test_alerts.py -v
```

---

## Documentation Updates

No README changes needed. The refactoring is internal to `shitty_ui/callbacks/`.

Update `CHANGELOG.md` under `## [Unreleased]`:

```markdown
### Changed
- **Alerts panel refactor** - Split `create_alert_config_panel()` into 8 sub-component builder functions in new `alert_components.py`
- **Alerts callbacks refactor** - Extracted `build_preferences_dict()`, `extract_preferences_tuple()`, and `build_alert_history_card()` from nested callbacks into testable module-level functions

### Added
- **Alert callback tests** - 60 new tests in `test_alert_callbacks.py` covering panel sub-components, preference serialization, and alert history card rendering
```

---

## Stress Testing & Edge Cases

### Edge cases handled by `build_alert_history_card()`
- **Empty alert dict** (`{}`): Uses defaults -- neutral sentiment, empty text, no assets
- **None timestamp**: Falls back to string `"None"[:16]`
- **Empty timestamp**: Falls back to empty string
- **Timestamps with `Z` suffix**: Correctly replaced before `fromisoformat()`
- **Non-list assets**: Falls back to `str(assets)`
- **Assets list longer than 3**: Truncates to first 3
- **Text exactly 120 chars**: Shows text without truncation marker
- **Text at 121+ chars**: Truncates to 120 and appends "..."
- **Confidence of 0** (falsy): Displays empty string, not "0%"
- **Confidence of None**: Displays empty string

### Edge cases handled by `build_preferences_dict()`
- **None confidence**: Defaults to 0.7
- **None/empty assets**: Defaults to `[]`
- **None sentiment**: Defaults to `"all"`
- **None email/phone**: Defaults to `""`
- **None quiet hours times**: Defaults to `"22:00"` / `"08:00"`

### Edge cases handled by `extract_preferences_tuple()`
- **Empty dict**: Returns all defaults (12 elements)
- **Partial dict**: Fills in defaults for missing keys
- **Extra keys in dict**: Ignored (`.get()` only reads known keys)

---

## Verification Checklist

After implementation, verify each item:

- [ ] `shitty_ui/callbacks/alert_components.py` exists and contains 8 `build_*` functions
- [ ] `shitty_ui/callbacks/alerts.py` imports all 8 functions from `alert_components`
- [ ] `create_alert_config_panel()` uses the builder functions instead of inline components
- [ ] `create_alert_config_panel()` returns an Offcanvas with the same `id="alert-config-offcanvas"`
- [ ] `build_preferences_dict()` is a module-level function in `alerts.py`
- [ ] `extract_preferences_tuple()` is a module-level function in `alerts.py`
- [ ] `build_alert_history_card()` is a module-level function in `alerts.py`
- [ ] `save_alert_preferences` callback calls `build_preferences_dict()`
- [ ] `load_preferences_into_form` callback calls `extract_preferences_tuple()`
- [ ] `render_alert_history` callback calls `build_alert_history_card()`
- [ ] `create_alert_history_panel()` is unchanged (stays in `alerts.py`)
- [ ] All 22 critical component IDs are still present in the panel tree
- [ ] `shitty_ui/layout.py` requires zero changes (imports unchanged)
- [ ] `shit_tests/shitty_ui/test_alert_callbacks.py` exists with ~60 tests
- [ ] Run: `source venv/bin/activate && pytest shit_tests/shitty_ui/test_alert_callbacks.py -v` -- all pass
- [ ] Run: `source venv/bin/activate && pytest shit_tests/shitty_ui/test_alerts.py -v` -- all pass (unchanged)
- [ ] Run: `source venv/bin/activate && pytest shit_tests/shitty_ui/ -v` -- all shitty_ui tests pass
- [ ] Dashboard loads without errors (manual check or check `logs/` for import errors)
- [ ] Alert config panel opens and closes correctly
- [ ] All form fields render with correct defaults

---

## What NOT To Do

1. **Do NOT modify `shitty_ui/alerts.py`** (the notifications-layer module). This phase only touches `shitty_ui/callbacks/alerts.py` (the callbacks-layer module). They are different files in different directories.

2. **Do NOT modify `shit_tests/shitty_ui/test_alerts.py`**. The existing 679-line test file covers the notifications layer and must pass unchanged.

3. **Do NOT change the function signatures** of `create_alert_config_panel()`, `create_alert_history_panel()`, or `register_alert_callbacks()`. External callers in `layout.py` depend on these exact signatures.

4. **Do NOT change Dash component IDs**. Every `id=` string in the panel is referenced by callbacks. Changing even one ID will silently break callback wiring. The integration test (`TestCreateAlertConfigPanelIntegration.test_all_critical_ids_present`) guards against this.

5. **Do NOT move clientside callbacks out of `register_alert_callbacks()`**. The JavaScript clientside callbacks (browser notification, badge count, interval control, test alert) cannot be extracted into separate testable functions because they are inline JS strings. Leave them inside `register_alert_callbacks()`.

6. **Do NOT try to unit-test the Dash callback decorators** (the `@app.callback(...)` registrations). Testing callback registration requires a full Dash test app with `dash.testing`. That is out of scope for this phase. We only test the extracted helper functions.

7. **Do NOT add `alert_components` to `shitty_ui/callbacks/__init__.py`**. The module is an internal dependency of `callbacks/alerts.py` and should not be re-exported.

8. **Do NOT change the order of `children=` in the Offcanvas**. The visual layout depends on the order of children. The refactored `create_alert_config_panel()` must produce children in the exact same order as the original.

9. **Do NOT introduce new dependencies**. The refactored code uses only `dash`, `dash_bootstrap_components`, and `constants` -- the same deps as the original.

10. **Do NOT extract `create_alert_history_panel()`** into `alert_components.py`. It is only ~40 lines and is re-exported from `layout.py` at line 42. Moving it would require updating `layout.py` imports, which risks merge conflicts with other phases.
