# Dashboard UI Overhaul — Session Overview

**Session Name**: `dashboard-ui-overhaul`
**Date**: 2026-02-12
**Scope**: `shitty_ui/` dashboard module — all 4 pages (Dashboard, Signals, Trends, Performance)
**Origin**: Live browser-based UI review of production dashboard at `shitpost-alpha-dash.up.railway.app`

---

## User's Stated Goals

- Fix broken functionality (signals page, duplicate cards, zero KPIs)
- Reduce information overload on the main dashboard
- Add visual polish (sentiment colors, typography, confidence consistency)
- Make the dashboard scannable and useful at a glance

---

## Phase Summary

| # | Phase | Risk | Effort | Files Modified |
|---|-------|------|--------|----------------|
| 01 | Label Countdown Timer | Low | ~30 min | `components/header.py` |
| 02 | Trends Auto-Select | Low | ~45 min | `pages/trends.py`, `data.py` |
| 03 | Fix Broken Signals Page | Medium | ~2 hrs | `pages/signals.py`, `data.py`, `components/cards.py` |
| 04 | Fix Duplicate Signal Cards | Medium | ~2 hrs | `data.py`, `pages/dashboard.py`, `components/cards.py` |
| 05 | Strip URLs from Cards | Low | ~30 min | `components/cards.py` |
| 06 | Consistent Confidence Display | Low | ~20 min | `components/cards.py` |
| 07 | Sentiment Visual Differentiation | Low | ~1.5 hrs | `components/cards.py`, `constants.py` |
| 08 | Smart Empty States | Low | ~1 hr | `pages/dashboard.py`, `components/cards.py`, `layout.py` |
| 09 | Unify Dashboard KPIs | Medium | ~1.5 hrs | `pages/dashboard.py`, `data.py` |
| 10 | Visual Hierarchy & Typography | Low | ~1.5 hrs | `layout.py`, `constants.py`, `components/header.py` |
| 11 | Dashboard IA Redesign | Medium | ~3 hrs | `pages/dashboard.py`, `layout.py` |

**Total estimated effort**: ~14.5 hours

---

## Dependency Graph

```
Batch 1 (parallel — all touch disjoint files):
  ├── 01  Label Countdown Timer       → components/header.py
  ├── 02  Trends Auto-Select          → pages/trends.py, data.py
  ├── 03  Fix Broken Signals Page     → pages/signals.py, data.py, components/cards.py
  └── 05  Strip URLs from Cards       → components/cards.py

Batch 2 (after Batch 1 — depends on 03's cards.py and data.py changes):
  ├── 04  Fix Duplicate Signals       → data.py, pages/dashboard.py, components/cards.py
  └── 06  Consistent Confidence       → components/cards.py

Batch 3 (after Batch 2 — depends on 04+06's cards.py changes):
  ├── 07  Sentiment Visual Diff       → components/cards.py, constants.py
  └── 09  Unify Dashboard KPIs        → pages/dashboard.py, data.py

Batch 4 (after Batch 3 — depends on 07's constants.py, 09's dashboard.py):
  ├── 08  Smart Empty States          → pages/dashboard.py, components/cards.py, layout.py
  └── 10  Visual Hierarchy            → layout.py, constants.py, components/header.py

Batch 5 (after Batch 4 — depends on 08+10's dashboard.py and layout.py):
  └── 11  Dashboard IA Redesign       → pages/dashboard.py, layout.py
```

### Key Dependencies

- **Phase 03 → Phase 04**: Both modify `data.py` and `components/cards.py`. Phase 03 adds `_safe_get` helper and fixes NaN handling; Phase 04 adds SQL deduplication. Must be sequential.
- **Phase 04/06 → Phase 07**: Phase 07 adds sentiment background colors to card functions modified by 04 and 06.
- **Phase 07 → Phase 08**: Phase 08 adds empty state patterns to cards modified by Phase 07.
- **Phase 09 → Phase 11**: Phase 11 restructures the dashboard layout built by Phase 09's KPI rewrite.
- **Phase 10 → Phase 11**: Phase 11 modifies `layout.py` CSS that Phase 10 also touches.

### Parallel Opportunities

Within each batch, the listed phases touch **disjoint file sets** and can be implemented as parallel PRs from the same base branch:
- Batch 1: 4 PRs in parallel
- Batch 2: 2 PRs in parallel
- Batch 3: 2 PRs in parallel
- Batch 4: 2 PRs in parallel
- Batch 5: 1 PR (final)

---

## File Touch Matrix

| File | 01 | 02 | 03 | 04 | 05 | 06 | 07 | 08 | 09 | 10 | 11 |
|------|----|----|----|----|----|----|----|----|----|----|-----|
| `components/header.py` | **W** | | | | | | | | | **W** | |
| `pages/trends.py` | | **W** | | | | | | | | | |
| `data.py` | | **W** | **W** | **W** | | | | | **W** | | |
| `pages/signals.py` | | | **W** | | | | | | | | |
| `components/cards.py` | | | **W** | **W** | **W** | **W** | **W** | **W** | | | |
| `pages/dashboard.py` | | | | **W** | | | | **W** | **W** | | **W** |
| `constants.py` | | | | | | | **W** | | | **W** | |
| `layout.py` | | | | | | | | **W** | | **W** | **W** |

**W** = Write (file is modified by this phase)

---

## Implementation Order

```
Phase 01 ─┐
Phase 02 ─┤
Phase 03 ─┼─→ Phase 04 ─┐
Phase 05 ─┘   Phase 06 ─┼─→ Phase 07 ─┐
                         │   Phase 09 ─┼─→ Phase 08 ─┐
                         │             │   Phase 10 ─┼─→ Phase 11
                         └─────────────┘             │
                                                     └──→ DONE
```

---

## Phase Docs

| File | Lines | Description |
|------|-------|-------------|
| [`01_label-countdown-timer.md`](01_label-countdown-timer.md) | 318 | Add "Next refresh" and "Last updated" labels to header timer |
| [`02_trends-auto-select.md`](02_trends-auto-select.md) | 484 | Auto-select top predicted asset on /trends, hide Plotly modebar |
| [`03_fix-signals-page.md`](03_fix-signals-page.md) | 990 | Fix /signals stuck on loading — NaN handling, try/except callbacks |
| [`04_fix-duplicate-signals.md`](04_fix-duplicate-signals.md) | 873 | Deduplicate hero signal cards via SQL GROUP BY |
| [`05_strip-urls-from-cards.md`](05_strip-urls-from-cards.md) | 367 | Add `strip_urls()` regex helper, apply to all card previews |
| [`06_consistent-confidence.md`](06_consistent-confidence.md) | 456 | Standardize confidence to bare `75%` format across all cards |
| [`07_sentiment-visual-differentiation.md`](07_sentiment-visual-differentiation.md) | 1,008 | Sentiment background colors + 3px left borders on all cards |
| [`08_smart-empty-states.md`](08_smart-empty-states.md) | 527 | Replace empty charts with compact 80px informative placeholders |
| [`09_unify-dashboard-kpis.md`](09_unify-dashboard-kpis.md) | 632 | New `get_dashboard_kpis()` querying only evaluated predictions |
| [`10_visual-hierarchy-typography.md`](10_visual-hierarchy-typography.md) | 878 | Font size/weight constants, CSS classes, active nav state |
| [`11_dashboard-ia-redesign.md`](11_dashboard-ia-redesign.md) | 1,175 | Tabbed analytics, remove Asset Deep Dive/Alert History, promote posts |

**Total**: 7,708 lines across 11 phase docs + this overview

---

## Test Files Modified

| Phase | Test File | New Tests |
|-------|-----------|-----------|
| 01 | `shit_tests/shitty_ui/test_layout.py` | `TestCreateHeaderLabels` |
| 02 | `shit_tests/shitty_ui/test_layout.py` | `TestTrendsAutoSelect` |
| 03 | `shit_tests/shitty_ui/test_signals_page.py` (new) | `TestSafeGet`, `TestSignalCardCreation`, `TestSignalCallbacks` |
| 04 | `shit_tests/shitty_ui/test_layout.py` | `TestDeduplicatedSignals`, `TestHeroSignalCard` |
| 05 | `shit_tests/shitty_ui/test_layout.py` | `TestStripUrls` |
| 06 | `shit_tests/shitty_ui/test_layout.py` | `TestConsistentConfidence` |
| 07 | `shit_tests/shitty_ui/test_layout.py` | `TestSentimentStyles`, `TestSentimentConstants` |
| 08 | `shit_tests/shitty_ui/test_layout.py` | `TestEmptyStateChart` |
| 09 | `shit_tests/shitty_ui/test_layout.py` | `TestDashboardKpis` |
| 10 | `shit_tests/shitty_ui/test_layout.py` | `TestTypographyConstants`, `TestIndexStringCSS` |
| 11 | `shit_tests/shitty_ui/test_layout.py` | `TestDashboardPageStructure`, `TestAnalyticsTabsCSS` |
