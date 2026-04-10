# 06: Confidence Calibration

**Feature**: Build a calibration curve from 1000+ historical predictions to map raw LLM confidence to actual accuracy rates.

**Status**: Design  
**Priority**: High  
**Estimated Effort**: 2-3 sessions  

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

### Fitting Method: Isotonic Regression

**Why isotonic regression over Platt scaling:**

- Platt scaling (logistic sigmoid fit) assumes a specific functional form. Our confidence-to-accuracy relationship may not be sigmoidal.
- Isotonic regression is non-parametric -- it produces a monotonically non-decreasing mapping with no functional form assumption.
- With 1000+ data points across 10 bins, we have enough data for non-parametric fitting.
- `sklearn.isotonic.IsotonicRegression` is battle-tested and available.

```python
from sklearn.isotonic import IsotonicRegression

def fit_calibration_curve(
    raw_confidences: list[float],
    correct_flags: list[bool],
) -> IsotonicRegression:
    """Fit isotonic regression calibration curve.

    Args:
        raw_confidences: LLM confidence scores for each prediction.
        correct_flags: Whether each prediction was correct (True/False).

    Returns:
        Fitted IsotonicRegression model.
    """
    import numpy as np

    X = np.array(raw_confidences)
    y = np.array(correct_flags, dtype=float)

    ir = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
    ir.fit(X, y)
    return ir
```

### Alternative: Simple Lookup Table

For environments where sklearn is undesirable, a simple bin-based lookup table works:

```python
def build_lookup_table(
    raw_confidences: list[float],
    correct_flags: list[bool],
    n_bins: int = 10,
) -> dict[str, float]:
    """Build bin-based calibration lookup table.

    Returns:
        Dict mapping bin label to empirical accuracy.
        Example: {"0.7-0.8": 0.62, "0.8-0.9": 0.71, ...}
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
        label: data["correct"] / data["total"] if data["total"] > 0 else None
        for label, data in sorted(bins.items())
    }
```

**Recommendation**: Implement both. Use isotonic regression as the primary calibration method, with the lookup table as a human-readable diagnostic.

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

```python
"""
Confidence Calibration Service

Fits calibration curves from historical prediction outcomes and applies
calibrated confidence to new predictions.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
import json
import pickle

from sqlalchemy import text
from shit.db.sync_session import get_session
from shit.logging import get_service_logger

logger = get_service_logger("calibration")


@dataclass
class CalibrationCurve:
    """Fitted calibration curve with metadata."""
    fitted_at: datetime
    timeframe: str                    # "t7" (primary), "t1", "t3", "t30"
    window_start: datetime
    window_end: datetime
    n_predictions: int
    n_bins: int
    bin_stats: list[dict]             # Per-bin: {bin_label, n_total, n_correct, accuracy}
    model_bytes: Optional[bytes]      # Pickled IsotonicRegression
    lookup_table: dict[str, float]    # Bin label -> empirical accuracy
    scope: str                        # "global", "provider:openai", "asset:TSLA"


class CalibrationService:
    """Fits and applies confidence calibration curves."""

    def __init__(
        self,
        timeframe: str = "t7",
        window_days: int = 180,
        min_samples: int = 100,
        min_per_bin: int = 5,
        n_bins: int = 10,
    ):
        self.timeframe = timeframe
        self.window_days = window_days
        self.min_samples = min_samples
        self.min_per_bin = min_per_bin
        self.n_bins = n_bins

    def fit(self, scope: str = "global") -> Optional[CalibrationCurve]:
        """Fit a calibration curve from historical data.

        Args:
            scope: "global", "provider:{id}", or "asset:{symbol}"

        Returns:
            CalibrationCurve if enough data, None otherwise.
        """
        # Query historical predictions with outcomes
        data = self._query_calibration_data(scope)
        if len(data) < self.min_samples:
            logger.warning(
                f"Insufficient data for calibration: {len(data)} < {self.min_samples}"
            )
            return None

        raw_confidences = [d["confidence"] for d in data]
        correct_flags = [d["correct"] for d in data]

        # Build lookup table
        lookup = self._build_lookup_table(raw_confidences, correct_flags)

        # Fit isotonic regression
        model_bytes = self._fit_isotonic(raw_confidences, correct_flags)

        # Build per-bin statistics
        bin_stats = self._compute_bin_stats(raw_confidences, correct_flags)

        window_end = datetime.utcnow()
        window_start = window_end - timedelta(days=self.window_days)

        curve = CalibrationCurve(
            fitted_at=datetime.utcnow(),
            timeframe=self.timeframe,
            window_start=window_start,
            window_end=window_end,
            n_predictions=len(data),
            n_bins=self.n_bins,
            bin_stats=bin_stats,
            model_bytes=model_bytes,
            lookup_table=lookup,
            scope=scope,
        )

        # Persist to database
        self._store_curve(curve)
        logger.info(
            f"Calibration curve fitted: {scope}, {len(data)} predictions, "
            f"timeframe={self.timeframe}"
        )
        return curve

    def calibrate(self, raw_confidence: float) -> Optional[float]:
        """Apply calibration to a raw confidence score.

        Args:
            raw_confidence: LLM-reported confidence (0.0-1.0).

        Returns:
            Calibrated confidence, or None if no calibration curve available.
        """
        curve = self._load_latest_curve()
        if not curve or not curve.model_bytes:
            return None

        try:
            import numpy as np
            model = pickle.loads(curve.model_bytes)
            calibrated = float(model.predict([raw_confidence])[0])
            return max(0.0, min(1.0, calibrated))
        except Exception as e:
            logger.error(f"Calibration prediction failed: {e}")
            return None

    def _query_calibration_data(self, scope: str) -> list[dict]:
        """Query predictions with outcomes for calibration fitting."""
        correct_col = f"correct_{self.timeframe}"
        window_start = datetime.utcnow() - timedelta(days=self.window_days)

        base_query = f"""
            SELECT
                p.confidence,
                po.{correct_col} as correct,
                p.llm_provider,
                po.symbol
            FROM predictions p
            JOIN prediction_outcomes po ON po.prediction_id = p.id
            WHERE p.analysis_status = 'completed'
                AND p.confidence IS NOT NULL
                AND po.{correct_col} IS NOT NULL
                AND p.created_at >= :window_start
        """

        params = {"window_start": window_start}

        # Add scope filter
        if scope.startswith("provider:"):
            provider = scope.split(":")[1]
            base_query += " AND p.llm_provider = :provider"
            params["provider"] = provider
        elif scope.startswith("asset:"):
            symbol = scope.split(":")[1]
            base_query += " AND po.symbol = :symbol"
            params["symbol"] = symbol

        with get_session() as session:
            result = session.execute(text(base_query), params)
            rows = result.fetchall()
            columns = result.keys()
            return [dict(zip(columns, row)) for row in rows]

    def _fit_isotonic(self, confidences: list[float], correct: list[bool]) -> Optional[bytes]:
        """Fit isotonic regression and return pickled model bytes."""
        try:
            import numpy as np
            from sklearn.isotonic import IsotonicRegression

            X = np.array(confidences)
            y = np.array(correct, dtype=float)
            ir = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
            ir.fit(X, y)
            return pickle.dumps(ir)
        except ImportError:
            logger.warning("sklearn not available, skipping isotonic regression")
            return None

    def _build_lookup_table(self, confidences: list[float], correct: list[bool]) -> dict:
        """Build bin-based lookup table."""
        bins = {}
        for conf, c in zip(confidences, correct):
            bin_idx = min(int(conf * self.n_bins), self.n_bins - 1)
            label = f"{bin_idx / self.n_bins:.1f}-{(bin_idx + 1) / self.n_bins:.1f}"
            if label not in bins:
                bins[label] = {"total": 0, "correct": 0}
            bins[label]["total"] += 1
            if c:
                bins[label]["correct"] += 1

        return {
            label: round(data["correct"] / data["total"], 4) if data["total"] >= self.min_per_bin else None
            for label, data in sorted(bins.items())
        }

    def _compute_bin_stats(self, confidences: list[float], correct: list[bool]) -> list[dict]:
        """Compute detailed per-bin statistics."""
        bins = {}
        for conf, c in zip(confidences, correct):
            bin_idx = min(int(conf * self.n_bins), self.n_bins - 1)
            if bin_idx not in bins:
                bins[bin_idx] = {"total": 0, "correct": 0}
            bins[bin_idx]["total"] += 1
            if c:
                bins[bin_idx]["correct"] += 1

        stats = []
        for i in range(self.n_bins):
            data = bins.get(i, {"total": 0, "correct": 0})
            accuracy = data["correct"] / data["total"] if data["total"] > 0 else None
            stats.append({
                "bin_label": f"{i / self.n_bins:.1f}-{(i + 1) / self.n_bins:.1f}",
                "bin_center": (i + 0.5) / self.n_bins,
                "n_total": data["total"],
                "n_correct": data["correct"],
                "accuracy": accuracy,
            })
        return stats

    def _store_curve(self, curve: CalibrationCurve) -> None:
        """Persist calibration curve to database."""
        with get_session() as session:
            session.execute(
                text("""
                    INSERT INTO calibration_curves (
                        fitted_at, timeframe, window_start, window_end,
                        n_predictions, n_bins, bin_stats, model_bytes,
                        lookup_table, scope
                    ) VALUES (
                        :fitted_at, :timeframe, :window_start, :window_end,
                        :n_predictions, :n_bins, :bin_stats, :model_bytes,
                        :lookup_table, :scope
                    )
                """),
                {
                    "fitted_at": curve.fitted_at,
                    "timeframe": curve.timeframe,
                    "window_start": curve.window_start,
                    "window_end": curve.window_end,
                    "n_predictions": curve.n_predictions,
                    "n_bins": curve.n_bins,
                    "bin_stats": json.dumps(curve.bin_stats),
                    "model_bytes": curve.model_bytes,
                    "lookup_table": json.dumps(curve.lookup_table),
                    "scope": curve.scope,
                },
            )

    def _load_latest_curve(self, scope: str = "global") -> Optional[CalibrationCurve]:
        """Load the most recently fitted calibration curve."""
        with get_session() as session:
            result = session.execute(
                text("""
                    SELECT * FROM calibration_curves
                    WHERE scope = :scope AND timeframe = :timeframe
                    ORDER BY fitted_at DESC
                    LIMIT 1
                """),
                {"scope": scope, "timeframe": self.timeframe},
            )
            row = result.fetchone()
            if not row:
                return None
            columns = result.keys()
            data = dict(zip(columns, row))
            return CalibrationCurve(
                fitted_at=data["fitted_at"],
                timeframe=data["timeframe"],
                window_start=data["window_start"],
                window_end=data["window_end"],
                n_predictions=data["n_predictions"],
                n_bins=data["n_bins"],
                bin_stats=json.loads(data["bin_stats"]) if isinstance(data["bin_stats"], str) else data["bin_stats"],
                model_bytes=data["model_bytes"],
                lookup_table=json.loads(data["lookup_table"]) if isinstance(data["lookup_table"], str) else data["lookup_table"],
                scope=data["scope"],
            )
```

---

## Schema Changes

### New Column on `predictions`

```python
# In shitvault/shitpost_models.py - Prediction class
calibrated_confidence = Column(Float, nullable=True)  # Calibrated confidence 0.0-1.0
```

### New Table: `calibration_curves`

```sql
CREATE TABLE calibration_curves (
    id SERIAL PRIMARY KEY,
    fitted_at TIMESTAMP NOT NULL DEFAULT NOW(),
    timeframe VARCHAR(10) NOT NULL,          -- 't1', 't3', 't7', 't30'
    window_start TIMESTAMP NOT NULL,
    window_end TIMESTAMP NOT NULL,
    n_predictions INTEGER NOT NULL,
    n_bins INTEGER NOT NULL DEFAULT 10,
    bin_stats JSONB NOT NULL,                -- Per-bin statistics
    model_bytes BYTEA,                       -- Pickled sklearn model
    lookup_table JSONB NOT NULL,             -- Bin -> accuracy mapping
    scope VARCHAR(100) NOT NULL DEFAULT 'global',  -- 'global', 'provider:openai', 'asset:TSLA'
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_calibration_curves_scope_timeframe
    ON calibration_curves (scope, timeframe, fitted_at DESC);

COMMENT ON TABLE calibration_curves IS 'Historical calibration curves mapping raw LLM confidence to empirical accuracy';
```

### Migration SQL

```sql
-- Add calibrated_confidence to predictions
ALTER TABLE predictions ADD COLUMN calibrated_confidence FLOAT;
COMMENT ON COLUMN predictions.calibrated_confidence IS 'Empirically calibrated confidence from calibration curve (null if uncalibrated)';

-- Create calibration_curves table
CREATE TABLE calibration_curves (
    id SERIAL PRIMARY KEY,
    fitted_at TIMESTAMP NOT NULL DEFAULT NOW(),
    timeframe VARCHAR(10) NOT NULL,
    window_start TIMESTAMP NOT NULL,
    window_end TIMESTAMP NOT NULL,
    n_predictions INTEGER NOT NULL,
    n_bins INTEGER NOT NULL DEFAULT 10,
    bin_stats JSONB NOT NULL,
    model_bytes BYTEA,
    lookup_table JSONB NOT NULL,
    scope VARCHAR(100) NOT NULL DEFAULT 'global',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_calibration_curves_scope_timeframe
    ON calibration_curves (scope, timeframe, fitted_at DESC);
```

---

## Refresh Schedule

### Weekly Refit Cron

A Railway cron job runs every Sunday at 02:00 UTC:

```python
# calibration_cron.py (new entry point)
"""Weekly calibration curve refit."""

from shit.market_data.calibration import CalibrationService
from shit.logging import setup_cli_logging

def main():
    setup_cli_logging(verbose=True)

    for timeframe in ["t1", "t3", "t7", "t30"]:
        svc = CalibrationService(timeframe=timeframe)

        # Global calibration
        curve = svc.fit(scope="global")
        if curve:
            print(f"Global {timeframe}: {curve.n_predictions} predictions, "
                  f"lookup={curve.lookup_table}")

        # Per-provider calibration (if ensemble is active)
        for provider in ["openai", "anthropic", "grok"]:
            curve = svc.fit(scope=f"provider:{provider}")
            if curve:
                print(f"Provider {provider} {timeframe}: {curve.n_predictions} predictions")

if __name__ == "__main__":
    main()
```

**Railway Service**: `calibration-refit`, cron schedule `0 2 * * 0` (Sunday 2 AM UTC).

### On-Demand Refit

The calibration service can also be triggered manually:

```bash
python -m shit.market_data.calibration --refit --timeframe t7 --scope global
```

---

## Per-Asset vs. Global Calibration

### Tradeoffs

| Approach | Pros | Cons |
|----------|------|------|
| **Global** | Most data per bin, stable estimates | Ignores asset-specific LLM bias |
| **Per-provider** | Captures model-specific calibration | 3x less data per curve |
| **Per-asset** | Most accurate per ticker | Very sparse (most tickers have < 20 predictions) |
| **Per-sector** | Good balance of specificity and data | Requires sector tagging |

### Recommendation

1. **Primary**: Global calibration (enough data, most stable).
2. **Secondary**: Per-provider calibration (useful when ensemble is active; each provider may have different confidence distributions).
3. **Future**: Per-sector calibration when enough data accumulates (group assets by `ticker_registry.sector`).
4. **Not recommended now**: Per-asset calibration (insufficient data for most tickers).

### Applying Calibration at Prediction Time

In `shitvault/prediction_operations.py`, when storing a prediction:

```python
async def store_analysis(self, shitpost_id: str, analysis: dict, shitpost: dict) -> Optional[int]:
    # ... existing logic ...

    # Apply calibration
    raw_confidence = analysis.get("confidence")
    calibrated = None
    if raw_confidence is not None:
        from shit.market_data.calibration import CalibrationService
        cal_svc = CalibrationService(timeframe="t7")
        calibrated = cal_svc.calibrate(raw_confidence)

    prediction = Prediction(
        confidence=raw_confidence,
        calibrated_confidence=calibrated,
        # ... other fields ...
    )
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
| `shit/market_data/calibration.py` | **NEW** - `CalibrationService`, `CalibrationCurve` |
| `shitvault/shitpost_models.py` | Add `calibrated_confidence` column to Prediction |
| `shitvault/prediction_operations.py` | Apply calibration when storing predictions |
| `notifications/telegram_sender.py` | Show calibrated confidence in alerts |
| `notifications/alert_engine.py` | Filter on calibrated confidence |
| `api/routers/calibration.py` | **NEW** - Calibration curve API endpoint |
| `api/schemas/feed.py` | Add `calibrated_confidence` to PredictionResponse |
| `frontend/src/components/CalibrationChart.tsx` | **NEW** - Reliability diagram |
| `calibration_cron.py` | **NEW** - Weekly refit entry point |
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

### New Python Package

```
scikit-learn>=1.4.0  # For IsotonicRegression
```

Add to `requirements.txt`. This is a well-maintained, BSD-licensed package already commonly used in ML applications. The only function we need is `IsotonicRegression`.

If adding sklearn is undesirable (large dependency), the lookup table approach works standalone. The isotonic regression is an enhancement, not a requirement.

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
