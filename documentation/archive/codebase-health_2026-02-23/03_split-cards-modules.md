# Phase 03: Split cards.py into Focused Card Modules

| Field            | Value                                                        |
|------------------|--------------------------------------------------------------|
| **PR Title**     | `refactor: split 2041-line cards.py into 8 focused card modules` |
| **Risk**         | Medium                                                       |
| **Effort**       | Medium (~3-4 hours)                                          |
| **Status**       | PENDING                                                      |
| **Dependencies** | Phase 02 (helper extraction must be completed first)         |
| **Unlocks**      | None                                                         |
| **Files Created**| 9 (`components/cards/` package: `__init__.py` + 8 modules)   |
| **Files Modified**| 0 (all consumer imports go through `__init__.py` re-exports) |
| **Files Deleted** | 1 (`shitty_ui/components/cards.py` — replaced by package)   |

---

## Context

`shitty_ui/components/cards.py` is 2,041 lines containing 18 functions that serve 7 completely
different card types. The file has grown through accretion — every new card type was added to the
same flat file. This makes the file difficult to navigate, hard to review in PRs, and creates
merge conflicts when multiple developers touch different card types simultaneously.

Phase 02 extracts the 4 duplicated helper patterns (time-ago formatting, sentiment extraction,
outcome badges, asset display) into shared utilities. After Phase 02, the remaining functions
are clean and self-contained, making this split purely mechanical — no logic changes, just
reorganizing functions into cohesive submodules based on their card type.

The key invariant: **every existing `from components.cards import X` statement must continue to
work unchanged** after the split. Python allows a module to be replaced by a package with the
same name, and the `__init__.py` re-exports ensure import compatibility.

---

## Dependencies

**Requires Phase 02 first.** Phase 02 extracts the 4 duplicated helper patterns out of cards.py.
Without that extraction, the split modules would each need to import those helpers from other
split modules, creating circular dependencies and defeating the purpose of the split.

After Phase 02, the shared helpers live elsewhere (e.g., a `card_helpers.py` or in `constants.py`),
and each card module can independently import them without cross-referencing sibling modules.

**Unlocks: None.** This is a terminal leaf in the dependency graph.

---

## Complete Function Inventory

All 18 functions currently in `cards.py`, mapped to their target module:

| # | Function | Lines | Target Module |
|---|----------|-------|---------------|
| 1 | `strip_urls()` | 16-39 | `cards/__init__.py` (utility, re-exported) |
| 2 | `get_sentiment_style()` | 42-60 | `cards/__init__.py` (utility, re-exported) |
| 3 | `create_error_card()` | 63-104 | `cards/empty_states.py` |
| 4 | `create_empty_chart()` | 107-121 | `cards/empty_states.py` |
| 5 | `create_empty_state_chart()` | 124-181 | `cards/empty_states.py` |
| 6 | `create_empty_state_html()` | 184-241 | `cards/empty_states.py` |
| 7 | `create_hero_signal_card()` | 244-415 | `cards/hero.py` |
| 8 | `create_metric_card()` | 418-524 | `cards/metrics.py` |
| 9 | `create_signal_card()` | 527-670 | `cards/signal.py` |
| 10 | `create_unified_signal_card()` | 673-905 | `cards/signal.py` |
| 11 | `create_post_card()` | 908-1089 | `cards/post.py` |
| 12 | `create_prediction_timeline_card()` | 1092-1301 | `cards/timeline.py` |
| 13 | `create_related_asset_link()` | 1304-1359 | `cards/timeline.py` |
| 14 | `create_performance_summary()` | 1362-1550 | `cards/metrics.py` |
| 15 | `_safe_get()` | 1553-1570 | `cards/feed.py` (private, only used by feed) |
| 16 | `_build_expandable_thesis()` | 1573-1650 | `cards/feed.py` (private, also used by post — see note) |
| 17 | `create_feed_signal_card()` | 1653-1992 | `cards/feed.py` |
| 18 | `create_new_signals_banner()` | 1995-2040 | `cards/feed.py` |

**Note on `_build_expandable_thesis()`:** This private helper is called from both
`create_post_card()` (line 979) and `create_feed_signal_card()` (line 1972). It must live in a
location importable by both `post.py` and `feed.py`. Place it in `feed.py` (its primary home)
and import it from there into `post.py`. Alternatively, if Phase 02 created a shared helpers
module, place it there. The plan below puts it in `feed.py` since that function contains the
more complex usage.

**Note on `strip_urls()` and `get_sentiment_style()`:** These two utilities are used across
multiple card modules AND are imported directly by test files. They stay as top-level exports
from `cards/__init__.py` but are defined inline in `__init__.py` since they are small (24 and
19 lines respectively) and serve as package-level utilities.

---

## Consumer Import Analysis

Every file that imports from `components.cards` and exactly what it imports:

### Production Code

**`shitty_ui/layout.py:31-38`**
```python
from components.cards import (  # noqa: F401
    create_error_card,
    create_empty_chart,
    create_empty_state_chart,
    create_feed_signal_card,
    create_metric_card,
    create_new_signals_banner,
    create_signal_card,
)
```

**`shitty_ui/pages/dashboard.py:22-26`**
```python
from components.cards import (
    create_error_card,
    create_metric_card,
    create_post_card,
)
```

**`shitty_ui/pages/assets.py:10-16`**
```python
from components.cards import (
    create_error_card,
    create_metric_card,
    create_prediction_timeline_card,
    create_related_asset_link,
    create_performance_summary,
)
```

### Test Code

**`shit_tests/shitty_ui/test_cards.py:12-23`**
```python
from components.cards import (
    strip_urls,
    create_hero_signal_card,
    create_signal_card,
    create_post_card,
    create_prediction_timeline_card,
    create_feed_signal_card,
    create_empty_state_html,
    create_unified_signal_card,
    get_sentiment_style,
    _build_expandable_thesis,
)
```

**`shit_tests/shitty_ui/test_layout.py`** (inline imports in test methods):
- `from components.cards import create_metric_card` (10 occurrences, lines 896-984)
- `from components.cards import create_empty_state_chart` (17 occurrences, lines 612-748)
- `from components.cards import _safe_get` (8 occurrences, lines 1167-1210)
- `from components.cards import create_hero_signal_card` (5 occurrences, lines 1300-1373)

### Complete Public API (all symbols that must be re-exported from `__init__.py`)

```
strip_urls
get_sentiment_style
create_error_card
create_empty_chart
create_empty_state_chart
create_empty_state_html
create_hero_signal_card
create_metric_card
create_signal_card
create_unified_signal_card
create_post_card
create_prediction_timeline_card
create_related_asset_link
create_performance_summary
create_feed_signal_card
create_new_signals_banner
_safe_get
_build_expandable_thesis
```

---

## Detailed Implementation Plan

### Step 0: Pre-flight Verification

Before making any changes, verify the test suite passes on the current `main` branch:

```bash
cd /Users/chris/Projects/shitpost-alpha && ./venv/bin/python -m pytest shit_tests/shitty_ui/test_cards.py -v
cd /Users/chris/Projects/shitpost-alpha && ./venv/bin/python -m pytest shit_tests/shitty_ui/test_layout.py -v
```

Record the pass/fail counts. Any pre-existing failures are not introduced by this phase.

### Step 1: Delete `shitty_ui/components/cards.py` and Create Package Directory

Python cannot have both `components/cards.py` (module) and `components/cards/` (package) at the
same path. The file must be removed before the package directory is created.

1. Delete `shitty_ui/components/cards.py`
2. Create `shitty_ui/components/cards/` directory
3. Create all 9 files inside it (Steps 2-9 below)

**Important:** Do all of this in a single commit. Never leave the repo in a state where
`from components.cards import X` fails.

### Step 2: Create `shitty_ui/components/cards/__init__.py`

This file re-exports every public symbol so existing imports work unchanged.

```python
"""Reusable card and chart components for the Shitty UI dashboard.

This package splits card components into focused modules by card type.
All public functions are re-exported here for backward compatibility —
existing ``from components.cards import X`` statements work unchanged.
"""

import re
from datetime import datetime

from dash import html, dcc

from constants import COLORS, SENTIMENT_COLORS, SENTIMENT_BG_COLORS


# ── Package-level utilities ──────────────────────────────────────────

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


# ── Re-exports from submodules ───────────────────────────────────────

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

from components.cards.post import create_post_card  # noqa: E402

from components.cards.timeline import (  # noqa: E402
    create_prediction_timeline_card,
    create_related_asset_link,
)

from components.cards.feed import (  # noqa: E402
    create_feed_signal_card,
    create_new_signals_banner,
    _safe_get,
    _build_expandable_thesis,
)


__all__ = [
    # Utilities
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
    # Post
    "create_post_card",
    # Timeline
    "create_prediction_timeline_card",
    "create_related_asset_link",
    # Feed
    "create_feed_signal_card",
    "create_new_signals_banner",
    # Private (exported for test compatibility)
    "_safe_get",
    "_build_expandable_thesis",
]
```

### Step 3: Create `shitty_ui/components/cards/empty_states.py`

Contains: `create_error_card()`, `create_empty_chart()`, `create_empty_state_chart()`,
`create_empty_state_html()`.

```python
"""Empty state and error card components."""

from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from constants import COLORS
from brand_copy import COPY
```

Copy **exactly** these functions from the current `cards.py` (preserving every line, indent, and comment):

- `create_error_card()` — lines 63-104
- `create_empty_chart()` — lines 107-121
- `create_empty_state_chart()` — lines 124-181
- `create_empty_state_html()` — lines 184-241

No changes to function bodies. The only change is the import block at the top of the file.

**Verification:** These functions do NOT import `strip_urls`, `get_sentiment_style`,
`FONT_SIZES`, `HIERARCHY`, `SENTIMENT_COLORS`, `SENTIMENT_BG_COLORS`, or any sparkline imports.
They only need `COLORS`, `COPY`, and the Dash/Plotly imports listed above.

### Step 4: Create `shitty_ui/components/cards/hero.py`

Contains: `create_hero_signal_card()`.

```python
"""Hero signal card component for high-confidence predictions."""

from datetime import datetime

from dash import html

from constants import COLORS
from components.cards import strip_urls, get_sentiment_style
```

Copy **exactly** `create_hero_signal_card()` from lines 244-415 of the current `cards.py`.

No changes to function body.

**Important:** This function imports `strip_urls` and `get_sentiment_style` from the package's
own `__init__.py`. This works because Python resolves `components.cards` to the package, and
the utilities are defined directly in `__init__.py` (not imported from a submodule), so no
circular import occurs.

### Step 5: Create `shitty_ui/components/cards/signal.py`

Contains: `create_signal_card()`, `create_unified_signal_card()`.

```python
"""Signal card components for prediction feeds."""

from datetime import datetime

from dash import html

from constants import COLORS
from components.cards import strip_urls, get_sentiment_style
from components.sparkline import create_sparkline_component, create_sparkline_placeholder
```

Copy **exactly** these functions from the current `cards.py`:

- `create_signal_card()` — lines 527-670
- `create_unified_signal_card()` — lines 673-905

No changes to function bodies.

### Step 6: Create `shitty_ui/components/cards/feed.py`

Contains: `_safe_get()`, `_build_expandable_thesis()`, `create_feed_signal_card()`,
`create_new_signals_banner()`.

```python
"""Feed signal card components for the /signals page."""

import math
from datetime import datetime, timedelta, timezone

from dash import html
import dash_bootstrap_components as dbc

from constants import COLORS
from components.cards import strip_urls, get_sentiment_style
from components.sparkline import create_sparkline_component, create_sparkline_placeholder
```

Copy **exactly** these functions from the current `cards.py`:

- `_safe_get()` — lines 1553-1570
- `_build_expandable_thesis()` — lines 1573-1650
- `create_feed_signal_card()` — lines 1653-1992
- `create_new_signals_banner()` — lines 1995-2040

No changes to function bodies.

**Note on `_safe_get`:** The original has `import math` inside the function body (line 1564).
Move the `import math` to the module-level imports in `feed.py` as shown above, and remove the
in-function import. This is a minor cleanup but the function body logic stays identical:

In `_safe_get()`, change lines 1564-1565 from:

```python
    try:
        import math

        if isinstance(value, float) and math.isnan(value):
```

To:

```python
    try:
        if isinstance(value, float) and math.isnan(value):
```

This is the **only** logic change in the entire phase. The `import math` is now at module level.

### Step 7: Create `shitty_ui/components/cards/post.py`

Contains: `create_post_card()`.

```python
"""Post card component for the Latest Posts feed."""

from datetime import datetime

from dash import html

from constants import COLORS, SENTIMENT_COLORS
from brand_copy import COPY
from components.cards import strip_urls, get_sentiment_style
from components.cards.feed import _build_expandable_thesis
```

Copy **exactly** `create_post_card()` from lines 908-1089 of the current `cards.py`.

No changes to function body.

**Critical:** `create_post_card()` calls `_build_expandable_thesis()` at line 979. Since
`_build_expandable_thesis` lives in `feed.py`, this module imports it from there. This is a
one-way dependency (`post.py` depends on `feed.py`), not circular.

### Step 8: Create `shitty_ui/components/cards/timeline.py`

Contains: `create_prediction_timeline_card()`, `create_related_asset_link()`.

```python
"""Timeline and related asset card components for the asset detail page."""

from datetime import datetime

from dash import html, dcc

from constants import COLORS
from components.cards import strip_urls, get_sentiment_style
```

Copy **exactly** these functions from the current `cards.py`:

- `create_prediction_timeline_card()` — lines 1092-1301
- `create_related_asset_link()` — lines 1304-1359

No changes to function bodies.

### Step 9: Create `shitty_ui/components/cards/metrics.py`

Contains: `create_metric_card()`, `create_performance_summary()`.

```python
"""Metric and performance summary card components."""

from typing import Dict, Any

from dash import html
import dash_bootstrap_components as dbc

from constants import COLORS, FONT_SIZES, HIERARCHY
```

Copy **exactly** these functions from the current `cards.py`:

- `create_metric_card()` — lines 418-524
- `create_performance_summary()` — lines 1362-1550

No changes to function bodies.

**Note:** These functions do NOT use `strip_urls`, `get_sentiment_style`, or any sparkline
imports. They only use `COLORS`, `FONT_SIZES`, `HIERARCHY`, and Dash/DBC components.

### Step 10: Verify — No Consumer Files Need Changes

Because all public symbols are re-exported from `components/cards/__init__.py`, the following
import statements continue to work **exactly as-is** with zero modifications:

| File | Import Statement | Status |
|------|-----------------|--------|
| `shitty_ui/layout.py:31` | `from components.cards import create_error_card, ...` | Works unchanged |
| `shitty_ui/pages/dashboard.py:22` | `from components.cards import create_error_card, ...` | Works unchanged |
| `shitty_ui/pages/assets.py:10` | `from components.cards import create_error_card, ...` | Works unchanged |
| `shit_tests/shitty_ui/test_cards.py:12` | `from components.cards import strip_urls, ...` | Works unchanged |
| `shit_tests/shitty_ui/test_layout.py` (inline) | `from components.cards import create_metric_card` | Works unchanged |
| `shit_tests/shitty_ui/test_layout.py` (inline) | `from components.cards import create_empty_state_chart` | Works unchanged |
| `shit_tests/shitty_ui/test_layout.py` (inline) | `from components.cards import _safe_get` | Works unchanged |
| `shit_tests/shitty_ui/test_layout.py` (inline) | `from components.cards import create_hero_signal_card` | Works unchanged |

**No consumer file requires any modifications.** This is the core design goal.

---

## Final File Tree

After this phase, the `components/cards/` directory looks like this:

```
shitty_ui/components/cards/
├── __init__.py          # ~115 lines — strip_urls, get_sentiment_style, re-exports
├── empty_states.py      # ~180 lines — 4 empty/error state components
├── hero.py              # ~175 lines — create_hero_signal_card()
├── signal.py            # ~385 lines — create_signal_card(), create_unified_signal_card()
├── feed.py              # ~400 lines — _safe_get, _build_expandable_thesis, feed cards
├── post.py              # ~190 lines — create_post_card()
├── timeline.py          # ~275 lines — timeline card + related asset link
└── metrics.py           # ~300 lines — create_metric_card(), create_performance_summary()
```

Total: ~2,020 lines across 8 files (vs 2,041 in one file). The slight reduction comes from
removing the duplicated `import math` inside `_safe_get`.

---

## Test Plan

### No New Tests Required

This is a pure structural refactoring with no logic changes. Every existing test exercises the
exact same code paths through the exact same import paths.

### Existing Tests to Verify (Must All Pass)

1. **`shit_tests/shitty_ui/test_cards.py`** — The primary card test file. Tests `strip_urls`,
   `create_hero_signal_card`, `create_signal_card`, `create_post_card`,
   `create_prediction_timeline_card`, `create_feed_signal_card`, `create_empty_state_html`,
   `create_unified_signal_card`, `get_sentiment_style`, `_build_expandable_thesis`, and
   `create_metric_card`.

2. **`shit_tests/shitty_ui/test_layout.py`** — Contains inline imports for `create_metric_card`
   (10 test methods), `create_empty_state_chart` (17 test methods), `_safe_get` (8 test methods),
   and `create_hero_signal_card` (5 test methods).

### Verification Commands

```bash
# Run card tests
cd /Users/chris/Projects/shitpost-alpha && ./venv/bin/python -m pytest shit_tests/shitty_ui/test_cards.py -v

# Run layout tests (includes inline card imports)
cd /Users/chris/Projects/shitpost-alpha && ./venv/bin/python -m pytest shit_tests/shitty_ui/test_layout.py -v

# Run ALL shitty_ui tests
cd /Users/chris/Projects/shitpost-alpha && ./venv/bin/python -m pytest shit_tests/shitty_ui/ -v

# Quick smoke test: verify package imports work
cd /Users/chris/Projects/shitpost-alpha && ./venv/bin/python -c "
import sys; sys.path.insert(0, 'shitty_ui')
from components.cards import (
    strip_urls, get_sentiment_style,
    create_error_card, create_empty_chart, create_empty_state_chart, create_empty_state_html,
    create_hero_signal_card,
    create_metric_card, create_performance_summary,
    create_signal_card, create_unified_signal_card,
    create_post_card,
    create_prediction_timeline_card, create_related_asset_link,
    create_feed_signal_card, create_new_signals_banner,
    _safe_get, _build_expandable_thesis,
)
print('All 18 symbols imported successfully')
"
```

---

## Documentation Updates

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Changed
- **cards.py split** — Reorganized 2,041-line `shitty_ui/components/cards.py` into 8 focused
  modules under `shitty_ui/components/cards/` package. All existing imports work unchanged via
  `__init__.py` re-exports.
```

### No Other Documentation Changes

- No README changes needed (the package is an internal implementation detail)
- No API documentation changes (public API is identical)
- The `CLAUDE.md` directory tree shows `components/` generically; no update needed

---

## Stress Testing & Edge Cases

### Circular Import Prevention

The dependency graph between submodules is strictly one-directional:

```
__init__.py  (defines strip_urls, get_sentiment_style)
    ↓ imports from
hero.py, signal.py, feed.py, post.py, timeline.py  (import from __init__)
    ↓
post.py  (also imports _build_expandable_thesis from feed.py)
```

There are no cycles. Verify by importing from each module individually:

```python
import sys; sys.path.insert(0, 'shitty_ui')
from components.cards.empty_states import create_error_card
from components.cards.hero import create_hero_signal_card
from components.cards.signal import create_signal_card
from components.cards.feed import create_feed_signal_card
from components.cards.post import create_post_card
from components.cards.timeline import create_prediction_timeline_card
from components.cards.metrics import create_metric_card
```

### Python Module vs Package Replacement

When Python sees `from components.cards import X`, it resolves `components.cards` to:
- `components/cards.py` (module) — **before** this phase
- `components/cards/__init__.py` (package) — **after** this phase

Both work identically for the importer. The key requirement is that `cards.py` (the file) must
not exist alongside `cards/` (the directory). Step 1 handles this by deleting the file first.

### Git Rename Detection

Git will not automatically detect the file-to-package transformation. The diff will show
`cards.py` as deleted and 9 new files as added. This is expected and correct. The PR description
should note this is a structural split, not a rewrite.

### Import Ordering in `__init__.py`

The `__init__.py` defines `strip_urls` and `get_sentiment_style` BEFORE the submodule imports.
This is required because `hero.py`, `signal.py`, etc. import these symbols from `components.cards`
(which resolves to `__init__.py`). If the submodule imports came first, Python would try to
execute (e.g.) `hero.py` before `strip_urls` was defined in `__init__.py`, causing an
`ImportError`.

The ordering in `__init__.py` MUST be:
1. Define `strip_urls()` and `get_sentiment_style()` as top-level functions
2. Then import from submodules

### `metrics.py` Does Not Import From `__init__`

`create_metric_card()` and `create_performance_summary()` do not use `strip_urls` or
`get_sentiment_style`. Their import block only references `constants` and Dash libraries.
This means `metrics.py` has zero dependency on the parent `__init__.py`, avoiding any
potential circular import issues.

### `empty_states.py` Does Not Import From `__init__`

Similarly, the empty state functions do not use `strip_urls` or `get_sentiment_style`.
They only import from `constants`, `brand_copy`, and Dash/Plotly.

---

## Verification Checklist

- [ ] `shitty_ui/components/cards.py` file is deleted (not just renamed)
- [ ] `shitty_ui/components/cards/` directory exists with 9 files
- [ ] `__init__.py` defines `strip_urls()` and `get_sentiment_style()` BEFORE submodule imports
- [ ] `__init__.py` has `__all__` listing all 18 exported symbols
- [ ] Every function body is byte-for-byte identical to the original (except `_safe_get` `import math` move)
- [ ] `_build_expandable_thesis` is in `feed.py` and imported by `post.py`
- [ ] No consumer files (`layout.py`, `dashboard.py`, `assets.py`) were modified
- [ ] No test files (`test_cards.py`, `test_layout.py`) were modified
- [ ] `./venv/bin/python -m pytest shit_tests/shitty_ui/test_cards.py -v` passes
- [ ] `./venv/bin/python -m pytest shit_tests/shitty_ui/test_layout.py -v` passes
- [ ] `./venv/bin/python -m pytest shit_tests/shitty_ui/ -v` passes
- [ ] Smoke test: all 18 symbols importable via `from components.cards import X`
- [ ] `./venv/bin/python -m ruff check shitty_ui/components/cards/` passes
- [ ] `./venv/bin/python -m ruff format --check shitty_ui/components/cards/` passes
- [ ] CHANGELOG.md updated

---

## What NOT To Do

1. **Do NOT modify any consumer import statements.** The entire point of the `__init__.py`
   re-exports is that existing imports work unchanged. If you find yourself editing `layout.py`,
   `dashboard.py`, `assets.py`, `test_cards.py`, or `test_layout.py`, you have made a mistake
   in the `__init__.py` exports.

2. **Do NOT leave `cards.py` alongside the `cards/` directory.** Python will be confused about
   whether `components.cards` refers to the file or the package. The old file must be deleted
   before the package is created.

3. **Do NOT change any function signatures or return types.** This is a structural move, not a
   refactoring of logic. Every function must have the identical signature and body.

4. **Do NOT reorder the `__init__.py` to put submodule imports before the utility function
   definitions.** Submodules import `strip_urls` and `get_sentiment_style` from `components.cards`
   (i.e., from `__init__.py`). Those functions must be defined before the submodule import
   statements execute.

5. **Do NOT create a separate `utils.py` submodule for `strip_urls` and `get_sentiment_style`.**
   This would add unnecessary indirection. They are small utility functions that belong in
   `__init__.py` as package-level definitions.

6. **Do NOT move `_build_expandable_thesis` into a shared utils submodule.** Keep it in `feed.py`
   where its primary (and more complex) caller lives. `post.py` can import it from `feed.py`
   directly.

7. **Do NOT forget the `import math` at module level in `feed.py`.** If you copy `_safe_get`
   verbatim from the original, it will have `import math` inside the function body. This works
   but is not idiomatic. Move the import to module level and remove the in-function import.

8. **Do NOT add type: ignore comments or suppress import warnings.** The `# noqa: E402` comments
   on the submodule imports in `__init__.py` are correct (they come after top-level function
   definitions). No other suppressions should be needed.

9. **Do NOT attempt this phase before Phase 02 is complete.** Phase 02 extracts the 4 duplicated
   helper patterns (time-ago formatting, sentiment extraction, outcome badges, asset display).
   If those helpers are still duplicated inline in the card functions, splitting the file will
   scatter the duplication across 5+ modules, making Phase 02 harder to implement later.
