# shitpost-alpha: what exists today (discovery, 2026-09-30)

Read-only survey of `main` at 139b145. Nothing was run against any database.

## Architecture and data flow
Event-driven, all cron jobs on Railway (`railway.json`), each every 5 minutes:

```
harvester (ScrapeCreators API -> S3 JSON)
  -> s3-processor-worker (S3 -> `signals` table)
  -> analyzer-worker (3-model LLM ensemble: GPT-5.4, Claude, Grok -> `predictions`)
  -> market-data-worker (prices, price_snapshots, prediction_outcomes)
  -> notifications-worker (Telegram alerts)
```
Stages hand off through a Postgres `events` table (`shit/events/`), not a queue.
Other crons: outcome maturation (daily), calibration refit (weekly), morning briefing,
follow-ups, weekly scorecard, event cleanup. FastAPI + React dashboard serves the data.

Worst-case latency post -> alert is roughly 5 stages x up to 5 min of cron wait, so
"within minutes" is not met today even before the scraper question.

## The paid API
Only `shitposts/truth_social_s3_harvester.py` calls ScrapeCreators
(`/truthsocial/user/posts?user_id=...`, cursor-paged), configured by
`SCRAPECREATORS_API_KEY`, `SCRAPECREATORS_BASE_URL`, `TRUTH_SOCIAL_USER_ID`.
It sits behind a clean abstraction: `SignalHarvester` (`shitposts/base_harvester.py`)
+ `HarvesterRegistry`. A replacement scraper only has to implement
`_test_connection`, `_fetch_batch`, and three extractors, and write the same raw
JSON shape to S3 (the S3 processor transforms it via `shit/db/signal_utils.py`).
`shitposts/twitter_harvester.py` is a non-functional skeleton of the same interface.

## Signals model (already half-built)
`signals` table (`shitvault/signal_models.py`) is source-agnostic: `signal_id`,
`source`, `author_username`, `published_at`, text, engagement, repost/reply/quote
flags, `platform_data` JSON. New writes go there; `truth_social_shitposts` is frozen.
Not finished: issue #224 / plan `documentation/planning/dead-code-cleanup_2026-07-24/06_finish-signals-migration.md`
(status READY): the analyzer still reads a `shitpost_id` alias, stats CLI still counts
the legacy table, legacy field names flow through bypass/analyzer (#254).

## Schema (SQLAlchemy models, no Alembic)
signals, truth_social_shitposts (archived), predictions, market_prices,
prediction_outcomes (T+1/3/7/30 plus same-day and 1h returns, correct_*, $1000 P&L),
price_snapshots, ticker_registry, calibration_curves, post_embeddings (pgvector),
events, telegram_subscriptions, alert_followups, conviction_votes.
Migrations are hand-written SQL in `scripts/001-008_*.sql`, run manually "against production Neon".

## Dev vs production database
There is no dev-branch setup in the code. A single `DATABASE_URL` decides everything
(default local SQLite; `ENVIRONMENT` defaults to development). `NEON_PROJECT_ID`/
`NEON_ORG_ID` settings exist but nothing reads them. `AGENTS.md` documents a local
Postgres 16 + pgvector for dev. A Neon dev branch would need creating and its URL
put in a dev `.env`; the dashboard queries need Postgres, not SQLite.

## Market data, backtest, alerting
- Market data: yfinance primary, Alpha Vantage fallback, intraday provider, market
  calendar, ticker registry and validator (`shit/market_data/`).
- Outcomes: `OutcomeCalculator` scores each prediction per ticker: direction-correct
  vs sentiment, return, P&L at several windows. This is per-prediction tracking,
  not a backtest: no code grep hits for "backtest". No baseline/benchmark (e.g. vs SPY
  or random), no magnitude or significance testing.
- Calibration: `CalibrationService` bins raw LLM confidence against t7 hit rate.
- Historical Echoes: embeds each post (OpenAI text-embedding-3-small) and aggregates
  outcomes of the 5 most similar past posts.
- Alerts: Telegram only in practice (`notifications/`); `enrich_alert` adds calibrated
  confidence and echoes. Dispatcher has email/SMS paths; SMS subscribers table was removed.

## In flight
- No open PRs; only branches are `main` and this session's branch.
- 84 open issues, mostly audit output from July and Aug 2026. Most relevant here:
  #244 no CI at all (2,035 tests, no linter), #224 finish signals migration,
  #219 outcome-calculator correctness, #221 event reliability, #218/#217 LLM
  ensemble bugs (junk predictions on parse failure, ensemble ignores prompt),
  #215 vote maturation never scheduled, #252 conflicting ticker validity rules.
- Planning docs: `PROJECT_MISSION.md` (plays 1-4, Play 3 is "backtesting engine"),
  `documentation/planning/` (tech-debt 2026-07-02, SIGNALS_MIGRATION, alerting).
- CLAUDE.md is partly stale (says GPT-4, lists removed tables).
