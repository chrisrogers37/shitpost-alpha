# Phase 02: Extract shared UI helpers from duplicated card code

**Status:** ✅ COMPLETE (PR #89)

| Field | Value |
|-------|-------|
| **PR Title** | refactor: extract 4 shared UI helpers from duplicated card code |
| **Risk Level** | Low-Medium |
| **Effort** | Medium (~3-4 hours) |
| **Files Created** | 2 (`shitty_ui/components/helpers.py`, `shit_tests/shitty_ui/test_helpers.py`) |
| **Files Modified** | 2 (`shitty_ui/components/cards.py`, `shitty_ui/components/insights.py`) |
| **Files Deleted** | 0 |

## Context

`shitty_ui/components/cards.py` is a 2,041-line file containing 6 megafunctions that each independently re-implement the same 4 patterns: relative time formatting, sentiment extraction from `market_impact` dicts, outcome badge rendering, and asset list display formatting. The research identified ~140 lines of pure duplication across these patterns.

This duplication has already caused a real bug: `create_hero_signal_card()` (lines 277-286) is missing weeks support in its time-ago formatter, while `create_signal_card()` and `create_unified_signal_card()` both handle weeks correctly. Meanwhile, `insights.py` has a superior `_format_insight_timestamp()` (lines 37-61) that handles weeks, just-now, and None gracefully -- but it is private and inaccessible to cards.py.

This phase extracts all 4 patterns into a new `shitty_ui/components/helpers.py` module, eliminating the duplication, fixing the weeks bug in the hero card, and establishing a shared utility layer that future card components can reuse.

## Dependencies

- **Depends on**: Phase 01 (conftest fix is required for tests to run reliably)
- **Unlocks**: Phase 03 (card megafunction decomposition benefits from having helpers already extracted)

## Detailed Implementation Plan

### Step 1: Create `shitty_ui/components/helpers.py`

**File to create**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/helpers.py`

This new file contains all 4 helper functions. The full content:

```python
"""Shared UI helper functions for card and component rendering.

Extracts common patterns used across multiple card types to eliminate
duplication and ensure consistent behavior (time formatting, sentiment
extraction, outcome badges, asset display).
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

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
```

---

### Step 2: Update `shitty_ui/components/cards.py` — add import

**File to modify**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/cards.py`

**Current code at lines 11-13:**
```python
from constants import COLORS, FONT_SIZES, HIERARCHY, SENTIMENT_COLORS, SENTIMENT_BG_COLORS
from brand_copy import COPY
from components.sparkline import create_sparkline_component, create_sparkline_placeholder
```

**Replace with:**
```python
from constants import COLORS, FONT_SIZES, HIERARCHY, SENTIMENT_COLORS, SENTIMENT_BG_COLORS
from brand_copy import COPY
from components.helpers import format_time_ago, extract_sentiment, create_outcome_badge, format_asset_display
from components.sparkline import create_sparkline_component, create_sparkline_placeholder
```

---

### Step 3: Update `create_hero_signal_card()` — 3 replacements

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/cards.py`

#### 3a: Sentiment extraction (lines 270-274)

**Current code:**
```python
    # Determine sentiment
    sentiment = "neutral"
    if isinstance(market_impact, dict) and market_impact:
        first_sentiment = list(market_impact.values())[0]
        if isinstance(first_sentiment, str):
            sentiment = first_sentiment.lower()
```

**Replace with:**
```python
    # Determine sentiment
    sentiment = extract_sentiment(market_impact)
```

#### 3b: Time-ago formatting (lines 277-286)

This is the instance with the **weeks bug** -- it jumps straight from days to the raw day count without weeks support.

**Current code:**
```python
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
```

**Replace with:**
```python
    # Format time ago
    time_ago = format_time_ago(timestamp)
```

#### 3c: Asset string (line 289)

**Current code:**
```python
    # Asset string
    asset_str = ", ".join(assets[:4]) if isinstance(assets, list) else str(assets)
```

**Replace with:**
```python
    # Asset string
    asset_str = format_asset_display(assets, max_count=4, show_overflow=False)
```

Note: The hero card does NOT show overflow counts (no "+N"), so `show_overflow=False`.

#### 3d: Outcome badge (lines 302-336)

**Current code:**
```python
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
```

**Replace with:**
```python
    # Outcome badge -- uses aggregated P&L when available
    pnl_display = total_pnl_t7 if total_pnl_t7 is not None else row.get("pnl_t7")
    outcome = create_outcome_badge(correct_t7, pnl_display, font_size="0.8rem")
```

---

### Step 4: Update `create_signal_card()` — 3 replacements

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/cards.py`

#### 4a: Sentiment extraction (lines 540-544)

**Current code:**
```python
    # Determine sentiment from market_impact
    sentiment = "neutral"
    if isinstance(market_impact, dict) and market_impact:
        first_sentiment = list(market_impact.values())[0]
        if isinstance(first_sentiment, str):
            sentiment = first_sentiment.lower()
```

**Replace with:**
```python
    # Determine sentiment from market_impact
    sentiment = extract_sentiment(market_impact)
```

#### 4b: Time-ago formatting (lines 547-558)

**Current code:**
```python
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
```

**Replace with:**
```python
    # Format time ago
    time_ago = format_time_ago(timestamp)
```

**Behavior note**: The old code used `max(1, delta.seconds // 60)` to avoid showing "0m ago". The new `format_time_ago()` returns `"just now"` for sub-60-second deltas instead, which is a UX improvement, not a regression.

#### 4c: Asset display (lines 561-563)

**Current code:**
```python
    # Format assets
    asset_str = ", ".join(assets[:3]) if isinstance(assets, list) else str(assets)
    if isinstance(assets, list) and len(assets) > 3:
        asset_str += f" +{len(assets) - 3}"
```

**Replace with:**
```python
    # Format assets
    asset_str = format_asset_display(assets, max_count=3)
```

#### 4d: Outcome badge (lines 566-594)

**Current code:**
```python
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
```

**Replace with:**
```python
    # Outcome badge with P&L
    outcome_badge = create_outcome_badge(correct_t7, pnl_t7)
```

---

### Step 5: Update `create_unified_signal_card()` — 3 replacements

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/cards.py`

#### 5a: Sentiment extraction (lines 708-712)

**Current code:**
```python
    # Determine sentiment
    sentiment = "neutral"
    if isinstance(market_impact, dict) and market_impact:
        first_sentiment = list(market_impact.values())[0]
        if isinstance(first_sentiment, str):
            sentiment = first_sentiment.lower()
```

**Replace with:**
```python
    # Determine sentiment
    sentiment = extract_sentiment(market_impact)
```

#### 5b: Time-ago formatting (lines 715-726)

**Current code:**
```python
    # Format time ago (supports weeks for older posts)
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
```

**Replace with:**
```python
    # Format time ago
    time_ago = format_time_ago(timestamp)
```

#### 5c: Asset string (lines 729-731)

**Current code:**
```python
    # Asset string
    asset_str = ", ".join(assets[:4]) if isinstance(assets, list) else str(assets)
    if isinstance(assets, list) and len(assets) > 4:
        asset_str += f" +{len(assets) - 4}"
```

**Replace with:**
```python
    # Asset string
    asset_str = format_asset_display(assets, max_count=4)
```

#### 5d: Outcome badge (lines 740-773)

**Current code:**
```python
    # Outcome badge -- uses aggregated P&L
    pnl_display = total_pnl_t7
    if correct_t7 is True:
        outcome_badge = html.Span(
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
        outcome_badge = html.Span(
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
        outcome_badge = html.Span(
            [html.I(className="fas fa-clock me-1"), "Pending"],
            style={
                "color": COLORS["warning"],
                "fontWeight": "600",
                "fontSize": "0.8rem",
            },
        )
```

**Replace with:**
```python
    # Outcome badge -- uses aggregated P&L
    pnl_display = total_pnl_t7
    outcome_badge = create_outcome_badge(correct_t7, pnl_display, font_size="0.8rem")
```

---

### Step 6: Update `create_post_card()` — 2 replacements

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/cards.py`

#### 6a: Sentiment extraction (lines 926-930)

**Current code:**
```python
    # Determine sentiment from market_impact
    sentiment = None
    if isinstance(market_impact, dict) and market_impact:
        first_sentiment = list(market_impact.values())[0]
        if isinstance(first_sentiment, str):
            sentiment = first_sentiment.lower()
```

**Replace with:**
```python
    # Determine sentiment from market_impact
    raw_sentiment = extract_sentiment(market_impact)
    sentiment = raw_sentiment if raw_sentiment != "neutral" else None
```

**Why the extra line**: `create_post_card()` uses `sentiment = None` as its default rather than `"neutral"` -- downstream code on line 933 does `sentiment or "neutral"` to handle the None case. We preserve this behavior by mapping `"neutral"` back to `None` so the rest of the function is unaffected.

#### 6b: Asset display (lines 938-940)

**Current code:**
```python
        # Format assets
        asset_str = ", ".join(assets[:5]) if isinstance(assets, list) else str(assets)
        if isinstance(assets, list) and len(assets) > 5:
            asset_str += f" +{len(assets) - 5}"
```

**Replace with:**
```python
        # Format assets
        asset_str = format_asset_display(assets, max_count=5)
```

Note: `create_post_card()` does NOT use the time-ago helper (it uses `strftime` for absolute timestamps) and does NOT use outcome badges. Only 2 of the 4 helpers apply here.

---

### Step 7: Update `create_prediction_timeline_card()` — 1 replacement

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/cards.py`

#### 7a: Outcome badge (lines 1120-1147)

The timeline card has a different badge style -- it uses `className="badge"` with `backgroundColor` as the full color (not text color), plus a `marginLeft`. This is a **different visual pattern** from the icon-based outcome badges in the other cards.

**DO NOT replace this with `create_outcome_badge()`.** The timeline card renders a solid-background badge with white text (`className="badge"` from Bootstrap), while the shared helper renders icon+text with colored text on transparent background. These are visually distinct components.

**Leave lines 1120-1147 unchanged.**

---

### Step 8: Update `create_feed_signal_card()` — 2 replacements

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/cards.py`

#### 8a: Sentiment extraction (lines 1686-1692)

**Current code:**
```python
    # Determine sentiment direction
    sentiment = "neutral"
    if prediction_sentiment:
        sentiment = prediction_sentiment.lower()
    elif isinstance(market_impact, dict) and market_impact:
        first_val = list(market_impact.values())[0]
        if isinstance(first_val, str):
            sentiment = first_val.lower()
```

**Replace with:**
```python
    # Determine sentiment direction
    if prediction_sentiment:
        sentiment = prediction_sentiment.lower()
    else:
        sentiment = extract_sentiment(market_impact)
```

**Why partial replacement**: The feed signal card has an additional `prediction_sentiment` field that takes priority over `market_impact`. The helper covers the fallback path only.

#### 8b: Asset display (lines 1700-1707)

**Current code:**
```python
    # Format asset display
    if symbol:
        asset_display = symbol
    elif isinstance(assets, list):
        asset_display = ", ".join(assets[:3])
        if len(assets) > 3:
            asset_display += f" +{len(assets) - 3}"
    else:
        asset_display = str(assets) if assets else "N/A"
```

**Replace with:**
```python
    # Format asset display
    if symbol:
        asset_display = symbol
    else:
        asset_display = format_asset_display(assets, max_count=3) or "N/A"
```

**Why partial replacement**: The feed card has a `symbol` field that takes priority. The helper covers the `elif/else` branch. The `or "N/A"` handles the case where `format_asset_display` returns `""` for empty/None assets.

#### 8c: Outcome badges (lines 1733-1774)

The feed signal card's outcome badges are **solid-background Bootstrap badges** (same pattern as the timeline card) -- they use `className="badge"` with full `backgroundColor` and white text. This is visually distinct from the icon-based badges produced by `create_outcome_badge()`.

**DO NOT replace this with `create_outcome_badge()`.** Leave lines 1733-1774 unchanged.

---

### Step 9: Update `shitty_ui/components/insights.py` — replace private function

**File to modify**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/insights.py`

#### 9a: Add import (after line 16)

**Current code at lines 15-17:**
```python
from constants import COLORS
from brand_copy import COPY
```

**Replace with:**
```python
from constants import COLORS
from brand_copy import COPY
from components.helpers import format_time_ago
```

#### 9b: Remove `_format_insight_timestamp` function (lines 37-61)

**Current code:**
```python
def _format_insight_timestamp(ts) -> str:
    """Format a timestamp into a human-readable relative string.

    Args:
        ts: datetime object or None.

    Returns:
        String like "2d ago", "5h ago", or "" if None.
    """
    if ts is None:
        return ""
    if not isinstance(ts, datetime):
        return str(ts)[:10]

    delta = datetime.now() - ts
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
```

**Replace with:**
```python
# Time formatting moved to components.helpers.format_time_ago
```

#### 9c: Update call site (line 89)

**Current code:**
```python
    time_str = _format_insight_timestamp(timestamp)
```

**Replace with:**
```python
    time_str = format_time_ago(timestamp)
```

---

### Step 10: Update test imports in `test_cards.py`

**File to modify**: `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_cards.py`

No changes needed to existing test imports or tests. The `get_sentiment_style` function stays in `cards.py` -- it is NOT being moved. All existing card function tests remain valid because the card functions still produce identical output (just delegating internally to helpers).

However, if any existing test directly calls `_format_insight_timestamp` from insights, that needs updating. Let me verify:

The only test file for insights is `shit_tests/shitty_ui/test_insights.py`. It tests `get_dynamic_insights()` and `create_insight_cards()` -- it does NOT directly test `_format_insight_timestamp`. No test file changes are needed for existing tests.

---

## Summary of All Changes

| File | Action | What Changes |
|------|--------|-------------|
| `shitty_ui/components/helpers.py` | **Create** | New file with 4 helper functions (~140 lines) |
| `shitty_ui/components/cards.py` | **Modify** | Add 1 import line; replace ~100 lines across 4 functions with helper calls |
| `shitty_ui/components/insights.py` | **Modify** | Add 1 import line; delete 25-line private function; update 1 call site |
| `shit_tests/shitty_ui/test_helpers.py` | **Create** | New test file (~200 lines) |

**Net line count change**: cards.py shrinks by ~100 lines. helpers.py adds ~140 lines. insights.py shrinks by ~24 lines. Total: ~16 more lines of production code, but zero duplication.

---

## Test Plan

### New test file: `shit_tests/shitty_ui/test_helpers.py`

**File to create**: `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_helpers.py`

```python
"""Tests for shitty_ui/components/helpers.py - Shared UI helper functions."""

import sys
import os

# Add shitty_ui to path for imports (matches pattern from test_cards.py)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

from components.helpers import (
    format_time_ago,
    extract_sentiment,
    create_outcome_badge,
    format_asset_display,
)
from constants import COLORS


class TestFormatTimeAgo:
    """Tests for format_time_ago()."""

    def test_none_returns_empty_string(self):
        assert format_time_ago(None) == ""

    def test_non_datetime_returns_truncated_string(self):
        assert format_time_ago("2025-06-15T10:30:00") == "2025-06-15"

    def test_integer_returns_truncated_string(self):
        assert format_time_ago(1234567890) == "1234567890"

    @patch("components.helpers.datetime")
    def test_weeks_ago(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 6, 22, 12, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        # 15 days ago -> 2 weeks
        ts = datetime(2025, 6, 7, 12, 0)
        result = format_time_ago(ts)
        assert result == "2w ago"

    @patch("components.helpers.datetime")
    def test_days_ago(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 6, 15, 12, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        ts = datetime(2025, 6, 12, 12, 0)
        result = format_time_ago(ts)
        assert result == "3d ago"

    @patch("components.helpers.datetime")
    def test_hours_ago(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 6, 15, 15, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        ts = datetime(2025, 6, 15, 12, 0)
        result = format_time_ago(ts)
        assert result == "3h ago"

    @patch("components.helpers.datetime")
    def test_minutes_ago(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 6, 15, 12, 30)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        ts = datetime(2025, 6, 15, 12, 5)
        result = format_time_ago(ts)
        assert result == "25m ago"

    @patch("components.helpers.datetime")
    def test_just_now(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 6, 15, 12, 0, 30)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        ts = datetime(2025, 6, 15, 12, 0, 5)
        result = format_time_ago(ts)
        assert result == "just now"

    @patch("components.helpers.datetime")
    def test_exactly_7_days_shows_weeks(self, mock_dt):
        """7 days is NOT > 7, should show days not weeks."""
        mock_dt.now.return_value = datetime(2025, 6, 22, 12, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        ts = datetime(2025, 6, 15, 12, 0)
        result = format_time_ago(ts)
        assert result == "7d ago"

    @patch("components.helpers.datetime")
    def test_8_days_shows_weeks(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 6, 23, 12, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        ts = datetime(2025, 6, 15, 12, 0)
        result = format_time_ago(ts)
        assert result == "1w ago"


class TestExtractSentiment:
    """Tests for extract_sentiment()."""

    def test_bullish_dict(self):
        assert extract_sentiment({"AAPL": "bullish"}) == "bullish"

    def test_bearish_dict(self):
        assert extract_sentiment({"TSLA": "Bearish"}) == "bearish"

    def test_neutral_dict(self):
        assert extract_sentiment({"SPY": "neutral"}) == "neutral"

    def test_empty_dict_returns_neutral(self):
        assert extract_sentiment({}) == "neutral"

    def test_none_returns_neutral(self):
        assert extract_sentiment(None) == "neutral"

    def test_non_dict_returns_neutral(self):
        assert extract_sentiment("bullish") == "neutral"

    def test_non_string_value_returns_neutral(self):
        assert extract_sentiment({"AAPL": 42}) == "neutral"

    def test_multi_asset_uses_first(self):
        # Dicts preserve insertion order in Python 3.7+
        result = extract_sentiment({"AAPL": "bullish", "TSLA": "bearish"})
        assert result == "bullish"

    def test_mixed_case_normalized(self):
        assert extract_sentiment({"AAPL": "BULLISH"}) == "bullish"


class TestCreateOutcomeBadge:
    """Tests for create_outcome_badge()."""

    def test_correct_with_pnl(self):
        badge = create_outcome_badge(True, pnl_display=150.0)
        assert badge.style["color"] == COLORS["success"]
        text = _extract_text(badge)
        assert "+$150" in text

    def test_correct_without_pnl(self):
        badge = create_outcome_badge(True, pnl_display=None)
        text = _extract_text(badge)
        assert "Correct" in text

    def test_incorrect_with_pnl(self):
        badge = create_outcome_badge(False, pnl_display=-75.0)
        assert badge.style["color"] == COLORS["danger"]
        text = _extract_text(badge)
        assert "$-75" in text

    def test_incorrect_without_pnl(self):
        badge = create_outcome_badge(False, pnl_display=None)
        text = _extract_text(badge)
        assert "Incorrect" in text

    def test_pending(self):
        badge = create_outcome_badge(None)
        assert badge.style["color"] == COLORS["warning"]
        text = _extract_text(badge)
        assert "Pending" in text

    def test_default_font_size(self):
        badge = create_outcome_badge(True)
        assert badge.style["fontSize"] == "0.75rem"

    def test_custom_font_size(self):
        badge = create_outcome_badge(True, font_size="0.8rem")
        assert badge.style["fontSize"] == "0.8rem"

    def test_correct_with_zero_pnl(self):
        """Zero P&L is falsy -- should show 'Correct', not '$0'."""
        badge = create_outcome_badge(True, pnl_display=0)
        text = _extract_text(badge)
        assert "Correct" in text

    def test_incorrect_with_zero_pnl(self):
        """Zero P&L is falsy -- should show 'Incorrect', not '$0'."""
        badge = create_outcome_badge(False, pnl_display=0)
        text = _extract_text(badge)
        assert "Incorrect" in text


class TestFormatAssetDisplay:
    """Tests for format_asset_display()."""

    def test_single_asset(self):
        assert format_asset_display(["AAPL"]) == "AAPL"

    def test_two_assets(self):
        assert format_asset_display(["AAPL", "TSLA"]) == "AAPL, TSLA"

    def test_three_assets_at_limit(self):
        assert format_asset_display(["AAPL", "TSLA", "GOOG"]) == "AAPL, TSLA, GOOG"

    def test_four_assets_shows_overflow(self):
        result = format_asset_display(["AAPL", "TSLA", "GOOG", "AMZN"])
        assert result == "AAPL, TSLA, GOOG +1"

    def test_custom_max_count(self):
        result = format_asset_display(["AAPL", "TSLA", "GOOG", "AMZN"], max_count=4)
        assert result == "AAPL, TSLA, GOOG, AMZN"

    def test_overflow_disabled(self):
        result = format_asset_display(
            ["AAPL", "TSLA", "GOOG", "AMZN"], max_count=3, show_overflow=False
        )
        assert result == "AAPL, TSLA, GOOG"
        assert "+" not in result

    def test_non_list_stringified(self):
        assert format_asset_display("AAPL") == "AAPL"

    def test_none_returns_empty(self):
        assert format_asset_display(None) == ""

    def test_empty_list(self):
        assert format_asset_display([]) == ""

    def test_max_count_5(self):
        assets = ["A", "B", "C", "D", "E", "F"]
        result = format_asset_display(assets, max_count=5)
        assert result == "A, B, C, D, E +1"


def _extract_text(component) -> str:
    """Recursively extract all text content from a Dash component tree."""
    parts = []
    if isinstance(component, str):
        return component
    if isinstance(component, (int, float)):
        return str(component)
    if hasattr(component, "children"):
        children = component.children
        if isinstance(children, str):
            parts.append(children)
        elif isinstance(children, (int, float)):
            parts.append(str(children))
        elif isinstance(children, list):
            for child in children:
                if child is not None:
                    parts.append(_extract_text(child))
        elif children is not None:
            parts.append(_extract_text(children))
    return " ".join(parts)
```

### Tests: coverage expectations

| Helper | Test Count | Coverage |
|--------|-----------|----------|
| `format_time_ago` | 10 | All branches: None, non-datetime, weeks, days, hours, minutes, just-now, boundary at 7d/8d |
| `extract_sentiment` | 9 | All branches: bullish, bearish, neutral, empty dict, None, non-dict, non-string value, multi-asset, mixed case |
| `create_outcome_badge` | 8 | All branches: correct+pnl, correct-no-pnl, incorrect+pnl, incorrect-no-pnl, pending, font sizes, zero pnl edge cases |
| `format_asset_display` | 9 | All branches: single, exact limit, overflow, custom max, overflow disabled, non-list, None, empty, max_count=5 |
| **Total** | **36** | |

### Existing tests to verify (no modifications needed)

All existing card tests in `shit_tests/shitty_ui/test_cards.py` must continue to pass unchanged. These tests call the card functions (e.g., `create_hero_signal_card()`, `create_signal_card()`) and verify their output -- since the output is identical (just generated via helpers now), all assertions remain valid.

Run the full test suite to confirm:
```bash
./venv/bin/python -m pytest shit_tests/shitty_ui/test_cards.py -v
./venv/bin/python -m pytest shit_tests/shitty_ui/test_insights.py -v
./venv/bin/python -m pytest shit_tests/shitty_ui/test_helpers.py -v
```

---

## Documentation Updates

No README or external documentation changes needed. This is a pure internal refactor.

Add a single-line entry to `CHANGELOG.md` under `## [Unreleased]`:

```markdown
### Changed
- **UI helpers extracted** - Consolidated 4 duplicated patterns (time-ago, sentiment extraction, outcome badges, asset display) from cards.py into shared `components/helpers.py`

### Fixed
- **Hero card weeks display** - Hero signal cards now correctly show "2w ago" for posts older than 7 days (was showing "14d ago")
```

---

## Stress Testing & Edge Cases

### Edge cases handled by `format_time_ago`

| Input | Expected Output | Notes |
|-------|----------------|-------|
| `None` | `""` | Graceful no-data handling |
| `"2025-06-15T10:30:00"` (string) | `"2025-06-15"` | Non-datetime fallback |
| `datetime.now() - timedelta(seconds=5)` | `"just now"` | Sub-minute case (was "0m ago" in some implementations) |
| `datetime.now() - timedelta(days=7)` | `"7d ago"` | Boundary: exactly 7 days is NOT > 7 |
| `datetime.now() - timedelta(days=8)` | `"1w ago"` | First week threshold |
| `datetime.now() - timedelta(days=100)` | `"14w ago"` | Large day counts |

### Edge cases handled by `extract_sentiment`

| Input | Expected Output | Notes |
|-------|----------------|-------|
| `{}` | `"neutral"` | Empty dict |
| `None` | `"neutral"` | None input |
| `{"AAPL": 42}` | `"neutral"` | Non-string value in dict |
| `{"AAPL": "BULLISH"}` | `"bullish"` | Case normalization |
| `"bullish"` (raw string, not dict) | `"neutral"` | Wrong type |

### Edge cases handled by `create_outcome_badge`

| Input | Expected Output | Notes |
|-------|----------------|-------|
| `correct_t7=True, pnl_display=0` | Shows "Correct" (not "$0") | Zero is falsy in Python |
| `correct_t7=True, pnl_display=0.0` | Shows "Correct" (not "$0") | Float zero also falsy |
| `correct_t7=False, pnl_display=-500.5` | Shows "$-501" | Negative P&L formatted with :,.0f |

### Edge cases handled by `format_asset_display`

| Input | Expected Output | Notes |
|-------|----------------|-------|
| `[]` | `""` | Empty list |
| `None` | `""` | None input |
| `["AAPL"]` | `"AAPL"` | Single asset, no overflow |
| `"AAPL"` (string, not list) | `"AAPL"` | Non-list stringified |

---

## Verification Checklist

After implementation, verify every item below:

- [ ] `shitty_ui/components/helpers.py` exists and contains exactly 4 public functions
- [ ] `shitty_ui/components/cards.py` imports all 4 helpers from `components.helpers`
- [ ] `shitty_ui/components/insights.py` imports `format_time_ago` from `components.helpers`
- [ ] `_format_insight_timestamp` function is removed from `insights.py`
- [ ] `insights.py` line 89 calls `format_time_ago(timestamp)` not `_format_insight_timestamp(timestamp)`
- [ ] Hero card time-ago now shows weeks (e.g., "2w ago" for 14-day-old posts)
- [ ] `create_prediction_timeline_card()` outcome badge is NOT changed (different visual style)
- [ ] `create_feed_signal_card()` outcome badges (lines 1733-1774) are NOT changed (Bootstrap badge style)
- [ ] `create_post_card()` sentiment extraction preserves `None` default (not `"neutral"`)
- [ ] All existing tests pass: `./venv/bin/python -m pytest shit_tests/shitty_ui/ -v`
- [ ] New helper tests pass: `./venv/bin/python -m pytest shit_tests/shitty_ui/test_helpers.py -v`
- [ ] 36 new tests all green
- [ ] `ruff check shitty_ui/components/helpers.py shitty_ui/components/cards.py shitty_ui/components/insights.py` reports no issues
- [ ] `ruff format --check shitty_ui/components/helpers.py shitty_ui/components/cards.py shitty_ui/components/insights.py` reports no changes needed
- [ ] Dashboard loads correctly at `http://localhost:8050` with no visual regressions
- [ ] CHANGELOG.md updated with entries under `## [Unreleased]`

---

## What NOT To Do

1. **Do NOT move `get_sentiment_style()` to helpers.py.** It lives in `cards.py` (lines 42-60) and is imported by multiple files. Moving it is a separate concern and risks breaking import chains. This phase only extracts the 4 *duplicated* patterns.

2. **Do NOT replace the timeline card's outcome badge (lines 1120-1147).** It uses `className="badge"` with solid `backgroundColor` and no icon -- a visually distinct component from the icon-based `create_outcome_badge()`. Forcing it through the shared helper would require adding parameters for `className`, `backgroundColor`, `marginLeft`, and text color -- making the helper worse, not better.

3. **Do NOT replace the feed card's outcome badges (lines 1733-1774).** Same reason as #2 -- they are Bootstrap solid-background badges, not icon+text badges.

4. **Do NOT change `format_time_ago` to use `max(1, ...)` for the minutes case.** The old `create_signal_card()` had `max(1, delta.seconds // 60)` to avoid "0m ago". The new helper returns `"just now"` for sub-60-second deltas, which is a better UX and matches what `insights.py` already did.

5. **Do NOT add timezone awareness to `format_time_ago`.** The existing code uses naive `datetime.now()` everywhere. Adding timezone support is a separate concern for a future phase. Match the existing behavior exactly.

6. **Do NOT move `strip_urls()` or `_safe_get()` to helpers.py in this PR.** They are not part of the 4 identified duplication patterns. Keep the scope tight.

7. **Do NOT change the `create_post_card()` sentiment default from `None` to `"neutral"`.** The function uses `sentiment or "neutral"` downstream (line 933). Changing the default would break the `card_border_color` logic. Use the `raw_sentiment if raw_sentiment != "neutral" else None` pattern shown in Step 6a.

8. **Do NOT mock `datetime` in the helpers module using `@patch("datetime.datetime")`.** The correct mock target is `@patch("components.helpers.datetime")` because `format_time_ago` imports `datetime` at module scope. Patching the wrong target will make tests non-deterministic.

9. **Do NOT add helpers.py exports to `components/__init__.py`.** The `__init__.py` is currently empty (1 line). All imports in this codebase use explicit module paths (`from components.helpers import ...`). Adding re-exports would be inconsistent with the existing pattern.
