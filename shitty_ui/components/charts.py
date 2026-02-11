"""Reusable Plotly chart builders for the Shitty UI dashboard."""

from datetime import timedelta

import pandas as pd
import plotly.graph_objects as go

from constants import COLORS, SENTIMENT_COLORS, MARKER_CONFIG, TIMEFRAME_COLORS


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
                increasing_line_color=COLORS["success"],
                decreasing_line_color=COLORS["danger"],
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
            post_preview = (post_text[:80] + "...") if len(post_text) > 80 else post_text

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
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color=COLORS["text"],
        margin=dict(l=50, r=20, t=30, b=40),
        xaxis=dict(
            gridcolor=COLORS["border"],
            rangeslider=dict(visible=False),
        ),
        yaxis=dict(
            gridcolor=COLORS["border"],
            title="Price ($)",
        ),
        height=chart_height,
        showlegend=False,
        hovermode="closest",
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
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color=COLORS["text_muted"],
        height=400,
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
    )
    return fig
