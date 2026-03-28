# Tech Debt Overview — 2026-03-26

**Session**: `tech-debt-2026-03-26`
**Scan date**: 2026-03-26
**Scan scope**: Full codebase (147 source files, 110 test files, ~2,338 tests)
**Archive destination**: `documentation/archive/tech-debt-2026-03-26/`

---

## Executive Summary

A full codebase scan of shitpost-alpha identified **5 actionable workstreams** across security, test coverage, dependency hygiene, code complexity, and legacy cleanup. The most urgent finding is that the **FastAPI API module (`api/`) has zero test coverage** despite serving production traffic on Railway, compounded by a **CORS wildcard (`allow_origins=["*"]`)** that exposes every endpoint to cross-origin abuse. The notifications database layer has thin coverage with 11 functions sharing a duplicated try/session/except pattern ripe for deduplication. Four unused dependencies inflate the install footprint, the outcome calculator contains a 245-line function begging for decomposition, and 5 stale TODOs plus misleading "Phase 2" comments add friction for future contributors.

The remediation is organized into 5 phases (one PR each), prioritized by production risk. Phases 1 and 2 can execute in parallel since they touch entirely disjoint file sets. Phases 3-5 are independent of each other and of Phases 1-2.

---

## Complete Inventory

### CRITICAL

| # | Finding | Location | Blast Radius | Fix Complexity | Risk if Unfixed |
|---|---------|----------|--------------|----------------|-----------------|
| C1 | **API module has zero test coverage** | `api/main.py`, `api/routers/feed.py`, `api/routers/prices.py`, `api/routers/telegram.py`, `api/queries/feed_queries.py`, `api/queries/price_queries.py`, `api/schemas/feed.py`, `api/dependencies.py` | HIGH -- any regression in feed, price, or webhook endpoints is invisible until users report it | MEDIUM -- ~50 tests across 3-4 test files using `httpx.ASGITransport` | Silent production regressions, broken Telegram webhook ingestion, incorrect price/feed data served to React frontend |
| C2 | **CORS wildcard in production** | `api/main.py:33` (`allow_origins=["*"]`) | HIGH -- every browser on the internet can make authenticated requests to the API | LOW -- replace `*` with environment-driven allowlist | Cross-site request forgery, data exfiltration, Telegram webhook spoofing |

### HIGH

| # | Finding | Location | Blast Radius | Fix Complexity | Risk if Unfixed |
|---|---------|----------|--------------|----------------|-----------------|
| H1 | **Notifications DB thin test coverage** | `notifications/db.py` (461 lines, 11 functions) | MEDIUM -- alert delivery failures affect Telegram subscribers | MEDIUM -- ~30 tests covering all 11 functions | Silent subscription bugs, alert delivery failures, error counter drift |
| H2 | **Notifications DB duplicated query pattern** | `notifications/db.py` -- every function repeats try/get_session/except/finally | LOW -- code smell, no production impact | LOW -- extract shared session-management helper | Maintenance burden, copy-paste bugs on future changes |

### MEDIUM

| # | Finding | Location | Blast Radius | Fix Complexity | Risk if Unfixed |
|---|---------|----------|--------------|----------------|-----------------|
| M1 | **245-line function in outcome_calculator** | `shit/market_data/outcome_calculator.py:~158` (`_calculate_single_outcome`) | LOW -- well-tested (725-line test file), but hard to review/modify | MEDIUM -- decompose into 3 focused helpers | Increasing cognitive load, harder code review, elevated bug risk on future changes |
| M2 | **754-line CLI with 14 commands** | `shit/market_data/cli.py` | LOW -- CLI is developer-facing, not user-facing | MEDIUM -- split into 3 sub-modules | Slow IDE navigation, merge conflicts when multiple devs touch CLI |
| M3 | **4 unused dependencies** | `requirements.txt` lines for `apscheduler`, `asyncio-mqtt`, `asyncio-throttle`, `structlog` | LOW -- no runtime impact, inflates install | LOW -- delete 4 lines | Slower installs, misleading dependency list, potential supply-chain surface |
| M4 | **65 outdated packages** | `requirements.txt` (notable: openai 2.24->2.30, pydantic 2.11->2.12, psycopg 3.2->3.3, sqlalchemy 2.0.47->2.0.48) | MEDIUM -- security patches, bug fixes accumulating | MEDIUM -- bump minors only, skip pandas 3.x and pytest 9.x majors | Missed security patches, growing upgrade delta, eventual forced migration |

### LOW

| # | Finding | Location | Blast Radius | Fix Complexity | Risk if Unfixed |
|---|---------|----------|--------------|----------------|-----------------|
| L1 | **5 stale TODO comments** | `shitposts/twitter_harvester.py:66,92`, `shitvault/s3_processor.py:217`, `shit/utils/error_handling.py:26,27` | NONE -- informational | LOW -- resolve or convert to tracked issues | Mental clutter, false impression of incomplete work |
| L2 | **Misleading "Phase 2" comments** | `requirements.txt:37-44` | NONE -- informational | LOW -- update or remove comments | Confuses new contributors about project roadmap |
| L3 | **Dual PostgreSQL drivers** | `psycopg[binary]` (async) + `psycopg2-binary` (sync) both in requirements | NONE -- both are actively used | N/A -- keep both, document rationale | Minor confusion for new contributors |
| L4 | **`twilio` dependency (lazy import)** | `notifications/dispatcher.py:331` | NONE -- lazy-loaded, never called in current flow | LOW -- annotate in requirements.txt | Misleading dependency list |

---

## Prioritized Remediation Order

| Phase | PR Title | Priority | Findings Addressed | Effort | Risk |
|-------|----------|----------|-------------------|--------|------|
| **1** | API Test Coverage + Security Hardening | HIGHEST | C1, C2 | High (~50 tests, CORS fix) | Medium (touches production config) |
| **2** | Notifications Test Coverage + Query Dedup | HIGH | H1, H2 | Medium (~30 tests, helper extraction) | Low (additive tests + internal refactor) |
| **3** | Dependency Cleanup | MEDIUM | M3, M4, L2, L4 | Low (delete lines, bump versions) | Low (minor version bumps only) |
| **4** | outcome_calculator Decomposition + CLI Split | MEDIUM | M1, M2 | Medium (refactor 2 files, update tests) | Medium (production code refactor) |
| **5** | TODO Resolution + Legacy Documentation | LOWER | L1, L3 | Low (resolve/convert 5 TODOs, add comments) | None |

### Why this order

1. **Phase 1 first** because zero test coverage on a production API is the highest-risk finding. The CORS wildcard is a security issue that should ship with the tests so the fix is verified.
2. **Phase 2 parallel with Phase 1** because notifications DB is the second-largest coverage gap and touches completely disjoint files.
3. **Phase 3 after 1-2** because dependency cleanup benefits from the new test coverage -- bumping packages is safer when tests catch regressions.
4. **Phase 4 after 1-2** because outcome_calculator decomposition is a production code refactor that benefits from the broader test safety net established in Phases 1-2.
5. **Phase 5 last** because TODOs and documentation have zero production risk and can be done anytime.

---

## Dependency Matrix

```
Phase 1 (API Tests + CORS) ──────┐
                                  ├──→ Phase 3 (Deps) ──→ [done]
Phase 2 (Notifications Tests) ────┘
                                  ├──→ Phase 4 (Decomposition) ──→ [done]
                                  │
                                  └──→ Phase 5 (TODOs) ──→ [done]
```

| Phase | Blocked By | Unlocks |
|-------|-----------|---------|
| 1 | None | 3, 4 (safer with test coverage) |
| 2 | None | 3, 4 (safer with test coverage) |
| 3 | None (recommended after 1-2) | None |
| 4 | None (recommended after 1-2) | None |
| 5 | None | None |

**Parallel safety:**
- **Phases 1 and 2**: SAFE to run in parallel. Phase 1 touches `api/`, `shit_tests/api/`. Phase 2 touches `notifications/db.py`, `shit_tests/notifications/`. Zero file overlap.
- **Phases 3, 4, 5**: SAFE to run in parallel with each other and after 1-2. Phase 3 touches `requirements.txt`. Phase 4 touches `shit/market_data/outcome_calculator.py`, `shit/market_data/cli.py`, and their tests. Phase 5 touches `shitposts/twitter_harvester.py`, `shitvault/s3_processor.py`, `shit/utils/error_handling.py`.

---

## Phase Summary Table

| # | PR Title | Priority | Effort | Risk | Dependencies | Unlocks | Key Files |
|---|----------|----------|--------|------|-------------|---------|-----------|
| 1 | API Test Coverage + Security Hardening | HIGHEST | High (~50 tests) | Medium | None | 3, 4 | `api/**`, `shit_tests/api/**` (new) |
| 2 | Notifications Test Coverage + Query Dedup | HIGH | Medium (~30 tests) | Low | None | 3, 4 | `notifications/db.py`, `shit_tests/notifications/` |
| 3 | Dependency Cleanup | MEDIUM | Low | Low | Recommended after 1-2 | None | `requirements.txt` |
| 4 | outcome_calculator Decomposition + CLI Split | MEDIUM | Medium | Medium | Recommended after 1-2 | None | `shit/market_data/outcome_calculator.py`, `shit/market_data/cli.py`, `shit/market_data/cli_fetch.py` (new), `shit/market_data/cli_outcomes.py` (new), `shit/market_data/cli_registry.py` (new) |
| 5 | TODO Resolution + Legacy Documentation | LOWER | Low | None | None | None | `shitposts/twitter_harvester.py`, `shitvault/s3_processor.py`, `shit/utils/error_handling.py`, `requirements.txt` |

---

## Out of Scope

The following items were noted during the scan but are explicitly **not addressed** in this remediation:

- **Dash dashboard (`shitty_ui/`) refactoring** -- this module is being retired in favor of the React+FastAPI frontend. No investment in refactoring retiring code.
- **pandas 3.x major upgrade** -- breaking changes require dedicated migration effort; skip for now and revisit when pandas 2.x reaches EOL.
- **pytest 9.x major upgrade** -- breaking changes to fixture semantics; skip for now.
- **Dual PostgreSQL driver consolidation** -- both `psycopg` (async) and `psycopg2-binary` (sync) are actively used by different subsystems. Document rationale but do not consolidate.
- **Signals migration backfill** -- tracked separately in `documentation/planning/SIGNALS_MIGRATION.md`.
