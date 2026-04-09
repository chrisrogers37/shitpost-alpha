# Investigation: Missing Price Data for Tickers (RTN et al.)

**Status:** COMPLETE
**Started:** 2026-04-09
**PR:** #132
**Date:** 2026-04-09
**Trigger:** RTN (Raytheon) shows "No price data available" on dispatch 1 of 383
**Root Cause:** LLM extracts delisted/renamed/conceptual symbols with no validation before registration

---

## Problem Sized

| Category | Count | Examples | Cause |
|---|---|---|---|
| **Not tickers** | 3 | DEFENSE, CRYPTO, NEWSMAX | LLM extracted concepts as ticker symbols |
| **Delisted/renamed** | 14 | RTN→RTX, TWTR, FB→META, RDS.A→SHEL, CBS→PARA, X (US Steel) | LLM used old/invalid symbols |
| **Active, need backfill** | 109 | AAPL, TSLA, AMZN | Auto-registered during FK migration, no prices yet |
| **Active, backfill failed** | ~46 | Various indices, foreign tickers | yfinance couldn't find data but not marked invalid |

**Impact:** 377 of 2,694 completed predictions (14%) have at least one bad ticker.

## Code Path Gaps

| Stage | File | Validation | Gap |
|---|---|---|---|
| LLM prompt | `shit/llm/prompts.py:67-72` | "Use standard ticker symbols" | No delisted/concept guidance |
| Registration | `shit/market_data/ticker_registry.py:48-55` | Format only (length, spaces) | No yfinance validation |
| Fundamentals | `shit/market_data/fundamentals_provider.py:82-90` | Returns `{}` on failure | Doesn't mark invalid |
| Backfill | `shit/market_data/auto_backfill_service.py:145-158` | Marks invalid on 0 prices | Correct but runs minutes later |
| Feed API | `api/queries/feed_queries.py:57-63` | None | Shows invalid tickers |
| Frontend | `frontend/src/pages/FeedPage.tsx:101-114` | Null coalescing | Shows "No price data" |

## Known Ticker Remappings (Corporate Actions)

| Old Symbol | Current Symbol | Corporate Action |
|---|---|---|
| RTN | RTX | Raytheon/UTC merger (Apr 2020) |
| TWTR | — | Twitter taken private by Musk (Oct 2022) |
| FB | META | Facebook rebrand (Oct 2021) |
| RDS.A / RDS.B | SHEL | Shell plc renamed (Jan 2022) |
| CBS | PARA | CBS/Viacom merger → Paramount (Dec 2019) |
| PTR | 0857.HK | PetroChina delisted from NYSE (Sep 2022) |
| SNP | 0386.HK | China Petroleum delisted from NYSE (Sep 2022) |
| AKS | CLF | AK Steel acquired by Cleveland-Cliffs (Mar 2020) |
| X | — | US Steel — actually still listed, yfinance issue? |
| KOL | — | VanEck Coal ETF closed (Dec 2020) |
| OIL | — | iPath Oil ETN delisted (Apr 2021) |

## Not Tickers (Concepts)

- DEFENSE — military/defense concept, not a ticker
- CRYPTO — cryptocurrency concept, not a ticker
- NEWSMAX — media company, not publicly traded (was briefly NMAX in 2025?)

---

## Fix Plan: 5 Tiers

See numbered docs in this directory for implementation details.

### Challenge Round Decisions (2026-04-09)

| # | Challenge | Decision | Rationale |
|---|-----------|----------|-----------|
| 1 | Analyzer vs. registry integration | **Analyzer only** | Single gate at the source. Registry is downstream, works on already-stored assets. DRY, clean separation. |
| 2 | yfinance spot-check latency | **Include with registry-first skip** | 0ms for known-active symbols (cached query). ~300ms only for novel unknowns. Negligible vs. 3-5s LLM call. |
| 3 | PR strategy | **One PR (Tiers 1-4), Tier 5 post-deploy** | Tightly coupled code changes ship together. Data ops run after deploy with backup. |
| 4 | Ticker display filtering | **SQL filter only, drop frontend changes** | Frontend already handles missing outcomes. API is single source of truth. Asset list filtered in feed_service.py. |
| 5 | Tier 5 approach | **CLI commands, not ad-hoc scripts** | Fits CLI-first pattern (13 existing commands). Repeatable for future corporate actions. |
