"""Metric and performance summary card components.

Provides KPI metric cards with hero-level visual treatment and the
asset performance comparison summary used on the asset detail page.
"""

from typing import Dict, Any

from dash import html
import dash_bootstrap_components as dbc

from constants import COLORS, FONT_SIZES, HIERARCHY


def create_metric_card(
    title: str,
    value: str,
    subtitle: str = "",
    icon: str = "chart-line",
    color: str = None,
    note: str = "",
):
    """Create a metric card component with hero-level visual treatment.

    KPI cards are the highest-priority elements on the dashboard. They use
    elevated styling with accent-colored icon backgrounds, larger value
    typography, and a subtle glow shadow to draw the eye first.
    """
    color = color or COLORS["accent"]
    return dbc.Card(
        [
            dbc.CardBody(
                [
                    # Icon with circular accent background
                    html.Div(
                        [
                            html.I(
                                className=f"fas fa-{icon}",
                                style={
                                    "fontSize": "1.1rem",
                                    "color": "#ffffff",
                                },
                            ),
                        ],
                        style={
                            "width": "40px",
                            "height": "40px",
                            "borderRadius": "50%",
                            "backgroundColor": color,
                            "display": "flex",
                            "alignItems": "center",
                            "justifyContent": "center",
                            "marginBottom": "10px",
                            "opacity": "0.9",
                        },
                    ),
                    # Value -- hero-sized, extra bold
                    html.Div(
                        value,
                        className="kpi-hero-value",
                        style={
                            "fontSize": "2rem",
                            "fontWeight": "800",
                            "color": color,
                            "lineHeight": "1.1",
                            "margin": "0 0 4px 0",
                        },
                    ),
                    # Title label
                    html.P(
                        title,
                        style={
                            "margin": 0,
                            "color": COLORS["text_muted"],
                            "fontSize": "0.82rem",
                            "fontWeight": "500",
                            "textTransform": "uppercase",
                            "letterSpacing": "0.03em",
                        },
                    ),
                    # Subtitle
                    html.Small(
                        subtitle,
                        style={
                            "color": COLORS["text_muted"],
                            "fontSize": "0.75rem",
                        },
                    )
                    if subtitle
                    else None,
                    # Optional note (e.g., "All-time" fallback from Phase 01)
                    html.Div(
                        note,
                        style={
                            "color": COLORS["warning"],
                            "fontSize": FONT_SIZES["small"],
                            "marginTop": "4px",
                        },
                    )
                    if note
                    else None,
                ],
                style={
                    "textAlign": "center",
                    "padding": "18px 15px",
                    "minHeight": "130px",
                    "display": "flex",
                    "flexDirection": "column",
                    "alignItems": "center",
                    "justifyContent": "center",
                },
            )
        ],
        className="metric-card kpi-hero-card",
        style={
            "backgroundColor": HIERARCHY["primary"]["background"],
            "border": HIERARCHY["primary"]["border"],
            "borderRadius": HIERARCHY["primary"]["border_radius"],
            "boxShadow": HIERARCHY["primary"]["shadow"],
        },
    )


def create_performance_summary(stats: Dict[str, Any]) -> html.Div:
    """
    Create the performance summary comparing this asset vs overall system.

    Args:
        stats: Dictionary from get_asset_stats()

    Returns:
        html.Div with comparison metrics
    """
    asset_accuracy = stats.get("accuracy", 0)
    overall_accuracy = stats.get("overall_accuracy", 0)
    accuracy_diff = asset_accuracy - overall_accuracy

    asset_return = stats.get("avg_return", 0)
    overall_return = stats.get("overall_avg_return", 0)
    return_diff = asset_return - overall_return

    best = stats.get("best_return")
    worst = stats.get("worst_return")

    return html.Div(
        [
            # Accuracy comparison
            html.Div(
                [
                    html.H6(
                        "Accuracy vs Overall", style={"color": COLORS["text_muted"]}
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Span(
                                        f"{asset_accuracy:.1f}%",
                                        style={
                                            "fontSize": "1.5rem",
                                            "fontWeight": "bold",
                                            "color": (
                                                COLORS["success"]
                                                if asset_accuracy > 60
                                                else COLORS["danger"]
                                            ),
                                        },
                                    ),
                                    html.Span(
                                        " this asset",
                                        style={
                                            "color": COLORS["text_muted"],
                                            "fontSize": "0.8rem",
                                        },
                                    ),
                                ]
                            ),
                            html.Div(
                                [
                                    html.Span(
                                        f"{overall_accuracy:.1f}%",
                                        style={
                                            "fontSize": "1rem",
                                            "color": COLORS["text_muted"],
                                        },
                                    ),
                                    html.Span(
                                        " overall",
                                        style={
                                            "color": COLORS["text_muted"],
                                            "fontSize": "0.8rem",
                                        },
                                    ),
                                ]
                            ),
                            html.Div(
                                [
                                    html.Span(
                                        f"{accuracy_diff:+.1f}pp",
                                        style={
                                            "color": (
                                                COLORS["success"]
                                                if accuracy_diff > 0
                                                else COLORS["danger"]
                                            ),
                                            "fontWeight": "bold",
                                            "fontSize": "0.9rem",
                                        },
                                    ),
                                    html.Span(
                                        " vs average",
                                        style={
                                            "color": COLORS["text_muted"],
                                            "fontSize": "0.8rem",
                                        },
                                    ),
                                ]
                            ),
                        ]
                    ),
                ],
                style={
                    "padding": "12px 0",
                    "borderBottom": f"1px solid {COLORS['border']}",
                },
            ),
            # Return comparison
            html.Div(
                [
                    html.H6(
                        "Avg 7-Day Return vs Overall",
                        style={"color": COLORS["text_muted"]},
                    ),
                    html.Div(
                        [
                            html.Span(
                                f"{asset_return:+.2f}%",
                                style={
                                    "fontSize": "1.2rem",
                                    "fontWeight": "bold",
                                    "color": (
                                        COLORS["success"]
                                        if asset_return > 0
                                        else COLORS["danger"]
                                    ),
                                },
                            ),
                            html.Span(
                                f" vs {overall_return:+.2f}% overall",
                                style={
                                    "color": COLORS["text_muted"],
                                    "fontSize": "0.85rem",
                                    "marginLeft": "10px",
                                },
                            ),
                            html.Span(
                                f" ({return_diff:+.2f}pp)",
                                style={
                                    "color": (
                                        COLORS["success"]
                                        if return_diff > 0
                                        else COLORS["danger"]
                                    ),
                                    "fontSize": "0.85rem",
                                    "marginLeft": "5px",
                                },
                            ),
                        ]
                    ),
                ],
                style={
                    "padding": "12px 0",
                    "borderBottom": f"1px solid {COLORS['border']}",
                },
            ),
            # Best/Worst predictions
            html.Div(
                [
                    html.H6(
                        "Best / Worst Predictions",
                        style={"color": COLORS["text_muted"]},
                    ),
                    html.Div(
                        [
                            html.Span(
                                f"Best: {best:+.2f}%"
                                if best is not None
                                else "Best: --",
                                style={
                                    "color": COLORS["success"],
                                    "fontSize": "0.9rem",
                                    "fontWeight": "bold",
                                },
                            ),
                            html.Span(" | ", style={"color": COLORS["border"]}),
                            html.Span(
                                f"Worst: {worst:+.2f}%"
                                if worst is not None
                                else "Worst: --",
                                style={
                                    "color": COLORS["danger"],
                                    "fontSize": "0.9rem",
                                    "fontWeight": "bold",
                                },
                            ),
                        ]
                    ),
                ],
                style={"padding": "12px 0"},
            ),
        ]
    )
