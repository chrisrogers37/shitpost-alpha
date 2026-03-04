# Phase 02 — Extract Signal Query Builder

| Field | Value |
|---|---|
| **PR Title** | `refactor: extract shared signal feed filter builder to eliminate WHERE clause duplication` |
| **Risk** | Medium — refactoring query logic used by three UI-facing functions |
| **Effort** | Medium (~4 hours) |
| **Files Modified** | 1 (`shitty_ui/data/signal_queries.py`) |
| **Files Created** | 0 |
| **Dependencies** | None |
| **Unlocks** | Phase 05 (test coverage) |

---

## Context

Three functions in `shitty_ui/data/signal_queries.py` — `get_signal_feed()` (lines 426-529), `get_signal_feed_count()` (lines 532-597), and indirectly `get_signal_feed_csv()` (lines 636-700, which delegates to `get_signal_feed()`) — share identical WHERE clause construction logic for five filter parameters: `sentiment_filter`, `confidence_min`, `confidence_max`, `asset_filter`, and `outcome_filter`.

Lines 486-514 in `get_signal_feed()` and lines 560-588 in `get_signal_feed_count()` are character-for-character duplicates. If a new filter is added or an existing filter is changed, both functions must be updated in lockstep. This duplication creates a maintenance risk: a developer might update one function and forget the other, causing the feed count to disagree with the feed data.

This phase extracts the shared filter logic into a single `_build_signal_feed_filters()` private helper that both functions call, eliminating the duplication.

Additionally, `load_filtered_posts()` (lines 54-161) shares a subset of the same filter parameters (`confidence_min`, `confidence_max`) but operates on a different table join pattern (LEFT JOIN vs INNER JOIN) and has additional filters (`has_prediction`, `date_from`, `date_to`, `assets_filter` as a list). The overlap is partial — only the confidence filters are identical SQL. We will **not** force `load_filtered_posts()` into the same builder because:
1. It uses a different base query (LEFT JOIN, different SELECT columns)
2. Its shared filters are only 2 of its 6 parameters
3. Forcing it would require the builder to handle parameters it doesn't share with the other two functions

This keeps the refactor focused and low-risk.

---

## Dependencies

- **Requires**: Nothing — this phase has no prerequisites.
- **Unlocks**: Phase 05 (test coverage) — once filters are consolidated, writing exhaustive tests for edge cases becomes simpler since there is only one code path to test.

---

## Detailed Implementation Plan

### Step 1: Add the `_build_signal_feed_filters()` helper function

Insert a new private function at line 425 (just before `get_signal_feed()`), between the `get_weekly_signal_count()` function (ends at line 423) and `get_signal_feed()` (starts at line 426).

**Add this new code at `shitty_ui/data/signal_queries.py`, insert between lines 424 and 426:**

```python
def _build_signal_feed_filters(
    sentiment_filter: Optional[str] = None,
    confidence_min: Optional[float] = None,
    confidence_max: Optional[float] = None,
    asset_filter: Optional[str] = None,
    outcome_filter: Optional[str] = None,
) -> tuple[str, Dict[str, Any]]:
    """
    Build shared WHERE clause fragments for signal feed queries.

    Constructs the dynamic filter portion of the WHERE clause used by both
    get_signal_feed() and get_signal_feed_count(). The returned SQL string
    is meant to be appended to a base query that already includes the standard
    completed-prediction filters (analysis_status, confidence IS NOT NULL, etc.).

    Args:
        sentiment_filter: 'bullish', 'bearish', or None.
        confidence_min: Minimum confidence (0.0-1.0).
        confidence_max: Maximum confidence (0.0-1.0).
        asset_filter: Specific ticker symbol (e.g. 'AAPL').
        outcome_filter: 'correct', 'incorrect', 'evaluated', 'pending', or None.

    Returns:
        Tuple of (where_clause_str, params_dict) where where_clause_str contains
        zero or more ' AND ...' fragments and params_dict contains the corresponding
        bind parameters.
    """
    clauses = ""
    params: Dict[str, Any] = {}

    if sentiment_filter and sentiment_filter in ("bullish", "bearish"):
        clauses += """
            AND EXISTS (
                SELECT 1 FROM jsonb_each_text(p.market_impact) kv
                WHERE LOWER(kv.value) = :sentiment_filter
            )
        """
        params["sentiment_filter"] = sentiment_filter.lower()

    if confidence_min is not None:
        clauses += " AND p.confidence >= :confidence_min"
        params["confidence_min"] = confidence_min

    if confidence_max is not None:
        clauses += " AND p.confidence <= :confidence_max"
        params["confidence_max"] = confidence_max

    if asset_filter:
        clauses += " AND po.symbol = :asset_filter"
        params["asset_filter"] = asset_filter.upper()

    if outcome_filter == "correct":
        clauses += " AND po.correct_t7 = true"
    elif outcome_filter == "incorrect":
        clauses += " AND po.correct_t7 = false"
    elif outcome_filter == "evaluated":
        clauses += " AND po.correct_t7 IS NOT NULL"
    elif outcome_filter == "pending":
        clauses += " AND po.correct_t7 IS NULL"

    return clauses, params
```

**Why this design:**
- Returns a `(str, dict)` tuple — the simplest possible contract. The caller appends the string to its base query and merges the dict into its params.
- The SQL fragments start with `AND` — identical to the current inline code, so they can be concatenated directly after the base WHERE clause.
- The function is private (prefixed with `_`) since it is an internal implementation detail of this module. It is NOT exported from `data/__init__.py`.

### Step 2: Refactor `get_signal_feed()` to use the builder

**BEFORE** (lines 486-514, the filter block inside `get_signal_feed()`):

```python
    params: Dict[str, Any] = {"limit": limit, "offset": offset}

    if sentiment_filter and sentiment_filter in ("bullish", "bearish"):
        base_query += """
            AND EXISTS (
                SELECT 1 FROM jsonb_each_text(p.market_impact) kv
                WHERE LOWER(kv.value) = :sentiment_filter
            )
        """
        params["sentiment_filter"] = sentiment_filter.lower()

    if confidence_min is not None:
        base_query += " AND p.confidence >= :confidence_min"
        params["confidence_min"] = confidence_min

    if confidence_max is not None:
        base_query += " AND p.confidence <= :confidence_max"
        params["confidence_max"] = confidence_max

    if asset_filter:
        base_query += " AND po.symbol = :asset_filter"
        params["asset_filter"] = asset_filter.upper()

    if outcome_filter == "correct":
        base_query += " AND po.correct_t7 = true"
    elif outcome_filter == "incorrect":
        base_query += " AND po.correct_t7 = false"
    elif outcome_filter == "evaluated":
        base_query += " AND po.correct_t7 IS NOT NULL"
    elif outcome_filter == "pending":
        base_query += " AND po.correct_t7 IS NULL"
```

**AFTER** (replace the above with):

```python
    params: Dict[str, Any] = {"limit": limit, "offset": offset}

    # Apply shared signal feed filters
    filter_clauses, filter_params = _build_signal_feed_filters(
        sentiment_filter=sentiment_filter,
        confidence_min=confidence_min,
        confidence_max=confidence_max,
        asset_filter=asset_filter,
        outcome_filter=outcome_filter,
    )
    base_query += filter_clauses
    params.update(filter_params)
```

**What changed:** Lines 486-514 (the 5 filter if/elif blocks and their params assignments) were replaced with 7 lines: a call to `_build_signal_feed_filters()` plus `params.update()`. Everything else — the function signature, docstring, base query, ORDER BY, pagination, try/except, and return type — is unchanged.

### Step 3: Refactor `get_signal_feed_count()` to use the builder

**BEFORE** (lines 560-588, the filter block inside `get_signal_feed_count()`):

```python
    params: Dict[str, Any] = {}

    if sentiment_filter and sentiment_filter in ("bullish", "bearish"):
        base_query += """
            AND EXISTS (
                SELECT 1 FROM jsonb_each_text(p.market_impact) kv
                WHERE LOWER(kv.value) = :sentiment_filter
            )
        """
        params["sentiment_filter"] = sentiment_filter.lower()

    if confidence_min is not None:
        base_query += " AND p.confidence >= :confidence_min"
        params["confidence_min"] = confidence_min

    if confidence_max is not None:
        base_query += " AND p.confidence <= :confidence_max"
        params["confidence_max"] = confidence_max

    if asset_filter:
        base_query += " AND po.symbol = :asset_filter"
        params["asset_filter"] = asset_filter.upper()

    if outcome_filter == "correct":
        base_query += " AND po.correct_t7 = true"
    elif outcome_filter == "incorrect":
        base_query += " AND po.correct_t7 = false"
    elif outcome_filter == "evaluated":
        base_query += " AND po.correct_t7 IS NOT NULL"
    elif outcome_filter == "pending":
        base_query += " AND po.correct_t7 IS NULL"
```

**AFTER** (replace the above with):

```python
    # Apply shared signal feed filters
    filter_clauses, filter_params = _build_signal_feed_filters(
        sentiment_filter=sentiment_filter,
        confidence_min=confidence_min,
        confidence_max=confidence_max,
        asset_filter=asset_filter,
        outcome_filter=outcome_filter,
    )
    base_query += filter_clauses
    params = filter_params
```

**What changed:** Lines 560-588 (the 5 filter if/elif blocks) were replaced with 7 lines. The `params: Dict[str, Any] = {}` initializer was replaced with `params = filter_params` since this function has no additional parameters (no limit/offset). Everything else is unchanged.

### Step 4: Verify `load_filtered_posts()` is NOT changed

`load_filtered_posts()` shares only `confidence_min`/`confidence_max` with the signal feed functions. It has its own distinct parameters (`has_prediction`, `date_from`, `date_to`, `assets_filter` as a list) and a different query structure (LEFT JOIN, different table aliases, WHERE 1=1 base). It also does post-processing asset filtering in Python rather than SQL.

**Decision: Do NOT modify `load_filtered_posts()`.** The overlap is too small (2 of 6 parameters) and the query structure is different enough that sharing the builder would add complexity, not reduce it.

### Step 5: Verify `get_signal_feed_csv()` is NOT changed

`get_signal_feed_csv()` already delegates to `get_signal_feed()` — it does not construct its own query. Since `get_signal_feed()` now uses the builder internally, `get_signal_feed_csv()` automatically benefits from the deduplication without any code changes.

---

## Test Plan

### Existing Tests (must all pass unchanged)

All 26+ existing tests across these test classes verify behavior through the public API and will continue to pass because:

1. **`TestGetSignalFeed`** (10 tests, `test_data.py` lines 2482-2665): Tests call `get_signal_feed()` and check `params` dict contents and query string fragments. The refactored function produces identical SQL strings and params dicts.

2. **`TestGetSignalFeedCount`** (5 tests, `test_data.py` lines 2668-2727): Tests call `get_signal_feed_count()` and check params and return values. Same analysis applies.

3. **`TestGetSignalFeedCsv`** (5 tests, `test_data.py` lines 2785-2960): Tests mock `get_signal_feed` at the module level (`@patch("data.signal_queries.get_signal_feed")`). Since the public API is unchanged, these tests are unaffected.

4. **`TestSignalFeedEvaluatedSort`** (3 tests, `test_data.py` lines 3169-3207): Tests verify `"evaluated"` outcome filter and ORDER BY clause. Both are preserved exactly.

5. **`TestLoadFilteredPosts`** (3 tests, `test_data.py` lines 738-807): These tests are unaffected because we are not modifying `load_filtered_posts()`.

### No New Tests Required

This phase is a pure internal refactor. The `_build_signal_feed_filters()` function is private and exercised entirely through the existing public functions. Every code path through the builder is already covered by existing tests. Phase 05 (test coverage) will add direct unit tests for `_build_signal_feed_filters()` if needed.

### Manual Verification Steps

After implementation, verify the refactored SQL output is character-identical:

1. Add a temporary `print()` at the end of `_build_signal_feed_filters()` during development to inspect the generated clauses
2. Compare the generated SQL with the original inline code for each filter combination
3. Remove the temporary print before committing

---

## Documentation Updates

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Changed
- **Signal Query Builder** — Extracted shared WHERE clause construction into `_build_signal_feed_filters()` helper in `signal_queries.py`, eliminating duplication between `get_signal_feed()` and `get_signal_feed_count()`
```

---

## Stress Testing & Edge Cases

### Edge Cases Handled by the Builder

All edge cases are inherited from the existing code and preserved exactly:

1. **`sentiment_filter` is an invalid value** (e.g., `"neutral"`): The `in ("bullish", "bearish")` guard skips the filter. No clause added, no param added. Identical to current behavior.
2. **`sentiment_filter` is empty string**: The truthy check (`if sentiment_filter and ...`) skips it. Identical to current behavior.
3. **`confidence_min` is `0.0`**: `0.0 is not None` is `True`, so the filter is applied. This matches current behavior.
4. **`asset_filter` is empty string**: The truthy check (`if asset_filter:`) skips it. Identical to current behavior.
5. **`outcome_filter` is an unknown value** (e.g., `"maybe"`): None of the `==` comparisons match, so no clause is added. Identical to current behavior.
6. **All filters are `None`**: Returns `("", {})`. The caller appends an empty string and merges an empty dict — no effect on the query. Identical to current behavior.
7. **All filters are set simultaneously**: All clauses and params are accumulated. The order of AND clauses is preserved (sentiment, confidence_min, confidence_max, asset, outcome). Identical to current behavior.

### Performance Considerations

None. The builder performs only string concatenation and dict assignment — no I/O, no allocation of significance. The SQL query itself is unchanged.

---

## Verification Checklist

- [ ] Run signal query tests: `./venv/bin/python -m pytest shit_tests/shitty_ui/test_data.py -v`
- [ ] Run data init tests: `./venv/bin/python -m pytest shit_tests/shitty_ui/test_data_init.py -v`
- [ ] Run ruff check: `./venv/bin/python -m ruff check shitty_ui/data/signal_queries.py`
- [ ] Run ruff format: `./venv/bin/python -m ruff format shitty_ui/data/signal_queries.py`
- [ ] Verify `_build_signal_feed_filters` is NOT in `shitty_ui/data/__init__.py`
- [ ] Run load_filtered_posts tests: `./venv/bin/python -m pytest shit_tests/shitty_ui/test_data.py::TestLoadFilteredPosts -v`
- [ ] Run full test suite: `./venv/bin/python -m pytest -v`

---

## What NOT To Do

1. **Do NOT export `_build_signal_feed_filters` from `data/__init__.py`.** It is a private helper. Adding it to the public API would create a coupling contract that makes future changes harder.

2. **Do NOT change the function signatures of `get_signal_feed()`, `get_signal_feed_count()`, or `get_signal_feed_csv()`.** This is an internal refactor. The public API must remain identical.

3. **Do NOT force `load_filtered_posts()` to use the builder.** Its query structure is different (LEFT JOIN vs INNER JOIN, different base WHERE clause, different parameters). Forcing it would require the builder to handle parameters it does not share with the signal feed functions, adding complexity instead of removing it.

4. **Do NOT change the order of AND clauses in the generated SQL.** Some tests check for specific SQL fragments in the query string. If the clause order changes, these assertions could break even though the SQL is logically equivalent.

5. **Do NOT add the builder to `base.py`.** It is specific to signal feed queries, not a general-purpose utility. Keeping it in `signal_queries.py` respects the module boundary.

6. **Do NOT create a new file for the builder.** One private function does not warrant its own module.

7. **Do NOT use a class or dataclass for the return value.** A simple `tuple[str, dict]` is the lightest-weight contract and matches the existing pattern.

8. **Do NOT change `params: Dict[str, Any] = {}` to `params = filter_params` in `get_signal_feed()`** — in that function, `params` is initialized with `{"limit": limit, "offset": offset}` first, so you must use `params.update(filter_params)`. Only in `get_signal_feed_count()`, where params starts empty, can you assign directly.
