# Architecture Evaluation: Decoupling Shitpost Alpha into Independent Services

**Date**: 2026-02-09
**Scope**: Full decomposition plan for the Shitpost Alpha monorepo
**Status**: Evaluation complete. Ready for phased implementation.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current State Assessment](#2-current-state-assessment)
3. [Service Boundary Definition](#3-service-boundary-definition)
4. [Communication Pattern Recommendation](#4-communication-pattern-recommendation)
5. [Shared Infrastructure Strategy](#5-shared-infrastructure-strategy)
6. [Deployment Topology](#6-deployment-topology)
7. [Data Architecture](#7-data-architecture)
8. [Migration Plan](#8-migration-plan)
9. [Decision Log](#9-decision-log)
10. [Anti-Patterns to Avoid](#10-anti-patterns-to-avoid)

---

## 1. Executive Summary

Shitpost Alpha is a five-stage data pipeline (Harvest → ETL → Analyze → Price Backfill → Outcome Calculation) with a Dash analytics dashboard. It is deployed as two Railway services sharing a single monorepo, a single `requirements.txt`, and a single Neon PostgreSQL database.

### The Core Problem

The system's architecture has three compounding failures:

1. **Sequential brittleness**: The orchestrator runs Phases 1-3 as subprocess calls in sequence. If Truth Social's API rate-limits the harvester, no analysis runs — even though there are ~1,548 unanalyzed posts already in the database from previous successful runs.

2. **Orphaned services**: Market data backfill (Phase 4) and outcome calculation (Phase 5) are fully implemented (`AutoBackfillService`, `OutcomeCalculator`) but nothing calls them. This is the **root cause** of the dashboard being non-functional: `prediction_outcomes` has 9 rows out of ~1,548 expected.

3. **Shared-everything coupling**: Every service imports the entire `shit/` infrastructure package and installs all 55+ dependencies, even though the harvester only needs `aiohttp` + `boto3` and the dashboard doesn't need `openai` or `yfinance`.

### Recommended Approach

**Do not fully decompose into microservices.** This is a solo-developer side project with ~1,700 posts and $11-16/month in infrastructure costs. Instead:

- **Keep the monorepo** but introduce per-service entry points with isolated dependency sets
- **Replace the sequential orchestrator** with independent cron jobs that each check their own preconditions
- **Wire in the orphaned services** as Phase 4 and Phase 5 cron jobs — this alone fixes the dashboard
- **Use the database as the integration point** (poll for work) rather than introducing a message queue
- **Split `requirements.txt`** into per-service requirement files
- **Extract the alert system** out of the dashboard process

---

## 2. Current State Assessment

### 2.1 Codebase Inventory

| Module | Lines of Code | Purpose | External Deps |
|--------|--------------|---------|---------------|
| `shitpost_alpha.py` | 356 | Orchestrator (subprocess launcher) | None beyond shit/ |
| `shitposts/` | ~400 | Truth Social API → S3 | aiohttp, boto3 |
| `shitvault/` | ~800 | S3 → PostgreSQL ETL | boto3, sqlalchemy |
| `shitpost_ai/` | ~500 | PostgreSQL → GPT-4 → PostgreSQL | openai |
| `shit/market_data/` | ~900 | Price fetch + outcome calc | yfinance, sqlalchemy |
| `shitty_ui/` | ~6,200 | Dash dashboard + alerts | dash, plotly, pandas, twilio |
| `shit/` (infra) | ~800 | Config, DB, logging, utils | pydantic, sqlalchemy, rich |
| `shit_tests/` | ~3,000 | 41 test files | pytest |

### 2.2 Coupling Map

```
shitpost_alpha.py (orchestrator)
  └── subprocess calls → shitposts/, shitvault/, shitpost_ai/

shitposts/ (harvester)
  └── imports: shit.config, shit.s3, shit.logging
  └── NO database dependency (pure S3 writer)

shitvault/ (ETL)
  └── imports: shit.config, shit.db, shit.s3, shit.logging
  └── WRITES: truth_social_shitposts
  └── READS: S3 bucket

shitpost_ai/ (analyzer)
  └── imports: shit.config, shit.db, shit.llm, shit.logging
  └── READS: truth_social_shitposts (analyzed=False)
  └── WRITES: predictions

shit/market_data/ (orphaned)
  └── imports: shit.config, shit.db, shit.logging, shitvault.shitpost_models
  └── READS: predictions (to get asset lists)
  └── WRITES: market_prices, prediction_outcomes

shitty_ui/ (dashboard)
  └── imports: shit.config (for DATABASE_URL only)
  └── CREATES OWN ENGINE (bypasses shit.db entirely)
  └── READS: truth_social_shitposts, predictions, market_prices, prediction_outcomes
  └── WRITES: nothing (read-only)
  └── EMBEDS: alert dispatch (email/SMS/Telegram)
```

### 2.3 Database Access Patterns

| Table | Written By | Read By |
|-------|-----------|---------|
| `truth_social_shitposts` | shitvault (ETL) | shitpost_ai, shitty_ui |
| `predictions` | shitpost_ai | shit/market_data, shitty_ui |
| `market_prices` | shit/market_data | shit/market_data, shitty_ui |
| `prediction_outcomes` | shit/market_data | shitty_ui |
| `subscribers` | (unused) | (unused) |
| `telegram_subscriptions` | shitty_ui (alerts) | shitty_ui (alerts) |
| `market_movements` | (unused legacy) | (unused legacy) |
| `llm_feedback` | (unused) | (unused) |

### 2.4 Dual Session Problem

The codebase has **three separate database session mechanisms**:

1. **`shit/db/database_client.py`**: Async sessions via `create_async_engine` with `psycopg` driver
2. **`shit/db/sync_session.py`**: Sync sessions via `create_engine` with `psycopg2` driver — used by market_data
3. **`shitty_ui/data.py`**: Creates its **own** sync engine at module level, bypassing `shit/db/` entirely

This means three connection pools to the same Neon database, with no shared connection management.

### 2.5 The Requirements Bloat

Current `requirements.txt` installs everything for everyone:

| Dependency | Needed By | Not Needed By |
|-----------|-----------|---------------|
| `openai`, `anthropic` | Analyzer | Harvester, Dashboard, Market Data |
| `boto3` | Harvester, ETL | Analyzer, Dashboard, Market Data |
| `dash`, `plotly`, `pandas` | Dashboard | Everything else |
| `yfinance` | Market Data | Everything else |
| `twilio` | Alerts | Everything except Dashboard |
| `apscheduler` | Nobody (installed but unused) | Everything |
| `asyncio-mqtt` | Nobody (installed but unused) | Everything |

---

## 3. Service Boundary Definition

### 3.1 Proposed Services

Seven logical services, deployed as five Railway services (two are combined for cost):

#### Service 1: Harvester

| Attribute | Value |
|-----------|-------|
| **Responsibility** | Fetch new posts from Truth Social API, store as JSON in S3 |
| **Trigger** | Railway cron, every 5 minutes |
| **Tables owned** | None (pure S3 writer) |
| **Tables read** | None |
| **External deps** | Truth Social API (via ScrapeCreators), AWS S3 |
| **Python packages** | `aiohttp`, `boto3`, `pydantic-settings`, `python-dotenv`, `rich` |
| **Produces** | S3 objects: `s3://shitpost-alpha/truth-social/posts/YYYY-MM-DD/post_*.json` |
| **Entry point** | `python -m shitposts --mode incremental` |
| **Failure mode** | Silent. Missed harvest = next run catches up. No downstream impact. |

**Key insight**: The harvester has zero database dependency. It should never have been sequentially coupled to the analyzer. A Truth Social rate limit should not block LLM analysis.

#### Service 2: ETL Processor

| Attribute | Value |
|-----------|-------|
| **Responsibility** | Load new S3 JSON files into PostgreSQL |
| **Trigger** | Railway cron, every 5 minutes (offset from harvester by 1-2 min) |
| **Tables owned (write)** | `truth_social_shitposts` |
| **Tables read** | `truth_social_shitposts` (for dedup via shitpost_id) |
| **External deps** | AWS S3, Neon PostgreSQL |
| **Python packages** | `boto3`, `sqlalchemy`, `psycopg2-binary`, `pydantic-settings`, `python-dotenv` |
| **Produces** | New rows in `truth_social_shitposts` |
| **Precondition check** | "Are there S3 files newer than my last processed timestamp?" |
| **Entry point** | `python -m shitvault load-database-from-s3 --mode incremental` |
| **Failure mode** | Idempotent. Reprocessing the same S3 files is safe (dedup on shitpost_id). |

#### Service 3: LLM Analyzer

| Attribute | Value |
|-----------|-------|
| **Responsibility** | Analyze unprocessed posts with GPT-4, store predictions |
| **Trigger** | Railway cron, every 5 minutes (offset from ETL by 1-2 min) |
| **Tables owned (write)** | `predictions` |
| **Tables read** | `truth_social_shitposts` (where analyzed=False or analysis_status='pending') |
| **External deps** | OpenAI API, Neon PostgreSQL |
| **Python packages** | `openai`, `sqlalchemy`, `psycopg2-binary`, `pydantic-settings`, `python-dotenv` |
| **Produces** | New rows in `predictions` with `analysis_status='completed'` or `'bypassed'` |
| **Precondition check** | "Are there posts with analyzed=False?" (already built into the analyzer) |
| **Entry point** | `python -m shitpost_ai --mode incremental` |
| **Failure mode** | Idempotent. Re-analyzing already-analyzed posts is prevented by status check. |
| **Cost control** | Batch size limit (default 5) prevents runaway GPT-4 spend per run. |

**Key insight**: This service already polls for work (`analyzed=False`). It doesn't need the harvester to succeed first — it just processes whatever unanalyzed posts exist.

#### Service 4: Market Data Service

| Attribute | Value |
|-----------|-------|
| **Responsibility** | Backfill price data for predicted assets, calculate prediction outcomes |
| **Trigger** | Railway cron, every 15 minutes (less frequent — prices don't change every 5 min) |
| **Tables owned (write)** | `market_prices`, `prediction_outcomes` |
| **Tables read** | `predictions` (to discover asset lists) |
| **External deps** | Yahoo Finance API, Neon PostgreSQL |
| **Python packages** | `yfinance`, `sqlalchemy`, `psycopg2-binary`, `pydantic-settings`, `python-dotenv` |
| **Produces** | Price history rows, outcome calculations (returns, P&L, correctness at T+1/3/7/30) |
| **Precondition check** | "Are there completed predictions with assets missing from market_prices?" |
| **Entry point** | `python -m shit.market_data backfill --mode auto` (needs new CLI entry point) |
| **Failure mode** | Idempotent. Re-fetching prices updates existing rows. yfinance rate limits are handled gracefully. |

**Key insight**: This service is fully built (`auto_backfill_service.py`, `outcome_calculator.py`). It just needs a CLI entry point and a cron schedule. **Wiring this in immediately fixes the dashboard.**

#### Service 5: Dashboard (Web)

| Attribute | Value |
|-----------|-------|
| **Responsibility** | Serve the Dash analytics UI, read-only database access |
| **Trigger** | Always-on Railway web service |
| **Tables owned (write)** | None |
| **Tables read** | All tables (read-only) |
| **External deps** | Neon PostgreSQL |
| **Python packages** | `dash`, `dash-bootstrap-components`, `plotly`, `pandas`, `sqlalchemy`, `psycopg2-binary` |
| **Produces** | HTTP responses (HTML/JSON) |
| **Entry point** | `cd shitty_ui && python app.py` |

**Key change**: Remove embedded alert dispatch from the dashboard. The dashboard should be a pure read-only view.

#### Service 6: Alert Service (extracted from Dashboard)

| Attribute | Value |
|-----------|-------|
| **Responsibility** | Monitor for new predictions, dispatch notifications |
| **Trigger** | Railway cron, every 2 minutes (matches current callback interval) |
| **Tables owned (write)** | `telegram_subscriptions` (subscription management) |
| **Tables read** | `predictions` (for new prediction detection) |
| **External deps** | Telegram Bot API, SMTP/SendGrid, Twilio (optional) |
| **Python packages** | `requests`, `sqlalchemy`, `psycopg2-binary`, `twilio` (optional) |
| **Produces** | Telegram messages, emails, SMS |
| **Entry point** | `python -m alerts --check-and-dispatch` (new module) |

**Rationale for extraction**: Alert dispatch involves network I/O to external services (Telegram API, SMTP servers). If Telegram is slow or down, it shouldn't make the dashboard callback hang. Currently `dispatch_server_notifications()` runs synchronously inside a Dash callback.

#### Service 7: Continuous Price Updates (combined with Service 4)

| Attribute | Value |
|-----------|-------|
| **Responsibility** | Keep price data fresh for assets with active predictions |
| **Trigger** | Part of Service 4's cron run (same entry point, different mode) |
| **Tables read** | `prediction_outcomes` (where is_complete=False) |
| **Tables written** | `market_prices`, `prediction_outcomes` |

This isn't a separate service — it's a second pass within the Market Data Service cron. After backfilling new assets, recalculate outcomes for predictions where `is_complete=False` (i.e., where T+30 hasn't elapsed yet).

### 3.2 Service Decomposition Diagram

```
                    ┌─────────────────────────────────────────────────┐
                    │              EXTERNAL APIS                       │
                    │  Truth Social    S3    OpenAI    Yahoo Finance   │
                    │  (ScrapeCreators)                                │
                    └──────┬──────────┬───────┬──────────┬────────────┘
                           │          │       │          │
              ┌────────────▼──┐   ┌───▼───┐   │   ┌──────▼──────────┐
              │   Harvester   │   │       │   │   │  Market Data    │
              │  (cron 5min)  │──>│  S3   │   │   │  (cron 15min)   │
              │               │   │       │   │   │                 │
              └───────────────┘   └───┬───┘   │   └────────┬────────┘
                                      │       │            │
                              ┌───────▼────┐  │    WRITES: market_prices
                              │    ETL     │  │            prediction_outcomes
                              │ (cron 5min)│  │            │
                              └───────┬────┘  │            │
                                      │       │            │
                           WRITES:    │       │            │
                           shitposts  │       │            │
                                      │       │            │
                              ┌───────▼────┐  │            │
                              │    LLM     │──┘            │
                              │  Analyzer  │               │
                              │ (cron 5min)│               │
                              └───────┬────┘               │
                                      │                    │
                           WRITES:    │                    │
                           predictions│                    │
                                      │                    │
                    ┌─────────────────▼────────────────────▼───────────┐
                    │                                                   │
                    │              Neon PostgreSQL                       │
                    │                                                   │
                    │  truth_social_shitposts  │  predictions           │
                    │  market_prices           │  prediction_outcomes   │
                    │  telegram_subscriptions                           │
                    │                                                   │
                    └────────────────┬──────────────────┬──────────────┘
                                     │                  │
                              READS: │           READS: │
                              all    │           predictions
                                     │                  │
                              ┌──────▼──────┐   ┌──────▼──────┐
                              │  Dashboard  │   │   Alert     │
                              │  (web)      │   │  Service    │
                              │  always-on  │   │  (cron 2min)│
                              └─────────────┘   └─────────────┘
```

### 3.3 Key Boundary Decisions

**Each pipeline stage checks its own preconditions.** No orchestrator coordinates them. Each service asks: "Is there work for me to do?"

| Service | Precondition Check |
|---------|-------------------|
| Harvester | "Is it time to check Truth Social?" (always yes on cron) |
| ETL | "Are there S3 files I haven't processed?" |
| Analyzer | "Are there posts where analyzed=False?" |
| Market Data | "Are there completed predictions with missing price data?" |
| Market Data (refresh) | "Are there incomplete outcomes where T+N has now elapsed?" |
| Alert Service | "Are there new predictions since my last check?" |

This pattern means **every service is independently restartable and independently testable**. If the analyzer crashes for a day, the market data service just has less new work. When the analyzer recovers, it processes the backlog. No coordination needed.

---

## 4. Communication Pattern Recommendation

### 4.1 Recommendation: Database-as-Queue (Polling)

**Use the PostgreSQL database itself as the integration point between services.** Do not introduce Redis, RabbitMQ, or any message broker.

**Rationale:**

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **Database polling** | Zero new infra, already works (analyzer polls for `analyzed=False`), idempotent, debuggable via SQL | Polling lag (up to cron interval), slight DB load | **Recommended** |
| PostgreSQL LISTEN/NOTIFY | Real-time, no polling | Requires persistent connections (not great with Neon serverless), needs listener process, adds operational complexity | Not worth it |
| Redis pub/sub | Fast, standard pattern | New dependency, new cost ($5-15/month), new failure mode, overkill for ~300 events/day | Over-engineered |
| HTTP webhooks between services | Explicit coupling, real-time | Services need to know about each other, retry logic needed, adds coupling | Wrong direction |

### 4.2 Why Database Polling Works Here

The math is simple:

- ~28,000 posts over ~13 months = ~70 posts/day = ~3 posts/hour
- 5-minute cron intervals = 12 runs/hour
- Average work per run: < 1 post to process per stage

At this volume, the "lag" of polling every 5 minutes is **the same lag the current system has** (it runs on a 5-minute Railway cron). There's no latency benefit to an event-driven architecture when the producer and consumer both run on the same 5-minute cadence.

### 4.3 Polling Patterns Per Service

**ETL Processor** (already implemented):
```sql
-- Check: are there S3 files newer than last processed?
-- The s3_processor already tracks processed files via S3 listing
```

**LLM Analyzer** (already implemented):
```sql
-- Check: are there unanalyzed posts?
SELECT * FROM truth_social_shitposts
WHERE shitpost_id NOT IN (SELECT shitpost_id FROM predictions)
LIMIT 5;  -- batch size
```

**Market Data Service** (needs implementation):
```sql
-- Check: are there predictions with assets missing from market_prices?
SELECT DISTINCT unnest(assets) AS symbol
FROM predictions
WHERE analysis_status = 'completed'
  AND assets IS NOT NULL
EXCEPT
SELECT DISTINCT symbol FROM market_prices;

-- Check: are there incomplete outcomes to recalculate?
SELECT prediction_id, symbol
FROM prediction_outcomes
WHERE is_complete = FALSE
  AND prediction_date < CURRENT_DATE - INTERVAL '1 day';
```

**Alert Service** (needs new query):
```sql
-- Check: are there new predictions since last check?
SELECT p.*, t.content, t.text
FROM predictions p
JOIN truth_social_shitposts t ON p.shitpost_id = t.shitpost_id
WHERE p.created_at > :last_check_time
  AND p.analysis_status = 'completed';
```

### 4.4 Future: When to Reconsider

Upgrade to event-driven (PostgreSQL LISTEN/NOTIFY or Redis) **only if**:

- Post volume exceeds ~500/day (need sub-minute latency)
- You add real-time trading signals that need second-level responsiveness
- You add multiple consumers that need guaranteed delivery

None of these apply today or in the foreseeable future.

---

## 5. Shared Infrastructure Strategy

### 5.1 What to Share vs. Duplicate vs. Replace

| Component | Current Location | Strategy | Rationale |
|-----------|-----------------|----------|-----------|
| **Pydantic Settings** | `shit/config/shitpost_settings.py` | **Split per service** | Each service only loads its own env vars. No service needs Twilio + OpenAI + S3 keys. |
| **SQLAlchemy models** | `shitvault/shitpost_models.py` + `shit/market_data/models.py` | **Keep shared, import selectively** | Models define the schema contract. All services that read/write the DB need the same model definitions. |
| **Database sessions** | `shit/db/sync_session.py` + `shit/db/database_client.py` | **Consolidate to one sync module** | The async DatabaseClient is unused in production (all pipeline services use sync). Dashboard should use the shared sync session instead of creating its own engine. |
| **Logging** | `shit/logging/` | **Keep shared** | Consistent log format across services is valuable. Lightweight dependency (just `rich`). |
| **S3 client** | `shit/s3/` | **Keep shared, only import in services that need S3** | Only Harvester and ETL need this. |
| **LLM client** | `shit/llm/` | **Keep shared, only import in Analyzer** | Only one consumer. |
| **Error handling** | `shit/utils/` | **Keep shared** | Lightweight, no external deps. |

### 5.2 Per-Service Settings

Replace the god-object `Settings` class with focused settings per service:

```
shit/config/
├── base_settings.py        # DATABASE_URL, ENVIRONMENT, LOG_LEVEL (shared by all)
├── harvester_settings.py   # SCRAPECREATORS_API_KEY, S3 config
├── analyzer_settings.py    # OPENAI_API_KEY, LLM_MODEL, batch config
├── market_data_settings.py # (just base — yfinance needs no API key)
├── dashboard_settings.py   # (just base + PORT)
├── alert_settings.py       # TELEGRAM_BOT_TOKEN, SMTP config, TWILIO config
```

Each settings class inherits from `BaseSettings` and only declares the env vars it needs. This means:

- The harvester container doesn't need `OPENAI_API_KEY` in its environment
- The dashboard doesn't need `SCRAPECREATORS_API_KEY`
- Missing env vars fail fast at startup with a clear error, not silently at runtime

### 5.3 Per-Service Requirements Files

```
requirements/
├── base.txt              # pydantic-settings, python-dotenv, rich, sqlalchemy, psycopg2-binary
├── harvester.txt         # -r base.txt + aiohttp, boto3
├── etl.txt               # -r base.txt + boto3
├── analyzer.txt          # -r base.txt + openai
├── market-data.txt       # -r base.txt + yfinance
├── dashboard.txt         # -r base.txt + dash, dash-bootstrap-components, plotly, pandas
├── alerts.txt            # -r base.txt + requests, twilio (optional)
├── dev.txt               # -r base.txt + pytest, pytest-asyncio, pytest-cov, ruff, vcrpy
```

Keep the root `requirements.txt` as an aggregate for local development:
```
-r requirements/base.txt
-r requirements/harvester.txt
-r requirements/etl.txt
-r requirements/analyzer.txt
-r requirements/market-data.txt
-r requirements/dashboard.txt
-r requirements/alerts.txt
-r requirements/dev.txt
```

### 5.4 Consolidate Database Sessions

The three-engine problem (async client, sync session, dashboard's own engine) should become one:

**Keep `shit/db/sync_session.py` as the single session provider.** Rationale:

- Every production service uses sync operations (subprocess CLIs, not async)
- The async `DatabaseClient` in `shit/db/database_client.py` is only used by tests
- The dashboard's standalone engine in `data.py` should be replaced with an import of `sync_session.get_session()`

This reduces Neon connection pool pressure from 3 pools to 1.

### 5.5 The `shit/` Package Stays as a Shared Library

Do not extract `shit/` into a separate repo or published package. It stays in the monorepo. Services import from it directly. The dependency is managed by Python's import system, not pip.

**Why**: Published packages add versioning overhead, CI complexity, and deployment coordination. For a solo developer, "just import it" is the right level of formality. The monorepo structure already gives you atomic commits across shared code and consumers.

---

## 6. Deployment Topology

### 6.1 Current State

```json
// railway.json (current)
{
  "services": {
    "shitpost-alpha": {
      "source": ".",
      "startCommand": "python shitpost_alpha.py --mode incremental"
    },
    "shitpost-alpha-dash": {
      "source": ".",
      "startCommand": "cd shitty_ui && python app.py"
    }
  }
}
```

**Problems:**
- Both services install all 55+ dependencies
- The pipeline service is a single monolithic cron job
- No market data or alert services

### 6.2 Proposed State

```json
// railway.json (proposed)
{
  "services": {
    "harvester": {
      "source": ".",
      "startCommand": "python -m shitposts --mode incremental",
      "cronSchedule": "*/5 * * * *"
    },
    "etl": {
      "source": ".",
      "startCommand": "python -m shitvault load-database-from-s3 --mode incremental",
      "cronSchedule": "1-59/5 * * * *"
    },
    "analyzer": {
      "source": ".",
      "startCommand": "python -m shitpost_ai --mode incremental --batch-size 5",
      "cronSchedule": "2-59/5 * * * *"
    },
    "market-data": {
      "source": ".",
      "startCommand": "python -m shit.market_data auto-pipeline",
      "cronSchedule": "*/15 * * * *"
    },
    "dashboard": {
      "source": ".",
      "startCommand": "cd shitty_ui && python app.py"
    }
  }
}
```

### 6.3 Service-by-Service Deployment Analysis

| Service | Type | Always-on? | Estimated Cost | Notes |
|---------|------|-----------|----------------|-------|
| Harvester | Cron | No | ~$1/month | Runs for ~10s every 5 min |
| ETL | Cron | No | ~$1/month | Runs for ~5s every 5 min |
| Analyzer | Cron | No | ~$1/month | Runs for ~30s every 5 min (GPT-4 latency) |
| Market Data | Cron | No | ~$1/month | Runs for ~60s every 15 min (yfinance is slow) |
| Dashboard | Web | Yes | ~$5/month | Must stay up for HTTP requests |
| **Total** | | | **~$9/month** | vs. current ~$5/month |

The ~$4/month increase is justified: it enables the dashboard to actually work (market data service), makes the pipeline fault-tolerant, and unlocks independent scaling.

### 6.4 Alert Service — Defer Extraction

**Don't extract the alert service as a separate Railway service in Phase 1.** Instead:

- Keep alert checking in the dashboard callbacks for now (it's functional, just architecturally impure)
- Extract it later when/if Telegram subscriber count or alert volume warrants it
- The architectural plan is ready, but the cost of a 6th Railway service isn't justified yet

### 6.5 Monorepo with Per-Service Dockerfiles (Future)

If Railway's Railpack builder doesn't support per-service `requirements.txt`, add lightweight Dockerfiles:

```dockerfile
# services/harvester/Dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY requirements/base.txt requirements/harvester.txt ./requirements/
RUN pip install -r requirements/harvester.txt
COPY shit/ ./shit/
COPY shitposts/ ./shitposts/
CMD ["python", "-m", "shitposts", "--mode", "incremental"]
```

**But try without Dockerfiles first.** Railway's Railpack may handle `pip install -r requirements.txt` fine, and you can use a startup script that installs only what's needed:

```bash
# services/harvester/start.sh
pip install -r requirements/harvester.txt
python -m shitposts --mode incremental
```

---

## 7. Data Architecture

### 7.1 Keep a Single Shared Database

**Do not split into per-service databases.** Rationale:

| Approach | Pros | Cons | Verdict |
|----------|------|------|---------|
| **Single Neon DB** (current) | Simple, free tier, JOINs work, one connection string | No write isolation | **Keep** |
| Per-service schemas | Logical isolation | Neon free tier = 1 database; schemas add migration complexity | Not worth it |
| Per-service databases | Full isolation | Multiple connection strings, no cross-service JOINs, Neon charges per database | Over-engineered |
| Read replicas | Dashboard doesn't block writers | Neon charges for read replicas ($19/month), dashboard load is trivial | Premature |

At ~1,700 posts and ~3,000 predictions, this is not a data volume that requires architectural complexity. The single-database approach is correct.

### 7.2 Schema Ownership Convention

Even within a single database, establish **write ownership** conventions:

```
┌────────────────────────────┬─────────────────────────┐
│  Table                     │  Write Owner            │
├────────────────────────────┼─────────────────────────┤
│  truth_social_shitposts    │  ETL Processor          │
│  predictions               │  LLM Analyzer           │
│  market_prices             │  Market Data Service    │
│  prediction_outcomes       │  Market Data Service    │
│  telegram_subscriptions    │  Alert Service          │
│  subscribers               │  DEPRECATED (remove)    │
│  market_movements          │  DEPRECATED (remove)    │
│  llm_feedback              │  DEPRECATED (remove)    │
└────────────────────────────┴─────────────────────────┘
```

**Rule**: Only the write owner may INSERT/UPDATE/DELETE a table. All other services may SELECT. This is enforced by convention (code review), not by PostgreSQL roles — adding row-level security for a solo developer is overhead without benefit.

### 7.3 Remove Dead Tables

Three tables are unused and should be dropped:

- `subscribers` — Replaced by `telegram_subscriptions` + in-browser preferences
- `market_movements` — Replaced by `prediction_outcomes` (more comprehensive)
- `llm_feedback` — Never implemented beyond the model definition

### 7.4 Dashboard Read Model

The dashboard's `data.py` uses raw SQL queries because it needs aggregations and JOINs that don't map cleanly to ORM operations. This is actually fine — the problem isn't raw SQL, it's that `data.py` creates its own engine.

**Recommended approach**:

1. Replace `data.py`'s standalone engine with an import of `shit.db.sync_session.get_session()`
2. Keep the raw SQL queries — they're read-only and performant
3. Add a materialized view or cached table **only if** dashboard query latency becomes a problem (it won't at this scale)

### 7.5 S3 as Source of Truth

S3 is correctly positioned as the immutable source of truth for raw post data. The database is a derived, queryable view. This means:

- If the database is corrupted, you can rebuild from S3
- The ETL processor is already idempotent (dedup on shitpost_id)
- S3 versioning provides audit trail

No changes needed here — this is well-designed.

---

## 8. Migration Plan

### Phase 0: Wire the Orphaned Market Data Service (Week 1)

**Risk**: Low
**Value**: Critical — this alone makes the dashboard functional
**Effort**: Small

#### Steps:

1. **Create a CLI entry point for the market data service** (`shit/market_data/cli.py` exists but may need an `auto-pipeline` command that calls `auto_backfill_recent()` then `OutcomeCalculator.calculate_outcomes_for_all_predictions()`)
2. **Add a `__main__.py`** so it can be invoked as `python -m shit.market_data auto-pipeline`
3. **Test locally** with `python -m shit.market_data auto-pipeline --days-back 30 --limit 20`
4. **Add to Railway** as a third service with a 15-minute cron schedule
5. **Verify dashboard** populates after first successful run

**Expected outcome**: `prediction_outcomes` goes from 9 rows to ~1,548 rows. Dashboard charts, metrics, and accuracy data all start showing real data.

**Backward compatibility**: Zero risk. This adds a new service; it doesn't change existing ones.

### Phase 1: Decouple the Orchestrator (Week 2)

**Risk**: Low-Medium
**Value**: High — eliminates the sequential brittleness
**Effort**: Medium

#### Steps:

1. **Split the single Railway cron into three independent crons** (harvester, ETL, analyzer) with staggered schedules
2. **Verify each service runs independently** by temporarily disabling the others
3. **Delete `shitpost_alpha.py`** once all three services are confirmed working independently
4. **Update `railway.json`** to the 5-service configuration
5. **Monitor for 48 hours** — check that posts are harvested, loaded, and analyzed on the expected cadence

**Backward compatibility**: The three sub-CLIs already work independently (they were designed as independent modules called via subprocess). The only change is removing the orchestrator that sequences them.

**Rollback plan**: Re-add the orchestrator as a single cron job. The sub-CLIs didn't change.

### Phase 2: Split Requirements and Settings (Week 3)

**Risk**: Low
**Value**: Medium — reduces deploy sizes, improves startup time, eliminates phantom dependencies
**Effort**: Medium

#### Steps:

1. **Create `requirements/` directory** with per-service requirement files
2. **Create per-service settings classes** in `shit/config/`
3. **Update each service's imports** to use its specific settings class
4. **Consolidate the dashboard's engine** to use `shit/db/sync_session.get_session()`
5. **Test each service in isolation** (run with only its requirements installed)
6. **Update Railway service configurations** to install per-service requirements if supported

**Backward compatibility**: The root `requirements.txt` remains as an aggregate. Local development workflow doesn't change.

### Phase 3: Clean Up Dead Code and Tables (Week 4)

**Risk**: Low
**Value**: Low-Medium — reduces confusion, removes maintenance burden
**Effort**: Small

#### Steps:

1. **Drop unused tables**: `subscribers`, `market_movements`, `llm_feedback`
2. **Remove unused dependencies**: `apscheduler`, `asyncio-mqtt`, `anthropic` (unless you plan to use Claude)
3. **Remove or deprecate the async `DatabaseClient`** if no service actually uses async DB access
4. **Update documentation** to reflect the new multi-service architecture
5. **Update `CLAUDE.md`** with new service boundaries and safe/unsafe commands per service

### Phase 4: Extract Alert Service (Future, When Needed)

**Risk**: Medium
**Value**: Medium — cleaner architecture, but not urgently needed
**Effort**: Medium

**Trigger for this phase**: When Telegram subscriber count exceeds ~50, or when alert dispatch latency noticeably affects dashboard responsiveness.

#### Steps:

1. Extract `shitty_ui/alerts.py` into a standalone `alerts/` module
2. Create a new CLI entry point: `python -m alerts --check-and-dispatch`
3. Move subscription management queries out of the dashboard callbacks
4. Add as a Railway cron service (every 2 minutes)
5. Remove alert callbacks from the dashboard

### Phase 5: Dashboard Refactoring (Future, When Needed)

**Risk**: Medium-High
**Value**: Medium — improves maintainability
**Effort**: High

**Trigger**: When `layout.py` (4,116 lines) or `data.py` (1,401 lines) become unmanageable, or when you want to move away from Dash.

#### Considerations:

- **Dash vs. alternatives**: Dash is adequate for a read-only dashboard. Its main limitation is that it's a Python server rendering everything server-side. If you want interactivity, mobile support, or SSR, consider:
  - **Streamlit**: Simpler but less customizable
  - **FastAPI + React/Next.js**: More work, but separates API from UI cleanly
  - **Evidence.dev**: SQL-first dashboards, very lightweight
- **Splitting `layout.py`**: Break into `pages/dashboard.py`, `pages/asset_detail.py`, `components/charts.py`, `components/cards.py`, `callbacks/dashboard_callbacks.py`, `callbacks/alert_callbacks.py`
- **Splitting `data.py`**: Break into `queries/predictions.py`, `queries/outcomes.py`, `queries/assets.py`, `queries/posts.py`

This is a large refactor with no functional benefit — defer until the existing structure blocks progress.

---

## 9. Decision Log

### D1: Monorepo vs. Multi-Repo

**Decision**: Keep monorepo.
**Rationale**: Solo developer. Atomic commits across shared code and consumers. No version coordination overhead. Railway supports monorepo multi-service natively.
**Tradeoff**: All services rebuild when any code changes. Acceptable at this scale.

### D2: Database Polling vs. Event-Driven

**Decision**: Database polling (each service checks for work on its cron schedule).
**Rationale**: Already implemented in the analyzer (`analyzed=False`). Zero new infrastructure. ~3 posts/hour doesn't justify event infrastructure. Debuggable via SQL.
**Tradeoff**: Up to 5-minute lag between stages. Acceptable — matches existing system behavior.
**Revisit when**: Post volume exceeds 500/day or real-time trading signals are needed.

### D3: Single Database vs. Per-Service Databases

**Decision**: Single shared Neon PostgreSQL database.
**Rationale**: Free tier, JOINs work, ~3,000 rows doesn't need isolation, one connection string to manage.
**Tradeoff**: No write isolation (enforced by convention only).
**Revisit when**: Multiple developers or data volume exceeds what a single Neon instance handles.

### D4: Delete the Orchestrator vs. Keep as Fallback

**Decision**: Delete `shitpost_alpha.py` after confirming independent crons work.
**Rationale**: The orchestrator's sequential coupling is the primary architectural problem. Keeping it as a fallback tempts reverting. The sub-CLIs are the real entry points.
**Tradeoff**: Lose the single-command "run everything" convenience. Replace with a Makefile or script for local development.

### D5: Extract Alert Service Now vs. Later

**Decision**: Later.
**Rationale**: Adding a 6th Railway service costs money and adds operational complexity. The current callback-based alerts work. Extract when Telegram volume or dashboard latency justifies it.
**Tradeoff**: Architecturally impure — notifications are coupled to the dashboard. Acceptable for now.

### D6: Dash vs. Alternative Frontend

**Decision**: Keep Dash.
**Rationale**: It works. It's deployed. The 4,116-line `layout.py` is large but functional (24 callbacks, clean separation from DB). Rewriting the frontend provides zero functional benefit and costs weeks.
**Tradeoff**: Dash's server-rendered model limits interactivity. Not a problem for a monitoring dashboard.
**Revisit when**: You want mobile support, real-time updates via WebSocket, or multi-user authentication.

### D7: Async vs. Sync Database Access

**Decision**: Standardize on synchronous database access.
**Rationale**: Every production service uses sync (subprocess CLIs). The async `DatabaseClient` is unused in production. Neon's serverless PostgreSQL handles connection pooling externally. Two session mechanisms (async + sync) is unnecessary complexity.
**Tradeoff**: Lose the option of async DB access. Can re-add later if a service genuinely needs it.

### D8: Per-Service Dockerfiles vs. Railpack

**Decision**: Start with Railpack (Railway's default builder). Add Dockerfiles only if per-service requirements can't be handled otherwise.
**Rationale**: Dockerfiles add maintenance burden (base image updates, layer caching). Railpack auto-detects Python and installs requirements. Try the simple path first.
**Tradeoff**: All services install all requirements unless Railway supports per-service build configs.

---

## 10. Anti-Patterns to Avoid

### 10.1 Don't Introduce a Message Queue

At ~70 posts/day and ~$15/month infrastructure budget, adding Kafka, RabbitMQ, or even Redis pub/sub is:
- Over-engineering for the volume
- A new failure mode to monitor
- A new cost to pay
- A new technology to learn and debug

The database-as-queue pattern is boring and correct for this scale.

### 10.2 Don't Build a Service Mesh

No API gateway. No service discovery. No circuit breakers. No distributed tracing. Services don't call each other — they read and write the shared database. The database IS the API contract.

### 10.3 Don't Create a Shared Package Registry

Don't publish `shit/` to PyPI or a private registry. Don't create a git submodule. Import it directly from the monorepo. Version it with the same git commits. This is a solo-developer project, not a platform team.

### 10.4 Don't Split the Database Prematurely

Don't create per-service schemas. Don't create read replicas. Don't create a separate analytics database. With ~3,000 predictions, the entire dataset fits in memory. A single `SELECT` with a `JOIN` takes milliseconds.

### 10.5 Don't Rewrite the Dashboard

The 4,116-line `layout.py` and 1,401-line `data.py` are large files, but they work. The dashboard's problem is empty tables (no market data), not bad UI code. Fix the data pipeline first. Refactor the UI only when the large file sizes actively block development.

### 10.6 Don't Over-Isolate Failure Domains

The independent-cron-with-polling pattern means each service is already isolated. If the analyzer fails, the harvester and ETL keep running. If the market data service fails, the dashboard shows stale data but doesn't crash. You don't need health checks, dead letter queues, or retry infrastructure. Cron already retries on the next tick.

### 10.7 Don't Add Health Check Endpoints to Cron Jobs

Cron jobs run, do work, and exit. They don't need HTTP health endpoints. Railway's cron infrastructure already tracks whether the job succeeded or failed. Add health checks **only** to the always-on dashboard service (and Dash already has this via its HTTP server).

### 10.8 Don't Prematurely Optimize the 5-Minute Cadence

The 5-minute check interval is fine. Trump posts at most a few times per hour. The market doesn't react to a Truth Social post within 5 minutes in a way that's capturable by a retail trading system. Reducing the interval to 1 minute would 5x the Railway compute cost with no measurable benefit.

---

## Appendix A: Files to Modify Per Phase

### Phase 0 (Wire Market Data)
- `shit/market_data/cli.py` — Add `auto-pipeline` command
- `shit/market_data/__main__.py` — Wire new command
- `railway.json` — Add market-data service

### Phase 1 (Decouple Orchestrator)
- `railway.json` — Split into 5 services
- `shitpost_alpha.py` — Delete after verification

### Phase 2 (Split Requirements)
- `requirements/` — New directory with per-service files
- `shit/config/` — New per-service settings classes
- `shitty_ui/data.py` — Replace standalone engine with shared session

### Phase 3 (Clean Up)
- Database migration — Drop `subscribers`, `market_movements`, `llm_feedback`
- `requirements.txt` — Remove `apscheduler`, `asyncio-mqtt`
- `shit/db/database_client.py` — Consider removal

---

## Appendix B: Railway Service Cost Model

Railway charges based on CPU/memory usage, not per-service. Cron jobs that run for 10-60 seconds every 5-15 minutes consume minimal resources.

**Estimated monthly cost breakdown:**

| Service | CPU-seconds/month | Est. Cost |
|---------|-------------------|-----------|
| Harvester (10s * 288 runs) | ~2,880s | ~$0.50 |
| ETL (5s * 288 runs) | ~1,440s | ~$0.25 |
| Analyzer (30s * 288 runs) | ~8,640s | ~$1.50 |
| Market Data (60s * 96 runs) | ~5,760s | ~$1.00 |
| Dashboard (always-on) | ~2,592,000s | ~$5.00 |
| **Total** | | **~$8.25** |

Compared to current ~$5/month (1 cron + 1 web service), this is roughly $3-4/month more for a fully decoupled, fault-tolerant pipeline that actually works end-to-end.

---

*This evaluation is based on codebase analysis performed on 2026-02-09. All file references are relative to the repository root.*
