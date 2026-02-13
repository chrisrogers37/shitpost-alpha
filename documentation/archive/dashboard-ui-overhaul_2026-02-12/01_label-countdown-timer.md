# Phase 01: Label the Countdown Timer

**Status:** 🔧 IN PROGRESS
**Started:** 2026-02-12

**PR Title:** `fix(ui): add "Next refresh" label to countdown timer and ensure MM:SS format`

**Risk Level:** Low

**Estimated Effort:** Small (< 1 hour)

**Files Modified:**
- `shitty_ui/components/header.py` (primary change)
- `shitty_ui/pages/dashboard.py` (verify clientside callback -- no change needed)
- `shit_tests/shitty_ui/test_layout.py` (new tests)
- `CHANGELOG.md` (entry)

---

## 1. Context

The dashboard header displays two pieces of refresh information in the top-right corner: the last-update time (e.g., "10:34:22 AM") and a countdown to the next refresh (e.g., "4:32"). The countdown timer currently has no label, so users seeing a raw number like "304:40" or "4:32" have no idea what it represents. Additionally, while the clientside callback in `dashboard.py` already formats the countdown as `M:SS` (minutes and zero-padded seconds), there is no descriptive context for the user.

The fix is purely cosmetic: add a "Next refresh" label beside the countdown value in the header component. The clientside JavaScript callback already produces the correct `MM:SS` format (see lines 568-570 of `dashboard.py`), so no JavaScript changes are needed.

---

## 2. Dependencies

None. This is a standalone UI label change with no backend, database, or API dependencies. It belongs to Batch 1 (independent, zero-risk changes).

---

## 3. Detailed Implementation Plan

### 3.1 File: `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/header.py`

**What changes:** Add a "Next refresh" label element next to the countdown span, and add a "Last updated" label next to the time display for visual consistency.

**BEFORE (lines 108-143):**

```python
                    # Refresh indicator
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.I(
                                        className="fas fa-sync-alt me-2",
                                        style={"color": COLORS["accent"]},
                                    ),
                                    html.Span(
                                        id="last-update-time",
                                        children="--:--",
                                        style={"color": COLORS["text"]},
                                    ),
                                ],
                                style={"marginBottom": "2px"},
                            ),
                            html.Div(
                                [
                                    html.Span(
                                        id="next-update-countdown",
                                        children="5:00",
                                        style={
                                            "color": COLORS["accent"],
                                            "fontWeight": "bold",
                                            "fontSize": "0.75rem",
                                        },
                                    ),
                                ]
                            ),
                        ],
                        style={
                            "fontSize": "0.8rem",
                            "textAlign": "right",
                        },
                    ),
```

**AFTER (lines 108-155, approximately):**

```python
                    # Refresh indicator
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.I(
                                        className="fas fa-sync-alt me-2",
                                        style={"color": COLORS["accent"]},
                                    ),
                                    html.Span(
                                        "Last updated ",
                                        style={
                                            "color": COLORS["text_muted"],
                                            "fontSize": "0.7rem",
                                        },
                                    ),
                                    html.Span(
                                        id="last-update-time",
                                        children="--:--",
                                        style={"color": COLORS["text"]},
                                    ),
                                ],
                                style={"marginBottom": "2px"},
                            ),
                            html.Div(
                                [
                                    html.Span(
                                        "Next refresh ",
                                        style={
                                            "color": COLORS["text_muted"],
                                            "fontSize": "0.7rem",
                                        },
                                    ),
                                    html.Span(
                                        id="next-update-countdown",
                                        children="5:00",
                                        style={
                                            "color": COLORS["accent"],
                                            "fontWeight": "bold",
                                            "fontSize": "0.75rem",
                                        },
                                    ),
                                ]
                            ),
                        ],
                        style={
                            "fontSize": "0.8rem",
                            "textAlign": "right",
                        },
                    ),
```

**Summary of changes:**
1. Add `html.Span("Last updated ", ...)` before the `last-update-time` span (line 117 area). Uses `COLORS["text_muted"]` at `0.7rem` to be visually subordinate.
2. Add `html.Span("Next refresh ", ...)` before the `next-update-countdown` span (line 127 area). Same muted styling.
3. No IDs change. No callback outputs change. The `id="last-update-time"` and `id="next-update-countdown"` spans are untouched -- their IDs, default children, and styles remain identical.

### 3.2 File: `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard.py`

**No changes needed.** The clientside callback (lines 558-583) already formats the countdown correctly as `M:SS`:

```javascript
const mins = Math.floor(remaining / 60);
const secs = Math.floor(remaining % 60);
const countdown = `${mins}:${secs.toString().padStart(2, '0')}`;
```

This produces output like `"4:32"` or `"0:05"`. The callback outputs to `Output("next-update-countdown", "children")` and `Output("last-update-time", "children")`, which update the inner text of the spans -- the static labels we are adding are sibling elements, not children of the same span, so they are unaffected.

### 3.3 File: `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_layout.py`

Add new tests to the existing `TestCreateHeader` class (currently at line 141 with only 2 tests). Add the following test methods after the existing `test_contains_title` method (after line 160):

```python
    def test_contains_next_refresh_label(self):
        """Test that header contains 'Next refresh' label for the countdown timer."""
        from layout import create_header

        header = create_header()

        # Walk the component tree to find the "Next refresh " text
        found = _find_text_in_component(header, "Next refresh")
        assert found, "Header should contain 'Next refresh' label"

    def test_contains_last_updated_label(self):
        """Test that header contains 'Last updated' label for the update time."""
        from layout import create_header

        header = create_header()

        found = _find_text_in_component(header, "Last updated")
        assert found, "Header should contain 'Last updated' label"

    def test_countdown_has_default_value(self):
        """Test that countdown timer has the default '5:00' value."""
        from layout import create_header

        header = create_header()

        found = _find_text_in_component(header, "5:00")
        assert found, "Header countdown should default to '5:00'"

    def test_last_update_has_default_value(self):
        """Test that last update time has the default '--:--' value."""
        from layout import create_header

        header = create_header()

        found = _find_text_in_component(header, "--:--")
        assert found, "Header last update time should default to '--:--'"
```

Also add the helper function at module level (before the first class, e.g., at line 16 after the imports):

```python
def _find_text_in_component(component, text):
    """Recursively search a Dash component tree for a text string.

    Returns True if the text is found as children or within children strings.
    """
    if isinstance(component, str):
        return text in component

    children = getattr(component, "children", None)
    if children is None:
        return False

    if isinstance(children, str):
        return text in children

    if isinstance(children, (list, tuple)):
        return any(_find_text_in_component(child, text) for child in children)

    # Single component child
    return _find_text_in_component(children, text)
```

---

## 4. Test Plan

### Tests to write in `shit_tests/shitty_ui/test_layout.py`

| # | Test Name | What It Verifies |
|---|-----------|-----------------|
| 1 | `TestCreateHeader.test_contains_next_refresh_label` | The header component tree contains the text "Next refresh" |
| 2 | `TestCreateHeader.test_contains_last_updated_label` | The header component tree contains the text "Last updated" |
| 3 | `TestCreateHeader.test_countdown_has_default_value` | The countdown span defaults to "5:00" |
| 4 | `TestCreateHeader.test_last_update_has_default_value` | The last-update span defaults to "--:--" |

### How to run

```bash
source venv/bin/activate && pytest shit_tests/shitty_ui/test_layout.py::TestCreateHeader -v
```

### Existing tests that must still pass

The two existing tests in `TestCreateHeader` (lines 144-160) must continue to pass:
- `test_returns_html_div`
- `test_contains_title`

Run the full UI test suite to verify no regressions:

```bash
source venv/bin/activate && pytest shit_tests/shitty_ui/ -v
```

---

## 5. Documentation Updates

### CHANGELOG.md entry

Add under `## [Unreleased]`:

```markdown
## [Unreleased]

### Fixed
- **Countdown timer missing label** - Added "Next refresh" and "Last updated" labels to the header refresh indicator so users understand what the countdown represents
```

---

## 6. Edge Cases

| Edge Case | Risk | Mitigation |
|-----------|------|-----------|
| Mobile layout wrapping | Low | The labels use small font (0.7rem) and are short. The existing `@media (max-width: 768px)` CSS in `layout.py` (lines 134-168) already handles the header-right section by stacking vertically. The added text is short enough to fit. |
| Clientside callback overwriting labels | None | The callback outputs to `Output("next-update-countdown", "children")` and `Output("last-update-time", "children")`. The labels are sibling `html.Span` elements in the parent `html.Div`, not children of the ID'd spans. The callback replaces the inner text of the spans only, not the parent div's children. |
| Default "5:00" display before first callback | None | The default `children="5:00"` is already set on the countdown span and remains unchanged. The "Next refresh" label appears immediately on page load. |
| Countdown showing "0:00" when expired | None | The clientside callback already clamps to 0 via `Math.max(0, ...)` on line 566. The label "Next refresh" still makes sense when showing "0:00" because it means the refresh is imminent. |

---

## 7. Verification Checklist

- [ ] `header.py` contains `html.Span("Next refresh ", ...)` before the countdown span
- [ ] `header.py` contains `html.Span("Last updated ", ...)` before the last-update-time span
- [ ] Both label spans use `COLORS["text_muted"]` for color
- [ ] Both label spans use `fontSize: "0.7rem"` to be visually subordinate
- [ ] The `id="next-update-countdown"` span is unchanged (same id, children, style)
- [ ] The `id="last-update-time"` span is unchanged (same id, children, style)
- [ ] No changes to `dashboard.py` clientside callback
- [ ] `pytest shit_tests/shitty_ui/test_layout.py::TestCreateHeader -v` passes (all 6 tests: 2 existing + 4 new)
- [ ] `pytest shit_tests/shitty_ui/ -v` passes (full UI test suite, no regressions)
- [ ] `ruff check shitty_ui/components/header.py` passes
- [ ] `ruff format shitty_ui/components/header.py` passes
- [ ] CHANGELOG.md updated under `[Unreleased]`
- [ ] Visual check: load dashboard, confirm "Last updated 10:34:22 AM" and "Next refresh 4:32" display correctly

---

## 8. What NOT To Do

1. **Do NOT modify the clientside callback in `dashboard.py`.** The MM:SS formatting already works. The callback outputs replace the `children` prop of the `id="next-update-countdown"` span only. Adding labels as children of that span would cause the callback to overwrite them.

2. **Do NOT wrap the label and value in a single span with one ID.** The label must be a separate `html.Span` sibling so the callback can independently update only the value span.

3. **Do NOT change the component IDs.** `"next-update-countdown"` and `"last-update-time"` are referenced by the clientside callback. Changing them breaks the timer.

4. **Do NOT add the labels inside the callback return values.** The labels are static text that never changes; they belong in the layout, not in the callback.

5. **Do NOT use a `html.Label` element.** The project consistently uses `html.Span` for inline text in the header. Follow the existing pattern.

6. **Do NOT add a trailing space in the label text like `"Next refresh"` without it.** Include a trailing space (`"Next refresh "`) so there is visual separation between the label and the value without needing CSS margins.

7. **Do NOT forget the helper function `_find_text_in_component`.** Without it, the new tests cannot walk the Dash component tree to verify text content. This is a utility needed because Dash components are nested Python objects, not rendered HTML.

---

### Critical Files for Implementation
- `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/header.py` - Primary file to modify: add "Next refresh" and "Last updated" labels
- `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard.py` - Reference only: verify clientside callback outputs to children of the ID'd spans (no changes needed)
- `/Users/chris/Projects/shitpost-alpha/shit_tests/shitty_ui/test_layout.py` - Add 4 new tests and the `_find_text_in_component` helper
- `/Users/chris/Projects/shitpost-alpha/CHANGELOG.md` - Add changelog entry under `[Unreleased]`
- `/Users/chris/Projects/shitpost-alpha/shitty_ui/constants.py` - Reference for `COLORS["text_muted"]` used in label styling
