# Plan 03: Database Session Consolidation

**Status**: ✅ COMPLETE
**Started**: 2026-02-10
**Completed**: 2026-02-10

**PR Title**: `refactor: consolidate database connection pools into shared sync_session`
**Risk Level**: High (changes touch every database consumer in the application)
**Effort**: 1-2 days
**Findings Addressed**: #11, #20

---

## Context

The application currently creates **three separate database connection pools**:

| Pool | Location | Used By |
|------|----------|---------|
| Pool 1 | `shit/db/sync_session.py:14-32` | `notifications/`, `shit/market_data/` |
| Pool 2 | `shitty_ui/data.py:78-118` | Dashboard queries |
| Pool 3 | `shit/db/database_client.py` | Async operations (harvester, analyzer) |

Pools 1 and 2 are both synchronous PostgreSQL connections doing the same thing — there's no reason to have two. Each pool holds 5 persistent connections with 10 overflow, so the application uses up to **30 connections** when it only needs 15.

---

## Finding #11: Three Separate Connection Pools

### Current State

**Pool 1 — `shit/db/sync_session.py`** (the canonical one):

```python
# shit/db/sync_session.py:14-32
DATABASE_URL = settings.DATABASE_URL.strip('"').strip("'")

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, echo=False, future=True)
else:
    sync_url = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
    sync_url = sync_url.replace("postgresql+asyncpg://", "postgresql://")
    if not sync_url.startswith("postgresql+psycopg2://"):
        sync_url = sync_url.replace("postgresql://", "postgresql+psycopg2://")
    engine = create_engine(sync_url, echo=False, future=True, pool_pre_ping=True)

SessionLocal = sessionmaker(engine, expire_on_commit=False)
```

**Pool 2 — `shitty_ui/data.py`** (the duplicate):

```python
# shitty_ui/data.py:58-118
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from shit.config.shitpost_settings import settings
    DATABASE_URL = settings.DATABASE_URL.strip('"').strip("'")
    print(f"🔍 Dashboard using settings DATABASE_URL: {DATABASE_URL[:50]}...")
except ImportError as e:
    DATABASE_URL = os.environ.get("DATABASE_URL", "").strip('"').strip("'")
    # ... fallback logic ...

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, echo=False, future=True)
    SessionLocal = sessionmaker(engine, expire_on_commit=False)
else:
    sync_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    sync_url = sync_url.replace("?sslmode=require&channel_binding=require", "")
    # ... more URL manipulation ...
    pool_settings = {
        "pool_size": 5, "max_overflow": 10, "pool_timeout": 30,
        "pool_recycle": 1800, "pool_pre_ping": True,
    }
    engine = create_engine(sync_url, echo=False, future=True, **pool_settings)
    SessionLocal = sessionmaker(engine, expire_on_commit=False)
```

These do the same thing with slightly different URL manipulation and pool settings. Pool 2 also has the `sys.path` hack and credential logging issues (addressed in Plans 01 and 05).

### Fix

**Step 1**: Enhance `sync_session.py` pool settings to match the dashboard's more robust configuration:

```python
# shit/db/sync_session.py — UPDATED
import logging
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from shit.config.shitpost_settings import settings

logger = logging.getLogger(__name__)

DATABASE_URL = settings.DATABASE_URL.strip('"').strip("'")

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, echo=False, future=True)
else:
    sync_url = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
    sync_url = sync_url.replace("postgresql+asyncpg://", "postgresql://")
    # Strip SSL parameters that cause issues with psycopg2
    sync_url = sync_url.replace("?sslmode=require&channel_binding=require", "")
    if not sync_url.startswith("postgresql+psycopg2://"):
        sync_url = sync_url.replace("postgresql://", "postgresql+psycopg2://")

    engine = create_engine(
        sync_url,
        echo=False,
        future=True,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800,
        pool_pre_ping=True,
    )

SessionLocal = sessionmaker(engine, expire_on_commit=False)

# ... get_session() and create_tables() unchanged ...
```

**Step 2**: Replace `shitty_ui/data.py` engine setup with an import:

```python
# shitty_ui/data.py — REPLACE lines 1-130 with:
"""
Database access layer for Shitty UI Dashboard.
Handles query functions for posts and predictions.
"""

import time
import logging
import pandas as pd
from datetime import datetime, timedelta
from functools import wraps
from sqlalchemy import text
from typing import List, Dict, Any, Optional, Callable

from shit.db.sync_session import get_session, SessionLocal

logger = logging.getLogger(__name__)


# Simple TTL cache decorator (keep as-is)
def ttl_cache(ttl_seconds: int = 300):
    # ... existing implementation unchanged ...


def execute_query(query, params=None):
    """Execute query using shared session."""
    try:
        with SessionLocal() as session:
            result = session.execute(query, params or {})
            return result.fetchall(), result.keys()
    except Exception as e:
        logger.error(f"Database query error: {e}")
        raise
```

**What this removes from `data.py`**:
- `import sys, os` (lines 7-8)
- `sys.path.insert(0, ...)` hack (line 59)
- All engine/SessionLocal creation code (lines 60-118)
- All `print()` statements with DATABASE_URL (lines 65, 69-71, 88, 105, 115, 117)
- The duplicate `DATABASE_URL` variable

**Step 3**: Update `execute_query()` callers — the function signature stays the same, so no caller changes needed.

---

## Finding #20: Raw SQL in `notifications/db.py`

### Current State

Every function in `notifications/db.py` uses `text()` with raw SQL strings:

```python
# notifications/db.py:37-48 (representative example)
query = text("""
    SELECT id, chat_id, chat_type, username, first_name, last_name,
           title, is_active, subscribed_at, unsubscribed_at,
           alert_preferences, last_alert_at, alerts_sent_count,
           last_interaction_at, consecutive_errors, last_error,
           created_at, updated_at
    FROM telegram_subscriptions
    WHERE chat_id = :chat_id
""")
result = session.execute(query, {"chat_id": str(chat_id)})
rows = result.fetchall()
columns = result.keys()
if rows:
    return dict(zip(columns, rows[0]))
```

### Why This is a Problem

1. **No type safety** — Column renames in the model won't be caught at compile time
2. **No relationship loading** — Can't leverage SQLAlchemy's relationship features
3. **Verbose** — Every function manually zips columns with rows

### Recommended Approach (NOT for this PR)

Converting all raw SQL to ORM queries is a significant change that should be its own PR. For this PR, the scope is limited to:

1. Ensuring `notifications/db.py` uses `get_session()` from `sync_session.py` (it already does)
2. Ensuring the session pool configuration is consistent (done in Step 1)
3. Documenting the ORM migration as a future follow-up

**Future PR** (not this plan): Create a `TelegramSubscription` SQLAlchemy model and rewrite `notifications/db.py` to use it instead of raw SQL. This would eliminate the SQL injection surface entirely.

---

## Migration Steps (Ordered)

1. Update `shit/db/sync_session.py` with enhanced pool settings (Step 1 above)
2. Remove engine/session setup from `shitty_ui/data.py` and replace with import (Step 2 above)
3. Remove `sys.path` hack and `print()` statements from `shitty_ui/data.py`
4. Verify all dashboard queries still work with shared session
5. Run full test suite

---

## Verification Checklist

- [ ] `grep -n "create_engine" shitty_ui/data.py` returns zero results
- [ ] `grep -n "sys.path" shitty_ui/data.py` returns zero results
- [ ] `grep -n "print(" shitty_ui/data.py` returns zero results (or only non-DB prints)
- [ ] `grep -rn "create_engine" --include="*.py" shit/ shitty_ui/ notifications/` returns only `sync_session.py` and `database_client.py` (async)
- [ ] `pytest shit_tests/ -v` — all tests pass
- [ ] Dashboard starts without error: `cd shitty_ui && python app.py` (verify no import errors)
- [ ] Dashboard loads data correctly (manual verification against production)

---

## What NOT To Do

1. **Do NOT touch the async database client** (`shit/db/database_client.py`). The async pool serves a completely different purpose (harvester, analyzer) and should not be consolidated with the sync pool.
2. **Do NOT convert `notifications/db.py` to ORM in this PR.** That's a separate, larger refactor. This PR only consolidates the sync session pools.
3. **Do NOT change pool size numbers** without load testing. The current 5+10 configuration is reasonable for the workload.
4. **Do NOT remove the SQLite fallback** in `sync_session.py`. Tests use SQLite.
5. **Do NOT change import paths in test files** unless they break. The goal is to minimize the blast radius.
