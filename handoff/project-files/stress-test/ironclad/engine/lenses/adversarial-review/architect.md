# Architect: technical correctness and integration points

Inline pass 1 of 6, run in sequence (no subagent dispatch). Plan: source-engine.md (engine plan, doc rev 130, with the notes and the growth plan's change list).

## Checked against the old code (main 139b145)
- 12 Railway services: confirmed in railway.json (11 cron services plus shitpost-alpha-web).
- Outcome maturation reads dropped columns: confirmed. shit/market_data/models.py:154 (`market_volatility`) and :160 (`notes`) are still mapped, while scripts/008_schema_cleanup.sql:25-26 drops both.
- `predictions.post_timestamp` holds the analysis time: confirmed. shitvault/signal_operations.py:162 passes `published_at` as a datetime, `.endswith("Z")` raises on it, and shit/db/database_utils.py:42-44 falls back to `datetime.now()`.
- #217 and #218 are as described: documentation/planning/tech-debt-2026-07-02/ISSUE_MAP.md:41-42.
- api/rate_limit.py:10 keys on `get_ipaddr` (notification note). Not the engine's to fix.

## Findings
1. **Alert evidence comes from a different labeller than the alert.** Live alerts get topic, tickers and direction from the LLM (D). The full-history layer is keyword-labelled (E). The plan never says which layer an alert quotes (F 'Evidence'). Quoting keyword-population statistics on an LLM-labelled alert is a validity error. Fix: one deterministic, versioned labeller for the evidence key, used on history and live alike.
2. **PR 10's nightly refresh has no production data path.** The placebo needs years of minute bars, which live as files in the sandbox. The production database keeps minute bars for 30 days plus alert windows. Railway has neither the files nor S3, which the plan retired. Fix: import historical runs frozen; production grades only matured live alerts from REST bars.
3. **CPU-heavy statistics share the live asyncio loop.** Permutation, bootstrap and BH would run in the same process as the pollers, the 15 s LLM calls, the WebSocket streams and N1's delivery workers. Fix: run them in a subprocess with a memory cap, or in the sandbox only.
4. **Migrations at start-up couple every plan to the live path.** App-schema tables from the notification, dashboard and growth plans sit in the engine's one Alembic history, and the engine 'refuses to start if one fails'. One merge also redeploys web and engine together, so web code can briefly run against the old schema. Fix: a separate migrate release step, expand-then-contract, and roles created once in the Neon console (no role passwords in migrations).
5. **`signals.seq` can skip rows.** Only `alert_revisions.seq` is described as taken under a lock held until commit. Signals are written concurrently: two pollers, stage updates, sightings. A plain sequence lets a reader pass seq N+1 before N commits, and N is then missed. Either take the same lock or drop the cursor; a 5 s re-query of the newest N is enough for the 'All posts' list.
6. **The 32 KB CNN range read holds about 58 posts** (20.3 MB / 36,571 posts). A refresh gap of up to 26 minutes during a posting spree, or recovery after an outage, can push posts out of the window. Fix: fall back to the full gzip fetch (3.7 MB) when the last-seen ID is not in the window.
7. **Display-rights machinery protects a single value.** `price_sources` with none/delayed/realtime and an API check exists for one vendor whose value is 'none'. A constant rule (the public API never serves bars or prices) does the same job. The notes' dashboard hookup `/prices/latest` polled every 5 s (ui-plan-hookups) contradicts 'none' outright.
8. **The derived-numbers rule doesn't hide prices.** A minute-resolution % series plus any public reference price (the day's close from any free source) rebuilds the raw series. Leaving out the entry price is a fig leaf. Window results (5m to 5d, hit or miss) are clearly analytics; a minute % chart may not be.

## Hookup drift to reconcile (dashboard doc older than notes)
- The dashboard doc still names `signal_tickers` and `alert_deliveries`; the notes say `signal_mentions` and app `deliveries`.
- The dashboard doc says 'read-only role'; the notes give the web role S/I/U on app, which N3's self-serve webhooks need.
- The dashboard doc's `/api/v1/bars/<symbol>` serves raw bars, which conflicts with the 'none' display rights.

## Holds up
- An insert-only `alert_revisions` with one locked sequence and a clock read after the lock is correct and right-sized for a few alerts a day.
- Post time from the snowflake ID (`id >> 16`) is verified on 36,571 posts (research/probe-live-check/findings.md).
- No events table, no S3 and the raw payload on the row are genuine simplifications.
