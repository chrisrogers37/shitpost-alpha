# Site PR D0: API base

You are building D0, the first of three website PRs in chrisrogers37/shitpost-alpha. D0 sets up the public read API that the website, the notification plan's API PR (N2) and agents all build on. It ships no pages and no alert routes.

D0 adds three things to the engine package:
- the web process;
- the `/api/v1` conventions every later route follows, with the rate-limiter fix;
- `/healthz` and the shared link builder.

It also deletes the old website.

The rest of the repo is the old system, shut down in production. Don't import it, edit it or copy its design, apart from the deletions listed below. Design from first principles.

What exists: **engine PR 1** (draft #258, branch `claude/engine-foundation-k6mh6s`) built `engine/`. It has its own `pyproject.toml`, settings with the `ENGINE_` prefix, Alembic with the `engine`, `prices` and `app` schemas, the `WEB_GRANTS` map in `engine/migrate.py`, `engine.engine_meta` (which holds `stream_id`), the CLI in `engine/cli.py` and CI in `.github/workflows/engine.yml`. Read it first and build on it. Engine PRs 2 to 4 (#259 to #261) stack on it; D0 needs none of them.

Send questions to the site planner (session_01KCJr6bPZiRiCHvXaSz29dj) with send_message; send questions about the engine's own code to the engine planner (session_01Gw4reivJGz4EWbyB29SbDJ). If an answer isn't needed to keep going, pick a sensible default, note it in the PR and carry on.

## Rules (non-negotiable)
- **Merging.** Never merge, approve or enable auto-merge. Open a draft PR and stop; Chris merges. Ignore the admin-merge pre-approval in the repo's CLAUDE.md.
- **Databases.** Never touch a production database. Never read or set DATABASE_URL. The web process reads WEB_DATABASE_URL and the engine reads ENGINE_DATABASE_URL. Locally, use the sandbox Postgres in DEV_DATABASE_URL.
- **Keys.** Never set OPENAI_API_KEY, ANTHROPIC_API_KEY or XAI_API_KEY: the old tests make paid calls when they exist. D0 needs no keys.
- **Outside services.** No Telegram, email or SMS. No crons. No Railway calls (connector or CLI). Nothing deploys from this PR.
- **Scope.** Keep it minimal. Test-only code stays thin and is marked test-only. N2 is the first user of the paging and cache helpers, so keep each one small and tested on its own.

## Environment
- Python 3.13 venv at /home/user/venv. If `python --version` isn't 3.13, use /home/user/venv/bin/python. Install the engine with `pip install -e "engine[dev]"`.
- Local Postgres 16 with superuser `shitpost`; its URL is in DEV_DATABASE_URL. Tests make throwaway databases there, as PR 1's conftest does. If Postgres has stopped, run `service postgresql start`.

## Scope

**1. Web process.**
- Put the web app in `engine/engine/web/` (FastAPI). Add fastapi and uvicorn to the engine's dependencies, and httpx to dev.
- `python -m engine web` serves it with uvicorn on 0.0.0.0:$PORT (default 8000): one process, no server header, and uvicorn's proxy-header handling off (step 3 reads the address itself).
- The `web` command loads its own settings, never the engine's. Today `cli.py` builds `Settings()` before it dispatches, so the web process would demand ENGINE_DATABASE_URL; fix that.
- Web settings use the `WEB_` prefix:
  - `WEB_DATABASE_URL` (SecretStr, required);
  - the rate limit;
  - the trusted address header (step 3);
  - the pool size, default 5.
- Every database connection sets a statement timeout of about 5 s. The web process never migrates.
- The access log records method, path, status and duration, never the visitor's address.
- Turn off FastAPI's `/docs` and `/redoc`, which load scripts from a CDN. Serve the schema at `/api/v1/openapi.json`.

**2. `/api/v1` conventions.** Write these in `engine/README.md` under "Public API", with a small module for each:
- **Explicit fields.** Every response is a Pydantic model that lists its fields. Nothing returns a row or dict as is.
- **stream_id.** Every successful JSON body under `/api/v1` carries `stream_id` at the top level, from `engine.engine_meta`, cached in-process for about 60 s.
- **Lists.** A list response is `{stream_id, items, next_before}`. It takes `?before=<cursor>&limit=`: `limit` defaults to 20, with a maximum of 100. The cursor is opaque (URL-safe base64 of the sort key). A bad `limit` or cursor gets a 400. N2 adds `after`, `head_seq` and `has_more` for its change feed on the same pattern.
- **Errors.** Every error under `/api/` is `{"error": {"code": ..., "message": ...}}`, never a stack trace and never FastAPI's default shape. That includes unknown paths, which get a JSON 404. The codes are:

  | Code | Status |
  |---|---|
  | `bad_request` | 400 |
  | `not_found` | 404 |
  | `rate_limited` | 429, with Retry-After |
  | `unavailable` | 503, when the database is down |
  | `internal` | 500 |

  Outside `/api/` the same statuses return plain text. D1 adds pages for them.
- **Cache.** A helper serves a GET response from a short in-process cache keyed by path and query, and marks it `Cache-Control: public, max-age=<ttl>`. Only 200s are cached. N2 uses it for the change feed (5 s).
- **CORS.** Any origin may GET `/api/v1/*` (`Access-Control-Allow-Origin: *`, no credentials). Other methods get no CORS.
- **Headers on every response:**
  - `Content-Security-Policy: default-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'`;
  - `Strict-Transport-Security: max-age=31536000`, without includeSubDomains or preload;
  - `X-Content-Type-Options: nosniff`;
  - `Referrer-Policy: strict-origin-when-cross-origin`.

**3. Rate limit by the real visitor.** The old limiter (`api/rate_limit.py:10`) keys on slowapi's `get_ipaddr`. That function looks for a header spelled `X_FORWARDED_FOR`, which never matches, so behind Railway's proxy every visitor shares one bucket.

The new limiter:
- is in-memory, per visitor address, a token bucket, with the rate as a setting (default 120 a minute plus a burst of 30);
- keeps the bucket table bounded by evicting idle entries;
- returns 429 with Retry-After;
- never limits `/healthz`.

The address is the one Railway's edge proxy saw, never one the visitor can send. Confirm from Railway's public docs which header the edge sets or appends (X-Forwarded-For, X-Real-IP or another), and how. Reading docs.railway.com with WebFetch is fine; it may ask Chris to approve, and he approves read prompts. Key on the value the edge writes: if it appends to X-Forwarded-For, that is the rightmost entry. Make the header and the number of trusted hops a setting with that default, cite the docs page in the code and the PR, and fall back to the socket address when the header is absent.

**4. `/healthz`.** It runs `SELECT 1` with a 2 s timeout and returns `{"ok": true}` (200) or `{"ok": false}` (503) with `Cache-Control: no-store`, and nothing else. Railway's health check uses it, and the engine's outside check calls it every minute from the shadow week.

**5. Link builder.** `engine/engine/links.py`: `SITE_URL = "https://shitpostalpha.com"` and `signal_url(public_id)`, which returns `https://shitpostalpha.com/s/<public_id>`. The engine, the notification code and the site build their links with it.

**6. Tests that guard the rules.** The ones the plan names:
- **No prices.** A test walks the response model of every route in the app, via the generated OpenAPI schema, and fails on any field whose name has a price-like token: price, open, high, low, close, vwap, volume, bid, ask, ohlc, bar or bars. Split names on underscores and camel case. A short allowlist covers fields that are not prices (for example the engine's `market_open` flag), each with a one-line reason. It passes with no routes today. A test-only router with a `close_price` field proves that it fails.
- **Web role.** The API's tests run as a real login role holding only what `migrate` grants (WEB_GRANTS), not as the superuser. Create that role in the test database, run migrate, and connect as it. One test shows that this role reads `engine.engine_meta` but gets "permission denied" on `prices` and on any write.
- **Limiter.** Requests from two addresses get separate buckets. A forged X-Forwarded-For entry from the visitor (left of the edge's entry) can't move a request into another bucket.
- **Errors and headers:**
  - a JSON 404 on an unknown `/api/v1` path;
  - a 503 from `/healthz` and from a test route when the database is unreachable;
  - CORS on GET only;
  - every header in step 2 on an `/api/v1` response, a `/healthz` response and an error.
- **Paging and cache:** a cursor round-trips, and a bad one is a 400; the cache serves a second hit without a query, and expires.

**7. Delete the old website.** Remove these, with every test that imports them:
- `api/`;
- `frontend/`;
- `shit_tests/api/` and `shit_tests/echoes/test_api.py`;
- the root `railway.json` and `railpack.json`. They describe the 12 old services, which were torn down. The engine's config stays at `engine/railway.json`, and the web service will keep its settings in Railway's dashboard, with no config file.

Leave `requirements.txt` alone; engine PR 11 removes the old code and its packages. Update the parts of CLAUDE.md, README.md and AGENTS.md that describe `api/` and `frontend/` so they point to `engine/engine/web/`. Change nothing else in those files.

**8. README.** Under "Web service" in `engine/README.md`:
- the start command `python -m engine web`;
- health check path `/healthz`;
- no pre-deploy command;
- variable `WEB_DATABASE_URL`;
- root directory `engine/`, as for the engine service;
- no config-file path.

D1 finishes this section.

## How to check your work
From `engine/`, `ruff check .`, `ruff format --check .`, `mypy` and `pytest` all pass, and CI is green. Start `python -m engine web` locally with WEB_DATABASE_URL pointing at a migrated test database as the web role:
- `curl /healthz` answers 200;
- after you stop Postgres, it answers 503 within about 2 s;
- an unknown `/api/v1/x` returns the JSON 404 with every header.

Before pushing, re-read your diff as a reviewer hunting for reasons to reject it.

## Deliver
1. **Branch** from `claude/engine-foundation-k6mh6s` while #258 is unmerged, or from main once it has merged. D0 adds no migration, so it doesn't collide with PRs 2 to 4. Commit and push.
2. **Draft PR** against main titled "Site D0: API base". Near the top, say that it goes in after #258, and only once the old Railway services are deleted, because a merge to main redeploys any that still exist. The body has:
   - a "Before:" paragraph and an "After:" paragraph;
   - a short "How";
   - how you tested it;
   - the Railway docs page for the address header;
   - anything not done.
3. **Changelog.** Add a CHANGELOG.md entry under [Unreleased].
4. **Stop.** No merge and no further PRs. Report the PR link and anything unfinished.
