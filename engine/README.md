# Signal engine

One always-on asyncio process. It holds a lease so only one copy works at a time, runs
daily jobs at New York times, and moves items through crash-safe stages. Nothing here
imports the old code in the rest of the repo.

## Commands

Run from this directory, with `ENGINE_DATABASE_URL` set (never the old `DATABASE_URL`):

    python -m engine migrate   # upgrade to head, then grant the web role (Railway pre-deploy)
    python -m engine run       # wait for the lease, then work while holding it
    python -m engine status    # print the status row and who holds the lease now
    python -m engine web       # serve the website's API (reads WEB_* settings, never ENGINE_*)

Settings are `ENGINE_*` variables; see `engine/settings.py`. New database connections
give up after 10 s per address the host resolves to; a `connect_timeout` in the URL wins.
In `engine.engine_meta`, `last_heartbeat_at` shows whether a copy is working;
`lease_holder` names the last holder and is not cleared when it stops.

## Database

Three schemas: `engine` (the web role may read it), `prices` (engine only) and `app`
(tables other plans add). The web role's access is the `WEB_GRANTS` map in
`engine/migrate.py`: a PR that adds a table the web app needs adds a line there. Grants
run on every migrate and only if the role in `ENGINE_WEB_ROLE` (default `web`) exists.

Migrations name the schema of every table. They run with `search_path` pinned to
`public`, so a table that forgets its schema lands in `public`, never in `engine` where
the web role could read it. The pin is a `SET LOCAL` in the migration transaction, so on
Neon run `migrate` against the direct (unpooled) endpoint, or set
`ALTER ROLE <engine role> SET search_path = public` once.

Migrations add first and remove later: old and new copies overlap during a deploy, so a
migration must keep the previous release working. New revision:
`alembic revision -m "..."` (writes into `engine/migrations/versions/`).

## Plug-in points

In `engine/registry.py`, `build_registry()`:

- `register_job(name, at, func, heavy=False)`: a daily job at New York time `at`, logged
  in `engine.job_runs`. A failed or interrupted run is retried up to `ENGINE_MAX_ATTEMPTS`
  times, then marked failed with one operator message. `heavy=True` runs it in a
  separate process. There is no job timeout yet: a hung job is skipped silently while it
  runs, so whoever adds the first real job adds `ENGINE_JOB_TIMEOUT_SECONDS` with it.
- `register_worker(name, func)`: a long-running task (delivery workers, the live loop),
  run only while this copy holds the lease and restarted with backoff if it raises (one
  operator message per failure streak).

`engine.notify.notify_operator(kind, text)` only logs for now.

`engine.stages.StageRunner` moves rows of a table with `stage_columns()` through named
stages, with `ENGINE_MAX_ATTEMPTS` attempts per stage before the final `error` state.
Rows at a stage this copy doesn't know are left alone (a newer copy may know it).

## Web service

`engine/web/` is the website's process: the public read API under `/api/v1` and
`/healthz`. It connects as the web role, reads only what `WEB_GRANTS` gives that role,
and never migrates. Railway settings for its service:

- Root directory: `engine/`, as for the engine service.
- Start command: `python -m engine web` (one uvicorn process on `0.0.0.0:$PORT`).
- Health check path: `/healthz`.
- Pre-deploy command: none.
- Config file path: none. Railway reads a config file from the repo root unless a service
  names one, whatever its root directory (https://docs.railway.com/deployments/monorepo),
  so the engine service names `/engine/railway.json` and this one names nothing.
- Variables: `WEB_DATABASE_URL`, the engine database as the web role, on Neon's direct
  (unpooled) endpoint. A transaction pooler would drop each connection's 5 s statement
  timeout.
- Keep Railway's CDN off for this service: behind it, `X-Real-IP` holds the CDN's address,
  so every visitor would share a rate-limit bucket.

Other settings (`engine/web/settings.py`) have defaults: `WEB_RATE_LIMIT_PER_MINUTE`
(120) and `WEB_RATE_LIMIT_BURST` (30) per visitor address; `WEB_CLIENT_IP_HEADER`
(`X-Real-IP`) and `WEB_TRUSTED_HOPS` (1), where the visitor's address comes from;
`WEB_POOL_SIZE` (5) database connections.

`/healthz` runs `SELECT 1` with a 2 s timeout: `{"ok": true}` (200) or `{"ok": false}`
(503), never cached and never rate limited. The access log has method, path, status and
duration, never the visitor's address.

The visitor's address is the one Railway's edge proxy saw: its docs list "`X-Real-IP` for
identifying client's remote IP"
(https://docs.railway.com/networking/public-networking/specs-and-limits). The limiter
takes the entry `WEB_TRUSTED_HOPS` from the right of that header, so a header that proxies
append to (`X-Forwarded-For`) also works: what a visitor writes lands on the left and never
counts. Without the header (local runs) it uses the socket address; uvicorn's own
proxy-header handling is off.

## Public API

Every route under `/api/v1` follows these rules; each has a small module in `engine/web/`.

- **Explicit fields** (`models.py`, `router.py`). Routes are defined on an `ApiRouter`,
  which refuses a route whose `response_model` isn't an `ApiResponse`. Models list their
  fields and forbid others, so a row or dict never passes through as is.
- **stream_id** (`stream.py`, `deps.py`). Every successful JSON body carries `stream_id`
  at the top level, from `engine.engine_meta`, read at most once a minute. Take it as a
  `StreamId` parameter. A new value means the database was rebuilt.
- **Lists** (`paging.py`). A list is `Page[Item]`: `{stream_id, items, next_before}`. It
  takes `?before=<cursor>&limit=` (`limit` 1 to 100, default 20). The cursor is opaque:
  URL-safe base64 of the sort key, a list of integers. A bad `limit` or cursor is a 400.
  The route fetches `limit + 1` rows below `page.before_key(n)` and calls `take_page`.
- **Errors** (`errors.py`). Under `/api/`, every error is
  `{"error": {"code": ..., "message": ...}}`, including unknown paths. Raise
  `ApiError(code, message)` from a route.

  | Code | Status |
  |---|---|
  | `bad_request` | 400 (also a wrong method: 405, with `Allow`) |
  | `not_found` | 404 |
  | `rate_limited` | 429, with `Retry-After` |
  | `unavailable` | 503, when the database is down or every connection is busy |
  | `internal` | 500; the traceback goes to the log only |

  Outside `/api/` the same statuses are plain text.
- **Cache** (`cache.py`). `ResponseCache(ttl).respond(request, build)` serves a GET from
  memory for `ttl` seconds, keyed by path and query string, and sends
  `Cache-Control: public, max-age=<ttl>`. Only 200s are kept.
- **CORS** (`policy.py`). Any origin may GET `/api/v1/*`:
  `Access-Control-Allow-Origin: *`, no credentials. Other methods get no CORS headers.
- **Headers** (`policy.py`). Every response, errors and `/healthz` included, has
  `Content-Security-Policy`, `Strict-Transport-Security: max-age=31536000`,
  `X-Content-Type-Options: nosniff` and `Referrer-Policy: strict-origin-when-cross-origin`.
- **No prices.** No response field may be a price (`tests/web/test_no_prices.py` walks
  the OpenAPI schema for price-like names; public output is % moves only).

The schema is at `/api/v1/openapi.json`, the one body under `/api/v1` without
`stream_id`; it documents the error shape as each route's 4XX and 5XX. The docs pages
are off (they load a CDN's scripts). Links to the site come from `engine/links.py`: `signal_url(public_id)`.

## Tests

    pip install -e ".[dev]"
    DEV_DATABASE_URL=postgresql://user:pass@localhost:5432/postgres pytest
    ruff check . && ruff format --check . && mypy

Tests create and drop their own databases on the `DEV_DATABASE_URL` server.
