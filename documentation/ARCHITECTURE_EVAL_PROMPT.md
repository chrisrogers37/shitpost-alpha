# System Architecture Evaluation: Decoupling a Monolithic Python Pipeline into Independent Services

## Your Role

You are a senior systems architect evaluating a Python monorepo for decomposition into independent, deployable services. Produce a detailed transformation plan — not code — that covers service boundaries, communication patterns, deployment topology, and migration sequencing.

## Current System: "Shitpost Alpha"

A real-time financial analysis system that monitors Donald Trump's Truth Social posts, uses LLMs to predict market movements, fetches market price data, calculates prediction outcomes, and serves a Dash analytics dashboard. Currently deployed on Railway as a monorepo with two services defined in a single railway.json.

### Current Architecture (Monorepo, Single Repo)

The top-level directory structure is: shitpost_alpha.py (orchestrator — sequentially shells out to 3 sub-CLIs), shit/ (shared infrastructure containing config/, db/, llm/, s3/, market_data/, logging/, utils/), shitposts/ (Truth Social → S3 harvester CLI module), shitvault/ (S3 → PostgreSQL ETL processor CLI module), shitpost_ai/ (LLM analysis engine CLI module), shitty_ui/ (Dash/Plotly dashboard with a 4100-line layout.py, 1400-line data.py, alerts.py, and app.py), shit_tests/ (pytest suite with 187 tests), railway.json (2 Railway services: pipeline cron + dashboard web), and requirements.txt (single file with ~55 deps for all concerns).

### Current Pipeline Flow (Sequential, Tightly Coupled)

The orchestrator (shitpost_alpha.py) runs as a Railway cron job and executes three phases sequentially as subprocess calls, failing the entire pipeline if any phase fails. Phase 1: Truth Social API → S3 (shitposts/ CLI). Phase 2: S3 → PostgreSQL (shitvault/ CLI). Phase 3: PostgreSQL → GPT-4 → PostgreSQL (shitpost_ai/ CLI).

What's missing from the pipeline (built but not wired in): Phase 4 — market price backfill for mentioned assets (shit/market_data/). Phase 5 — outcome calculation for predictions (shit/market_data/). Ongoing scheduled price updates for tracked assets.

The dashboard (shitty_ui/) runs as a separate Railway service but shares the entire codebase and directly imports from shit/db/, shitvault/, and shit/market_data/.

### External Dependencies

Truth Social API is used by the Harvester (API key, rate-limited). AWS S3 is used by the Harvester and S3 Processor (storage + requests). Neon PostgreSQL is used by everything (serverless, connection-pooled). OpenAI GPT-4 is used by the Analyzer (per-token, $$$). Yahoo Finance is used by the market data backfill (free, rate-limited). Telegram Bot API is used by dashboard alerts (free). Railway is used for deployment (per-service pricing).

### Database Schema (Single Neon PostgreSQL)

All tables live in a single database with no schema ownership boundaries. The "shitposts" table stores raw posts (id, body, created_at, retruth, analyzed, bypassed, s3_location). The "predictions" table stores LLM analysis (sentiment, assets[], confidence, reasoning, bypass_reason). The "market_prices" table stores OHLCV price data (asset, date, open, high, low, close, volume). The "prediction_outcomes" table stores calculated returns at T+1/3/7/30, correctness, and hypothetical P&L.

## Known Coupling Problems

1. Sequential orchestration brittleness: If harvesting fails (Truth Social rate limit), no analysis runs — even though there may be unanalyzed posts already in the DB from previous runs. The pipeline is all-or-nothing when it doesn't need to be.

2. Shared shit/ infrastructure blob: Config, DB, LLM, S3, logging, market data all live in one package. Every service imports the entire dependency tree even if it only needs DB access.

3. No event-driven triggers: The LLM analyzer polls for analyzed=False posts. The market data backfill isn't triggered at all. There's no mechanism to say "a new prediction was created, go fetch prices for its assets."

4. Dashboard data layer does everything: data.py (1400 lines) contains raw SQL queries, caching logic, database session management, and business logic for stats/predictions/posts all in one file. It directly creates SQLAlchemy engines rather than going through a shared client.

5. Single requirements.txt: The dashboard doesn't need openai, boto3, or yfinance. The harvester doesn't need dash, plotly, or pandas. But everything installs everything.

6. Market data is orphaned: AutoBackfillService has process_single_prediction() and auto_backfill_recent() designed for pipeline integration, but nothing calls them. The apscheduler dependency is installed but never used.

7. No health checks or observability boundary: If the LLM analyzer is slow or failing, there's no way to know without reading logs. No service exposes health, no metrics, no dead letter queue for failed analyses.

## Evaluation Requirements

### 1. Service Boundary Definition

Define clear service boundaries. For each proposed service, specify: responsibility (single concern), owned database tables/schemas (who reads, who writes), external dependencies it needs, Python packages it requires, how it's triggered (cron, event, HTTP, queue), and what it produces (events, DB writes, API responses).

Consider at minimum these candidate services: Harvester (Truth Social → S3, pure ingestion, no DB dependency), ETL Processor (S3 → PostgreSQL, data loading, schema ownership of shitposts), LLM Analyzer (analyze unprocessed posts, schema ownership of predictions), Market Data Service (price fetching + outcome calculation, schema ownership of market_prices and prediction_outcomes), Dashboard API (read-only API layer for the frontend), Dashboard Frontend (Dash/Plotly UI — or evaluate whether Dash is the right choice at all for a multi-service architecture), and Alert Service (Telegram notifications, currently embedded in dashboard).

### 2. Communication Patterns

Evaluate and recommend communication between services. Event bus vs. polling vs. direct calls — what's appropriate at this scale? Should the DB itself be the integration point (poll for analyzed=False) or should there be explicit events ("new post ingested", "prediction created")? Consider Railway's constraints (no native message queue, but supports Redis/PostgreSQL LISTEN/NOTIFY). How to handle the "steady active pipeline" pattern: once an asset appears in a prediction, price data should be continuously fetched until outcomes are fully calculated.

### 3. Shared Infrastructure Strategy

The shit/ package is the biggest coupling risk. Evaluate: what becomes a shared library (published package or git submodule)? What gets duplicated per service (config loading, DB models)? What gets replaced by service-to-service calls? How to handle the database client — shared models or each service owns its slice?

### 4. Deployment Topology

Current: Railway with 2 services from 1 repo. Evaluate: monorepo with per-service Dockerfiles vs. multi-repo, Railway multi-service vs. alternative platforms, which services need to be always-on vs. cron-triggered vs. event-triggered, cost implications (Railway charges per service), and how to handle the "5-minute check" cadence without coupling.

### 5. Migration Sequencing

This is a live production system. Propose a phased migration: what can be decoupled first with minimal risk? What requires the most careful extraction? How to maintain backward compatibility during migration. Testing strategy for each phase.

### 6. Data Architecture

Evaluate whether a single shared PostgreSQL database is correct, or whether: each service should have its own schema/database, read replicas should serve the dashboard, there should be a materialized view or separate read model for the dashboard, or the S3 data lake should be the source of truth with DB as derived state.

## Constraints

Budget-conscious: This is a side project. Avoid recommending Kafka, Kubernetes, or $500/month infrastructure. Prefer lightweight alternatives (Redis pub/sub, PostgreSQL LISTEN/NOTIFY, simple HTTP webhooks, Railway's native capabilities).

Python ecosystem: Stay in Python. Don't recommend rewriting in Go/Rust.

Railway deployment: Prefer Railway unless there's a compelling reason to migrate. Railway supports multi-service monorepos, cron jobs, and private networking.

Solo developer: The system is maintained by one person. Operational complexity matters. Prefer boring, debuggable patterns over clever distributed systems patterns.

Production data: There are ~1,700 posts, ~1,548 predictions, and growing. This is not big data — don't over-engineer for scale that won't exist.

## Deliverables

1. Service decomposition diagram with boundaries, ownership, and communication arrows.
2. Per-service specification (responsibility, tables owned, deps, trigger mechanism).
3. Communication pattern recommendation with rationale.
4. Shared infrastructure strategy (what's shared, what's duplicated, what's replaced).
5. Deployment topology (Railway service definitions, Dockerfiles if needed).
6. Migration plan with phases, ordered by risk and value.
7. Decision log documenting key tradeoffs and why you chose each pattern.
8. Anti-patterns to avoid — what NOT to do given the constraints.

## Context Files to Read

If you have access to the codebase, prioritize reading these files in order: (1) shitpost_alpha.py — current orchestrator, see coupling pattern. (2) railway.json — current deployment topology. (3) shit/market_data/auto_backfill_service.py — example of built-but-not-wired service. (4) shitty_ui/data.py — dashboard data layer, see query coupling. (5) shitty_ui/layout.py — 4100-line UI file, see callback complexity. (6) shit/db/ — shared database layer. (7) shit/config/shitpost_settings.py — centralized config. (8) documentation/UI_SYSTEM_ANALYSIS.md — existing analysis of UI issues. (9) requirements.txt — single dependency file for all concerns.
