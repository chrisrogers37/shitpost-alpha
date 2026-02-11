# Plan 04: Code Deduplication

**Status**: ✅ COMPLETE
**Started**: 2026-02-10
**Completed**: 2026-02-10

**PR Title**: `refactor: deduplicate subprocess execution, shared queries, and result mapping`
**Risk Level**: Low (refactoring with no behavior change)
**Effort**: 1-2 days
**Findings Addressed**: #12, #13, #14, #17

---

## Finding #12: Three Identical Subprocess Execution Functions

### Location

`shitpost_alpha.py:20-172`

### Problem

Three functions — `execute_harvesting_cli()`, `execute_s3_to_database_cli()`, and `execute_analysis_cli()` — share the same structure:

```python
async def execute_harvesting_cli(args) -> bool:       # lines 20-68
async def execute_s3_to_database_cli(args) -> bool:   # lines 71-119
async def execute_analysis_cli(args) -> bool:          # lines 122-172
```

Each follows the identical pattern:
1. Build a `cmd` list from args
2. Call `asyncio.create_subprocess_exec(*cmd, ...)`
3. Await `process.communicate()`
4. Check `process.returncode`
5. Log success/failure with stdout/stderr

The only differences are:
- The base command (`-m shitposts` vs `-m shitvault` vs `-m shitpost_ai`)
- The specific argument mapping (slightly different flag names)
- The log emoji and phase name

### Fix

Extract a shared `_execute_subprocess()` helper:

```python
# shitpost_alpha.py — REFACTORED

async def _execute_subprocess(cmd: list[str], phase_name: str, emoji: str) -> bool:
    """Execute a subprocess and stream its output.

    Args:
        cmd: Command and arguments to execute.
        phase_name: Human-readable name for logging (e.g., "Harvesting").
        emoji: Emoji prefix for log messages.

    Returns:
        True if subprocess exited with code 0.
    """
    logger.info(f"{emoji} Executing {phase_name} CLI: {' '.join(cmd)}")

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            logger.info(f"✅ {phase_name} completed successfully")
            if stdout:
                print(f"📊 {phase_name} Output:")
                print(stdout.decode())
            return True
        else:
            logger.error(f"❌ {phase_name} failed with return code {process.returncode}")
            if stderr:
                print(f"🚨 {phase_name} Errors:")
                print(stderr.decode())
            return False

    except Exception as e:
        logger.error(f"❌ Failed to execute {phase_name} CLI: {e}")
        return False


def _build_harvesting_cmd(args) -> list[str]:
    """Build command for harvesting CLI."""
    cmd = [sys.executable, "-m", "shitposts", "--mode", args.mode]
    if args.from_date:
        cmd.extend(["--from", args.from_date])
    if args.to_date:
        cmd.extend(["--to", args.to_date])
    if args.limit:
        cmd.extend(["--limit", str(args.limit)])
    if hasattr(args, "max_id") and args.max_id:
        cmd.extend(["--max-id", args.max_id])
    if args.verbose:
        cmd.append("--verbose")
    return cmd


def _build_s3_to_db_cmd(args) -> list[str]:
    """Build command for S3-to-database CLI."""
    cmd = [sys.executable, "-m", "shitvault", "load-database-from-s3", "--mode", args.mode]
    if args.from_date:
        cmd.extend(["--start-date", args.from_date])
    if args.to_date:
        cmd.extend(["--end-date", args.to_date])
    if args.limit:
        cmd.extend(["--limit", str(args.limit)])
    return cmd


def _build_analysis_cmd(args) -> list[str]:
    """Build command for analysis CLI."""
    cmd = [sys.executable, "-m", "shitpost_ai", "--mode", args.mode]
    if args.from_date:
        cmd.extend(["--from", args.from_date])
    if args.to_date:
        cmd.extend(["--to", args.to_date])
    if args.limit:
        cmd.extend(["--limit", str(args.limit)])
    if args.batch_size:
        cmd.extend(["--batch-size", str(args.batch_size)])
    if args.verbose:
        cmd.append("--verbose")
    return cmd


# Usage in main():
harvest_success = await _execute_subprocess(
    _build_harvesting_cmd(args), "Harvesting", "🚀"
)
s3_success = await _execute_subprocess(
    _build_s3_to_db_cmd(args), "S3 to Database", "💾"
)
analysis_success = await _execute_subprocess(
    _build_analysis_cmd(args), "Analysis", "🧠"
)
```

**Lines saved**: ~80 lines (from ~150 to ~70)

---

## Finding #13: Duplicate `get_new_predictions_since()`

### Locations

| File | Line | Used By |
|------|------|---------|
| `notifications/db.py` | 275 | `notifications/alert_engine.py` |
| `shitty_ui/data.py` | 1701 | `shitty_ui/alerts.py` |

### Problem

Two independent implementations of the same query exist. They have nearly identical SQL, but:
- The `notifications/db.py` version uses `get_session()` from `sync_session.py`
- The `shitty_ui/data.py` version uses its own `SessionLocal`

If the query logic needs to change, both must be updated.

### Fix

After Plan 03 (database session consolidation) is complete, both modules use the same session. Then:

1. **Keep the canonical version** in `notifications/db.py` (it's the more natural home for alert-related queries)
2. **Import it** in `shitty_ui/data.py` instead of duplicating:

```python
# shitty_ui/data.py — REPLACE the duplicate function with an import
# Remove the ~50-line get_new_predictions_since() function and replace with:

from notifications.db import get_new_predictions_since  # Reuse canonical implementation
```

3. **Update `shitty_ui/alerts.py`** if it imports from `data.py`:

```python
# If shitty_ui/alerts.py currently does:
from data import get_new_predictions_since

# Change to:
from notifications.db import get_new_predictions_since
```

**Prerequisite**: Plan 03 must be completed first so both modules use the same session pool.

---

## Finding #14: Repeated `dict(zip(columns, row))` Pattern

### Location

`notifications/db.py` — appears in nearly every function:

```python
# This pattern appears ~10 times in notifications/db.py:
result = session.execute(query, params)
rows = result.fetchall()
columns = result.keys()
if rows:
    return dict(zip(columns, rows[0]))       # Single result
# or
return [dict(zip(columns, row)) for row in rows]  # Multiple results
```

Lines where this pattern appears: 48-51, 78-80, 260-263, 314-316, 350-351, 405-409

### Fix

Extract a helper function:

```python
# notifications/db.py — Add at top of file, after imports:

def _row_to_dict(result) -> Optional[Dict[str, Any]]:
    """Convert a single query result row to a dictionary."""
    rows = result.fetchall()
    if not rows:
        return None
    columns = result.keys()
    return dict(zip(columns, rows[0]))


def _rows_to_dicts(result) -> List[Dict[str, Any]]:
    """Convert query result rows to a list of dictionaries."""
    rows = result.fetchall()
    columns = result.keys()
    return [dict(zip(columns, row)) for row in rows]
```

Then refactor each function. For example:

```python
# BEFORE (get_subscription, lines 46-51):
result = session.execute(query, {"chat_id": str(chat_id)})
rows = result.fetchall()
columns = result.keys()
if rows:
    return dict(zip(columns, rows[0]))
return None

# AFTER:
result = session.execute(query, {"chat_id": str(chat_id)})
return _row_to_dict(result)
```

```python
# BEFORE (get_active_subscriptions, lines 77-80):
result = session.execute(query)
rows = result.fetchall()
columns = result.keys()
return [dict(zip(columns, row)) for row in rows]

# AFTER:
result = session.execute(query)
return _rows_to_dicts(result)
```

**Lines saved**: ~30 lines across the file.

---

## Finding #17: CLI Argument Duplication in Dry-Run Path

### Location

`shitpost_alpha.py:259-311`

### Problem

The dry-run path rebuilds the exact same command lists that the execution functions build:

```python
# Lines 267-279 rebuild the harvesting command
# Lines 282-293 rebuild the S3 command
# Lines 296-309 rebuild the analysis command
```

This duplicates the command-building logic from the three execution functions.

### Fix

After Finding #12 is fixed (extracting `_build_*_cmd()` functions), the dry-run path simply reuses them:

```python
# shitpost_alpha.py — REFACTORED dry-run block
if args.dry_run:
    print_info("🔍 DRY RUN MODE - No commands will be executed")
    print_info(f"Processing Mode: {args.mode}")
    print_info(f"Shared Settings: from={args.from_date}, to={args.to_date}, limit={args.limit}")
    print_info(f"Analysis Parameters: batch_size={args.batch_size}")
    print_info("\n📋 Commands that would be executed:")
    print_info(f"  1. Harvesting: {' '.join(_build_harvesting_cmd(args))}")
    print_info(f"  2. S3 to Database: {' '.join(_build_s3_to_db_cmd(args))}")
    print_info(f"  3. LLM Analysis: {' '.join(_build_analysis_cmd(args))}")
    return
```

**Lines saved**: ~40 lines.

---

## Verification Checklist

- [ ] `python shitpost_alpha.py --dry-run` produces the same output as before
- [ ] `python shitpost_alpha.py --mode range --from 2025-01-01 --dry-run` produces correct output
- [ ] `grep -c "get_new_predictions_since" shitty_ui/data.py` returns 1 (the import) not 2+ (an implementation)
- [ ] `grep -c "dict(zip(columns" notifications/db.py` returns 0 (all replaced with helpers)
- [ ] `pytest shit_tests/ -v` — all tests pass
- [ ] `ruff check shitpost_alpha.py notifications/db.py shitty_ui/data.py`

---

## What NOT To Do

1. **Do NOT change function signatures** of the public-facing functions. Internal refactoring only.
2. **Do NOT consolidate `_build_*_cmd()` into a single generic function** — the three command builders have genuinely different argument mappings (e.g., `--from` vs `--start-date`), so keeping them separate is clearer.
3. **Do NOT start this plan before Plan 03** (session consolidation). The `get_new_predictions_since` deduplication depends on having a single session provider.
4. **Do NOT move functions between modules** beyond what's specified. Moving `get_new_predictions_since` to a shared location is fine; reorganizing the entire query layer is out of scope.
