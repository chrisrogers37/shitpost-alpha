# PR #262 "Site D0: API base for the website": review round 1

**Reviewed:** 7970317, D0's own change on top of engine PR 1 (`git diff 201e01e 7970317`). Completion was judged against build-briefs/site-d0.md.

**Passes**, each in a fresh agent:
- **simplify:** the built-in simplify lens, report-only, with each change tried on a scratch checkout.
- **review:** the built-in code-review at high effort plus clauDNA review-work. It wrote 16 probes and ran 6 mutations.
- **verify:** clauDNA verify-completion against the brief. It ran 36 mutations and did by-hand runs against a real `python -m engine web` and a local database proxy that can go silent.

I re-ran all 16 review probes (16 pass at 7970317) and the hung-database repro for S2 (503 after 12.01 s) myself.

## Where it stands

- **Checks:**
  - ruff, ruff format and mypy strict are clean.
  - pytest passes 138/138 three times, once as the `engine` role like CI. The 51 new tests match your count.
  - CI is green on 7970317. The only workflow, `engine.yml`, references none of the deleted paths.
  - The old suite now collects 1930 tests: 2035 at 201e01e minus the 105 deleted, with no new collection error.
- **The brief is done.** Every item has evidence; verify's checklist has file:line for each.
- **Held up under probing:**
  - the limiter's key rule, across header lines, IPv6 (/64), mapped addresses and 200,000 fuzzed values;
  - the error shape for every error class, with no input values or driver text;
  - CORS, the cache headers, paging and the cursor (one spelling per key, integers only);
  - settings and secrets: no password in any error, and the web command never builds the engine's Settings;
  - the web role's grants (five mutations caught), and the deletions.

**Result: changes needed.** 1 blocker, 5 should-fix, 11 nits, 4 optional simplifications and 6 questions.

## How to answer

- Fix each blocker and should-fix, or decline it with a reason. Nits and simplifications are optional.
- Push, and send me the head with one line per id.

**Probes:** [pr-262-round-1-probes/](pr-262-round-1-probes/)
- `review/`: `run_probes.sh -w <your checkout> <probe files>` adds `-p tests.conftest -p tests.web.conftest` and strips the keys (edit the venv path in it). Each `test_probe_…` passes while its finding stands.
- `verify/`:
  - `test_probe_hung_db.py` is S2's repro, and `health_fix_sketch.py` the fix it was tried with.
  - `pgproxy.py` is the database proxy that goes silent; `drive.py` and the `phase*.log` files are the by-hand runs.
  - `mutate.py` and `mutations.txt` hold the 36 mutations.
- `simplify/simplify.patch`: the tried simplifications. It applies to 7970317, and the full suite passes with it. One patch per item is next to it.
- The three passes' own write-ups: `review-findings.md`, `verify-findings.md` and `simplify-findings.md`.

Copy the probes into engine/tests/ to run them. Don't commit them as they are, except as tests you adopt.

---

## Blocker

### B1. One visitor can starve the API's pool, and fail the health check, through the unlimited `/healthz` (review B1, verify Q2)

**Where:**
- `engine/engine/web/health.py:22-35`: every call runs `db.connect()` and `SELECT 1`.
- `engine/engine/web/ratelimit.py:13`: `UNLIMITED_PATHS = {"/healthz"}`.
- `engine/engine/web/app.py:40` and `engine/engine/web/db.py:17-22`: one engine with `pool_size=5`, `max_overflow=0`, shared with `/api/v1`.

**Problem:** the brief rightly exempts `/healthz` from the limiter. But each call takes a connection from the API's own pool of 5. So the one path anyone can call without limit is also a database round trip on the connections the API needs.

**Failure scenario:** one anonymous client keeps a few hundred `/healthz` requests in flight.
- None is limited. The pool's queue fills with health checks, each waiting up to 2 s.
- API requests queue behind them.
- The engine's outside check (every minute from the shadow week) and Railway's deploy check get 503 while the database is healthy.
- Each timed-out check logs a WARNING.

At Neon's 1-3 ms round trip the same effect needs about 10 times the concurrency of the probe, which one machine can still supply.

**Evidence:** `review/test_probe_healthz_flood.py`, with a proxy adding 20 ms per database reply and the default pool:
- An API request takes 0.08 s at rest.
- One visitor runs 200 concurrent `/healthz` loops for 6 s: about 700 requests, about 590 of them 503, none 429.
- Meanwhile an API request from another visitor takes **2.21 s**, and a separate checker's `/healthz` gets **503**.
- The same flood on an `/api/v1` path gets 30 x 200, then 429.

Verify found the reverse case too: with 5 slow API requests in flight, `/healthz` answers 503 in 2.00 s, so a busy site reads as down.

**Fix:**
- Give `/healthz` its own engine with `pool_size=1` and `max_overflow=0`, so it never takes an API connection.
- Make it single-flight: concurrent callers wait on one stored probe task (`asyncio.shield`). Optionally keep its result for about 1 s.
- Do this together with S2: callers wait on that task with `asyncio.wait(..., timeout=2)`, not inside it.
- Test both ways: N concurrent `/healthz` calls make one query, and an API request's latency is unchanged under a `/healthz` flood (the probe, inverted).
- Say in the README that `/healthz` means "the database answers", not "the API has a free connection".

## Should-fix

### S1. The no-prices guard misses `prices`, other plurals, `ohlcv`, and routes left out of the schema (review F1, verify V3)

**Where:** `engine/tests/web/test_no_prices.py:13-14` (`PRICE_TOKENS`), `:21-24` (`tokens`), `:44` (exact match) and `:49-51` (only `schema["paths"]` is walked); `engine/engine/web/router.py:18-24`, where `ApiRouter` accepts `include_in_schema=False`.

**Problem:** tokens match exactly, so the guard passes:
- `prices`, the most natural name for a list of prices;
- `closes`, `opens`, `highs`, `lows`, `volumes`, `bids`, `asks`, `ohlcv` and `price2`;
- any field on a route declared with `include_in_schema=False`, which is live under `/api/v1` but absent from the schema the test walks;
- a price field with a `serialization_alias`.

**Failure scenario:** N2 or D1 adds `prices: list[float]` to a response, or a debug route with `include_in_schema=False` that returns `close_price`. CI stays green and raw prices go public, which is the one thing this test guards.

**Evidence:**
- `review/test_probe_no_prices.py` (3 tests). An `include_in_schema=False` route returns `close_price: 187.23` with a 200, and the walk finds nothing.
- `verify/probe_no_prices.py`: the guard caught `PRICE`, `askSize`, `closePrices`, `close_px`, `price_usd` and `vwapUSD`, and missed the names above.

**Fix:**
- Normalise each word before matching: strip trailing digits, then compare both `word` and `word.removesuffix("s")`. Add `ohlcv`. No current token collides.
- Have `ApiRouter.add_api_route` refuse `include_in_schema=False`.
- Either walk model fields and aliases as well, or forbid aliases on `ApiModel` (see N6).
- Add `prices` and an `include_in_schema=False` route to `test_the_check_catches_a_price_field`.

### S2. `/healthz` takes about 12 s, not 2 s, when a pooled connection stops answering (verify V2)

**Where:** `engine/engine/web/health.py:26-31`.

**Problem:** `asyncio.timeout(2)` fires at 2 s. psycopg then handles the cancellation itself: it sends a server-side cancel with a 5 s timeout and then waits another 5 s. The handler returns only after about 12 s. The brief says `/healthz` uses a 2 s timeout, and the PR body claims "503 in about 2 s from a database that never answers". The PR's test only covers a fresh connection to a silent port.

**Evidence:**
- `verify/test_probe_hung_db.py`: a healthy `/healthz` first, then the proxy goes silent. It fails `assert elapsed < 3.5` with "took 12.01s" (I re-ran it), and logs `query cancellation failed: cancellation timeout expired`.
- By hand, SIGTERM waited 11.77 s for one such request.

**Fix:**
- Run the probe as a task and answer from `asyncio.wait({probe}, timeout=2)`.
- On a timeout, cancel the task without awaiting the driver's cleanup, and log its failure from a done-callback.
- With B1's single-flight task, later callers keep getting a 503 in 2 s while the old probe winds down.
- `verify/health_fix_sketch.py` made the repro answer in 2.00 s with the PR's health and rate-limit tests still passing. Adopt the repro as a test.

### S3. The security-header tests check the module against itself (verify V1)

**Where:** `engine/tests/web/api_checks.py:5-10` imports `SECURITY_HEADERS` from `engine/engine/web/policy.py:13-21`, and every header assertion goes through it.

**Problem:** the brief fixes the exact values: the CSP text, HSTS without `includeSubDomains` or `preload`, `nosniff` and the referrer policy. If an entry in `SECURITY_HEADERS` is edited or deleted, the test's oracle changes with it.

**Evidence:** three mutations pass the web suite 50/50:
- HSTS gains `includeSubDomains; preload`;
- `Referrer-Policy` is removed;
- the CSP becomes `default-src *`.

**Fix:** write the brief's four header/value pairs as literals in `api_checks.py`, or add one test asserting `SECURITY_HEADERS == {…literal…}`.

### S4. Nothing tests a full pool (review F2)

**Where:** `engine/engine/web/errors.py:109` (`PoolTimeoutError` → `unavailable`); `engine/engine/web/db.py:20-21` (`max_overflow=0`, `pool_timeout=5`); the README's promise of a 503 "when the database is down or every connection is busy" (`engine/README.md:116`).

**Failure scenario:** a refactor drops the `PoolTimeoutError` handler, or raises `max_overflow` or `pool_timeout`. A busy pool then becomes a 500 with a traceback, or opens more than 5 connections against Neon's limit, or makes requests wait 30 s. The suite stays green in each case.

**Evidence:** removing the handler, `max_overflow=10` and `pool_timeout=30` each pass the web suite 51/51. `review/test_probe_busy_pool.py` (`pool_size=1`, one request holding the connection for 7 s, a second request) gives 503 `unavailable` after 5.0 s at 7970317, and fails under each of the three mutations.

**Fix:** adopt that probe as a test.

### S5. Nothing tests the response cache's size bound (review F3)

**Where:** `engine/engine/web/cache.py:38-39`, the `MAX_ENTRIES` loop.

**Problem:** expired entries are only replaced when the same key is asked for again, so this loop is the only bound on memory, and the key is the raw query string. Removing it passes the web suite 51/51. Once broken, every distinct `?x=N` adds an entry for good. N2's change feed is the first user.

**Evidence:** `test_probe_nits.py::test_the_cache_stays_bounded` (356 keys in, 256 expected) passes at 7970317 and fails with the loop removed.

**Fix:** adopt that test next to the cache tests.

## Nits (optional, file:line at 7970317)

- **N1. A trailing slash redirects to `http://`** (app.py:32-39, cli.py:89; review N1). Behind Railway's TLS edge the app sees `http`, so `GET /api/v1/openapi.json/` answers 307 to `http://…`, a downgrade that an https page's `fetch` refuses as mixed content. **Fix:** `FastAPI(..., redirect_slashes=False)`, so it is the JSON 404. Probe: `test_a_trailing_slash_redirects_to_plain_http`.
- **N2. Cross-origin scripts can't read `Retry-After`** (policy.py:23, ratelimit.py:101; review N2). It isn't a CORS-safelisted header. **Fix:** add `Access-Control-Expose-Headers: Retry-After` to `OPEN_CORS`.
- **N3. The unhandled-error log line can be forged through the path** (policy.py:56; review N3). The access line escapes the path, but `log.exception("unhandled error on %s %s", …)` logs `scope["path"]` raw, so a `%0A` in a path parameter of a route that raises writes a fake log line. **Fix:** compute the escaped path once and use it in both lines.
- **N4. A bad client-IP header setting fails silently or loudly** (settings.py:21, ratelimit.py:62 and :69-75; review N4, verify V7).
  - If the header is missing, too short for `trusted_hops`, or unparseable, every visitor falls back to the edge's address and shares one bucket, with nothing logged. A trailing space in `WEB_CLIENT_IP_HEADER`, or `WEB_TRUSTED_HOPS=2` with the single-valued `X-Real-IP`, does exactly that.
  - A non-ASCII header name is accepted, then makes every rate-limited request a 500 (`UnicodeEncodeError`), while `/healthz` stays green.
  - **Fix:** validate the name as an HTTP token (`^[A-Za-z0-9-]+$`), and log a WARNING at most every few minutes when a request from a non-loopback socket has no usable header entry.
- **N5. A cache hit near expiry still sends `max-age=ttl`** (cache.py:40-44; review N5, simplify N3). A browser can then hold N2's 5 s change feed for about 10 s. **Fix:** `max-age=ceil(expires - now)`.
- **N6. Cached bodies ignore serialization aliases** (cache.py:35; review N6). `model_dump_json()` uses field names while FastAPI uses `by_alias=True`, so one model has two shapes. It's latent: no model uses aliases. **Fix:** `by_alias=True`, or forbid aliases on `ApiModel`.
- **N7. On a silent database, an API request waits 10 s** (web/db.py:17-22, inheriting `CONNECT_TIMEOUT_SECONDS = 10` from engine/db.py:27; review N7). The docstring's "longest a request waits" (5 s) covers only the pool queue. **Fix:** a shorter `connect_timeout` for the web engine (about 3 s). Probe: `test_probe_silent_db.py`.
- **N8. Docs still describe the deleted site** (review N8, verify V4).
  - `README.md:174-177` advertises the React single-post feed, and `:182` "browser push alerts via dashboard".
  - `AGENTS.md:14` and `:19` still say "dashboard", `:17` names `./venv/bin/uvicorn`, and `:32` says about 1976 tests (1930 now).
  - `AGENTS.md:27` says to run `python -m engine web`, but the root venv it names is Python 3.12 without alembic. Point it at a 3.13 venv with `pip install -e "engine[dev]"`, or at engine/README.md.
- **N9. `create_app` accepts a plain `APIRouter` at runtime** (app.py:24 and :43-44, models.py:1; verify V5, simplify N1 and N2). Only mypy enforces `ApiRouter`, and a plain router's route can return a dict with `close_price` that the no-prices walk never sees (`verify/probe_bypass.py`). models.py:1 says "create_app checks". **Fix:** `isinstance` check in the loop, or correct the docstring.
- **N10. A malformed `WEB_DATABASE_URL` crashes with a 31-39 line traceback and exit 1** (settings.py:12; verify V6). No password appears. **Fix:** a validator that parses with `make_url` and requires a postgres scheme, so `load_settings` prints one line and exits 2.
- **N11. Database-failure warnings log only the exception class** (health.py:31, errors.py:102; verify V8). A wrong password, a missing grant, a refused connection and a timeout all read `OperationalError`. **Fix:** log the driver's first line, as PR 1's `database_error_line` does, or at least the SQLSTATE.

## Simplifications (optional; tried, and the suite stays green with each)

The combined patch is `pr-262-round-1-probes/simplify/simplify.patch` (9 files, +37/-43). Details are in `simplify-findings.md`.

- **C1. Paging parameters as a query model** (paging.py:53-68, tests/web/routes.py). Make `PageQuery` a Pydantic model taken with `Query()`, and export `PageParams = Annotated[PageQuery, Query()]`. Routes write `page: PageParams`, and N2 can subclass it for `after`. The OpenAPI output and the 400 messages are unchanged.
- **C2. `@app.exception_handler` instead of `add_exception_handler`** (errors.py:78-109). The decorator types the exception precisely, so the three `assert isinstance` lines (stripped under `python -O`) go.
- **C3. Lazy-import the web stack in cli.py** (cli.py:9 and :23). `run`, `migrate` and `status` currently load FastAPI, Starlette and uvicorn: 770 modules against 592, about 170 ms and 9 MB more for the long-lived engine process.
- **C4. Schema-only tests needn't build a database** (test_no_prices.py:61 and :65, test_api_conventions.py:113). A `NO_DATABASE = WebSettings(database_url="postgresql://unused")` constant saves three databases and migrations per run, about 8% of the web suite.

## Questions

- **Q1. Does Railway's edge overwrite a visitor-sent `X-Real-IP`?** (settings.py:21-27; review Q1, verify Q4). The anti-spoofing guarantee rests on it, and no pass could reach Railway's docs. Your PR body already lists it for the first deploy. A check that needs no code, from one machine against the `*.up.railway.app` URL before DNS:

      for i in $(seq 1 31); do curl -s -o /dev/null -w "%{http_code}\n" \
        -H "X-Real-IP: 203.0.113.$i" https://<service>.up.railway.app/api/v1/x; done

  30 x 404 then a 429 means the edge overwrites. 31 x 404 means the header is spoofable. Is it worth putting this line in the PR body so PR 7's SETUP.md picks it up?
- **Q2. How will the production `web` role be made?** (README:70, web/db.py; review Q2). The no-prices rule holds only if the role has nothing beyond `WEB_GRANTS`. Roles made in Neon's console may belong to `neon_superuser` (from memory, unverified), and the web process wouldn't notice: `test_probe_web_role.py` grants `pg_read_all_data`, and the app starts, says ok and reads `prices.market_bars.close`. Should the README say to create it with `CREATE ROLE web LOGIN …`, and should the process refuse to serve (or log an ERROR) if its role is a superuser, can create roles or databases, bypasses RLS, has `pg_read_all_data`, or has `USAGE` on `prices`?
- **Q3. Should the web role read `engine.job_runs.error` and `engine.engine_lease`?** (tests/web/test_web_role.py:10; `WEB_GRANTS` `"engine.*": "SELECT"` from PR 1's migrate.py:58-62; review Q3). The test is named "reads engine_meta and nothing else", but the role also reads job error text, the lease holder and `alembic_version`, can create TEMP tables, and can connect to other databases (PUBLIC defaults). Error text holds raw exception strings, and httpx's include the full URL: the probe reads back `?apikey=SECRETKEY` from `engine.job_runs`. Either rename the test to what it proves, or narrow the grants to named tables, and revoke TEMP and CONNECT from PUBLIC in the setup steps.
- **Q4. Is 405 with the code `bad_request` what you want?** (errors.py:84-92, README:113; verify Q1). The brief's closed code list has no 405. Keeping the closed set with a documented 405 status looks like the better reading; just confirm it was deliberate.
- **Q5. Should a database that stops answering mid-query be bounded?** (web/db.py:17-22, cli.py:85-93; verify Q3). The 5 s statement timeout is server-side and can't help. A request in flight when the proxy went silent was still waiting at 45 s, and five of them exhaust the pool until TCP gives up, minutes on Linux. SIGTERM waits on them too. Options: libpq keepalives or `tcp_user_timeout`, and uvicorn's `timeout_graceful_shutdown`. Rare on Neon; D0 or later is your call.
- **Q6. Should D1's pages share the API's per-address budget?** (ratelimit.py:13 and :97-99; review Q4). Every path but `/healthz` is limited, so D1's pages and static assets will share 120 a minute plus 30 burst with the API, and carrier NAT puts many readers behind one IPv4. Worth deciding now whether static assets bypass the limiter or get their own budget.

## Dropped

- **The deleted Telegram webhook route, and old Railway services failing to deploy:** the clean-slate rule, and the plan merges D0 only after those services are gone, as the PR body says.
- **No single-flight on `StreamIds` or `ResponseCache`, and the raw query-string cache key:** the reads are cheap, and S5 pins the bound.
- **uvicorn's own 400 for malformed HTTP lacks the security headers:** it comes from outside the app, and browsers don't render it.
- **Health's `raise_if_cancelling` is unpinned:** a defensive guard from PR 1's pattern, hard to trigger in a test.
- **`notifications/briefing.py:322` and `scorecard_service.py:11` still mention the deleted `railway.json`:** old code that engine PR 11 deletes; the brief forbids editing it.
- **Missing Google-style docstrings:** that's the old system's rule; ruff passes.
- **WebSocket scopes skip the limiter:** no websocket support is installed and there are no websocket routes.
