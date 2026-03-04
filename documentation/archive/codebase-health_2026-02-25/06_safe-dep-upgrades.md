# Phase 06: Safe Dependency Upgrades

| Field | Value |
|-------|-------|
| **PR Title** | chore: upgrade certifi, urllib3, anthropic, sqlalchemy, boto3, pytest and test tooling |
| **Risk Level** | Low |
| **Effort** | Low (~3 hours) |
| **Files Created** | 0 |
| **Files Modified** | 3 (`requirements.txt`, `shit_tests/requirements-test.txt`, `shit_tests/conftest.py`) |
| **Files Deleted** | 0 |

## Context

The project has 10+ dependencies that are minor or patch versions behind their current releases. While none are critically broken, keeping dependencies current reduces the attack surface (especially `certifi` and `urllib3` which handle SSL/TLS), ensures compatibility with the latest Python 3.13 features, and prevents "dependency drift" where a large gap accumulates and makes future upgrades painful.

This phase upgrades dependencies in a tiered order from security-critical to test-only tooling, running the full test suite after each tier to isolate any breakage. The Anthropic SDK upgrade (0.64 to 0.83) spans 20 minor versions but uses the same `AsyncAnthropic` / `messages.create()` API surface the project depends on, making it safe. The pytest-asyncio upgrade from 0.x to 1.x is the highest-risk item in this phase because it removes the deprecated `event_loop` fixture that `shit_tests/conftest.py` currently defines.

OpenAI SDK, Dash, and pandas major upgrades are explicitly excluded (Phases 07 and 08).

## Dependencies

- **Depends on**: None (this phase modifies only `requirements.txt`, `shit_tests/requirements-test.txt`, and `shit_tests/conftest.py` -- disjoint from all other Wave 1 phases)
- **Unlocks**: Phase 07 (OpenAI SDK v2 Migration) -- Phase 07 needs a clean, up-to-date dependency baseline before introducing the OpenAI v2 SDK

## Detailed Implementation Plan

All changes follow a strict pattern: update one tier at a time, install, run full test suite, only proceed if green. If any tier causes failures, investigate and either fix the compatibility issue or pin that package at the current version and document why.

### Step 1: Tier 1 -- Security Packages (certifi, urllib3)

**File to modify**: `/Users/chris/Projects/shitpost-alpha/requirements.txt`

These are transitive dependencies (pulled in by `requests`, `boto3`, etc.) but pinning them ensures we get the latest SSL certificates and HTTP security fixes.

**Current state** (line-by-line -- these packages are not explicitly listed in `requirements.txt`):

`requirements.txt` does not pin `certifi` or `urllib3` at all. They are pulled in transitively by `requests>=2.31.0` and `boto3>=1.26.0`.

**Action**: Add explicit pins at the end of the `# HTTP and web scraping` section (after line 9):

```python
# requirements.txt lines 7-11 (before)
# HTTP and web scraping
aiohttp>=3.8.0
requests>=2.31.0
```

```python
# requirements.txt lines 7-13 (after)
# HTTP and web scraping
aiohttp>=3.8.0
requests>=2.31.0
certifi>=2026.1.4
urllib3>=2.6.3
```

**Why pin explicitly**: Transitive dependency resolution may install older cached versions. Explicit floor pins ensure `pip install -r requirements.txt` always fetches at least these security-patched versions.

**Verification**:
```bash
./venv/bin/pip install -r requirements.txt
./venv/bin/python -c "import certifi; print(certifi.__version__)"
./venv/bin/python -c "import urllib3; print(urllib3.__version__)"
./venv/bin/python -m pytest
```

### Step 2: Tier 2 -- Anthropic SDK Update

**File to modify**: `/Users/chris/Projects/shitpost-alpha/requirements.txt`

**Current code at line 15:**
```python
anthropic>=0.40.0
```

**Replace with:**
```python
anthropic>=0.83.0
```

**Why this is safe**: The project uses exactly two API surface points from the Anthropic SDK:

1. `anthropic.AsyncAnthropic(api_key=self.api_key)` -- constructor at `/Users/chris/Projects/shitpost-alpha/shit/llm/llm_client.py:53`
2. `self.client.messages.create(model=..., max_tokens=..., temperature=..., system=..., messages=[...])` -- at `/Users/chris/Projects/shitpost-alpha/shit/llm/llm_client.py:183-194`

Both of these are the core stable API of the Anthropic SDK. The `messages.create()` signature has remained backward-compatible across all 0.4x-0.8x releases. New features (tool use, prompt caching, batch API) are additive and do not affect existing callers.

**Test files that mock the Anthropic SDK** (verify these still work):
- `/Users/chris/Projects/shitpost-alpha/shit_tests/conftest.py:407` -- `patch('anthropic.Anthropic')` (note: this patches the sync client, not `AsyncAnthropic`; the mock is unused by real code but must still resolve)
- `/Users/chris/Projects/shitpost-alpha/shit_tests/shit/llm/test_llm_client.py:74` -- `patch('anthropic.AsyncAnthropic')`
- `/Users/chris/Projects/shitpost-alpha/shit_tests/shit/llm/test_llm_client.py:320` -- `patch('anthropic.AsyncAnthropic')`
- `/Users/chris/Projects/shitpost-alpha/shit_tests/shit/llm/test_llm_client.py:535` -- `patch('anthropic.AsyncAnthropic')`

Since these all patch at the module import level (not internal SDK methods), they will continue to work regardless of SDK internals.

**Verification**:
```bash
./venv/bin/pip install -r requirements.txt
./venv/bin/python -c "import anthropic; print(anthropic.__version__)"
./venv/bin/python -m pytest shit_tests/shit/llm/
```

### Step 3: Tier 3 -- Framework Patches (SQLAlchemy, boto3, botocore)

**File to modify**: `/Users/chris/Projects/shitpost-alpha/requirements.txt`

**Current code at line 12 and line 19:**
```python
# AWS S3
boto3>=1.26.0
```
```python
sqlalchemy[asyncio]>=2.0.0
```

**Replace with:**
```python
# AWS S3
boto3>=1.42.0
```
```python
sqlalchemy[asyncio]>=2.0.47
```

**Why these specific versions**:
- `boto3>=1.42.0` -- picks up latest 1.42.x patch series. `botocore` is automatically upgraded as a boto3 dependency (they are version-locked by AWS). The project uses only `boto3.client('s3', ...)` and `boto3.resource('s3', ...)` (see `/Users/chris/Projects/shitpost-alpha/shit/s3/s3_client.py:52-65`), which are the most stable AWS SDK APIs.
- `sqlalchemy[asyncio]>=2.0.47` -- stays within the 2.0.x line (2.1.x is pre-release). The project uses standard ORM patterns: `create_async_engine`, `AsyncSession`, `sessionmaker`, `Base.metadata.create_all`. All 2.0.x patches are backward compatible.

**Note on botocore**: Do NOT add a separate `botocore>=X.Y.Z` line. boto3 pins its own botocore dependency internally. Adding a separate pin can cause version conflicts. Let boto3 manage botocore.

**Verification**:
```bash
./venv/bin/pip install -r requirements.txt
./venv/bin/python -c "import boto3; print(boto3.__version__)"
./venv/bin/python -c "import sqlalchemy; print(sqlalchemy.__version__)"
./venv/bin/python -m pytest shit_tests/shit/s3/ shit_tests/shit/db/ shit_tests/shitvault/
```

### Step 4: Tier 4 -- Testing Tools (pytest, pytest-cov, pytest-asyncio, vcrpy)

This is the most complex tier because `pytest-asyncio` 1.x removes the deprecated `event_loop` fixture that the project currently defines. This requires a code change in `shit_tests/conftest.py`.

#### Step 4a: Update pytest and pytest-cov versions

**File to modify**: `/Users/chris/Projects/shitpost-alpha/requirements.txt`

**Current code at lines 24-26:**
```python
# Testing
pytest>=7.0.0
pytest-asyncio>=0.21.0
pytest-cov>=4.0.0
vcrpy>=6.0.0
```

**Replace with:**
```python
# Testing
pytest>=8.4.0
pytest-asyncio>=0.25.0
pytest-cov>=6.2.0
vcrpy>=7.0.0
```

**IMPORTANT**: Do NOT upgrade pytest-asyncio to 1.x yet. The 0.25.x series is the last 0.x release and includes deprecation warnings for the `event_loop` fixture but does not remove it. This gives us a safe stepping stone. Similarly, stay on pytest 8.x rather than jumping to 9.x, since the project's `pytest.ini` has `minversion = 7.0` and some ecosystem plugins may not yet support pytest 9.

**Why NOT pytest 9.x**: pytest 9.0 removed the private `config.inicfg` attribute and changed terminal progress behavior. Several plugins in the ecosystem (including potential interactions with the project's `pytest-postgresql`, `pytest-html`, etc. in `shit_tests/requirements-test.txt`) may not yet be compatible. Staying on 8.x is safer for this phase.

**Why NOT pytest-asyncio 1.x**: Version 1.x removes the `event_loop` fixture entirely. The project defines a session-scoped `event_loop` fixture at `/Users/chris/Projects/shitpost-alpha/shit_tests/conftest.py:39-44`. Migrating to 1.x requires removing this fixture and configuring `loop_scope` settings, which is a behavioral change that should be tested carefully. Keep this for a future phase or tackle it in Step 4c if time permits and the 0.25.x deprecation warnings indicate how to proceed.

**Why NOT vcrpy 8.x**: VCR.py is listed in `requirements.txt` line 27 (`vcrpy>=6.0.0`) but is **not actually imported or used anywhere in the codebase** (confirmed by grep -- zero import hits in `shit_tests/` or source code). The 7.0 to 8.0 jump drops Python 3.7 support and changes cassette persister error handling. Since we do not use VCR.py, upgrading to 7.x is safe (it is already installed as a transitive resolution), and 8.x would also be safe but unnecessary. Pinning to `>=7.0.0` is a conservative choice.

**Verification**:
```bash
./venv/bin/pip install -r requirements.txt
./venv/bin/python -m pytest --version
./venv/bin/python -m pytest
```

#### Step 4b: Update shit_tests/requirements-test.txt pins

**File to modify**: `/Users/chris/Projects/shitpost-alpha/shit_tests/requirements-test.txt`

**Current code at lines 3-6:**
```python
# Core testing framework
pytest>=7.0.0
pytest-asyncio>=0.21.0
pytest-cov>=4.0.0
```

**Replace with:**
```python
# Core testing framework
pytest>=8.4.0
pytest-asyncio>=0.25.0
pytest-cov>=6.2.0
```

**Current code at line 15:**
```python
vcrpy>=6.0.0  # For recording HTTP interactions
```

**Replace with:**
```python
vcrpy>=7.0.0  # For recording HTTP interactions
```

This file mirrors the main `requirements.txt` pins. It is not used by the production install but is referenced by documentation and CI tooling.

#### Step 4c: (Conditional) Address pytest-asyncio deprecation warnings

After running the test suite with pytest-asyncio 0.25.x, check for deprecation warnings about the `event_loop` fixture:

```bash
./venv/bin/python -m pytest -W default::DeprecationWarning 2>&1 | grep -i "event_loop"
```

If warnings appear (expected), prepare the conftest.py for eventual pytest-asyncio 1.x migration by adding the `asyncio_default_fixture_loop_scope` configuration. This step is **optional for this phase** -- the warnings are informational, not failures.

**File to modify** (if pursuing): `/Users/chris/Projects/shitpost-alpha/shit_tests/pytest.ini`

**Current code at line 40:**
```ini
asyncio_mode = auto
```

**Add after line 40:**
```ini
asyncio_default_fixture_loop_scope = session
```

This tells pytest-asyncio 0.25+ that all async fixtures default to session scope for their event loop, matching the behavior of the current `event_loop` fixture at `/Users/chris/Projects/shitpost-alpha/shit_tests/conftest.py:39-44` (which is `scope="session"`).

**Note**: Do NOT remove the `event_loop` fixture from conftest.py in this phase. That is a pytest-asyncio 1.x migration step for a future phase.

### Step 5: Update pytest.ini minversion

**File to modify**: `/Users/chris/Projects/shitpost-alpha/shit_tests/pytest.ini`

**Current code at line 49:**
```ini
minversion = 7.0
```

**Replace with:**
```ini
minversion = 8.4
```

This prevents accidental use of older pytest versions that would not be compatible with the new test configuration.

### Step 6: Final Full Requirements File State

After all tiers, the relevant sections of `/Users/chris/Projects/shitpost-alpha/requirements.txt` should look like:

```python
# Core dependencies
pydantic>=2.0.0
sqlalchemy[asyncio]>=2.0.47
aiosqlite>=0.19.0
asyncio-mqtt>=0.16.0

# HTTP and web scraping
aiohttp>=3.8.0
requests>=2.31.0
certifi>=2026.1.4
urllib3>=2.6.3

# AWS S3
boto3>=1.42.0

# LLM providers
openai>=1.0.0
anthropic>=0.83.0

# Database
psycopg[binary]>=3.2.0  # For PostgreSQL async support
psycopg2-binary>=2.9.0  # For PostgreSQL sync support (dashboard)
asyncpg>=0.29.0  # For PostgreSQL async support (dashboard)

# Testing
pytest>=8.4.0
pytest-asyncio>=0.25.0
pytest-cov>=6.2.0
vcrpy>=7.0.0

# Development and utilities
python-dotenv>=1.0.0
pydantic-settings>=2.0.0
click>=8.1.0
rich>=13.0.0

# SMS/Alerting (Phase 2)
twilio>=8.0.0

# Job scheduling (Phase 2)
apscheduler>=3.10.0

# Logging and monitoring
structlog>=23.0.0

# Data processing
pandas>=2.0.0
numpy>=1.24.0

# Market data
yfinance>=0.2.48

# Dashboard dependencies
dash>=2.14.0
plotly>=5.15.0
dash-bootstrap-components>=1.5.0

# Async utilities
asyncio-throttle>=1.0.0
```

## Test Plan

### No new tests needed

This phase only changes dependency versions and a configuration value. The entire existing test suite serves as the verification mechanism.

### Existing tests as verification gates

Each tier must pass the full test suite before proceeding:

| Tier | Test Command | Expected Result |
|------|-------------|-----------------|
| 1 (Security) | `./venv/bin/python -m pytest` | All passing (no code changes) |
| 2 (Anthropic) | `./venv/bin/python -m pytest shit_tests/shit/llm/` | All passing (same API surface) |
| 3 (Framework) | `./venv/bin/python -m pytest shit_tests/shit/s3/ shit_tests/shit/db/ shit_tests/shitvault/` | All passing (patch-level changes) |
| 4 (Testing tools) | `./venv/bin/python -m pytest` | All passing (may show deprecation warnings) |
| Final | `./venv/bin/python -m pytest` | Full green suite |

### Manual verification steps

```bash
# 1. Verify all packages installed at expected versions
./venv/bin/pip freeze | grep -E "certifi|urllib3|anthropic|sqlalchemy|boto3|pytest"

# 2. Verify no version conflicts
./venv/bin/pip check

# 3. Verify import works for each upgraded package
./venv/bin/python -c "import certifi, urllib3, anthropic, sqlalchemy, boto3, pytest; print('All imports OK')"

# 4. Check for deprecation warnings
./venv/bin/python -m pytest -W default::DeprecationWarning 2>&1 | tail -20

# 5. Run full test suite
./venv/bin/python -m pytest
```

## Documentation Updates

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Changed
- **Dependency upgrades** — Updated 8 dependencies to latest compatible versions:
  - Security: `certifi` >=2026.1.4, `urllib3` >=2.6.3
  - SDK: `anthropic` >=0.83.0 (from >=0.40.0)
  - Framework: `sqlalchemy` >=2.0.47, `boto3` >=1.42.0
  - Testing: `pytest` >=8.4.0, `pytest-cov` >=6.2.0, `pytest-asyncio` >=0.25.0, `vcrpy` >=7.0.0
```

### No README changes needed

The README does not reference specific dependency versions.

## Stress Testing and Edge Cases

### Edge Case 1: boto3/botocore version lock conflict
boto3 and botocore are version-locked by AWS. If any other dependency (e.g., `moto` in `requirements-test.txt`) pins an incompatible botocore version, `pip install` will fail with a version conflict. **Mitigation**: Run `./venv/bin/pip check` after install. If a conflict appears, remove the explicit boto3 floor pin and let pip resolve it naturally.

### Edge Case 2: pytest-asyncio deprecation warnings flooding test output
pytest-asyncio 0.25.x emits deprecation warnings for the `event_loop` fixture. The project's `pytest.ini` has `filterwarnings = ignore::DeprecationWarning` (line 53), so these will be suppressed by default. **Mitigation**: Already handled by existing config. If explicitly testing with `-W default::DeprecationWarning`, expect these warnings -- they are informational.

### Edge Case 3: SQLAlchemy 2.0.47 deprecation of legacy patterns
SQLAlchemy patch releases occasionally add new deprecation warnings for patterns that will be removed in 2.1. The project uses standard ORM patterns, but check for new warnings. **Mitigation**: Run `./venv/bin/python -m pytest -W default::DeprecationWarning shit_tests/shit/db/` and review any new SQLAlchemy warnings.

### Edge Case 4: Anthropic SDK adding required parameters
In rare cases, SDK minor versions add new required parameters to existing methods. The `messages.create()` call uses only `model`, `max_tokens`, `temperature`, `system`, and `messages` -- all of which are core stable parameters. **Mitigation**: The targeted LLM test suite (`shit_tests/shit/llm/`) exercises this API surface with mocks.

## Verification Checklist

- [ ] `certifi` version >= 2026.1.4 (`./venv/bin/pip show certifi`)
- [ ] `urllib3` version >= 2.6.3 (`./venv/bin/pip show urllib3`)
- [ ] `anthropic` version >= 0.83.0 (`./venv/bin/pip show anthropic`)
- [ ] `sqlalchemy` version >= 2.0.47 (`./venv/bin/pip show sqlalchemy`)
- [ ] `boto3` version >= 1.42.0 (`./venv/bin/pip show boto3`)
- [ ] `pytest` version >= 8.4.0 (`./venv/bin/python -m pytest --version`)
- [ ] `pytest-cov` version >= 6.2.0 (`./venv/bin/pip show pytest-cov`)
- [ ] `pytest-asyncio` version >= 0.25.0 (`./venv/bin/pip show pytest-asyncio`)
- [ ] `vcrpy` version >= 7.0.0 (`./venv/bin/pip show vcrpy`)
- [ ] `./venv/bin/pip check` reports no conflicts
- [ ] All imports succeed: `./venv/bin/python -c "import certifi, urllib3, anthropic, sqlalchemy, boto3, pytest"`
- [ ] Full test suite passes: `./venv/bin/python -m pytest`
- [ ] `requirements.txt` has all updated pins
- [ ] `shit_tests/requirements-test.txt` has matching pins for test packages
- [ ] `shit_tests/pytest.ini` minversion updated to 8.4
- [ ] CHANGELOG.md updated

## What NOT To Do

1. **Do NOT upgrade `openai`** -- that is Phase 07 (OpenAI SDK v2 Migration), which depends on this phase completing first.
2. **Do NOT upgrade `dash`** -- that is Phase 08 (Dash 4 Migration), which has separate breaking changes.
3. **Do NOT upgrade `pandas` to 3.x** -- major version with breaking API changes to DataFrame operations. Out of scope.
4. **Do NOT upgrade `numpy` to 2.x** -- major version with breaking ABI changes. Out of scope.
5. **Do NOT upgrade `pytest-asyncio` to 1.x** -- it removes the `event_loop` fixture at `/Users/chris/Projects/shitpost-alpha/shit_tests/conftest.py:39-44`. Stay on 0.25.x which shows deprecation warnings but does not break.
6. **Do NOT upgrade `pytest` to 9.x** -- plugin ecosystem compatibility is uncertain. Stay on 8.x.
7. **Do NOT remove the `event_loop` fixture from `shit_tests/conftest.py`** -- it is still needed by pytest-asyncio 0.25.x. Removal is a future task when upgrading to 1.x.
8. **Do NOT add a separate `botocore>=X.Y.Z` pin** -- boto3 manages its own botocore dependency. Adding a separate pin risks version conflicts.
9. **Do NOT upgrade all packages at once** -- follow the tiered approach so breakage can be isolated to the specific package that caused it.
10. **Do NOT remove `vcrpy` from requirements.txt** even though it is unused. It may be referenced by CI or future test plans. Leave removal for a dedicated cleanup phase.

---

### Critical Files for Implementation
- `/Users/chris/Projects/shitpost-alpha/requirements.txt` - Primary file: all dependency version pins are updated here
- `/Users/chris/Projects/shitpost-alpha/shit_tests/requirements-test.txt` - Secondary file: test dependency pins must stay in sync
- `/Users/chris/Projects/shitpost-alpha/shit_tests/pytest.ini` - Config update: minversion bump and optional asyncio_default_fixture_loop_scope
- `/Users/chris/Projects/shitpost-alpha/shit_tests/conftest.py` - Reference: contains the event_loop fixture (do NOT modify in this phase)
- `/Users/chris/Projects/shitpost-alpha/shit/llm/llm_client.py` - Reference: Anthropic SDK usage surface to verify after upgrade
