"""
Shared navigation bar for the multi-page dashboard.
Provides consistent navigation across all pages.
"""

from dash import html
import dash_bootstrap_components as dbc

COLORS = {
    "primary": "#1e293b",
    "secondary": "#334155",
    "accent": "#3b82f6",
    "text": "#f1f5f9",
    "text_muted": "#94a3b8",
    "border": "#475569",
}


def create_navbar() -> dbc.Navbar:
    """Create the shared navigation bar."""
    return dbc.Navbar(
        dbc.Container(
            [
                # Brand / logo
                dbc.NavbarBrand(
                    html.Span(
                        [
                            html.Span(
                                "Shitpost Alpha",
                                style={"color": COLORS["accent"], "fontWeight": "bold"},
                            ),
                        ]
                    ),
                    href="/",
                    className="me-auto",
                ),
                # Navigation links
                dbc.Nav(
                    [
                        dbc.NavItem(
                            dbc.NavLink(
                                [html.I(className="fas fa-home me-1"), "Dashboard"],
                                href="/",
                                active="exact",
                                style={"color": COLORS["text"]},
                            )
                        ),
                        dbc.NavItem(
                            dbc.NavLink(
                                [
                                    html.I(className="fas fa-chart-line me-1"),
                                    "Performance",
                                ],
                                href="/performance",
                                active="exact",
                                style={"color": COLORS["text"]},
                            )
                        ),
                    ],
                    navbar=True,
                ),
                # Auto-refresh indicator
                html.Div(
                    [
                        html.Span(
                            id="refresh-countdown",
                            children="Auto-refresh: 5:00",
                            style={
                                "color": COLORS["text_muted"],
                                "fontSize": "0.8rem",
                            },
                        ),
                    ]
                ),
            ],
            fluid=True,
        ),
        color=COLORS["secondary"],
        dark=True,
        style={"borderBottom": f"1px solid {COLORS['border']}"},
    )
