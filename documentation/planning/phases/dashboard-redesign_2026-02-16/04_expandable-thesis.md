# Phase 04: Expandable Thesis Cards

**Status**: 🔧 IN PROGRESS
**Started**: 2026-02-16
**PR Title**: feat: click-to-expand prediction detail cards
**Risk Level**: Low
**Estimated Effort**: Medium (2-3 hours)
**Dependencies**: None
**Unlocks**: Phase 05 (Merge Sections)

## Files Modified

| File | Action |
|------|--------|
| `shitty_ui/components/cards.py` | Modify `create_feed_signal_card()` and `create_post_card()` to render thesis in a collapsible container with expand/collapse toggle |
| `shitty_ui/pages/signals.py` | Add `dcc.Store` for expanded-card tracking; register clientside expand/collapse callback |
| `shitty_ui/layout.py` | Add CSS classes for thesis expand/collapse animation and chevron rotation |
| `shit_tests/shitty_ui/test_cards.py` | Add tests for expandable thesis rendering, short-thesis auto-expand, truncation boundary |
| `shit_tests/shitty_ui/test_layout.py` | Add tests for new CSS classes in index_string |
| `CHANGELOG.md` | Add entry |

## Context

The thesis text -- the LLM's investment reasoning -- is the most valuable content in every prediction card, yet it is aggressively truncated:

- **`create_feed_signal_card()`** (line 1487 in `cards.py`): Truncates thesis to **120 characters** with `thesis[:120] + "..."`. A typical thesis is 300-600 characters, meaning users see only the first sentence.
- **`create_post_card()`** (line 610 in `cards.py`): Truncates thesis to **200 characters** with `thesis[:200] + "..."`.
- **`create_hero_signal_card()`** (line 175 in `cards.py`): Truncates post text to 200 characters but does not display thesis at all.
- **Chart hover** (`charts.py` line 91): Shows 100-character thesis preview in hover tooltip -- acceptable for tooltips but not for reading.

The `/signals` feed page is where users go to read predictions in detail, and `create_feed_signal_card()` is the primary card component there. Users report that they want to click a card and see the full thesis without navigating to another page. The truncation at 120 characters often cuts off mid-sentence, making the analysis useless.

**Screenshots**: See `/tmp/design-review/signals-desktop.png` -- thesis previews are truncated with "..." and there is no way to expand them.

## Design Decisions

### Why clientside callback (not server-side callback)?

Expanding/collapsing a card is a **pure UI state toggle** with no data fetching. A server round-trip would add latency and consume server resources for zero benefit. Dash's `clientside_callback` is the correct pattern -- the same pattern already used for:
- Chevron rotation on the data table collapse (dashboard.py line 945)
- Refresh countdown timer (dashboard.py line 500)
- Nav link active state (layout.py line 445)

### Why not CSS-only (:target or :checked)?

CSS-only approaches (e.g., hidden checkbox + label + `:checked ~ .content`) are fragile in Dash because Dash manages the DOM. Components can be re-rendered by callbacks, which would reset CSS-only toggle state. Using Dash's component model (`n_clicks` triggering a clientside callback that toggles a style) is the idiomatic approach and survives re-renders when the card list is rebuilt by `update_signal_feed()`.

### Approach: per-card expand via unique IDs + pattern-matching callbacks

Each card gets a unique ID based on its index in the feed. The thesis container and toggle button share a pattern-matched ID so a single clientside callback handles all cards. This avoids registering N separate callbacks.

Dash supports pattern-matching callbacks via `MATCH`, `ALL`, and `ALLSMALLER` wildcards. We will use `{"type": "thesis-toggle", "index": N}` for the toggle button and `{"type": "thesis-container", "index": N}` for the collapsible container.

---

## Detailed Implementation

### Change A: Add Expandable Thesis to `create_feed_signal_card()`

#### Step A1: Add card_index parameter and thesis expansion logic

**File**: `shitty_ui/components/cards.py`
**Location**: Line 1206 -- `create_feed_signal_card()` function signature

Change the function signature from:

```python
def create_feed_signal_card(row) -> html.Div:
```

To:

```python
def create_feed_signal_card(row, card_index: int = 0) -> html.Div:
```

The `card_index` parameter defaults to 0 for backward compatibility with any callers that pass a single row without an index.

#### Step A2: Define thesis truncation threshold constant

**File**: `shitty_ui/components/cards.py`
**Location**: Line 1206, inside `create_feed_signal_card()`, after extracting `thesis` (currently line 1229)

Add a constant for the truncation threshold and compute whether the thesis needs expansion:

```python
    thesis = _safe_get(row, "thesis", "")

    # Thesis expansion logic
    THESIS_TRUNCATE_LEN = 120
    thesis_is_long = isinstance(thesis, str) and len(thesis) > THESIS_TRUNCATE_LEN
    thesis_preview = (thesis[:THESIS_TRUNCATE_LEN] + "...") if thesis_is_long else thesis
```

#### Step A3: Replace the static thesis preview (Row 5) with expandable container

**File**: `shitty_ui/components/cards.py`
**Location**: Lines 1483-1496 (the current "Row 5: Thesis preview" block)

Replace:

```python
    # Row 5: Thesis preview
    if thesis:
        children.append(
            html.P(
                thesis[:120] + "..." if len(thesis) > 120 else thesis,
                style={
                    "fontSize": "0.8rem",
                    "color": COLORS["text_muted"],
                    "margin": "8px 0 0 0",
                    "fontStyle": "italic",
                    "lineHeight": "1.4",
                },
            )
        )
```

With:

```python
    # Row 5: Thesis — expandable if long, static if short
    if thesis:
        thesis_style_base = {
            "fontSize": "0.8rem",
            "color": COLORS["text_muted"],
            "margin": "0",
            "fontStyle": "italic",
            "lineHeight": "1.4",
        }

        if thesis_is_long:
            # Collapsed preview (visible by default)
            thesis_preview_el = html.P(
                thesis_preview,
                id={"type": "thesis-preview", "index": card_index},
                style={**thesis_style_base, "display": "block"},
            )
            # Full thesis (hidden by default)
            thesis_full_el = html.P(
                thesis,
                id={"type": "thesis-full", "index": card_index},
                style={**thesis_style_base, "display": "none"},
            )
            # Toggle button
            thesis_toggle = html.Div(
                [
                    html.Span(
                        [
                            html.I(
                                className="fas fa-chevron-down me-1",
                                id={"type": "thesis-chevron", "index": card_index},
                                style={
                                    "fontSize": "0.65rem",
                                    "transition": "transform 0.2s ease",
                                },
                            ),
                            "Show full thesis",
                        ],
                        id={"type": "thesis-toggle-text", "index": card_index},
                    ),
                ],
                id={"type": "thesis-toggle", "index": card_index},
                n_clicks=0,
                style={
                    "color": COLORS["accent"],
                    "fontSize": "0.75rem",
                    "cursor": "pointer",
                    "marginTop": "4px",
                    "userSelect": "none",
                },
            )
            children.append(
                html.Div(
                    [thesis_preview_el, thesis_full_el, thesis_toggle],
                    style={"marginTop": "8px"},
                )
            )
        else:
            # Short thesis — show in full, no toggle needed
            children.append(
                html.P(
                    thesis,
                    style={**thesis_style_base, "marginTop": "8px"},
                )
            )
```

**Key design points**:
1. Short theses (<=120 chars) render as a plain `<p>` with no toggle -- identical to the current behavior.
2. Long theses render a collapsed preview + hidden full text + clickable toggle.
3. Pattern-matching IDs (`{"type": ..., "index": card_index}`) let a single callback control all cards.
4. The `n_clicks=0` on the toggle div is required for Dash to register click events.

#### Step A4: Pass card_index from the signal feed callback

**File**: `shitty_ui/pages/signals.py`
**Location**: Line 372 (in `update_signal_feed()`) and line 492 (in `load_more_signals()`)

Change the card creation in `update_signal_feed()` from:

```python
            cards = [create_feed_signal_card(row) for _, row in df.iterrows()]
```

To:

```python
            cards = [
                create_feed_signal_card(row, card_index=idx)
                for idx, (_, row) in enumerate(df.iterrows())
            ]
```

Change the card creation in `load_more_signals()` from:

```python
            new_cards = [create_feed_signal_card(row) for _, row in df.iterrows()]
```

To:

```python
            new_cards = [
                create_feed_signal_card(row, card_index=current_offset + idx)
                for idx, (_, row) in enumerate(df.iterrows())
            ]
```

The offset-based indexing ensures that "Load More" cards get unique indices that don't collide with existing cards. When the page loads cards 0-19, the next batch starts at index 20.

---

### Change B: Register Clientside Callback for Thesis Toggle

#### Step B1: Add pattern-matching imports to signals.py

**File**: `shitty_ui/pages/signals.py`
**Location**: Line 5 (import section)

Change:

```python
from dash import Dash, html, dcc, Input, Output, State
```

To:

```python
from dash import Dash, html, dcc, Input, Output, State, MATCH
```

#### Step B2: Register the clientside callback in `register_signal_callbacks()`

**File**: `shitty_ui/pages/signals.py`
**Location**: At the end of `register_signal_callbacks()` (after the existing callback 3.6, around line 624)

Add:

```python
    # 3.7 Thesis Expand/Collapse — clientside callback for zero-latency toggling
    app.clientside_callback(
        """
        function(n_clicks) {
            if (!n_clicks || n_clicks === 0) {
                return [
                    {"display": "block"},
                    {"display": "none"},
                    "Show full thesis",
                    {"fontSize": "0.65rem", "transition": "transform 0.2s ease", "transform": "rotate(0deg)"}
                ];
            }
            var isExpanded = (n_clicks % 2) === 1;
            if (isExpanded) {
                return [
                    {"display": "none"},
                    {"display": "block"},
                    "Hide thesis",
                    {"fontSize": "0.65rem", "transition": "transform 0.2s ease", "transform": "rotate(180deg)"}
                ];
            } else {
                return [
                    {"display": "block"},
                    {"display": "none"},
                    "Show full thesis",
                    {"fontSize": "0.65rem", "transition": "transform 0.2s ease", "transform": "rotate(0deg)"}
                ];
            }
        }
        """,
        [
            Output({"type": "thesis-preview", "index": MATCH}, "style"),
            Output({"type": "thesis-full", "index": MATCH}, "style"),
            Output({"type": "thesis-toggle-text", "index": MATCH}, "children"),
            Output({"type": "thesis-chevron", "index": MATCH}, "style"),
        ],
        [Input({"type": "thesis-toggle", "index": MATCH}, "n_clicks")],
    )
```

**How it works**:
- `MATCH` ensures each toggle only affects its own card's thesis elements (same `index`).
- `n_clicks % 2` acts as a toggle: odd = expanded, even = collapsed.
- The chevron rotates 180 degrees when expanded (down -> up), matching the existing collapse-chevron pattern in the app.
- Returns are `[preview_style, full_style, toggle_text, chevron_style]`.
- The `if (!n_clicks || n_clicks === 0)` guard handles the initial state (no clicks yet).

---

### Change C: Add CSS for Thesis Toggle Interaction

#### Step C1: Add thesis-toggle CSS class to the app stylesheet

**File**: `shitty_ui/layout.py`
**Location**: Inside `app.index_string`, after the `.collapse-chevron.rotated` block (around line 337, before the closing `</style>` tag)

Add:

```css
            /* ======================================
               Thesis expand/collapse
               ====================================== */
            .thesis-toggle-area {
                cursor: pointer;
                user-select: none;
            }
            .thesis-toggle-area:hover {
                text-decoration: underline;
            }
```

**Note**: This CSS is supplementary. The actual show/hide logic is controlled by the clientside callback setting `display: block/none` on the preview and full text elements. The CSS only provides the hover interaction hint.

---

### Change D: Apply Expandable Thesis to `create_post_card()` (Dashboard Post Feed)

The dashboard post feed uses `create_post_card()` which also truncates thesis at 200 characters (line 610). For consistency, we apply the same pattern here.

#### Step D1: Add card_index parameter to `create_post_card()`

**File**: `shitty_ui/components/cards.py`
**Location**: Line 538 -- `create_post_card()` function signature

Change:

```python
def create_post_card(row):
```

To:

```python
def create_post_card(row, card_index: int = 0):
```

#### Step D2: Replace thesis truncation in `create_post_card()` analysis section

**File**: `shitty_ui/components/cards.py`
**Location**: Lines 609-619 (thesis display inside the `analysis_status == "completed"` branch)

Replace:

```python
                html.P(
                    thesis[:200] + "..." if thesis and len(thesis) > 200 else thesis,
                    style={
                        "fontSize": "0.8rem",
                        "color": COLORS["text_muted"],
                        "fontStyle": "italic",
                        "margin": 0,
                    },
                )
                if thesis
                else None,
```

With:

```python
                _build_expandable_thesis(
                    thesis,
                    card_index=card_index,
                    truncate_len=200,
                    id_prefix="post-thesis",
                )
                if thesis
                else None,
```

This uses a shared helper function (defined in Step D3) to avoid code duplication.

#### Step D3: Extract a shared `_build_expandable_thesis()` helper

**File**: `shitty_ui/components/cards.py`
**Location**: After the `_safe_get()` helper function (after line 1203), add:

```python
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
```

#### Step D4: Refactor `create_feed_signal_card()` to use the shared helper

Now that we have `_build_expandable_thesis()`, refactor the thesis section in `create_feed_signal_card()` from the code in Step A3 to use the helper instead of inlining the logic.

**File**: `shitty_ui/components/cards.py`
**Location**: Replace the entire "Row 5" thesis block in `create_feed_signal_card()` with:

```python
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
```

Remove the `THESIS_TRUNCATE_LEN`, `thesis_is_long`, and `thesis_preview` variables added in Step A2 (they are now inside the helper). Only `thesis = _safe_get(row, "thesis", "")` remains at the original location.

#### Step D5: Register a second clientside callback for post-thesis cards

**File**: `shitty_ui/pages/signals.py`
**Location**: After the thesis clientside callback (3.7), add:

**IMPORTANT**: This is NOT needed if `create_post_card()` is only used on the dashboard page. However, if `create_post_card()` is used on the signals page OR if we want to keep the patterns consistent, we need to register the callback globally.

Since `create_post_card()` is used in the dashboard page's post feed (rendered by `update_dashboard()` in `dashboard.py`), we should register this callback in `dashboard.py` instead.

**File**: `shitty_ui/pages/dashboard.py`
**Location**: At the end of `register_dashboard_callbacks()`, after the chevron rotation clientside callback (around line 956)

Add:

```python
    # Post-card thesis expand/collapse — clientside callback
    app.clientside_callback(
        """
        function(n_clicks) {
            if (!n_clicks || n_clicks === 0) {
                return [
                    {"display": "block"},
                    {"display": "none"},
                    "Show full thesis",
                    {"fontSize": "0.65rem", "transition": "transform 0.2s ease", "transform": "rotate(0deg)"}
                ];
            }
            var isExpanded = (n_clicks % 2) === 1;
            if (isExpanded) {
                return [
                    {"display": "none"},
                    {"display": "block"},
                    "Hide thesis",
                    {"fontSize": "0.65rem", "transition": "transform 0.2s ease", "transform": "rotate(180deg)"}
                ];
            } else {
                return [
                    {"display": "block"},
                    {"display": "none"},
                    "Show full thesis",
                    {"fontSize": "0.65rem", "transition": "transform 0.2s ease", "transform": "rotate(0deg)"}
                ];
            }
        }
        """,
        [
            Output({"type": "post-thesis-preview", "index": MATCH}, "style"),
            Output({"type": "post-thesis-full", "index": MATCH}, "style"),
            Output({"type": "post-thesis-toggle-text", "index": MATCH}, "children"),
            Output({"type": "post-thesis-chevron", "index": MATCH}, "style"),
        ],
        [Input({"type": "post-thesis-toggle", "index": MATCH}, "n_clicks")],
    )
```

Also add `MATCH` to the dashboard.py imports:

```python
from dash import Dash, html, dcc, Input, Output, State, no_update, MATCH
```

And pass `card_index` when creating post cards. Find the line in `update_dashboard()` where `create_post_card()` is called (in the post feed section) and add indexing:

```python
post_cards = [
    create_post_card(row, card_index=idx)
    for idx, (_, row) in enumerate(df.iterrows())
]
```

---

## Summary of All Code Changes

### `shitty_ui/components/cards.py`

1. **Add `_build_expandable_thesis()` helper** after `_safe_get()` (after line 1203)
2. **Add `card_index: int = 0` parameter** to `create_feed_signal_card()` (line 1206)
3. **Replace Row 5 thesis block** in `create_feed_signal_card()` (lines 1483-1496) with call to `_build_expandable_thesis()`
4. **Add `card_index: int = 0` parameter** to `create_post_card()` (line 538)
5. **Replace thesis truncation** in `create_post_card()` (lines 609-619) with call to `_build_expandable_thesis()`

### `shitty_ui/pages/signals.py`

1. **Add `MATCH` to imports** (line 5)
2. **Pass `card_index`** in `update_signal_feed()` card creation (line 372)
3. **Pass `card_index`** in `load_more_signals()` card creation (line 492)
4. **Add clientside callback 3.7** for thesis expand/collapse (after line 624)

### `shitty_ui/pages/dashboard.py`

1. **Add `MATCH` to imports**
2. **Pass `card_index`** in post card creation inside `update_dashboard()`
3. **Add clientside callback** for post-thesis expand/collapse (after line 956)

### `shitty_ui/layout.py`

1. **Add `.thesis-toggle-area` CSS classes** to `app.index_string` (before `</style>`)

---

## Test Plan

### New Tests in `shit_tests/shitty_ui/test_cards.py`

```python
class TestExpandableThesis:
    """Tests for expandable thesis rendering in signal and post cards."""

    def test_short_thesis_no_toggle(self):
        """Short thesis (<= 120 chars) should render as plain text, no toggle."""
        short_thesis = "Tariffs will boost domestic steel production."
        card = create_feed_signal_card(
            _make_row(thesis=short_thesis), card_index=0
        )
        text = _extract_text(card)
        # Full text should be visible
        assert short_thesis in text
        # No toggle text
        assert "Show full thesis" not in text

    def test_long_thesis_shows_truncated_preview(self):
        """Long thesis (> 120 chars) should show truncated preview by default."""
        long_thesis = "A" * 200
        card = create_feed_signal_card(
            _make_row(thesis=long_thesis), card_index=1
        )
        text = _extract_text(card)
        # Should show the truncated preview (120 chars + "...")
        assert "A" * 120 + "..." in text
        # Should also include toggle
        assert "Show full thesis" in text

    def test_long_thesis_contains_full_text_hidden(self):
        """Long thesis should have the full text in a hidden element."""
        long_thesis = "B" * 300
        card = create_feed_signal_card(
            _make_row(thesis=long_thesis), card_index=2
        )
        # The full text element exists but is display:none
        # We can find it by searching the component tree
        full_el = _find_component_by_pattern_id(card, "thesis-full", 2)
        assert full_el is not None
        assert full_el.style.get("display") == "none"
        assert full_el.children == long_thesis

    def test_toggle_has_pattern_matching_id(self):
        """Toggle div should have pattern-matching ID with correct index."""
        card = create_feed_signal_card(
            _make_row(thesis="X" * 200), card_index=42
        )
        toggle = _find_component_by_pattern_id(card, "thesis-toggle", 42)
        assert toggle is not None
        assert toggle.id == {"type": "thesis-toggle", "index": 42}
        assert toggle.n_clicks == 0

    def test_empty_thesis_no_expand_section(self):
        """Empty thesis should not render any thesis section."""
        card = create_feed_signal_card(
            _make_row(thesis=""), card_index=0
        )
        text = _extract_text(card)
        assert "Show full thesis" not in text

    def test_none_thesis_no_expand_section(self):
        """None thesis should not render any thesis section."""
        card = create_feed_signal_card(
            _make_row(thesis=None), card_index=0
        )
        text = _extract_text(card)
        assert "Show full thesis" not in text

    def test_thesis_exactly_at_boundary_no_toggle(self):
        """Thesis exactly 120 chars should NOT show toggle."""
        thesis_120 = "C" * 120
        card = create_feed_signal_card(
            _make_row(thesis=thesis_120), card_index=0
        )
        text = _extract_text(card)
        assert "Show full thesis" not in text
        assert thesis_120 in text

    def test_thesis_one_over_boundary_shows_toggle(self):
        """Thesis at 121 chars should show toggle."""
        thesis_121 = "D" * 121
        card = create_feed_signal_card(
            _make_row(thesis=thesis_121), card_index=0
        )
        text = _extract_text(card)
        assert "Show full thesis" in text

    def test_card_index_default_zero(self):
        """Card should render without explicit card_index (defaults to 0)."""
        card = create_feed_signal_card(
            _make_row(thesis="E" * 200)
        )
        # Should not crash and should have index 0
        toggle = _find_component_by_pattern_id(card, "thesis-toggle", 0)
        assert toggle is not None

    def test_backward_compatible_without_card_index(self):
        """Existing callers that don't pass card_index should still work."""
        # This simulates existing code that calls create_feed_signal_card(row)
        card = create_feed_signal_card(_make_row(thesis="Short"))
        assert card is not None


class TestExpandableThesisPostCard:
    """Tests for expandable thesis in create_post_card()."""

    def test_post_card_short_thesis_no_toggle(self):
        """Post card with short thesis (<=200 chars) shows full text, no toggle."""
        card = create_post_card(
            _make_row(thesis="Short thesis text"), card_index=0
        )
        text = _extract_text(card)
        assert "Short thesis text" in text
        assert "Show full thesis" not in text

    def test_post_card_long_thesis_shows_toggle(self):
        """Post card with long thesis (>200 chars) shows truncated preview + toggle."""
        long_thesis = "F" * 300
        card = create_post_card(
            _make_row(thesis=long_thesis), card_index=0
        )
        text = _extract_text(card)
        assert "F" * 200 + "..." in text
        assert "Show full thesis" in text

    def test_post_card_backward_compatible(self):
        """create_post_card() without card_index should still work."""
        card = create_post_card(_make_row(thesis="G" * 250))
        assert card is not None


class TestBuildExpandableThesisHelper:
    """Tests for the _build_expandable_thesis() helper function."""

    def test_short_text_returns_plain_p(self):
        """Text under threshold returns a plain html.P."""
        from components.cards import _build_expandable_thesis

        result = _build_expandable_thesis("Short", card_index=0, truncate_len=120)
        assert isinstance(result, html.P)
        assert result.children == "Short"

    def test_long_text_returns_div_with_three_children(self):
        """Text over threshold returns html.Div with preview, full, toggle."""
        from components.cards import _build_expandable_thesis

        result = _build_expandable_thesis("H" * 200, card_index=5, truncate_len=120)
        assert isinstance(result, html.Div)
        assert len(result.children) == 3  # preview, full, toggle

    def test_custom_truncate_len(self):
        """Custom truncate_len is respected."""
        from components.cards import _build_expandable_thesis

        # 50-char threshold: "I" * 60 should be truncated
        result = _build_expandable_thesis("I" * 60, card_index=0, truncate_len=50)
        assert isinstance(result, html.Div)
        # Preview should be 50 chars + "..."
        preview = result.children[0]
        assert preview.children == "I" * 50 + "..."

    def test_custom_id_prefix(self):
        """Custom id_prefix changes the component ID types."""
        from components.cards import _build_expandable_thesis

        result = _build_expandable_thesis("J" * 200, card_index=3, id_prefix="post-thesis")
        toggle = result.children[2]  # Third child is the toggle
        assert toggle.id == {"type": "post-thesis-toggle", "index": 3}
```

### Helper function needed for pattern-matching ID searches in tests

Add to `shit_tests/shitty_ui/test_cards.py`, after the existing `_make_row()` helper:

```python
def _find_component_by_pattern_id(component, type_str, index):
    """Recursively find a component whose id matches {"type": type_str, "index": index}."""
    comp_id = getattr(component, "id", None)
    if isinstance(comp_id, dict) and comp_id.get("type") == type_str and comp_id.get("index") == index:
        return component

    children = getattr(component, "children", None)
    if children is None:
        return None
    if isinstance(children, (list, tuple)):
        for child in children:
            if child is not None and not isinstance(child, str):
                result = _find_component_by_pattern_id(child, type_str, index)
                if result:
                    return result
    elif not isinstance(children, str):
        result = _find_component_by_pattern_id(children, type_str, index)
        if result:
            return result
    return None
```

### New Tests in `shit_tests/shitty_ui/test_layout.py`

```python
class TestThesisToggleCSS:
    """Tests for thesis expand/collapse CSS classes in the app stylesheet."""

    @patch("data.get_prediction_stats")
    @patch("layout.get_performance_metrics")
    @patch("layout.get_accuracy_by_confidence")
    @patch("layout.get_accuracy_by_asset")
    @patch("layout.get_recent_signals")
    @patch("layout.get_active_assets_from_db")
    def test_index_string_contains_thesis_toggle_css(
        self, mock_assets, mock_signals, mock_asset_acc, mock_conf_acc, mock_perf, mock_stats,
    ):
        """Test that app index_string contains .thesis-toggle-area CSS class."""
        mock_stats.return_value = {"total_posts": 0, "analyzed_posts": 0, "completed_analyses": 0, "bypassed_posts": 0, "avg_confidence": 0.0, "high_confidence_predictions": 0}
        mock_perf.return_value = {"total_outcomes": 0, "evaluated_predictions": 0, "correct_predictions": 0, "incorrect_predictions": 0, "accuracy_t7": 0.0, "avg_return_t7": 0.0, "total_pnl_t7": 0.0, "avg_confidence": 0.0}
        mock_conf_acc.return_value = pd.DataFrame()
        mock_asset_acc.return_value = pd.DataFrame()
        mock_signals.return_value = pd.DataFrame()
        mock_assets.return_value = []

        from layout import create_app
        app = create_app()

        assert ".thesis-toggle-area" in app.index_string
```

### Existing Test Compatibility

- **`test_handles_long_thesis`** (test_layout.py line 1006): Calls `create_feed_signal_card(self._make_row(thesis="A" * 500))` -- still works because `card_index` defaults to 0.
- **`test_handles_empty_thesis`** (test_layout.py line 999): Calls with `thesis=""` -- still works, no thesis section rendered.
- **`test_handles_nan_thesis`** (test_layout.py line 1041): `_safe_get` normalizes NaN to `""` -- no thesis section rendered.
- **All 6 post card test functions in TestSentimentLeftBorder and TestSentimentBadgeBackground**: Call `create_post_card(_make_row(...))` without `card_index` -- still works because `card_index` defaults to 0.

---

## What NOT To Do

1. **Do NOT use a server-side callback for expand/collapse.** This is a pure UI toggle with zero data fetching. A server round-trip adds 100-300ms of latency for no benefit. Use `clientside_callback` like the existing chevron rotation and countdown timer.

2. **Do NOT use CSS-only toggle (`:checked`, `:target`).** Dash re-renders components when callbacks fire, which resets CSS-only state. The Dash callback model is the correct way to persist toggle state.

3. **Do NOT modify `create_hero_signal_card()`.** Hero cards show a text preview of the post content, not the thesis. Adding expandable thesis to hero cards is out of scope for this phase and would require a different data flow (hero cards don't always have thesis data in their row).

4. **Do NOT use `dbc.Collapse` for thesis toggling.** `dbc.Collapse` requires a `is_open` state managed by a server-side callback. For a list of N cards, that would mean N separate `is_open` stores or a complex `ALL`-based callback. The `display: block/none` approach with `MATCH` is simpler and faster.

5. **Do NOT change the truncation lengths.** 120 characters for feed cards and 200 characters for post cards are established UX decisions. The expandable toggle makes the full text available on demand, so there is no need to show more in the preview.

6. **Do NOT break `create_feed_signal_card()` callers that don't pass `card_index`.** The `card_index=0` default ensures backward compatibility. The dashboard's `create_signal_card()` (a different function) is not affected by this change.

7. **Do NOT store expanded/collapsed state in `dcc.Store`.** The toggle state is transient UI state that resets on page reload or filter change, which is the correct behavior. Persisting it would create stale state bugs when the card list changes.

8. **Do NOT add transitions to the thesis text elements themselves.** CSS `transition` on `display` property does not work (display is not an animatable property). The chevron rotation is the animation. If smooth height animation is desired in the future, it would require a `max-height` transition approach, which is a Phase 08 visual polish concern.

---

## Verification Checklist

- [ ] `/signals` page shows "Show full thesis" toggle on cards with thesis > 120 characters
- [ ] Clicking "Show full thesis" reveals the full text and changes to "Hide thesis"
- [ ] Clicking "Hide thesis" collapses back to the truncated preview
- [ ] Chevron icon rotates 180 degrees when expanded
- [ ] Cards with thesis <= 120 characters show full text without any toggle
- [ ] Cards with empty or null thesis show no thesis section at all
- [ ] "Load More" button works correctly -- new cards get unique indices and their toggles work independently
- [ ] Dashboard post feed cards with thesis > 200 characters also have working expand/collapse
- [ ] All existing tests pass: `source venv/bin/activate && pytest shit_tests/shitty_ui/ -v`
- [ ] New tests pass for `TestExpandableThesis`, `TestExpandableThesisPostCard`, `TestBuildExpandableThesisHelper`, `TestThesisToggleCSS`
- [ ] No regression on `/performance`, `/trends`, or `/assets/` pages
- [ ] CHANGELOG.md updated

---

## CHANGELOG Entry

```markdown
### Added
- **Expandable thesis cards** -- Signal feed and post feed cards now show a "Show full thesis" toggle when the LLM investment reasoning exceeds the preview length, allowing users to read the full analysis without navigating away
  - Feed signal cards expand at 120 characters, post cards at 200 characters
  - Click-to-expand uses clientside callbacks for zero-latency toggling
  - Chevron icon animates on expand/collapse
  - Short theses display in full without a toggle
```
