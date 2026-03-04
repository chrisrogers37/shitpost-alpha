# Alpha Quality: Product Enhancement Session

**Session:** alpha-quality
**Date:** 2026-03-04
**Scope:** Comprehensive quality overhaul — outcome maturation, bug fixes, multi-timeframe support, analytics charts, company fundamentals, and market-aware timing

## User Goals

The system has significant gaps between its intent (predict market movements from Trump's Truth Social posts and track performance) and its current implementation:

1. Predictions sit on the home page without outcomes — no maturation pipeline re-evaluates them
2. Only T+7 is surfaced despite T+1, T+3, T+30 all being calculated
3. NaN values leak to the UI, sentiment is mis-extracted, the 7D default view is structurally empty
4. No company fundamentals, no financial context for tracked tickers
5. Analytics query functions exist but aren't wired to any charts
6. Calendar-day math instead of trading-day math; no intraday price data

## Phase Summary

| #  | Phase | Impact | Effort | Risk | Files |
|----|-------|--------|--------|------|-------|
| 01 | ~~Outcome Maturation Pipeline~~ | High | Medium | Low | 4 mod, 1 new | ✅ PR #104 |
| 02 | ~~Fix Sentiment Bug & NaN Guards~~ | High | Low | Low | 6 mod, 0 new | ✅ PR #105 |
| 03 | ~~Smart Default View & Copy Cleanup~~ | High | Medium | Medium | 8 mod, 0 new | ✅ PR #106 |
| 04 | ~~Multi-Timeframe Dashboard~~ | High | High | Medium | 13 mod, 2 new | ✅ PR #107 |
| 05 | [Analytics Charts](05_analytics-charts.md) | Medium | Medium | Medium | 7 mod, 3 new |
| 06 | [Company Fundamentals & Asset Profiles](06_company-fundamentals-asset-profiles.md) | Medium | High | Medium | 9 mod, 3 new |
| 07 | [Market-Aware Timing](07_market-aware-timing.md) | Medium | High | High | 7 mod, 3 new |

## Dependency Graph

```
Phase 01 (Outcome Maturation)
    └─→ Phase 02 (Bug Fixes) ─ depends on 01: outcomes must exist to fix NaN display
         └─→ Phase 03 (Default View) ─ depends on 02: screener needs correct data
              └─→ Phase 04 (Multi-Timeframe) ─ depends on 03: builds on fixed queries

Phase 05 (Analytics Charts) ─ independent, can run in parallel with 03-04
Phase 06 (Company Fundamentals) ─ independent, can run in parallel with anything
Phase 07 (Market-Aware Timing) ─ independent, can run in parallel with anything
```

## Parallelization

### Must be sequential
- **01 → 02 → 03 → 04**: Core data pipeline. Each phase depends on the previous producing correct, non-empty data.

### Can run in parallel
- **Phase 05** (Analytics Charts): Only adds new UI components wired to existing query functions. No overlap with phases 01-04.
- **Phase 06** (Company Fundamentals): Touches `TickerRegistry` model and asset detail page. Disjoint from the outcome/query path.
- **Phase 07** (Market-Aware Timing): Modifies `outcome_calculator.py` and `models.py`. Should run AFTER Phase 01 (which also modifies `outcome_calculator.py`) to avoid merge conflicts. Can run in parallel with 05 and 06.

### Recommended execution order
1. **Phase 01** (unblocks everything)
2. **Phase 02** (quick wins, fixes NaN and sentiment)
3. **Phases 03 + 05 + 06** (in parallel — disjoint file sets)
4. **Phase 04** (after 03 completes)
5. **Phase 07** (after 01 completes, ideally last)

## Total Estimated Effort

~15-20 engineering days across all 7 phases.
