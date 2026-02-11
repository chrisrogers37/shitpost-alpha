# Alerting System Specification [PARTIALLY COMPLETE]

> **STATUS: PARTIALLY COMPLETE** - Telegram bot is live (webhook mode, multi-tenant subscriptions). Email (SMTP) and SMS (Twilio) channels are coded but not configured in production. Browser notifications work client-side.

## Implementation Context for Engineering Team

### Current State (as of 2026-01-29)

The database already has a **`subscribers` table** for SMS alert management:

```sql
subscribers (
  id, created_at, updated_at,
  phone_number (UNIQUE),    -- SMS target
  name, email,              -- Contact info
  is_active (DEFAULT=True), -- Active subscription
  confidence_threshold (DEFAULT=0.7),  -- Min confidence for alerts
  alert_frequency ('all', 'high_confidence', 'daily_summary'),
  last_alert_sent,          -- Rate limiting
  alerts_sent_today         -- Daily limit tracking
)
```

**This table is ready to use** - no schema changes needed for SMS alerts.

### Existing Infrastructure

1. **Twilio Integration** - The project uses Twilio for SMS (see `shit/config/`)
2. **Email Config** - SMTP settings available via environment variables
3. **Browser localStorage** - No backend needed for browser push preferences
4. **dcc.Interval** - Already used for 5-minute refresh; can add separate alert interval

### Database Tables for Alert Logic

```sql
-- New predictions to check
predictions (analysis_status='completed', confidence >= threshold)

-- Recent signals for alert checking
SELECT * FROM predictions p
JOIN truth_social_shitposts tss ON p.shitpost_id = tss.shitpost_id
WHERE p.analysis_status = 'completed'
  AND p.confidence >= :threshold
  AND tss.timestamp > :last_check_time
ORDER BY tss.timestamp DESC
```

### Recommended Implementation Approach

1. **Start with browser notifications** - Easiest to implement, no backend changes
2. **Use clientside callback** - Store preferences in localStorage via JS
3. **Add alert checker interval** - Separate from refresh interval (e.g., 2 min)
4. **Add SMS later** - Use existing `subscribers` table
5. **Add email last** - Requires SMTP/SendGrid setup

### Security Notes

- SMS phone numbers are stored in database (already exists)
- Email addresses require user verification before alerts
- Browser push requires explicit permission
- No PII stored in localStorage (just preferences)

---

## Overview

This document specifies the alerting and notification system for the Shitpost Alpha dashboard. The system monitors for new high-confidence predictions and notifies users via browser push notifications, email, and SMS. Alert preferences are stored in browser localStorage so no user accounts are required.

**Estimated Effort**: 4-5 days
**Priority**: P2 (Nice to Have)
**Prerequisites**: ✅ Dashboard Enhancements (02) - DONE; Data Layer Expansion (07) - Partial

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Alert Flow](#alert-flow)
3. [Task 1: Alert Preferences Store (localStorage)](#task-1-alert-preferences-store-localstorage)
4. [Task 2: Alert Configuration UI Panel](#task-2-alert-configuration-ui-panel)
5. [Task 3: Backend Alert Checking Logic](#task-3-backend-alert-checking-logic)
6. [Task 4: Browser Push Notifications](#task-4-browser-push-notifications)
7. [Task 5: Email Notifications (SMTP / SendGrid)](#task-5-email-notifications-smtp--sendgrid)
8. [Task 6: SMS Alerts via Twilio](#task-6-sms-alerts-via-twilio)
9. [Task 7: Alert History Panel](#task-7-alert-history-panel)
10. [Security Considerations](#security-considerations)
11. [Test Specifications](#test-specifications)
12. [Implementation Checklist](#implementation-checklist)
13. [Definition of Done](#definition-of-done)

---

## Architecture Overview

```
                        +---------------------+
                        |    Dashboard UI     |
                        |  (Plotly Dash App)  |
                        +----------+----------+
                                   |
                    +--------------+--------------+
                    |              |              |
             +------+------+ +----+----+ +------+------+
             | Browser Push| | Alert   | | Alert       |
             | Notification| | Config  | | History     |
             | (JS/SW)     | | Panel   | | Panel       |
             +------+------+ +----+----+ +------+------+
                    |              |              |
                    +--------------+--------------+
                                   |
                        +----------+----------+
                        |  Alert Preferences  |
                        |  (localStorage)     |
                        +----------+----------+
                                   |
                        +----------+----------+
                        |  Alert Checker      |
                        |  (dcc.Interval)     |
                        +----------+----------+
                                   |
              +--------------------+--------------------+
              |                    |                    |
     +--------+--------+ +--------+--------+ +--------+--------+
     | Browser Push    | | Email (SMTP/   | | SMS (Twilio)    |
     | Notification API| | SendGrid)      | |                 |
     +-----------------+ +-----------------+ +-----------------+
              |                    |                    |
              +--------------------+--------------------+
                                   |
                        +----------+----------+
                        |   PostgreSQL DB     |
                        |   (predictions,     |
                        |    truth_social_    |
                        |    shitposts)       |
                        +---------------------+
```

### File Structure (New Files)

```
shitty_ui/
├── app.py              # Updated: register alert callbacks
├── layout.py           # Updated: add alert panel to layout
├── data.py             # Updated: add alert query functions
├── alerts.py           # NEW: alert checking and dispatch logic
└── assets/
    └── service-worker.js  # NEW: browser push notification service worker

shit/config/
└── shitpost_settings.py   # Updated: add email settings (SMTP/SendGrid)
```

### Color Palette Reference

All UI components use this palette. Import from `layout.py`:

```python
COLORS = {
    "primary": "#1e293b",      # Slate 800 - main background
    "secondary": "#334155",    # Slate 700 - cards
    "accent": "#3b82f6",       # Blue 500 - highlights
    "success": "#10b981",      # Emerald 500 - bullish/correct
    "danger": "#ef4444",       # Red 500 - bearish/incorrect
    "warning": "#f59e0b",      # Amber 500 - pending
    "text": "#f1f5f9",         # Slate 100 - primary text
    "text_muted": "#94a3b8",   # Slate 400 - secondary text
    "border": "#475569",       # Slate 600 - borders
}
```

---

## Alert Flow

This is the end-to-end flow from database poll to user notification.

### Step-by-Step

1. **Dashboard polls database** via `dcc.Interval` every 2 minutes (configurable).
2. **Alert checker callback** fires, calling `check_for_new_alerts()` in `alerts.py`.
3. `check_for_new_alerts()` queries `predictions` for rows where `created_at > last_check_timestamp` and `analysis_status = 'completed'`.
4. For each new prediction, compare against the user's stored alert preferences (passed from localStorage via `dcc.Store`):
   - Does `confidence >= user's minimum confidence threshold`?
   - Does any asset in `assets` match the user's `assets_of_interest` list (or is the list empty, meaning "all assets")?
   - Does the sentiment (derived from `market_impact`) match the user's `sentiment_filter` (or "all")?
5. If a match is found:
   - Add the prediction to the `alert_history` store.
   - Trigger a browser push notification via `clientside_callback`.
   - If the user has configured email, dispatch via SMTP/SendGrid (server-side).
   - If the user has configured SMS, dispatch via Twilio (server-side).
6. Update `last_check_timestamp` in the store.

### Data Flow Diagram

```
dcc.Interval (2 min)
    |
    v
[Callback: check_alerts]
    |
    +---> Input: alert-check-interval.n_intervals
    +---> State: alert-preferences-store.data    (from localStorage)
    +---> State: last-alert-check-store.data     (timestamp)
    |
    v
alerts.py :: check_for_new_alerts(preferences, last_check)
    |
    +---> data.py :: get_new_predictions_since(last_check)
    +---> alerts.py :: filter_by_preferences(predictions, preferences)
    +---> alerts.py :: dispatch_notifications(matched, preferences)
    |
    v
    Output: alert-notification-store.data        (triggers JS notification)
    Output: alert-history-store.data             (append new alerts)
    Output: last-alert-check-store.data          (updated timestamp)
```

---

## Task 1: Alert Preferences Store (localStorage)

### Purpose

Store user alert preferences in the browser's localStorage so they persist across page reloads. No server-side accounts needed.

### Implementation

#### Step 1: Define the Preferences Schema

The preferences object stored in localStorage has this shape:

```python
# Default alert preferences - used when no localStorage data exists
DEFAULT_ALERT_PREFERENCES = {
    "enabled": False,                    # Master toggle
    "min_confidence": 0.7,              # Minimum confidence threshold (0.0 - 1.0)
    "assets_of_interest": [],           # Empty list = all assets. e.g. ["AAPL", "TSLA"]
    "sentiment_filter": "all",          # "all", "bullish", "bearish", "neutral"
    "browser_notifications": True,      # Enable browser push
    "email_enabled": False,             # Enable email alerts
    "email_address": "",                # User's email address
    "sms_enabled": False,               # Enable SMS alerts
    "sms_phone_number": "",             # User's phone number (E.164 format)
    "quiet_hours_enabled": False,       # Suppress alerts during quiet hours
    "quiet_hours_start": "22:00",       # Quiet hours start (local time)
    "quiet_hours_end": "08:00",         # Quiet hours end (local time)
    "max_alerts_per_hour": 10,          # Rate limit
}
```

#### Step 2: Add Stores to Layout

Add these `dcc.Store` components inside `create_app()` in `layout.py`, next to the existing `dcc.Store(id="selected-asset")`:

```python
# In create_app(), inside app.layout = html.Div([...]):

# Alert system stores
dcc.Store(
    id="alert-preferences-store",
    storage_type="local",       # Persists in localStorage
    data=DEFAULT_ALERT_PREFERENCES,
),
dcc.Store(
    id="last-alert-check-store",
    storage_type="local",       # Persists across reloads
    data=None,                  # ISO timestamp string, initially None
),
dcc.Store(
    id="alert-history-store",
    storage_type="local",       # Persists across reloads
    data=[],                    # List of alert history entries
),
dcc.Store(
    id="alert-notification-store",
    storage_type="memory",      # Ephemeral - triggers JS notification
    data=None,                  # Set to alert data to trigger notification
),

# Alert check interval (separate from dashboard refresh)
dcc.Interval(
    id="alert-check-interval",
    interval=2 * 60 * 1000,    # 2 minutes
    n_intervals=0,
    disabled=True,              # Disabled until alerts are enabled
),
```

#### Step 3: Sync localStorage on Page Load

Use a `clientside_callback` to load preferences from localStorage when the page loads. Dash `dcc.Store` with `storage_type="local"` handles this automatically -- when the page loads, the store reads its value from `localStorage`. If the key does not exist, it uses the `data` default.

However, we need a callback to enable/disable the alert interval based on the stored preference:

```python
# In register_callbacks(app):

app.clientside_callback(
    """
    function(prefs) {
        // Enable or disable the alert check interval based on preferences
        if (prefs && prefs.enabled) {
            return false;  // disabled=false means interval IS running
        }
        return true;  // disabled=true means interval is NOT running
    }
    """,
    Output("alert-check-interval", "disabled"),
    Input("alert-preferences-store", "data"),
)
```

### Key Points

- `dcc.Store` with `storage_type="local"` automatically persists to `window.localStorage`.
- The key name in localStorage is the component `id` (e.g., `alert-preferences-store`).
- The data is automatically JSON-serialized/deserialized by Dash.
- No manual `localStorage.getItem()` or `localStorage.setItem()` calls needed for basic storage.

---

## Task 2: Alert Configuration UI Panel

### Purpose

A collapsible panel in the dashboard sidebar where users configure their alert preferences. The panel uses `dbc.Offcanvas` (slide-out drawer) triggered by a bell icon button in the header.

### Implementation

#### Step 1: Add Bell Icon Button to Header

Update `create_header()` in `layout.py`:

```python
def create_header():
    """Create the dashboard header with alert bell."""
    return html.Div([
        html.Div([
            html.H1([
                html.Span("Shitpost Alpha", style={"color": COLORS["accent"]}),
            ], style={"fontSize": "2rem", "fontWeight": "bold", "margin": 0}),
            html.P(
                "Trump Tweet Prediction Performance Dashboard",
                style={"color": COLORS["text_muted"], "margin": 0, "fontSize": "0.9rem"}
            ),
        ], style={"flex": 1}),

        # Right side: alert bell + refresh indicator
        html.Div([
            # Alert bell button
            dbc.Button(
                [
                    html.I(className="fas fa-bell", id="alert-bell-icon"),
                    # Badge showing number of unread alerts
                    html.Span(
                        id="alert-badge",
                        className="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger",
                        style={"fontSize": "0.6rem", "display": "none"},
                    ),
                ],
                id="open-alert-config-button",
                color="link",
                className="position-relative me-3",
                style={
                    "color": COLORS["text_muted"],
                    "fontSize": "1.3rem",
                    "padding": "5px 10px",
                    "border": f"1px solid {COLORS['border']}",
                    "borderRadius": "8px",
                },
            ),
            html.Span(
                "Auto-refresh: 5 min",
                style={"color": COLORS["text_muted"], "fontSize": "0.8rem"},
            ),
        ], style={"display": "flex", "alignItems": "center"}),
    ], style={
        "display": "flex",
        "justifyContent": "space-between",
        "alignItems": "center",
        "padding": "20px",
        "borderBottom": f"1px solid {COLORS['border']}",
        "backgroundColor": COLORS["secondary"],
    })
```

#### Step 2: Create the Alert Configuration Offcanvas

Add this function to `layout.py`:

```python
def create_alert_config_panel():
    """
    Create the alert configuration slide-out panel.

    Returns a dbc.Offcanvas component that slides in from the right
    when the user clicks the bell icon in the header.
    """
    return dbc.Offcanvas(
        id="alert-config-offcanvas",
        title="Alert Configuration",
        placement="end",           # Slide in from the right
        is_open=False,
        backdrop=True,
        scrollable=True,
        style={
            "backgroundColor": COLORS["primary"],
            "color": COLORS["text"],
            "width": "400px",
        },
        children=[
            # Master toggle
            html.Div([
                html.Div([
                    html.I(
                        className="fas fa-power-off me-2",
                        style={"color": COLORS["accent"]},
                    ),
                    html.Span(
                        "Enable Alerts",
                        style={"fontWeight": "bold", "fontSize": "1rem"},
                    ),
                ], style={"display": "flex", "alignItems": "center"}),
                dbc.Switch(
                    id="alert-master-toggle",
                    value=False,
                    className="ms-auto",
                    style={"transform": "scale(1.3)"},
                ),
            ], style={
                "display": "flex",
                "justifyContent": "space-between",
                "alignItems": "center",
                "padding": "15px",
                "backgroundColor": COLORS["secondary"],
                "borderRadius": "8px",
                "marginBottom": "20px",
            }),

            # Alert status indicator
            html.Div(
                id="alert-status-indicator",
                children=[
                    html.I(className="fas fa-circle me-2", style={"color": COLORS["danger"], "fontSize": "0.6rem"}),
                    html.Span("Alerts disabled", style={"color": COLORS["text_muted"], "fontSize": "0.85rem"}),
                ],
                style={"marginBottom": "20px", "textAlign": "center"},
            ),

            html.Hr(style={"borderColor": COLORS["border"]}),

            # --- Filter Settings ---
            html.H6([
                html.I(className="fas fa-filter me-2"),
                "Filter Settings",
            ], style={"color": COLORS["accent"], "marginBottom": "15px"}),

            # Minimum confidence threshold
            html.Div([
                html.Label(
                    "Minimum Confidence",
                    style={"color": COLORS["text"], "fontWeight": "500", "fontSize": "0.9rem"},
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
                        0.0: {"label": "0%", "style": {"color": COLORS["text_muted"]}},
                        0.5: {"label": "50%", "style": {"color": COLORS["text_muted"]}},
                        0.7: {"label": "70%", "style": {"color": COLORS["warning"]}},
                        1.0: {"label": "100%", "style": {"color": COLORS["text_muted"]}},
                    },
                    tooltip={"placement": "bottom", "always_visible": False},
                ),
                html.Small(
                    "Only alert when prediction confidence is at or above this level.",
                    style={"color": COLORS["text_muted"]},
                ),
            ], style={"marginBottom": "20px"}),

            # Assets of interest
            html.Div([
                html.Label(
                    "Assets of Interest",
                    style={"color": COLORS["text"], "fontWeight": "500", "fontSize": "0.9rem"},
                ),
                dcc.Dropdown(
                    id="alert-assets-dropdown",
                    options=[],        # Populated by callback from DB
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
            ], style={"marginBottom": "20px"}),

            # Sentiment filter
            html.Div([
                html.Label(
                    "Sentiment Filter",
                    style={"color": COLORS["text"], "fontWeight": "500", "fontSize": "0.9rem"},
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
            ], style={"marginBottom": "20px"}),

            html.Hr(style={"borderColor": COLORS["border"]}),

            # --- Notification Channels ---
            html.H6([
                html.I(className="fas fa-paper-plane me-2"),
                "Notification Channels",
            ], style={"color": COLORS["accent"], "marginBottom": "15px"}),

            # Browser notifications toggle
            html.Div([
                html.Div([
                    html.I(className="fas fa-globe me-2", style={"color": COLORS["text_muted"]}),
                    html.Span("Browser Notifications", style={"fontSize": "0.9rem"}),
                ], style={"display": "flex", "alignItems": "center"}),
                dbc.Switch(
                    id="alert-browser-toggle",
                    value=True,
                    className="ms-auto",
                ),
            ], style={
                "display": "flex",
                "justifyContent": "space-between",
                "alignItems": "center",
                "padding": "10px 15px",
                "backgroundColor": COLORS["secondary"],
                "borderRadius": "8px",
                "marginBottom": "10px",
            }),

            # Browser notification permission status
            html.Div(
                id="browser-notification-status",
                style={"marginBottom": "15px", "fontSize": "0.8rem"},
            ),

            # Email notifications
            html.Div([
                html.Div([
                    html.Div([
                        html.I(className="fas fa-envelope me-2", style={"color": COLORS["text_muted"]}),
                        html.Span("Email Notifications", style={"fontSize": "0.9rem"}),
                    ], style={"display": "flex", "alignItems": "center"}),
                    dbc.Switch(
                        id="alert-email-toggle",
                        value=False,
                        className="ms-auto",
                    ),
                ], style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                }),
                # Email input (shown only when email is enabled)
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
            ], style={
                "padding": "10px 15px",
                "backgroundColor": COLORS["secondary"],
                "borderRadius": "8px",
                "marginBottom": "10px",
            }),

            # SMS notifications
            html.Div([
                html.Div([
                    html.Div([
                        html.I(className="fas fa-sms me-2", style={"color": COLORS["text_muted"]}),
                        html.Span("SMS Notifications", style={"fontSize": "0.9rem"}),
                    ], style={"display": "flex", "alignItems": "center"}),
                    dbc.Switch(
                        id="alert-sms-toggle",
                        value=False,
                        className="ms-auto",
                    ),
                ], style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                }),
                # Phone input (shown only when SMS is enabled)
                dbc.Collapse(
                    html.Div([
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
                    ]),
                    id="sms-input-collapse",
                    is_open=False,
                ),
            ], style={
                "padding": "10px 15px",
                "backgroundColor": COLORS["secondary"],
                "borderRadius": "8px",
                "marginBottom": "10px",
            }),

            html.Hr(style={"borderColor": COLORS["border"]}),

            # --- Quiet Hours ---
            html.H6([
                html.I(className="fas fa-moon me-2"),
                "Quiet Hours",
            ], style={"color": COLORS["accent"], "marginBottom": "15px"}),

            html.Div([
                html.Div([
                    html.Span("Enable Quiet Hours", style={"fontSize": "0.9rem"}),
                    dbc.Switch(
                        id="alert-quiet-hours-toggle",
                        value=False,
                        className="ms-auto",
                    ),
                ], style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                    "marginBottom": "10px",
                }),
                dbc.Collapse(
                    dbc.Row([
                        dbc.Col([
                            html.Label("Start", style={"fontSize": "0.85rem", "color": COLORS["text_muted"]}),
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
                        ], width=6),
                        dbc.Col([
                            html.Label("End", style={"fontSize": "0.85rem", "color": COLORS["text_muted"]}),
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
                        ], width=6),
                    ]),
                    id="quiet-hours-collapse",
                    is_open=False,
                ),
            ], style={
                "padding": "10px 15px",
                "backgroundColor": COLORS["secondary"],
                "borderRadius": "8px",
                "marginBottom": "20px",
            }),

            html.Hr(style={"borderColor": COLORS["border"]}),

            # --- Save / Test Buttons ---
            html.Div([
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
            ]),

            # Save confirmation toast
            dbc.Toast(
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
            ),
        ],
    )
```

#### Step 3: Add the Offcanvas to the App Layout

In `create_app()` within `layout.py`, add the offcanvas inside the top-level `html.Div`:

```python
app.layout = html.Div([
    # Existing stores and intervals...
    dcc.Interval(id="refresh-interval", interval=5*60*1000, n_intervals=0),
    dcc.Store(id="selected-asset", data=None),

    # NEW: Alert system stores
    dcc.Store(id="alert-preferences-store", storage_type="local", data=DEFAULT_ALERT_PREFERENCES),
    dcc.Store(id="last-alert-check-store", storage_type="local", data=None),
    dcc.Store(id="alert-history-store", storage_type="local", data=[]),
    dcc.Store(id="alert-notification-store", storage_type="memory", data=None),
    dcc.Interval(id="alert-check-interval", interval=2*60*1000, n_intervals=0, disabled=True),

    # NEW: Alert configuration panel (offcanvas)
    create_alert_config_panel(),

    # Existing layout...
    create_header(),
    html.Div([...]),  # Main content
])
```

#### Step 4: Register Panel Callbacks

Add these callbacks inside `register_callbacks(app)` in `layout.py`:

```python
def register_alert_callbacks(app: Dash):
    """Register all alert-related callbacks. Called from register_callbacks()."""

    # --- Open/Close the alert config offcanvas ---
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

    # --- Show/hide email input ---
    @app.callback(
        Output("email-input-collapse", "is_open"),
        [Input("alert-email-toggle", "value")],
    )
    def toggle_email_input(email_enabled: bool) -> bool:
        """Show email input when email alerts are enabled."""
        return bool(email_enabled)

    # --- Show/hide SMS input ---
    @app.callback(
        Output("sms-input-collapse", "is_open"),
        [Input("alert-sms-toggle", "value")],
    )
    def toggle_sms_input(sms_enabled: bool) -> bool:
        """Show SMS input when SMS alerts are enabled."""
        return bool(sms_enabled)

    # --- Show/hide quiet hours inputs ---
    @app.callback(
        Output("quiet-hours-collapse", "is_open"),
        [Input("alert-quiet-hours-toggle", "value")],
    )
    def toggle_quiet_hours(quiet_enabled: bool) -> bool:
        """Show quiet hours time inputs when quiet hours are enabled."""
        return bool(quiet_enabled)

    # --- Update confidence threshold display ---
    @app.callback(
        Output("confidence-threshold-display", "children"),
        [Input("alert-confidence-slider", "value")],
    )
    def update_confidence_display(value: float) -> str:
        """Display the confidence slider value as a percentage."""
        return f"{value:.0%}"

    # --- Update alert status indicator ---
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

    # --- Populate asset dropdown from DB ---
    @app.callback(
        Output("alert-assets-dropdown", "options"),
        [Input("alert-config-offcanvas", "is_open")],
    )
    def populate_alert_assets(is_open: bool):
        """Populate the assets dropdown when the panel opens."""
        if not is_open:
            from dash import no_update
            return no_update
        active_assets = get_active_assets_from_db()
        return [{"label": asset, "value": asset} for asset in active_assets]

    # --- Save preferences to localStorage ---
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

    # --- Load preferences into form when panel opens ---
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
        from dash import no_update

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

    # --- Enable/disable alert check interval based on master toggle ---
    app.clientside_callback(
        """
        function(prefs) {
            if (prefs && prefs.enabled) {
                return false;
            }
            return true;
        }
        """,
        Output("alert-check-interval", "disabled"),
        Input("alert-preferences-store", "data"),
    )
```

Then call this from the existing `register_callbacks`:

```python
def register_callbacks(app: Dash):
    """Register all callbacks for the dashboard."""

    # ... existing callbacks ...

    # Register alert callbacks
    register_alert_callbacks(app)
```

---

## Task 3: Backend Alert Checking Logic

### Purpose

Server-side logic that queries the database for new predictions and filters them against the user's preferences. This logic runs in a Dash callback triggered by `alert-check-interval`.

### Implementation

#### Step 1: Create `shitty_ui/alerts.py`

```python
"""
Alert checking and dispatch logic for Shitty UI Dashboard.
Handles querying for new predictions, filtering by user preferences,
and dispatching notifications via browser, email, and SMS.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def check_for_new_alerts(
    preferences: Dict[str, Any],
    last_check: Optional[str],
) -> Dict[str, Any]:
    """
    Check the database for new predictions that match the user's alert preferences.

    Args:
        preferences: User's alert preferences dict (from localStorage).
        last_check: ISO timestamp of the last check, or None if first check.

    Returns:
        Dict with keys:
            - "matched_alerts": list of alert dicts that matched preferences
            - "last_check": updated ISO timestamp string
            - "total_new": total new predictions found (before filtering)
    """
    from data import get_new_predictions_since

    # Determine the time window
    if last_check:
        try:
            since = datetime.fromisoformat(last_check)
        except (ValueError, TypeError):
            since = datetime.utcnow() - timedelta(minutes=5)
    else:
        # First check: look back 5 minutes
        since = datetime.utcnow() - timedelta(minutes=5)

    # Query database for new completed predictions
    new_predictions = get_new_predictions_since(since)
    total_new = len(new_predictions)

    if total_new == 0:
        return {
            "matched_alerts": [],
            "last_check": datetime.utcnow().isoformat(),
            "total_new": 0,
        }

    # Filter predictions against user preferences
    matched = filter_predictions_by_preferences(new_predictions, preferences)

    # Build alert objects for matched predictions
    matched_alerts = []
    for pred in matched:
        alert = {
            "prediction_id": pred.get("prediction_id"),
            "shitpost_id": pred.get("shitpost_id"),
            "text": pred.get("text", "")[:200],
            "confidence": pred.get("confidence"),
            "assets": pred.get("assets", []),
            "sentiment": _extract_sentiment(pred.get("market_impact", {})),
            "thesis": pred.get("thesis", ""),
            "timestamp": pred.get("timestamp"),
            "alert_triggered_at": datetime.utcnow().isoformat(),
        }
        matched_alerts.append(alert)

    logger.info(
        f"Alert check complete: {total_new} new predictions, "
        f"{len(matched_alerts)} matched preferences"
    )

    return {
        "matched_alerts": matched_alerts,
        "last_check": datetime.utcnow().isoformat(),
        "total_new": total_new,
    }


def filter_predictions_by_preferences(
    predictions: List[Dict[str, Any]],
    preferences: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Filter a list of prediction dicts against user alert preferences.

    Args:
        predictions: List of prediction dicts from the database.
        preferences: User's alert preferences dict.

    Returns:
        Filtered list of predictions that match all preference criteria.
    """
    min_confidence = preferences.get("min_confidence", 0.7)
    assets_of_interest = preferences.get("assets_of_interest", [])
    sentiment_filter = preferences.get("sentiment_filter", "all")

    matched = []
    for pred in predictions:
        # Check confidence threshold
        confidence = pred.get("confidence")
        if confidence is None or confidence < min_confidence:
            continue

        # Check asset filter (empty list = match all)
        if assets_of_interest:
            pred_assets = pred.get("assets", [])
            if not isinstance(pred_assets, list):
                pred_assets = []
            # Check if any of the prediction's assets are in the user's list
            if not any(asset in assets_of_interest for asset in pred_assets):
                continue

        # Check sentiment filter
        if sentiment_filter != "all":
            pred_sentiment = _extract_sentiment(pred.get("market_impact", {}))
            if pred_sentiment != sentiment_filter:
                continue

        matched.append(pred)

    return matched


def is_in_quiet_hours(preferences: Dict[str, Any]) -> bool:
    """
    Check if the current time falls within the user's configured quiet hours.

    Args:
        preferences: User's alert preferences dict.

    Returns:
        True if currently in quiet hours and quiet hours are enabled.
    """
    if not preferences.get("quiet_hours_enabled", False):
        return False

    now = datetime.now()
    current_time = now.strftime("%H:%M")

    start = preferences.get("quiet_hours_start", "22:00")
    end = preferences.get("quiet_hours_end", "08:00")

    # Handle overnight quiet hours (e.g., 22:00 - 08:00)
    if start > end:
        # Overnight: quiet if current >= start OR current < end
        return current_time >= start or current_time < end
    else:
        # Same day: quiet if current >= start AND current < end
        return start <= current_time < end


def _extract_sentiment(market_impact: Any) -> str:
    """
    Extract the primary sentiment from a market_impact JSONB field.

    The market_impact field is a dict mapping asset symbols to sentiment strings.
    Example: {"AAPL": "bullish", "GOOGL": "bearish"}

    Returns the first sentiment found, or "neutral" if empty/invalid.
    """
    if not isinstance(market_impact, dict) or not market_impact:
        return "neutral"

    first_value = next(iter(market_impact.values()), "neutral")
    if isinstance(first_value, str):
        return first_value.lower()
    return "neutral"


def format_alert_message(alert: Dict[str, Any]) -> str:
    """
    Format an alert dict into a human-readable notification message.

    Args:
        alert: Alert dict with keys: text, confidence, assets, sentiment, thesis.

    Returns:
        Formatted message string suitable for browser/email/SMS notifications.
    """
    confidence_pct = f"{alert.get('confidence', 0):.0%}"
    assets_str = ", ".join(alert.get("assets", [])[:5])
    sentiment = alert.get("sentiment", "neutral").upper()

    message = (
        f"New {sentiment} prediction ({confidence_pct} confidence)\n"
        f"Assets: {assets_str}\n"
        f"Post: {alert.get('text', '')[:120]}..."
    )
    return message


def format_alert_message_html(alert: Dict[str, Any]) -> str:
    """
    Format an alert dict into an HTML email body.

    Args:
        alert: Alert dict.

    Returns:
        HTML string for email body.
    """
    confidence_pct = f"{alert.get('confidence', 0):.0%}"
    assets_str = ", ".join(alert.get("assets", [])[:5])
    sentiment = alert.get("sentiment", "neutral").upper()
    thesis = alert.get("thesis", "No thesis provided.")

    sentiment_color = "#10b981" if sentiment == "BULLISH" else "#ef4444" if sentiment == "BEARISH" else "#94a3b8"

    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #1e293b; padding: 20px; border-radius: 8px;">
            <h2 style="color: #3b82f6; margin: 0 0 10px 0;">Shitpost Alpha Alert</h2>

            <div style="background: #334155; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                <div style="color: {sentiment_color}; font-weight: bold; font-size: 18px; margin-bottom: 5px;">
                    {sentiment} ({confidence_pct} confidence)
                </div>
                <div style="color: #94a3b8; font-size: 14px;">
                    Assets: {assets_str}
                </div>
            </div>

            <div style="background: #334155; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                <div style="color: #f1f5f9; font-size: 14px; line-height: 1.5;">
                    {alert.get('text', '')[:300]}
                </div>
            </div>

            <div style="background: #334155; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                <div style="color: #94a3b8; font-size: 12px; text-transform: uppercase; margin-bottom: 5px;">
                    Thesis
                </div>
                <div style="color: #f1f5f9; font-size: 14px; line-height: 1.5;">
                    {thesis[:500]}
                </div>
            </div>

            <div style="color: #475569; font-size: 12px; text-align: center; margin-top: 20px;">
                This is NOT financial advice. For entertainment and research purposes only.
            </div>
        </div>
    </div>
    """
```

#### Step 2: Add Database Query Function

Add this function to `shitty_ui/data.py`:

```python
def get_new_predictions_since(since: datetime) -> List[Dict[str, Any]]:
    """
    Get new completed predictions created after the given timestamp.
    Used by the alert system to find predictions the user hasn't been notified about.

    Args:
        since: Only return predictions created after this timestamp.

    Returns:
        List of prediction dicts with associated shitpost data.
    """
    query = text("""
        SELECT
            tss.timestamp,
            tss.text,
            tss.shitpost_id,
            p.id as prediction_id,
            p.assets,
            p.market_impact,
            p.confidence,
            p.thesis,
            p.analysis_status,
            p.created_at as prediction_created_at
        FROM predictions p
        INNER JOIN truth_social_shitposts tss
            ON tss.shitpost_id = p.shitpost_id
        WHERE p.analysis_status = 'completed'
            AND p.created_at > :since
            AND p.confidence IS NOT NULL
            AND p.assets IS NOT NULL
            AND p.assets::jsonb <> '[]'::jsonb
        ORDER BY p.created_at DESC
        LIMIT 50
    """)

    try:
        rows, columns = execute_query(query, {"since": since})
        results = []
        for row in rows:
            row_dict = dict(zip(columns, row))
            # Convert timestamp to ISO string for JSON serialization
            if isinstance(row_dict.get("timestamp"), datetime):
                row_dict["timestamp"] = row_dict["timestamp"].isoformat()
            if isinstance(row_dict.get("prediction_created_at"), datetime):
                row_dict["prediction_created_at"] = row_dict["prediction_created_at"].isoformat()
            results.append(row_dict)
        return results
    except Exception as e:
        print(f"Error loading new predictions: {e}")
        return []
```

#### Step 3: Register the Alert Check Callback

Add this callback inside `register_alert_callbacks()`:

```python
    # --- Main alert check callback ---
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
        """
        Periodically check for new predictions that match alert preferences.
        Triggered by alert-check-interval (every 2 minutes when enabled).
        """
        from alerts import check_for_new_alerts, is_in_quiet_hours

        if not preferences or not preferences.get("enabled", False):
            from dash import no_update
            return no_update, no_update, no_update

        # Check quiet hours
        if is_in_quiet_hours(preferences):
            # Still update last_check to avoid alert flood after quiet hours
            return None, alert_history, datetime.utcnow().isoformat()

        # Run the alert check
        result = check_for_new_alerts(preferences, last_check)

        matched_alerts = result["matched_alerts"]
        new_last_check = result["last_check"]

        if not matched_alerts:
            return None, alert_history, new_last_check

        # Append matched alerts to history (keep last 100)
        updated_history = (alert_history or []) + matched_alerts
        updated_history = updated_history[-100:]  # Keep most recent 100

        # Dispatch server-side notifications (email, SMS)
        for alert in matched_alerts:
            _dispatch_server_notifications(alert, preferences)

        # Return the first matched alert to trigger browser notification
        # (The clientside callback in Task 4 reads this and shows the notification)
        notification_data = matched_alerts[0] if matched_alerts else None

        return notification_data, updated_history, new_last_check

    def _dispatch_server_notifications(
        alert: dict,
        preferences: dict,
    ) -> None:
        """
        Dispatch email and SMS notifications for a matched alert.
        This runs server-side in the callback.

        Args:
            alert: The matched alert dict.
            preferences: User preferences dict.
        """
        from alerts import format_alert_message, format_alert_message_html

        # Send email if enabled
        if preferences.get("email_enabled") and preferences.get("email_address"):
            try:
                _send_email_alert(
                    to_email=preferences["email_address"],
                    subject=f"Shitpost Alpha: {alert.get('sentiment', 'NEW').upper()} Alert",
                    html_body=format_alert_message_html(alert),
                    text_body=format_alert_message(alert),
                )
            except Exception as e:
                logger.error(f"Failed to send email alert: {e}")

        # Send SMS if enabled
        if preferences.get("sms_enabled") and preferences.get("sms_phone_number"):
            try:
                _send_sms_alert(
                    to_phone=preferences["sms_phone_number"],
                    message=format_alert_message(alert),
                )
            except Exception as e:
                logger.error(f"Failed to send SMS alert: {e}")
```

**Note on `_send_email_alert` and `_send_sms_alert`**: These are defined in Tasks 5 and 6 below. Import them in the callback file or define them in `alerts.py`.

---

## Task 4: Browser Push Notifications

### Purpose

Show native browser notifications when a new prediction matches the user's alert preferences. This uses the Web Notifications API (not a full service worker push setup, since we are already polling).

### Implementation

#### Step 1: Request Notification Permission (Clientside Callback)

Add this clientside callback in `register_alert_callbacks()`:

```python
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
                // We can't update Dash state from here, but the next toggle
                // will re-check the permission status.
                console.log("Notification permission:", permission);
            });

            return "Requesting permission...";
        }
        """,
        Output("browser-notification-status", "children"),
        Input("alert-browser-toggle", "value"),
    )
```

#### Step 2: Trigger Browser Notification When Alert Fires

This clientside callback watches `alert-notification-store`. When it receives data, it creates a browser notification:

```python
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
```

> **Note**: The `allow_duplicate=True` parameter is needed because `alert-notification-store.data` is already an Output of the `run_alert_check` callback. This requires Dash >= 2.9. If your Dash version does not support `allow_duplicate`, use a separate hidden `html.Div(id="notification-trigger-sink")` as the output instead.

#### Step 3: Service Worker for Background Notifications (Optional Enhancement)

If the dashboard is open in a background tab, the Web Notifications API still works without a service worker. However, if you want notifications even when the tab is closed (true push), you would need a service worker plus a server-side push service. This is a stretch goal.

Create `shitty_ui/assets/service-worker.js`:

```javascript
/*
 * Service Worker for Shitpost Alpha Push Notifications.
 *
 * STRETCH GOAL: This enables notifications even when the browser tab is closed.
 * For the initial implementation, browser tab must be open since we rely on
 * dcc.Interval polling. This file is provided for future expansion.
 *
 * To activate:
 * 1. Register this service worker in the dashboard's index HTML.
 * 2. Implement a server-side push mechanism (e.g., web-push library).
 * 3. Store push subscriptions server-side.
 */

// Cache name for static assets
const CACHE_NAME = 'shitpost-alpha-v1';

// Install event - pre-cache static assets
self.addEventListener('install', function(event) {
    console.log('[ServiceWorker] Install');
    self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener('activate', function(event) {
    console.log('[ServiceWorker] Activate');
    event.waitUntil(self.clients.claim());
});

// Push event - handle incoming push notifications
self.addEventListener('push', function(event) {
    console.log('[ServiceWorker] Push received');

    var data = {};
    if (event.data) {
        try {
            data = event.data.json();
        } catch (e) {
            data = { body: event.data.text() };
        }
    }

    var title = data.title || 'Shitpost Alpha Alert';
    var options = {
        body: data.body || 'New prediction alert!',
        icon: '/assets/favicon.ico',
        badge: '/assets/favicon.ico',
        tag: data.tag || 'shitpost-alert',
        data: {
            url: data.url || '/',
            prediction_id: data.prediction_id,
        },
        actions: [
            { action: 'view', title: 'View Dashboard' },
            { action: 'dismiss', title: 'Dismiss' },
        ],
        requireInteraction: false,
        vibrate: [200, 100, 200],
    };

    event.waitUntil(
        self.registration.showNotification(title, options)
    );
});

// Notification click event - open dashboard
self.addEventListener('notificationclick', function(event) {
    console.log('[ServiceWorker] Notification click:', event.action);

    event.notification.close();

    if (event.action === 'dismiss') {
        return;
    }

    // Open or focus the dashboard
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true })
            .then(function(clientList) {
                // Try to focus an existing window
                for (var i = 0; i < clientList.length; i++) {
                    var client = clientList[i];
                    if (client.url.includes('/') && 'focus' in client) {
                        return client.focus();
                    }
                }
                // Open a new window if none exists
                if (clients.openWindow) {
                    var url = event.notification.data && event.notification.data.url
                        ? event.notification.data.url
                        : '/';
                    return clients.openWindow(url);
                }
            })
    );
});
```

To register the service worker, add this to the app's index string or a clientside callback that runs on page load:

```python
    # --- Register service worker on page load (optional) ---
    app.clientside_callback(
        """
        function(n) {
            if ('serviceWorker' in navigator) {
                navigator.serviceWorker.register('/assets/service-worker.js')
                    .then(function(registration) {
                        console.log('ServiceWorker registered:', registration.scope);
                    })
                    .catch(function(err) {
                        console.log('ServiceWorker registration failed:', err);
                    });
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output("alert-notification-store", "data", allow_duplicate=True),
        Input("refresh-interval", "n_intervals"),
        prevent_initial_call=False,
    )
```

#### Step 4: Test Alert Button (Sends a Fake Notification)

```python
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
```

---

## Task 5: Email Notifications (SMTP / SendGrid)

### Purpose

Send email alerts when new predictions match the user's preferences. Supports either raw SMTP or SendGrid API.

### Implementation

#### Step 1: Add Email Settings

Update `shit/config/shitpost_settings.py` to add email configuration:

```python
class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ... existing fields ...

    # Email Configuration (Phase 2 - Alerting)
    EMAIL_PROVIDER: str = Field(default="smtp", env="EMAIL_PROVIDER")  # "smtp" or "sendgrid"
    SMTP_HOST: Optional[str] = Field(default=None, env="SMTP_HOST")
    SMTP_PORT: int = Field(default=587, env="SMTP_PORT")
    SMTP_USERNAME: Optional[str] = Field(default=None, env="SMTP_USERNAME")
    SMTP_PASSWORD: Optional[str] = Field(default=None, env="SMTP_PASSWORD")
    SMTP_USE_TLS: bool = Field(default=True, env="SMTP_USE_TLS")
    EMAIL_FROM_ADDRESS: str = Field(
        default="alerts@shitpostalpha.com",
        env="EMAIL_FROM_ADDRESS",
    )
    EMAIL_FROM_NAME: str = Field(
        default="Shitpost Alpha",
        env="EMAIL_FROM_NAME",
    )
    SENDGRID_API_KEY: Optional[str] = Field(default=None, env="SENDGRID_API_KEY")
```

#### Step 2: Email Dispatch Functions

Add these functions to `shitty_ui/alerts.py`:

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def _send_email_alert(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str,
) -> bool:
    """
    Send an email alert to the user.

    Reads configuration from settings to determine whether to use
    SMTP or SendGrid.

    Args:
        to_email: Recipient email address.
        subject: Email subject line.
        html_body: HTML version of the email body.
        text_body: Plain text version of the email body.

    Returns:
        True if the email was sent successfully, False otherwise.

    Raises:
        ValueError: If email provider is not configured.
    """
    try:
        from shit.config.shitpost_settings import settings
    except ImportError:
        import os
        logger.error("Could not import settings for email configuration")
        return False

    provider = getattr(settings, "EMAIL_PROVIDER", "smtp")

    if provider == "sendgrid":
        return _send_via_sendgrid(to_email, subject, html_body, text_body, settings)
    else:
        return _send_via_smtp(to_email, subject, html_body, text_body, settings)


def _send_via_smtp(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str,
    settings: Any,
) -> bool:
    """
    Send an email using SMTP.

    Args:
        to_email: Recipient email address.
        subject: Email subject line.
        html_body: HTML body.
        text_body: Plain text body.
        settings: Application settings with SMTP configuration.

    Returns:
        True if sent successfully.
    """
    smtp_host = getattr(settings, "SMTP_HOST", None)
    smtp_port = getattr(settings, "SMTP_PORT", 587)
    smtp_user = getattr(settings, "SMTP_USERNAME", None)
    smtp_pass = getattr(settings, "SMTP_PASSWORD", None)
    use_tls = getattr(settings, "SMTP_USE_TLS", True)
    from_addr = getattr(settings, "EMAIL_FROM_ADDRESS", "alerts@shitpostalpha.com")
    from_name = getattr(settings, "EMAIL_FROM_NAME", "Shitpost Alpha")

    if not smtp_host or not smtp_user or not smtp_pass:
        logger.warning("SMTP not configured. Skipping email alert.")
        return False

    # Build the email
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_addr}>"
    msg["To"] = to_email

    # Attach plain text and HTML parts
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        if use_tls:
            server = smtplib.SMTP(smtp_host, smtp_port)
            server.ehlo()
            server.starttls()
            server.ehlo()
        else:
            server = smtplib.SMTP(smtp_host, smtp_port)
            server.ehlo()

        server.login(smtp_user, smtp_pass)
        server.sendmail(from_addr, to_email, msg.as_string())
        server.quit()

        logger.info(f"Email alert sent to {to_email}")
        return True

    except smtplib.SMTPException as e:
        logger.error(f"SMTP error sending email to {to_email}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending email to {to_email}: {e}")
        return False


def _send_via_sendgrid(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str,
    settings: Any,
) -> bool:
    """
    Send an email using the SendGrid API.

    Requires the `sendgrid` package: pip install sendgrid

    Args:
        to_email: Recipient email address.
        subject: Email subject line.
        html_body: HTML body.
        text_body: Plain text body (used as fallback).
        settings: Application settings with SendGrid configuration.

    Returns:
        True if sent successfully.
    """
    api_key = getattr(settings, "SENDGRID_API_KEY", None)
    from_addr = getattr(settings, "EMAIL_FROM_ADDRESS", "alerts@shitpostalpha.com")
    from_name = getattr(settings, "EMAIL_FROM_NAME", "Shitpost Alpha")

    if not api_key:
        logger.warning("SendGrid API key not configured. Skipping email alert.")
        return False

    try:
        import requests as req

        payload = {
            "personalizations": [
                {
                    "to": [{"email": to_email}],
                    "subject": subject,
                }
            ],
            "from": {"email": from_addr, "name": from_name},
            "content": [
                {"type": "text/plain", "value": text_body},
                {"type": "text/html", "value": html_body},
            ],
        }

        response = req.post(
            "https://api.sendgrid.com/v3/mail/send",
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=10,
        )

        if response.status_code in (200, 201, 202):
            logger.info(f"SendGrid email sent to {to_email}")
            return True
        else:
            logger.error(
                f"SendGrid API error: {response.status_code} - {response.text}"
            )
            return False

    except ImportError:
        logger.error("requests package not available for SendGrid API call")
        return False
    except Exception as e:
        logger.error(f"SendGrid error: {e}")
        return False
```

---

## Task 6: SMS Alerts via Twilio

### Purpose

Send SMS alerts when new predictions match the user's preferences. The project already has Twilio configured in `requirements.txt` and `shitpost_settings.py`.

### Existing Configuration

From `shit/config/shitpost_settings.py`:

```python
# SMS/Alerting Configuration (Phase 2)
TWILIO_ACCOUNT_SID: Optional[str] = Field(default=None, env="TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN: Optional[str] = Field(default=None, env="TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER: Optional[str] = Field(default=None, env="TWILIO_PHONE_NUMBER")
```

From `requirements.txt`:

```
twilio>=8.0.0
```

### Implementation

Add this function to `shitty_ui/alerts.py`:

```python
def _send_sms_alert(
    to_phone: str,
    message: str,
) -> bool:
    """
    Send an SMS alert via Twilio.

    Args:
        to_phone: Recipient phone number in E.164 format (e.g., "+15551234567").
        message: The SMS message body. Twilio allows up to 1600 characters,
                 but standard SMS is 160 characters. Messages longer than 160
                 characters will be sent as multi-part SMS.

    Returns:
        True if the SMS was sent successfully, False otherwise.
    """
    try:
        from shit.config.shitpost_settings import settings
    except ImportError:
        logger.error("Could not import settings for Twilio configuration")
        return False

    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    from_number = settings.TWILIO_PHONE_NUMBER

    if not account_sid or not auth_token or not from_number:
        logger.warning("Twilio not configured. Skipping SMS alert.")
        return False

    # Validate phone number format (basic E.164 check)
    if not _validate_phone_number(to_phone):
        logger.error(f"Invalid phone number format: {to_phone}")
        return False

    # Truncate message to Twilio's limit (1600 chars)
    if len(message) > 1600:
        message = message[:1597] + "..."

    try:
        from twilio.rest import Client

        client = Client(account_sid, auth_token)

        sms = client.messages.create(
            body=message,
            from_=from_number,
            to=to_phone,
        )

        logger.info(f"SMS alert sent to {to_phone}, SID: {sms.sid}")
        return True

    except ImportError:
        logger.error("Twilio package not installed. Run: pip install twilio")
        return False
    except Exception as e:
        logger.error(f"Twilio error sending SMS to {to_phone}: {e}")
        return False


def _validate_phone_number(phone: str) -> bool:
    """
    Validate that a phone number is in E.164 format.

    E.164 format: + followed by 1-15 digits.
    Examples: +15551234567, +442071234567

    Args:
        phone: Phone number string to validate.

    Returns:
        True if the phone number appears valid.
    """
    import re

    if not phone:
        return False

    # E.164: + followed by 1 to 15 digits
    pattern = r'^\+[1-9]\d{1,14}$'
    return bool(re.match(pattern, phone.strip()))
```

### Rate Limiting

To prevent excessive SMS charges, implement a rate limiter. This uses an in-memory counter (resets when the dashboard server restarts, which is acceptable for this use case):

```python
# Module-level rate limiter for SMS
_sms_sent_timestamps: List[float] = []
_SMS_RATE_LIMIT = 10     # Max SMS per hour
_SMS_RATE_WINDOW = 3600  # 1 hour in seconds


def _check_sms_rate_limit() -> bool:
    """
    Check if sending another SMS would exceed the rate limit.

    Returns:
        True if sending is allowed, False if rate limit would be exceeded.
    """
    import time

    now = time.time()
    cutoff = now - _SMS_RATE_WINDOW

    # Remove timestamps older than the window
    while _sms_sent_timestamps and _sms_sent_timestamps[0] < cutoff:
        _sms_sent_timestamps.pop(0)

    if len(_sms_sent_timestamps) >= _SMS_RATE_LIMIT:
        logger.warning(
            f"SMS rate limit reached: {len(_sms_sent_timestamps)} "
            f"messages in the last hour (limit: {_SMS_RATE_LIMIT})"
        )
        return False

    return True


def _record_sms_sent() -> None:
    """Record that an SMS was sent for rate limiting purposes."""
    import time
    _sms_sent_timestamps.append(time.time())
```

Update `_send_sms_alert` to use rate limiting:

```python
def _send_sms_alert(to_phone: str, message: str) -> bool:
    # ... existing validation code ...

    # Check rate limit before sending
    if not _check_sms_rate_limit():
        logger.warning(f"SMS to {to_phone} blocked by rate limit")
        return False

    try:
        from twilio.rest import Client

        client = Client(account_sid, auth_token)
        sms = client.messages.create(
            body=message,
            from_=from_number,
            to=to_phone,
        )

        _record_sms_sent()  # Record successful send
        logger.info(f"SMS alert sent to {to_phone}, SID: {sms.sid}")
        return True

    except Exception as e:
        logger.error(f"Twilio error sending SMS to {to_phone}: {e}")
        return False
```

---

## Task 7: Alert History Panel

### Purpose

Show users a log of recent alerts: what was triggered, when, and which notification channels were used. The history is stored in localStorage via `alert-history-store`.

### Implementation

#### Step 1: Add Alert History Section to Layout

Add this below the main content area in `create_app()`, or as a tab inside the alert config offcanvas. Here we add it as a collapsible card in the main dashboard:

```python
def create_alert_history_panel():
    """
    Create the alert history card for the main dashboard.

    Shows recent alerts with timestamp, prediction details,
    and whether they were triggered (matched preferences).
    """
    return dbc.Card([
        dbc.CardHeader([
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
        ], className="fw-bold"),
        dbc.Collapse(
            dbc.CardBody(
                id="alert-history-content",
                style={"maxHeight": "400px", "overflowY": "auto"},
            ),
            id="collapse-alert-history",
            is_open=False,
        ),
    ], className="mt-4", style={"backgroundColor": COLORS["secondary"]})
```

Add this card to the main layout, after the collapsible data table and before the footer:

```python
# In create_app(), inside the main content container:

    # ... existing collapsible data table ...

    # Alert history panel
    create_alert_history_panel(),

    # Footer
    create_footer(),
```

#### Step 2: Register History Callbacks

Add to `register_alert_callbacks()`:

```python
    # --- Toggle alert history collapse ---
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

    # --- Render alert history ---
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
                    style={"color": COLORS["text_muted"], "textAlign": "center", "padding": "20px"},
                ),
                "0",
            )

        count = len(history)
        alert_cards = []

        # Show most recent first
        for alert in reversed(history[-50:]):
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
                ts = datetime.fromisoformat(triggered_at)
                time_str = ts.strftime("%b %d, %H:%M")
            except (ValueError, TypeError):
                time_str = str(triggered_at)[:16]

            asset_str = ", ".join(assets[:3]) if isinstance(assets, list) else str(assets)

            card = html.Div([
                html.Div([
                    html.Span(
                        time_str,
                        style={"color": COLORS["text_muted"], "fontSize": "0.75rem"},
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
                        f" | {confidence:.0%}",
                        style={"color": COLORS["text_muted"], "fontSize": "0.75rem"},
                    ),
                ], className="d-flex align-items-center mb-1"),
                html.P(
                    text + "..." if len(text) >= 120 else text,
                    style={
                        "fontSize": "0.8rem",
                        "margin": "3px 0",
                        "lineHeight": "1.3",
                        "color": COLORS["text"],
                    },
                ),
                html.Div([
                    html.Span(
                        f"Assets: {asset_str}",
                        style={"color": COLORS["text_muted"], "fontSize": "0.75rem"},
                    ),
                ]),
            ], style={
                "padding": "10px",
                "borderBottom": f"1px solid {COLORS['border']}",
            })

            alert_cards.append(card)

        return alert_cards, str(count)

    # --- Clear alert history ---
    @app.callback(
        Output("alert-history-store", "data", allow_duplicate=True),
        [Input("clear-alert-history-button", "n_clicks")],
        prevent_initial_call=True,
    )
    def clear_alert_history(n_clicks: int) -> list:
        """Clear all alert history from localStorage."""
        if n_clicks:
            return []
        from dash import no_update
        return no_update

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

---

## Security Considerations

### 1. No API Keys in the Frontend

**Rule**: Never expose `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `SMTP_PASSWORD`, or `SENDGRID_API_KEY` in the browser.

These credentials are only loaded server-side in `alerts.py` via:

```python
from shit.config.shitpost_settings import settings
```

Dash callbacks run on the server. The clientside callbacks (JavaScript) only handle browser notifications and localStorage. No secrets are passed to any `clientside_callback`.

**Verification checklist**:
- No secrets appear in `dcc.Store` data.
- No secrets appear in `clientside_callback` JavaScript strings.
- The `alerts.py` module is never imported in clientside code.
- Settings are only accessed in server-side Python callback functions.

### 2. Input Validation

**Phone numbers**: Validate E.164 format before passing to Twilio.

```python
# In alerts.py - already implemented above
def _validate_phone_number(phone: str) -> bool:
    import re
    if not phone:
        return False
    pattern = r'^\+[1-9]\d{1,14}$'
    return bool(re.match(pattern, phone.strip()))
```

**Email addresses**: Validate format before sending.

```python
def _validate_email(email: str) -> bool:
    """Basic email validation."""
    import re
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))
```

### 3. Rate Limiting

Prevent abuse of server-side notification channels:

| Channel | Rate Limit | Window |
|---------|-----------|--------|
| Browser | N/A (client-side, browser handles) | N/A |
| Email | 20 per hour | 1 hour |
| SMS | 10 per hour | 1 hour |

The SMS rate limiter is implemented above. Apply the same pattern for email:

```python
_email_sent_timestamps: List[float] = []
_EMAIL_RATE_LIMIT = 20
_EMAIL_RATE_WINDOW = 3600


def _check_email_rate_limit() -> bool:
    """Check if sending another email would exceed the rate limit."""
    import time
    now = time.time()
    cutoff = now - _EMAIL_RATE_WINDOW
    while _email_sent_timestamps and _email_sent_timestamps[0] < cutoff:
        _email_sent_timestamps.pop(0)
    if len(_email_sent_timestamps) >= _EMAIL_RATE_LIMIT:
        logger.warning(f"Email rate limit reached: {len(_email_sent_timestamps)} in last hour")
        return False
    return True


def _record_email_sent() -> None:
    """Record that an email was sent for rate limiting."""
    import time
    _email_sent_timestamps.append(time.time())
```

### 4. localStorage Limitations

- localStorage is per-origin. If the dashboard URL changes (e.g., different Railway deployment URL), preferences are lost.
- localStorage has a ~5MB limit per origin. Our data is well within this (alert history is capped at 100 entries).
- localStorage is not encrypted. Phone numbers and email addresses stored there are visible to anyone with browser access. Add a note in the UI:

```python
html.Small(
    "Preferences are stored in your browser. They are not synced across devices.",
    style={"color": COLORS["text_muted"], "fontSize": "0.75rem", "display": "block", "marginTop": "10px"},
)
```

### 5. SQL Injection Prevention

All database queries use SQLAlchemy `text()` with parameterized queries. The `get_new_predictions_since()` function uses `:since` as a parameter placeholder. Never concatenate user input into SQL strings.

```python
# CORRECT - parameterized query
query = text("SELECT * FROM predictions WHERE created_at > :since")
execute_query(query, {"since": since})

# WRONG - SQL injection vulnerability
query = text(f"SELECT * FROM predictions WHERE created_at > '{since}'")
```

---

## Test Specifications

### Test File: `shit_tests/shitty_ui/test_alerts.py`

```python
"""
Tests for the alerting system.
Covers alert checking, filtering, notification dispatch, and rate limiting.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock


# ============================================================
# Test: filter_predictions_by_preferences
# ============================================================


class TestFilterPredictionsByPreferences:
    """Test the prediction filtering logic against user preferences."""

    def _make_prediction(
        self,
        confidence: float = 0.8,
        assets: list = None,
        market_impact: dict = None,
    ) -> dict:
        """Helper to create a prediction dict for testing."""
        return {
            "prediction_id": 1,
            "shitpost_id": "abc123",
            "text": "Big news for AAPL today!",
            "confidence": confidence,
            "assets": assets or ["AAPL"],
            "market_impact": market_impact or {"AAPL": "bullish"},
            "thesis": "Test thesis",
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _make_preferences(
        self,
        min_confidence: float = 0.7,
        assets_of_interest: list = None,
        sentiment_filter: str = "all",
    ) -> dict:
        """Helper to create a preferences dict for testing."""
        return {
            "enabled": True,
            "min_confidence": min_confidence,
            "assets_of_interest": assets_of_interest or [],
            "sentiment_filter": sentiment_filter,
        }

    def test_matches_when_all_criteria_met(self):
        """Prediction matches when confidence, asset, and sentiment all pass."""
        from alerts import filter_predictions_by_preferences

        predictions = [self._make_prediction(confidence=0.85, assets=["AAPL"])]
        prefs = self._make_preferences(min_confidence=0.7, assets_of_interest=["AAPL"])

        result = filter_predictions_by_preferences(predictions, prefs)
        assert len(result) == 1

    def test_filters_low_confidence(self):
        """Predictions below confidence threshold are excluded."""
        from alerts import filter_predictions_by_preferences

        predictions = [self._make_prediction(confidence=0.5)]
        prefs = self._make_preferences(min_confidence=0.7)

        result = filter_predictions_by_preferences(predictions, prefs)
        assert len(result) == 0

    def test_filters_wrong_asset(self):
        """Predictions for non-matching assets are excluded."""
        from alerts import filter_predictions_by_preferences

        predictions = [self._make_prediction(assets=["GOOGL"])]
        prefs = self._make_preferences(assets_of_interest=["AAPL", "TSLA"])

        result = filter_predictions_by_preferences(predictions, prefs)
        assert len(result) == 0

    def test_empty_assets_matches_all(self):
        """Empty assets_of_interest list matches all assets."""
        from alerts import filter_predictions_by_preferences

        predictions = [self._make_prediction(assets=["GOOGL"])]
        prefs = self._make_preferences(assets_of_interest=[])

        result = filter_predictions_by_preferences(predictions, prefs)
        assert len(result) == 1

    def test_filters_wrong_sentiment(self):
        """Predictions with non-matching sentiment are excluded."""
        from alerts import filter_predictions_by_preferences

        predictions = [self._make_prediction(market_impact={"AAPL": "bearish"})]
        prefs = self._make_preferences(sentiment_filter="bullish")

        result = filter_predictions_by_preferences(predictions, prefs)
        assert len(result) == 0

    def test_sentiment_all_matches_everything(self):
        """Sentiment filter 'all' matches any sentiment."""
        from alerts import filter_predictions_by_preferences

        predictions = [
            self._make_prediction(market_impact={"AAPL": "bullish"}),
            self._make_prediction(market_impact={"AAPL": "bearish"}),
            self._make_prediction(market_impact={"AAPL": "neutral"}),
        ]
        prefs = self._make_preferences(sentiment_filter="all")

        result = filter_predictions_by_preferences(predictions, prefs)
        assert len(result) == 3

    def test_none_confidence_excluded(self):
        """Predictions with None confidence are excluded."""
        from alerts import filter_predictions_by_preferences

        predictions = [self._make_prediction(confidence=None)]
        prefs = self._make_preferences(min_confidence=0.5)

        result = filter_predictions_by_preferences(predictions, prefs)
        assert len(result) == 0

    def test_multiple_asset_overlap(self):
        """Match when prediction has multiple assets and one overlaps."""
        from alerts import filter_predictions_by_preferences

        predictions = [self._make_prediction(assets=["GOOGL", "AAPL", "MSFT"])]
        prefs = self._make_preferences(assets_of_interest=["AAPL"])

        result = filter_predictions_by_preferences(predictions, prefs)
        assert len(result) == 1


# ============================================================
# Test: is_in_quiet_hours
# ============================================================


class TestIsInQuietHours:
    """Test quiet hours checking."""

    def test_returns_false_when_disabled(self):
        """Returns False when quiet hours are disabled."""
        from alerts import is_in_quiet_hours

        prefs = {"quiet_hours_enabled": False}
        assert is_in_quiet_hours(prefs) is False

    @patch("alerts.datetime")
    def test_overnight_quiet_hours_during(self, mock_dt):
        """Returns True during overnight quiet hours (22:00-08:00)."""
        from alerts import is_in_quiet_hours

        mock_dt.now.return_value = datetime(2024, 1, 15, 23, 30)
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)

        prefs = {
            "quiet_hours_enabled": True,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "08:00",
        }
        assert is_in_quiet_hours(prefs) is True

    @patch("alerts.datetime")
    def test_overnight_quiet_hours_outside(self, mock_dt):
        """Returns False outside overnight quiet hours."""
        from alerts import is_in_quiet_hours

        mock_dt.now.return_value = datetime(2024, 1, 15, 14, 0)
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)

        prefs = {
            "quiet_hours_enabled": True,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "08:00",
        }
        assert is_in_quiet_hours(prefs) is False


# ============================================================
# Test: _extract_sentiment
# ============================================================


class TestExtractSentiment:
    """Test sentiment extraction from market_impact."""

    def test_extracts_bullish(self):
        """Extracts bullish sentiment from market_impact dict."""
        from alerts import _extract_sentiment

        result = _extract_sentiment({"AAPL": "bullish"})
        assert result == "bullish"

    def test_extracts_bearish(self):
        """Extracts bearish sentiment."""
        from alerts import _extract_sentiment

        result = _extract_sentiment({"TSLA": "bearish"})
        assert result == "bearish"

    def test_returns_neutral_for_empty(self):
        """Returns neutral for empty market_impact."""
        from alerts import _extract_sentiment

        assert _extract_sentiment({}) == "neutral"
        assert _extract_sentiment(None) == "neutral"

    def test_returns_neutral_for_non_dict(self):
        """Returns neutral for non-dict market_impact."""
        from alerts import _extract_sentiment

        assert _extract_sentiment("bullish") == "neutral"
        assert _extract_sentiment([]) == "neutral"


# ============================================================
# Test: _validate_phone_number
# ============================================================


class TestValidatePhoneNumber:
    """Test phone number validation."""

    def test_valid_us_number(self):
        """Accepts valid US phone number."""
        from alerts import _validate_phone_number

        assert _validate_phone_number("+15551234567") is True

    def test_valid_uk_number(self):
        """Accepts valid UK phone number."""
        from alerts import _validate_phone_number

        assert _validate_phone_number("+442071234567") is True

    def test_rejects_no_plus(self):
        """Rejects phone number without + prefix."""
        from alerts import _validate_phone_number

        assert _validate_phone_number("15551234567") is False

    def test_rejects_empty(self):
        """Rejects empty string."""
        from alerts import _validate_phone_number

        assert _validate_phone_number("") is False

    def test_rejects_none(self):
        """Rejects None."""
        from alerts import _validate_phone_number

        assert _validate_phone_number(None) is False

    def test_rejects_too_short(self):
        """Rejects numbers that are too short."""
        from alerts import _validate_phone_number

        assert _validate_phone_number("+1") is True  # Minimum 2 digits (country code)
        assert _validate_phone_number("+") is False   # No digits

    def test_rejects_letters(self):
        """Rejects numbers containing letters."""
        from alerts import _validate_phone_number

        assert _validate_phone_number("+1555abc4567") is False


# ============================================================
# Test: format_alert_message
# ============================================================


class TestFormatAlertMessage:
    """Test alert message formatting."""

    def test_formats_bullish_alert(self):
        """Formats a bullish alert message."""
        from alerts import format_alert_message

        alert = {
            "confidence": 0.85,
            "assets": ["AAPL", "GOOGL"],
            "sentiment": "bullish",
            "text": "Great day for American tech companies!",
        }
        result = format_alert_message(alert)
        assert "BULLISH" in result
        assert "85%" in result
        assert "AAPL" in result
        assert "GOOGL" in result

    def test_handles_empty_assets(self):
        """Handles empty assets list."""
        from alerts import format_alert_message

        alert = {
            "confidence": 0.7,
            "assets": [],
            "sentiment": "neutral",
            "text": "Some post",
        }
        result = format_alert_message(alert)
        assert "NEUTRAL" in result


# ============================================================
# Test: _send_sms_alert
# ============================================================


class TestSendSmsAlert:
    """Test SMS dispatch via Twilio."""

    @patch("alerts._check_sms_rate_limit", return_value=True)
    @patch("alerts._record_sms_sent")
    @patch("alerts._validate_phone_number", return_value=True)
    def test_sends_sms_successfully(self, mock_validate, mock_record, mock_rate):
        """Successfully sends SMS via Twilio."""
        with patch("twilio.rest.Client") as MockClient:
            mock_client = MockClient.return_value
            mock_msg = MagicMock()
            mock_msg.sid = "SM123abc"
            mock_client.messages.create.return_value = mock_msg

            with patch("alerts.settings") as mock_settings:
                mock_settings.TWILIO_ACCOUNT_SID = "test_sid"
                mock_settings.TWILIO_AUTH_TOKEN = "test_token"
                mock_settings.TWILIO_PHONE_NUMBER = "+15550001234"

                from alerts import _send_sms_alert

                result = _send_sms_alert("+15551234567", "Test message")
                assert result is True
                mock_client.messages.create.assert_called_once()

    def test_rejects_invalid_phone(self):
        """Rejects invalid phone numbers before calling Twilio."""
        with patch("alerts.settings") as mock_settings:
            mock_settings.TWILIO_ACCOUNT_SID = "test_sid"
            mock_settings.TWILIO_AUTH_TOKEN = "test_token"
            mock_settings.TWILIO_PHONE_NUMBER = "+15550001234"

            from alerts import _send_sms_alert

            result = _send_sms_alert("not-a-phone", "Test message")
            assert result is False

    def test_returns_false_when_not_configured(self):
        """Returns False when Twilio is not configured."""
        with patch("alerts.settings") as mock_settings:
            mock_settings.TWILIO_ACCOUNT_SID = None
            mock_settings.TWILIO_AUTH_TOKEN = None
            mock_settings.TWILIO_PHONE_NUMBER = None

            from alerts import _send_sms_alert

            result = _send_sms_alert("+15551234567", "Test message")
            assert result is False


# ============================================================
# Test: _send_email_alert
# ============================================================


class TestSendEmailAlert:
    """Test email dispatch."""

    @patch("alerts._send_via_smtp")
    def test_dispatches_to_smtp(self, mock_smtp):
        """Routes to SMTP when EMAIL_PROVIDER is smtp."""
        mock_smtp.return_value = True

        with patch("alerts.settings") as mock_settings:
            mock_settings.EMAIL_PROVIDER = "smtp"

            from alerts import _send_email_alert

            result = _send_email_alert(
                "test@example.com",
                "Test Subject",
                "<p>HTML body</p>",
                "Text body",
            )
            assert result is True
            mock_smtp.assert_called_once()

    @patch("alerts._send_via_sendgrid")
    def test_dispatches_to_sendgrid(self, mock_sg):
        """Routes to SendGrid when EMAIL_PROVIDER is sendgrid."""
        mock_sg.return_value = True

        with patch("alerts.settings") as mock_settings:
            mock_settings.EMAIL_PROVIDER = "sendgrid"

            from alerts import _send_email_alert

            result = _send_email_alert(
                "test@example.com",
                "Test Subject",
                "<p>HTML body</p>",
                "Text body",
            )
            assert result is True
            mock_sg.assert_called_once()


# ============================================================
# Test: check_for_new_alerts (integration-style)
# ============================================================


class TestCheckForNewAlerts:
    """Test the main alert checking function."""

    @patch("alerts.get_new_predictions_since")
    def test_returns_empty_when_no_new_predictions(self, mock_query):
        """Returns empty matched_alerts when no new predictions."""
        mock_query.return_value = []

        from alerts import check_for_new_alerts

        prefs = {
            "enabled": True,
            "min_confidence": 0.7,
            "assets_of_interest": [],
            "sentiment_filter": "all",
        }
        result = check_for_new_alerts(prefs, datetime.utcnow().isoformat())
        assert result["matched_alerts"] == []
        assert result["total_new"] == 0

    @patch("alerts.get_new_predictions_since")
    def test_returns_matched_alerts(self, mock_query):
        """Returns matched alerts when predictions match preferences."""
        mock_query.return_value = [
            {
                "prediction_id": 1,
                "shitpost_id": "abc",
                "text": "AAPL going up!",
                "confidence": 0.85,
                "assets": ["AAPL"],
                "market_impact": {"AAPL": "bullish"},
                "thesis": "Strong earnings",
                "timestamp": datetime.utcnow().isoformat(),
            }
        ]

        from alerts import check_for_new_alerts

        prefs = {
            "enabled": True,
            "min_confidence": 0.7,
            "assets_of_interest": [],
            "sentiment_filter": "all",
        }
        result = check_for_new_alerts(prefs, datetime.utcnow().isoformat())
        assert len(result["matched_alerts"]) == 1
        assert result["total_new"] == 1

    @patch("alerts.get_new_predictions_since")
    def test_handles_none_last_check(self, mock_query):
        """Handles None last_check timestamp (first check)."""
        mock_query.return_value = []

        from alerts import check_for_new_alerts

        prefs = {
            "enabled": True,
            "min_confidence": 0.7,
            "assets_of_interest": [],
            "sentiment_filter": "all",
        }
        result = check_for_new_alerts(prefs, None)
        assert result["matched_alerts"] == []
        assert result["last_check"] is not None


# ============================================================
# Test: Rate Limiting
# ============================================================


class TestRateLimiting:
    """Test SMS and email rate limiting."""

    def test_sms_rate_limit_allows_initial(self):
        """Allows SMS when under rate limit."""
        import alerts

        # Reset the rate limiter
        alerts._sms_sent_timestamps.clear()

        result = alerts._check_sms_rate_limit()
        assert result is True

    def test_sms_rate_limit_blocks_when_exceeded(self):
        """Blocks SMS when rate limit is exceeded."""
        import time
        import alerts

        # Fill up the rate limiter
        alerts._sms_sent_timestamps.clear()
        now = time.time()
        for _ in range(alerts._SMS_RATE_LIMIT):
            alerts._sms_sent_timestamps.append(now)

        result = alerts._check_sms_rate_limit()
        assert result is False

    def test_sms_rate_limit_clears_old_entries(self):
        """Old SMS timestamps are cleared from the rate limiter."""
        import time
        import alerts

        alerts._sms_sent_timestamps.clear()
        old_time = time.time() - 7200  # 2 hours ago
        for _ in range(alerts._SMS_RATE_LIMIT):
            alerts._sms_sent_timestamps.append(old_time)

        result = alerts._check_sms_rate_limit()
        assert result is True


# ============================================================
# Test: Data Layer - get_new_predictions_since
# ============================================================


class TestGetNewPredictionsSince:
    """Test the database query for new predictions."""

    @patch("data.execute_query")
    def test_returns_list_of_dicts(self, mock_execute):
        """Returns a list of dicts with expected keys."""
        mock_execute.return_value = (
            [
                (
                    datetime(2024, 1, 15, 10, 0),  # timestamp
                    "Test post",                    # text
                    "post123",                      # shitpost_id
                    1,                              # prediction_id
                    ["AAPL"],                       # assets
                    {"AAPL": "bullish"},            # market_impact
                    0.85,                           # confidence
                    "Strong thesis",                # thesis
                    "completed",                    # analysis_status
                    datetime(2024, 1, 15, 10, 5),  # prediction_created_at
                ),
            ],
            [
                "timestamp", "text", "shitpost_id", "prediction_id",
                "assets", "market_impact", "confidence", "thesis",
                "analysis_status", "prediction_created_at",
            ],
        )

        from data import get_new_predictions_since

        result = get_new_predictions_since(datetime(2024, 1, 15, 9, 0))
        assert len(result) == 1
        assert result[0]["shitpost_id"] == "post123"
        assert result[0]["confidence"] == 0.85

    @patch("data.execute_query")
    def test_returns_empty_on_error(self, mock_execute):
        """Returns empty list on database error."""
        mock_execute.side_effect = Exception("Database connection failed")

        from data import get_new_predictions_since

        result = get_new_predictions_since(datetime(2024, 1, 15, 9, 0))
        assert result == []

    @patch("data.execute_query")
    def test_returns_empty_when_no_rows(self, mock_execute):
        """Returns empty list when query returns no rows."""
        mock_execute.return_value = (
            [],
            [
                "timestamp", "text", "shitpost_id", "prediction_id",
                "assets", "market_impact", "confidence", "thesis",
                "analysis_status", "prediction_created_at",
            ],
        )

        from data import get_new_predictions_since

        result = get_new_predictions_since(datetime(2024, 1, 15, 9, 0))
        assert result == []
```

### Test File: `shit_tests/shitty_ui/test_alert_layout.py`

```python
"""
Tests for alert UI layout components.
"""

import pytest
from datetime import datetime


class TestAlertConfigPanel:
    """Test the alert configuration panel component."""

    def test_create_alert_config_panel_returns_offcanvas(self):
        """Panel returns a dbc.Offcanvas component."""
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'shitty_ui'))
        from layout import create_alert_config_panel
        import dash_bootstrap_components as dbc

        panel = create_alert_config_panel()
        assert isinstance(panel, dbc.Offcanvas)

    def test_panel_has_master_toggle(self):
        """Panel contains the alert master toggle switch."""
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'shitty_ui'))
        from layout import create_alert_config_panel

        panel = create_alert_config_panel()
        # Verify the offcanvas has children (configuration controls)
        assert panel.children is not None
        assert len(panel.children) > 0

    def test_panel_has_correct_id(self):
        """Panel has the expected component ID."""
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'shitty_ui'))
        from layout import create_alert_config_panel

        panel = create_alert_config_panel()
        assert panel.id == "alert-config-offcanvas"


class TestAlertHistoryPanel:
    """Test the alert history panel component."""

    def test_create_alert_history_panel_returns_card(self):
        """History panel returns a dbc.Card component."""
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'shitty_ui'))
        from layout import create_alert_history_panel
        import dash_bootstrap_components as dbc

        panel = create_alert_history_panel()
        assert isinstance(panel, dbc.Card)


class TestDefaultAlertPreferences:
    """Test default alert preferences."""

    def test_default_preferences_has_required_keys(self):
        """Default preferences dict has all required keys."""
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'shitty_ui'))
        from layout import DEFAULT_ALERT_PREFERENCES

        required_keys = [
            "enabled",
            "min_confidence",
            "assets_of_interest",
            "sentiment_filter",
            "browser_notifications",
            "email_enabled",
            "email_address",
            "sms_enabled",
            "sms_phone_number",
        ]
        for key in required_keys:
            assert key in DEFAULT_ALERT_PREFERENCES, f"Missing key: {key}"

    def test_default_preferences_disabled(self):
        """Alerts are disabled by default."""
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'shitty_ui'))
        from layout import DEFAULT_ALERT_PREFERENCES

        assert DEFAULT_ALERT_PREFERENCES["enabled"] is False

    def test_default_confidence_threshold(self):
        """Default confidence threshold is 0.7."""
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'shitty_ui'))
        from layout import DEFAULT_ALERT_PREFERENCES

        assert DEFAULT_ALERT_PREFERENCES["min_confidence"] == 0.7
```

### Running the Tests

```bash
# Run all alert tests
cd /home/user/shitpost-alpha
python3 -m pytest shit_tests/shitty_ui/test_alerts.py -v
python3 -m pytest shit_tests/shitty_ui/test_alert_layout.py -v

# Run with coverage
python3 -m pytest shit_tests/shitty_ui/test_alerts.py shit_tests/shitty_ui/test_alert_layout.py --cov=shitty_ui -v
```

---

## Implementation Checklist

### Task 1: Alert Preferences Store (localStorage)
- [ ] Define `DEFAULT_ALERT_PREFERENCES` dict in `layout.py`
- [ ] Add `dcc.Store(id="alert-preferences-store", storage_type="local")` to layout
- [ ] Add `dcc.Store(id="last-alert-check-store", storage_type="local")` to layout
- [ ] Add `dcc.Store(id="alert-history-store", storage_type="local")` to layout
- [ ] Add `dcc.Store(id="alert-notification-store", storage_type="memory")` to layout
- [ ] Add `dcc.Interval(id="alert-check-interval")` to layout
- [ ] Add clientside callback to enable/disable interval based on preferences
- [ ] Add tests for default preferences

### Task 2: Alert Configuration UI Panel
- [ ] Update `create_header()` with bell icon button
- [ ] Create `create_alert_config_panel()` function
- [ ] Add offcanvas to app layout
- [ ] Register `toggle_alert_config` callback (open/close panel)
- [ ] Register `toggle_email_input` callback
- [ ] Register `toggle_sms_input` callback
- [ ] Register `toggle_quiet_hours` callback
- [ ] Register `update_confidence_display` callback
- [ ] Register `update_alert_status` callback
- [ ] Register `populate_alert_assets` callback
- [ ] Register `save_alert_preferences` callback
- [ ] Register `load_preferences_into_form` callback
- [ ] Add tests for panel components

### Task 3: Backend Alert Checking Logic
- [ ] Create `shitty_ui/alerts.py` module
- [ ] Implement `check_for_new_alerts()` function
- [ ] Implement `filter_predictions_by_preferences()` function
- [ ] Implement `is_in_quiet_hours()` function
- [ ] Implement `_extract_sentiment()` helper
- [ ] Implement `format_alert_message()` function
- [ ] Implement `format_alert_message_html()` function
- [ ] Add `get_new_predictions_since()` to `data.py`
- [ ] Register `run_alert_check` callback
- [ ] Add tests for all filtering logic
- [ ] Add tests for message formatting

### Task 4: Browser Push Notifications
- [ ] Add clientside callback for notification permission request
- [ ] Add clientside callback to trigger browser notification from store
- [ ] Create `shitty_ui/assets/service-worker.js` (optional)
- [ ] Add service worker registration callback (optional)
- [ ] Add test alert button callback
- [ ] Test in Chrome, Firefox, Safari
- [ ] Test notification click behavior

### Task 5: Email Notifications
- [ ] Add email settings to `shitpost_settings.py`
- [ ] Implement `_send_email_alert()` in `alerts.py`
- [ ] Implement `_send_via_smtp()` function
- [ ] Implement `_send_via_sendgrid()` function
- [ ] Implement `_validate_email()` helper
- [ ] Implement email rate limiting
- [ ] Add tests for email dispatch
- [ ] Test with real SMTP server (dev only)

### Task 6: SMS Alerts via Twilio
- [ ] Implement `_send_sms_alert()` in `alerts.py`
- [ ] Implement `_validate_phone_number()` helper
- [ ] Implement `_check_sms_rate_limit()` function
- [ ] Implement `_record_sms_sent()` function
- [ ] Add tests for SMS dispatch
- [ ] Add tests for phone number validation
- [ ] Add tests for rate limiting
- [ ] Test with Twilio test credentials

### Task 7: Alert History Panel
- [ ] Create `create_alert_history_panel()` function
- [ ] Add history panel to main layout
- [ ] Register `toggle_alert_history` callback
- [ ] Register `render_alert_history` callback
- [ ] Register `clear_alert_history` callback
- [ ] Add bell icon badge callbacks (clientside)
- [ ] Add tests for history rendering
- [ ] Verify localStorage cap at 100 entries

### Security & Polish
- [ ] Verify no API keys exposed in frontend
- [ ] Verify all SQL queries use parameterized inputs
- [ ] Verify rate limiting works for SMS
- [ ] Verify rate limiting works for email
- [ ] Add localStorage privacy note to UI
- [ ] Verify phone number validation before Twilio calls
- [ ] Verify email validation before SMTP/SendGrid calls
- [ ] Run `ruff check .` and `ruff format .`
- [ ] Update CHANGELOG.md

---

## Definition of Done

- [ ] All tasks implemented per checklist above
- [ ] All existing tests still pass (`pytest -v`)
- [ ] New tests added and passing (target: 30+ new tests)
- [ ] Browser notifications work in Chrome, Firefox
- [ ] Email notifications work with at least one provider (SMTP or SendGrid)
- [ ] SMS notifications work with Twilio test credentials
- [ ] Alert history shows recent alerts correctly
- [ ] Alert preferences persist across page reloads (localStorage)
- [ ] No API keys, tokens, or credentials exposed in browser
- [ ] Rate limiting prevents SMS/email abuse
- [ ] Quiet hours suppress notifications during configured times
- [ ] Code formatted with `ruff format .`
- [ ] Linting passes with `ruff check .`
- [ ] CHANGELOG.md updated with alerting system entries
- [ ] No console errors in browser dev tools
