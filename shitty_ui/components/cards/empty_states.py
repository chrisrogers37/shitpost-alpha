"""Empty state and error card components.

Provides placeholder UI for error conditions, missing data, and sections
that have no content yet -- both as Plotly figures and Dash HTML components.
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from constants import COLORS
from brand_copy import COPY


def create_error_card(message: str, details: str = None):
    """Create an error display card for graceful degradation."""
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
                                COPY["card_error_title"],
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


def create_empty_chart(message: str = "No data available"):
    """Create an empty chart with a message for error states."""
    fig = go.Figure()
    fig.add_annotation(
        text=message, showarrow=False, font=dict(color=COLORS["text_muted"], size=14)
    )
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color=COLORS["text_muted"],
        height=250,
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
    )
    return fig


def create_empty_state_chart(
    message: str = "No data available",
    hint: str = "",
    icon: str = "\u2139\ufe0f",
    height: int = 80,
    context_line: str = "",
    action_text: str = "",
) -> go.Figure:
    """Create a compact empty-state chart for sections with no data.

    Unlike create_empty_chart(), this produces a shorter, visually subtle
    figure designed to minimize wasted vertical space while informing the
    user why data is missing and when to expect it.

    Args:
        message: Primary message (e.g., "No accuracy data yet").
        hint: Secondary hint explaining what needs to happen
              (e.g., "Predictions need 7+ days to mature").
        icon: Unicode icon prefix for the message. Default info icon.
        height: Figure height in pixels. Default 80.
        context_line: Data-driven secondary line (e.g., "74 evaluated trades all-time").
        action_text: Navigation hint (e.g., "Try expanding to All").

    Returns:
        A Plotly go.Figure with centered annotation text and minimal chrome.
    """
    display_text = f"{icon}  {message}"
    if hint:
        display_text += (
            f"<br><span style='font-size:11px; color:{COLORS['border']}'>{hint}</span>"
        )
    if context_line:
        display_text += f"<br><span style='font-size:11px; color:{COLORS['text_muted']}'>{context_line}</span>"
    if action_text:
        display_text += f"<br><span style='font-size:11px; color:{COLORS['accent']}'>{action_text}</span>"

    extra_lines = sum(1 for x in [context_line, action_text] if x)
    if extra_lines > 0 and height == 80:
        height = 80 + (extra_lines * 18)

    fig = go.Figure()
    fig.add_annotation(
        text=display_text,
        showarrow=False,
        font=dict(color=COLORS["text_muted"], size=13),
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
    )
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color=COLORS["text_muted"],
        height=height,
        margin=dict(l=0, r=0, t=10, b=10),
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
    )
    return fig


def create_empty_state_html(
    message: str,
    hint: str = "",
    context_line: str = "",
    action_text: str = "",
    action_href: str = "",
    icon_class: str = "fas fa-moon",
) -> html.Div:
    """Create an HTML empty-state card with contextual guidance.

    For sections that render Dash components (hero section, signal lists)
    rather than Plotly figures.

    Args:
        message: Primary message.
        hint: Secondary hint in muted border color.
        context_line: Data-driven secondary line.
        action_text: Navigation hint text.
        action_href: If provided, wraps action_text in a dcc.Link.
        icon_class: Font Awesome icon class.

    Returns:
        html.Div styled as a centered empty state card.
    """
    children = [
        html.I(className=f"{icon_class} me-2", style={"color": COLORS["text_muted"]}),
        html.Span(message, style={"color": COLORS["text_muted"], "fontSize": "0.9rem"}),
    ]

    sub_children = []
    if hint:
        sub_children.append(
            html.Div(
                hint,
                style={
                    "color": COLORS["border"],
                    "fontSize": "0.8rem",
                    "marginTop": "6px",
                },
            )
        )
    if context_line:
        sub_children.append(
            html.Div(
                context_line,
                style={
                    "color": COLORS["text_muted"],
                    "fontSize": "0.8rem",
                    "marginTop": "4px",
                },
            )
        )
    if action_text:
        action_content = (
            dcc.Link(
                action_text,
                href=action_href,
                style={
                    "color": COLORS["accent"],
                    "fontSize": "0.8rem",
                    "textDecoration": "none",
                },
            )
            if action_href
            else html.Span(
                action_text,
                style={
                    "color": COLORS["accent"],
                    "fontSize": "0.8rem",
                },
            )
        )
        sub_children.append(html.Div(action_content, style={"marginTop": "4px"}))

    return html.Div(
        [html.Div(children), *sub_children],
        style={
            "padding": "24px",
            "textAlign": "center",
            "backgroundColor": COLORS["secondary"],
            "borderRadius": "12px",
            "border": f"1px solid {COLORS['border']}",
        },
    )
