# WS05 — Consolidate Database Session Architecture

**Priority**: HIGH
**Type**: architecture
**Findings**: H1, H2, H3
**Primary files**: `shit/db/database_client.py`, `shit/db/sync_session.py`, `shit/services.py`, `shit/README.md`

---

## Context

The codebase runs two DB access stacks against the same PostgreSQL:
- **Async** `DatabaseClient` (psycopg async) — harvesting/analysis pipeline.
- **Sync** module-level `get_session()` / `SessionLocal` (psycopg2) — events, market_data, echoes, calibration, notifications.

A prior review decided to keep both drivers intentionally. This workstream does **not** force a single driver; it fixes the concrete correctness/lifecycle bugs and reduces confusion.

## Findings

### H2 — `get_session()` misused as an async context manager
`DatabaseClient.get_session()` (`database_client.py:73-77`) returns a bare `AsyncSession`, but the README (`shit/README.md:268`) and callers use `async with db_client.get_session() as session:`. A bare `AsyncSession` is not an async context manager in the way callers assume; sessions may not be closed/returned to the pool deterministically.

**Fix**: Provide an explicit `@asynccontextmanager` (e.g. `session_scope()`) that yields a session and guarantees `close()`/rollback-on-error, and update callers + docs. Or make `get_session()` itself return an async context manager. Pick one and make the docs match reality.

### H3 — `create_all()` runs on every async init
`initialize()` (`database_client.py:67-69`) calls `Base.metadata.create_all` on every startup. In production this risks schema drift, races with migrations, and accidental table creation.

**Fix**: Gate schema creation behind an explicit flag / dev-only path (e.g. tests or `ENVIRONMENT=development`), or remove it in favor of the migration scripts already in `shitvault/`.

### H1 — Dual session mechanisms increase pool pressure & cognitive load
Two engines, two pools, two driver stacks on one DB; some modules mix them (e.g. nested `get_session()` + `OutcomeCalculator`’s own session in `auto_backfill_service.py:183-229`, and `market_data/event_consumer.py:68` using `SessionLocal()` directly while the producer uses `get_session()`).

**Fix (bounded)**: Do not consolidate drivers, but:
- Standardize on the context-manager form everywhere (no bare `SessionLocal()` scattered around; no double-commit inside `with get_session()`).
- Document the async-vs-sync boundary in `shit/README.md` (which subsystems use which and why).
- Audit for nested/overlapping sessions on the same logical operation and flatten them.

## Acceptance criteria

- [ ] One documented async session pattern; README examples match actual API (no misleading `async with get_session()`).
- [ ] Schema `create_all()` no longer runs unconditionally on production startup.
- [ ] `shit/README.md` documents the sync/async boundary; obvious nested-session cases (auto_backfill, market event consumer) use a single consistent pattern.
