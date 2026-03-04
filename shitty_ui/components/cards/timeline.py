"""Prediction timeline and related asset link components.

Provides timeline cards for the asset detail page showing individual
predictions with price changes, and clickable related-asset links.
"""

from datetime import datetime

from dash import html, dcc

from constants import COLORS
from components.cards import strip_urls, get_sentiment_style
from components.utils import safe_get


def create_prediction_timeline_card(row: dict) -> html.Div:
    """
    Create a single prediction card for the timeline.

    Args:
        row: Dictionary with keys from get_asset_predictions() DataFrame row

    Returns:
        html.Div component for one timeline entry
    """
    prediction_date = safe_get(row, "prediction_date")
    timestamp = safe_get(row, "timestamp")
    tweet_text = safe_get(row, "text", "")
    sentiment = safe_get(row, "prediction_sentiment", "neutral")
    confidence = safe_get(row, "prediction_confidence", 0)
    return_t7 = safe_get(row, "return_t7")
    correct_t7 = safe_get(row, "correct_t7")
    pnl_t7 = safe_get(row, "pnl_t7")
    price_at = safe_get(row, "price_at_prediction")
    price_after = safe_get(row, "price_t7")

    # Sentiment styling
    s_style = get_sentiment_style(sentiment)
    sentiment_color = s_style["color"]
    sentiment_icon = s_style["icon"]
    sentiment_bg = s_style["bg_color"]

    # Outcome badge
    if correct_t7 is True:
        outcome_badge = html.Span(
            "Correct",
            className="badge",
            style={
                "backgroundColor": COLORS["success"],
                "marginLeft": "8px",
            },
        )
    elif correct_t7 is False:
        outcome_badge = html.Span(
            "Incorrect",
            className="badge",
            style={
                "backgroundColor": COLORS["danger"],
                "marginLeft": "8px",
            },
        )
    else:
        outcome_badge = html.Span(
            "Pending",
            className="badge",
            style={
                "backgroundColor": COLORS["warning"],
                "color": "#000",
                "marginLeft": "8px",
            },
        )

    # Format the date
    if isinstance(prediction_date, datetime):
        date_str = prediction_date.strftime("%b %d, %Y")
    elif hasattr(prediction_date, "strftime"):
        date_str = prediction_date.strftime("%b %d, %Y")
    else:
        date_str = str(prediction_date)[:10] if prediction_date else "Unknown"

    # Format timestamp for the tweet time
    if isinstance(timestamp, datetime):
        time_str = timestamp.strftime("%H:%M")
    else:
        time_str = str(timestamp)[11:16] if timestamp else ""

    # Truncate tweet text
    tweet_text = strip_urls(tweet_text)
    display_text = tweet_text[:200] + "..." if len(tweet_text) > 200 else tweet_text

    # Price change display
    price_info = []
    if price_at is not None:
        price_info.append(
            html.Span(
                f"Entry: ${price_at:,.2f}",
                style={"color": COLORS["text_muted"], "fontSize": "0.8rem"},
            )
        )
    if price_after is not None:
        price_info.append(
            html.Span(
                f" -> ${price_after:,.2f} (7d)",
                style={"color": COLORS["text_muted"], "fontSize": "0.8rem"},
            )
        )

    return html.Div(
        [
            # Top row: date, sentiment, outcome badge
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(
                                date_str,
                                style={
                                    "fontWeight": "bold",
                                    "color": COLORS["text"],
                                    "fontSize": "0.9rem",
                                },
                            ),
                            html.Span(
                                f" at {time_str}" if time_str else "",
                                style={
                                    "color": COLORS["text_muted"],
                                    "fontSize": "0.8rem",
                                },
                            ),
                            outcome_badge,
                        ]
                    ),
                    html.Div(
                        [
                            html.I(
                                className=f"fas fa-{sentiment_icon} me-1",
                                style={"color": sentiment_color},
                            ),
                            html.Span(
                                (sentiment or "neutral").upper(),
                                style={
                                    "color": sentiment_color,
                                    "backgroundColor": sentiment_bg,
                                    "padding": "2px 8px",
                                    "borderRadius": "4px",
                                    "fontWeight": "bold",
                                    "fontSize": "0.85rem",
                                },
                            ),
                            html.Span(
                                f" | {confidence:.0%}" if confidence else "",
                                style={
                                    "color": COLORS["text_muted"],
                                    "fontSize": "0.85rem",
                                    "marginLeft": "10px",
                                },
                            ),
                        ],
                        style={"marginTop": "4px"},
                    ),
                ]
            ),
            # Tweet text
            html.P(
                display_text,
                style={
                    "fontSize": "0.85rem",
                    "color": COLORS["text_muted"],
                    "margin": "8px 0",
                    "lineHeight": "1.5",
                    "fontStyle": "italic",
                    "borderLeft": f"3px solid {sentiment_color}",
                    "paddingLeft": "12px",
                },
            ),
            # Metrics row: return, P&L, prices
            html.Div(
                [
                    # 7-day return
                    html.Span(
                        f"Return (7d): {return_t7:+.2f}%"
                        if return_t7 is not None
                        else "Return (7d): --",
                        style={
                            "color": (
                                COLORS["success"]
                                if return_t7 and return_t7 > 0
                                else COLORS["danger"]
                                if return_t7 and return_t7 < 0
                                else COLORS["text_muted"]
                            ),
                            "fontSize": "0.85rem",
                            "fontWeight": "bold",
                        },
                    ),
                    html.Span(" | ", style={"color": COLORS["border"]}),
                    # P&L
                    html.Span(
                        f"P&L: ${pnl_t7:+,.0f}" if pnl_t7 is not None else "P&L: --",
                        style={
                            "color": (
                                COLORS["success"]
                                if pnl_t7 and pnl_t7 > 0
                                else COLORS["danger"]
                                if pnl_t7 and pnl_t7 < 0
                                else COLORS["text_muted"]
                            ),
                            "fontSize": "0.85rem",
                        },
                    ),
                    html.Span(" | ", style={"color": COLORS["border"]}),
                    # Price info
                    *price_info,
                ],
                style={"marginBottom": "4px"},
            ),
        ],
        style={
            "padding": "16px",
            "borderBottom": f"1px solid {COLORS['border']}",
            "borderLeft": f"3px solid {sentiment_color}",
        },
    )


def create_related_asset_link(row: dict) -> html.Div:
    """
    Create a clickable link for a related asset.

    Args:
        row: Dictionary with keys: related_symbol, co_occurrence_count, avg_return

    Returns:
        html.Div component
    """
    symbol = safe_get(row, "related_symbol", "???")
    count = safe_get(row, "co_occurrence_count", 0)
    avg_return = safe_get(row, "avg_return")

    return_color = COLORS["text_muted"]
    return_str = "--"
    if avg_return is not None:
        return_color = COLORS["success"] if avg_return > 0 else COLORS["danger"]
        return_str = f"{avg_return:+.2f}%"

    return html.Div(
        [
            dcc.Link(
                html.Span(
                    symbol,
                    style={
                        "fontWeight": "bold",
                        "color": COLORS["accent"],
                        "fontSize": "0.95rem",
                    },
                ),
                href=f"/assets/{symbol}",
                style={"textDecoration": "none"},
            ),
            html.Span(
                f" ({count} shared predictions)",
                style={
                    "color": COLORS["text_muted"],
                    "fontSize": "0.8rem",
                    "marginLeft": "8px",
                },
            ),
            html.Span(
                f" | Avg return: {return_str}",
                style={
                    "color": return_color,
                    "fontSize": "0.8rem",
                    "marginLeft": "8px",
                },
            ),
        ],
        style={
            "padding": "10px 0",
            "borderBottom": f"1px solid {COLORS['border']}",
        },
    )
