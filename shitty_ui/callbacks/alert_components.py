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
