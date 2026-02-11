# System Evolution - Enhancement Session Overview

## Session Context

| Field | Value |
|---|---|
| **Session Name** | `system-evolution` |
| **Date** | 2026-02-11 |
| **Scope** | Whole system |
| **User's Stated Goals** | Transform from single-source Truth Social pipeline into a generalizable multi-source signal feed: source → LLM → prediction → measurement → display |

### Core User Intent

1. **Reactive measurement**: When a ticker appears in a prediction, market data should auto-backfill immediately
2. **Source-agnostic architecture**: Data model shouldn't be anchored to Truth Social; support future sources (Twitter/X, etc.)
3. **Signal visualization**: Dashboard should juxtapose signals over market trend charts
4. **Deploy existing code**: Alerts and market data cron exist but aren't deployed to production infra
5. **LLM flexibility**: Evaluate Claude/Grok alongside OpenAI
6. **Multi-source harvesting**: Abstract harvester layer to support pluggable data sources
7. **Data resilience**: Fallback price providers, health checks, retry logic

---

## Phase Documents

| # | Title | PR Title | Risk | Effort | Summary |
|---|-------|----------|------|--------|---------|
| 01 | [Reactive Ticker Lifecycle](01_reactive-ticker-lifecycle.md) | `feat: reactive ticker lifecycle with auto-backfill on prediction creation` | Low | Medium (3-5h) | Event-driven market data backfill triggered by LLM predictions. Creates TickerRegistry for tracking all tickers the system encounters. |
| 02 | [Source-Agnostic Data Model](02_source-agnostic-data-model.md) | `feat: introduce source-agnostic Signal model for multi-platform support` | Medium | High (3-5d) | Generic `Signal` model replacing coupling to Truth Social. Dual-FK migration on Prediction, dual-write during transition. |
| 03 | [Signal-Over-Trend View](03_signal-over-trend-view.md) | `feat(ui): add signal-over-trend chart view with price overlays` | Low | Medium (2-3d) | Plotly candlestick charts with prediction signal overlays. New `/trends` route with asset selector and time range controls. |
| 04 | [Deploy Alerts to Production](04_deploy-alerts-production.md) | `fix+feat: deploy Telegram alerts to production with MarkdownV2 fix` | Low | Low (2-3h) | Fix MarkdownV2 parse_mode bug, add notifications cron to Railway, add health check endpoint, BotFather setup guide. |
| 05 | [LLM Provider Switch](05_llm-provider-switch.md) | `feat: add Grok/xAI as third LLM provider with comparison CLI` | Low | Medium (3-5h) | Grok/xAI via OpenAI-compatible API. Provider config module, comparison CLI for side-by-side analysis across providers. |
| 06 | [Harvester Abstraction Layer](06_harvester-abstraction-layer.md) | `feat: abstract harvester layer for multi-source signal collection` | Medium | Medium (3-5h) | Abstract `SignalHarvester` base class, `HarvesterRegistry` with config-driven source management, skeleton TwitterHarvester template. |
| 07 | [Market Data Resilience](07_market-data-resilience.md) | `feat: multi-provider price fetching with fallback and health monitoring` | Low | Medium (3-5h) | Alpha Vantage as fallback provider, retry with exponential backoff, data freshness monitoring, health-check CLI. |

---

## Dependency Graph

```
Phase 01: Reactive Ticker Lifecycle
  ├── (no dependencies - start here)
  │
  ├──→ Phase 02: Source-Agnostic Data Model (depends on 01)
  │     └──→ Phase 06: Harvester Abstraction Layer (depends on 02)
  │
  ├──→ Phase 03: Signal-Over-Trend View (depends on 01)
  │
  └──→ Phase 07: Market Data Resilience (depends on 01)

Phase 04: Deploy Alerts to Production
  ├── (no dependencies - can run in parallel with 01)

Phase 05: LLM Provider Switch
  ├── (no dependencies - can run in parallel with 01)
```

### Implementation Order (recommended)

1. **Phase 01** - Foundation: everything else builds on ticker tracking
2. **Phase 04** - Independent: can start immediately (parallel with 01)
3. **Phase 05** - Independent: can start immediately (parallel with 01)
4. **Phase 02** - After Phase 01 merges (modifies analyzer that 01 also touches)
5. **Phase 03** - After Phase 01 merges (needs ticker data for charts)
6. **Phase 07** - After Phase 01 merges (extends market data client from 01)
7. **Phase 06** - After Phase 02 merges (builds on source-agnostic model)

### Parallel-Safe Phases

These phase pairs touch **completely disjoint files** and can safely run in parallel:

- **01 + 04**: Ticker lifecycle vs. Telegram alerts (no shared files)
- **01 + 05**: Ticker lifecycle vs. LLM provider switch (both touch `shitpost_analyzer.py` but different functions -- use caution)
- **04 + 05**: Deploy alerts vs. LLM provider switch (no shared files)
- **03 + 07**: Signal-over-trend view vs. market data resilience (no shared files after 01 merges)

### Sequential Requirements

These phases **must not run in parallel** due to shared file modifications:

- **01 → 02**: Both modify `shitpost_ai/shitpost_analyzer.py` and `shit/db/sync_session.py`
- **02 → 06**: Phase 06 builds on the source-agnostic model from Phase 02
- **01 → 07**: Both modify `shit/market_data/client.py` and market data infrastructure

---

## Total Estimated Effort

| Category | Estimate |
|----------|----------|
| **Implementation** | ~20-30 hours |
| **Testing** | ~8-12 hours |
| **Total** | ~28-42 hours |
| **New tests** | ~250+ across all phases |
| **PRs** | 7 |

---

## Key Architectural Decisions

1. **Dual-write migration** (Phase 02): Write to both `truth_social_shitposts` and new `signals` table during transition. No big-bang migration.
2. **Thread executor pattern** (Phase 01): Run sync backfill code from async analyzer via `loop.run_in_executor` to avoid blocking the event loop.
3. **OpenAI SDK reuse** (Phase 05): Grok uses the `openai` Python package with a custom `base_url` -- no new dependencies.
4. **Registry pattern** (Phase 06): Config-driven harvester registration with lazy imports to avoid circular dependencies.
5. **Provider chain** (Phase 07): Ordered list of price providers with automatic fallback. yfinance remains primary; Alpha Vantage is backup.

---

## Files Index

Quick reference of all files created/modified across all phases:

### New Files Created
- `shit/market_data/ticker_registry.py` (Phase 01)
- `shitvault/signal_models.py` (Phase 02)
- `shitvault/signal_operations.py` (Phase 02)
- `shit/db/signal_utils.py` (Phase 02)
- `shitty_ui/pages/trends.py` (Phase 03)
- `shitty_ui/components/charts.py` (Phase 03)
- `shit/llm/provider_config.py` (Phase 05)
- `shit/llm/compare_providers.py` (Phase 05)
- `shitposts/base_harvester.py` (Phase 06)
- `shitposts/harvester_registry.py` (Phase 06)
- `shitposts/harvester_models.py` (Phase 06)
- `shitposts/twitter_harvester.py` (Phase 06 - skeleton)
- `shit/market_data/price_provider.py` (Phase 07)
- `shit/market_data/alphavantage_provider.py` (Phase 07)
- `shit/market_data/health.py` (Phase 07)

### Most-Modified Files (touch count)
- `shitpost_ai/shitpost_analyzer.py` (Phases 01, 02)
- `shit/db/sync_session.py` (Phases 01, 02)
- `shit/config/shitpost_settings.py` (Phases 05, 07)
- `shit/market_data/client.py` (Phases 01, 07)
- `railway.json` (Phases 01, 04)
- `CHANGELOG.md` (all phases)
