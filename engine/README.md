# Signal engine

One always-on asyncio process. It holds a lease so only one copy works at a time, runs
daily jobs at New York times, and moves items through crash-safe stages. Nothing here
imports the old code in the rest of the repo.

## Commands

Run from this directory, with `ENGINE_DATABASE_URL` set (never the old `DATABASE_URL`):

    python -m engine migrate   # upgrade to head, then grant the web role (Railway pre-deploy)
    python -m engine run       # wait for the lease, then work while holding it
    python -m engine status    # print the status row and who holds the lease

Settings are `ENGINE_*` variables; see `engine/settings.py`.

## Database

Three schemas: `engine` (the web role may read it), `prices` (engine only) and `app`
(tables other plans add; each PR grants the web role what its table needs). Grants run on
every migrate and only if the role in `ENGINE_WEB_ROLE` (default `web`) exists.

Migrations add first and remove later: old and new copies overlap during a deploy, so a
migration must keep the previous release working. New revision:
`alembic revision -m "..."` (writes into `engine/migrations/versions/`).

## Plug-in points

In `engine/registry.py`, `build_registry()`:

- `register_job(name, at, func, heavy=False)`: a daily job at New York time `at`, logged
  in `engine.job_runs`. `heavy=True` runs it in a separate process.
- `register_worker(name, func)`: a long-running task (delivery workers, the live loop),
  run only while this copy holds the lease and restarted if it raises.

`engine.notify.notify_operator(kind, text)` only logs for now.

`engine.stages.StageRunner` moves rows of a table with `stage_columns()` through named
stages, with three attempts per stage before the final `error` state.

## Tests

    pip install -e ".[dev]"
    DEV_DATABASE_URL=postgresql://user:pass@localhost:5432/postgres pytest
    ruff check . && ruff format --check . && mypy

Tests create and drop their own databases on the `DEV_DATABASE_URL` server.
