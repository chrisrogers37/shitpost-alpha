# PR #262 "Site D0: API base", verify-completion pass, round 1

- Commit under test: `7970317` (the PR's own change is `git diff 201e01e 7970317`; `201e01e` is the current tip of `origin/claude/engine-foundation-k6mh6s`). The PR head on GitHub is `7970317b`, so this pass tested the live head.
- Checkout: `$SP/verify-262-r1-wt` (detached). Mutation tree: `$SP/verify-262-r1-mut`, clean again afterwards. Base tree for the root-suite comparison: `$SP/verify-262-r1-base` (`201e01e`).
- Venv: `/home/user/engine-venv-262` (Python 3.13.14, fastapi 0.142.2, starlette 1.7.0, uvicorn 0.54.0, psycopg 3.3.6, SQLAlchemy 2.1.2). Every command ran under `review-262-r1/verify/clean.sh`, which unsets DATABASE_URL, the *_API_KEY names, ENGINE_*_KEY, ALPACA_*, AWS_*, ENGINE_/WEB_DATABASE_URL and the GH/cloud tokens. No environment values were printed.
- Probes, logs and raw outputs are in `$SP/review-262-r1/verify/`.

**Verdict: the brief is done.** Every item has evidence, CI is green, the suite passes three times, and a real server behaves as specified. There are no blockers. Three should-fix items:
- **V1:** the header tests can't catch a wrong or missing header.
- **V2:** `/healthz` takes 12 s, not 2 s, when a pooled database connection stops answering.
- **V3:** the no-prices guard misses plurals such as `prices`.

---

## 1. Checklist (brief → status → evidence at 7970317)

### 1. Web process
| Requirement | Status | Evidence |
|---|---|---|
| Web app in `engine/engine/web/` (FastAPI) | done | `engine/engine/web/app.py:24` `create_app` |
| fastapi + uvicorn deps, httpx dev | done | `engine/pyproject.toml:12,17,22` |
| `python -m engine web`, uvicorn on 0.0.0.0:$PORT (default 8000), one process | done | `engine/engine/cli.py:82-93`; `settings.py:32` `port` default 8000 via `PORT`. By hand: log shows "Uvicorn running on http://0.0.0.0:<PORT>", one process |
| No server header | done | `cli.py:90` `server_header=False`; by hand: no `server` header on any response (phaseA) |
| uvicorn proxy-header handling off | done | `cli.py:89`; by hand: X-Forwarded-For never changes the bucket; mutation M14 caught |
| `web` loads its own settings, never the engine's (fix for `Settings()` before dispatch) | done | `cli.py:39-45` dispatches `web` before `load_settings(Settings, ...)`. By hand: with only ENGINE_DATABASE_URL set it prints `invalid web settings: WEB_DATABASE_URL: Field required` (exit 2). Test `test_server.py:28-36`; M28 caught |
| `WEB_` prefix: `WEB_DATABASE_URL` (SecretStr, required), rate limit, trusted address header, pool size default 5 | done | `web/settings.py:10,12,16-27,29` |
| Statement timeout ~5 s on every connection | done | `web/db.py:11,23,27-31`. By hand: `pg_sleep(8)` gave 503 `unavailable` after 5.01 s. The test asserts `SHOW statement_timeout` = `5s` (`test_web_role.py:23`); M5 caught |
| Web process never migrates | done | no migrate call under `engine/web/`; `db.py:1` |
| Access log: method, path, status, duration, never the address | done | `web/policy.py:61-64`, `cli.py:91` `access_log=False`. By hand: 199 log lines with no `127.0.0.1`, `198.51.100`, `2001:db8` or password. M27 caught |
| `/docs` and `/redoc` off; schema at `/api/v1/openapi.json` | done | `app.py:35-37`. By hand: `/docs`, `/redoc` and `/openapi.json` give 404; `/api/v1/openapi.json` gives 200. M35 caught |

### 2. `/api/v1` conventions (README "Public API", one module each)
| Requirement | Status | Evidence |
|---|---|---|
| Written in `engine/README.md` under "Public API" | done | `engine/README.md:93-133` |
| Explicit fields: every response a Pydantic model listing its fields | done | `web/models.py:8-19` (`extra="forbid"`); `web/router.py:18-24` refuses a non-`ApiResponse` model. M6 and M7 caught. Only mypy enforces this inside `create_app` (see V5) |
| `stream_id` at the top level, from `engine.engine_meta`, cached ~60 s | done | `web/stream.py:12,28-33`; `deps.py:30-35`. By hand: the body's `stream_id` matches `engine_meta`. M31 caught |
| Lists `{stream_id, items, next_before}`, `?before=&limit=` (default 20, max 100), opaque URL-safe base64 cursor, bad limit/cursor → 400 | done | `web/paging.py:19-76`. By hand: 3 pages walk 50 items in order. limit 0, 101, `abc`, -1 and 1.5 each give 400; bad, padded, float, wrong-size, string, 2**63, non-UTF-8, other-spelling and empty cursors each give 400. M32 and M36 caught |
| Errors `{"error":{"code","message"}}` under `/api/`, never a stack trace or FastAPI's shape, JSON 404 for unknown paths; codes `bad_request`/`not_found`/`rate_limited`+Retry-After/`unavailable`/`internal` | done | `web/errors.py:18-109`, `policy.py:53-60`, `ratelimit.py:100-106`. By hand, each in the error shape with every header: `/api/v1/x`, `/api/v1` and `/api/nope` give JSON 404; 405 keeps `Allow`; FastAPI's 422 becomes 400; 429 has Retry-After; 503 on a stopped database; 500 for `boom` with no details. 405 maps to `bad_request` (Q1). M16-M20 caught |
| Outside `/api/` the same statuses as plain text | done | `errors.py:69-72`. By hand: `/x` gives 404 `Not found`, `POST /healthz` gives 405, 429 is plain text |
| Cache helper: path+query key, `Cache-Control: public, max-age=<ttl>`, only 200s | done | `web/cache.py:14-44`. By hand: two hits gave answer 1 then 1 and another query gave 2; `max-age=5`; a 404 is not cached and has no Cache-Control. M33 and M34 caught |
| CORS: any origin may GET `/api/v1/*` (`*`, no credentials); other methods none | done | `policy.py:23,42-43`. By hand: GET from `https://shitpostalpha.com`, `https://evil.example` and `null` all get `ACAO: *` with no credentials. OPTIONS preflights (GET or POST, any origin) and POST/DELETE get 405 with no `access-control-*`. M21-M23 caught |
| CSP / HSTS (no subdomains or preload) / nosniff / Referrer-Policy on every response | done (behaviour); test weak (V1) | `policy.py:13-21,50`. By hand: all four, compared against the brief's literal strings, on 200, 404 (api and non-api), 405, 429 (api and non-api), 500, 503, `/healthz` and openapi.json. M24-M26 **survived** |

### 3. Rate limit
| Requirement | Status | Evidence |
|---|---|---|
| In-memory token bucket per visitor address; rate a setting (default 120/min + burst 30) | done | `ratelimit.py:17-54`; `settings.py:16-19`. By hand at defaults: 32 rapid requests from one address give 30x404 then 2x429 with `Retry-After: 1` |
| Bucket table bounded by evicting idle entries | done | `ratelimit.py:36-41,49-50` (idle refill, plus an LRU cap of 50 000); `test_rate_limit.py:63-71` |
| 429 with Retry-After; never limits `/healthz` | done | `ratelimit.py:13,98-106`. By hand: 40 `/healthz` calls from a limited address all got 200. M13 and M15 caught |
| Header from Railway's docs; header and trusted hops are settings; docs cited in code and PR; rightmost entry; socket fallback | done; partly unverifiable here | `settings.py:21-27` cites `https://docs.railway.com/networking/public-networking/specs-and-limits` (X-Real-IP, 1 hop), and so does the PR body. `client_address` (`ratelimit.py:57-75`) takes the entry `trusted_hops` from the right across all header lines, with socket fallback. By hand: two X-Real-IP lines `[C, A]` land in A's bucket; `"C, A"` lands in A's; garbage falls back to the socket address; a forged X-Forwarded-For is ignored; IPv6 shares a /64 bucket. This pass may not fetch Railway's docs, so whether the edge overwrites a visitor-sent X-Real-IP is unverified. The PR lists this under "Not done" |

### 4. `/healthz`
| Requirement | Status | Evidence |
|---|---|---|
| `SELECT 1` with a 2 s timeout, `{"ok": true}` 200 / `{"ok": false}` 503, `Cache-Control: no-store`, nothing else | done; timeout not bounded in one case (V2) | `web/health.py:22-35`. By hand: 200 `{"ok":true}` with no-store. A stopped (refused) database gives 503 in 0.00 s and recovers to 200. A silent database on a fresh connection gives 503 in 2.00 s. A database that goes silent while the pool holds a connection gives 503 after **12.00 s** (V2). M29 and M30 caught |

### 5. Link builder
| `engine/engine/links.py`: `SITE_URL`, `signal_url(public_id)` → `https://shitpostalpha.com/s/<id>` | done | `engine/engine/links.py:5-12`; `tests/test_links.py` |
|---|---|---|

### 6. Tests that guard the rules
| Requirement | Status | Evidence |
|---|---|---|
| No prices: OpenAPI walk, tokens split on `_` and camelCase, short allowlist with reasons, passes with no routes, a test router with `close_price` fails it | done; plural gap (V3) | `tests/web/test_no_prices.py:13-76`. M8 and M9 caught. Probe: `prices`, `closes`, `highs`, `lows`, `opens`, `volumes`, `bids`, `asks`, `ohlcv` and `price2` are **missed** (V3) |
| Web role: tests run as a real login role with only WEB_GRANTS; reads `engine_meta`, permission denied on `prices` and any write | done | `tests/web/conftest.py:22-29`, `tests/conftest.py:41-62`, `tests/web/test_web_role.py:10-43`. M1-M4 caught |
| Limiter: two addresses, separate buckets; a forged XFF entry can't move buckets | done | `test_rate_limit.py:74-112`; M10-M12 caught |
| JSON 404 on unknown `/api/v1`; 503 from `/healthz` and a test route when the DB is unreachable; CORS GET only; every header on `/api/v1`, `/healthz` and an error | done; header oracle weak (V1) | `test_api_conventions.py:18-82`, `test_health.py:19-49`, `api_checks.py:8-10` |
| Paging/cache: cursor round-trips, bad is 400; cache serves a second hit without a query, and expires | done | `test_paging_and_cache.py` |
| Test-only code thin and marked | done | `tests/web/routes.py:1`, `tests/web/api_checks.py:1` |

### 7. Deletions
| `api/`, `frontend/`, `shit_tests/api/`, `shit_tests/echoes/test_api.py`, root `railway.json`, `railpack.json` | done | `git ls-files` at 7970317 shows none of them. Root collection: 2035 tests before, 1930 after; the 105 removed are exactly those files' tests; no new collection error (section 4) |
|---|---|---|
| `requirements.txt` untouched | done | `git diff 201e01e 7970317 -- requirements.txt` is empty |
| CLAUDE.md, README.md, AGENTS.md point to `engine/engine/web/` | partly | `CLAUDE.md:89`, `README.md:83,117`, `AGENTS.md:13,20,27-29`. Some stale "dashboard" text remains (V4) |

### 8. README "Web service"
| Start command, `/healthz`, no pre-deploy, `WEB_DATABASE_URL`, root `engine/`, no config-file path | done | `engine/README.md:57-75` |
|---|---|---|

### Delivery
| Requirement | Status | Evidence |
|---|---|---|
| Branch from `claude/engine-foundation-k6mh6s`; no migration | done | parent `201e01e` = `origin/claude/engine-foundation-k6mh6s`; no change under `engine/engine/migrations` |
| Draft PR "Site D0: API base" with merge-order note (after #258, only once the old Railway services are deleted), Before/After, How, tests, Railway docs page, not-done list | done | PR #262 is a draft. Its body has every section. Its "about 2 s" healthz claim holds only for a fresh connection (V2) |
| CHANGELOG under [Unreleased] | done | `CHANGELOG.md:11` (Removed), `CHANGELOG.md:46-51` (Added) |
| CI green | done | GitHub check `check` on 7970317: success; GitGuardian: success |

---

## 2. Command results (from `engine/`, PYTHONPATH = the checkout, keys stripped)

| Command | Result |
|---|---|
| `ruff check .` | `All checks passed!`, exit 0 |
| `ruff format --check .` | `56 files already formatted`, exit 0 |
| `mypy` | `Success: no issues found in 55 source files`, exit 0 |
| `pytest` run 1 (DEV_DATABASE_URL, superuser `shitpost`) | `138 passed in 78.52s`, exit 0 |
| `pytest` run 2 | `138 passed in 80.51s`, exit 0 |
| `pytest` as superuser role `engine` (`postgresql://engine:<redacted>@localhost:5432/postgres`, as in `.github/workflows/engine.yml`) | `138 passed in 80.17s`, exit 0 |
| New tests | 51 (`tests/web` 50, `tests/test_links.py` 1), matching the builder's count |

Role `engine` was used as-is (`rolsuper = t` before and after) and was not altered. No throwaway `engine_test_*` or `web_test_*` databases or roles were left behind by these runs.

---

## 3. By-hand results

Setup: throwaway database `verify262_6cf74416` and LOGIN role `verify262_web_6cf74416`. `python -m engine migrate` ran with `ENGINE_WEB_ROLE` set to that role, then the grants were checked:
- `engine`: USAGE, plus SELECT on all four tables;
- `app`: USAGE;
- `prices`: none;
- no CREATE anywhere.

The web process connected as that role through a local TCP proxy (`pgproxy.py`). Killing the proxy stood in for "Postgres stopped"; its silent mode stood in for "accepts, never answers". The shared sandbox Postgres was never stopped, because other passes were using it. Both the database and the role were dropped afterwards.

- **Phase A**: the real `python -m engine web` (`byhand_A.txt`, `phaseA.log`).
- **Phases B and D**: the real CLI path (`cli.main(["web"])`) with the PR's test routes and one `pg_sleep` route added (`launch_probe.py`, `byhand_BC.txt`, `byhand_D.txt`).
- **Phase C**: SIGTERM while a request is in flight.

| Check | Result |
|---|---|
| `/healthz` | 200 `{"ok":true}`, `no-store`, all 4 security headers, no `server` header, no ACAO |
| `/api/v1` route | `/api/v1/test/query` gives 200 `{"stream_id":<matches engine_meta>,"answer":42}` with ACAO `*`; `/api/v1/openapi.json` gives 200 with `paths: {}` |
| 404 | `/api/v1/x` gives `{"error":{"code":"not_found","message":"Not found"}}` with every header and ACAO; `/x` gives plain-text `Not found` |
| 405 | `POST /api/v1/openapi.json` gives 405 `bad_request` "Method Not Allowed" with `Allow: GET, HEAD`; `POST /healthz` gives plain-text 405 |
| 422 | `limit=abc` gives 400 `bad_request` "limit: Input should be a valid integer, ..." (never a 422) |
| CORS preflight | OPTIONS from an allowed (`https://shitpostalpha.com`) and a disallowed-looking (`https://evil.example`, `null`) origin both give 405 with no `access-control-*`. GET from each gives `ACAO: *` and no credentials. This matches the brief: any origin may GET, and there is no preflight |
| Cache headers | `public, max-age=5` on the cached route, and a second hit is served from memory; nothing on non-cached routes or errors |
| Security headers | all four, equal to the brief's literal text, on every response checked: 200, 404, 405, 429, 500, 503 and healthz |
| Paging | default page has 20 items; limit=100 gives all 50; the cursor `WzMxXQ` (= `[31]`) continues at 30. A tampered but well-formed cursor (`WzMxXQ` rewritten) is accepted, as it should be (it only moves the page). Every malformed variant gives 400 |
| Rate limit, X-Real-IP set | 30 pass, then 429 with Retry-After 1; another address has its own bucket |
| Rate limit, header missing | socket address 127.0.0.1 is the key (shared with "garbage" header values) |
| Rate limit, spoofed | forged X-Forwarded-For is ignored. With two X-Real-IP lines the last wins; in a comma list the rightmost wins. A visitor-sent X-Real-IP is honoured locally because there is no edge (behind Railway, depends on the edge, see Q4) |
| Statement timeout | `pg_sleep(8)` gives 503 `unavailable` at 5.01 s; `pg_sleep(1)` gives 200 at 1.01 s |
| Pool (5) | 7 concurrent 4 s queries: 5 got 200 at 4.0 s and 2 at 8.0 s. `/healthz` during that window gave **503 in 2.00 s** (Q2) |
| DB stopped (proxy killed) | `/healthz` 503 in 0.00 s; API route 503 `unavailable` in 0.00 s; both 200 again after restart |
| DB silent, fresh connection | `/healthz` 503 in 2.00 s |
| DB silent, pooled connection | `/healthz` 503 in **12.00 s** (phase A) and **12.01 s** (phase C). The API route gave 503 after 10.0 s |
| DB silent mid-query | the in-flight API request was still hanging when the client gave up at **45 s** (Q3); it recovered once forwarding resumed |
| SIGTERM | idle with a keep-alive open: exit -15 in 0.21 s. With a 3 s request in flight: 2.62 s, and the request got 200 (graceful). With a healthz waiting on a silent DB: 11.77 s. Log ends `Finished server process` |
| Bad settings | each prints one line on stderr and exits 2, with no password: no WEB_DATABASE_URL; ENGINE URL only; `WEB_TRUSTED_HOPS=0`; `PORT=eighty`; rate, burst and pool set to 0 (one line naming all three); empty URL; empty header |
| Malformed WEB_DATABASE_URL | not a URL, bad port, mysql:// or https:// each give a 31-39 line traceback and exit 1. No password printed. The engine's own commands behave the same (V6) |
| Unreachable DB at start | the process starts. `/healthz` gives 503 with one WARNING line `health check failed: OperationalError`; `/api/v1/x` still gives 404. No password printed. SIGTERM shuts down cleanly. (Engine `migrate`/`status` print one line `could not reach the engine database: ...` and exit 1) |
| Non-latin-1 `WEB_CLIENT_IP_HEADER` | accepted at start. Every rate-limited request then gives 500 (`UnicodeEncodeError` in the log) while `/healthz` stays green (V7) |

---

## 4. Deletion check

- **Tracked files.** `git ls-files` at 7970317 has nothing under `api/`, `frontend/` or `shit_tests/api/`, and no `shit_tests/echoes/test_api.py`, root `railway.json` or `railpack.json`.
- **Live references.** I searched `.github/workflows` (only `engine.yml`), the root `conftest.py`, `shit_tests/pytest.ini`, `scripts/` (SQL only), all `*.py` and the top-level docs, looking for `api/`, `api.main`, `frontend`, `railway.json`, `railpack`, `/api/feed`, `slowapi` and `uvicorn`. No live code imports or runs the deleted paths. There is no root pyproject or Dockerfile. What remains is inert:
  - `requirements.txt:48-51`: the old FastAPI/slowapi pins. The brief says to leave these for engine PR 11.
  - `.gitignore:254`: `frontend/dist/`.
  - Docstrings in old code that mention the deleted root `railway.json`: `notifications/briefing.py:322` and `notifications/scorecard_service.py:11`. The brief forbids editing old code.
  - Historical planning docs under `documentation/` and `docs/`.
- **Old root suite collection** (`/home/user/venv`, every key stripped, collection only):

  | Tree | `pytest --collect-only` (root) | `pytest -c shit_tests/pytest.ini --collect-only` |
  |---|---|---|
  | base `201e01e` | 2035 collected, 1 error | 2035 collected, 1 error |
  | PR `7970317` | 1930 collected, 1 error | 1930 collected, 1 error |

  - The single error is the same before and after: `ERROR engine/tests - ModuleNotFoundError: No module named 'alembic'`. The root venv has no engine dependencies, and root collection walks into `engine/tests`. This was already broken by engine PR 1 and is not caused by D0.
  - The 105 missing tests are exactly the tests in `shit_tests/api/*` and `shit_tests/echoes/test_api.py`.
  - The deletions broke nothing else's collection.

---

## 5. Docs vs code

- **engine/README.md, "Web service" and "Public API".** These match the code: settings and defaults, error table (including 405 and `Allow`), cursor rules, cache, CORS, headers, healthz, log, the link builder and the Neon direct-endpoint note.
  - It says `unavailable` is for "database down or every connection busy". A statement timeout also maps to `unavailable` (measured), which is fine but unstated.
- **CLAUDE.md.** The tree entry for `engine/engine/web/` is correct. Nothing else changed.
- **README.md.** The structure list and tree are updated. Stale text remains:
  - `README.md:174-177` still describes the deleted React 19 single-post feed as a current feature;
  - `:182` says "Browser push alerts via dashboard".
- **AGENTS.md.** The web service, health check and JSON 404 entries are correct. Stale text remains:
  - "test the dashboard" (`:14`);
  - `./venv/bin/uvicorn` (`:17`);
  - the heading "the dashboard requires PostgreSQL" (`:19`);
  - "~1976 tests pass" (`:32`; 1930 are now collected);
  - the root `./venv` it points to cannot run `python -m engine web`, because it has no `alembic`, and AGENTS doesn't say to `pip install -e "engine[dev]"`.
- **`engine/engine/web/models.py:1`.** It says "(create_app checks)", but `ApiRouter` does the check and `create_app` does not (V5).
- **CHANGELOG.** It has an [Unreleased] entry under both Removed and Added.

---

## 6. Mutation results (`review-262-r1/verify/mutate.py`, `mutations.txt`)

Each mutation reverts one guard, runs the tests that should catch it, then restores the file with `git checkout`. The tree was clean at the end.

| Property | Mutations | Result |
|---|---|---|
| Web role least privilege | M1 grant `prices`; M2 grant writes on `engine.*`; M3 grant on `app.*`; M4 tests connect as superuser; M5 statement timeout removed | all **caught** (`test_web_role.py`) |
| No prices / explicit fields | M6 `extra="ignore"`; M7 ApiRouter accepts any model; M8 walker ignores `$ref`; M9 no camelCase split | all **caught**. Separate probe: plural names are missed (V3) |
| Rate-limit key rule | M10 leftmost entry; M11 header ignored; M12 one shared bucket; M13 `/healthz` limited; M14 uvicorn `proxy_headers=True`; M15 no Retry-After | all **caught** |
| Error shape hides internals | M16 ResponsePolicy doesn't catch; M17 503 message includes the driver error; M18 Starlette's 404 text; M19 FastAPI 422 back; M20 OperationalError unhandled | all **caught** |
| CORS | M21 all methods; M22 all paths; M23 credentials | all **caught** |
| Security headers | M24 HSTS gains `includeSubDomains; preload`; M25 Referrer-Policy dropped; M26 CSP weakened to `default-src *` | **SURVIVED**: 50/50 web tests pass (V1) |
| Other | M27 address in access log; M28 web builds engine Settings; M29 healthz 10 s; M30 healthz cacheable; M31 stream_id uncached; M32 any cursor spelling; M33 cache ignores query; M34 cache never expires; M35 docs on; M36 max limit 1000 | all **caught** |

---

## 7. Findings

### Blocker
None.

### Should-fix

**V1. The header tests check the module against itself, so a wrong or missing security header passes.**
- **Where:** `engine/tests/web/api_checks.py:5-10` imports `SECURITY_HEADERS` from `engine/web/policy.py:13-21` and asserts each response matches it. Every header assertion in `test_api_conventions.py`, `test_health.py` and `test_rate_limit.py` goes through this.
- **Problem:** the brief fixes the exact values: CSP text, HSTS "without includeSubDomains or preload", nosniff and the referrer policy. If someone edits or deletes an entry in `SECURITY_HEADERS`, the oracle changes with it.
- **Evidence:** mutations M24 (HSTS gains `includeSubDomains; preload`), M25 (Referrer-Policy removed) and M26 (CSP becomes `default-src *`) all survive: 50 passed.
- **Fix:** put the brief's four literal header/value pairs in `api_checks.py` (or add one test asserting `SECURITY_HEADERS == {...literal...}`) instead of importing the constant.

**V2. `/healthz` answers in about 12 s, not 2 s, when the database stops answering on a pooled connection.**
- **Where:** `engine/engine/web/health.py:26-31`.
- **Problem:** `asyncio.timeout(2)` fires at 2 s. psycopg then handles the cancellation in `AsyncConnection.wait`: `connection_async.py:535-552` sends a server-side cancel (5 s timeout) and then waits another 5 s, so the handler returns only after about 12 s. The brief says `/healthz` uses a 2 s timeout, and the PR body claims "503 in about 2 s from a database that never answers". The PR's test (`test_health.py:38-49`) covers only a fresh connection to a silent port. A refused or stopped database is fine (0.00 s), so the brief's literal check passes.
- **Evidence:**
  - phase A: 503 after 12.00 s;
  - phase C: 12.01 s, and SIGTERM waited 11.77 s for it;
  - an in-process repro with the PR's fixtures (`review-262-r1/verify/test_probe_hung_db.py`) fails `assert elapsed < 3.5` with `took 12.00s` and logs `psycopg ... query cancellation failed: cancellation timeout expired`.
- **Fix:** run the probe as a task and answer from `asyncio.wait({probe}, timeout=2)`. On timeout, call `probe.cancel()` without awaiting the driver's cleanup, and log the failure in a done-callback. Cancel the probe in a `finally` too, if the request itself is cancelled.
  - A sketch is in `review-262-r1/verify/health_fix_sketch.py`. In the mutation tree it made the repro answer 503 in 2.00 s, and `test_health.py`, `test_rate_limit.py` and the repro all passed (13 passed). The tree was reverted afterwards.
  - Add the repro as a test: a healthy `/healthz` first, then the database goes silent.

**V3. The no-prices guard misses plural and suffixed price names, including `prices`.**
- **Where:** `engine/tests/web/test_no_prices.py:13-14` (token set), `:21-24` (`tokens`), `:44` (exact set membership).
- **Problem:** the walk matches whole tokens only. A response field named `prices` (or `closes`, `highs`, `lows`, `opens`, `volumes`, `bids`, `asks`, `ohlcv` or `price2`) passes, and that defeats the guard's purpose ("public output is % moves only"). The brief lists `bar` and `bars` together, so plurals were in view.
- **Evidence:** `review-262-r1/verify/probe_no_prices.py` builds a route with those fields. It caught `PRICE`, `askSize`, `closePrices`, `close_px`, `price_usd` and `vwapUSD`, and missed `prices`, `closes`, `highs`, `lows`, `opens`, `volumes`, `bids`, `asks`, `ohlcv` and `price2` (also `candles`, `quote` and `lastPx`, which are outside the brief's list).
- **Fix:** normalise each token before matching: strip trailing digits, then compare both `word` and `word.removesuffix("s")`. Add `ohlcv` (and optionally `candle`, `px`, `quote`). Add `prices` to `test_the_check_catches_a_price_field`.

### Nit

**V4. Stale references to the deleted dashboard in README.md and AGENTS.md.**
- **Where:**
  - `README.md:174-177` ("Performance Dashboard: React 19 + TypeScript single-post feed ...") and `:182` ("Browser push alerts via dashboard");
  - `AGENTS.md:14` ("test the dashboard"), `:17` (`./venv/bin/uvicorn`), `:19` (heading "the dashboard requires PostgreSQL"), `:32` ("~1976 tests pass"; 1930 are now collected);
  - `AGENTS.md:27` tells agents to run `python -m engine web`, but the root `./venv` it names has no `alembic` and can't import the engine.
- **Problem:** the brief asks for the parts describing `api/` and `frontend/` to point at `engine/engine/web/`.
- **Fix:**
  - point README's dashboard bullets at the web service (or drop them);
  - reword AGENTS' "dashboard" mentions to "web service";
  - add `pip install -e "engine[dev]"` (or "see engine/README.md") to the web-service run line;
  - drop `./venv/bin/uvicorn`.

**V5. `models.py` says `create_app` enforces `ApiResponse`; at runtime only `ApiRouter` does.**
- **Where:** `engine/engine/web/models.py:1`; `engine/engine/web/app.py:24,43-44`.
- **Problem:** at runtime `create_app` mounts a plain `APIRouter`, whose route can return a bare dict with `close_price`, and the no-prices walk sees nothing because a `dict[str, float]` schema has no properties. mypy's typing of `API_ROUTERS: tuple[ApiRouter, ...]` catches this in CI.
- **Evidence:** `review-262-r1/verify/probe_bypass.py` printed `GET /api/v1/raw -> 200 {"close_price":101.5}` and `no-prices walk finds: set()`.
- **Fix:** add `if not isinstance(router, ApiRouter): raise TypeError(...)` in the `create_app` loop, or correct the docstring.

**V6. A malformed `WEB_DATABASE_URL` crashes with a traceback (exit 1) instead of one line (exit 2).**
- **Where:** `engine/engine/web/settings.py:12` accepts any non-empty string. `create_app` → `make_web_engine` → `make_url` raises at start.
- **Evidence:** not-a-URL, a non-numeric port, `mysql://` and `https://` each produce a 31-39 line traceback ending in `ArgumentError`, `ValueError`, `ModuleNotFoundError` or `NoSuchModuleError`, and exit 1. No password appears. Engine PR 1's `ENGINE_DATABASE_URL` behaves the same.
- **Fix:** add a field validator that parses with `make_url` and requires a `postgres`/`postgresql` scheme, raising `ValueError("not a postgresql:// URL")` so `load_settings` prints one line. This could be shared with the engine's Settings later.

**V7. A non-ASCII `WEB_CLIENT_IP_HEADER` is accepted, then turns every rate-limited request into a 500.**
- **Where:** `engine/engine/web/settings.py:21`; `engine/engine/web/ratelimit.py:62` (`header.lower().encode("latin-1")`).
- **Evidence:** with `WEB_CLIENT_IP_HEADER=X-Réal-ÏP€`, `/api/v1/x` gives 500 `internal` and the log shows `UnicodeEncodeError`. `/healthz` is exempt from the limiter, so it stays green and a deploy health check would pass.
- **Fix:** constrain the setting to an HTTP token, e.g. `pattern=r"^[A-Za-z0-9-]+$"`.

**V8. Database-failure warnings log only the exception class.**
- **Where:** `engine/engine/web/health.py:31`; `engine/engine/web/errors.py:102`.
- **Problem:** a wrong web-role password, a missing grant, a refused connection and a timeout all log `health check failed: OperationalError`. The engine's CLI prints the driver's first line (`cli.py:96-101`).
- **Fix:** log the first line of `exc.orig` (as `database_error_line` does), or at least the SQLSTATE.

### Question

**Q1. 405 maps to `bad_request`, with status 405.**
- **Where:** `engine/engine/web/errors.py:84-92`; README table `engine/README.md:113`.
- **Question:** the brief's code table pairs `bad_request` with 400 and lists no 405. Is keeping the closed code set with a 405 status (documented) what the planner wants, or should a `method_not_allowed` code be added? Keeping it looks like the better reading of a closed list.

**Q2. `/healthz` shares the 5-connection request pool, so a busy site reads as down.**
- **Where:** `engine/engine/web/health.py:26`.
- **Evidence:** with 5 slow requests in flight, `/healthz` answered 503 in 2.00 s.
- **Question:** Railway checks health only at deploy, but the engine's outside check calls `/healthz` every minute and would report the site down under load. Is that intended? Alternatives are a dedicated one-connection pool for health, or accepting it as "can't serve".

**Q3. A database that stops answering mid-query holds a request, and a pool connection, with no bound.**
- **Where:** `engine/engine/web/db.py:17-22` (no TCP keepalive or `tcp_user_timeout` connect args) and `engine/engine/cli.py:85-93` (no `timeout_graceful_shutdown`).
- **Evidence:** a request in flight when the proxy went silent was still waiting when the client gave up at 45 s. Five such requests exhaust the pool, so every route gives 503 after the 5 s pool timeout until TCP gives up (minutes on Linux). SIGTERM would wait on them too.
- **Question:** the 5 s statement timeout is server-side and can't help here. Should D0 add libpq keepalives or `tcp_user_timeout` and a uvicorn graceful-shutdown timeout, or leave this for D1/N2? It is rare on Neon.

**Q4. Whether Railway's edge overwrites a visitor-sent `X-Real-IP` is unproven.**
- **Where:** `engine/engine/web/settings.py:21-27`.
- **Status:** this pass may not reach Railway's docs. Locally, a visitor-sent X-Real-IP is honoured because there is no edge. The code takes the last line and rightmost entry, which is safe if the edge overwrites or appends, but not if it forwards a visitor's line after its own.
- **Question:** the PR already lists this under "Not done" for the first deploy (PR 7). Is a one-request check on the first deploy enough (send `X-Real-IP: 192.0.2.1` and confirm it doesn't get its own bucket)?
