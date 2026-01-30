"""
Shared UI components used across multiple pages.
Extracted from layout.py for reuse.
"""

from dash import html
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

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


def create_metric_card(
    title: str,
    value: str,
    subtitle: str = "",
    icon: str = "chart-line",
    color: str = None,
) -> dbc.Card:
    """Create a metric card component.

    Args:
        title: Label below the value (e.g., "Prediction Accuracy").
        value: The main displayed value (e.g., "65.2%").
        subtitle: Optional smaller text below the title.
        icon: Font Awesome icon name without 'fa-' prefix.
        color: Hex color for the icon and value. Defaults to accent blue.

    Returns:
        A dbc.Card component.
    """
    color = color or COLORS["accent"]
    return dbc.Card(
        [
            dbc.CardBody(
                [
                    html.Div(
                        [
                            html.I(
                                className=f"fas fa-{icon}",
                                style={"fontSize": "1.5rem", "color": color},
                            ),
                        ],
                        className="mb-2",
                    ),
                    html.H3(
                        value,
                        style={"margin": 0, "color": color, "fontWeight": "bold"},
                    ),
                    html.P(
                        title,
                        style={
                            "margin": 0,
                            "color": COLORS["text_muted"],
                            "fontSize": "0.85rem",
                        },
                    ),
                    html.Small(subtitle, style={"color": COLORS["text_muted"]})
                    if subtitle
                    else None,
                ],
                style={"textAlign": "center", "padding": "15px"},
            ),
        ],
        style={
            "backgroundColor": COLORS["secondary"],
            "border": f"1px solid {COLORS['border']}",
        },
    )


def create_empty_chart_figure(message: str = "No data available") -> go.Figure:
    """Create a placeholder figure with a centered message.

    Use this when a chart has no data to display.

    Args:
        message: Text to display in the empty chart area.

    Returns:
        A Plotly figure.
    """
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        showarrow=False,
        font=dict(color=COLORS["text_muted"], size=14),
    )
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color=COLORS["text_muted"],
        height=300,
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
    )
    return fig


def create_section_card(
    title: str,
    icon: str,
    children,
    card_id: str = None,
) -> dbc.Card:
    """Create a card with a header, used to wrap chart sections.

    Args:
        title: Card header text.
        icon: Font Awesome icon name.
        children: Content to place inside the card body.
        card_id: Optional HTML id for the card.

    Returns:
        A dbc.Card component.
    """
    card_props = {
        "className": "mb-3",
        "style": {"backgroundColor": COLORS["secondary"]},
    }
    if card_id:
        card_props["id"] = card_id

    return dbc.Card(
        [
            dbc.CardHeader(
                [
                    html.I(className=f"fas fa-{icon} me-2"),
                    title,
                ],
                className="fw-bold",
            ),
            dbc.CardBody(children),
        ],
        **card_props,
    )


def create_error_card(message: str, details: str = None) -> dbc.Card:
    """Create an error display card for graceful degradation.

    Args:
        message: Main error message to display.
        details: Optional additional details.

    Returns:
        A dbc.Card component styled for errors.
    """
    return dbc.Card(
        [
            dbc.CardBody(
                [
                    html.Div(
                        [
                            html.I(
                                className="fas fa-exclamation-triangle me-2",
                                style={"color": COLORS["danger"]},
                            ),
                            html.Span(
                                "Error Loading Data",
                                style={"color": COLORS["danger"], "fontWeight": "bold"},
                            ),
                        ],
                        className="mb-2",
                    ),
                    html.P(
                        message,
                        style={
                            "color": COLORS["text_muted"],
                            "margin": 0,
                            "fontSize": "0.9rem",
                        },
                    ),
                    html.Small(
                        details,
                        style={"color": COLORS["text_muted"], "fontSize": "0.8rem"},
                    )
                    if details
                    else None,
                ],
                style={"padding": "15px"},
            )
        ],
        style={
            "backgroundColor": COLORS["secondary"],
            "border": f"1px solid {COLORS['danger']}",
        },
    )
