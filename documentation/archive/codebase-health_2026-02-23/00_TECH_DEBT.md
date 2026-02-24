# Tech Debt: Codebase Health

**Session**: codebase-health
**Date**: 2026-02-23
**Scope**: Full codebase scan — test infrastructure, UI module splitting, test coverage gaps, CSS extraction, worker deduplication

---

## Inventory Summary

| # | Category | Severity | Finding |
|---|----------|----------|---------|
| 1 | Test infrastructure | **HIGH** | pytest_plugins in non-root conftest blocks test collection; 10 tests failing (5 config, 5 stale bypass) |
| 2 | Code duplication | **MEDIUM** | 4 duplicated patterns across 6 megafunctions in cards.py (2,041 lines) |
| 3 | Module size | **MEDIUM** | cards.py (2,041 lines) — 6 megafunctions with shared patterns, no separation of concerns |
| 4 | Module size | **MEDIUM-HIGH** | data.py (2,865 lines) — 60+ query functions in a single file, cache invalidation scattered |
| 5 | Test coverage | **CRITICAL** | 4 production event consumers + CLI have zero test coverage (~60-80 tests needed) |
| 6 | Module size + test gap | **MEDIUM-HIGH** | alerts.py (1,240 lines) — 2 megafunctions, 19 callbacks, zero tests |
| 7 | Code organization | **LOW-MEDIUM** | 611 lines of inline CSS in layout.py (lines 80-690), zero Python dependencies |
| 8 | Code duplication | **MEDIUM** | 4 event consumers have identical 28-line main() functions (~100 eliminable lines) |

---

## Remediation Phases

| Phase | Slug | PR Title | Risk | Effort | Depends On | Unlocks |
|-------|------|----------|------|--------|------------|---------|
| 01 | fix-conftest-and-failing-tests | fix: resolve conftest pytest_plugins blocker, delete stale bypass tests, modernize settings config | Low | Low (~1-2h) | None | 02-08 | ✅ PR #88 |
| 02 | extract-shared-ui-helpers | refactor: extract shared UI helpers from cards.py | Low | Low (~1-2h) | 01 | 03 | ✅ PR #89 |
| 03 | split-cards-modules | refactor: split 2041-line cards.py into card module package | Low | Medium (~2-3h) | 02 | — | ✅ PR #94 |
| 04 | split-data-modules | refactor: split 2865-line data.py into domain query modules | Medium | High (~4-6h) | 01 | — | ✅ PR #90 |
| 05 | event-system-tests | test: add 52 tests for event consumers, worker gaps, and CLI | Low | High (~4-6h) | 01 | 08 | ✅ PR #93 |
| 06 | alerts-refactor-and-tests | refactor: extract alert components and add 60 callback tests | Medium | High (~4-6h) | 01 | — | ✅ PR #92 |
| 07 | extract-css-to-stylesheet | refactor: extract 611 lines of inline CSS to external stylesheet | Low | Low (~1h) | 01 | — | ✅ PR #91 |
| 08 | dedup-event-worker-cli | refactor: extract run_worker_main() helper, deduplicate 4 event consumers | Low | Low (~1-2h) | 01, 05 | — | ✅ PR #95 |

**Total estimated effort**: ~18-27 hours across 8 PRs

---

## Dependency Graph

```
Phase 01 (foundation) ──┬──→ Phase 02 ──→ Phase 03
                        ├──→ Phase 04
                        ├──→ Phase 05 ──→ Phase 08
                        ├──→ Phase 06
                        └──→ Phase 07
```

### Parallel Execution Guide

After Phase 01 merges, these groups can run **in parallel** (they touch disjoint files):

| Group | Phases | Files Touched |
|-------|--------|---------------|
| A | 02 → 03 | `shitty_ui/components/cards.py`, `shitty_ui/components/helpers.py` |
| B | 04 | `shitty_ui/data.py` → `shitty_ui/data/` |
| C | 05 → 08 | `shit/events/`, `shit_tests/events/`, event consumers |
| D | 06 | `shitty_ui/callbacks/alerts.py` |
| E | 07 | `shitty_ui/layout.py`, `shitty_ui/assets/` |

Groups A–E are fully independent. Within a group, phases are sequential.

---

## Phase Documents

1. [01 — Fix conftest & failing tests](01_fix-conftest-and-failing-tests.md)
2. [02 — Extract shared UI helpers](02_extract-shared-ui-helpers.md)
3. [03 — Split cards.py into modules](03_split-cards-modules.md)
4. [04 — Split data.py into modules](04_split-data-modules.md)
5. [05 — Event system test coverage](05_event-system-tests.md)
6. [06 — Alerts refactor & tests](06_alerts-refactor-and-tests.md)
7. [07 — Extract CSS to stylesheet](07_extract-css-to-stylesheet.md)
8. [08 — Deduplicate event worker CLI](08_dedup-event-worker-cli.md)

---

## Research Files

Detailed analysis files used to generate phase docs: `/tmp/tech-debt-2026-02-23_120000/research/`

| File | Contents |
|------|----------|
| `01-conftest-and-failing-tests.md` | pytest_plugins blocker, 10 failing tests, Pydantic V2 settings |
| `02-cards-duplication.md` | 4 duplication patterns in cards.py (2,041 lines) |
| `04-data-splitting.md` | 60+ functions in data.py (2,865 lines), 7-module split proposal |
| `05-event-system-tests.md` | 62 existing tests, 60-80 new tests needed |
| `06-alerts-refactor.md` | alerts.py (1,240 lines), 2 megafunctions, 19 callbacks |
| `07-css-extraction.md` | 611 lines CSS in layout.py, zero Python dependencies |
| `08-worker-dedup.md` | 4 identical 28-line main() functions |
