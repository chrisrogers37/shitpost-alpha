"""Reusable Plotly chart builders for the Shitty UI dashboard."""

from datetime import timedelta

import pandas as pd
import plotly.graph_objects as go

from constants import (
    COLORS,
    SENTIMENT_COLORS,
    MARKER_CONFIG,
    TIMEFRAME_COLORS,
    CHART_LAYOUT,
    CHART_COLORS,
)


def apply_chart_layout(
    fig: go.Figure,
    height: int = 300,
    show_legend: bool = False,
    **overrides,
) -> go.Figure:
    """Apply the shared chart layout to a Plotly figure.

    Merges CHART_LAYOUT base with caller-specific overrides.
    Always call this LAST, after adding traces, so it can override
    any trace-level defaults that Plotly might have set on the layout.

    Args:
        fig: The Plotly figure to style.
        height: Chart height in pixels.
        show_legend: Whether to show the legend.
        **overrides: Additional layout keys to override (e.g.,
            yaxis=dict(title="Accuracy %", range=[0, 105])).

    Returns:
        The same figure, mutated in place (also returned for chaining).
    """
    layout = {**CHART_LAYOUT}
    layout["height"] = height
    layout["showlegend"] = show_legend

    for axis_key in ("xaxis", "yaxis"):
        if axis_key in overrides:
            base_axis = {**layout.get(axis_key, {})}
            base_axis.update(overrides.pop(axis_key))
            layout[axis_key] = base_axis

    layout.update(overrides)
    fig.update_layout(**layout)
    return fig


def build_signal_over_trend_chart(
    prices_df: pd.DataFrame,
    signals_df: pd.DataFrame,
    symbol: str = "",
    show_timeframe_windows: bool = False,
    chart_height: int = 500,
) -> go.Figure:
    """
    Build a candlestick chart with prediction signal markers overlaid.

    Args:
        prices_df: DataFrame with columns: date, open, high, low, close, volume
        signals_df: DataFrame with columns: prediction_date, prediction_sentiment,
                    prediction_confidence, thesis, correct_t7, return_t7, pnl_t7,
                    post_text, price_at_prediction
        symbol: Ticker symbol for chart title
        show_timeframe_windows: If True, draw shaded regions for t7 windows
        chart_height: Height of the chart in pixels

    Returns:
        go.Figure ready to be rendered by dcc.Graph
    """
    fig = go.Figure()

    # --- Trace 1: Candlestick ---
    if not prices_df.empty:
        fig.add_trace(
            go.Candlestick(
                x=prices_df["date"],
                open=prices_df["open"],
                high=prices_df["high"],
                low=prices_df["low"],
                close=prices_df["close"],
                name=symbol or "Price",
                increasing_line_color=CHART_COLORS["candle_up"],
                decreasing_line_color=CHART_COLORS["candle_down"],
                increasing_fillcolor=CHART_COLORS["candle_up_fill"],
                decreasing_fillcolor=CHART_COLORS["candle_down_fill"],
                showlegend=False,
            )
        )

    # --- Trace 2: Signal Markers ---
    if not signals_df.empty and not prices_df.empty:
        for _, signal in signals_df.iterrows():
            pred_date = signal["prediction_date"]
            sentiment = (signal.get("prediction_sentiment") or "neutral").lower()
            confidence = signal.get("prediction_confidence") or 0.5
            thesis = signal.get("thesis") or ""
            correct_t7 = signal.get("correct_t7")
            return_t7 = signal.get("return_t7")
            pnl_t7 = signal.get("pnl_t7")
            post_text = signal.get("post_text") or ""

            # Find the price at this date for y-placement
            price_row = prices_df[prices_df["date"].dt.date == pred_date.date()]
            if price_row.empty:
                continue

            y_val = float(price_row.iloc[0]["high"]) * 1.03

            # Color from sentiment
            marker_color = SENTIMENT_COLORS.get(sentiment, SENTIMENT_COLORS["neutral"])

            # Size from confidence (scale min_size to max_size)
            size_range = MARKER_CONFIG["max_size"] - MARKER_CONFIG["min_size"]
            marker_size = MARKER_CONFIG["min_size"] + (confidence * size_range)

            # Shape from sentiment
            marker_symbol = MARKER_CONFIG["symbols"].get(
                sentiment, MARKER_CONFIG["symbols"]["neutral"]
            )

            # Outcome text for tooltip
            if correct_t7 is True:
                outcome_text = "CORRECT"
            elif correct_t7 is False:
                outcome_text = "INCORRECT"
            else:
                outcome_text = "PENDING"

            # Build hover text
            thesis_preview = (thesis[:100] + "...") if len(thesis) > 100 else thesis
            post_preview = (
                (post_text[:80] + "...") if len(post_text) > 80 else post_text
            )

            hover_parts = [
                f"<b>{pred_date.strftime('%Y-%m-%d')}</b>",
                f"Sentiment: <b>{sentiment.upper()}</b>",
                f"Confidence: <b>{confidence:.0%}</b>",
                f"Outcome: <b>{outcome_text}</b>",
            ]
            if return_t7 is not None:
                hover_parts.append(f"7d Return: <b>{return_t7:+.2f}%</b>")
            if pnl_t7 is not None:
                hover_parts.append(f"P&L: <b>${pnl_t7:+,.0f}</b>")
            if thesis_preview:
                hover_parts.append(f"<br><i>{thesis_preview}</i>")

            hover_text = "<br>".join(hover_parts)

            fig.add_trace(
                go.Scatter(
                    x=[pred_date],
                    y=[y_val],
                    mode="markers",
                    marker=dict(
                        size=marker_size,
                        color=marker_color,
                        symbol=marker_symbol,
                        opacity=MARKER_CONFIG["opacity"],
                        line=dict(
                            width=MARKER_CONFIG["border_width"],
                            color=COLORS["text"],
                        ),
                    ),
                    hovertemplate=hover_text + "<extra></extra>",
                    showlegend=False,
                    name=f"{sentiment} signal",
                )
            )

            # --- Optional: Timeframe windows ---
            if show_timeframe_windows and not price_row.empty:
                _add_timeframe_window(fig, pred_date)

    # --- Layout ---
    apply_chart_layout(
        fig,
        height=chart_height,
        show_legend=False,
        hovermode="closest",
        margin={"l": 50, "r": 20, "t": 30, "b": 40},
        xaxis={"rangeslider": {"visible": False}},
        yaxis={"title": "Price ($)"},
    )

    # Add a custom legend for sentiment markers
    _add_sentiment_legend(fig)

    return fig


def _add_timeframe_window(
    fig: go.Figure,
    pred_date: pd.Timestamp,
) -> None:
    """Add a shaded rectangle for the 7-day evaluation window."""
    t7_end = pred_date + timedelta(days=7)
    fig.add_vrect(
        x0=pred_date,
        x1=t7_end,
        fillcolor=TIMEFRAME_COLORS["t7"],
        layer="below",
        line_width=0,
    )


def _add_sentiment_legend(fig: go.Figure) -> None:
    """Add invisible traces to serve as a sentiment color legend."""
    for sentiment, color in SENTIMENT_COLORS.items():
        symbol = MARKER_CONFIG["symbols"][sentiment]
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker=dict(size=10, color=color, symbol=symbol),
                name=sentiment.capitalize(),
                showlegend=True,
            )
        )

    fig.update_layout(
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color=COLORS["text_muted"], size=11),
        ),
    )


def build_empty_signal_chart(message: str = "No data available") -> go.Figure:
    """Build an empty chart with a centered message."""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        showarrow=False,
        font=dict(color=COLORS["text_muted"], size=14),
    )
    apply_chart_layout(
        fig,
        height=400,
        xaxis={"showgrid": False, "showticklabels": False, "zeroline": False},
        yaxis={"showgrid": False, "showticklabels": False, "zeroline": False},
    )
    return fig


def build_annotated_price_chart(
    prices_df: pd.DataFrame,
    signals_df: pd.DataFrame,
    symbol: str = "",
    chart_height: int = 450,
) -> go.Figure:
    """
    Build a line chart of closing prices with vertical annotation lines
    marking each shitpost prediction date.

    This replaces the candlestick chart for the asset detail page. The
    design prioritizes the "Trump posted, then the market moved" correlation
    by drawing full-height vertical lines at each prediction date, color-coded
    by predicted sentiment.

    Args:
        prices_df: DataFrame with columns: date, open, high, low, close, volume.
            Must be sorted by date ascending.
        signals_df: DataFrame with columns: prediction_date, prediction_sentiment,
            prediction_confidence, thesis, correct_t7, return_t7, pnl_t7, post_text,
            price_at_prediction. Can be empty.
        symbol: Ticker symbol for axis labeling.
        chart_height: Height of the chart in pixels.

    Returns:
        go.Figure ready to be rendered by dcc.Graph.
    """
    if prices_df.empty:
        return build_empty_signal_chart(f"No price data for {symbol}")

    fig = go.Figure()

    # --- Trace 1: Price Line ---
    fig.add_trace(
        go.Scatter(
            x=prices_df["date"],
            y=prices_df["close"],
            mode="lines",
            line=dict(
                color=CHART_COLORS["line_accent"],
                width=2,
            ),
            fill="tozeroy",
            fillcolor=CHART_COLORS["line_accent_fill"],
            name=f"{symbol} Close",
            showlegend=False,
            hovertemplate=(
                "<b>%{x|%b %d, %Y}</b><br>Close: <b>$%{y:,.2f}</b><extra></extra>"
            ),
        )
    )

    # --- Compute y-axis range with headroom for markers ---
    y_min = float(prices_df["close"].min()) * 0.97
    y_max = float(prices_df["close"].max()) * 1.07
    y_marker = float(prices_df["close"].max()) * 1.04

    # --- Vertical lines + marker dots for signals ---
    if not signals_df.empty:
        marker_dates = []
        marker_colors = []
        customdata_rows = []

        for _, signal in signals_df.iterrows():
            pred_date = signal["prediction_date"]
            sentiment = (signal.get("prediction_sentiment") or "neutral").lower()
            confidence = signal.get("prediction_confidence") or 0.5
            correct_t7 = signal.get("correct_t7")
            return_t7 = signal.get("return_t7")
            pnl_t7 = signal.get("pnl_t7")
            post_text = signal.get("post_text") or ""

            sentiment_color = SENTIMENT_COLORS.get(
                sentiment, SENTIMENT_COLORS["neutral"]
            )

            # --- Vertical annotation line ---
            fig.add_shape(
                type="line",
                x0=pred_date,
                x1=pred_date,
                y0=0,
                y1=1,
                yref="paper",
                line=dict(
                    color=sentiment_color,
                    width=1.5,
                    dash="solid",
                ),
                opacity=0.4,
                layer="below",
            )

            # --- Collect marker data ---
            marker_dates.append(pred_date)
            marker_colors.append(sentiment_color)

            post_snippet = (
                (post_text[:80] + "...") if len(post_text) > 80 else post_text
            )
            conf_str = f"{confidence:.0%}"

            if correct_t7 is True:
                outcome_str = "CORRECT"
            elif correct_t7 is False:
                outcome_str = "INCORRECT"
            else:
                outcome_str = "PENDING"

            return_str = f"{return_t7:+.2f}%" if pd.notna(return_t7) else "PENDING"
            pnl_str = f"${pnl_t7:+,.0f}" if pd.notna(pnl_t7) else "N/A"

            customdata_rows.append(
                [
                    post_snippet,
                    sentiment.upper(),
                    conf_str,
                    return_str,
                    outcome_str,
                    pnl_str,
                ]
            )

        # --- Trace 2: Marker dots (single batched trace) ---
        if marker_dates:
            fig.add_trace(
                go.Scatter(
                    x=marker_dates,
                    y=[y_marker] * len(marker_dates),
                    mode="markers",
                    marker=dict(
                        size=8,
                        color=marker_colors,
                        symbol="circle",
                        line=dict(
                            width=1.5,
                            color=COLORS["text"],
                        ),
                    ),
                    customdata=customdata_rows,
                    hovertemplate=(
                        "<b>%{customdata[0]}</b><br>"
                        "Sentiment: <b>%{customdata[1]}</b><br>"
                        "Confidence: <b>%{customdata[2]}</b><br>"
                        "7d Return: <b>%{customdata[3]}</b><br>"
                        "Outcome: <b>%{customdata[4]}</b><br>"
                        "P&L: <b>%{customdata[5]}</b>"
                        "<extra></extra>"
                    ),
                    showlegend=False,
                    name="Shitpost Signals",
                )
            )

    # --- Layout ---
    apply_chart_layout(
        fig,
        height=chart_height,
        show_legend=False,
        hovermode="closest",
        margin={"l": 50, "r": 20, "t": 30, "b": 40},
        yaxis={
            "title": "Price ($)",
            "range": [y_min, y_max],
        },
    )

    # --- Sentiment legend ---
    _add_annotation_legend(fig)

    return fig


def _add_annotation_legend(fig: go.Figure) -> None:
    """Add invisible scatter traces as a legend for annotation line colors."""
    for sentiment, color in SENTIMENT_COLORS.items():
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker=dict(size=8, color=color, symbol="circle"),
                name=sentiment.capitalize(),
                showlegend=True,
            )
        )
    fig.update_layout(
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color=COLORS["text_muted"], size=11),
        ),
    )
