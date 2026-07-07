# Full System Review & Tech-Debt Triage — 2026-07-02

**Session**: `tech-debt-2026-07-02`
**Scan date**: 2026-07-02
**Scan scope**: Full system — `shit/` (core infra), `shitposts/` + `shitvault/` + `shitpost_ai/` (pipeline), `shit/market_data/`, `api/` (FastAPI), `frontend/` (React), `notifications/` (Telegram), `shit/events/` (event queue), and the `shitpost_alpha.py` orchestrator.
**Method**: Read-only source review of every subsystem. Highest-severity findings were spot-verified against the code.
**Location**: `documentation/planning/tech-debt-2026-07-02/` — durable analysis artifacts. Archive to `documentation/archive/` when all workstreams close.

> This is a **triage tracker**, not a set of applied fixes. No production code was changed. Each finding has a stable ID (`C#`/`H#`/`M#`/`L#`) and is grouped into an actionable workstream (`01`–`14`) in the sibling files in this directory.
>
> **GitHub issues:** the CRITICAL (P0) and HIGH (P1) findings are filed as **individual** GitHub issues; MEDIUM (P2) and LOW (P3/P4/nice-to-have) findings are filed as **clustered** issues grouped by workstream/theme. See [`ISSUE_MAP.md`](ISSUE_MAP.md) for the finding-ID → issue-number mapping. Priority mapping: **P0 = CRITICAL, P1 = HIGH, P2 = MEDIUM, P3/P4/nice-to-have = LOW**.

---

## Executive Summary

The system is a mature, event-driven pipeline (harvest → S3 → DB → LLM analysis → market outcomes → alerts) with a React/FastAPI dashboard and a Telegram bot. It has broad test coverage (~2,300 tests) and many good patterns (event fan-out, service factories, path-traversal-safe static serving, timing-safe API-key compare, SQL column allow-lists). This review nonetheless surfaced **five production-correctness issues** that silently degrade user-facing behavior or can hang/duplicate work, plus a large amount of architectural drift from the ongoing `signals` migration and the CLI→events transition.

**The five things worth fixing first:**

1. **Production alerts are degraded** — the live Telegram path (`notifications.event_consumer`) hardcodes `sentiment="neutral"` and sends empty `thesis`/`text`, so subscribers with a sentiment filter are silently dropped and everyone else gets contentless alerts (**C1**).
2. **Analyzer range-mode can infinite-loop** — unprocessed posts newer than the requested end-date cause endless empty batches until the process is killed (**C2**).
3. **Dual execution model can double-spend LLM calls** — the orchestrator runs phases as subprocesses *and* the same phases emit events consumed by workers; with both deployed, S3 loads and LLM analysis can run twice (**C3**).
4. **Event queue has no stale-claim recovery** — a worker that dies between "claim" and "process" leaves events stuck in `claimed` forever (**C4**).
5. **No alert delivery idempotency** — retried events or overlapping cron can re-send the same prediction to subscribers (**C5**).

Cutting across everything: a **dual database access model** (async `psycopg` for the pipeline, sync `psycopg2` for events/market/notifications), an **unfinished `signals` migration** (`shitpost_id` vs `signal_id` dual identity, legacy table still driving stats), and **two "sources of truth" for schema** (rich ORM models alongside hand-written `text()` SQL in `api/` and `notifications/`).

---

## Severity Legend

- **CRITICAL** — production correctness/user-facing degradation, data loss, unbounded cost, or hang. Fix first.
- **HIGH** — meaningful bug, security exposure, or architectural risk that will bite under load or during maintenance.
- **MEDIUM** — real debt: complexity, inconsistency, or latent bug behind a guard.
- **LOW** — informational, cosmetic, or cleanup.

---

## Complete Inventory

### CRITICAL

| # | Finding | Location | Workstream |
|---|---------|----------|-----------|
| C1 | **Degraded production alerts** — event consumer hardcodes `sentiment="neutral"`, empty `thesis`/`text`; `enrich_alert()` never adds DB fields. Sentiment-filtered subscribers dropped; others get contentless alerts. | `notifications/event_consumer.py:56-67`, `notifications/alert_engine.py:30-75` | 01 |
| C2 | **Analyzer range-mode infinite loop** — `get_unprocessed_signals()` returns newest-first with no date bound; posts newer than `end_date` yield endless empty filtered batches (`continue` forever). | `shitpost_ai/shitpost_analyzer.py:241-296`, `shitvault/signal_operations.py:67-125` | 03 |
| C3 | **Dual execution model (CLI subprocess + events)** — orchestrator runs harvest/S3/analyze as subprocesses while the same phases emit events to workers; both deployed → duplicate S3 loads and LLM spend. | `shitpost_alpha.py:118-152`, `*/event_consumer.py`, `shitpost_ai/event_consumer.py:39-49` | 02 |
| C4 | **Orphaned `claimed` events** — claim and process run in separate transactions with no stale-claim timeout/reclaim; a crash between them wedges events forever. | `shit/events/worker.py:141-224` | 04 |
| C5 | **No alert delivery idempotency** — no `(prediction_id, chat_id)` ledger; retried events or overlapping cron re-send the same prediction. | `notifications/alert_engine.py:156-167`, `notifications/event_consumer.py:94-127`, `shit/events/worker.py:194-206` | 01 |

### HIGH

| # | Finding | Location | Workstream |
|---|---------|----------|-----------|
| H1 | **Dual DB session mechanisms** — async `DatabaseClient` (psycopg) for pipeline vs module-level sync `get_session()`/psycopg2 for events/market/echoes/notifications. Two engines/pools/drivers on one DB. | `shit/db/database_client.py:23-77`, `shit/db/sync_session.py:13-65` | 05 |
| H2 | **`get_session()` misused as async context manager** — `DatabaseClient.get_session()` returns a bare `AsyncSession`, but docs/callers use `async with ...`. Session lifecycle/close is unreliable. | `shit/db/database_client.py:73-77`, `shit/services.py:13-14`, `shit/README.md:268` | 05 |
| H3 | **`create_all()` on every async init** — schema creation runs on every startup; risks drift/races with migrations in production. | `shit/db/database_client.py:67-69` | 05 |
| H4 | **No `session.rollback()` on prediction write failure** — one failed write poisons the session for the rest of the batch. | `shitvault/prediction_operations.py:147-149,218-220` | 06 |
| H5 | **Failed LLM analysis leaves no DB footprint** — returns `None`, never writes `analysis_status='error'`; signal stays "unprocessed" forever and gets retried (repeat LLM spend). | `shitpost_ai/shitpost_analyzer.py:539-541`, `prediction_operations.py` | 06 |
| H6 | **`check_prediction_exists` fails open** — DB error returns `False` (“doesn’t exist”), inviting duplicate analysis + LLM cost. | `shitvault/prediction_operations.py:254-256` | 06 |
| H7 | **Incremental S3 processing can reprocess everything** — if latest DB `signal_id` isn’t in the S3 listing, *all* keys are processed. | `shitvault/s3_processor.py:76-99` | 09 |
| H8 | **`list_raw_data()` ignores `end_date`** — parameter accepted/documented but never applied; range mode loads files outside the window. | `shit/s3/s3_data_lake.py:197-246` | 09 |
| H9 | **`--max-id` and `--source` CLI args are dead** — backfill can’t resume from an ID; `python -m shitposts` always runs the Truth Social harvester regardless of `--source`. | `shitposts/truth_social_s3_harvester.py:36-45`, `shitposts/cli.py:44-48`, `shitposts/__main__.py:9-13` | 12 |
| H10 | **API open when `API_KEY` unset** — `verify_api_key` allows all requests if `settings.API_KEY is None`; a Railway deploy without the key makes every route public. | `api/dependencies.py:28-29` | 07 |
| H11 | **`COUNT(*) OVER()` on every feed request** — window function scans the full filtered set per offset fetch; cost grows with data, no caching. | `api/queries/feed_queries.py:59-69` | 07 |
| H12 | **`PriceKPIs` violates Rules of Hooks** — early `return null` (line 112) precedes `useFlashColor`/`useUpdatedAgo`/`useMemo`; hook count changes when live data arrives. | `frontend/src/components/PriceKPIs.tsx:112-124` | 08 |
| H13 | **Vote maturation never scheduled** — `mature_all_votes()` exists/tested but isn’t wired to any cron/CLI; `/mystats`, `/leaderboard`, and vote closure depend on `vote_correct` that is never populated. | `notifications/vote_maturation.py:84-119`, `railway.json` | 01 |
| H14 | **Re-subscribe leaves `consecutive_errors >= 5`** — `/start` doesn’t reset the counter, so auto-silenced users can never receive alerts again without manual DB edits. | `notifications/db.py:158-178,206-209`, `notifications/telegram_bot.py:55-62` | 01 |
| H15 | **`analyze_ensemble()` drops `prompt_func`/`kwargs`** — ensemble runs always use the default prompt even when a custom one is passed. | `shit/llm/compare_providers.py:358-376,441-449` | 11 |
| H16 | **Manual JSON fallback stores junk predictions** — on JSON parse failure, invents assets from words containing "inc"/"corp" and sets confidence 0.5 instead of failing. | `shit/llm/llm_client.py:238-259` | 11 |

### MEDIUM

| # | Finding | Location | Workstream |
|---|---------|----------|-----------|
| M1 | **`OutcomeCalculator` god class** (~819 lines) — price resolution, fills, intraday, batch stats, maturation, accuracy in one class. | `shit/market_data/outcome_calculator.py` | 10 |
| M2 | **Per-asset commit inside prediction loop** — partial outcomes persist on mid-loop failure; excessive transaction overhead. | `shit/market_data/outcome_calculator.py:251` | 10 |
| M3 | **Outcome/calibration anchor mismatch** — batch filters on `Prediction.created_at` while outcome math anchors on post publish time; late-analyzed posts mis-scoped. | `shit/market_data/outcome_calculator.py:508-510,762-776`, `calibration.py:114` | 10 |
| M4 | **Sentiment fallback misattributes accuracy** — asset missing from `market_impact` falls back to first sentiment in the dict, scoring multi-asset predictions wrong. | `shit/market_data/outcome_calculator.py:816-818` | 10 |
| M5 | **`get_missing_tickers()` coarse existence check** — checks if a symbol exists *anywhere*, not whether the date range is covered; skips needed backfill. | `shit/market_data/auto_backfill_service.py:65-71` | 10 |
| M6 | **Prompt injection surface** — post text concatenated raw into LLM prompt with no delimiter hardening. | `shitpost_ai/shitpost_analyzer.py:707`, `shit/llm/prompts.py` | 11 |
| M7 | **No LLM rate limiting / backoff** — `rate_limit_rpm` config exists but is unused; ensemble fires all providers concurrently with only a 30s timeout. | `shit/llm/llm_client.py:166-199`, `compare_providers.py:374-378` | 11 |
| M8 | **Dead global circuit breakers / rate limiters** — `llm_circuit_breaker`/`llm_rate_limiter` defined but never used; `CircuitBreaker` also calls `asyncio.get_running_loop()` and breaks in sync context. | `shit/utils/error_handling.py:145-201` | 11 |
| M9 | **Event payload schemas not enforced** — `PAYLOAD_SCHEMAS` is reference-only; `emit_event()` accepts any dict. | `shit/events/event_types.py:50-84`, `producer.py:19-93` | 04 |
| M10 | **Event consumers ignore their payload IDs** — analyzer/notifications workers run generic incremental passes over *all* unprocessed rows instead of the specific `signal_ids`/`prediction_id` in the event. | `shitpost_ai/event_consumer.py:39-49`, `notifications/event_consumer.py` | 02 |
| M11 | **Event worker calls private processor internals** — `S3Processor._process_single_s3_data()` invoked directly, bypassing public API and duplicating event emission. | `shitvault/event_consumer.py:65-66` | 02 |
| M12 | **Analyzer date filter done in Python, not SQL** — should be `WHERE published_at BETWEEN ...` with ASC/DESC for backfill. | `shitpost_ai/shitpost_analyzer.py:248-251` | 03 |
| M13 | **All API handlers are sync in an async app** — `def` endpoints block the single uvicorn worker during DB/yfinance I/O. | `api/routers/*.py` | 07 |
| M14 | **Two DB round-trips per feed response** — separate sessions for post + outcomes; no request-scoped session or join. | `api/services/feed_service.py:40-45`, `api/dependencies.py:40-47` | 07 |
| M15 | **Sync `process_update` blocks async webhook** — telegram webhook is `async` but calls sync bot processing (+`requests`+sync DB) without `to_thread`. | `api/routers/telegram.py:33-36`, `notifications/telegram_bot.py:1026-1105` | 07 |
| M16 | **Unauthenticated `/telegram/health` leaks ops data** — subscriber counts, alert totals, bot config, internal errors, no API-key gate. | `api/routers/telegram.py:43-68` | 07 |
| M17 | **Echoes `limit`/`timeframe` unvalidated** — `limit` unbounded (DoS on pgvector), `timeframe` accepts any string. | `api/routers/echoes.py:13-14` | 07 |
| M18 | **`telegram_bot.py` god object** (~1106 lines) — 15+ handlers, watchlist CRUD, vote callbacks, DB/ticker validation, routing; duplicated prefs parsing & escapers. | `notifications/telegram_bot.py` | 13 |
| M19 | **Duplicate dispatch logic (cron vs events)** — near-identical subscriber loops; event path omits quiet-hours check → inconsistent behavior. | `notifications/alert_engine.py:135-185`, `event_consumer.py:74-127` | 01 |
| M20 | **Email/SMS dispatcher is dead code** — implemented + tested but never wired into any live path; SMS never activated. | `notifications/dispatcher.py` | 13 |
| M21 | **Quiet hours use server-local time** — `datetime.now()` while briefing/scorecard use `America/New_York`; ET users’ quiet hours are wrong. | `notifications/alert_engine.py:251-261` | 01 |
| M22 | **`signals` migration unfinished (dual identity)** — analyzer/CLI/events still speak `shitpost_id`; aliases injected at read time, not stored. | `shitvault/signal_operations.py:160-161`, `shitpost_ai/shitpost_analyzer.py:386-394,603-604` | 12 |
| M23 | **Legacy table still drives stats** — `stats`/`analysis_rate` count `truth_social_shitposts`, not `signals`; dashboards under-report post-migration. | `shitvault/statistics.py:31-99` | 12 |
| M24 | **Harvester registry / multi-source is dead at runtime** — `HarvesterRegistry`, `create_default_registry()`, Twitter stub exported but never invoked; `--source` ignored. | `shitposts/harvester_registry.py`, `shitposts/twitter_harvester.py` | 12 |
| M25 | **Fake-async S3 + inconsistent `to_thread` usage** — `async def` methods call sync boto3 directly; some paths wrap in `to_thread`, others don’t → event-loop blocking. | `shit/s3/s3_client.py:46-74`, `s3_data_lake.py:109-293` | 09 |
| M26 | **Naive-UTC timestamps stripped through pipeline** — harvester `.replace(tzinfo=None)` + naive date filters cause edge-of-day/DST ambiguity end to end. | `shitposts/truth_social_s3_harvester.py:133-137`, `shit/db/database_utils.py:40-42` | 09 |
| M27 | **`validate_config()` never called; `DEBUG` defaults True** — missing LLM keys fail late; deploys omitting `ENVIRONMENT`/`DEBUG` run in debug. | `shit/config/shitpost_settings.py:28,181-198` | 14 |
| M28 | **Two `ENVIRONMENT`/bucket sources of truth** — API uses `os.environ` default `production`; settings default `development`; S3 bucket default differs between settings and `S3DataLake`. | `api/main.py:45`, `shit/config/shitpost_settings.py:27,107`, `shit/s3/s3_data_lake.py:34-36` | 14 |
| M29 | **ORM models vs raw `text()` SQL duplication** — `api/` and `notifications/` hand-write SQL despite rich models existing → two sources of schema truth. | `api/queries/*`, `notifications/db.py` | 07/13 |
| M30 | **Vote correctness bugs** — vote recorded with `from_user.id` not `chat.id` (breaks groups); TOCTOU on check-then-insert; closure keyed on any non-null `vote_correct`. | `notifications/telegram_bot.py:875-921`, `notifications/vote_db.py:71-85` | 01 |
| M31 | **`/latest` duplicates predictions per asset; `/stats` "Total Return" is meaningless** — `LEFT JOIN prediction_outcomes` fans out rows; `SUM(return_t7)` isn’t a portfolio metric. | `notifications/db.py:415-478` | 13 |

### LOW

| # | Finding | Location | Workstream |
|---|---------|----------|-----------|
| L1 | Webhook secret not registered with Telegram — `set_webhook()` omits `secret_token`, so header verification is bypassed unless set manually. | `notifications/telegram_sender.py:84-113`, `__main__.py:122-131` | 01 |
| L2 | Unescaped user name in `/start` MarkdownV2. | `notifications/telegram_bot.py:65-67` | 13 |
| L3 | Railway cron vs documented ET schedules drift by 1h across DST. | `railway.json:55-68` | 14 |
| L4 | `datetime.utcnow()` (naive, deprecated) used widely; inconsistent with tz-aware code. | many (`notifications/*`, `shit/market_data/client.py`, models) | 14 |
| L5 | Frontend has no test suite (vitest/jest/playwright). | `frontend/` | 08 |
| L6 | React Query `retry: 2` retries 4xx (404/403/422) instead of failing fast. | `frontend/src/App.tsx:9` | 08 |
| L7 | `offset` URL param not sanitized → `NaN` → broken request. | `frontend/src/pages/FeedPage.tsx:66` | 08 |
| L8 | Error boundary renders `error.stack` to the DOM in production. | `frontend/src/App.tsx:33-35` | 08 |
| L9 | `CalibrationChart` bypasses React Query (raw `useEffect` + fetch); echoes API unused in UI; timeframe labels mismatch data windows. | `frontend/src/components/CalibrationChart.tsx`, `TimeframeToggle.tsx` | 08 |
| L10 | Frontend `fetchJson` has no timeout/abort and no runtime schema validation (casts to types). | `frontend/src/api/client.ts:8-17` | 08 |
| L11 | Dead `transform_s3_data_to_shitpost()` legacy transformer in core db utils. | `shit/db/database_utils.py:49-134` | 12 |
| L12 | `get_cli_logger` in `__all__` but not imported (AttributeError on import); duplicate definitions in two modules. | `shit/logging/__init__.py:31-88` | 14 |
| L13 | Over-aggressive bypass test phrases (`'hello'`, `'hi'`) can bypass real posts. | `shit/content/bypass_service.py:60,159-160` | 12 |
| L14 | `get_s3_processing_stats` is a stub; `processing-stats` CLI mostly non-functional. | `shitvault/s3_processor.py:236-245` | 12 |
| L15 | `use_signal` parameter documented "deprecated, ignored" but still threaded through call sites. | `shitvault/prediction_operations.py:49-57` | 12 |
| L16 | TOCTOU in `echo_service.embed_and_store` (existence check + embed + insert across sessions). | `shit/echoes/echo_service.py:56-78` | 06 |
| L17 | `_extract_scalar()` treats legitimate `0` as NULL; follow-up `abandoned` counter never incremented; scorecard empty-week check uses string matching. | `notifications/db.py:36-41`, `followups.py:496-538`, `scorecard_service.py:108-112` | 13 |
| L18 | Duplicate `/latest` vs `/at` feed endpoints (frontend uses only `/at`); unbounded module-level price cache; empty lifespan hook; `get_db()` dead code with leak pattern. | `api/routers/feed.py:13-30`, `api/queries/price_queries.py:14-89`, `api/main.py:22-25`, `api/dependencies.py:35-37` | 07 |
| L19 | No auth/rate-limit on expensive bot commands; `/leaderboard` exposes usernames. | `notifications/telegram_bot.py:1026-1099`, `vote_db.py:204-232` | 01 |

---

## Workstreams (proposed PRs)

Each workstream is a self-contained file in this directory, sized to be one PR. Ordered by priority.

| WS | Title | Priority | Findings | Type |
|----|-------|----------|----------|------|
| [01](01_production-alert-correctness.md) | Production alert correctness & delivery integrity | **CRITICAL** | C1, C5, H13, H14, M19, M21, M30, L1, L19 | bug/security |
| [02](02_pipeline-execution-model.md) | Unify pipeline execution model (CLI vs events) | **CRITICAL** | C3, M10, M11 | architecture |
| [03](03_analyzer-range-mode.md) | Fix analyzer range-mode loop & push date filters to SQL | **CRITICAL** | C2, M12 | bug |
| [04](04_event-queue-reliability.md) | Event queue reliability (stale-claim recovery, payload validation) | HIGH | C4, M9 | bug/architecture |
| [05](05_database-session-architecture.md) | Consolidate DB session architecture | HIGH | H1, H2, H3 | architecture |
| [06](06_transaction-safety.md) | Transaction safety & failure persistence | HIGH | H4, H5, H6, L16 | bug |
| [07](07_api-security-performance.md) | API security & performance hardening | HIGH | H10, H11, M13, M14, M15, M16, M17, M29, L18 | security/perf |
| [08](08_frontend-robustness.md) | Frontend correctness & robustness | HIGH | H12, L5, L6, L7, L8, L9, L10 | bug/enhancement |
| [09](09_harvest-s3-correctness.md) | Harvest & S3 correctness (incremental, end_date, timezones, async) | HIGH | H7, H8, M25, M26 | bug |
| [10](10_market-data-outcomes.md) | Market data / outcome calculator correctness & decomposition | MEDIUM | M1, M2, M3, M4, M5 | bug/complexity |
| [11](11_llm-robustness.md) | LLM robustness (ensemble, JSON fallback, rate limiting, injection) | MEDIUM | H15, H16, M6, M7, M8 | bug/security |
| [12](12_migration-and-legacy-cleanup.md) | Finish `signals` migration & remove dead abstractions | MEDIUM | H9*, M22, M23, M24, L11, L13, L14, L15 | tech-debt |
| [13](13_notifications-refactor.md) | Notifications refactor (bot god object, dead channels, query bugs) | MEDIUM | M18, M20, M31, L2, L17 | tech-debt |
| [14](14_config-and-consistency.md) | Config validation & cross-cutting consistency | LOW | M27, M28, L3, L4, L12 | tech-debt |

\* H9 (`--max-id`/`--source` dead) is grouped under WS12 because it is part of the same multi-source/migration cleanup.

### Recommended order & parallelism

1. **First wave (correctness, mostly disjoint files):** WS01, WS02, WS03 can proceed together — WS01 touches `notifications/`, WS03 touches `shitpost_ai/`, WS02 spans the orchestrator + consumers (coordinate WS02/WS03 since both touch `shitpost_ai/event_consumer.py`).
2. **Second wave (infra):** WS04, WS05, WS06 — WS05 (session model) should land before or with WS06 to avoid churn; WS04 is independent.
3. **Third wave (web):** WS07, WS08 — fully disjoint (`api/` vs `frontend/`), safe in parallel.
4. **Fourth wave (domain hardening):** WS09, WS10, WS11 — independent file sets.
5. **Cleanup wave:** WS12, WS13, WS14 — do after correctness work so the migration cleanup rides on a green test suite.

---

## Out of Scope / Notes

- **`gh` is read-only here**, so this tracker is the deliverable rather than filed GitHub issues. Each `NN_*.md` file is issue-ready (title, context, findings, acceptance criteria) for a maintainer to paste into GitHub.
- **Dual PostgreSQL drivers** (`psycopg` async + `psycopg2` sync) were previously reviewed and intentionally kept; WS05 proposes *reducing the surface* (session lifecycle bugs) rather than forcing a single driver.
- **CHANGELOG drift (verify before closing WS01/WS12):** the `[Unreleased]` section of `CHANGELOG.md` claims *"Signals Migration Complete — All readers now use `signals`"* and *"Both cron engine and event consumer produce identically enriched alerts."* Both were spot-checked and are **not** fully true in the code: `shitvault/statistics.py:31-99` still counts `truth_social_shitposts` (M23), and `notifications/event_consumer.py:56-67` still hardcodes `sentiment="neutral"` with empty `thesis`/`text` because `enrich_alert()` only adds calibration + echoes (C1). Treat those changelog entries as aspirational, not done.
- Prior tech-debt scans live under `documentation/archive/` (`tech-debt-2026-03-26`, `codebase-health_2026-02-23/25`, `full-scan_2026-02-10`). Some items here are recurrences where the earlier fix was partial (e.g. outcome_calculator decomposition, API test coverage gaps for middleware/rate limiting).
- No estimates in calendar time are given; "priority/wave" reflects production risk and file-overlap, not schedule.
