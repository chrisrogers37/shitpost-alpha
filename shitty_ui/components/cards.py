"""Reusable card and chart components for the Shitty UI dashboard."""

import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from constants import COLORS, FONT_SIZES, SENTIMENT_COLORS, SENTIMENT_BG_COLORS


def strip_urls(text: str) -> str:
    """Remove URLs from text for card preview display.

    Strips http/https URLs from post text so that card previews
    show meaningful content instead of long URL strings. Collapses
    any resulting double-spaces and strips leading/trailing whitespace.

    Args:
        text: Raw post text that may contain URLs.

    Returns:
        Text with URLs removed. If the text was nothing but URLs,
        returns "[link]" as a fallback so the card is never empty.
    """
    # Match http:// and https:// URLs (greedy, non-whitespace)
    cleaned = re.sub(r"https?://\S+", "", text)
    # Collapse multiple spaces left behind by removed URLs
    cleaned = re.sub(r"  +", " ", cleaned)
    # Strip leading/trailing whitespace
    cleaned = cleaned.strip()
    # If stripping URLs left nothing, show a placeholder
    if not cleaned:
        return "[link]"
    return cleaned


def get_sentiment_style(sentiment: str) -> dict:
    """Return color, icon, and background for a sentiment value.

    Args:
        sentiment: One of 'bullish', 'bearish', or 'neutral'.

    Returns:
        Dict with keys: color, icon, bg_color.
    """
    sentiment = (sentiment or "neutral").lower()
    return {
        "color": SENTIMENT_COLORS.get(sentiment, SENTIMENT_COLORS["neutral"]),
        "icon": {
            "bullish": "arrow-up",
            "bearish": "arrow-down",
            "neutral": "minus",
        }.get(sentiment, "minus"),
        "bg_color": SENTIMENT_BG_COLORS.get(sentiment, SENTIMENT_BG_COLORS["neutral"]),
    }


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

    Returns:
        A Plotly go.Figure with centered annotation text and minimal chrome.
    """
    display_text = f"{icon}  {message}"
    if hint:
        display_text += f"<br><span style='font-size:11px; color:{COLORS['border']}'>{hint}</span>"

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


def create_hero_signal_card(row) -> html.Div:
    """Create a hero signal card for a high-confidence prediction."""
    timestamp = row.get("timestamp")
    text_content = row.get("text", "")
    text_content = strip_urls(text_content)
    preview = text_content[:200] + "..." if len(text_content) > 200 else text_content
    confidence = row.get("confidence", 0)
    assets = row.get("assets", [])
    market_impact = row.get("market_impact", {})
    # Derive outcome from aggregated counts (new dedup columns)
    # Fall back to correct_t7 for backward compatibility
    outcome_count = row.get("outcome_count", 0) or 0
    correct_count = row.get("correct_count", 0) or 0
    incorrect_count = row.get("incorrect_count", 0) or 0
    total_pnl_t7 = row.get("total_pnl_t7")

    if outcome_count > 0 and correct_count + incorrect_count > 0:
        # At least some outcomes evaluated -- majority wins
        correct_t7 = correct_count > incorrect_count
    elif "correct_t7" in row.index if hasattr(row, "index") else "correct_t7" in row:
        # Backward compatibility: use single correct_t7 if available
        correct_t7 = row.get("correct_t7")
    else:
        correct_t7 = None  # Pending

    # Determine sentiment
    sentiment = "neutral"
    if isinstance(market_impact, dict) and market_impact:
        first_sentiment = list(market_impact.values())[0]
        if isinstance(first_sentiment, str):
            sentiment = first_sentiment.lower()

    # Format time ago
    if isinstance(timestamp, datetime):
        delta = datetime.now() - timestamp
        if delta.days > 0:
            time_ago = f"{delta.days}d ago"
        elif delta.seconds >= 3600:
            time_ago = f"{delta.seconds // 3600}h ago"
        else:
            time_ago = f"{delta.seconds // 60}m ago"
    else:
        time_ago = str(timestamp)[:16] if timestamp else ""

    # Asset string
    asset_str = ", ".join(assets[:4]) if isinstance(assets, list) else str(assets)

    # Sentiment styling
    s_style = get_sentiment_style(sentiment)
    s_color = s_style["color"]
    s_bg = s_style["bg_color"]
    # Hero cards use trend icons (different from standard arrow icons)
    s_icon = {
        "bullish": "arrow-trend-up",
        "bearish": "arrow-trend-down",
        "neutral": "minus",
    }.get(sentiment, "minus")

    # Outcome badge -- uses aggregated P&L when available
    pnl_display = total_pnl_t7 if total_pnl_t7 is not None else row.get("pnl_t7")
    if correct_t7 is True:
        outcome = html.Span(
            [
                html.I(className="fas fa-check me-1"),
                f"+${pnl_display:,.0f}" if pnl_display else "Correct",
            ],
            style={
                "color": COLORS["success"],
                "fontWeight": "600",
                "fontSize": "0.8rem",
            },
        )
    elif correct_t7 is False:
        outcome = html.Span(
            [
                html.I(className="fas fa-times me-1"),
                f"${pnl_display:,.0f}" if pnl_display else "Incorrect",
            ],
            style={
                "color": COLORS["danger"],
                "fontWeight": "600",
                "fontSize": "0.8rem",
            },
        )
    else:
        outcome = html.Span(
            [html.I(className="fas fa-clock me-1"), "Pending"],
            style={
                "color": COLORS["warning"],
                "fontWeight": "600",
                "fontSize": "0.8rem",
            },
        )

    return html.Div(
        [
            # Top row: time ago + outcome
            html.Div(
                [
                    html.Span(
                        time_ago,
                        style={
                            "color": COLORS["text_muted"],
                            "fontSize": "0.75rem",
                        },
                    ),
                    outcome,
                ],
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "marginBottom": "8px",
                },
            ),
            # Post preview
            html.P(
                preview,
                style={
                    "fontSize": "0.85rem",
                    "margin": "0 0 10px 0",
                    "lineHeight": "1.5",
                    "color": COLORS["text"],
                },
            ),
            # Bottom row: sentiment badge + assets + confidence
            html.Div(
                [
                    html.Span(
                        [
                            html.I(className=f"fas fa-{s_icon} me-1"),
                            sentiment.upper(),
                        ],
                        className="sentiment-badge",
                        style={
                            "backgroundColor": s_bg,
                            "color": s_color,
                        },
                    ),
                    html.Span(
                        asset_str,
                        style={
                            "color": COLORS["accent"],
                            "fontSize": "0.8rem",
                            "fontWeight": "600",
                        },
                    ),
                    html.Span(
                        f"{confidence:.0%}",
                        style={
                            "color": COLORS["text_muted"],
                            "fontSize": "0.8rem",
                        },
                    ),
                ],
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "gap": "12px",
                    "flexWrap": "wrap",
                },
            ),
        ],
        className="hero-signal-card",
        style={
            "padding": "16px",
            "backgroundColor": COLORS["secondary"],
            "border": f"1px solid {COLORS['border']}",
            "borderLeft": f"3px solid {s_color}",
            "flex": "1 1 0",
            "minWidth": "280px",
        },
    )


def create_metric_card(
    title: str,
    value: str,
    subtitle: str = "",
    icon: str = "chart-line",
    color: str = None,
    note: str = "",
):
    """Create a metric card component with responsive styling."""
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
                        value, style={"margin": 0, "color": color, "fontWeight": "bold"}
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
                style={"textAlign": "center", "padding": "15px"},
            )
        ],
        className="metric-card",
        style={
            "backgroundColor": COLORS["secondary"],
            "border": f"1px solid {COLORS['border']}",
        },
    )


def create_signal_card(row):
    """Create a signal card for recent predictions with time-ago format."""
    timestamp = row.get("timestamp")
    text_content = row.get("text", "")
    text_content = strip_urls(text_content)
    preview = text_content[:120] + "..." if len(text_content) > 120 else text_content
    confidence = row.get("confidence", 0)
    assets = row.get("assets", [])
    market_impact = row.get("market_impact", {})
    correct_t7 = row.get("correct_t7")
    pnl_t7 = row.get("pnl_t7")

    # Determine sentiment from market_impact
    sentiment = "neutral"
    if isinstance(market_impact, dict) and market_impact:
        first_sentiment = list(market_impact.values())[0]
        if isinstance(first_sentiment, str):
            sentiment = first_sentiment.lower()

    # Format time ago
    if isinstance(timestamp, datetime):
        delta = datetime.now() - timestamp
        if delta.days > 7:
            time_ago = f"{delta.days // 7}w ago"
        elif delta.days > 0:
            time_ago = f"{delta.days}d ago"
        elif delta.seconds >= 3600:
            time_ago = f"{delta.seconds // 3600}h ago"
        else:
            time_ago = f"{max(1, delta.seconds // 60)}m ago"
    else:
        time_ago = str(timestamp)[:16] if timestamp else ""

    # Format assets
    asset_str = ", ".join(assets[:3]) if isinstance(assets, list) else str(assets)
    if isinstance(assets, list) and len(assets) > 3:
        asset_str += f" +{len(assets) - 3}"

    # Outcome badge with P&L
    if correct_t7 is True:
        pnl_text = f"+${pnl_t7:,.0f}" if pnl_t7 else "Correct"
        outcome_badge = html.Span(
            [html.I(className="fas fa-check me-1"), pnl_text],
            style={
                "color": COLORS["success"],
                "fontSize": "0.75rem",
                "fontWeight": "600",
            },
        )
    elif correct_t7 is False:
        pnl_text = f"${pnl_t7:,.0f}" if pnl_t7 else "Incorrect"
        outcome_badge = html.Span(
            [html.I(className="fas fa-times me-1"), pnl_text],
            style={
                "color": COLORS["danger"],
                "fontSize": "0.75rem",
                "fontWeight": "600",
            },
        )
    else:
        outcome_badge = html.Span(
            [html.I(className="fas fa-clock me-1"), "Pending"],
            style={
                "color": COLORS["warning"],
                "fontSize": "0.75rem",
                "fontWeight": "600",
            },
        )

    # Sentiment styling
    s_style = get_sentiment_style(sentiment)
    s_color = s_style["color"]
    s_icon = s_style["icon"]
    s_bg = s_style["bg_color"]

    return html.Div(
        [
            # Top: time ago + outcome
            html.Div(
                [
                    html.Span(
                        time_ago,
                        style={"color": COLORS["text_muted"], "fontSize": "0.75rem"},
                    ),
                    outcome_badge,
                ],
                className="d-flex justify-content-between align-items-center mb-1",
            ),
            # Post preview
            html.P(
                preview,
                style={
                    "fontSize": "0.82rem",
                    "margin": "4px 0 8px 0",
                    "lineHeight": "1.4",
                    "color": COLORS["text"],
                },
            ),
            # Bottom: sentiment badge + assets + confidence
            html.Div(
                [
                    html.Span(
                        [
                            html.I(className=f"fas fa-{s_icon} me-1"),
                            sentiment.upper(),
                        ],
                        className="sentiment-badge",
                        style={
                            "backgroundColor": s_bg,
                            "color": s_color,
                            "fontSize": "0.7rem",
                        },
                    ),
                    html.Span(
                        asset_str,
                        style={
                            "color": COLORS["accent"],
                            "fontSize": "0.78rem",
                            "fontWeight": "600",
                        },
                    ),
                    html.Span(
                        f"{confidence:.0%}",
                        style={
                            "color": COLORS["text_muted"],
                            "fontSize": "0.78rem",
                        },
                    ),
                ],
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "gap": "10px",
                },
            ),
        ],
        style={
            "padding": "12px",
            "borderBottom": f"1px solid {COLORS['border']}",
            "borderLeft": f"3px solid {s_color}",
            "cursor": "pointer",
        },
        className="signal-card",
    )


def create_post_card(row, card_index: int = 0):
    """Create a card for a post in the Latest Posts feed."""
    timestamp = row.get("timestamp")
    post_text = row.get("text", "")
    analysis_status = row.get("analysis_status")
    assets = row.get("assets", [])
    market_impact = row.get("market_impact", {})
    confidence = row.get("confidence")
    thesis = row.get("thesis", "")
    replies = row.get("replies_count", 0) or 0
    reblogs = row.get("reblogs_count", 0) or 0
    favourites = row.get("favourites_count", 0) or 0

    # Truncate post text for display
    post_text = strip_urls(post_text)
    display_text = post_text[:300] + "..." if len(post_text) > 300 else post_text

    # Determine sentiment from market_impact
    sentiment = None
    if isinstance(market_impact, dict) and market_impact:
        first_sentiment = list(market_impact.values())[0]
        if isinstance(first_sentiment, str):
            sentiment = first_sentiment.lower()

    # Card border color based on sentiment (defaults to neutral for bypassed/pending)
    card_border_color = SENTIMENT_COLORS.get(sentiment or "neutral", SENTIMENT_COLORS["neutral"])

    # Build analysis section based on status
    if analysis_status == "completed" and assets:
        # Format assets
        asset_str = ", ".join(assets[:5]) if isinstance(assets, list) else str(assets)
        if isinstance(assets, list) and len(assets) > 5:
            asset_str += f" +{len(assets) - 5}"

        s_style = get_sentiment_style(sentiment or "neutral")
        sentiment_color = s_style["color"]
        sentiment_icon = s_style["icon"]
        sentiment_bg = s_style["bg_color"]

        analysis_section = html.Div(
            [
                html.Div(
                    [
                        html.Span(
                            [
                                html.I(className=f"fas fa-{sentiment_icon} me-1"),
                                (sentiment or "neutral").upper(),
                            ],
                            style={
                                "color": sentiment_color,
                                "backgroundColor": sentiment_bg,
                                "padding": "2px 8px",
                                "borderRadius": "4px",
                                "fontSize": "0.85rem",
                                "fontWeight": "bold",
                            },
                        ),
                        html.Span(
                            f" | {asset_str}",
                            style={"color": COLORS["accent"], "fontSize": "0.85rem"},
                        ),
                        html.Span(
                            f" | {confidence:.0%}" if confidence else "",
                            style={
                                "color": COLORS["text_muted"],
                                "fontSize": "0.85rem",
                            },
                        ),
                    ],
                    className="mb-1",
                ),
                _build_expandable_thesis(
                    thesis,
                    card_index=card_index,
                    truncate_len=200,
                    id_prefix="post-thesis",
                )
                if thesis
                else None,
            ],
            style={
                "padding": "8px",
                "backgroundColor": COLORS["primary"],
                "borderRadius": "6px",
                "marginTop": "8px",
            },
        )
    elif analysis_status == "bypassed":
        analysis_section = html.Div(
            [
                html.Span(
                    [
                        html.I(className="fas fa-forward me-1"),
                        "Bypassed",
                    ],
                    className="badge",
                    style={
                        "backgroundColor": COLORS["border"],
                        "color": COLORS["text_muted"],
                        "fontSize": "0.75rem",
                    },
                ),
                html.Small(
                    f" {row.get('analysis_comment', '') or ''}",
                    style={"color": COLORS["text_muted"]},
                ),
            ],
            style={"marginTop": "8px"},
        )
    else:
        analysis_section = html.Div(
            html.Span(
                [
                    html.I(className="fas fa-clock me-1"),
                    "Pending Analysis",
                ],
                className="badge",
                style={
                    "backgroundColor": COLORS["warning"],
                    "color": COLORS["primary"],
                    "fontSize": "0.75rem",
                },
            ),
            style={"marginTop": "8px"},
        )

    # Engagement metrics
    engagement = html.Div(
        [
            html.Span(
                [html.I(className="fas fa-reply me-1"), f"{replies}"],
                style={
                    "color": COLORS["text_muted"],
                    "fontSize": "0.75rem",
                    "marginRight": "12px",
                },
            ),
            html.Span(
                [html.I(className="fas fa-retweet me-1"), f"{reblogs}"],
                style={
                    "color": COLORS["text_muted"],
                    "fontSize": "0.75rem",
                    "marginRight": "12px",
                },
            ),
            html.Span(
                [html.I(className="fas fa-heart me-1"), f"{favourites}"],
                style={"color": COLORS["text_muted"], "fontSize": "0.75rem"},
            ),
        ],
        style={"marginTop": "8px"},
    )

    return html.Div(
        [
            # Timestamp
            html.Div(
                timestamp.strftime("%b %d, %Y %H:%M")
                if isinstance(timestamp, datetime)
                else str(timestamp)[:16],
                style={
                    "color": COLORS["text_muted"],
                    "fontSize": "0.75rem",
                    "marginBottom": "4px",
                },
            ),
            # Post text
            html.P(
                display_text,
                style={"fontSize": "0.9rem", "margin": "5px 0", "lineHeight": "1.5"},
            ),
            # Analysis
            analysis_section,
            # Engagement
            engagement,
        ],
        style={
            "padding": "15px",
            "borderBottom": f"1px solid {COLORS['border']}",
            "borderLeft": f"3px solid {card_border_color}",
        },
    )


def create_prediction_timeline_card(row: dict) -> html.Div:
    """
    Create a single prediction card for the timeline.

    Args:
        row: Dictionary with keys from get_asset_predictions() DataFrame row

    Returns:
        html.Div component for one timeline entry
    """
    prediction_date = row.get("prediction_date")
    timestamp = row.get("timestamp")
    tweet_text = row.get("text", "")
    sentiment = row.get("prediction_sentiment", "neutral")
    confidence = row.get("prediction_confidence", 0)
    return_t7 = row.get("return_t7")
    correct_t7 = row.get("correct_t7")
    pnl_t7 = row.get("pnl_t7")
    price_at = row.get("price_at_prediction")
    price_after = row.get("price_t7")

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
                                f" | {confidence:.0%}"
                                if confidence
                                else "",
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
        row: Dictionary with keys: related_symbol, co_occurrence_count, avg_return_t7

    Returns:
        html.Div component
    """
    symbol = row.get("related_symbol", "???")
    count = row.get("co_occurrence_count", 0)
    avg_return = row.get("avg_return_t7")

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


def create_performance_summary(stats: Dict[str, Any]) -> html.Div:
    """
    Create the performance summary comparing this asset vs overall system.

    Args:
        stats: Dictionary from get_asset_stats()

    Returns:
        html.Div with comparison metrics
    """
    asset_accuracy = stats.get("accuracy_t7", 0)
    overall_accuracy = stats.get("overall_accuracy_t7", 0)
    accuracy_diff = asset_accuracy - overall_accuracy

    asset_return = stats.get("avg_return_t7", 0)
    overall_return = stats.get("overall_avg_return_t7", 0)
    return_diff = asset_return - overall_return

    best = stats.get("best_return_t7")
    worst = stats.get("worst_return_t7")

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


def _safe_get(row, key, default=None):
    """
    NaN-safe field extraction from a Pandas Series or dict.

    Pandas Series.get() returns NaN (not the default) when the key exists
    but the value is NaN. This helper normalizes NaN to the provided default.
    """
    value = row.get(key, default)
    if value is None:
        return default
    try:
        import math

        if isinstance(value, float) and math.isnan(value):
            return default
    except (TypeError, ValueError):
        pass
    return value


def _build_expandable_thesis(
    thesis: str,
    card_index: int,
    truncate_len: int = 120,
    id_prefix: str = "thesis",
) -> html.Div:
    """Build an expandable thesis container with toggle.

    If the thesis is shorter than truncate_len, returns a simple paragraph.
    If longer, returns a collapsible container with preview/full text and
    a clickable toggle that works with a MATCH clientside callback.

    Args:
        thesis: Full thesis text.
        card_index: Unique index for pattern-matching callback IDs.
        truncate_len: Character count before truncation kicks in.
        id_prefix: Prefix for component IDs to avoid collisions between
                   different card types using the same callback.

    Returns:
        html.Div or html.P containing the thesis display.
    """
    thesis_style_base = {
        "fontSize": "0.8rem",
        "color": COLORS["text_muted"],
        "margin": "0",
        "fontStyle": "italic",
        "lineHeight": "1.4",
    }

    thesis_is_long = len(thesis) > truncate_len
    if not thesis_is_long:
        return html.P(thesis, style=thesis_style_base)

    thesis_preview = thesis[:truncate_len] + "..."

    # Collapsed preview (visible by default)
    preview_el = html.P(
        thesis_preview,
        id={"type": f"{id_prefix}-preview", "index": card_index},
        style={**thesis_style_base, "display": "block"},
    )
    # Full thesis (hidden by default)
    full_el = html.P(
        thesis,
        id={"type": f"{id_prefix}-full", "index": card_index},
        style={**thesis_style_base, "display": "none"},
    )
    # Toggle button
    toggle_el = html.Div(
        [
            html.Span(
                [
                    html.I(
                        className="fas fa-chevron-down me-1",
                        id={"type": f"{id_prefix}-chevron", "index": card_index},
                        style={
                            "fontSize": "0.65rem",
                            "transition": "transform 0.2s ease",
                        },
                    ),
                    "Show full thesis",
                ],
                id={"type": f"{id_prefix}-toggle-text", "index": card_index},
            ),
        ],
        id={"type": f"{id_prefix}-toggle", "index": card_index},
        n_clicks=0,
        style={
            "color": COLORS["accent"],
            "fontSize": "0.75rem",
            "cursor": "pointer",
            "marginTop": "4px",
            "userSelect": "none",
        },
    )

    return html.Div([preview_el, full_el, toggle_el])


def create_feed_signal_card(row, card_index: int = 0) -> html.Div:
    """
    Create a signal card for the /signals feed page.

    More detailed than the dashboard signal card — includes badges,
    confidence bar, thesis preview, and return/P&L metrics.

    Args:
        row: Dict-like object with keys from get_signal_feed().

    Returns:
        html.Div containing the rendered card.
    """
    timestamp = _safe_get(row, "timestamp")
    post_text = _safe_get(row, "text", "")
    confidence = _safe_get(row, "confidence", 0) or 0
    assets = _safe_get(row, "assets", [])
    market_impact = _safe_get(row, "market_impact", {})
    symbol = _safe_get(row, "symbol")
    prediction_sentiment = _safe_get(row, "prediction_sentiment")
    return_t7 = _safe_get(row, "return_t7")
    correct_t7 = _safe_get(row, "correct_t7")
    pnl_t7 = _safe_get(row, "pnl_t7")
    thesis = _safe_get(row, "thesis", "")

    # Determine if "New" badge should show (post < 24 hours old)
    is_new = False
    if isinstance(timestamp, datetime):
        ts = timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        is_new = ts > cutoff

    # Determine sentiment direction
    sentiment = "neutral"
    if prediction_sentiment:
        sentiment = prediction_sentiment.lower()
    elif isinstance(market_impact, dict) and market_impact:
        first_val = list(market_impact.values())[0]
        if isinstance(first_val, str):
            sentiment = first_val.lower()

    s_style = get_sentiment_style(sentiment)
    sentiment_color = s_style["color"]
    sentiment_icon = s_style["icon"]
    sentiment_bg = s_style["bg_color"]

    # Format asset display
    if symbol:
        asset_display = symbol
    elif isinstance(assets, list):
        asset_display = ", ".join(assets[:3])
        if len(assets) > 3:
            asset_display += f" +{len(assets) - 3}"
    else:
        asset_display = str(assets) if assets else "N/A"

    # Truncate text
    post_text = strip_urls(post_text)
    max_text_len = 250
    display_text = (
        post_text[:max_text_len] + "..." if len(post_text) > max_text_len else post_text
    )

    # Build badges
    badges = []
    if is_new:
        badges.append(
            html.Span(
                "New",
                className="badge me-2",
                style={
                    "backgroundColor": COLORS["accent"],
                    "color": "white",
                    "fontSize": "0.7rem",
                    "padding": "4px 8px",
                    "borderRadius": "4px",
                },
            )
        )

    if correct_t7 is True:
        badges.append(
            html.Span(
                "Correct",
                className="badge",
                style={
                    "backgroundColor": COLORS["success"],
                    "color": "white",
                    "fontSize": "0.7rem",
                    "padding": "4px 8px",
                    "borderRadius": "4px",
                },
            )
        )
    elif correct_t7 is False:
        badges.append(
            html.Span(
                "Incorrect",
                className="badge",
                style={
                    "backgroundColor": COLORS["danger"],
                    "color": "white",
                    "fontSize": "0.7rem",
                    "padding": "4px 8px",
                    "borderRadius": "4px",
                },
            )
        )
    else:
        badges.append(
            html.Span(
                "Pending",
                className="badge",
                style={
                    "backgroundColor": COLORS["warning"],
                    "color": COLORS["primary"],
                    "fontSize": "0.7rem",
                    "padding": "4px 8px",
                    "borderRadius": "4px",
                },
            )
        )

    # Format timestamp display
    if isinstance(timestamp, datetime):
        ts_display = timestamp.strftime("%b %d, %Y %H:%M")
    else:
        ts_display = str(timestamp)[:16] if timestamp else "Unknown"

    # Confidence bar
    conf_pct = confidence * 100
    conf_bar_color = (
        COLORS["success"]
        if confidence >= 0.75
        else COLORS["warning"]
        if confidence >= 0.6
        else COLORS["danger"]
    )
    confidence_bar = html.Div(
        [
            html.Div(
                style={
                    "width": f"{conf_pct}%",
                    "height": "4px",
                    "backgroundColor": conf_bar_color,
                    "borderRadius": "2px",
                }
            ),
        ],
        style={
            "width": "60px",
            "height": "4px",
            "backgroundColor": COLORS["border"],
            "borderRadius": "2px",
            "display": "inline-block",
            "verticalAlign": "middle",
            "marginLeft": "6px",
        },
    )

    # Return / P&L display
    metrics_children = []
    if return_t7 is not None:
        ret_color = COLORS["success"] if return_t7 > 0 else COLORS["danger"]
        metrics_children.append(
            html.Span(
                f"7d Return: {return_t7:+.2f}%",
                style={
                    "color": ret_color,
                    "fontSize": "0.8rem",
                    "fontWeight": "bold",
                },
            )
        )
    if pnl_t7 is not None:
        pnl_color = COLORS["success"] if pnl_t7 > 0 else COLORS["danger"]
        if metrics_children:
            metrics_children.append(
                html.Span(
                    " | ", style={"color": COLORS["border"], "margin": "0 6px"}
                )
            )
        metrics_children.append(
            html.Span(
                f"P&L: ${pnl_t7:,.0f}",
                style={"color": pnl_color, "fontSize": "0.8rem"},
            )
        )

    # Assemble the card
    children = [
        # Row 1: Timestamp + Badges
        html.Div(
            [
                html.Span(
                    ts_display,
                    style={"color": COLORS["text_muted"], "fontSize": "0.75rem"},
                ),
                html.Div(
                    badges,
                    style={"display": "inline-flex", "alignItems": "center"},
                ),
            ],
            style={
                "display": "flex",
                "justifyContent": "space-between",
                "alignItems": "center",
                "marginBottom": "8px",
            },
        ),
        # Row 2: Tweet text
        html.P(
            display_text,
            style={
                "fontSize": "0.9rem",
                "margin": "0 0 10px 0",
                "lineHeight": "1.5",
                "color": COLORS["text"],
            },
        ),
        # Row 3: Asset | Sentiment | Confidence
        html.Div(
            [
                html.Span(
                    asset_display,
                    style={
                        "backgroundColor": COLORS["primary"],
                        "color": COLORS["accent"],
                        "padding": "2px 8px",
                        "borderRadius": "4px",
                        "fontSize": "0.8rem",
                        "fontWeight": "bold",
                        "marginRight": "12px",
                        "border": f"1px solid {COLORS['border']}",
                    },
                ),
                html.Span(
                    [
                        html.I(className=f"fas fa-{sentiment_icon} me-1"),
                        sentiment.upper(),
                    ],
                    className="sentiment-badge",
                    style={
                        "backgroundColor": sentiment_bg,
                        "color": sentiment_color,
                        "fontSize": "0.8rem",
                        "marginRight": "12px",
                    },
                ),
                html.Span(
                    [
                        html.Span(
                            f"{confidence:.0%}",
                            style={
                                "color": COLORS["text_muted"],
                                "fontSize": "0.8rem",
                            },
                        ),
                        confidence_bar,
                    ]
                ),
            ],
            style={
                "display": "flex",
                "alignItems": "center",
                "flexWrap": "wrap",
                "gap": "4px",
            },
        ),
    ]

    # Row 4: Return / P&L metrics (only if we have data)
    if metrics_children:
        children.append(
            html.Div(metrics_children, style={"marginTop": "8px"})
        )

    # Row 5: Thesis — expandable if long, static if short
    if thesis:
        children.append(
            html.Div(
                _build_expandable_thesis(
                    thesis,
                    card_index=card_index,
                    truncate_len=120,
                    id_prefix="thesis",
                ),
                style={"marginTop": "8px"},
            )
        )

    return html.Div(
        children,
        style={
            "padding": "16px",
            "backgroundColor": COLORS["secondary"],
            "border": f"1px solid {COLORS['border']}",
            "borderLeft": f"3px solid {sentiment_color}",
            "borderRadius": "8px",
            "marginBottom": "12px",
        },
    )


def create_new_signals_banner(count: int) -> html.Div:
    """
    Create a banner showing how many new signals have arrived.

    Args:
        count: Number of new signals detected.

    Returns:
        html.Div with the banner content.
    """
    return html.Div(
        [
            html.Div(
                [
                    html.I(className="fas fa-bell me-2"),
                    html.Span(
                        f"{count} new signal{'s' if count != 1 else ''}"
                        " since you last checked",
                        style={"fontWeight": "bold"},
                    ),
                ],
                style={
                    "display": "inline-flex",
                    "alignItems": "center",
                },
            ),
            dbc.Button(
                "Show New Signals",
                id="signal-feed-show-new-btn",
                color="primary",
                size="sm",
                className="ms-3",
            ),
        ],
        style={
            "backgroundColor": "rgba(59, 130, 246, 0.15)",
            "border": f"1px solid {COLORS['accent']}",
            "borderRadius": "8px",
            "padding": "12px 16px",
            "marginBottom": "16px",
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "color": COLORS["accent"],
        },
    )

