# Dashboard (UI) changes: design handoff

Drafted 2026-09-30 by the "Plan the signal engine" thread, after Chris asked "How do we plan on changing the UI to align behind this new system?" Chris then asked for it to be planned in its own thread. This is a starting sketch, not an approved plan.

Engine plan (the source of the hookup points below): https://claude.ai/code/artifact/d15b7e6a-2c23-42bf-9eee-37101131fdeb
Code references are to `main` at 139b145.

## What exists today (checked in the code)

- React 19 + Vite + TypeScript SPA in `frontend/`, TanStack Query, lightweight-charts, framer-motion (`frontend/package.json`). Served by the FastAPI app (`api/main.py`) from `frontend/dist`.
- One page, `frontend/src/pages/FeedPage.tsx`: one analysed post at a time, arrows and keyboard to step back (`?offset=`), then ShitpostCard, PredictionPanel, TickerSelector, FundamentalsStrip, PriceKPIs, MetricBubbles, TimeframeToggle, PriceChart, CalibrationChart.
- It lists only posts with a completed analysis, a confidence, and at least one ticker (`api/queries/feed_queries.py`, `get_analyzed_post_at_offset`). Posts with no tickers never show.
- Nothing updates on its own: `useFeedPost` has `staleTime` 60 s and no `refetchInterval` (`frontend/src/api/hooks.ts`), so a new alert shows only after a reload. Only the live quote refetches (every 15 s).
- The post card assumes Truth Social fields (reblogs, upvotes, downvotes from `platform_data`).
- API routers: `feed`, `prices`, `calibration`, `echoes`, `telegram` (`api/routers/`). All public, per-IP rate limits.

## Hookup points the engine plan provides (settle changes with the engine thread)

- `signals` with posted time (`published_at`) and a first-seen time recorded by the mirror harvester (engine PR 6).
- `predictions` as today, plus `signal_tickers` (signal x ticker, direction, topic, method, is_realtime).
- An `alerts` table holding each alert as a versioned JSON object, `alert.v1` (engine PR 7): alert id, signal, tickers with direction, the model's call, evidence lines, confidence tier, tradeable flag, alerted time. Evidence and tier fill in from engine PR 12. Delivery status per channel is in `alert_deliveries` (Telegram only in the engine plan).
- Backtest tables `backtest_runs`, `backtest_rows`, `backtest_summary` (engine PR 10, in production from PR 12).
- Engine health: `job_runs` (every scheduled job's runs) and per-mirror poll health (last poll, last success, last error), both shown by `python -m shit.engine status`; per-post timings posted, first seen, stored, analyzed, alerted.
- The existing API keeps working unchanged through the engine plan.
- A live alert stream (server-sent events) is proposed in the notification plan (handoff/notifications-design.md); the dashboard can share it.

## Proposed design

- **Live.** The page listens to the alert stream, so a new alert appears within seconds, with a timing strip: posted, first seen, alerted. A toggle shows every signal, not only those with tickers.
- **The alert's own evidence.** The prediction panel renders `alert.v1`: tier, evidence lines, tradeable flag, and later the ensemble's verdict. The web, Telegram and any other channel can't disagree.
- **Any source.** Generalise ShitpostCard to a signal card with a source badge; show platform fields only when the source has them (ready for the second source).
- **Evidence page.** A grid of topic x ticker x window: hit rate with its interval against the placebo, and the result after costs. Each cell opens the posts behind it.
- **Track record page.** Real-time alerts only, never backfill: cumulative hit rate and after-cost return by tier against SPY and the placebo. The calibration chart moves here.
- **Status page.** Each mirror's last poll and today's lag, last alert, delivery success by channel. Useful to agents too.
- **Connect page.** Telegram bot link, X account, API and webhook docs with a sample payload and a signature check (depends on the notification plan).
- Same stack and look; the draft treated a visual redesign as out of scope.

## Draft PR sketch (was PRs 15 and 16 in the engine plan's draft; renumber freely)

1. Live dashboard: stream updates, timing strip, source badge, the alert's evidence block, status and connect pages. Verified with component tests and a local run on replayed posts, screenshots in the PR. Needs engine PR 12 for evidence and the notification plan's stream (or a simple poll of `alerts` until then).
2. Evidence and track-record pages. Verified by pages built from saved backtest files matching the report. After engine PR 12.

## Open questions for Chris

- Keep the one-post-at-a-time feed as the home page, or make a live list the home page?
- Public or private: should the evidence and track-record pages be public?
- Any visual redesign wanted, or keep the current look?

## Costs and network

No new spend and no new sandbox hosts. The frontend build needs registry.npmjs.org, already on the allowlist.
