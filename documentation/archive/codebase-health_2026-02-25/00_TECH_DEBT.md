# Tech Debt Remediation: codebase-health (2026-02-25)

## Executive Summary

A codebase health scan of shitpost-alpha identified 18 findings across four domains: deprecated asyncio patterns threatening Python 3.13 compatibility, duplicated query builder logic in the dashboard data layer, copy-pasted service initialization and CLI boilerplate across 8+ files, and monolithic callback registrations (939 combined LOC) paired with 4 untested modules (~1,163 LOC with zero coverage). The remediation is organized into 8 phases, 5 of which can run in parallel on disjoint file sets, with the remaining 3 gated by explicit dependencies.

## Inventory

| # | Issue | Severity | Phase | Effort | Files Affected |
|---|-------|----------|-------|--------|----------------|
| 1 | `asyncio.get_event_loop()` in shitpost_analyzer.py | HIGH | 01 | Low | `shitpost_ai/shitpost_analyzer.py` |
| 2 | `asyncio.get_event_loop()` in s3_data_lake.py (3 instances) | HIGH | 01 | Low | `shit/s3/s3_data_lake.py` |
| 3 | `asyncio.get_event_loop()` in error_handling.py (3 instances) | HIGH | 01 | Low | `shit/utils/error_handling.py` |
| 4 | Unused `validate_prompt_version()` function | LOW | 01 | Low | `shit/llm/prompts.py` |
| 5 | Unused `from decimal import Decimal` import | LOW | 01 | Low | `shit/market_data/models.py` |
| 6 | `twitter_harvester.py` non-functional skeleton | LOW | 01 | Low | `shitposts/twitter_harvester.py` |
| 7 | `backfill_prices.py` standalone orphan script | LOW | 01 | Low | `shit/market_data/backfill_prices.py` |
| 8 | Duplicated WHERE clause logic in `get_signal_feed()` | MEDIUM | 02 | Medium | `shitty_ui/data/signal_queries.py` |
| 9 | Duplicated WHERE clause logic in `get_signal_feed_count()` | MEDIUM | 02 | Medium | `shitty_ui/data/signal_queries.py` |
| 10 | DB+S3 initialization boilerplate repeated 5+ times | MEDIUM | 03 | Medium | `shitvault/cli.py`, `shitvault/event_consumer.py` |
| 11 | CLI argument parser duplication across 3 modules | MEDIUM | 03 | Medium | `shitpost_ai/cli.py`, `shitposts/cli.py`, `shitvault/cli.py` |
| 12 | CLI validation logic duplication | MEDIUM | 03 | Low | `shitpost_ai/cli.py`, `shitposts/cli.py` |
| 13 | CLI print helper function duplication | MEDIUM | 03 | Low | `shitpost_ai/cli.py`, `shitposts/cli.py` |
| 14 | Monolithic `register_alert_callbacks()` — 479 LOC, 17 nested callbacks | HIGH | 04 | High | `shitty_ui/callbacks/alerts.py` |
| 15 | Monolithic `register_dashboard_callbacks()` — 460 LOC, 7 callbacks | HIGH | 04 | High | `shitty_ui/pages/dashboard.py` |
| 16 | Untested `alert_components.py` — 627 LOC, 0% coverage | MEDIUM | 05 | Medium | `shitty_ui/callbacks/alert_components.py` |
| 17 | Untested `empty_states.py` — 221 LOC, 0% coverage | MEDIUM | 05 | Low | `shitty_ui/components/cards/empty_states.py` |
| 18 | Untested `compare_cli.py` — 156 LOC, 0% coverage | MEDIUM | 05 | Low | `shitpost_ai/compare_cli.py` |

## Phase Overview

| Phase | Title | Dependencies | Blocks | Effort | Risk |
|-------|-------|-------------|--------|--------|------|
| 01 | Quick Wins: Asyncio + Dead Code | None | None | Low | Low |
| 02 | Extract Signal Query Builder | None | 05 | Medium | Medium |
| 03 | Service Initialization Factory + CLI Shared Args | None | None | Medium | Low |
| 04 | Split Monolithic Dashboard Callbacks | None | 05, 08 | High | Medium |
| 05 | Add Missing Test Coverage | 02, 04 | None | Medium | Low |
| 06 | Safe Dependency Upgrades | None | 07 | Low | Low |
| 07 | OpenAI SDK v2 Migration | 06 | None | High | High |
| 08 | Dash 4 Migration | 04 | None | High | High |

## Dependency Graph

```
  01 (Asyncio + Dead Code)          [standalone]

  02 (Query Builder) ──────────┐
                               ├──▶ 05 (Test Coverage)
  04 (Split Callbacks) ────────┘
         │
         └──────────────────────────▶ 08 (Dash 4 Migration)

  03 (Service Init Factory)         [standalone]

  06 (Dep Upgrades) ───────────────▶ 07 (OpenAI SDK v2)
```

## Parallel Execution Guide

**Wave 1 — All independent, touch disjoint files:**
- Phase 01: `shitpost_ai/shitpost_analyzer.py`, `shit/s3/s3_data_lake.py`, `shit/utils/error_handling.py`, `shit/llm/prompts.py`, `shit/market_data/models.py`, `shitposts/twitter_harvester.py`, `shit/market_data/backfill_prices.py`
- Phase 02: `shitty_ui/data/signal_queries.py`
- Phase 03: `shitvault/cli.py`, `shitvault/event_consumer.py`, `shitpost_ai/cli.py`, `shitposts/cli.py`
- Phase 04: `shitty_ui/callbacks/alerts.py`, `shitty_ui/pages/dashboard.py`
- Phase 06: `requirements.txt` (pinning only, no code changes)

**Wave 2 — After Wave 1 prerequisites complete:**
- Phase 05: Requires 02 (query builder extracted) and 04 (callbacks split) — new test files only, no production code changes
- Phase 07: Requires 06 (deps upgraded) — touches `shit/llm/llm_client.py` and related LLM modules
- Phase 08: Requires 04 (callbacks split) — touches all `shitty_ui/` files for Dash 4 API changes

**Conflict analysis:** No two Wave 1 phases modify the same file. Phase 03 touches `shitvault/cli.py` while Phase 02 touches `shitty_ui/data/signal_queries.py` — fully disjoint. Phase 04 touches `shitty_ui/callbacks/alerts.py` and `shitty_ui/pages/dashboard.py` which Phase 02 does not touch.
