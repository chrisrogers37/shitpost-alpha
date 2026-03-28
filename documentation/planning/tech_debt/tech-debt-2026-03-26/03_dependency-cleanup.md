# Phase 03: Remove Unused Dependencies, Bump Safe Minors

## Header

| Field | Value |
|-------|-------|
| **PR Title** | `chore: remove unused dependencies, bump safe minors` |
| **Risk** | Low |
| **Effort** | Low |
| **Files Modified** | 1 (`requirements.txt`) |
| **Files Created** | 0 |
| **Files Deleted** | 0 |

---

## Context

The `requirements.txt` file has accumulated four completely unused packages (`asyncio-mqtt`, `apscheduler`, `structlog`, `asyncio-throttle`) that are installed on every Railway deploy and in every developer environment for no reason. They add install time, increase the attack surface, and confuse new contributors who may assume they are in use.

Additionally, several safe minor version bumps are available (`sqlalchemy`, `psycopg`, `click`, `rich`) that should be taken now. The file also has misleading "Phase 2" section labels from early project planning that no longer apply -- these should be reorganized for clarity.

This is a low-risk, low-effort PR that touches only `requirements.txt`.

---

## Dependencies

- **Depends on**: None (this phase touches only `requirements.txt` and is independent of all other phases)
- **Unlocks**: None
- **Parallel safe**: Yes -- no other phase in this session modifies `requirements.txt`

---

## Detailed Implementation Plan

### Step 1: Understand the current file

The current `requirements.txt` is at `/Users/chris/Projects/shitpost-alpha/requirements.txt` (65 lines including trailing newline).

**COMPLETE current file (before):**

```
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
openai>=2.0.0,<3.0.0
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
exchange_calendars>=4.5.0

# Dashboard dependencies
dash>=4.0.0,<5.0.0
plotly>=5.15.0
dash-bootstrap-components>=2.0.0,<3.0.0

# Async utilities
asyncio-throttle>=1.0.0

# FastAPI web server (new React frontend API)
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
```

### Step 2: Apply all changes

The following changes are applied simultaneously in a single edit:

1. **Remove `asyncio-mqtt>=0.16.0`** (line 5) -- zero imports in entire codebase.
2. **Remove `apscheduler>=3.10.0`** (line 41) -- zero imports, labeled "Phase 2" but never implemented.
3. **Remove `structlog>=23.0.0`** (line 44) -- zero imports; project uses custom `shit.logging` module.
4. **Remove `asyncio-throttle>=1.0.0`** (line 60) -- zero imports in entire codebase.
5. **Remove the misleading "Phase 2" section headers** (lines 37, 40) and the orphaned "Logging and monitoring" + "Async utilities" section headers (lines 43, 59).
6. **Move `twilio` under a new "Notifications" section** with an accurate comment explaining the lazy import.
7. **Update `psycopg2-binary` comment** to explain its actual consumer and retirement plan.
8. **Update `asyncpg` comment** -- the current comment says "For PostgreSQL async support (dashboard)" but the async driver is actually `psycopg[binary]` (the codebase uses `postgresql+psycopg://` URLs). The `asyncpg` package is referenced only in URL string cleanup in `sync_session.py:22` for backwards compatibility. Update the comment to reflect this.
9. **Bump `sqlalchemy[asyncio]`**: `>=2.0.47` to `>=2.0.48` (patch bump, no breaking changes).
10. **Bump `psycopg[binary]`**: `>=3.2.0` to `>=3.3.0` (minor bump within same major, async driver improvements).
11. **Bump `click`**: `>=8.1.0` to `>=8.3.0` (minor bump, bug fixes only).
12. **Bump `rich`**: `>=13.0.0` to `>=14.3.0` (minor bump to match installed `14.1.0`; floor should be at or near installed version).

### Step 3: Write the new file

**COMPLETE new file (after):**

```
# Core dependencies
pydantic>=2.0.0
sqlalchemy[asyncio]>=2.0.48
aiosqlite>=0.19.0

# HTTP and web scraping
aiohttp>=3.8.0
requests>=2.31.0
certifi>=2026.1.4
urllib3>=2.6.3

# AWS S3
boto3>=1.42.0

# LLM providers
openai>=2.0.0,<3.0.0
anthropic>=0.83.0

# Database
psycopg[binary]>=3.3.0  # Async PostgreSQL driver (used by shit/db/database_client.py)
psycopg2-binary>=2.9.0  # Sync PostgreSQL driver for shit/db/sync_session.py — remove when Dash UI retired
asyncpg>=0.29.0  # Legacy: only referenced in URL cleanup (sync_session.py:22), not directly imported

# Testing
pytest>=8.4.0
pytest-asyncio>=0.25.0
pytest-cov>=6.2.0
vcrpy>=7.0.0

# Development and utilities
python-dotenv>=1.0.0
pydantic-settings>=2.0.0
click>=8.3.0
rich>=14.3.0

# Notifications
twilio>=8.0.0  # Lazy import in notifications/dispatcher.py:331 for SMS delivery

# Data processing
pandas>=2.0.0
numpy>=1.24.0

# Market data
yfinance>=0.2.48
exchange_calendars>=4.5.0

# Dashboard dependencies
dash>=4.0.0,<5.0.0
plotly>=5.15.0
dash-bootstrap-components>=2.0.0,<3.0.0

# FastAPI web server (new React frontend API)
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
```

### Exact diff summary

| Line(s) in old file | Change | Reason |
|---|---|---|
| 3 | `>=2.0.47` to `>=2.0.48` | Patch bump for SQLAlchemy |
| 5 | **Deleted** `asyncio-mqtt>=0.16.0` | Zero imports in codebase |
| 21 | Comment updated, `>=3.2.0` to `>=3.3.0` | Minor bump + accurate comment |
| 22 | Comment rewritten | Explains consumer + retirement plan |
| 23 | Comment rewritten | Clarifies `asyncpg` is legacy/not directly imported |
| 34 | `>=8.1.0` to `>=8.3.0` | Minor bump for Click |
| 35 | `>=13.0.0` to `>=14.3.0` | Minor bump for Rich (matches installed) |
| 37-38 | Section renamed from "SMS/Alerting (Phase 2)" to "Notifications" | Accurate section name |
| 38 | Comment added to `twilio` | Explains lazy import location |
| 40-41 | **Deleted** `apscheduler>=3.10.0` + section header | Zero imports |
| 43-44 | **Deleted** `structlog>=23.0.0` + section header | Zero imports, project uses `shit.logging` |
| 59-60 | **Deleted** `asyncio-throttle>=1.0.0` + section header | Zero imports |

---

## Test Plan

This phase does not add or change any source code, so no new tests are needed. The verification is entirely about confirming that the remaining dependencies still install correctly and the test suite still passes.

### Existing tests to run

All existing tests -- there are no test modifications, but we need to confirm nothing breaks:

```bash
source venv/bin/activate && pytest -v
```

Or using the venv python directly:

```bash
./venv/bin/python -m pytest -v
```

### Manual verification steps

1. **Reinstall from updated requirements.txt:**
   ```bash
   pip install -r requirements.txt
   ```
   Confirm: no errors, all packages resolve.

2. **Verify removed packages are no longer required by confirming zero imports:**
   ```bash
   grep -rn "import asyncio_mqtt\|from asyncio_mqtt\|import apscheduler\|from apscheduler\|import structlog\|from structlog\|import asyncio_throttle\|from asyncio_throttle" --include="*.py" .
   ```
   Expected: zero matches (excluding `venv/` and `.claude/`).

3. **Verify twilio lazy import still works:**
   ```bash
   python -c "from twilio.rest import Client; print('twilio OK')"
   ```

4. **Run full test suite:**
   ```bash
   pytest -v
   ```
   Expected: same pass/fail counts as before (approximately 2,338 passing, 5 pre-existing config failures).

5. **Verify bumped packages install correctly:**
   ```bash
   pip install "sqlalchemy[asyncio]>=2.0.48" "psycopg[binary]>=3.3.0" "click>=8.3.0" "rich>=14.3.0"
   ```

---

## Documentation Updates

### CLAUDE.md

No changes needed. The `requirements.txt` structure is not documented in CLAUDE.md beyond general references to `pip install -r requirements.txt`.

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Removed
- **Unused dependencies** - Removed `asyncio-mqtt`, `apscheduler`, `structlog`, `asyncio-throttle` from requirements.txt (zero imports in codebase)
- **Misleading "Phase 2" labels** - Reorganized requirements.txt sections for clarity

### Changed
- **Dependency version bumps** - Bumped minimum versions for `sqlalchemy[asyncio]` (2.0.48), `psycopg[binary]` (3.3.0), `click` (8.3.0), `rich` (14.3.0)
- **Dependency comments** - Added context comments to `twilio`, `psycopg2-binary`, and `asyncpg` explaining their usage and retirement plans
```

---

## Stress Testing & Edge Cases

### Edge case: Railway build with new version floors

The bumped version floors (`>=2.0.48`, `>=3.3.0`, `>=8.3.0`, `>=14.3.0`) are all below or equal to the currently installed versions in production (sqlalchemy 2.0.47->2.0.48, psycopg 3.2.10->3.3.0 minimum, click 8.2.1->8.3.0 minimum, rich 14.1.0->14.3.0 minimum). On Railway's next deploy, `pip install` will pull the latest compatible versions, which are the same or newer than what is already running.

**Risk**: psycopg `>=3.3.0` raises the floor above the currently installed `3.2.10`. This means pip will upgrade to `3.3.x` on next install. The psycopg 3.3.x series is backwards compatible with 3.2.x (same major version, non-breaking minor). The SQLAlchemy integration (`postgresql+psycopg://`) is stable across both.

**Risk**: rich `>=14.3.0` raises the floor above the currently installed `14.1.0`. Rich 14.x is backwards compatible within the major version. Our usage is limited to CLI output formatting.

### Edge case: asyncpg as a transitive dependency

Even though `asyncpg` is not directly imported, it may be pulled in as a transitive dependency by other packages. Keeping it in `requirements.txt` with an explanatory comment is the right call -- it documents why the package exists and when it can be removed.

### Edge case: structlog as a transitive dependency

`structlog` is NOT a transitive dependency of any package in our dependency tree. It was added speculatively and never used. Safe to remove.

---

## Verification Checklist

- [ ] `requirements.txt` matches the "COMPLETE new file (after)" exactly
- [ ] `asyncio-mqtt` line is gone
- [ ] `apscheduler` line is gone
- [ ] `structlog` line is gone
- [ ] `asyncio-throttle` line is gone
- [ ] No "Phase 2" text anywhere in the file
- [ ] `twilio` has a comment referencing `notifications/dispatcher.py:331`
- [ ] `psycopg2-binary` comment mentions `sync_session.py` and Dash UI retirement
- [ ] `asyncpg` comment mentions it is legacy / not directly imported
- [ ] `sqlalchemy[asyncio]>=2.0.48` (was `>=2.0.47`)
- [ ] `psycopg[binary]>=3.3.0` (was `>=3.2.0`)
- [ ] `click>=8.3.0` (was `>=8.1.0`)
- [ ] `rich>=14.3.0` (was `>=13.0.0`)
- [ ] `pip install -r requirements.txt` succeeds with no errors
- [ ] `pytest -v` passes (same results as before)
- [ ] Zero grep hits for imports of removed packages
- [ ] CHANGELOG.md updated with Removed and Changed entries

---

## What NOT To Do

1. **Do NOT remove `twilio`**. It has a lazy import at `notifications/dispatcher.py:331`. It is a real dependency, just loaded at runtime rather than at module level. The `except ImportError` guard (line 345) means the app degrades gracefully, but the package should remain in requirements.

2. **Do NOT remove `asyncpg`**. Although it is not directly imported anywhere, it is referenced in URL cleanup logic (`sync_session.py:22`) and may be a transitive dependency expectation. The correct action is to annotate it with a comment, not remove it. A separate PR can evaluate full removal after the Dash UI is retired.

3. **Do NOT remove `psycopg2-binary`**. It is the sync PostgreSQL driver used by `shit/db/sync_session.py` for the Dash dashboard and notifications module. It will be removed when the Dash UI is retired, not before.

4. **Do NOT bump major versions**. The following upgrades are available but require their own dedicated PRs due to breaking API changes:
   - `pandas` 2.x to 3.x (breaking DataFrame API changes)
   - `pytest` 8.x to 9.x (potential test runner behavior changes)
   - `protobuf` 6.x to 7.x (breaking serialization changes)
   - `vcrpy` 7.x to 8.x (breaking cassette format changes)

5. **Do NOT reorganize the entire file**. Keep the existing section groupings intact (Core, HTTP, AWS, LLM, Database, Testing, etc.). Only rename/remove the "Phase 2" sections and the orphaned section headers for removed packages.

6. **Do NOT pin exact versions** (e.g., `==2.0.48`). The project uses `>=` minimum floor pins throughout, which is the correct pattern for an application (not a library). Maintain this convention.

7. **Do NOT add new dependencies**. This PR is strictly about cleanup and minor bumps. Any new packages belong in their own PRs.

8. **Do NOT forget to update CHANGELOG.md**. Every PR in this project requires a changelog entry per CLAUDE.md conventions.
