# WS07 — API Security & Performance Hardening

**Priority**: HIGH
**Type**: security / performance / tech-debt
**Findings**: H10, H11, M13, M14, M15, M16, M17, M29, L18
**Primary files**: `api/dependencies.py`, `api/queries/feed_queries.py`, `api/services/feed_service.py`, `api/routers/*.py`, `api/main.py`, `api/middleware.py`, `api/queries/price_queries.py`

---

## Security

### H10 — API is fully open when `API_KEY` is unset
`verify_api_key` (`dependencies.py:28-29`) returns success when `settings.API_KEY is None`. A production deploy that forgets to set `API_KEY` exposes feed/prices/calibration/echoes to the internet, silently. (Note: the frontend’s `VITE_API_KEY` is baked into the JS bundle and thus public by design — so for a public SPA the key is not a real secret; decide explicitly whether the API is public or gated, and don’t rely on faux header auth.)

**Fix**: In `production`, fail startup (or refuse requests) if `API_KEY` is unset. Document the intended trust model for the public SPA.

### M16 — `/telegram/health` leaks ops data unauthenticated
`api/routers/telegram.py:43-68` returns subscriber counts, alert totals, last-alert timestamp, bot config, and internal error strings with no API-key gate.

**Fix**: Require the API key (or reduce the payload to a bare liveness boolean).

### M17 — Echoes params unvalidated
`api/routers/echoes.py:13-14`: `limit` is unbounded (expensive pgvector work → DoS), `timeframe` accepts any string (unlike calibration’s `pattern="^t(1|3|7|30)$"`).

**Fix**: `limit: int = Query(5, ge=1, le=50)`, constrain `timeframe`, add `response_model=EchoResponse` (currently unused schema).

### Also
- Add a Content-Security-Policy header (`api/middleware.py:8-22` has HSTS/X-Frame but no CSP).
- Validate `{symbol}` on price routes (length/charset) before hitting yfinance/DB.
- Rate-limit or exclude health endpoints deliberately.

## Performance / architecture

### H11 — `COUNT(*) OVER()` on every feed request
`feed_queries.py:59-69` computes a window-function total over the full filtered set on each offset fetch. Cost grows linearly with analyzed posts.

**Fix**: Replace with a cached/periodic total, an approximate count, or a separate cheap `COUNT(*)` that’s cached with a short TTL.

### M13 — All API handlers are sync in an async app
Endpoints are `def`, not `async def` (`routers/feed.py:15`, `prices.py:16`, etc.), so DB/yfinance I/O blocks the single uvicorn worker.

**Fix**: Make handlers `async` with async DB access, or run blocking work via `run_in_threadpool`. (FastAPI already threadpools sync handlers, but the intent/session model is muddled — see M14.)

### M14 — Two DB round-trips + two sessions per feed response
`feed_service.py:40-45` opens separate sessions for post and outcomes.

**Fix**: Use a single request-scoped session and/or a joined query.

### M15 — Sync `process_update` blocks the async webhook
`api/routers/telegram.py:33-36` `await`s an `async` handler that calls synchronous `process_update()` (+`requests`+sync DB). Under load this blocks the event loop.

**Fix**: `await run_in_threadpool(process_update, update)`.

## Tech debt (L18, M29)

- `get_db()` (`dependencies.py:35-37`) is dead code that would leak sessions if adopted; remove or fix.
- Duplicate `/latest` vs `/at` endpoints (frontend only uses `/at`).
- Unbounded module-level `_price_cache` (`price_queries.py:14-89`) never evicts — memory creep.
- Empty `lifespan` hook (`main.py:22-25`).
- M29: `api/` hand-writes `text()` SQL duplicating ORM knowledge (manual JSON parsing at `feed_queries.py:80-90`). Longer term, consider reusing the SQLAlchemy models in `shitvault/`.
- Add tests for `SecurityHeadersMiddleware`, CORS, and slowapi enforcement (currently untested).

## Acceptance criteria

- [ ] Production refuses to serve (or start) with `API_KEY` unset; trust model documented.
- [ ] `/telegram/health` is gated or minimized; echoes `limit`/`timeframe` validated; symbol validated.
- [ ] Feed total count no longer uses per-request `COUNT(*) OVER()`.
- [ ] Webhook offloads sync processing to a threadpool.
- [ ] Dead `get_db()` and duplicate `/latest` removed; price cache bounded.
- [ ] Middleware/CORS/rate-limit tests added.
