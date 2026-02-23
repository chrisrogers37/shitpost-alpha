"""Shared UI helper functions for card and component rendering.

Extracts common patterns used across multiple card types to eliminate
duplication and ensure consistent behavior (time formatting, sentiment
extraction, outcome badges, asset display).
"""

from datetime import datetime
from typing import Optional

from dash import html

from constants import COLORS


def format_time_ago(timestamp) -> str:
    """Format a timestamp into a human-readable relative string.

    Handles datetime objects, None, and non-datetime values gracefully.
    Supports granularity from "just now" through weeks.

    Args:
        timestamp: datetime object, None, or any stringifiable value.

    Returns:
        String like "2w ago", "3d ago", "5h ago", "12m ago", "just now",
        or "" if None.
    """
    if timestamp is None:
        return ""
    if not isinstance(timestamp, datetime):
        return str(timestamp)[:10]

    delta = datetime.now() - timestamp
    if delta.days > 7:
        return f"{delta.days // 7}w ago"
    elif delta.days > 0:
        return f"{delta.days}d ago"
    elif delta.seconds >= 3600:
        return f"{delta.seconds // 3600}h ago"
    elif delta.seconds >= 60:
        return f"{delta.seconds // 60}m ago"
    else:
        return "just now"


def extract_sentiment(market_impact) -> str:
    """Extract the primary sentiment string from a market_impact dict.

    The market_impact field stores a dict mapping asset tickers to
    sentiment strings (e.g., {"AAPL": "bullish", "TSLA": "bearish"}).
    This function extracts the first value as the overall sentiment.

    Args:
        market_impact: Dict of {asset: sentiment_string}, or any other
            type (gracefully returns "neutral").

    Returns:
        Lowercase sentiment string: "bullish", "bearish", or "neutral".
    """
    if isinstance(market_impact, dict) and market_impact:
        first_sentiment = list(market_impact.values())[0]
        if isinstance(first_sentiment, str):
            return first_sentiment.lower()
    return "neutral"


def create_outcome_badge(
    correct_t7: Optional[bool],
    pnl_display: Optional[float] = None,
    font_size: str = "0.75rem",
) -> html.Span:
    """Create a styled outcome badge showing prediction result.

    Renders a Correct/Incorrect/Pending badge with icon and optional
    P&L amount. Used consistently across hero, signal, unified, and
    feed card types.

    Args:
        correct_t7: True for correct, False for incorrect, None for pending.
        pnl_display: Dollar P&L amount to display. If None, shows text
            label ("Correct", "Incorrect", "Pending") instead.
        font_size: CSS font-size string. Default "0.75rem" for standard
            cards; use "0.8rem" for hero/unified cards.

    Returns:
        html.Span containing the styled badge.
    """
    if correct_t7 is True:
        return html.Span(
            [
                html.I(className="fas fa-check me-1"),
                f"+${pnl_display:,.0f}" if pnl_display else "Correct",
            ],
            style={
                "color": COLORS["success"],
                "fontWeight": "600",
                "fontSize": font_size,
            },
        )
    elif correct_t7 is False:
        return html.Span(
            [
                html.I(className="fas fa-times me-1"),
                f"${pnl_display:,.0f}" if pnl_display else "Incorrect",
            ],
            style={
                "color": COLORS["danger"],
                "fontWeight": "600",
                "fontSize": font_size,
            },
        )
    else:
        return html.Span(
            [html.I(className="fas fa-clock me-1"), "Pending"],
            style={
                "color": COLORS["warning"],
                "fontWeight": "600",
                "fontSize": font_size,
            },
        )


def format_asset_display(
    assets,
    max_count: int = 3,
    show_overflow: bool = True,
) -> str:
    """Format an asset list into a display string with overflow indicator.

    Truncates long asset lists and appends a "+N" suffix when there are
    more assets than max_count.

    Args:
        assets: List of asset ticker strings, or a non-list value that
            will be stringified directly.
        max_count: Maximum number of assets to show before truncating.
        show_overflow: Whether to append "+N" for hidden assets.

    Returns:
        Formatted string like "AAPL, TSLA" or "AAPL, TSLA, GOOG +2".
    """
    if not isinstance(assets, list):
        return str(assets) if assets else ""
    asset_str = ", ".join(assets[:max_count])
    if show_overflow and len(assets) > max_count:
        asset_str += f" +{len(assets) - max_count}"
    return asset_str
