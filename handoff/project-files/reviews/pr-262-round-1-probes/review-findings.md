# PR #262 "Site D0: API base for the website": review round 1

**Reviewed:** 7970317, the PR's own change on top of engine PR 1 (`git diff 201e01e 7970317`). Method:
- the built-in code-review at high effort, plus clauDNA review-dimensions and severity-categories;
- a by-hand read of every new module and test against the brief (`build-briefs/site-d0.md`);
- 16 probe tests and 7 mutations.

**Result: one blocker, three should-fix, eight nits and four questions.**
- **The blocker:** `/healthz` is the one path the rate limit never touches, and every call takes a connection from the API's own 5-connection pool. With about 200 requests in flight, one visitor makes the real health check return 503 and slows every API request by about 25 times.
- **The rest is sound.** The limiter, the error shape, CORS, paging, the cursor, settings and secrets, and the deletions all held up under probing. See "Checked and dropped".

## Where it stands at 7970317

- **Checks:**
  - ruff, ruff format and mypy (strict) are clean.
  - The engine's pytest passes 138/138 in 71.8 s, and the web tests pass 51/51.
  - The probes pass 16/16 (`$SP/review-262-r1/review/`).
- **Old suite:** under `shit_tests/pytest.ini` it now collects 1930 tests, which is the 2035 at 201e01e minus the 105 deleted, with no new collection error. The `engine/tests` collection error under that ini (no alembic in the old venv) already exists at 201e01e.
- **CI:** the only workflow is `.github/workflows/engine.yml`, and nothing in it references the deleted paths.

Paths: `$SP` = `/tmp/claude-0/-home-user-shitpost-alpha/aa37c4ca-915a-53be-b149-d37cd9089ba3/scratchpad`.
- Probes: `$SP/review-262-r1/review/test_probe_*.py`.
- To run the probes against a checkout: `$SP/review-262-r1/run_probes.sh [-w <checkout>] <probe paths>`.
- To run one mutation against a probe: `$SP/review-262-r1/mutate_probe.sh`.
- To run one mutation against the PR's own web tests: `$SP/review-262-r1/mutate.sh`.
- Both mutation scripts expect a scratch checkout at `$SP/review-262-r1-mut`. I removed it after the run; to rerun, recreate it with `git worktree add --detach $SP/review-262-r1-mut 7970317`.

---

## Blocker

### B1. One visitor can starve the API's pool and fail the health check through the unlimited `/healthz`

**Where:**
- `engine/engine/web/health.py:22-35`: every call runs `db.connect()` plus `SELECT 1`.
- `engine/engine/web/ratelimit.py:13`: `UNLIMITED_PATHS = {"/healthz"}`.
- `engine/engine/web/app.py:40`: one engine shared with the API.
- `engine/engine/web/db.py:17-22`: `pool_size=5`, `max_overflow=0`.

**Problem:**
- `/healthz` is exempt from the limiter, as the brief requires. But each call checks a connection out of the same 5-connection pool the `/api/v1` routes use. With `pool_pre_ping`, that is a ping, the `SELECT 1` and the rollback on return.
- So the one path a visitor can call without limit is also a database round trip, on the connections the API needs. Every other path is cut off at the 30-request burst; the probe shows the same flood against `/api/v1` getting 429 after 30.

**Failure scenario:**
- An anonymous client keeps a few hundred `/healthz` requests in flight from one address. None of them is limited.
- The pool's queue fills with health checks that each wait up to 2 s. API requests queue behind them and take about 2 s per checkout instead of about 0.08 s.
- The engine's outside check, which calls `/healthz` every minute from the shadow week, gets `{"ok": false}` 503 while the database is healthy. So does Railway's deploy-time health check if the flood runs during a deploy.
- Each timed-out health check also logs a WARNING: about 590 lines in 6 s in the probe.
- **Production numbers:** RTT to Neon is about 1 to 3 ms, against 20 ms in the probe. The pool then clears roughly 500 to 800 health checks a second, so the same effect needs about 10 times the concurrency, which one machine can still supply. This is the cheapest way to deny the site's database that the limiter leaves open.

**Evidence:** `test_probe_healthz_flood.py` uses a localhost proxy that adds 20 ms to each database reply, with the default pool of 5. Three runs:
- Baseline API request: 0.08 s.
- One visitor runs 200 concurrent `/healthz` loops for 6 s:
  - about 700 requests, about 590 of them 503, and 0 of them 429;
  - an API request from another visitor takes **2.21 s** (27 times the baseline);
  - a separate checker's `/healthz` gets **503**.
- The same visitor on an `/api/v1` path gets 30 x 200, then 429.

**Fix (small, within the brief's letter):**
- Give `/healthz` its own engine with `pool_size=1` (`make_web_engine` with an override), so it can never take an API connection.
- Make it single-flight: concurrent callers await one in-flight `SELECT 1` task, through `asyncio.shield` on a stored task. Optionally keep the result for about 1 s.
- A flood then costs at most one round trip at a time on a connection the API doesn't use.
- Add a test: N concurrent `/healthz` produce one query, and an API request's latency is unchanged under a `/healthz` flood (the probe, inverted).
- **Side effect:** API load can no longer make `/healthz` report the database as down. Today, 5 slow API requests do exactly that. Say in the README which meaning is intended.

---

## Should-fix

### F1. The no-prices guard misses `prices`, plurals in general, `ohlcv`, and routes left out of the schema

**Where:**
- `engine/tests/web/test_no_prices.py:13-14` (`PRICE_TOKENS`), `:21-24` (`tokens`) and `:49-51` (only `schema["paths"]` is walked).
- `engine/engine/web/router.py:18-24`: `ApiRouter` accepts `include_in_schema=False`.

**Problem:** tokens are matched exactly, so the guard flags none of these:
- the most natural name for a list of prices, `prices`;
- `closes`, `opens`, `highs`, `lows`, `volumes`, `bids` and `asks`;
- `ohlcv`.

A route declared with `include_in_schema=False` is absent from the OpenAPI schema, so the walk never sees it, though it is live under `/api/v1`. A `serialization_alias` also hides a price field.

**Failure scenario:** N2 or D1 adds `class Chart(ApiResponse): prices: list[float]`, or a debug route with `include_in_schema=False` that returns `close_price`. CI stays green, and raw prices go public. That breaks the plan's "% moves only" rule, which this test exists to guard.

**Evidence:** `test_probe_no_prices.py`, 3 tests, all passing:
- A model with `prices`, `closes`, `opens`, `volumes`, `bids` and `asks`, plus a nested model with `ohlcv`, `highs` and `lows`: `price_fields(...) == set()`.
- An `include_in_schema=False` route: `price_fields(...) == set()`, while `GET /api/v1/quote` returns 200 with `close_price: 187.23`.
- `close_price` with `serialization_alias="c"`: not flagged.

**Fix:**
- Also match each word with its trailing `s` removed (`word.removesuffix("s")`), and add `ohlcv`. No current token collides: `status` becomes `statu` and `has` becomes `ha`.
- Have `ApiRouter.add_api_route` refuse `include_in_schema=False`, so every `/api/v1` route is in the schema the guard walks.
- Optionally walk `model_fields` names and aliases instead of the schema.
- Extend `test_the_check_catches_a_price_field` with `prices` and an `include_in_schema=False` route.

### F2. The busy-pool behaviour is unpinned: three mutations pass the PR's suite

**Where:**
- `engine/engine/web/errors.py:109`: `PoolTimeoutError` → `unavailable`.
- `engine/engine/web/db.py:20-21`: `max_overflow=0` and `pool_timeout=5`.
- The README promises "503, when the database is down or every connection is busy" (`engine/README.md:116`).

**Problem:** no test exercises a full pool.

**Failure scenario:** a refactor drops the `PoolTimeoutError` handler, or raises `max_overflow` or `pool_timeout`.
- Without the handler, a busy pool becomes a 500 `internal` with a logged traceback, not a 503.
- With more overflow, the "fixed pool of 5" against Neon's connection limit is gone.
- With `pool_timeout=30`, requests hang for 30 s.

The suite stays green in every case.

**Evidence:**
- Each mutation passes the PR's own web tests 51/51: M2 removes the handler, M5 sets `max_overflow=10` and M6 sets `pool_timeout=30`.
- `test_probe_busy_pool.py` has `pool_size=1`, one request holding the connection for 7 s, and a second request. It passes at 7970317 (503 `unavailable` after 5.0 s) and fails under each mutation:
  - M2: 500;
  - M5: 200, no wait;
  - M6: 200 after the holder releases.

**Fix:** add that test (the probe is ready to drop into `tests/web/`).

### F3. The response cache's size bound is unpinned

**Where:** `engine/engine/web/cache.py:38-39`, the `MAX_ENTRIES` loop.

**Problem:**
- Expired entries are never purged; they are only replaced when the same key is asked for again. The `MAX_ENTRIES` loop is the only bound on memory, and the key is the raw query string.
- Removing the loop passes the PR's suite (M3: 51/51).

**Failure scenario:** after a refactor drops or breaks the loop, every distinct `?x=N` adds an entry forever. N2's change feed is the first user.

**Evidence:**
- M3: 51/51 pass with the loop removed.
- `test_probe_nits.py::test_the_cache_stays_bounded` (fill 356 keys, expect 256) passes at 7970317 and fails under M3 (`356 == 256`).

**Fix:** add that test next to the cache tests.

---

## Nits

### N1. A trailing slash redirects to `http://`

**Where:** `engine/engine/web/app.py:32-39` and `engine/engine/cli.py:89`. Starlette's `redirect_slashes` is on by default, and `proxy_headers=False`.

**Problem:** behind Railway's TLS edge the app sees `http`. So `GET /api/v1/openapi.json/` answers `307 Location: http://shitpostalpha.com/api/v1/openapi.json`. That is a downgrade hop, and a cross-origin `fetch` from an https page fails it as mixed content.

**Evidence:** `test_probe_nits.py::test_a_trailing_slash_redirects_to_plain_http` starts a real `python -m engine web` and sends `Host: shitpostalpha.com` and `X-Forwarded-Proto: https`.

**Fix:** `FastAPI(..., redirect_slashes=False)`, so a trailing slash is the JSON 404.

### N2. Cross-origin scripts can't read `Retry-After`

**Where:** `engine/engine/web/policy.py:23` and `engine/engine/web/ratelimit.py:101`.

**Problem:** `Retry-After` isn't a CORS-safelisted response header, and no `Access-Control-Expose-Headers` is sent. Another origin's script sees the 429 but not when to retry.

**Evidence:** `test_retry_after_is_hidden_from_cross_origin_scripts`.

**Fix:** add `Access-Control-Expose-Headers: Retry-After` to `OPEN_CORS`.

### N3. The unhandled-error log line can be forged through the path

**Where:** `engine/engine/web/policy.py:56`.

**Problem:** the access line escapes the path (`printable`), but `log.exception("unhandled error on %s %s", method, path)` logs `scope["path"]` raw. A `%0A` in a path parameter of a route that raises therefore writes a fake log line.

**Evidence:** `test_error_log_lines_can_be_forged_through_the_path`. errors.py's "database unavailable on %s" is safe: `request.url.path` goes through `urlsplit`, which strips newlines.

**Fix:** compute `printable` once at the top and use it in both lines.

### N4. An unusable header silently puts every visitor in one bucket

**Where:** `engine/engine/web/ratelimit.py:69-75` and `engine/engine/web/settings.py:21`.

**Problem:** if the header is missing, too short for `trusted_hops`, or unparseable, the key falls back to the socket address. Behind Railway that is the edge, so every visitor shares one bucket, the bug this PR fixes, and nothing is logged. Ways to get there:
- an `ip:port` value;
- a typo, or a trailing space, in `WEB_CLIENT_IP_HEADER` (only `min_length=1` is checked);
- `WEB_TRUSTED_HOPS=2` with the single-valued `X-Real-IP`.

The brief asks for the fallback; the silence is the problem.

**Evidence:** `test_an_unusable_edge_value_silently_puts_everyone_in_one_bucket`:
- visitor 2 is locked out by visitor 1's requests, with no WARNING;
- `client_ip_header="X-Real-Ip "` is accepted and does the same.

**Fix:**
- Validate the header name as an HTTP token.
- Log a WARNING at most once every few minutes when a request from a non-loopback socket has no usable header entry.

### N5. A cache hit near expiry still sends `max-age=ttl`

**Where:** `engine/engine/web/cache.py:40-44`.

**Problem:** a hit 4.9 s into a 5 s entry says `max-age=5`, so browsers can show the body for nearly twice the ttl after it was built. For N2's 5 s change feed, that is up to about 10 s of staleness.

**Evidence:** `test_a_cache_hit_near_expiry_still_says_max_age_ttl`.

**Fix:** send `max-age=ceil(expires - now)`.

### N6. Cached bodies ignore serialization aliases

**Where:** `engine/engine/web/cache.py:35`.

**Problem:**
- `model_dump_json()` uses field names; FastAPI's own path uses `by_alias=True`. One model therefore comes out in two shapes, and the cached one doesn't match the schema.
- It is latent today, since no model uses aliases.

**Evidence:** `test_a_cached_body_ignores_serialization_aliases`: the plain route gives `publicId` and the cached route gives `public_id`.

**Fix:** `model_dump_json(by_alias=True)`, or forbid aliases on `ApiModel`.

### N7. On a silent database, an API request hangs 10 s

**Where:** `engine/engine/web/db.py:17-22`, which inherits `CONNECT_TIMEOUT_SECONDS = 10` from `engine/engine/db.py:27`.

**Problem:**
- `/healthz` gives up at 2 s, but a route waits out the engine's 10 s connect timeout per address before its 503.
- The module docstring's "longest a request waits" (5 s) covers only the pool queue.

**Evidence:** `test_probe_silent_db.py`: 503 after 10.0 s.

**Fix:** pass a shorter `connect_timeout` for the web engine (about 3 s), or bound each request's database time.

### N8. Docs still describe the deleted site

**Where:** `README.md:174-176` and `AGENTS.md:14`, `:17`, `:19` and `:27`.

**Problem:**
- `README.md:174-176` still advertises "React 19 + TypeScript single-post feed …" under Performance Dashboard. It describes `frontend/` and is in scope of the brief's "update the parts that describe api/ and frontend/".
- AGENTS.md:
  - `:14` and `:19` still talk about "the dashboard";
  - `:17` says the VM's Python 3.12 "works fine";
  - the new `:27` tells agents to run `python -m engine web`, but the engine needs Python ≥ 3.13 (`pip install -e engine` refuses on 3.12).

**Fix:**
- Point README `:174-176` at the web service, or drop it.
- In AGENTS.md `:27`, say "in a Python 3.13 venv after `pip install -e "engine[dev]"`".

---

## Questions

### Q1. Does Railway's edge overwrite an `X-Real-IP` the visitor sends?

**Where:** `engine/engine/web/settings.py:21-27` and `engine/engine/web/ratelimit.py:57-75`.

**Why it matters:**
- The anti-spoofing guarantee rests on the edge replacing a client-sent `X-Real-IP`, or at least appending its own line after the client's. The cited line ("X-Real-IP for identifying client's remote IP") says the edge sets it, but not that a client value is discarded.
- If the edge passes the client's value through, any visitor gets unlimited buckets (a fresh forged address per request) and can lock out a chosen victim by forging the victim's address.
- I could not check the docs (no outbound calls in this review), and the PR body wasn't readable here.

**Proposed check:** a black-box test on the first deploy, before DNS, that needs no code. From one machine, against the `*.up.railway.app` URL:

      for i in $(seq 1 31); do curl -s -o /dev/null -w "%{http_code}\n" \
        -H "X-Real-IP: 203.0.113.$i" https://<service>.up.railway.app/api/v1/x; done

- 30 x 404, then 429: the edge overwrites, and the default is safe.
- 31 x 404: the header is spoofable; switch the setting.
- Repeat with two `-H "X-Real-IP: …"` lines.
- Put this in the PR body or in D1's deploy steps.

### Q2. How will the production `web` role be made, and should the process check its own privileges?

**Where:** `engine/README.md:70` ("the engine database as the web role") and `engine/engine/web/db.py`.

**Why it matters:**
- The "web never reads prices" rule holds only if the role has nothing beyond `WEB_GRANTS`.
- Roles made in Neon's console or API are, as I recall, members of `neon_superuser`, which carries broad predefined data roles. That is from memory and not verified here. If so, `WEB_GRANTS` stops mattering.
- Nothing in the web process notices an over-privileged role.

**Evidence:** `test_probe_web_role.py::test_nothing_checks_that_the_production_role_is_least_privilege`. The test grants the role `pg_read_all_data`. The app starts, `/healthz` says ok, and the role reads `prices.market_bars.close`.

**Suggestion:**
- Create the role with SQL (`CREATE ROLE web LOGIN PASSWORD …`), and say so in D0's README; PR 7's SETUP.md repeats it.
- Have the web process check its role on first connect, and refuse to serve or log an ERROR if any of these hold:
  - `rolsuper`, `rolcreaterole`, `rolcreatedb` or `rolbypassrls`;
  - `pg_has_role(current_user, 'pg_read_all_data', 'MEMBER')`;
  - `has_schema_privilege('prices', 'USAGE')`.

### Q3. Should the web role read `engine.job_runs.error` and `engine.engine_lease`?

**Where:** `engine/tests/web/test_web_role.py:10`, and `WEB_GRANTS` `"engine.*": "SELECT"` (PR 1, `engine/engine/migrate.py:58-62`).

**What the probe shows:**
- The test is named "reads engine_meta and nothing else".
- The role also reads job error text, the lease holder and `alembic_version`.
- It can create TEMP tables (a write; PUBLIC has TEMP by default).
- It can connect to other databases on the same server (PUBLIC has CONNECT).

`error_text` stores raw exception strings. httpx's `HTTPStatusError` text includes the full URL, query string and all, so any engine job that puts a key in a URL lands it where the web role can read it.

**Evidence:** `test_the_web_role_reads_more_than_engine_meta` reads back `…?apikey=SECRETKEY` from `engine.job_runs`.

**Suggestion:**
- Rename the test to what it proves, or narrow `WEB_GRANTS` to per-table entries in PR 1's line of work.
- Revoke `TEMP` (and `CONNECT` on other databases) from PUBLIC in the setup steps.

### Q4. Is one per-address budget right for every path?

**Where:** `engine/engine/web/ratelimit.py:13` and `:97-99`.

**Why it matters:**
- The limit covers every path but `/healthz`, so D1's pages and static assets will share the visitor's 120 a minute plus 30 burst with the API.
- Mobile carriers' CGNAT, offices and campuses put many people behind one IPv4. A viral post sends exactly that traffic.

**Suggestion:** decide now whether D1's static assets bypass the limiter or get their own budget, so D1 doesn't discover it under load.

---

## Mutations (each against the PR's own web suite, `tests/web` + `test_links.py`, 51 tests)

| # | Mutation | PR suite | Probe that catches it |
|---|---|---|---|
| M1 | db.py: drop `dbapi_connection.commit()` | **caught** (`test_web_role`) | |
| M2 | errors.py: drop the `PoolTimeoutError` handler | 51/51 pass | `test_probe_busy_pool` (500) |
| M3 | cache.py: drop the `MAX_ENTRIES` loop | 51/51 pass | `test_the_cache_stays_bounded` |
| M4 | health.py: drop `raise_if_cancelling()` | 51/51 pass | none (low value; see dropped) |
| M5 | db.py: `max_overflow=10` | 51/51 pass | `test_probe_busy_pool` (200) |
| M6 | db.py: `pool_timeout=30` | 51/51 pass | `test_probe_busy_pool` (200) |

## Probes (all pass at 7970317; 16/16 in 29.8 s)

- `test_probe_healthz_flood.py` (2): B1.
- `test_probe_no_prices.py` (3): F1.
- `test_probe_busy_pool.py` (1): F2, a missing pin (fails under M2, M5 and M6).
- `test_probe_nits.py` (7):
  - the redirect (N1);
  - Retry-After (N2);
  - the log line (N3);
  - the silent fallback (N4);
  - max-age (N5);
  - the cache bound (F3, fails under M3);
  - aliases (N6).
- `test_probe_silent_db.py` (1): N7.
- `test_probe_web_role.py` (2): Q2 and Q3.

Each probe makes its own throwaway database and roles through the PR's fixtures. Afterwards there are 0 `web_test_*` roles and 0 `engine_test_*` databases left, and the `engine` role was untouched.

---

## Checked and dropped

**The rate limiter**

- **Spoofing through `X-Forwarded-For` / rightmost-N:**
  - Correct: entries a visitor writes to the left never count, across one header line or several.
  - An unparseable rightmost entry falls back to the socket address and never shifts left.
  - `trusted_hops` is `ge=1`, so `entries[-0]` (the leftmost, visitor-controlled entry) is impossible, and that is tested.
  - Whether Railway overwrites `X-Real-IP` is Q1.
- **No header, several lines, IPv6, malformed values:**
  - 200,000 fuzzed inputs, zone ids (`fe80::1%eth0`), mapped addresses, brackets, ports, NULs, non-ASCII digits and 10 kB strings.
  - `_parse` never raises anything but `ValueError`, which is caught. Latin-1 high bytes are fine.
  - IPv6 is keyed per /64, and mapped IPv4 addresses are unwrapped.
- **Memory:**
  - At 50,000 buckets, the cap, the table takes about 11.6 MB.
  - Idle buckets go once refilled (`burst/rate` = 15 s).
  - Evicting a depleted bucket by LRU gives no attacker more than the 50k keys it already had.
- **Concurrency and clock:**
  - `take()` has no `await`, so it is atomic on the single event loop. The server runs one process.
  - The clock is `time.monotonic`.
  - Denied requests don't spend tokens, and `Retry-After` is the ceiling and at least 1.

**The error shape**

- **Under `/api/`:** 404, 405 (with `Allow`), validation errors (as 400), `ApiError`, `OperationalError` (as 503), `ResponseValidationError` and arbitrary exceptions (as 500) all come back in the shape.
  - Starlette's `ServerErrorMiddleware` sits outside `ResponsePolicy` and never sees a swallowed exception.
  - The validation messages carry no input values.
  - Database errors log type names only.
- **A route returning a subclass instance with an extra field:** the extra field is dropped, not leaked (checked by hand).
- **uvicorn's own 400 for malformed HTTP** lacks the security headers. It comes from outside the app, and browsers don't render it as a page.

**CORS and cache headers**

- **CORS:** `*` on GET under `/api/v1/` only, no credentials, and no CORS on preflight, HEAD, POST or `/healthz`, all as the brief says.
- **Cache headers:**
  - Only the `ResponseCache` 200s carry `public, max-age`.
  - Errors (429, 500 and 503 included) carry none.
  - `/healthz` is `no-store`.
  - Nothing varies by user, since there is no auth.

**Paging and stream_id**

- **Paging:**
  - `limit` is limited to 1..100, and huge or garbage values are a 400.
  - The cursor (200 characters at most) must hold exactly `size` integers within bigint, with no bools, and must re-encode to the identical string. That rejects every alternative spelling, including the characters base64 would discard.
  - Injection is impossible, since the cursor holds integers only.
  - `take_page` is correct at `limit` rows, at `limit + 1` and on an empty list.
- **stream_id:**
  - The 60 s staleness after a rebuild is what the brief asks for ("cached ... about 60 s").
  - A concurrent miss at expiry costs a few cheap reads; that's not worth a lock.

**`/healthz`, the database and settings**

- **What `/healthz` reveals:** only `{"ok": bool}`, with no version and nothing about the database. Its cost is B1.
- **Statement timeout:** it is `5s` on every pooled connection, committed so the pool's rollback keeps it; M1 is caught.
  - Neon's pooled endpoint caveat is documented.
- **Startup and shutdown:**
  - SIGTERM leads to a graceful uvicorn shutdown, the lifespan disposes the pool, and the log ends "Finished server process" (`test_server`).
  - There is no server header, no access log from uvicorn and no visitor address in any log.
  - `create_app` doesn't connect at import.
- **Settings and secrets:**
  - Six malformed `WEB_DATABASE_URL` shapes (bad scheme, bad port, unknown driver, no scheme, `@` in the password, a bad option) never print the password. SQLAlchemy 2.1 omits the URL from parse errors.
  - Bad settings print variable names and messages only (tested).
  - `WebSettings`' repr masks the URL.
  - The web command never builds the engine's `Settings` (tested).

**The deletions**

- **Leftover references:** none in `.github/`, `pyproject.toml`, the root `conftest.py`, `shit_tests/pytest.ini`, `scripts/` or `.claude/`.
- **The only mentions left** are docstrings in `notifications/briefing.py:322` and `notifications/scorecard_service.py:11`, which point to the deleted `railway.json`. That is old code that engine PR 11 deletes, and the brief forbids editing it.
- **The old suite** collects cleanly (see "Where it stands").

**Code-review suggestions not taken**

- **Telegram webhook route deleted:** dropped under the clean-slate rule (the old system is shut down).
- **Old Railway services would fail to deploy:** dropped. The plan merges only after they are deleted, and the PR body says so per the brief.
- **`cli.py` imports the web stack for `run`, `migrate` and `status`:** dropped. It adds 0.12 s of import time, and the coupling is acceptable for one package.
- **No single-flight on `StreamIds` or `ResponseCache`:** dropped. The reads are cheap and a stampede is negligible at these rates.
- **Raw query-string cache key:** dropped. It is bounded by 256 entries (F3 pins that) and by the per-visitor limit.
- **Missing Google-style docstrings:** dropped. That is the old system's CLAUDE.md rule; the engine follows its own conventions, and ruff passes.

**Also dropped**

- **Health's `raise_if_cancelling` (M4):** unpinned, but it is a defensive guard copied from PR 1's pattern, and hard to trigger in a test.
- **`engine/railway.json` picked up by the web service:** the README's reading (a config file doesn't follow the root directory) is consistent with the brief's "no config file". It wasn't re-checked against Railway's docs, since no outbound calls are allowed here.
- **Log volume:** one INFO line per request, 429s included, is the brief's access log. The WARNING storm during a `/healthz` flood is noted under B1.
- **WebSocket scopes skip the limiter:** no websocket implementation is installed and there are no websocket routes.
