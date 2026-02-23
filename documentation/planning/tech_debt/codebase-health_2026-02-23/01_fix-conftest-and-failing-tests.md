# Phase 01: Fix pytest conftest blocker and 10 failing tests

**Status:** 🔧 IN PROGRESS
**Started:** 2026-02-23

| Field | Value |
|-------|-------|
| **PR Title** | fix: resolve conftest pytest_plugins blocker, delete stale bypass tests, modernize settings config |
| **Risk Level** | Low |
| **Effort** | Low (~1-2 hours) |
| **Files Created** | 1 |
| **Files Modified** | 3 |
| **Files Deleted** | 0 |

## Context

The test suite has three distinct problems that erode CI trust and block other development:

1. **pytest_plugins blocker**: `shit_tests/conftest.py` line 36 declares `pytest_plugins = ['pytest_asyncio']`. In pytest 8.x, this is forbidden in non-root-level conftest files. This blocks the entire test suite from running with bare `pytest` from the project root.

2. **5 failing bypass reason tests**: `shit_tests/shitvault/test_prediction_operations.py` lines 434-468 contain 5 tests that call `prediction_ops._get_bypass_reason(shitpost_data)`. This method no longer exists on `PredictionOperations`. The bypass logic was refactored into `BypassService` (in `shit/content/bypass_service.py`), which already has comprehensive tests at `shit_tests/content/test_bypass_service.py`.

3. **Pydantic V2 deprecation warnings in Settings**: `shit/config/shitpost_settings.py` uses the legacy `class Config` inner class pattern and the deprecated `env=` parameter on every `Field()` call. The correct pattern is `model_config = SettingsConfigDict(...)`.

This phase is the foundation for all subsequent codebase-health work.

## Dependencies

- **Depends on**: None (this is the foundation phase)
- **Unlocks**: Phases 02-08

## Detailed Implementation Plan

### Step 1: Create root-level conftest.py with pytest_plugins

**File to create**: `/Users/chris/Projects/shitpost-alpha/conftest.py`

```python
"""
Root-level conftest.py for pytest plugin registration.

pytest_plugins must be declared in a root-level conftest.py (not in subdirectories).
This requirement was enforced starting in pytest 8.x.
"""

pytest_plugins = ['pytest_asyncio']
```

### Step 2: Remove pytest_plugins from shit_tests/conftest.py

**File to modify**: `/Users/chris/Projects/shitpost-alpha/shit_tests/conftest.py`

**Current code at lines 35-36:**
```python
# Configure pytest for async tests
pytest_plugins = ['pytest_asyncio']
```

**Replace with:**
```python
# NOTE: pytest_plugins declaration moved to root-level conftest.py
# (pytest 8.x requires pytest_plugins in root conftest only)
```

No other lines change. The `import pytest_asyncio` on line 14 must remain — it is used by `@pytest_asyncio.fixture` decorators.

### Step 3: Delete the 5 stale _get_bypass_reason tests

**File to modify**: `/Users/chris/Projects/shitpost-alpha/shit_tests/shitvault/test_prediction_operations.py`

Delete lines 434-468 — the 5 tests calling `prediction_ops._get_bypass_reason()`:
- `test_get_bypass_reason_no_text` (line 434)
- `test_get_bypass_reason_short_text` (line 440)
- `test_get_bypass_reason_test_content` (line 446)
- `test_get_bypass_reason_insufficient_words` (line 455)
- `test_get_bypass_reason_fallback` (line 463)

**Why delete instead of rewrite**: Equivalent coverage already exists in `shit_tests/content/test_bypass_service.py` (226 lines, 15+ test cases).

### Step 4: Modernize Settings class to use ConfigDict pattern

**File to modify**: `/Users/chris/Projects/shitpost-alpha/shit/config/shitpost_settings.py`

#### Part 4a: Update imports

**Current lines 8-9:**
```python
from pydantic_settings import BaseSettings
from pydantic import Field
```

**Replace with:**
```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
```

#### Part 4b: Replace inner Config class with model_config

**Current code at lines 141-143:**
```python
    class Config:
        env_file = ".env"
        case_sensitive = False
```

**Replace with:**
```python
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
    )
```

#### Part 4c: Remove deprecated `env=` parameter from all Field() calls

Every `Field()` call with `env=` must have that parameter removed. Field names already match env var names (all uppercase), so the explicit `env=` is redundant when `case_sensitive=False`.

For single-line fields, remove `env="..."`:
```python
# Before:
OPENAI_API_KEY: str = Field(default=None, env="OPENAI_API_KEY")
# After:
OPENAI_API_KEY: str = Field(default=None)
```

For multi-line fields, collapse after removing `env=`:
```python
# Before:
EMAIL_FROM_ADDRESS: str = Field(
    default="alerts@shitpostalpha.com",
    env="EMAIL_FROM_ADDRESS",
)
# After:
EMAIL_FROM_ADDRESS: str = Field(default="alerts@shitpostalpha.com")
```

Apply this to ALL Field() calls in lines 27-139 (~40 fields total).

## Test Plan

### Existing tests to verify (no modifications needed)
All 648+ existing settings tests in `test_shitpost_settings.py` should pass unchanged. The Settings class API is not changing — only its internal configuration mechanism.

### Tests that will be removed
The 5 stale tests in `test_prediction_operations.py` (already covered by `test_bypass_service.py`).

### No new tests needed
1. Root conftest.py change is configuration, not logic
2. Deleted tests are covered by existing BypassService tests
3. Settings ConfigDict migration preserves identical behavior

### Manual verification
```bash
# 1. Verify pytest collection works
./venv/bin/python -m pytest --collect-only 2>&1 | head -20

# 2. Run full test suite
./venv/bin/python -m pytest

# 3. Verify no pydantic deprecation warnings
./venv/bin/python -m pytest -W error::DeprecationWarning shit_tests/shit/config/

# 4. Verify prediction ops tests (5 fewer)
./venv/bin/python -m pytest shit_tests/shitvault/test_prediction_operations.py -v
```

## Verification Checklist

- [ ] Root-level `conftest.py` exists at project root
- [ ] `pytest_plugins` is in root conftest.py, NOT in `shit_tests/conftest.py`
- [ ] `pytest --collect-only` succeeds without errors
- [ ] `test_get_bypass_reason_*` tests no longer exist
- [ ] Settings uses `model_config = SettingsConfigDict(...)` (no `class Config`)
- [ ] No `env=` parameters remain in any `Field()` call
- [ ] Full test suite passes
- [ ] No pydantic deprecation warnings
- [ ] CHANGELOG.md updated

## What NOT To Do

1. **Do NOT move `pytest.ini`** from `shit_tests/` to project root — different issue, would break rootdir discovery.
2. **Do NOT rewrite the 5 stale tests** to call BypassService — they'd duplicate existing comprehensive tests.
3. **Do NOT add `validation_alias`** to Field() calls — redundant with `case_sensitive=False`.
4. **Do NOT change the `load_dotenv` call** at lines 14-20 — it coexists safely with `env_file`.
5. **Do NOT remove `import pytest_asyncio`** from `shit_tests/conftest.py` line 14 — it's used by fixture decorators.
6. **Do NOT add `env_prefix`** to SettingsConfigDict — no prefix convention in this project.
