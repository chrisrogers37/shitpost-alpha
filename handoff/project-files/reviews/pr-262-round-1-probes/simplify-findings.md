# PR #262 r1: simplify pass (commit 7970317, "Site D0: API base")

Report only. The PR was not changed. All trial edits were made in
`scratchpad/simplify-262-r1` (detached at 7970317).

**Combined patch:** `scratchpad/review-262-r1/simplify/simplify.patch`
- 9 files, +37 / -43.
- Per-finding patches are next to it as `step-S-*.patch`.

**Verification** (from `engine/`, venv 262, secrets stripped):
- `ruff check .`, `ruff format --check .` and `mypy` (strict) are all clean with the full patch applied.
- `pytest tests` passed 138 tests. That includes `test_server.py`, which starts a real `python -m engine web` process, and `test_processes.py`.

**Overall:** `engine/web` is already lean.
- No dead code: every public name is referenced.
- No function is over about 25 lines.
- No extra database round trips per request beyond SQLAlchemy's pre-ping.
- The module split follows the brief's "a small module for each" convention.

The findings below are modest, ranked by value.

---

## S1. Paging parameters as a FastAPI query model, with a `PageParams` alias

**Where:**
- `engine/engine/web/paging.py:53-68`: the `@dataclass PageQuery` plus the `page_query()` dependency.
- `engine/tests/web/routes.py:3-5,12,57-60`: where it is used.

**Problem:** Two pieces describe one set of parameters.
- A dataclass holds the values.
- A separate function re-declares each field with `Query(...)` and builds the dataclass.

Every list route then has to spell out `page: Annotated[PageQuery, Depends(page_query)]`. The deps module, by contrast, gives `Db` and `StreamId` as one-word aliases. N2 also needs to add `after`, `head_seq` and `has_more`, so it would need a second dependency function that repeats the pattern.

**Fix:** Make `PageQuery` a Pydantic model and take it as a query model. FastAPI has supported this since 0.115, which is the floor in `pyproject.toml`.

```python
class PageQuery(BaseModel):
    """?before=<cursor>&limit=. Take it as a `page: PageParams` parameter."""

    before: str | None = Field(default=None, max_length=200)
    limit: int = Field(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)

    def before_key(self, size: int) -> SortKey | None: ...  # unchanged

PageParams = Annotated[PageQuery, Query()]
```

- Routes then write `page: PageParams`.
- N2 can extend it with `class FeedQuery(PageQuery): after: ...`.
- One line in the README "Lists" section changes to say so.

**What stays the same** (checked in the generated OpenAPI):
- The parameters: `before` with maxLength 200, and `limit` from 1 to 100, default 20.
- The responses: still `200`, `4XX` and `5XX`, with no 422.
- The 400 messages still name `limit` or `before`.

**Lines saved:** 7 net (-17 / +9 including routes.py and the README line). Each future list route signature also gets shorter.

**Verified green.**

## S2. Register the error handlers with `@app.exception_handler` and drop three `assert isinstance`

**Where:** `engine/engine/web/errors.py:78-109`, with the asserts at lines 79, 84 and 95.

**Problem:**
- The handlers are typed `exc: Exception` only so that `app.add_exception_handler` type-checks. Starlette types it as `(Request, Exception)`.
- Each handler then narrows the type with a runtime `assert isinstance(...)`, and `python -O` would strip those asserts.
- The five `add_exception_handler` lines at the bottom also repeat which handler goes with which exception.

**Fix:** Use FastAPI's decorator. It is typed with `DecoratedCallable`, so mypy strict accepts the precise exception types:

```python
@app.exception_handler(ApiError)
async def api_error(request: Request, exc: ApiError) -> Response: ...

@app.exception_handler(OperationalError)  # refused, lost, timed out
@app.exception_handler(PoolTimeoutError)  # every connection busy
async def unavailable(request: Request, exc: Exception) -> Response: ...
```

The behaviour is identical.

**Lines saved:** 4 (-11 / +8).

**Verified green.**

## S3. Lazy-import the web stack in `cli.py`

**Where:** `engine/engine/cli.py:9` (`import uvicorn`) and `engine/engine/cli.py:23` (`from engine.web.app import create_app`).

**Problem:** Both imports are at module level. So every engine command loads FastAPI, Starlette, uvicorn and the whole `engine.web` package without using them:
- `python -m engine run`, the long-lived engine process;
- `migrate`, the Railway pre-deploy step;
- `status`.

**Cost**, measured five times each by importing `engine.cli` in the venv:

| | Before | After |
|---|---|---|
| Modules loaded | 770 | 592 |
| Import time | about 520-580 ms | about 370-410 ms |
| Peak RSS | 74 MB | 65 MB |

The spawned heavy-job children are not affected. multiprocessing does not re-run a package's `__main__`, so they never import `cli`.

**Fix:** Move the two imports into `serve_web()` with a one-line comment. `WebSettings` stays at the top, because `main()` needs it and it is cheap.

**Lines saved:** 0. This is an efficiency fix.

**Verified green.** That includes `test_server.py`, which runs the real server process, and `test_processes.py`.

## S4. Tests that only read the schema needn't build a database

**Where:**
- `engine/tests/web/test_no_prices.py:61` and `:65`;
- `engine/tests/web/test_api_conventions.py:113`.

**Problem:** These three tests take `web_settings`. That fixture creates a throwaway database and a login role, then runs Alembic (about 0.28 s each). But the tests only call `create_app(...)` and read `app.openapi()`, and the app never connects. `test_rate_limit.py:16` already uses `WebSettings(database_url="postgresql://x")` inline for the same reason.

**Fix:**
- Add one constant to `tests/web/conftest.py`: `NO_DATABASE = WebSettings(database_url="postgresql://unused")`, with a one-line docstring.
- Use it in those three tests and in `test_rate_limit.py:16`.

This saves three databases, three role setups and three migrations per run: about 0.85 s, roughly 8% of the web suite. The tests can also run without Postgres.

**Lines saved:** -2 (one constant added). The gain is speed, not lines.

**Verified green.**

---

## Noticed in passing (not simplifications)

**N1. The router check is type-only in `create_app`.** `create_app` accepts a plain `APIRouter` at runtime (`app.py:24,43-44`). Only mypy enforces `Sequence[ApiRouter]`.
- I checked it: a plain router whose route returns `dict[str, float]` with `close_price` mounts under `/api/v1`.
- The no-prices test can't see it either, because a dict schema has no `properties`.
- FastAPI 0.142 (installed) includes routers lazily, as `_IncludedRouter`. So `ApiRouter.add_api_route` (`router.py:18-24`) is the only runtime guard. It still holds for routes defined on an `ApiRouter`.
- **Cheap fix:** in the `create_app` loop, add `if not isinstance(router, ApiRouter): raise TypeError(...)`. That is 2 lines.

**N2. Stale docstring.** `engine/engine/web/models.py:1` says "(create_app checks)", but the check lives in `ApiRouter` (`router.py`). It should name `ApiRouter`.

**N3. `max-age` on cache hits.** `cache.py:43` sends `Cache-Control: public, max-age=<ttl>` on every hit, including one served with 1 s of its in-process TTL left. A browser or proxy can then hold the body for up to about 2×ttl: 10 s for N2's 5 s change feed. This matches the brief's wording. If N2 cares, send the remaining time instead: `math.ceil(expires - now)`.

---

## Checked and fine

- **Module layout.** The brief asks for "a small module for each" convention. Only `db.py` (31 lines) could fold into `deps.py`, which is marginal.
- **`ResponsePolicy` catching unhandled exceptions itself.** This is needed. Starlette's `ServerErrorMiddleware` sits outside user middleware, so a 500 from an `Exception` handler would miss the security headers.
- **Hand-rolled CORS rather than `CORSMiddleware`.**
  - `CORSMiddleware` answers preflights with `Access-Control-*` headers and acts on every path.
  - The brief wants GET only, `/api/v1` only, and nothing on preflight.
  - The custom version is shorter.
- **`RateLimit` and `ResponsePolicy` as pure ASGI**, not `BaseHTTPMiddleware`. This is the right choice.
- **`TokenBuckets` has two eviction rules.** Both are needed:
  - idle buckets are full by definition, so they are free to drop;
  - the LRU cap bounds a burst from many IPv6 /64s within one refill window.
- **`decode_cursor` checks.** Each one is needed:
  - the re-encode check catches base64's silent dropping of characters (`"not base64!"`) and padding variants;
  - the type and bigint checks catch `[true]`, `[1.5]` and `[2**63]`, which re-encode identically.
- **Statement timeout via the `connect` event plus a commit (`db.py`).**
  - libpq's `options=-c statement_timeout=5s` would remove the listener and two round trips per new connection.
  - But `engine/db.py:make_engine` (PR 1) would need a `connect_args` parameter.
  - It would also silently override any `options` carried in the URL (Neon endpoint routing).
  - Not worth it.
- **`pool_pre_ping`** (inherited from `make_engine`). It costs one extra `SELECT 1` per checkout. Keep it: Neon suspends idle compute and drops connections, and without the ping the first request after an idle spell would get a 503.
- **Smaller modules.** These need no change:
  - `health.py` and `stream.py`;
  - `deps.py` (the `WebState` assert is needed under mypy strict, because `app.state` is `Any`);
  - `links.py`;
  - `cli.load_settings` and `_variable`, which reuse the engine's settings-error printing without leaking the URL.
- **Tests.** There are no meaningful duplicates.
  - The forged X-Forwarded-For case has both a unit test and an integration test. Both are named in the brief and test different layers.
  - `assert_security_headers` is repeated about 8 times, but each call is one line and the brief requires each case.
  - `tests/web/api_checks.py` is a one-function module that could live in `tests/web/conftest.py`, which tests already import `MakeClient` from. That is trivia, so I didn't apply it.
- **`ApiRouter.add_api_route` pops the rejected route before raising.** This is slightly over-defensive, since the `TypeError` aborts the import anyway. It is one line, so I'm leaving it.
- **Tried and dropped: replacing `ApiRouter` with one walk over `app.routes` in `create_app`.** On FastAPI 0.142, included routers are lazy `_IncludedRouter` objects, so `app.routes` holds no `APIRoute`s for them, and walking them needs FastAPI internals (`iter_route_contexts`). Keep `ApiRouter`.
