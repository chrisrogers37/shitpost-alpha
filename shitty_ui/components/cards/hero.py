"""Hero signal card component for high-confidence predictions.

Renders an elevated card in the hero section of the dashboard, using
trend icons and aggregated outcome data.
"""

from dash import html

from constants import COLORS
from components.cards import strip_urls, get_sentiment_style
from components.helpers import (
    format_time_ago,
    extract_sentiment,
    create_outcome_badge,
    format_asset_display,
)
from components.utils import safe_get


def create_hero_signal_card(row) -> html.Div:
    """Create a hero signal card for a high-confidence prediction."""
    timestamp = safe_get(row, "timestamp")
    text_content = safe_get(row, "text", "")
    text_content = strip_urls(text_content)
    preview = text_content[:200] + "..." if len(text_content) > 200 else text_content
    confidence = safe_get(row, "confidence", 0)
    assets = safe_get(row, "assets", [])
    market_impact = safe_get(row, "market_impact", {})
    # Derive outcome from aggregated counts (new dedup columns)
    # Fall back to correct_t7 for backward compatibility
    outcome_count = safe_get(row, "outcome_count", 0) or 0
    correct_count = safe_get(row, "correct_count", 0) or 0
    incorrect_count = safe_get(row, "incorrect_count", 0) or 0
    total_pnl_t7 = safe_get(row, "total_pnl_t7")

    if outcome_count > 0 and correct_count + incorrect_count > 0:
        # At least some outcomes evaluated -- majority wins
        correct_t7 = correct_count > incorrect_count
    elif "correct_t7" in row.index if hasattr(row, "index") else "correct_t7" in row:
        # Backward compatibility: use single correct_t7 if available
        correct_t7 = row.get("correct_t7")
    else:
        correct_t7 = None  # Pending

    # Determine sentiment
    sentiment = extract_sentiment(market_impact)

    # Format time ago
    time_ago = format_time_ago(timestamp)

    # Asset string
    asset_str = format_asset_display(assets, max_count=4, show_overflow=False)

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
    pnl_display = total_pnl_t7 if total_pnl_t7 is not None else safe_get(row, "pnl_t7")
    outcome = create_outcome_badge(correct_t7, pnl_display, font_size="0.8rem")

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
