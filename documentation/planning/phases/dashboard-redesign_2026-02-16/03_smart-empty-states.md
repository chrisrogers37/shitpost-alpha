# Phase 03: Smart Empty States

**Status**: 🔧 IN PROGRESS
**Started**: 2026-02-16

**PR Title**: feat: contextual empty states with guidance
**Risk Level**: Low
**Estimated Effort**: Small-Medium (~2-3 hours)
**Dependencies**: Phase 01 (soft — uses similar fallback pattern)
**Unlocks**: Phase 10 (Brand Identity)

## Files Modified

| File | Action |
|------|--------|
| `shitty_ui/components/cards.py` | Enhance `create_empty_state_chart()` with `context_line`/`action_text` params; add new `create_empty_state_html()` |
| `shitty_ui/data.py` | Add `get_empty_state_context()` cached query function |
| `shitty_ui/pages/dashboard.py` | Update 7 empty state locations across 2 callbacks |
| `shitty_ui/pages/dashboard.py` | Add `create_empty_state_html` and `get_empty_state_context` imports |
| `shit_tests/shitty_ui/test_cards.py` | Add `TestEmptyStateHtml` class (8 tests) |
| `shit_tests/shitty_ui/test_layout.py` | Extend `TestEmptyStateChart` (7 tests for new params) |
| `shit_tests/shitty_ui/test_data.py` | Add `TestGetEmptyStateContext` class (5 tests) |
| `CHANGELOG.md` | Add entry |

## Context

The dashboard currently shows six distinct empty state messages that are dead ends: a gray icon, a static message, and no path forward. Users see these when:
- The selected time period (7D, 30D) has no evaluated data, even though a wider window does
- Predictions are too young to have outcomes (7-day maturation window)
- The system is new and very little data exists yet

**Goal**: Replace each dead end with a contextual message that tells the user (a) why it's empty, (b) what timeframe has data, and (c) where to look next.

**Screenshot**: See `/tmp/design-review/dashboard-desktop.png` — all KPI zeros, empty charts with static messages.

## Detailed Implementation

### Step A: Add `get_empty_state_context()` to data.py

**File**: `shitty_ui/data.py`
**Location**: Around line 1475, after `get_high_confidence_metrics`

One lightweight query that gathers counts all empty states need:

```python
@ttl_cache(ttl_seconds=300)
def get_empty_state_context() -> Dict[str, Any]:
    """Get contextual counts for smart empty state messages.

    Returns lightweight aggregate counts used by empty-state components
    to guide users toward timeframes and pages that have data.

    Returns:
        Dict with keys:
            total_evaluated: int -- all-time evaluated prediction outcomes
            total_pending: int -- outcomes awaiting maturation
            total_high_confidence: int -- all-time high-confidence signals (>=0.75)
    """
    query = text("""
        SELECT
            COUNT(CASE WHEN correct_t7 IS NOT NULL THEN 1 END) AS total_evaluated,
            COUNT(CASE WHEN correct_t7 IS NULL THEN 1 END) AS total_pending,
            COUNT(CASE WHEN prediction_confidence >= 0.75 AND correct_t7 IS NOT NULL THEN 1 END) AS total_high_confidence
        FROM prediction_outcomes
    """)

    try:
        rows, columns = execute_query(query)
        if rows and rows[0]:
            total_evaluated = rows[0][0] or 0
            total_pending = rows[0][1] or 0
            total_high_confidence = rows[0][2] or 0

            return {
                "total_evaluated": total_evaluated,
                "total_pending": total_pending,
                "total_high_confidence": total_high_confidence,
            }
    except Exception as e:
        logger.error(f"Error loading empty state context: {e}")

    return {
        "total_evaluated": 0,
        "total_pending": 0,
        "total_high_confidence": 0,
    }
```

Also add to `clear_all_caches()` (~line 1095):
```python
get_empty_state_context.clear_cache()  # type: ignore
```

### Step B: Enhance `create_empty_state_chart()` in cards.py

**File**: `shitty_ui/components/cards.py`
**Current signature** (line ~130):

```python
def create_empty_state_chart(
    message: str = "No data available",
    hint: str = "",
    icon: str = "ℹ️",
    height: int = 80,
) -> go.Figure:
```

**New signature** (backward-compatible):

```python
def create_empty_state_chart(
    message: str = "No data available",
    hint: str = "",
    icon: str = "ℹ️",
    height: int = 80,
    context_line: str = "",
    action_text: str = "",
) -> go.Figure:
```

- `context_line`: Secondary data-driven line (e.g., "74 evaluated trades all-time"). Rendered in `COLORS["text_muted"]`.
- `action_text`: Navigation hint (e.g., "Try expanding to All"). Rendered in `COLORS["accent"]`.

Update the annotation text assembly (lines ~144-146):
```python
display_text = f"{icon}  {message}"
if hint:
    display_text += f"<br><span style='font-size:11px; color:{COLORS['border']}'>{hint}</span>"
if context_line:
    display_text += f"<br><span style='font-size:11px; color:{COLORS['text_muted']}'>{context_line}</span>"
if action_text:
    display_text += f"<br><span style='font-size:11px; color:{COLORS['accent']}'>{action_text}</span>"
```

Auto-adjust height when extra lines present:
```python
extra_lines = sum(1 for x in [context_line, action_text] if x)
if extra_lines > 0 and height == 80:
    height = 80 + (extra_lines * 18)
```

### Step C: Add `create_empty_state_html()` to cards.py

**File**: `shitty_ui/components/cards.py`
**Location**: Near `create_empty_state_chart` (around line 167)

For sections that render Dash components (hero section, signal lists) rather than Plotly figures:

```python
def create_empty_state_html(
    message: str,
    hint: str = "",
    context_line: str = "",
    action_text: str = "",
    action_href: str = "",
    icon_class: str = "fas fa-moon",
) -> html.Div:
    """Create an HTML empty-state card with contextual guidance."""
    children = [
        html.I(className=f"{icon_class} me-2", style={"color": COLORS["text_muted"]}),
        html.Span(message, style={"color": COLORS["text_muted"], "fontSize": "0.9rem"}),
    ]

    sub_children = []
    if hint:
        sub_children.append(html.Div(hint, style={
            "color": COLORS["border"], "fontSize": "0.8rem", "marginTop": "6px",
        }))
    if context_line:
        sub_children.append(html.Div(context_line, style={
            "color": COLORS["text_muted"], "fontSize": "0.8rem", "marginTop": "4px",
        }))
    if action_text:
        action_content = (
            dcc.Link(action_text, href=action_href, style={
                "color": COLORS["accent"], "fontSize": "0.8rem", "textDecoration": "none",
            })
            if action_href
            else html.Span(action_text, style={
                "color": COLORS["accent"], "fontSize": "0.8rem",
            })
        )
        sub_children.append(html.Div(action_content, style={"marginTop": "4px"}))

    return html.Div(
        [html.Div(children), *sub_children],
        style={
            "padding": "24px", "textAlign": "center",
            "backgroundColor": COLORS["secondary"], "borderRadius": "12px",
            "border": f"1px solid {COLORS['border']}",
        },
    )
```

### Step D: Update Empty States in dashboard.py

Update 7 locations where empty states appear. Each follows the same pattern:

```python
try:
    ctx = get_empty_state_context()
    total_eval = ctx["total_evaluated"]
    context_line = f"{total_eval} evaluated trade{'s' if total_eval != 1 else ''} all-time" if total_eval > 0 else ""
    action_text = "Try expanding to All" if total_eval > 0 and days is not None else ""
except Exception:
    context_line = ""
    action_text = ""
```

Then pass `context_line` and `action_text` to `create_empty_state_chart()` or `create_empty_state_html()`.

**Locations to update:**

| Location | Lines | Type | Context Message |
|----------|-------|------|-----------------|
| Hero signals empty | ~599-625 | HTML | "N high-confidence signals all-time" + link to /performance |
| Accuracy over time | ~750-753 | Chart | "N evaluated trades all-time" + "Try expanding to All" |
| Confidence chart | ~791-794 | Chart | "N evaluated trades all-time" + "Try expanding to All" |
| Asset chart | ~835-838 | Chart | "N evaluated trades all-time" + "Try expanding to All" |
| Recent signals | ~851-861 | HTML | "N signals all-time" + link to /signals |
| Performance confidence | ~1250-1253 | Chart | "N predictions awaiting evaluation" |
| Performance sentiment | ~1315-1318 | Chart | "N predictions awaiting evaluation" |

### Step E: Update dashboard.py imports

Add `create_empty_state_html` to the existing cards import in `dashboard.py`, and add `get_empty_state_context` to the data import.

### Key Design Decisions

- **Single query for all context**: `get_empty_state_context()` runs one query cached for 5 minutes. Multiple empty states in the same render hit the cache.
- **Graceful degradation**: Every `get_empty_state_context()` call is wrapped in `try/except`. If the query fails, empty states fall back to the original behavior (message + hint, no context).
- **No buttons in charts**: Plotly annotations are SVG text — they can't contain clickable HTML. Only the HTML empty states (`create_empty_state_html`) get `dcc.Link` components.

---

## Test Plan

### `TestEmptyStateChart` extensions (test_layout.py)
1. `test_context_line_appears_in_annotation`
2. `test_action_text_appears_in_annotation`
3. `test_context_and_action_combined`
4. `test_empty_context_line_omitted`
5. `test_auto_height_adjustment_with_context`
6. `test_explicit_height_no_crash`
7. `test_backward_compatibility_no_new_params`

### `TestEmptyStateHtml` (test_cards.py)
1. `test_returns_html_div`
2. `test_message_appears_in_text`
3. `test_hint_appears_when_provided`
4. `test_context_line_appears_when_provided`
5. `test_action_text_with_href_creates_link`
6. `test_action_text_without_href_creates_span`
7. `test_icon_class_applied`
8. `test_minimal_call_only_message`

### `TestGetEmptyStateContext` (test_data.py)
1. `test_returns_expected_keys`
2. `test_handles_all_zeros`
3. `test_handles_null_values`
4. `test_handles_query_error`

---

## Verification Checklist

- [ ] `source venv/bin/activate && pytest shit_tests/shitty_ui/ -v` — full UI suite passes
- [ ] All existing callers of `create_empty_state_chart()` work without modification (no new required params)
- [ ] Visual: set period to "7D" — confirm context messages render with counts and action text
- [ ] Visual: set period to "All" — confirm charts load normally (no empty states shown)
- [ ] CHANGELOG.md updated

## What NOT To Do

1. **Do NOT add navigation buttons to chart empty states.** Plotly annotations are SVG text, not clickable HTML.
2. **Do NOT make `get_empty_state_context()` a required dependency.** Every call is wrapped in try/except with fallbacks.
3. **Do NOT change the default height unconditionally.** Auto-adjust only when new content lines are present.
4. **Do NOT query full prediction_outcomes per empty state.** Use the single cached function.
5. **Do NOT modify `build_empty_signal_chart()` in charts.py.** That serves trends/asset pages (different scope).
6. **Do NOT duplicate the `dcc` import in cards.py.** It already exists on line 7.
7. **Do NOT break existing test assertions.** The new params are all optional with empty-string defaults.

## CHANGELOG Entry

```markdown
### Added
- **Smart empty states** -- Dashboard sections now show contextual guidance when empty, including data counts, why the section is empty, and suggestions to expand the time period or visit other pages
  - New `create_empty_state_html()` component for HTML-based empty states with navigation links
  - Enhanced `create_empty_state_chart()` with `context_line` and `action_text` parameters
  - New `get_empty_state_context()` cached query for aggregate counts
```
