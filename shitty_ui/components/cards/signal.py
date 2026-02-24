"""Signal card components for the prediction feed.

Provides the compact signal card used in the sidebar and the unified
signal card used in the main dashboard feed. Both support sparkline
price charts and aggregated outcome data.
"""

from datetime import datetime

from dash import html

from constants import COLORS
from components.cards import strip_urls, get_sentiment_style
from components.helpers import (
    format_time_ago,
    extract_sentiment,
    create_outcome_badge,
    format_asset_display,
)
from components.sparkline import (
    create_sparkline_component,
    create_sparkline_placeholder,
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
    sentiment = extract_sentiment(market_impact)

    # Format time ago
    time_ago = format_time_ago(timestamp)

    # Format assets
    asset_str = format_asset_display(assets, max_count=3)

    # Outcome badge with P&L
    outcome_badge = create_outcome_badge(correct_t7, pnl_t7)

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


def create_unified_signal_card(row, sparkline_prices: dict = None) -> html.Div:
    """Create a card for the unified prediction feed on the dashboard.

    Combines the aggregated outcome logic from hero cards with the compact
    vertical layout of signal cards. Designed for the unified feed that
    replaces both the hero section and the recent predictions sidebar.

    Args:
        row: Dict-like object with columns from get_unified_feed().

    Returns:
        html.Div containing the rendered card.
    """
    timestamp = row.get("timestamp")
    text_content = row.get("text", "")
    text_content = strip_urls(text_content)
    preview = text_content[:200] + "..." if len(text_content) > 200 else text_content
    confidence = row.get("confidence", 0)
    assets = row.get("assets", [])
    market_impact = row.get("market_impact", {})
    thesis = row.get("thesis", "")

    # Aggregated outcome data (from GROUP BY query)
    outcome_count = row.get("outcome_count", 0) or 0
    correct_count = row.get("correct_count", 0) or 0
    incorrect_count = row.get("incorrect_count", 0) or 0
    total_pnl_t7 = row.get("total_pnl_t7")

    # Derive overall correctness from aggregated counts
    if outcome_count > 0 and correct_count + incorrect_count > 0:
        correct_t7 = correct_count > incorrect_count
    else:
        correct_t7 = None  # Pending

    # Determine sentiment
    sentiment = extract_sentiment(market_impact)

    # Format time ago
    time_ago = format_time_ago(timestamp)

    # Asset string
    asset_str = format_asset_display(assets, max_count=4)

    # Sentiment styling
    s_style = get_sentiment_style(sentiment)
    s_color = s_style["color"]
    s_bg = s_style["bg_color"]
    s_icon = s_style["icon"]

    # Outcome badge -- uses aggregated P&L
    pnl_display = total_pnl_t7
    outcome_badge = create_outcome_badge(correct_t7, pnl_display, font_size="0.8rem")

    # Build card children
    children = [
        # Row 1: time ago + outcome badge
        html.Div(
            [
                html.Span(
                    time_ago,
                    style={"color": COLORS["text_muted"], "fontSize": "0.75rem"},
                ),
                outcome_badge,
            ],
            style={
                "display": "flex",
                "justifyContent": "space-between",
                "alignItems": "center",
                "marginBottom": "8px",
            },
        ),
        # Row 2: Post preview
        html.P(
            preview,
            style={
                "fontSize": "0.85rem",
                "margin": "0 0 10px 0",
                "lineHeight": "1.5",
                "color": COLORS["text"],
            },
        ),
        # Row 3: sentiment badge + assets + confidence
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
    ]

    # Row 3b: Sparkline for first asset (if available)
    first_asset = assets[0] if isinstance(assets, list) and assets else None
    sparkline_element = None
    if sparkline_prices and first_asset and first_asset in sparkline_prices:
        price_df = sparkline_prices[first_asset]
        pred_date = timestamp.date() if isinstance(timestamp, datetime) else None
        sparkline_element = create_sparkline_component(
            price_df,
            prediction_date=pred_date,
            component_id=f"sparkline-unified-{first_asset}-{id(row)}",
        )
    elif sparkline_prices is not None and first_asset:
        sparkline_element = create_sparkline_placeholder()

    if sparkline_element is not None:
        children.append(
            html.Div(
                [
                    html.Span(
                        f"{first_asset} price",
                        style={
                            "color": COLORS["text_muted"],
                            "fontSize": "0.7rem",
                            "marginRight": "8px",
                            "verticalAlign": "middle",
                        },
                    ),
                    sparkline_element,
                ],
                style={
                    "marginTop": "8px",
                    "display": "flex",
                    "alignItems": "center",
                },
            )
        )

    # Row 4: Thesis preview (truncated)
    if thesis:
        children.append(
            html.P(
                thesis[:150] + "..." if len(thesis) > 150 else thesis,
                style={
                    "fontSize": "0.8rem",
                    "color": COLORS["text_muted"],
                    "margin": "8px 0 0 0",
                    "fontStyle": "italic",
                    "lineHeight": "1.4",
                },
            )
        )

    return html.Div(
        children,
        className="unified-signal-card",
        style={
            "padding": "16px",
            "backgroundColor": COLORS["secondary"],
            "border": f"1px solid {COLORS['border']}",
            "borderLeft": f"3px solid {s_color}",
            "borderRadius": "8px",
            "marginBottom": "12px",
        },
    )
