# Architect: technical correctness and integration points

Reviewer 1 of 5 (inline, first pass; had read only the plan, notes, the other three plans and the code).

## Code claims checked at main 139b145

- The four read endpoints exist as the plan says: api/main.py:58-61 mount /api/calibration, /api/echoes, /api/feed, /api/prices. framer-motion is in frontend/package.json. telegram router at api/main.py:63. Claims hold.
- The SPA catch-all is api/main.py:81-95: every unknown path gets the same index.html. There is no per-URL HTML today, so link previews (D1) and growth's server-rendered titles need new server code in that route; the plan does not say so.
- Rate limiting: api/rate_limit.py:10 uses slowapi `get_ipaddr`. The installed slowapi looks up the header "X_FORWARDED_FOR" (underscores). The real header is X-Forwarded-For, so the lookup never matches and the key falls back to request.client.host. Behind Railway's proxy, with uvicorn started without --proxy-headers/--forwarded-allow-ips (railway.json:78), that is the proxy's address. Every visitor shares one bucket. The plan's "rate-limited per address" (What the dashboard reads) is false as the code stands. The notification note already flags it for N2/N4; the dashboard's 5 s poll is the endpoint that will trip it first.
- api/dependencies.py:7 imports shit.db.sync_session, which builds a pool to settings.DATABASE_URL at import (shit/db/sync_session.py:14-38). D1 deletes "their queries, services, schemas" but does not name dependencies.py. If it survives D1, the web keeps a pool to the old production DB and breaks when PR 11 deletes shit/.
- No CI exists (.github/workflows absent). API tests live in shit_tests/api and their conftest sets DATABASE_URL=sqlite (shit_tests/api/conftest.py:19). D1 adds "a frontend job in CI" only. The new /api/v1 Python code has no CI home.
- Web build: railway.json:77 builds `cd frontend && npm ci && npm run build`. "A rewrite in a new folder" means that command changes in D1 (or the new app reuses frontend/). Not stated.

## Integration findings

1. **Raw prices on public endpoints (critical).** D1 ships /api/v1/bars/<symbol> (market_bars) and a 1-minute price chart; the 00:05 note adds /api/v1/prices/latest polled every 5 s; Evidence drill-down lists "entry price"; the signal page "renders the stored alert as is", and engine PR 10 writes outcome revisions "with the entry price and time used" into alert.v1. All contradict the 1 Oct rule (no raw prices, no raw entry price, Alpaca free data not displayable). The note concedes the bars endpoint "likely changes", but D1's endpoint list was never changed. Also the DB keeps 1-minute bars only for alert windows and the last 30 days (engine Data model, storage tiers), so the doc's "minute bars cover every post since 2022" is wrong for the site: historical pages get daily or hourly at best.
2. **First production contact at the cutover (major).** WEB_DATABASE_URL is set "at the cutover" (Build order, last paragraph), yet N2's endpoints merge before the cutover and need it. If the new code builds its DB engine at import, the web service fails to boot on N2's merge and takes the old site down. D1's only real-data check is an optional temporary service.
3. **Snapshot-then-changes race (major, contract).** The list loads from /api/v1/alerts (current state) and then polls /changes?after=<seq>. Unless the list response carries the head seq read in the same transaction, the client either misses revisions between the two calls or starts at after=0 and replays all history on every page load. One field: head_seq.
4. **Two owners of one API (major).** D1 and N2 both add /api/v1 routers before the cutover, in parallel PRs, with no named owner for shared conventions (pagination, error shape, limiter, stream_id, caching headers). N4's MCP tools "use the same queries" as D3 but N4 is sequenced only after engine PR 10, not after D3. N2's agent guide "lists them all" before D2/D3 exist.
5. **Two ids for one page (minor-major).** Notifications deep-links /s/<signal_id> ('truth_social:<id>', a colon in the path); engine adds alerts.public_id "for share links/previews". Canonical links (growth) need exactly one, and links baked into Telegram posts from the cutover are permanent.
6. **Doc vs note.** "The web service connects with a read-only role" vs the agreed role (SELECT engine; SELECT/INSERT/UPDATE app). "alert_deliveries" vs notification's `deliveries`. "Results per window from backtest_rows live layer" vs engine's outcome revisions on the alert; pick one source or the page and the alert can disagree (the plan's own risk row).

## What is sound

A pure /api/v1 client, insert-only revisions as the cursor, polling paused while hidden, endpoint tests on a DB built from the engine's migrations, and the Evidence/Track record numbers tested against the saved report are all right.
