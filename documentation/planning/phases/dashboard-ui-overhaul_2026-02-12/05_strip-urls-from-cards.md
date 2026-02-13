# Phase 05: Strip URLs from Card Previews

**Status**: COMPLETE (PR #62)

**PR Title**: `fix: strip raw URLs from card text previews to improve readability`
**Risk Level**: Low (cosmetic change, preview-only, no data mutation)
**Estimated Effort**: Small (1-2 hours implementation + tests)
**Files Modified**: 1 source file, 1 new test file, CHANGELOG.md

---

## Context

Card components across the dashboard display truncated text previews of Truth Social posts. These posts frequently contain raw URLs such as:

```
BREAKING: Pentagon prepares second aircraft carrier https://www.wsj.com/politics/national-security/pentagon-prepares-second-aircraft-carrier-to-deploy-to-the-middle-east-e7140a64
```

A URL like the one above consumes approximately 100 of the 120-200 available preview characters, pushing actual post content out of the preview entirely. The result is cards that display nearly nothing but a URL string -- ugly, uninformative, and a waste of the limited preview space.

URLs add zero value in a card preview context. Users cannot click raw text in a Dash `html.P` element, and the URL itself communicates nothing that the post text does not already convey. The fix is to strip URLs from text before truncation, applied consistently across all five card functions that generate text previews.

---

## Dependencies

None. This is a standalone cosmetic improvement with no dependencies on other phases or features. Safe for Batch 1 (can be implemented and merged independently).

---

## Detailed Implementation Plan

### Step 1: Add the `strip_urls` helper function

Add a new utility function at the top of `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/cards.py`, immediately after the existing imports (after line 10, before line 13).

**Add import (line 3 area, among the existing imports):**

```python
import re
```

**Add helper function (insert between line 10 and line 13, i.e., after the `from constants import COLORS` line and before the `def create_error_card` function):**

```python

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
```

**Why this regex**: `https?://\S+` matches any sequence starting with `http://` or `https://` followed by one or more non-whitespace characters. This is intentionally simple and conservative. It will not match bare domain names like `wsj.com` (which are rarely present in these posts and would risk false positives on legitimate text). The `\S+` is greedy and will consume the entire URL including paths, query parameters, and fragments.

### Step 2: Apply `strip_urls` in `create_hero_signal_card`

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/cards.py`
**Line 78**

**Before:**
```python
    preview = text_content[:200] + "..." if len(text_content) > 200 else text_content
```

**After:**
```python
    text_content = strip_urls(text_content)
    preview = text_content[:200] + "..." if len(text_content) > 200 else text_content
```

The `strip_urls` call is placed before the truncation so that the 200-character budget is spent on meaningful content, not URL characters that would be truncated away anyway.

### Step 3: Apply `strip_urls` in `create_signal_card`

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/cards.py`
**Line 287**

**Before:**
```python
    preview = text_content[:120] + "..." if len(text_content) > 120 else text_content
```

**After:**
```python
    text_content = strip_urls(text_content)
    preview = text_content[:120] + "..." if len(text_content) > 120 else text_content
```

### Step 4: Apply `strip_urls` in `create_post_card`

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/cards.py`
**Line 449**

**Before:**
```python
    display_text = post_text[:300] + "..." if len(post_text) > 300 else post_text
```

**After:**
```python
    post_text = strip_urls(post_text)
    display_text = post_text[:300] + "..." if len(post_text) > 300 else post_text
```

### Step 5: Apply `strip_urls` in `create_prediction_timeline_card`

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/cards.py`
**Line 701**

**Before:**
```python
    display_text = tweet_text[:200] + "..." if len(tweet_text) > 200 else tweet_text
```

**After:**
```python
    tweet_text = strip_urls(tweet_text)
    display_text = tweet_text[:200] + "..." if len(tweet_text) > 200 else tweet_text
```

### Step 6: Apply `strip_urls` in `create_feed_signal_card`

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/cards.py`
**Lines 1152-1154**

**Before:**
```python
    max_text_len = 250
    display_text = (
        post_text[:max_text_len] + "..." if len(post_text) > max_text_len else post_text
    )
```

**After:**
```python
    post_text = strip_urls(post_text)
    max_text_len = 250
    display_text = (
        post_text[:max_text_len] + "..." if len(post_text) > max_text_len else post_text
    )
```

---

## Test Plan

Create a new test file at `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_cards.py`.

Follow the existing test conventions from `test_charts.py`: add `shitty_ui` to `sys.path` at the top, use plain `pytest` classes, and import directly from the `components.cards` module.

```python
"""Tests for shitty_ui/components/cards.py - Card components and helpers."""

import sys
import os

# Add shitty_ui to path for imports (matches pattern from test_charts.py)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))

import pytest
from datetime import datetime

from components.cards import strip_urls


class TestStripUrls:
    """Tests for the strip_urls helper function."""

    def test_removes_https_url(self):
        """Test that a single https URL is removed."""
        text = "Check this out https://www.wsj.com/article/something great news"
        assert strip_urls(text) == "Check this out great news"

    def test_removes_http_url(self):
        """Test that a single http URL is removed."""
        text = "See http://example.com/path for details"
        assert strip_urls(text) == "See for details"

    def test_removes_url_with_long_path(self):
        """Test removal of URLs with long paths and query params."""
        text = "Breaking https://www.wsj.com/politics/national-security/pentagon-prepares-second-aircraft-carrier-to-deploy-to-the-middle-east-e7140a64 wow"
        assert strip_urls(text) == "Breaking wow"

    def test_removes_url_with_query_params(self):
        """Test removal of URLs with query parameters."""
        text = "Link https://example.com/page?foo=bar&baz=qux#section end"
        assert strip_urls(text) == "Link end"

    def test_removes_multiple_urls(self):
        """Test that multiple URLs in the same text are all removed."""
        text = "See https://a.com and https://b.com/path for info"
        assert strip_urls(text) == "See and for info"

    def test_text_with_no_urls_unchanged(self):
        """Test that text without URLs passes through unchanged."""
        text = "This is a normal post about tariffs"
        assert strip_urls(text) == "This is a normal post about tariffs"

    def test_empty_string(self):
        """Test that an empty string returns the link placeholder."""
        assert strip_urls("") == "[link]"

    def test_url_only_text_returns_placeholder(self):
        """Test that text consisting only of a URL returns '[link]'."""
        assert strip_urls("https://example.com/some/long/path") == "[link]"

    def test_multiple_urls_only_returns_placeholder(self):
        """Test text with only URLs and whitespace returns placeholder."""
        assert strip_urls("https://a.com https://b.com") == "[link]"

    def test_collapses_double_spaces(self):
        """Test that spaces left by URL removal are collapsed."""
        text = "Before https://url.com after"
        result = strip_urls(text)
        assert "  " not in result
        assert result == "Before after"

    def test_strips_leading_trailing_whitespace(self):
        """Test that leading/trailing whitespace is stripped."""
        text = "https://url.com some text"
        assert strip_urls(text) == "some text"

    def test_url_at_end_of_text(self):
        """Test URL at the end of the text."""
        text = "Great article here https://example.com/article"
        assert strip_urls(text) == "Great article here"

    def test_url_at_start_of_text(self):
        """Test URL at the start of the text."""
        text = "https://example.com/article Great article here"
        assert strip_urls(text) == "Great article here"

    def test_preserves_non_url_content(self):
        """Test that dollar amounts, tickers, etc. are preserved."""
        text = "$AAPL is up 5% today https://finance.yahoo.com/quote/AAPL check it"
        assert strip_urls(text) == "$AAPL is up 5% today check it"

    def test_does_not_strip_bare_domains(self):
        """Test that bare domains without protocol are NOT stripped."""
        text = "Visit wsj.com for more info"
        assert strip_urls(text) == "Visit wsj.com for more info"

    def test_url_with_parentheses(self):
        """Test URL containing parentheses (e.g., Wikipedia)."""
        text = "See https://en.wikipedia.org/wiki/Test_(computing) for more"
        result = strip_urls(text)
        # The regex will consume up to the closing paren since it's non-whitespace
        assert "https://" not in result

    def test_preserves_newlines(self):
        """Test that newlines in text are preserved."""
        text = "First line\nhttps://url.com\nThird line"
        assert strip_urls(text) == "First line\n\nThird line"
```

### Running the tests

```bash
source venv/bin/activate && pytest shit_tests/shitty_ui/test_cards.py -v
```

### Integration verification

After implementing, visually verify on the running dashboard:

1. Navigate to the main dashboard page -- hero signal cards and signal sidebar cards should show clean text without URLs
2. Scroll to the Latest Posts section -- post cards should display clean preview text
3. Navigate to `/signals` -- feed signal cards should show clean text
4. Navigate to `/assets/<ticker>` -- prediction timeline cards should show clean text
5. Confirm that no card shows an empty text preview (the `[link]` fallback should appear for URL-only posts)

---

## Documentation Updates

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Fixed
- **Raw URLs cluttering card previews** - Strip http/https URLs from text previews in all card components (hero signal, signal, post, feed signal, prediction timeline). URLs consumed 50-100+ characters of limited preview space, making cards unreadable. Cards now show meaningful post content instead of URL strings.
```

---

## Edge Cases

| Edge Case | Expected Behavior | Handled By |
|-----------|-------------------|------------|
| Post text is entirely a URL | Card displays `[link]` instead of empty text | `if not cleaned: return "[link]"` fallback |
| Post contains multiple URLs | All URLs removed, spaces collapsed | `re.sub` with global replacement + space collapse |
| Post contains no URLs | Text passes through completely unchanged | Regex simply does not match |
| Empty string input | Returns `[link]` | Empty string after strip triggers fallback |
| URL at start of text | URL removed, leading whitespace stripped | `.strip()` call after regex |
| URL at end of text | URL removed, trailing whitespace stripped | `.strip()` call after regex |
| URL with query params, fragments, long paths | Entire URL removed (regex matches all non-whitespace after `https://`) | `\S+` greedily consumes entire URL |
| Bare domain without protocol (e.g., `wsj.com`) | NOT stripped (intentional -- avoids false positives) | Regex requires `https?://` prefix |
| Post with `$AAPL` or other dollar-prefixed text | Preserved (not a URL pattern) | Regex only matches `http://` or `https://` |
| Malformed URL like `https://` with nothing after | Removed (matches `https://` as a 0-length `\S+` would not match, but `https://` alone has no non-whitespace after the `//`, so it stays) | Actually, `https://` alone will NOT be matched since `\S+` requires 1+ chars. This is correct behavior -- `https://` alone is not a real URL. |

**Correction on the last edge case**: `re.sub(r"https?://\S+", "", "https://")` -- the `\S+` requires one or more non-whitespace characters after `://`. The bare `https://` string has nothing after it, so it will NOT be matched and will remain in the text. This is acceptable behavior since bare `https://` is not a real URL. If desired, use `\S*` instead, but `\S+` is safer against false positives.

---

## Verification Checklist

- [ ] `import re` added to the imports section of `cards.py`
- [ ] `strip_urls()` function added between imports and `create_error_card`
- [ ] `strip_urls()` called in `create_hero_signal_card` (before line 78 truncation)
- [ ] `strip_urls()` called in `create_signal_card` (before line 287 truncation)
- [ ] `strip_urls()` called in `create_post_card` (before line 449 truncation)
- [ ] `strip_urls()` called in `create_prediction_timeline_card` (before line 701 truncation)
- [ ] `strip_urls()` called in `create_feed_signal_card` (before line 1153 truncation)
- [ ] All 5 card functions strip URLs BEFORE truncation, not after
- [ ] `strip_urls()` is applied to the text variable, not the truncated preview
- [ ] Test file created at `shit_tests/shitty_ui/test_cards.py`
- [ ] All tests pass: `source venv/bin/activate && pytest shit_tests/shitty_ui/test_cards.py -v`
- [ ] Existing tests still pass: `source venv/bin/activate && pytest shit_tests/shitty_ui/ -v`
- [ ] Full test suite unaffected: `source venv/bin/activate && pytest -x`
- [ ] Linting passes: `source venv/bin/activate && python3 -m ruff check shitty_ui/components/cards.py`
- [ ] CHANGELOG.md updated with entry under `[Unreleased]`

---

## What NOT To Do

1. **Do NOT strip URLs from the full post view or any non-preview context.** The `strip_urls` call goes ONLY on the variable that feeds into the truncation line. The raw `row["text"]` is not mutated -- we reassign the local variable before truncation. If a future full-post detail modal is added, it should display the original text with clickable links.

2. **Do NOT use an overly aggressive regex.** Patterns like `\b\w+\.\w+/\S*` or attempts to match bare domains (`wsj.com`, `google.com`) risk stripping legitimate text content. The regex `https?://\S+` is intentionally conservative: it only matches text that starts with an explicit protocol prefix.

3. **Do NOT add the regex pattern as a module-level compiled constant.** Python internally caches the last few `re.sub` patterns, and this pattern is simple enough that compilation overhead is negligible. A compiled constant would add clutter for no measurable gain.

4. **Do NOT replace URLs with `[link]` inline.** The requirement says "optionally replace with a short indicator or just remove entirely." Inline `[link]` markers (e.g., `"Check this out [link] for details"`) add noise to the preview. Only use `[link]` as a last-resort fallback when the entire post was nothing but URLs.

5. **Do NOT modify the `create_prediction_timeline_card` thesis preview truncation on line 1374.** The thesis is LLM-generated analysis text and will never contain raw URLs. Only the post text (`row["text"]`) previews need URL stripping.

6. **Do NOT modify `create_post_card`'s thesis truncation on line 510.** Same reasoning: the thesis preview (`thesis[:200]`) is LLM output, not raw post text.

7. **Do NOT mutate the original `row` dictionary.** Always reassign the local variable (`text_content = strip_urls(text_content)`) rather than writing back to `row["text"]`. The row may be used elsewhere.

---

### Critical Files for Implementation
- `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/cards.py` - Primary target: add `strip_urls()` helper and apply it in all 5 card preview functions
- `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_cards.py` - New test file to create with comprehensive tests for `strip_urls()`
- `/Users/chris/Projects/shitpost-alpha/CHANGELOG.md` - Add entry under `[Unreleased]` section
- `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_charts.py` - Reference file for test conventions (sys.path setup, import patterns, class structure)
- `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/conftest.py` - Existing conftest providing mock settings for all shitty_ui tests