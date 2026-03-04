"""Card components package for the Shitty UI dashboard.

Splits the original monolithic cards.py into focused submodules while
preserving full backward compatibility -- every ``from components.cards
import X`` that worked before continues to work.

Utility functions ``strip_urls()`` and ``get_sentiment_style()`` are
defined here (before submodule imports) to avoid circular imports since
multiple submodules depend on them.
"""

import re

from constants import SENTIMENT_COLORS, SENTIMENT_BG_COLORS


# ---------------------------------------------------------------------------
# Shared utilities -- defined BEFORE submodule imports so that submodules
# can safely ``from components.cards import strip_urls, get_sentiment_style``
# at module level without triggering circular import errors.
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Re-export everything from submodules so that existing imports like
#     from components.cards import create_hero_signal_card
# continue to work unchanged.
# ---------------------------------------------------------------------------

from components.cards.empty_states import (  # noqa: E402
    create_error_card,
    create_empty_chart,
    create_empty_state_chart,
    create_empty_state_html,
)
from components.cards.hero import create_hero_signal_card  # noqa: E402
from components.cards.metrics import (  # noqa: E402
    create_metric_card,
    create_performance_summary,
)
from components.cards.signal import (  # noqa: E402
    create_signal_card,
    create_unified_signal_card,
)
from components.cards.feed import (  # noqa: E402
    _build_expandable_thesis,
    create_feed_signal_card,
    create_new_signals_banner,
)
from components.utils import safe_get  # noqa: E402
from components.cards.post import create_post_card  # noqa: E402
from components.cards.timeline import (  # noqa: E402
    create_prediction_timeline_card,
    create_related_asset_link,
)

__all__ = [
    # Utilities (defined in this file)
    "strip_urls",
    "get_sentiment_style",
    # Empty states
    "create_error_card",
    "create_empty_chart",
    "create_empty_state_chart",
    "create_empty_state_html",
    # Hero
    "create_hero_signal_card",
    # Metrics
    "create_metric_card",
    "create_performance_summary",
    # Signal
    "create_signal_card",
    "create_unified_signal_card",
    # Feed
    "safe_get",
    "_build_expandable_thesis",
    "create_feed_signal_card",
    "create_new_signals_banner",
    # Post
    "create_post_card",
    # Timeline
    "create_prediction_timeline_card",
    "create_related_asset_link",
]
