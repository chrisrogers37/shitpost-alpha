"""Post card component for the Latest Posts feed.

Renders individual posts with analysis status (completed, bypassed,
pending), engagement metrics, and expandable thesis sections.
"""

from datetime import datetime

from dash import html

from constants import COLORS, SENTIMENT_COLORS
from brand_copy import COPY
from components.cards import strip_urls, get_sentiment_style
from components.cards.feed import _build_expandable_thesis
from components.helpers import (
    extract_sentiment,
    format_asset_display,
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
    raw_sentiment = extract_sentiment(market_impact)
    sentiment = raw_sentiment if raw_sentiment != "neutral" else None

    # Card border color based on sentiment (defaults to neutral for bypassed/pending)
    card_border_color = SENTIMENT_COLORS.get(
        sentiment or "neutral", SENTIMENT_COLORS["neutral"]
    )

    # Build analysis section based on status
    if analysis_status == "completed" and assets:
        # Format assets
        asset_str = format_asset_display(assets, max_count=5)

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
                        COPY["card_bypassed"],
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
                    COPY["card_pending_analysis"],
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
