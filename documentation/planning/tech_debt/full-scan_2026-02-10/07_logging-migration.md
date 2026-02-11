# Plan 07: Logging Migration

**Status**: ✅ COMPLETE
**PR Title**: `refactor: migrate remaining modules to centralized logging system`
**Risk Level**: Low (logging changes don't affect business logic)
**Effort**: 1-2 days
**Findings Addressed**: #19

---

## Context

The project has a comprehensive centralized logging system in `shit/logging/` with:
- `BeautifulFormatter` — emoji-based, color-coded output
- Service-specific loggers: `S3Logger`, `DatabaseLogger`, `LLMLogger`, `CLILogger`
- `ProgressTracker` for long-running operations
- Setup functions: `setup_harvester_logging()`, `setup_analyzer_logging()`, `setup_database_logging()`

Of the 8 migration phases defined in `documentation/LOGGING_MIGRATION_PLAN.md`, only **2 are complete** (Phase 1: CLI entry points, Phase 5: Main orchestrator). The remaining 6 phases cover internal modules that still use raw `logging.getLogger(__name__)`.

---

## Finding #19: 6 of 8 Logging Migration Phases Pending

### Current Status

| Phase | Scope | Status |
|-------|-------|--------|
| 1 | CLI entry points (`shitposts/cli.py`, `shitpost_ai/cli.py`) | COMPLETED |
| 2 | Database module (`shitvault/s3_processor.py`, `statistics.py`, `shitpost_operations.py`, `prediction_operations.py`) | PENDING |
| 3 | Infrastructure (`shit/db/database_client.py`, `database_operations.py`, `database_utils.py`) | PENDING |
| 4 | S3 module (`shit/s3/s3_client.py`, `s3_data_lake.py`) | PENDING |
| 5 | Main orchestrator (`shitpost_alpha.py`) | COMPLETED |
| 6 | Market data (`shit/market_data/client.py`, `outcome_calculator.py`, `cli.py`) | PENDING |
| 7 | LLM module (`shit/llm/llm_client.py`) | PENDING |
| 8 | Dashboard + Notifications (`shitty_ui/data.py`, `notifications/`) | PENDING |

### Migration Pattern

The migration pattern is the same for every file:

**BEFORE** (raw logger):
```python
import logging

logger = logging.getLogger(__name__)

# Usage:
logger.info("Processing started")
logger.error(f"Failed: {e}")
```

**AFTER** (centralized logger):
```python
from shit.logging import get_service_logger

logger = get_service_logger("service_name")

# Usage is identical:
logger.info("Processing started")
logger.error(f"Failed: {e}")
```

The `get_service_logger()` function returns a standard Python logger that's pre-configured with the `BeautifulFormatter`, so the usage doesn't change at all. Only the import and initialization change.

### Phase 2: Database Module

**Files to migrate**:

| File | Current Import | New Import | Logger Name |
|------|---------------|-----------|-------------|
| `shitvault/s3_processor.py` | `logging.getLogger(__name__)` | `get_service_logger("s3_processor")` | `s3_processor` |
| `shitvault/statistics.py` | `logging.getLogger(__name__)` | `get_service_logger("statistics")` | `statistics` |
| `shitvault/shitpost_operations.py` | `logging.getLogger(__name__)` | `get_service_logger("shitpost_ops")` | `shitpost_ops` |
| `shitvault/prediction_operations.py` | `logging.getLogger(__name__)` | `get_service_logger("prediction_ops")` | `prediction_ops` |

**Example change for `shitvault/s3_processor.py`**:

```python
# BEFORE:
import logging
logger = logging.getLogger(__name__)

# AFTER:
from shit.logging import get_service_logger
logger = get_service_logger("s3_processor")
```

### Phase 3: Infrastructure

**Files to migrate**:

| File | Logger Name |
|------|-------------|
| `shit/db/database_client.py` | `db_client` |
| `shit/db/database_operations.py` | `db_ops` |
| `shit/db/database_utils.py` | `db_utils` |

**Special case**: These files should use the `DatabaseLogger` for richer database-specific formatting:

```python
# BEFORE:
import logging
logger = logging.getLogger(__name__)

# AFTER:
from shit.logging.service_loggers import DatabaseLogger
db_logger = DatabaseLogger("db_client")
logger = db_logger.logger
```

### Phase 4: S3 Module

**Files to migrate**:

| File | Logger Name |
|------|-------------|
| `shit/s3/s3_client.py` | `s3_client` |
| `shit/s3/s3_data_lake.py` | `s3_data_lake` |

These should use the `S3Logger`:

```python
from shit.logging.service_loggers import S3Logger
s3_logger = S3Logger("s3_client")
logger = s3_logger.logger
```

### Phase 6: Market Data

**Files to migrate**:

| File | Logger Name | Notes |
|------|-------------|-------|
| `shit/market_data/client.py` | `market_data` | Already uses `get_service_logger` — verify |
| `shit/market_data/outcome_calculator.py` | `outcome_calculator` | Already uses `get_service_logger` — verify |
| `shit/market_data/cli.py` | `market_data_cli` | Uses `print_success`, `print_error` — already migrated |

**Check**: Some market data files may already be using centralized logging. Verify before making changes.

### Phase 7: LLM Module

**File**: `shit/llm/llm_client.py`

This file **already uses** the centralized logger (lines 16-20):

```python
from shit.logging.service_loggers import LLMLogger
llm_logger = LLMLogger("llm_client")
logger = llm_logger.logger
```

**No action needed** — mark Phase 7 as COMPLETED.

### Phase 8: Dashboard + Notifications

**Files to migrate**:

| File | Logger Name |
|------|-------------|
| `shitty_ui/data.py` | `dashboard_data` |
| `notifications/db.py` | `notifications_db` |
| `notifications/dispatcher.py` | `notifications_dispatch` |
| `notifications/alert_engine.py` | `alert_engine` |

**Note**: `shitty_ui/data.py` currently uses `print()` for errors (addressed in Plans 01 and 03). After those plans are complete, the remaining logging in `data.py` should use:

```python
from shit.logging import get_service_logger
logger = get_service_logger("dashboard_data")
```

---

## Implementation Order

1. **Phase 7**: Verify already complete (just update the plan doc status)
2. **Phase 6**: Verify market data files (may already be complete)
3. **Phase 2**: Database module (4 files)
4. **Phase 3**: Infrastructure (3 files)
5. **Phase 4**: S3 module (2 files)
6. **Phase 8**: Dashboard + Notifications (4 files) — do this AFTER Plans 01 and 03

Each phase can be a separate commit within the PR.

---

## Verification Checklist

- [ ] `grep -rn "logging.getLogger(__name__)" --include="*.py" shitvault/ shit/db/ shit/s3/ shit/market_data/ shit/llm/ shitty_ui/ notifications/` returns zero results (all migrated)
- [ ] `pytest shit_tests/ -v` — all tests pass
- [ ] `python -m shitvault stats` — produces formatted output (no import errors)
- [ ] `python shitpost_alpha.py --dry-run` — produces formatted output
- [ ] Update `documentation/LOGGING_MIGRATION_PLAN.md` to mark all phases COMPLETED

---

## What NOT To Do

1. **Do NOT change log message content.** Only change the logger initialization. The actual `logger.info()`, `logger.error()`, etc. calls stay identical.
2. **Do NOT add new log messages** in this PR. This is a migration, not an enhancement.
3. **Do NOT change log levels** (e.g., changing `logger.info` to `logger.debug`). Keep the same levels as the original code.
4. **Do NOT create new service logger classes.** Use the existing `get_service_logger()` for simple cases and the typed loggers (`DatabaseLogger`, `S3Logger`, `LLMLogger`) where they exist.
5. **Do NOT migrate test files.** Test files can use `logging.getLogger(__name__)` — they don't need beautiful formatting.
