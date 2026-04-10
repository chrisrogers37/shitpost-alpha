# 06: Confidence Calibration

**Feature**: Build a calibration curve from 1000+ historical predictions to map raw LLM confidence to actual accuracy rates.

**Status**: IN PROGRESS  
**Started**: 2026-04-10  
**Priority**: High  
**Estimated Effort**: 2-3 sessions  

---

## Challenge Round Resolutions

1. **Calibration method: Lookup table only (no sklearn).** Isotonic regression adds a ~50MB dependency for marginal smoothing between bins. With 10 bins and 100+ samples/bin, lookup table accuracy is sufficient. No pickle, no BYTEA, no sklearn versioning. Add isotonic later if data volume justifies it.

2. **Scope: Global only for v1 (no per-provider/per-asset).** System uses one LLM provider. Feature 05 (ensemble) isn't built. Adding scope later = add column + WHERE clause (~30 min). No `scope` column in table.

3. **Entry point: `python -m shit.market_data.calibration --refit` (not root-level `calibration_cron.py`).** Follows existing CLI patterns (`shit/echoes/backfill.py`, `shit/market_data/cli.py`).

4. **Table simplified.** No `scope` column, no `model_bytes` BYTEA column. Just JSONB for bin_stats and lookup_table.

5. **Staleness guard added.** `max_age_days=30` on curve loading. Returns None if curve is older than threshold — falls back to raw confidence gracefully.

---

## Overview

The LLM assigns a confidence score (0.0-1.0) to every prediction. But "0.8 confidence" is meaningless without knowing whether 80%-confident predictions are actually correct 80% of the time, or 50%, or 95%. Calibration maps raw LLM confidence to empirical accuracy using historical prediction outcomes.

The system already has all the data needed:
- `predictions` table has `confidence` (0.0-1.0) for 1000+ completed analyses.
- `prediction_outcomes` table has `correct_t1`, `correct_t3`, `correct_t7`, `correct_t30` boolean accuracy flags.
- `OutcomeCalculator.get_accuracy_stats()` can already query accuracy by timeframe.

What's missing: binning predictions by confidence, computing empirical accuracy per bin, fitting a calibration function, applying it at prediction storage time, and refreshing it on a schedule.

---

## Motivation

1. **Uncalibrated confidence is misleading**: If the LLM says 0.9 confidence but historically 0.9 predictions are only 65% correct, subscribers are making decisions on inflated numbers.
2. **Better alerting thresholds**: The default `min_confidence: 0.7` subscriber preference is arbitrary. With calibration, we can set thresholds in terms of actual expected accuracy: "only alert me when the prediction has >= 60% historical accuracy."
3. **Ensemble integration**: Feature 05 (Multi-LLM Ensemble) produces consensus confidence. Calibrating consensus confidence separately from single-model confidence gives better accuracy estimates.
4. **Trust building**: Showing "this confidence level has been historically correct 71% of the time" in the frontend and alerts builds user trust.

---

## Statistical Approach

### Binning Strategy

Divide the confidence range [0.0, 1.0] into 10 bins of width 0.1:

| Bin | Range | Example |
|-----|-------|---------|
| 0 | [0.0, 0.1) | Very low confidence |
| 1 | [0.1, 0.2) | |
| ... | | |
| 7 | [0.7, 0.8) | Default alert threshold |
| 8 | [0.8, 0.9) | High confidence |
| 9 | [0.9, 1.0] | Very high confidence |

For each bin, calculate:
- `n_total`: Number of predictions in this bin with evaluated outcomes
- `n_correct`: Number where `correct_t7 = True` (using T+7 as the primary timeframe)
- `empirical_accuracy`: `n_correct / n_total`
- `confidence_interval`: Wilson score interval for the proportion

### Why T+7 as Primary Timeframe?

T+7 (7 trading days, ~1.5 calendar weeks) is the sweet spot:
- T+1 is too noisy (daily volatility swamps signal).
- T+30 is too slow (too few matured outcomes, long feedback loop).
- T+7 has the most matured data points and represents a meaningful trading horizon.

Calibration curves for other timeframes (T+1, T+3, T+30) can be computed too, but T+7 is the default.

### Fitting Method: Bin-Based Lookup Table

**Why lookup table over isotonic regression (Challenge Round Resolution #1):**

- No new dependency (sklearn ~50MB+ with scipy). Zero new packages.
- With 10 bins and 100+ samples per bin, accuracy estimates are already stable.
- JSON-native — debuggable, inspectable, no pickle versioning issues.
- Isotonic regression on 10 bins converges to ~10 breakpoints — same resolution as lookup table.
- If data volume grows to 10,000+ predictions, isotonic regression can be added in one PR.

```python
def build_lookup_table(
    raw_confidences: list[float],
    correct_flags: list[bool],
    n_bins: int = 10,
    min_per_bin: int = 5,
) -> dict[str, float | None]:
    """Build bin-based calibration lookup table.

    Returns:
        Dict mapping bin label to empirical accuracy.
        Example: {"0.7-0.8": 0.62, "0.8-0.9": 0.71, ...}
        Bins with fewer than min_per_bin samples return None.
    """
    bins = {}
    for conf, correct in zip(raw_confidences, correct_flags):
        bin_idx = min(int(conf * n_bins), n_bins - 1)
        bin_label = f"{bin_idx / n_bins:.1f}-{(bin_idx + 1) / n_bins:.1f}"
        if bin_label not in bins:
            bins[bin_label] = {"total": 0, "correct": 0}
        bins[bin_label]["total"] += 1
        if correct:
            bins[bin_label]["correct"] += 1

    return {
        label: round(data["correct"] / data["total"], 4)
        if data["total"] >= min_per_bin else None
        for label, data in sorted(bins.items())
    }
```

---

## Data Requirements

### Minimum Sample Sizes

| Requirement | Threshold | Rationale |
|-------------|-----------|-----------|
| Total predictions with outcomes | >= 100 | Minimum for any calibration |
| Per-bin minimum | >= 5 | Below this, bin accuracy is unreliable |
| Recommended total | >= 500 | For stable isotonic regression |
| Ideal total | >= 1000 | For per-asset calibration |

Current system state (~1050 completed predictions, ~800+ with T+7 outcomes): sufficient for global calibration.

### Time Windows

Calibration should be computed on a rolling window, not all-time data:
- **Default window**: Last 6 months of predictions.
- **Rationale**: LLM behavior changes with model updates; Trump's posting patterns evolve; market regimes shift.
- **Minimum window**: 3 months (to ensure enough data points).

```python
CALIBRATION_WINDOW_DAYS: int = 180  # 6 months rolling window
CALIBRATION_MIN_SAMPLES: int = 100  # Minimum predictions in window
CALIBRATION_MIN_PER_BIN: int = 5    # Minimum per bin
```

---

## Implementation

### New Module: `shit/market_data/calibration.py`

> **Challenge Round**: Simplified — no sklearn, no pickle, no scope, no BYTEA. Lookup table only. Staleness guard added.

See implementation for final code. Key design:
- `CalibrationCurve` dataclass: fitted_at, timeframe, window dates, n_predictions, n_bins, bin_stats (list[dict]), lookup_table (dict)
- `CalibrationService`: fit() queries data + builds lookup, calibrate() does bin lookup, _load_latest_curve() has max_age_days=30 staleness guard
- CLI entry: `python -m shit.market_data.calibration --refit [--timeframe t7]`

---

## Schema Changes

### New Column on `predictions`

```python
# In shitvault/shitpost_models.py - Prediction class
calibrated_confidence = Column(Float, nullable=True)  # Calibrated confidence 0.0-1.0
```

### New Table: `calibration_curves`

> **Challenge Round**: Simplified — no `scope` column, no `model_bytes` BYTEA column.

```sql
CREATE TABLE calibration_curves (
    id SERIAL PRIMARY KEY,
    fitted_at TIMESTAMP NOT NULL DEFAULT NOW(),
    timeframe VARCHAR(10) NOT NULL,
    window_start TIMESTAMP NOT NULL,
    window_end TIMESTAMP NOT NULL,
    n_predictions INTEGER NOT NULL,
    n_bins INTEGER NOT NULL DEFAULT 10,
    bin_stats JSONB NOT NULL,
    lookup_table JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_calibration_curves_timeframe
    ON calibration_curves (timeframe, fitted_at DESC);
```

### Migration SQL

```sql
ALTER TABLE predictions ADD COLUMN calibrated_confidence FLOAT;

CREATE TABLE calibration_curves (
    id SERIAL PRIMARY KEY,
    fitted_at TIMESTAMP NOT NULL DEFAULT NOW(),
    timeframe VARCHAR(10) NOT NULL,
    window_start TIMESTAMP NOT NULL,
    window_end TIMESTAMP NOT NULL,
    n_predictions INTEGER NOT NULL,
    n_bins INTEGER NOT NULL DEFAULT 10,
    bin_stats JSONB NOT NULL,
    lookup_table JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_calibration_curves_timeframe
    ON calibration_curves (timeframe, fitted_at DESC);
```

---

## Refresh Schedule

### Weekly Refit Cron

> **Challenge Round**: Entry point moved from root-level `calibration_cron.py` to `python -m shit.market_data.calibration --refit`. Per-provider loop removed (global only).

**Railway Service**: `calibration-refit`, cron schedule `0 2 * * 0` (Sunday 2 AM UTC).
**Command**: `python -m shit.market_data.calibration --refit`

### On-Demand Refit

```bash
python -m shit.market_data.calibration --refit                    # All timeframes
python -m shit.market_data.calibration --refit --timeframe t7     # Single timeframe
```

---

## Scope: Global Only (v1)

> **Challenge Round**: Per-provider and per-asset scoping deferred until Feature 05 (Multi-LLM Ensemble) lands. Global calibration is sufficient with one provider.

### Applying Calibration at Prediction Time

In `shitvault/prediction_operations.py`, apply calibration via deferred import + `asyncio.to_thread`:

```python
# After creating prediction, apply calibration
raw_confidence = analysis_data.get("confidence")
if raw_confidence is not None:
    from shit.market_data.calibration import CalibrationService
    cal_svc = CalibrationService(timeframe="t7")
    calibrated = cal_svc.calibrate(raw_confidence)
    # Store on prediction object
```

---

## Visualization

### Calibration Chart for Dashboard

A reliability diagram (calibration plot) showing predicted confidence vs. actual accuracy:

```
1.0 |                                        /
    |                                      /
0.8 |                              *     /
    |                          *       /
0.6 |                    *           /     * = actual accuracy
    |              *               /       / = perfect calibration
0.4 |        *                   /
    |    *                     /
0.2 |                        /
    |  *                   /
0.0 +--+--+--+--+--+--+--+--+--+--+
    0.0  0.1  0.2  ...  0.8  0.9  1.0
                Raw LLM Confidence
```

### API Endpoint

```python
# api/routers/calibration.py
@router.get("/api/calibration/curve")
async def get_calibration_curve(timeframe: str = "t7", scope: str = "global"):
    """Get the latest calibration curve for display."""
    svc = CalibrationService(timeframe=timeframe)
    curve = svc._load_latest_curve(scope=scope)
    if not curve:
        raise HTTPException(404, "No calibration curve available")
    return {
        "fitted_at": curve.fitted_at.isoformat(),
        "timeframe": curve.timeframe,
        "n_predictions": curve.n_predictions,
        "bin_stats": curve.bin_stats,
        "lookup_table": curve.lookup_table,
        "scope": curve.scope,
    }
```

### Frontend Component

A new `CalibrationChart` component in the React dashboard:

```typescript
// frontend/src/components/CalibrationChart.tsx
// Renders a reliability diagram using Lightweight Charts or a simple SVG
// X-axis: raw confidence bins, Y-axis: actual accuracy
// Perfect calibration line shown as diagonal reference
// Each bin shown as a point with error bars (based on sample size)
```

---

## Alert Integration

### Show Calibrated Confidence in Messages

Update `notifications/telegram_sender.py`:

```python
def format_telegram_alert(alert: dict) -> str:
    confidence = alert.get("confidence", 0)
    calibrated = alert.get("calibrated_confidence")

    if calibrated is not None:
        confidence_str = escape_markdown(
            f"{confidence:.0%} raw / {calibrated:.0%} calibrated"
        )
    else:
        confidence_str = escape_markdown(f"{confidence:.0%}")

    # ... rest of formatting
```

**Example alert:**

```
SHITPOST ALPHA ALERT

Sentiment: BEARISH (85% raw / 71% calibrated)
Assets: TSLA, F
```

### Subscriber Preference Update

The `min_confidence` preference should filter on `calibrated_confidence` when available, falling back to raw `confidence`:

```python
# In alert_engine.py - filter_predictions_by_preferences
effective_confidence = pred.get("calibrated_confidence") or pred.get("confidence", 0)
if effective_confidence < min_confidence:
    continue
```

---

## Cold Start

### What To Do Before Enough Data Exists

When the system first deploys or after a major model change, there may not be enough historical data for calibration. Strategies:

1. **No calibration (default)**: `calibrated_confidence` is `NULL`. Frontend/alerts show only raw confidence. This is the current behavior.
2. **Prior-based initialization**: Start with a mildly pessimistic prior that assumes LLMs are overconfident. Map raw confidence * 0.85 as a rough calibration. This is NOT implemented by default -- only if we want to ship a placeholder before real data accumulates.
3. **Minimum data threshold**: The `CalibrationService.fit()` method already returns `None` if `n_predictions < min_samples`. When `None`, `calibrate()` returns `None`, and the system gracefully falls back to raw confidence.

### Transition Plan

1. Deploy with `calibrated_confidence` column (nullable, initially all NULL).
2. Run first calibration fit after 3 months of ensemble data (or immediately if 100+ existing outcomes suffice).
3. Once calibration is available, populate `calibrated_confidence` for all new predictions.
4. Optionally backfill `calibrated_confidence` for historical predictions (read-only, using the latest curve).

---

## File Changes Summary

| File | Change |
|------|--------|
| `shit/market_data/calibration.py` | **NEW** - `CalibrationService`, `CalibrationCurve` (with CLI `__main__` block) |
| `shitvault/shitpost_models.py` | Add `calibrated_confidence` column to Prediction |
| `shitvault/prediction_operations.py` | Apply calibration when storing predictions |
| `notifications/telegram_sender.py` | Show calibrated confidence in alerts |
| `notifications/alert_engine.py` | Filter on calibrated confidence |
| `notifications/event_consumer.py` | Pass `calibrated_confidence` in alert dict |
| `api/routers/calibration.py` | **NEW** - Calibration curve API endpoint |
| `api/schemas/feed.py` | Add `calibrated_confidence` to PredictionResponse |
| `api/schemas/calibration.py` | **NEW** - Calibration API response models |
| `frontend/src/components/CalibrationChart.tsx` | **NEW** - Reliability diagram |
| `shit_tests/shit/market_data/test_calibration.py` | **NEW** - Unit tests |

---

## Testing Strategy

### Unit Tests (`shit_tests/shit/market_data/test_calibration.py`)

1. **Lookup table construction**:
   - `test_lookup_table_uniform`: Equal predictions in each bin, verify accuracy computation
   - `test_lookup_table_sparse_bins`: Some bins have < min_per_bin, return None for those
   - `test_lookup_table_empty`: No data returns empty dict
   - `test_lookup_table_single_bin`: All predictions in one confidence range

2. **Isotonic regression fitting**:
   - `test_isotonic_fit_monotonic`: Output is monotonically non-decreasing
   - `test_isotonic_fit_perfect_calibration`: When actual accuracy matches confidence
   - `test_isotonic_fit_overconfident_model`: When 0.9 confidence = 0.6 accuracy, calibrated output < 0.9
   - `test_isotonic_fit_clipping`: Output clamped to [0.0, 1.0]

3. **Calibration application**:
   - `test_calibrate_returns_float`: Valid input returns calibrated score
   - `test_calibrate_no_curve_returns_none`: When no curve fitted, returns None
   - `test_calibrate_boundary_values`: Test confidence=0.0 and confidence=1.0

4. **Data query**:
   - `test_query_global_scope`: Correct SQL for global
   - `test_query_provider_scope`: Filters by llm_provider
   - `test_query_window_filter`: Only includes predictions within time window

5. **Persistence**:
   - `test_store_and_load_curve`: Round-trip store/load
   - `test_load_latest_curve`: Returns most recent by fitted_at

### Integration Tests

1. `test_prediction_storage_with_calibration`: Mock calibration service, verify `calibrated_confidence` stored
2. `test_alert_uses_calibrated_confidence`: Verify filtering uses calibrated value
3. `test_cold_start_no_calibration`: When no curve exists, everything works with raw confidence

### Test Data Strategy

Create synthetic prediction/outcome datasets:

```python
@pytest.fixture
def synthetic_calibration_data():
    """Generate 500 predictions with known calibration relationship."""
    import random
    data = []
    for _ in range(500):
        raw_conf = random.uniform(0.3, 0.95)
        # Simulate overconfident LLM: actual accuracy = raw_conf * 0.8
        is_correct = random.random() < (raw_conf * 0.8)
        data.append({"confidence": raw_conf, "correct": is_correct})
    return data
```

---

## Dependencies

> **Challenge Round**: No new Python packages. sklearn removed — lookup table uses only stdlib + existing numpy/sqlalchemy.

---

## Open Questions

1. **Should `calibrated_confidence` replace `confidence` in the API response, or be shown alongside?** Recommendation: show both. Raw confidence tells you what the LLM thinks; calibrated tells you what historically happened. Different users may prefer different signals.

2. **Should the subscriber `min_confidence` threshold apply to raw or calibrated confidence?** Recommendation: calibrated when available, raw as fallback. This means changing the subscriber default from 0.7 to something like 0.5 (since calibrated confidence will typically be lower than raw).

3. **How to handle model changes?** When OpenAI deploys a new GPT-4 version, the calibration curve for "provider:openai" may become stale. Consider tracking `llm_model` in calibration scope (e.g., `provider:openai:gpt-4o`) vs. just `provider:openai`. Start simple with provider-level granularity.

4. **Should we calibrate consensus confidence differently from single-model confidence?** Yes, in theory ensemble consensus confidence has a different distribution. Add scope `"mode:ensemble"` and `"mode:single"` to separate them.

5. **How to visualize uncertainty?** The calibration chart shows point estimates. Adding confidence intervals (Wilson score) per bin would show where we have enough data vs. sparse bins. Implement in the frontend chart as error bars.

---

## Implementation Order

1. **Phase 1**: Create `shit/market_data/calibration.py` with `CalibrationService`. Create `calibration_curves` table. Add `calibrated_confidence` column. Write unit tests.
2. **Phase 2**: Integrate into prediction storage (`prediction_operations.py`). Set up weekly cron. Run first calibration fit on existing data.
3. **Phase 3**: Update alerts to show calibrated confidence. Update alert filtering.
4. **Phase 4**: Add API endpoint and frontend calibration chart.
