"""Filter controls and period selection components."""

from datetime import datetime, timedelta

from dash import html, dcc
import dash_bootstrap_components as dbc

from constants import COLORS


def get_period_button_styles(selected: str):
    """Return button colors/outlines for each period button."""
    periods = ["7d", "30d", "90d", "all"]
    styles = []
    for p in periods:
        if p == selected:
            styles.extend(["primary", False])  # color, outline
        else:
            styles.extend(["secondary", True])
    return styles


def create_filter_controls():
    """Create filter controls for the data table."""
    return dbc.Row(
        [
            dbc.Col(
                [
                    html.Label("Confidence Range:", className="small text-muted"),
                    dcc.RangeSlider(
                        id="confidence-slider",
                        min=0,
                        max=1,
                        step=0.05,
                        value=[0, 1],
                        marks={0: "0", 0.5: "0.5", 1: "1"},
                        tooltip={"placement": "bottom", "always_visible": False},
                    ),
                ],
                md=4,
            ),
            dbc.Col(
                [
                    html.Label("Date Range:", className="small text-muted"),
                    dcc.DatePickerRange(
                        id="date-range-picker",
                        start_date=(datetime.now() - timedelta(days=90)).date(),
                        end_date=datetime.now().date(),
                        display_format="YYYY-MM-DD",
                        style={"fontSize": "0.8rem"},
                    ),
                ],
                md=4,
            ),
            dbc.Col(
                [
                    html.Label("Results:", className="small text-muted"),
                    dcc.Dropdown(
                        id="limit-selector",
                        options=[
                            {"label": "25", "value": 25},
                            {"label": "50", "value": 50},
                            {"label": "100", "value": 100},
                        ],
                        value=50,
                        clearable=False,
                        style={"fontSize": "0.9rem"},
                    ),
                ],
                md=2,
            ),
        ],
        className="g-3",
    )

