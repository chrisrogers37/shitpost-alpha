# Phase 01 — Quick Wins: Asyncio Fixes + Dead Code Cleanup

| Field | Value |
|---|---|
| **PR Title** | `fix: replace deprecated asyncio.get_event_loop() and remove dead code` |
| **Risk** | Low |
| **Effort** | Low (~2 hours) |
| **Files Modified** | 5 source files, 2 test files |
| **Files Created** | 0 |
| **Dependencies** | None |
| **Unlocks** | None |

---

## Context

Python 3.13 deprecates `asyncio.get_event_loop()` when no running event loop exists. The project currently uses this pattern in 3 production files (5 call sites in source, 3 in error handling utilities). While these calls currently work because they are always invoked from within a running async context, the deprecation warnings create noise and the pattern will eventually break in a future Python release. Fixing them now is a zero-risk modernization.

Additionally, two small dead code items exist: an unused `validate_prompt_version()` function in the prompt module and an unused `Decimal` import in market data models. Removing them reduces cognitive load for future developers.

---

## Dependencies

- **Depends on**: Nothing. This phase is fully independent.
- **Unlocks**: Nothing. Other phases do not depend on this work.
- **Parallel safety**: This phase modifies files that no other phase touches (confirmed: `shitpost_analyzer.py`, `s3_data_lake.py`, `error_handling.py`, `prompts.py`, `models.py`).

---

## Detailed Implementation Plan

### Change 1: Replace `asyncio.get_event_loop()` in `shitpost_ai/shitpost_analyzer.py`

**File**: `/Users/chris/Projects/shitpost-alpha/shitpost_ai/shitpost_analyzer.py`

**What and why**: The `_trigger_reactive_backfill` method at line 527-534 uses `asyncio.get_event_loop()` to get the loop, then creates a `ThreadPoolExecutor` manually to run a sync function. The modern replacement is `asyncio.to_thread()`, which handles executor management internally and is the idiomatic Python 3.9+ pattern.

**Import change** (line 7): Remove the `concurrent.futures` import since it is only used in this one location.

**Before** (lines 6-7):
```python
import asyncio
import concurrent.futures
```

**After** (lines 6-7):
```python
import asyncio
```

**Before** (lines 527-534):
```python
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                result = await loop.run_in_executor(
                    executor,
                    auto_backfill_prediction,
                    prediction_id,
                )
```

**After** (lines 527-530):
```python
            result = await asyncio.to_thread(
                auto_backfill_prediction,
                prediction_id,
            )
```

**Notes**:
- `asyncio.to_thread()` uses the default executor internally, which is a `ThreadPoolExecutor`. The previous code created a dedicated single-worker executor per call. The default executor is shared but this is fine — the backfill operation is infrequent and non-blocking to other tasks.
- The `await` semantics are identical: both patterns schedule the sync function in a thread and return a coroutine.

---

### Change 2: Replace `asyncio.get_event_loop()` in `shit/s3/s3_data_lake.py` (3 instances)

**File**: `/Users/chris/Projects/shitpost-alpha/shit/s3/s3_data_lake.py`

**What and why**: Three methods (`store_raw_data`, `check_object_exists`, `get_raw_data`) use `asyncio.get_event_loop().run_in_executor(None, lambda: ...)` to run synchronous boto3 S3 calls off the async event loop. The modern replacement is `asyncio.to_thread()`.

**Important**: The `store_raw_data` method wraps the executor call in `asyncio.wait_for()` for timeout handling. This pattern must be preserved — `asyncio.to_thread()` returns an awaitable that works with `asyncio.wait_for()`.

#### Instance 1: `store_raw_data` (lines 109-123)

**Before** (lines 109-123):
```python
                await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self.s3_client.client.put_object(
                            Bucket=self.config.bucket_name,
                            Key=s3_key,
                            Body=json.dumps(storage_data.__dict__, indent=2),
                            ContentType='application/json',
                            Metadata={
                                'shitpost_id': shitpost_id,
                                'post_timestamp': post_timestamp.isoformat(),
                                'source': 'truth_social_api'
                            }
                        )
                    ),
                    timeout=self.config.timeout_seconds
                )
```

**After** (lines 109-122):
```python
                await asyncio.wait_for(
                    asyncio.to_thread(
                        lambda: self.s3_client.client.put_object(
                            Bucket=self.config.bucket_name,
                            Key=s3_key,
                            Body=json.dumps(storage_data.__dict__, indent=2),
                            ContentType='application/json',
                            Metadata={
                                'shitpost_id': shitpost_id,
                                'post_timestamp': post_timestamp.isoformat(),
                                'source': 'truth_social_api'
                            }
                        )
                    ),
                    timeout=self.config.timeout_seconds
                )
```

**Key detail**: The `asyncio.wait_for()` wrapping is preserved. The only change is replacing `asyncio.get_event_loop().run_in_executor(None, lambda: ...)` with `asyncio.to_thread(lambda: ...)`.

#### Instance 2: `check_object_exists` (lines 151-153)

**Before** (lines 151-153):
```python
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.s3_client.client.head_object(Bucket=self.config.bucket_name, Key=s3_key)
            )
```

**After** (lines 151-153):
```python
            await asyncio.to_thread(
                lambda: self.s3_client.client.head_object(Bucket=self.config.bucket_name, Key=s3_key)
            )
```

#### Instance 3: `get_raw_data` (lines 180-182)

**Before** (lines 180-182):
```python
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.s3_client.client.get_object(Bucket=self.config.bucket_name, Key=s3_key)
            )
```

**After** (lines 180-182):
```python
            response = await asyncio.to_thread(
                lambda: self.s3_client.client.get_object(Bucket=self.config.bucket_name, Key=s3_key)
            )
```

---

### Change 3: Replace `asyncio.get_event_loop().time()` in `shit/utils/error_handling.py` (3 instances)

**File**: `/Users/chris/Projects/shitpost-alpha/shit/utils/error_handling.py`

**What and why**: The `CircuitBreaker` and `RateLimiter` classes use `asyncio.get_event_loop().time()` to get the event loop's internal clock for timing. The replacement is `asyncio.get_running_loop().time()`, which is the non-deprecated way to access the same clock from within a running async context.

**Note on `_on_failure`**: This is a **sync** method, not async. However, it is only ever called from within the async `call()` method, so `asyncio.get_running_loop()` will always find a running loop. The same applies to `_should_attempt_reset()`.

#### Instance 1: `_on_failure` (line 144)

**Before** (line 144):
```python
        self.last_failure_time = asyncio.get_event_loop().time()
```

**After** (line 144):
```python
        self.last_failure_time = asyncio.get_running_loop().time()
```

#### Instance 2: `_should_attempt_reset` (line 155)

**Before** (line 155):
```python
        return (asyncio.get_event_loop().time() - self.last_failure_time) >= self.recovery_timeout
```

**After** (line 155):
```python
        return (asyncio.get_running_loop().time() - self.last_failure_time) >= self.recovery_timeout
```

#### Instance 3: `RateLimiter.acquire` (line 168)

**Before** (line 168):
```python
        now = asyncio.get_event_loop().time()
```

**After** (line 168):
```python
        now = asyncio.get_running_loop().time()
```

---

### Change 4: Remove unused `validate_prompt_version()` from `shit/llm/prompts.py`

**File**: `/Users/chris/Projects/shitpost-alpha/shit/llm/prompts.py`

**What and why**: The `validate_prompt_version()` function at lines 380-389 is never called in production code. It is not exported from `shit/llm/__init__.py`. Removing it eliminates dead code. The associated tests must also be removed (see Test Plan section).

**Before** (lines 380-389):
```python
def validate_prompt_version(version: str) -> bool:
    """Validate prompt version for consistency.

    Args:
        version: Version string to validate

    Returns:
        True if version is valid
    """
    return version == PROMPT_VERSION
```

**After**: Delete these 10 lines entirely (lines 380-389). The `get_prompt_metadata()` function that follows should move up accordingly.

---

### Change 5: Remove unused `Decimal` import from `shit/market_data/models.py`

**File**: `/Users/chris/Projects/shitpost-alpha/shit/market_data/models.py`

**Before** (lines 6-12):
```python
from datetime import datetime, date
from typing import Optional
from sqlalchemy import Column, String, Date, DateTime, Float, BigInteger, ForeignKey, Integer, Boolean, Text
from sqlalchemy.orm import relationship
from decimal import Decimal

from shit.db.data_models import Base, TimestampMixin, IDMixin
```

**After** (lines 6-11):
```python
from datetime import datetime, date
from typing import Optional
from sqlalchemy import Column, String, Date, DateTime, Float, BigInteger, ForeignKey, Integer, Boolean, Text
from sqlalchemy.orm import relationship

from shit.db.data_models import Base, TimestampMixin, IDMixin
```

---

## Test Plan

### Tests to modify

#### 1. Update S3 Data Lake tests to mock `asyncio.to_thread` instead of `asyncio.get_event_loop`

**File**: `/Users/chris/Projects/shitpost-alpha/shit_tests/shit/s3/test_s3_data_lake.py`

The existing tests heavily mock `asyncio.get_event_loop` and `loop.run_in_executor`. After the source changes, these mocks will target the wrong function. Every test that patches `asyncio.get_event_loop` must be updated to patch `asyncio.to_thread` instead.

**Affected tests** (12 tests total):
- `test_store_raw_data_success`, `test_store_raw_data_invalid_timestamp`, `test_store_raw_data_timeout`, `test_store_raw_data_upload_error`
- `test_check_object_exists_true`, `test_check_object_exists_false`, `test_check_object_exists_other_error`
- `test_get_raw_data_success`, `test_get_raw_data_not_found`, `test_get_raw_data_other_error`
- `test_store_raw_data_with_z_timestamp`

**Pattern for `store_raw_data` tests** (tests that also mock `asyncio.wait_for`):

**Before**:
```python
        with patch('asyncio.wait_for') as mock_wait_for, \
             patch('asyncio.get_event_loop') as mock_get_loop:
            mock_wait_for.return_value = None
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            mock_loop.run_in_executor.return_value = None
```

**After**:
```python
        with patch('asyncio.wait_for') as mock_wait_for, \
             patch('asyncio.to_thread') as mock_to_thread:
            mock_wait_for.return_value = None
            mock_to_thread.return_value = None
```

**Pattern for `check_object_exists` and `get_raw_data` tests** (no `wait_for` wrapping):

**Before**:
```python
        with patch('asyncio.get_event_loop') as mock_get_loop:
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            mock_loop.run_in_executor = AsyncMock(return_value=None)
```

**After**:
```python
        with patch('asyncio.to_thread', new_callable=AsyncMock, return_value=None) as mock_to_thread:
```

**Pattern for error tests** (side_effect on the mock):

**Before**:
```python
            mock_loop.run_in_executor = AsyncMock(side_effect=mock_error)
```

**After**:
```python
        with patch('asyncio.to_thread', new_callable=AsyncMock, side_effect=mock_error):
```

Apply the same transformation pattern to all 12 listed tests individually.

#### 2. Update error handling tests

**File**: `/Users/chris/Projects/shitpost-alpha/shit_tests/shit/utils/test_error_handling.py`

**Test: `test_should_attempt_reset_within_timeout`** (line 531):
```python
# Before:
cb.last_failure_time = asyncio.get_event_loop().time()
# After:
cb.last_failure_time = asyncio.get_running_loop().time()
```

**Test: `test_should_attempt_reset_after_timeout`** (lines 538-539):
```python
# Before:
loop = asyncio.get_event_loop()
# After:
loop = asyncio.get_running_loop()
```

#### 3. Remove `validate_prompt_version` tests

**File**: `/Users/chris/Projects/shitpost-alpha/shit_tests/shit/llm/test_prompts.py`

- Remove `validate_prompt_version` from the import list (line 17)
- Delete both `test_validate_prompt_version_valid` and `test_validate_prompt_version_invalid` test methods (lines 278-288)

### Coverage expectations

Test count will decrease by 2 (the removed `validate_prompt_version` tests). All other tests remain, with updated mocking targets.

---

## Documentation Updates

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Fixed
- **Asyncio deprecation warnings** — Replaced 5 instances of deprecated `asyncio.get_event_loop()` with modern alternatives (`asyncio.to_thread()` and `asyncio.get_running_loop()`) for Python 3.13 compatibility

### Removed
- **Dead code cleanup** — Removed unused `validate_prompt_version()` function from prompt module and unused `Decimal` import from market data models
```

---

## Stress Testing & Edge Cases

### Edge case: No running event loop

`asyncio.get_running_loop()` raises `RuntimeError` if called outside an async context. This is **intentionally correct behavior** — these functions should only ever be called from within a running event loop. The old `get_event_loop()` would silently create a new loop in this case, which would mask bugs.

### Edge case: `asyncio.to_thread()` executor behavior

`asyncio.to_thread()` uses the default thread pool executor. Unlike the previous code in `shitpost_analyzer.py` which created a dedicated `ThreadPoolExecutor(max_workers=1)`, the default executor is shared. This is safe because the `auto_backfill_prediction` function is called infrequently (once per prediction analysis) and the default executor has sufficient capacity.

### Edge case: `asyncio.wait_for` + `asyncio.to_thread` compatibility

In `s3_data_lake.py`'s `store_raw_data`, the `asyncio.wait_for(asyncio.to_thread(...), timeout=...)` pattern works correctly because `asyncio.to_thread()` returns a coroutine. The timeout behavior is identical to the previous pattern.

---

## Verification Checklist

- [ ] Run full test suite: `./venv/bin/python -m pytest -v`
- [ ] Run linting: `./venv/bin/python -m ruff check .`
- [ ] Run formatting: `./venv/bin/python -m ruff format .`
- [ ] Verify no remaining `get_event_loop` calls: `grep -rn "get_event_loop" shitpost_ai/ shit/ --include="*.py" | grep -v __pycache__ | grep -v test`
- [ ] Verify `concurrent.futures` removed: `grep -n "concurrent.futures" shitpost_ai/shitpost_analyzer.py`
- [ ] Verify `Decimal` import removed: `grep -n "from decimal import Decimal" shit/market_data/models.py`
- [ ] Verify `validate_prompt_version` fully removed: `grep -rn "validate_prompt_version" shit/ shitpost_ai/ --include="*.py" | grep -v __pycache__`

---

## What NOT To Do

1. **Do NOT replace `asyncio.get_running_loop().time()` with `time.monotonic()` or `time.perf_counter()`**. The event loop's `.time()` method is the canonical clock for asyncio timing.

2. **Do NOT remove the `PROMPT_VERSION` constant** from `prompts.py`. It is still used by `get_prompt_metadata()`. Only the `validate_prompt_version()` function is dead code.

3. **Do NOT remove the other "test-only" prompt functions** (`get_sector_analysis_prompt`, `get_crypto_analysis_prompt`, `get_alert_prompt`, `get_custom_prompt`). These are tested and may represent future features. Out of scope for this PR.

4. **Do NOT change the `asyncio.wait_for()` wrapping** in `store_raw_data`. The timeout behavior is production-critical.

5. **Do NOT use `asyncio.get_running_loop().run_in_executor()`** as the replacement in `s3_data_lake.py`. `asyncio.to_thread()` is the cleaner, higher-level API.

6. **Do NOT create any new test files**. All test changes are modifications to existing files.

7. **Do NOT batch the S3 test updates as search-and-replace**. Each test has slightly different mock setup. Update each individually.
