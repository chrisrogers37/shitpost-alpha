# Phase 06: Consistent Confidence Display Format

**Status:** COMPLETE
**PR:** #64

**PR Title**: `fix(ui): standardize confidence display format across all card types`
**Risk Level**: Low (cosmetic change only, no data mutation, no calculation changes)
**Estimated Effort**: Small (1-2 hours implementation + tests)
**Files Modified**: 1 primary source file, 1 test file (new or extended), CHANGELOG.md

| File | Change |
|------|--------|
| `shitty_ui/components/cards.py` | Standardize 5 confidence rendering locations |
| `shit_tests/shitty_ui/test_cards.py` | Add tests for confidence display consistency |
| `CHANGELOG.md` | Add entry under `[Unreleased]` |

---

## 1. Context

Confidence is the single most important signal metadata element -- it tells the user how much weight the LLM placed behind a prediction. Currently, it is rendered in at least 4 different string formats across the card components in `cards.py`:

| Card Type | Function | Line | Current Format | Example Output |
|-----------|----------|------|----------------|---------------|
| Hero signal card | `create_hero_signal_card` | 208 | `f"Conf: {confidence:.0%}"` | `Conf: 75%` |
| Signal card | `create_signal_card` | 412 | `f"{confidence:.0%}"` | `75%` |
| Post card | `create_post_card` | 500 | `f" | Confidence: {confidence:.0%}"` | ` | Confidence: 75%` |
| Prediction timeline card | `create_prediction_timeline_card` | 760 | `f" | Confidence: {confidence:.0%}"` | ` | Confidence: 75%` |
| Feed signal card | `create_feed_signal_card` | 1345 | `f"{confidence:.0%}"` + visual bar | `75%` + bar |

This inconsistency makes the dashboard look unfinished. A user scanning from the hero card to the signal sidebar to the Latest Posts section encounters three different labels for the same data point. Standardizing on one format is a small change with an outsized impact on perceived polish.

### Chosen Standard Format

**`{confidence:.0%}`** (e.g., `75%`) -- bare percentage with no text label.

Rationale:
- The context already makes the meaning clear: confidence always appears alongside sentiment and asset tickers in the bottom metadata row of every card.
- Removing the text label saves horizontal space, which matters on mobile layouts where the bottom row wraps.
- The signal card (line 412) and feed signal card (line 1345) already use this format -- they represent the majority of cards users see.
- A tooltip can be added later if user research reveals ambiguity, but the current layout (sentiment badge + tickers + percentage) is self-explanatory.

The pipe separator (`" | "`) used in `create_post_card` and `create_prediction_timeline_card` is a separate formatting concern (those cards use a different layout with inline pipe-separated metadata). The pipe itself is not part of the confidence format -- only the label text inside it needs to change.

---

## 2. Dependencies

**Depends on Phase 05 completing first.** Phase 05 (Strip URLs from Card Previews) modifies the same file (`shitty_ui/components/cards.py`) and may shift line numbers. This phase should be implemented after Phase 05 is merged. If Phase 05 creates a new test file at `shit_tests/shitty_ui/test_cards.py`, the confidence display tests in this phase should be added to that same file rather than creating a duplicate.

No other dependencies. No backend, database, API, or configuration changes required.

---

## 3. Detailed Implementation Plan

All changes are in a single file: `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/cards.py`

Line numbers below refer to the current state of the file on `main` (commit `6e5df67`). If Phase 05 has been merged, line numbers will have shifted by approximately +15 lines (due to the `strip_urls` helper and `import re` addition). The code patterns are unambiguous regardless of line offset.

### 3.1 `create_hero_signal_card` -- Line 207-213

This is the only location that uses the `Conf:` abbreviation. Change it to the bare percentage format.

**Current code (lines 207-213):**
```python
                    html.Span(
                        f"Conf: {confidence:.0%}",
                        style={
                            "color": COLORS["text_muted"],
                            "fontSize": "0.8rem",
                        },
                    ),
```

**New code:**
```python
                    html.Span(
                        f"{confidence:.0%}",
                        style={
                            "color": COLORS["text_muted"],
                            "fontSize": "0.8rem",
                        },
                    ),
```

**Change**: Remove the `Conf: ` prefix from the f-string. Everything else (style, element type, position in the layout) stays the same.

### 3.2 `create_signal_card` -- Line 411-417

This location already uses the target format (`f"{confidence:.0%}"`). **No change required.** It serves as the reference implementation.

**Current code (lines 411-417):**
```python
                    html.Span(
                        f"{confidence:.0%}",
                        style={
                            "color": COLORS["text_muted"],
                            "fontSize": "0.78rem",
                        },
                    ),
```

**Verification only**: Confirm this matches the standard. It does.

### 3.3 `create_post_card` -- Lines 499-505

This location uses `" | Confidence: {confidence:.0%}"` with the full word label and a pipe prefix. The pipe is part of the layout pattern for this card (inline pipe-separated metadata: `BULLISH | AAPL, TSLA | Confidence: 75%`), so we keep the pipe but remove the word "Confidence: ".

**Current code (lines 499-505):**
```python
                        html.Span(
                            f" | Confidence: {confidence:.0%}" if confidence else "",
                            style={
                                "color": COLORS["text_muted"],
                                "fontSize": "0.85rem",
                            },
                        ),
```

**New code:**
```python
                        html.Span(
                            f" | {confidence:.0%}" if confidence else "",
                            style={
                                "color": COLORS["text_muted"],
                                "fontSize": "0.85rem",
                            },
                        ),
```

**Change**: Remove the `Confidence: ` label from the f-string, keeping the `" | "` pipe separator that visually separates this field from the asset tickers before it. The conditional `if confidence else ""` is preserved to handle the None/falsy case.

### 3.4 `create_prediction_timeline_card` -- Lines 759-768

Same pattern as the post card: pipe-separated inline metadata with a full `Confidence:` label.

**Current code (lines 759-768):**
```python
                            html.Span(
                                f" | Confidence: {confidence:.0%}"
                                if confidence
                                else "",
                                style={
                                    "color": COLORS["text_muted"],
                                    "fontSize": "0.85rem",
                                    "marginLeft": "10px",
                                },
                            ),
```

**New code:**
```python
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
```

**Change**: Remove the `Confidence: ` label from the f-string. Keep the pipe separator and conditional. Keep the `marginLeft` styling that provides spacing from the sentiment badge.

### 3.5 `create_feed_signal_card` -- Lines 1342-1353

This location already uses the target format (`f"{confidence:.0%}"`) paired with a visual confidence bar. **No change required.**

**Current code (lines 1342-1353):**
```python
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
```

**Verification only**: Confirm this matches the standard. It does. The visual confidence bar is a bonus element on this card type and does not conflict with the standard format.

### Summary of Changes

| Function | Line | Action | Before | After |
|----------|------|--------|--------|-------|
| `create_hero_signal_card` | 208 | **CHANGE** | `Conf: 75%` | `75%` |
| `create_signal_card` | 412 | No change | `75%` | `75%` |
| `create_post_card` | 500 | **CHANGE** | ` | Confidence: 75%` | ` | 75%` |
| `create_prediction_timeline_card` | 760 | **CHANGE** | ` | Confidence: 75%` | ` | 75%` |
| `create_feed_signal_card` | 1345 | No change | `75%` + bar | `75%` + bar |

Total lines changed: 3 lines in 3 functions. This is an intentionally minimal change.

---

## 4. Out-of-Scope Confidence Displays (Why They Are Excluded)

Several other files render confidence values. These are intentionally excluded from this phase because they serve different contexts where a label or different format is appropriate:

| File | Line | Format | Why Excluded |
|------|------|--------|-------------|
| `callbacks/alerts.py` | 1140 | `f" | {confidence:.0%}"` | Alert history cards in the notification panel. Already uses the bare percentage format with pipe separator. Matches the new standard. |
| `callbacks/alerts.py` | 909 | JS: `confidence * 100 + "%"` | Browser push notification body text. This renders as `BULLISH (75% confidence)` in the OS notification. The word "confidence" appears after the percentage in prose context, not as a label. OS notifications need clarity without visual context. Out of scope. |
| `components/charts.py` | 97 | `f"Confidence: <b>{confidence:.0%}</b>"` | Plotly chart hover tooltip text. Tooltips are standalone text boxes that lack visual context cues, so the explicit label is necessary for comprehension. Out of scope. |
| `pages/assets.py` | 370 | `f"Confidence: {stats['avg_confidence']:.0%}"` | Subtitle of a metric card (via `create_metric_card`). This is a standalone subtitle string, not inline metadata. The label provides necessary context because the subtitle text stands alone below a primary metric value. Out of scope. |

If the user wants these secondary locations standardized as well, they should be handled in a follow-up phase to keep this change focused and reviewable.

---

## 5. Test Plan

### 5.1 Test File Location

If Phase 05 has already created `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_cards.py`, add a new test class to that file. Otherwise, create the file following the same pattern as `test_charts.py`.

### 5.2 Test Approach

The tests verify that each card function's output contains the confidence value in the standardized format and does NOT contain the old labeled formats. Since Dash components are Python objects with inspectable properties, we can render a card and search its component tree for the confidence text.

```python
"""Tests for confidence display consistency in card components."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))

import pytest
from datetime import datetime

from components.cards import (
    create_hero_signal_card,
    create_signal_card,
    create_post_card,
    create_prediction_timeline_card,
    create_feed_signal_card,
)


def _extract_text(component) -> str:
    """Recursively extract all text content from a Dash component tree."""
    parts = []
    if isinstance(component, str):
        return component
    if hasattr(component, "children"):
        children = component.children
        if isinstance(children, str):
            parts.append(children)
        elif isinstance(children, list):
            for child in children:
                if child is not None:
                    parts.append(_extract_text(child))
        elif children is not None:
            parts.append(_extract_text(children))
    return " ".join(parts)


def _make_row(**overrides):
    """Create a minimal row dict for card rendering."""
    base = {
        "timestamp": datetime(2025, 6, 15, 10, 30),
        "text": "Big announcement about tariffs today",
        "confidence": 0.75,
        "assets": ["AAPL", "TSLA"],
        "market_impact": {"AAPL": "bullish"},
        "correct_t7": None,
        "pnl_t7": None,
        "analysis_status": "completed",
        "thesis": "Tariffs expected to boost domestic production",
        "replies_count": 10,
        "reblogs_count": 5,
        "favourites_count": 20,
    }
    base.update(overrides)
    return base


def _make_timeline_row(**overrides):
    """Create a minimal row dict for prediction timeline card."""
    base = {
        "prediction_date": datetime(2025, 6, 15),
        "timestamp": datetime(2025, 6, 15, 10, 30),
        "text": "Trade deal announcement",
        "prediction_sentiment": "bullish",
        "prediction_confidence": 0.75,
        "return_t7": 2.5,
        "correct_t7": True,
        "pnl_t7": 250.0,
        "price_at_prediction": 150.0,
        "price_t7": 153.75,
    }
    base.update(overrides)
    return base


class TestConfidenceDisplayConsistency:
    """Verify all card types display confidence in standardized format."""

    def test_hero_signal_card_no_conf_label(self):
        """Hero signal card should show '75%' not 'Conf: 75%'."""
        card = create_hero_signal_card(_make_row(confidence=0.75))
        text = _extract_text(card)
        assert "75%" in text
        assert "Conf:" not in text
        assert "Confidence:" not in text

    def test_signal_card_bare_percentage(self):
        """Signal card should show bare percentage."""
        card = create_signal_card(_make_row(confidence=0.80))
        text = _extract_text(card)
        assert "80%" in text
        assert "Conf:" not in text
        assert "Confidence:" not in text

    def test_post_card_no_confidence_label(self):
        """Post card should show '| 75%' not '| Confidence: 75%'."""
        card = create_post_card(_make_row(confidence=0.75))
        text = _extract_text(card)
        assert "75%" in text
        assert "Confidence:" not in text

    def test_prediction_timeline_card_no_confidence_label(self):
        """Prediction timeline card should show '| 75%' not '| Confidence: 75%'."""
        card = create_prediction_timeline_card(_make_timeline_row(prediction_confidence=0.75))
        text = _extract_text(card)
        assert "75%" in text
        assert "Confidence:" not in text

    def test_feed_signal_card_bare_percentage(self):
        """Feed signal card should show bare percentage."""
        card = create_feed_signal_card(_make_row(confidence=0.85))
        text = _extract_text(card)
        assert "85%" in text
        assert "Conf:" not in text
        assert "Confidence:" not in text

    def test_confidence_zero_renders(self):
        """0% confidence should still render, not be suppressed."""
        card = create_hero_signal_card(_make_row(confidence=0.0))
        text = _extract_text(card)
        assert "0%" in text

    def test_confidence_one_hundred_renders(self):
        """100% confidence should render correctly."""
        card = create_signal_card(_make_row(confidence=1.0))
        text = _extract_text(card)
        assert "100%" in text

    def test_post_card_no_confidence_when_none(self):
        """Post card should render empty string when confidence is None."""
        card = create_post_card(_make_row(confidence=None))
        text = _extract_text(card)
        assert "Confidence:" not in text
        # Should not crash

    def test_prediction_timeline_no_confidence_when_zero(self):
        """Prediction timeline card hides confidence when falsy (0)."""
        card = create_prediction_timeline_card(_make_timeline_row(prediction_confidence=0))
        text = _extract_text(card)
        # When confidence is 0 (falsy), the conditional hides it entirely
        assert "Confidence:" not in text
```

### 5.3 Running Tests

```bash
source venv/bin/activate && pytest shit_tests/shitty_ui/test_cards.py -v -k "Confidence"
```

### 5.4 Integration Verification

After implementing, visually verify on the running dashboard:

1. **Main dashboard** -- Hero signal cards in the top section should show `75%` not `Conf: 75%`
2. **Signal sidebar** -- Signal cards should show `75%` (already correct, verify no regression)
3. **Latest Posts section** -- Post cards should show `| 75%` not `| Confidence: 75%`
4. **`/signals` page** -- Feed signal cards should show `75%` + visual bar (already correct, verify no regression)
5. **`/assets/<ticker>` page** -- Prediction timeline cards should show `| 75%` not `| Confidence: 75%`

---

## 6. Documentation Updates

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Fixed
- **Inconsistent confidence display across card types** - Standardized confidence format to bare percentage (e.g., `75%`) across hero signal cards, post cards, and prediction timeline cards. Previously used three different formats: `Conf: 75%`, `75%`, and `Confidence: 75%`.
```

---

## 7. Edge Cases

| Edge Case | Expected Behavior | How It Is Handled |
|-----------|-------------------|-------------------|
| `confidence = None` | Post card and prediction timeline card render empty string (no crash) | Existing conditional: `if confidence else ""` evaluates `None` as falsy, producing `""`. No change needed. |
| `confidence = 0` | Hero and signal cards render `0%`. Post card and prediction timeline card render empty string (falsy). | The `:.0%` format spec handles `0` correctly as `0%`. The falsy conditional in post/timeline cards suppresses `0` -- this is existing behavior and intentional (0% confidence predictions are typically bypassed). |
| `confidence = 0.0` | Same as `0` above. | `0.0` is falsy in Python, same handling. |
| `confidence = 1.0` | Renders as `100%`. | The `:.0%` format spec multiplies by 100 and rounds, producing `100%`. |
| `confidence = 0.999` | Renders as `100%` (rounds up). | `:.0%` rounds to 0 decimal places: `0.999 * 100 = 99.9 -> 100%`. This is correct behavior -- the rounding is appropriate for display. |
| `confidence = 0.001` | Renders as `0%` (rounds down). | `:.0%` rounds: `0.001 * 100 = 0.1 -> 0%`. This is correct -- sub-1% confidence is effectively zero. |
| `confidence = NaN` | Python's `:.0%` format spec on `float('nan')` produces `nan%`. | This would be a data quality issue upstream. The display layer should not guard against NaN -- it should be caught during analysis. No change in this phase. If NaN display becomes a real problem, a separate phase should add a `format_confidence()` helper with NaN handling. |

---

## 8. Verification Checklist

- [ ] `create_hero_signal_card`: Line 208 changed from `f"Conf: {confidence:.0%}"` to `f"{confidence:.0%}"`
- [ ] `create_signal_card`: Line 412 verified as already using `f"{confidence:.0%}"` (no change)
- [ ] `create_post_card`: Line 500 changed from `f" | Confidence: {confidence:.0%}"` to `f" | {confidence:.0%}"`
- [ ] `create_prediction_timeline_card`: Line 760 changed from `f" | Confidence: {confidence:.0%}"` to `f" | {confidence:.0%}"`
- [ ] `create_feed_signal_card`: Line 1345 verified as already using `f"{confidence:.0%}"` (no change)
- [ ] No other lines in `cards.py` contain `Conf:` or `Confidence:` as a display label
- [ ] Tests added/extended in `shit_tests/shitty_ui/test_cards.py` covering all 5 card functions
- [ ] Tests verify absence of old label formats (`Conf:`, `Confidence:`) in rendered output
- [ ] Tests cover edge cases: 0%, 100%, None confidence
- [ ] All tests pass: `source venv/bin/activate && pytest shit_tests/shitty_ui/test_cards.py -v`
- [ ] Existing tests still pass: `source venv/bin/activate && pytest shit_tests/shitty_ui/ -v`
- [ ] Full test suite unaffected: `source venv/bin/activate && pytest -x`
- [ ] Linting passes: `source venv/bin/activate && python3 -m ruff check shitty_ui/components/cards.py`
- [ ] CHANGELOG.md updated with entry under `[Unreleased]`

---

## 9. What NOT To Do

1. **Do NOT change the confidence calculation or the `:.0%` format specifier.** This phase changes only the label text surrounding the value. The format `:.0%` (which multiplies by 100 and appends `%` with zero decimal places) is correct and consistent everywhere.

2. **Do NOT remove the pipe separator (`" | "`) from `create_post_card` or `create_prediction_timeline_card`.** The pipe is a layout separator between metadata fields in those specific cards (e.g., `BULLISH | AAPL | 75%`). Removing it would break the visual layout. Only the word `Confidence: ` inside the pipe-separated field is being removed.

3. **Do NOT modify confidence displays outside of `cards.py`.** The chart tooltip (`charts.py` line 97), metric card subtitle (`assets.py` line 370), alert history cards (`alerts.py` line 1140), and browser notifications (`alerts.py` line 909) each have valid reasons for their format in their respective contexts. See Section 4 for the rationale.

4. **Do NOT add a confidence icon (e.g., gauge icon) in this phase.** The enhancement description mentions "a small icon or tooltip" as optional. Adding an icon is a separate design decision that should be evaluated independently. This phase focuses solely on removing inconsistent text labels.

5. **Do NOT add a `format_confidence()` helper function.** With only 3 lines changing (and all using the same `f"{confidence:.0%}"` pattern), a helper function would be over-engineering. If a future phase wants to add NaN handling, color-coding, or icon logic to confidence display, that is the appropriate time to extract a helper.

6. **Do NOT change the confidence bar in `create_feed_signal_card`.** The visual bar (lines 1223-1252) is a bonus visual element specific to the feed page. It complements the percentage and should remain as-is.

7. **Do NOT change the `confidence_range` slider or any data-layer confidence references in `dashboard.py` or `data.py`.** These are functional elements (filtering, querying), not display labels.

---

### Critical Files for Implementation
- `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/cards.py` - Primary target: 3 f-string label changes across 3 functions (lines 208, 500, 760)
- `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_cards.py` - Test file to create or extend with confidence display consistency tests
- `/Users/chris/Projects/shitpost-alpha/CHANGELOG.md` - Add entry under `[Unreleased]` section
- `/Users/chris/Projects/shitpost-alpha/shitty_ui/callbacks/alerts.py` - Reference only: verify alert history cards (line 1140) already match the standard format
- `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_charts.py` - Reference for test file conventions (sys.path setup, import patterns)