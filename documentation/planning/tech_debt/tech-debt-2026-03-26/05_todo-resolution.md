# Phase 05: Resolve TODOs, Add Legacy Documentation

**PR Title**: `chore: resolve TODOs, add legacy documentation`
**Risk**: Low (comment-only changes, no behavior changes)
**Estimated Effort**: Low (~30 minutes)
**Files Modified**: 4
**Files Created**: 0
**Files Deleted**: 0

---

## Context

The codebase contains 5 TODO comments spread across 4 files. These TODOs create the false impression that work is pending when in reality the decisions have already been made:

- The dual-write in `s3_processor.py` stays until the signals migration is complete (documented in `SIGNALS_MIGRATION.md`)
- The Twitter harvester is a skeleton with no concrete implementation timeline
- Error reporting and metrics collection are not warranted at current scale
- The `shitty_ui/data/__init__.py` re-export layer serves a retiring dashboard but has no deprecation notice

Resolving these TODOs replaces vague future intent with concrete decision records, improving codebase clarity for any developer reading the code.

---

## Dependencies

- **Depends on**: None
- **Unlocks**: None
- **Parallel-safe with**: All other phases (this phase touches only comments/docstrings, no code changes)

---

## Detailed Implementation Plan

### Change 1: `shitvault/s3_processor.py` (line 217)

**Why**: The TODO says "Remove after full migration is complete" but gives no context about what migration, what the blocker is, or where to find the plan. Replace with a decision record comment that links to the migration plan.

**File**: `/Users/chris/Projects/shitpost-alpha/shitvault/s3_processor.py`

**Before** (lines 216-219):
```python
                # Also store in legacy table for backward compatibility
                # TODO: Remove after full migration is complete
                legacy_data = DatabaseUtils.transform_s3_data_to_shitpost(s3_data)
                await self.shitpost_ops.store_shitpost(legacy_data)
```

**After** (lines 216-221):
```python
                # Dual-write to legacy truth_social_shitposts table.
                # This stays until api/queries/feed_queries.py and shitty_ui/data/
                # migrate their reads to the signals table. Tracked in:
                # documentation/planning/SIGNALS_MIGRATION.md
                legacy_data = DatabaseUtils.transform_s3_data_to_shitpost(s3_data)
                await self.shitpost_ops.store_shitpost(legacy_data)
```

### Change 2: `shitposts/twitter_harvester.py` (lines 66 and 92)

**Why**: These TODOs imply the Twitter integration is planned work. It is not — the file is explicitly documented as a skeleton template. Replace with notes clarifying the status.

**File**: `/Users/chris/Projects/shitpost-alpha/shitposts/twitter_harvester.py`

**Before** (line 66, inside `_test_connection` docstring):
```python
    async def _test_connection(self) -> None:
        """Test Twitter API v2 connection.

        TODO: Implement with real Twitter API call.
        """
```

**After**:
```python
    async def _test_connection(self) -> None:
        """Test Twitter API v2 connection.

        NOTE: Skeleton -- implement when Twitter/X API access is obtained.
        Not currently planned.
        """
```

**Before** (line 92, inside `_fetch_batch` docstring):
```python
    async def _fetch_batch(
        self, cursor: Optional[str] = None
    ) -> tuple[List[Dict], Optional[str]]:
        """Fetch a batch of tweets.

        TODO: Implement with Twitter API v2 search or user timeline.
        """
```

**After**:
```python
    async def _fetch_batch(
        self, cursor: Optional[str] = None
    ) -> tuple[List[Dict], Optional[str]]:
        """Fetch a batch of tweets.

        NOTE: Skeleton -- implement when Twitter/X API access is obtained.
        Not currently planned.
        """
```

### Change 3: `shit/utils/error_handling.py` (lines 26-27)

**Why**: These TODOs suggest Sentry and metrics are upcoming. At current scale, Railway service logs and orchestrator log files provide sufficient error visibility. Replace with a concrete deferred-decision note.

**File**: `/Users/chris/Projects/shitpost-alpha/shit/utils/error_handling.py`

**Before** (lines 26-27):
```python
    # TODO: Add error reporting to external services (Sentry, etc.)
    # TODO: Add metrics collection for error rates
```

**After** (lines 26-28):
```python
    # Deferred: Error reporting (Sentry) and metrics collection.
    # Currently tracked via Railway service logs and the orchestrator
    # log files. Re-evaluate when error volume warrants external tooling.
```

### Change 4: `shitty_ui/data/__init__.py` (after the docstring)

**Why**: This file is a backward-compatibility re-export layer for the legacy Dash dashboard (`shitty_ui/`). The Dash dashboard is being retired in favor of the React frontend (`api/` + `frontend/`). Without a deprecation notice, developers may add new query functions here instead of in `api/queries/`.

**File**: `/Users/chris/Projects/shitpost-alpha/shitty_ui/data/__init__.py`

**Before** (lines 1-16):
```python
"""
Database access layer for Shitty UI Dashboard.

This package re-exports all query functions for backward compatibility.
All existing `from data import X` statements continue to work unchanged.

Internal structure:
    data/base.py              -- execute_query, ttl_cache, logger
    data/signal_queries.py    -- Signal loading, feed, filtering
    data/performance_queries.py -- KPIs, accuracy, P&L, streaks
    data/asset_queries.py     -- Screener, sparklines, asset stats
    data/insight_queries.py   -- Dynamic insight cards
    data/timeframe.py         -- Timeframe column mapping helper
"""

# --- Timeframe helpers ---
```

**After** (lines 1-21):
```python
"""
Database access layer for Shitty UI Dashboard.

This package re-exports all query functions for backward compatibility.
All existing `from data import X` statements continue to work unchanged.

Internal structure:
    data/base.py              -- execute_query, ttl_cache, logger
    data/signal_queries.py    -- Signal loading, feed, filtering
    data/performance_queries.py -- KPIs, accuracy, P&L, streaks
    data/asset_queries.py     -- Screener, sparklines, asset stats
    data/insight_queries.py   -- Dynamic insight cards
    data/timeframe.py         -- Timeframe column mapping helper
"""

# DEPRECATED: This module re-exports query functions for the legacy Dash
# dashboard (shitty_ui/). The Dash dashboard is being retired in favor of
# the React frontend (api/ + frontend/). Do not add new functions here.
# New query work should go in api/queries/.

# --- Timeframe helpers ---
```

---

## Test Plan

### No new tests required

This phase changes only comments and docstrings. There are no behavioral changes, no new functions, no modified signatures, and no altered control flow. Existing tests cover all four files and should continue to pass without modification.

### Verification steps

1. Run the full test suite to confirm no regressions:
   ```bash
   source venv/bin/activate && pytest -v
   ```

2. Run the linter to confirm no style issues introduced:
   ```bash
   source venv/bin/activate && ruff check shitvault/s3_processor.py shitposts/twitter_harvester.py shit/utils/error_handling.py shitty_ui/data/__init__.py
   ```

3. Grep for remaining TODOs to confirm all 5 are resolved:
   ```bash
   grep -rn "TODO" shitvault/s3_processor.py shitposts/twitter_harvester.py shit/utils/error_handling.py
   ```
   Expected output: no matches.

---

## Documentation Updates

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Changed
- **TODO resolution** -- Replaced 5 vague TODO comments with concrete decision records
  - `shitvault/s3_processor.py`: Dual-write stays until signals migration (linked to plan)
  - `shitposts/twitter_harvester.py`: Twitter skeleton marked as not currently planned
  - `shit/utils/error_handling.py`: Sentry/metrics deferred until error volume warrants it
  - `shitty_ui/data/__init__.py`: Added deprecation notice for legacy Dash re-export layer
```

### CLAUDE.md

No changes needed. The `shitty_ui/data/__init__.py` deprecation notice is self-documenting in the file. The signals migration plan is already referenced in `documentation/planning/SIGNALS_MIGRATION.md`.

---

## Stress Testing & Edge Cases

Not applicable. This phase modifies only comments and docstrings. There are no code paths, error scenarios, or performance considerations to evaluate.

---

## Verification Checklist

- [ ] `shitvault/s3_processor.py` line 217: TODO replaced with decision record linking to `SIGNALS_MIGRATION.md`
- [ ] `shitposts/twitter_harvester.py` line 66: TODO replaced with "NOTE: Skeleton" note
- [ ] `shitposts/twitter_harvester.py` line 92: TODO replaced with "NOTE: Skeleton" note
- [ ] `shit/utils/error_handling.py` lines 26-27: TODOs replaced with deferred-decision note
- [ ] `shitty_ui/data/__init__.py`: Deprecation notice added after docstring, before imports
- [ ] `grep -rn "TODO"` across all 4 files returns zero matches
- [ ] `pytest -v` passes with no new failures
- [ ] `ruff check` passes on all 4 files
- [ ] CHANGELOG.md updated with entry under `## [Unreleased]`

---

## What NOT To Do

1. **Do NOT delete or modify any code.** This phase is strictly comment/docstring changes. The dual-write in `s3_processor.py` must remain functional. The `NotImplementedError` raises in `twitter_harvester.py` must remain. The empty block after the error handling TODOs must remain.

2. **Do NOT remove the `twitter_harvester.py` file.** It serves as a template demonstrating the `SignalHarvester` interface pattern. The module docstring already explains this purpose.

3. **Do NOT add `# type: ignore` or `# noqa` comments.** The existing `# noqa: F401` comments in `shitty_ui/data/__init__.py` are intentional (re-exports). Do not add new suppression comments.

4. **Do NOT change the deprecation notice into a runtime `warnings.warn()`.** The Dash dashboard is still in production. A runtime warning would spam logs on every import. A static comment is the correct approach until the dashboard is fully retired.

5. **Do NOT move the deprecation notice inside the docstring.** It belongs as a standalone comment between the docstring and the first import, where it is immediately visible to developers adding new imports. Inside the docstring it would only appear in `help()` output, which nobody runs on `__init__.py` modules.

6. **Do NOT reformat or restructure any of the 4 files.** Touch only the specific lines identified above. Do not reorganize imports, adjust whitespace, or "clean up" adjacent code.
