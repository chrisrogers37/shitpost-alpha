# WS10 — Market Data / Outcome Calculator Correctness & Decomposition

**Priority**: MEDIUM
**Type**: bug / complexity
**Findings**: M1, M2, M3, M4, M5
**Primary files**: `shit/market_data/outcome_calculator.py`, `shit/market_data/calibration.py`, `shit/market_data/auto_backfill_service.py`

---

> Note: outcome_calculator decomposition was partially attempted in `tech-debt-2026-03-26` (M1). This workstream folds in the correctness bugs found alongside the size problem.

## Findings

### M2 — Per-asset commit inside the prediction loop
`outcome_calculator.py:251` commits after each asset in `_calculate_single_outcome`. A mid-loop failure persists partial outcomes for a prediction, and the pattern adds transaction overhead.

**Fix**: Commit once per prediction (all assets in one transaction), rolling back the whole prediction on failure.

### M3 — Outcome/calibration date-anchor mismatch
Batch processing filters on `Prediction.created_at` (`:508-510`) while the outcome math anchors on **post publication time** (`_get_source_date`, `:762-776`). Calibration filters on `p.created_at` too (`calibration.py:114`). Predictions analyzed late (backfill) can be excluded or scoped to the wrong window.

**Fix**: Anchor batch selection and calibration windows on post publication time consistently.

### M4 — Sentiment fallback misattributes accuracy
`:816-818`: when an asset isn’t present in `market_impact`, the code falls back to the first sentiment in the dict, scoring multi-asset predictions against the wrong asset’s sentiment.

**Fix**: Skip (or explicitly mark unknown) assets missing from `market_impact` rather than borrowing another asset’s sentiment.

### M5 — `get_missing_tickers()` coarse existence check
`auto_backfill_service.py:65-71` checks whether a symbol exists *anywhere* in `market_prices`, not whether the **required date range** is covered, so partial history skips needed backfill.

**Fix**: Check coverage for the required `[start, end]` window, not mere existence.

### M1 — `OutcomeCalculator` god class (~819 lines)
One class handles price resolution, timeframe fills, intraday snapshots, batch stats, maturation, and accuracy.

**Fix**: Extract cohesive helpers (price resolution, timeframe/return computation, accuracy/P&L, batch orchestration) so each is independently testable. Preserve the existing 725-line test suite behavior.

### Minor (fold in)
- `last_price_update = date.today()` assigned to a `DateTime` column (`:245`) — use a datetime.
- `stats["outcomes_updated"]` defined but never incremented (`:528-539`) — misleading batch reporting.
- Dynamic `correct_{timeframe}` f-string in SQL (`calibration.py:102-115`) is safe today (validated) but fragile — keep the validation assertion adjacent.

## Acceptance criteria

- [ ] One transaction per prediction; partial-asset writes cannot persist on failure (test).
- [ ] Batch selection and calibration windows anchor on post publication time (test with a late-analyzed prediction).
- [ ] Assets absent from `market_impact` are not scored against another asset’s sentiment (test).
- [ ] Ticker backfill triggers when the required date range isn’t fully covered (test).
- [ ] `OutcomeCalculator` split into focused units with tests green.
