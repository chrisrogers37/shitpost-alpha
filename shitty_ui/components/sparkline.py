"""Sparkline chart components for inline price visualization on signal cards."""

from datetime import date
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

from constants import COLORS, SPARKLINE_CONFIG


def build_sparkline_figure(
    price_df: pd.DataFrame,
    prediction_date: Optional[date] = None,
) -> go.Figure:
    """Build a minimal sparkline Plotly figure from price data.

    Creates a tiny line chart with no axes, no gridlines, no legend -- just
    the price line, an optional fill, and a dot marking the prediction date.

    Args:
        price_df: DataFrame with columns [date, close]. Must have >= 2 rows.
        prediction_date: Date of the prediction. If provided, a marker dot
            is drawn at this date's closing price.

    Returns:
        go.Figure configured for sparkline rendering (tiny, chrome-free).
    """
    fig = go.Figure()

    dates = price_df["date"]
    closes = price_df["close"]

    # Determine line color based on price direction
    first_close = float(closes.iloc[0])
    last_close = float(closes.iloc[-1])
    pct_change = ((last_close - first_close) / first_close) * 100 if first_close else 0

    if pct_change > 0.5:
        line_color = SPARKLINE_CONFIG["color_up"]
    elif pct_change < -0.5:
        line_color = SPARKLINE_CONFIG["color_down"]
    else:
        line_color = SPARKLINE_CONFIG["color_flat"]

    # Fill color: same as line but with low opacity
    r, g, b = (
        int(line_color[1:3], 16),
        int(line_color[3:5], 16),
        int(line_color[5:7], 16),
    )
    fill_color = f"rgba({r}, {g}, {b}, {SPARKLINE_CONFIG['fill_opacity']})"

    # Price line
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=closes,
            mode="lines",
            line=dict(
                color=line_color,
                width=SPARKLINE_CONFIG["line_width"],
            ),
            fill="tozeroy",
            fillcolor=fill_color,
            hovertemplate="%{x|%b %d}: $%{y:,.2f}<extra></extra>",
            showlegend=False,
        )
    )

    # Prediction date marker
    if prediction_date is not None:
        pred_dt = pd.Timestamp(prediction_date)
        # Find the closest date in the data
        date_diffs = (price_df["date"] - pred_dt).abs()
        closest_idx = date_diffs.idxmin()
        closest_date = price_df.loc[closest_idx, "date"]
        closest_close = float(price_df.loc[closest_idx, "close"])

        fig.add_trace(
            go.Scatter(
                x=[closest_date],
                y=[closest_close],
                mode="markers",
                marker=dict(
                    color=SPARKLINE_CONFIG["marker_color"],
                    size=SPARKLINE_CONFIG["marker_size"],
                    line=dict(width=0),
                ),
                hovertemplate="Prediction: $%{y:,.2f}<extra></extra>",
                showlegend=False,
            )
        )

    # Minimal layout: no axes, no chrome, transparent background
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=0, b=0),
        height=SPARKLINE_CONFIG["height"],
        width=SPARKLINE_CONFIG["width"],
        xaxis=dict(
            showgrid=False,
            showticklabels=False,
            zeroline=False,
            showline=False,
        ),
        yaxis=dict(
            showgrid=False,
            showticklabels=False,
            zeroline=False,
            showline=False,
        ),
        showlegend=False,
        hovermode="x unified",
    )

    return fig


def create_sparkline_component(
    price_df: pd.DataFrame,
    prediction_date: Optional[date] = None,
    component_id: str = "",
) -> dcc.Graph:
    """Create a dcc.Graph wrapping a sparkline figure.

    This is the component that gets embedded directly in signal cards.

    Args:
        price_df: DataFrame with columns [date, close]. Must have >= 2 rows.
        prediction_date: Date of the prediction for marker placement.
        component_id: Unique id for the dcc.Graph element.

    Returns:
        dcc.Graph with sparkline figure and interaction disabled.
    """
    fig = build_sparkline_figure(price_df, prediction_date)

    return dcc.Graph(
        id=component_id or f"sparkline-{id(price_df)}",
        figure=fig,
        config={
            "displayModeBar": False,
            "staticPlot": False,  # Allow hover but no zoom/pan
        },
        style={
            "width": f"{SPARKLINE_CONFIG['width']}px",
            "height": f"{SPARKLINE_CONFIG['height']}px",
            "display": "inline-block",
            "verticalAlign": "middle",
        },
    )


def create_sparkline_placeholder() -> html.Div:
    """Create a placeholder shown when no price data is available for a symbol.

    Returns:
        html.Div with a subtle "no data" indicator matching sparkline dimensions.
    """
    return html.Div(
        html.Span(
            "No price data",
            style={
                "color": COLORS["border"],
                "fontSize": "0.65rem",
                "fontStyle": "italic",
            },
        ),
        style={
            "width": f"{SPARKLINE_CONFIG['width']}px",
            "height": f"{SPARKLINE_CONFIG['height']}px",
            "display": "inline-flex",
            "alignItems": "center",
            "justifyContent": "center",
            "border": f"1px dashed {COLORS['border']}",
            "borderRadius": "4px",
        },
    )
