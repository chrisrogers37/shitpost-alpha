"""Header and footer navigation components."""

from dash import html, dcc
import dash_bootstrap_components as dbc

from constants import COLORS


def create_header():
    """Create the dashboard header with navigation, alert bell and refresh indicator."""
    return html.Div(
        [
            html.Div(
                [
                    # Logo and title
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
                    # Navigation links
                    html.Div(
                        [
                            dcc.Link(
                                [html.I(className="fas fa-home me-1"), "Dashboard"],
                                href="/",
                                className="nav-link-custom",
                            ),
                            dcc.Link(
                                [
                                    html.I(className="fas fa-rss me-1"),
                                    "Signals",
                                ],
                                href="/signals",
                                className="nav-link-custom",
                            ),
                            dcc.Link(
                                [
                                    html.I(className="fas fa-chart-area me-1"),
                                    "Trends",
                                ],
                                href="/trends",
                                className="nav-link-custom",
                            ),
                            dcc.Link(
                                [
                                    html.I(className="fas fa-chart-pie me-1"),
                                    "Performance",
                                ],
                                href="/performance",
                                className="nav-link-custom",
                            ),
                        ],
                        style={"display": "flex", "gap": "8px", "alignItems": "center"},
                    ),
                ],
                style={"display": "flex", "alignItems": "center", "flex": 1},
            ),
            # Right side: alert bell + refresh indicator
            html.Div(
                [
                    # Alert bell button
                    dbc.Button(
                        [
                            html.I(className="fas fa-bell", id="alert-bell-icon"),
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
                ],
                className="header-right",
                style={"display": "flex", "alignItems": "center"},
            ),
        ],
        className="header-container",
        style={
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "padding": "15px 20px",
            "borderBottom": f"1px solid {COLORS['border']}",
            "backgroundColor": COLORS["secondary"],
        },
    )


def create_footer():
    """Create the dashboard footer."""
    return html.Div(
        [
            html.Hr(style={"borderColor": COLORS["border"], "margin": "40px 0 20px 0"}),
            html.P(
                [
                    "Disclaimer: This is NOT financial advice. For entertainment and research purposes only."
                ],
                style={
                    "textAlign": "center",
                    "color": COLORS["text_muted"],
                    "fontSize": "0.8rem",
                    "fontStyle": "italic",
                },
            ),
            html.P(
                [
                    html.A(
                        [html.I(className="fab fa-github me-1"), "View Source"],
                        href="https://github.com/chrisrogers37/shitpost-alpha",
                        target="_blank",
                        style={"color": COLORS["accent"], "textDecoration": "none"},
                    )
                ],
                style={"textAlign": "center", "marginBottom": "20px"},
            ),
        ]
    )

