"""Alert system callbacks and alert panel components."""

from datetime import datetime

from dash import Dash, html
import dash_bootstrap_components as dbc

from constants import COLORS
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


def create_alert_history_panel():
    """
    Create the alert history card for the main dashboard.

    Shows recent alerts with timestamp, prediction details,
    and whether they were triggered (matched preferences).
    """
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
        enabled,
        min_confidence,
        assets,
        sentiment,
        browser_on,
        email_on,
        email_addr,
        sms_on,
        sms_phone,
        quiet_on,
        quiet_start,
        quiet_end,
    ).to_dict()


def extract_preferences_tuple(prefs: dict) -> tuple:
    """Extract form field values from a preferences dict.

    Delegates to AlertPreferences.from_stored().to_form_tuple().
    Kept for backward compatibility with existing tests.
    """
    return AlertPreferences.from_stored(prefs).to_form_tuple()


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
    except (ValueError, TypeError, AttributeError):
        time_str = str(triggered_at)[:16]

    asset_str = ", ".join(assets[:3]) if isinstance(assets, list) else str(assets)

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
