# Phase 02: Fix Sentiment Extraction Bug & NaN Display Guards

> **Status**: 🔧 IN PROGRESS
> **Started**: 2026-03-04

## Header

| Field | Value |
|---|---|
| **PR Title** | fix: per-asset sentiment extraction and NaN display guards |
| **Risk Level** | Low |
| **Estimated Effort** | Low (2-3 hours) |
| **Files Modified** | 8 |
| **Files Created** | 2 |
| **Files Deleted** | 0 |

## Context

Two independent bugs degrade data quality and user experience:

1. **Sentiment Extraction Bug**: `OutcomeCalculator._extract_sentiment()` in `shit/market_data/outcome_calculator.py` extracts the *first* sentiment value from the `market_impact` dict and applies it to ALL assets in the prediction. For a prediction with `{"AAPL": "bullish", "TSLA": "bearish"}`, both AAPL and TSLA get labeled "bullish" in `prediction_outcomes.prediction_sentiment`. This corrupts accuracy calculations -- a bearish TSLA prediction is recorded as bullish, so a price drop is marked "incorrect" when it should be "correct."

2. **NaN Display Bug**: When `prediction_outcomes` rows have NULL values for `return_t7`, `pnl_t7`, etc., Pandas loads them as `float('nan')`. The `_safe_get()` helper in `shitty_ui/components/cards/feed.py` correctly converts NaN to a default value, but most other card components and callbacks use bare `row.get()` without NaN protection. This causes the UI to display "+nan%", "$nan", or crash on format strings.

## Dependencies

- **Depends on**: None (standalone bug fixes)
- **Unlocks**: Phase 01 (Outcome Maturation Pipeline) -- once sentiment is correctly per-asset, outcomes calculated by the maturation pipeline will be accurate

## Detailed Implementation Plan

### Part A: Fix Sentiment Extraction Bug

#### Step 1: Change `_extract_sentiment()` to accept an asset parameter

**File**: `shit/market_data/outcome_calculator.py`

**Current code (lines 462-473)**:
```python
def _extract_sentiment(self, market_impact: Dict[str, Any]) -> Optional[str]:
    """Extract primary sentiment from market_impact dict."""
    if not market_impact:
        return None

    # market_impact is typically {asset: sentiment}
    sentiments = list(market_impact.values())
    if not sentiments:
        return None

    # Return most common sentiment, or first one
    return sentiments[0].lower() if sentiments else None
```

**New code**:
```python
def _extract_sentiment(
    self, market_impact: Dict[str, Any], asset: Optional[str] = None
) -> Optional[str]:
    """Extract sentiment from market_impact dict, optionally for a specific asset.

    Args:
        market_impact: Dict mapping asset tickers to sentiment strings,
            e.g. {"AAPL": "bullish", "TSLA": "bearish"}.
        asset: If provided, look up this specific asset's sentiment.
            Tries exact match, then case-insensitive match.
            Falls back to the first sentiment if the asset is not found.

    Returns:
        Lowercase sentiment string, or None if market_impact is empty.
    """
    if not market_impact:
        return None

    sentiments = list(market_impact.values())
    if not sentiments:
        return None

    if asset is not None:
        # Try exact match first
        sentiment = market_impact.get(asset)
        if sentiment is None:
            # Try case-insensitive match (assets may be stored as "aapl" or "AAPL")
            sentiment = market_impact.get(asset.upper())
        if sentiment is None:
            sentiment = market_impact.get(asset.lower())
        if sentiment is None:
            # Try iterating for case-insensitive key match
            asset_upper = asset.upper()
            for key, val in market_impact.items():
                if key.upper() == asset_upper:
                    sentiment = val
                    break
        if sentiment is not None and isinstance(sentiment, str):
            return sentiment.lower()
        # Asset not found in market_impact -- fall back to first sentiment

    return sentiments[0].lower() if isinstance(sentiments[0], str) else None
```

#### Step 2: Pass asset into `_extract_sentiment()` inside the asset loop

**File**: `shit/market_data/outcome_calculator.py`

**Current code (lines 102-121)**:
```python
# Get sentiment from market_impact
sentiment = (
    self._extract_sentiment(prediction.market_impact)
    if prediction.market_impact
    else None
)

outcomes = []

# Calculate outcome for each asset
for asset in prediction.assets:
    try:
        outcome = self._calculate_single_outcome(
            prediction_id=prediction_id,
            symbol=asset,
            prediction_date=prediction_date,
            sentiment=sentiment,
            confidence=prediction.confidence,
            force_refresh=force_refresh,
        )
```

**New code (replace lines 102-121)**:
```python
outcomes = []

# Calculate outcome for each asset
for asset in prediction.assets:
    try:
        # Extract per-asset sentiment from market_impact
        sentiment = (
            self._extract_sentiment(prediction.market_impact, asset=asset)
            if prediction.market_impact
            else None
        )

        outcome = self._calculate_single_outcome(
            prediction_id=prediction_id,
            symbol=asset,
            prediction_date=prediction_date,
            sentiment=sentiment,
            confidence=prediction.confidence,
            force_refresh=force_refresh,
        )
```

**Why**: The sentiment extraction now happens inside the loop, passing the current `asset` to `_extract_sentiment()`. Each asset gets its own per-asset sentiment from the `market_impact` dict. If the asset is not found in the dict (unlikely but possible), it falls back to the first sentiment, preserving backward compatibility.

#### Step 3: Flag existing multi-asset outcomes for recalculation

After fixing the extraction, existing `prediction_outcomes` rows with incorrect sentiment need to be recalculated. Add a one-time CLI command.

**File**: `shit/market_data/__main__.py`

Add a new CLI command `fix-sentiments` that:

1. Queries all predictions where `assets` has more than one entry AND `market_impact` has more than one key
2. For each, calls `calculate_outcome_for_prediction(prediction_id, force_refresh=True)`
3. Logs how many outcomes were recalculated

**Add after the existing CLI commands** (find the `argparse` block or `click` group):

```python
elif args.command == "fix-sentiments":
    """Recalculate outcomes for multi-asset predictions with incorrect sentiment."""
    from shitvault.shitpost_models import Prediction
    from sqlalchemy import func

    with OutcomeCalculator() as calc:
        # Find predictions with multiple assets where market_impact has data
        preds = (
            calc.session.query(Prediction)
            .filter(
                Prediction.analysis_status == "completed",
                Prediction.assets.isnot(None),
                Prediction.market_impact.isnot(None),
                func.jsonb_array_length(Prediction.assets) > 1,
            )
            .all()
        )

        logger.info(f"Found {len(preds)} multi-asset predictions to re-evaluate")
        recalculated = 0
        errors = 0

        for pred in preds:
            try:
                outcomes = calc.calculate_outcome_for_prediction(
                    pred.id, force_refresh=True
                )
                recalculated += len(outcomes)
            except Exception as e:
                errors += 1
                logger.error(f"Error recalculating prediction {pred.id}: {e}")

        logger.info(
            f"Recalculated {recalculated} outcomes, {errors} errors"
        )
```

Read the existing `__main__.py` to determine the exact CLI framework used (argparse vs click) and adapt accordingly.

**File to read**: `shit/market_data/__main__.py`

**Important**: This command must be added to the argparse subcommand definitions. Check the existing file for the exact pattern.

### Part B: NaN Display Guards

#### Step 4: Create shared `safe_get` utility

**Create new file**: `shitty_ui/components/utils.py`

```python
"""Shared utility functions for UI components.

Provides NaN-safe data extraction and other helpers used across
multiple card types and callback modules.
"""

import math
from typing import Any, Optional


def safe_get(row, key: str, default: Any = None) -> Any:
    """NaN-safe field extraction from a Pandas Series or dict.

    Pandas Series.get() returns NaN (not the default) when the key
    exists but the value is NaN. This helper normalizes NaN to the
    provided default, preventing '+nan%' and '$nan' display bugs.

    Args:
        row: Dict-like object (Pandas Series or plain dict).
        key: Field name to extract.
        default: Value to return if the field is missing or NaN.

    Returns:
        The field value, or default if missing/None/NaN.
    """
    value = row.get(key, default)
    if value is None:
        return default
    try:
        if isinstance(value, float) and math.isnan(value):
            return default
    except (TypeError, ValueError):
        pass
    return value


def safe_format_pct(value: Optional[float], fmt: str = "+.2f") -> str:
    """Format a float as a percentage string, returning '--' for None/NaN.

    Args:
        value: Float value to format, or None.
        fmt: Format spec string (default '+.2f' for '+1.23').

    Returns:
        Formatted string like '+1.23%' or '--'.
    """
    if value is None:
        return "--"
    try:
        if isinstance(value, float) and math.isnan(value):
            return "--"
    except (TypeError, ValueError):
        return "--"
    return f"{value:{fmt}}%"


def safe_format_dollar(value: Optional[float], fmt: str = "+,.0f") -> str:
    """Format a float as a dollar string, returning '--' for None/NaN.

    Args:
        value: Float value to format, or None.
        fmt: Format spec string (default '+,.0f' for '+$1,234').

    Returns:
        Formatted string like '$+1,234' or '--'.
    """
    if value is None:
        return "--"
    try:
        if isinstance(value, float) and math.isnan(value):
            return "--"
    except (TypeError, ValueError):
        return "--"
    return f"${value:{fmt}}"
```

#### Step 5: Update `feed.py` to import from shared utility

**File**: `shitty_ui/components/cards/feed.py`

**Current code (lines 1-41)**:
The file defines `_safe_get()` locally at lines 26-41.

**Change**:
1. Remove the local `_safe_get()` definition (lines 26-41)
2. Add import at top of file: `from components.utils import safe_get`
3. Replace all `_safe_get(` calls with `safe_get(` (lines 139-149)

**Before (line 8)**:
```python
import math
```

**After**:
Remove the `import math` line (no longer needed in this file).

**Before (lines 26-41)**:
```python
def _safe_get(row, key, default=None):
    """
    NaN-safe field extraction from a Pandas Series or dict.
    ...
    """
    value = row.get(key, default)
    if value is None:
        return default
    try:
        if isinstance(value, float) and math.isnan(value):
            return default
    except (TypeError, ValueError):
        pass
    return value
```

**After**: Delete these lines entirely.

**Before (line 1-7, add import)**:
```python
from components.utils import safe_get
```

**Rename all usages (lines 139-149)**: Change `_safe_get(` to `safe_get(`:
```python
    timestamp = safe_get(row, "timestamp")
    post_text = safe_get(row, "text", "")
    confidence = safe_get(row, "confidence", 0) or 0
    assets = safe_get(row, "assets", [])
    market_impact = safe_get(row, "market_impact", {})
    symbol = safe_get(row, "symbol")
    prediction_sentiment = safe_get(row, "prediction_sentiment")
    return_t7 = safe_get(row, "return_t7")
    correct_t7 = safe_get(row, "correct_t7")
    pnl_t7 = safe_get(row, "pnl_t7")
    thesis = safe_get(row, "thesis", "")
```

#### Step 6: Update `cards/__init__.py` to re-export `safe_get` instead of `_safe_get`

**File**: `shitty_ui/components/cards/__init__.py`

**Current (line 93)**:
```python
    _safe_get,
```

**After**:
```python
    safe_get,
```

**Current (line 122)**:
```python
    "_safe_get",
```

**After**:
```python
    "safe_get",
```

No backward-compat alias needed — `_safe_get` was always private (`_` prefix). Clean break to `safe_get`.

#### Step 7: Apply NaN guards to `timeline.py`

**File**: `shitty_ui/components/cards/timeline.py`

**Add import (after line 9)**:
```python
from components.utils import safe_get
```

**Current code (lines 25-34)** in `create_prediction_timeline_card`:
```python
    prediction_date = row.get("prediction_date")
    timestamp = row.get("timestamp")
    tweet_text = row.get("text", "")
    sentiment = row.get("prediction_sentiment", "neutral")
    confidence = row.get("prediction_confidence", 0)
    return_t7 = row.get("return_t7")
    correct_t7 = row.get("correct_t7")
    pnl_t7 = row.get("pnl_t7")
    price_at = row.get("price_at_prediction")
    price_after = row.get("price_t7")
```

**New code**:
```python
    prediction_date = safe_get(row, "prediction_date")
    timestamp = safe_get(row, "timestamp")
    tweet_text = safe_get(row, "text", "")
    sentiment = safe_get(row, "prediction_sentiment", "neutral")
    confidence = safe_get(row, "prediction_confidence", 0)
    return_t7 = safe_get(row, "return_t7")
    correct_t7 = safe_get(row, "correct_t7")
    pnl_t7 = safe_get(row, "pnl_t7")
    price_at = safe_get(row, "price_at_prediction")
    price_after = safe_get(row, "price_t7")
```

Also fix `create_related_asset_link` (lines 235-237):

**Current**:
```python
    symbol = row.get("related_symbol", "???")
    count = row.get("co_occurrence_count", 0)
    avg_return = row.get("avg_return_t7")
```

**New**:
```python
    symbol = safe_get(row, "related_symbol", "???")
    count = safe_get(row, "co_occurrence_count", 0)
    avg_return = safe_get(row, "avg_return_t7")
```

#### Step 8: Apply NaN guards to `hero.py`

**File**: `shitty_ui/components/cards/hero.py`

**Add import (after line 5)**:
```python
from components.utils import safe_get
```

**Current code (lines 21-33)** in `create_hero_signal_card`:
```python
    timestamp = row.get("timestamp")
    text_content = row.get("text", "")
    ...
    confidence = row.get("confidence", 0)
    assets = row.get("assets", [])
    market_impact = row.get("market_impact", {})
    ...
    outcome_count = row.get("outcome_count", 0) or 0
    correct_count = row.get("correct_count", 0) or 0
    incorrect_count = row.get("incorrect_count", 0) or 0
    total_pnl_t7 = row.get("total_pnl_t7")
```

**New code**:
```python
    timestamp = safe_get(row, "timestamp")
    text_content = safe_get(row, "text", "")
    ...
    confidence = safe_get(row, "confidence", 0)
    assets = safe_get(row, "assets", [])
    market_impact = safe_get(row, "market_impact", {})
    ...
    outcome_count = safe_get(row, "outcome_count", 0) or 0
    correct_count = safe_get(row, "correct_count", 0) or 0
    incorrect_count = safe_get(row, "incorrect_count", 0) or 0
    total_pnl_t7 = safe_get(row, "total_pnl_t7")
```

Also fix line 65:
**Current**:
```python
    pnl_display = total_pnl_t7 if total_pnl_t7 is not None else row.get("pnl_t7")
```

**New**:
```python
    pnl_display = total_pnl_t7 if total_pnl_t7 is not None else safe_get(row, "pnl_t7")
```

#### Step 9: Apply NaN guards to `signal.py`

**File**: `shitty_ui/components/cards/signal.py`

**Add import (after line 9)**:
```python
from components.utils import safe_get
```

**Current code (lines 28-36)** in `create_signal_card`:
```python
    timestamp = row.get("timestamp")
    text_content = row.get("text", "")
    ...
    confidence = row.get("confidence", 0)
    assets = row.get("assets", [])
    market_impact = row.get("market_impact", {})
    correct_t7 = row.get("correct_t7")
    pnl_t7 = row.get("pnl_t7")
```

**New code**:
```python
    timestamp = safe_get(row, "timestamp")
    text_content = safe_get(row, "text", "")
    ...
    confidence = safe_get(row, "confidence", 0)
    assets = safe_get(row, "assets", [])
    market_impact = safe_get(row, "market_impact", {})
    correct_t7 = safe_get(row, "correct_t7")
    pnl_t7 = safe_get(row, "pnl_t7")
```

**Current code (lines 140-153)** in `create_unified_signal_card`:
```python
    timestamp = row.get("timestamp")
    text_content = row.get("text", "")
    ...
    confidence = row.get("confidence", 0)
    assets = row.get("assets", [])
    market_impact = row.get("market_impact", {})
    thesis = row.get("thesis", "")

    # Aggregated outcome data (from GROUP BY query)
    outcome_count = row.get("outcome_count", 0) or 0
    correct_count = row.get("correct_count", 0) or 0
    incorrect_count = row.get("incorrect_count", 0) or 0
    total_pnl_t7 = row.get("total_pnl_t7")
```

**New code**:
```python
    timestamp = safe_get(row, "timestamp")
    text_content = safe_get(row, "text", "")
    ...
    confidence = safe_get(row, "confidence", 0)
    assets = safe_get(row, "assets", [])
    market_impact = safe_get(row, "market_impact", {})
    thesis = safe_get(row, "thesis", "")

    # Aggregated outcome data (from GROUP BY query)
    outcome_count = safe_get(row, "outcome_count", 0) or 0
    correct_count = safe_get(row, "correct_count", 0) or 0
    incorrect_count = safe_get(row, "incorrect_count", 0) or 0
    total_pnl_t7 = safe_get(row, "total_pnl_t7")
```

#### Step 10: Apply NaN guards to `dashboard_callbacks/content.py`

**File**: `shitty_ui/pages/dashboard_callbacks/content.py`

**Add import (after line 8)**:
```python
from components.utils import safe_format_pct, safe_format_dollar
```

**Current code (line 130)**:
```python
                            f"{kpis['avg_return_t7']:+.2f}%",
```

**New code**:
```python
                            safe_format_pct(kpis['avg_return_t7']),
```

**Current code (line 146)**:
```python
                            f"${kpis['total_pnl']:+,.0f}",
```

**New code**:
```python
                            safe_format_dollar(kpis['total_pnl']),
```

**Why**: Although `get_dashboard_kpis()` returns 0.0 defaults, edge cases (e.g., cache invalidation, database returning NULL for AVG of an empty set that sneaks past the `or 0.0` guard) can leak NaN. Defensive formatting at the display layer is the last line of defense.

#### Step 11: Apply NaN guards to `pages/assets.py`

**File**: `shitty_ui/pages/assets.py`

**Add import (after line 8)**:
```python
from components.utils import safe_format_pct, safe_format_dollar
```

**Current code (line 346)** inside `update_asset_page`:
```python
                            f"${stats['total_pnl_t7']:,.0f}",
```

**New code**:
```python
                            safe_format_dollar(stats['total_pnl_t7'], fmt=",.0f"),
```

Note: `safe_format_dollar` uses `+,.0f` by default (with sign). For the asset page stat card, we want `,.0f` (no forced sign). The function's `fmt` parameter supports this.

**Current code (line 361)**:
```python
                            f"{stats['avg_return_t7']:+.2f}%",
```

**New code**:
```python
                            safe_format_pct(stats['avg_return_t7']),
```

Also guard the color conditionals around these values. Currently line 350:
```python
                            (
                                COLORS["success"]
                                if stats["total_pnl_t7"] > 0
                                else COLORS["danger"]
                            ),
```

**New code**:
```python
                            (
                                COLORS["success"]
                                if (stats["total_pnl_t7"] or 0) > 0
                                else COLORS["danger"]
                            ),
```

And line 365:
```python
                            (
                                COLORS["success"]
                                if stats["avg_return_t7"] > 0
                                else COLORS["danger"]
                            ),
```

**New code**:
```python
                            (
                                COLORS["success"]
                                if (stats["avg_return_t7"] or 0) > 0
                                else COLORS["danger"]
                            ),
```

**Why**: Comparing `NaN > 0` returns `False` in Python (so it would always show danger color), but it is semantically wrong. Using `or 0` normalizes NaN/None to 0 for the color comparison.

## Test Plan

### New test file: `shit_tests/shitty_ui/test_utils.py`

```python
"""Tests for shitty_ui/components/utils.py -- NaN-safe utilities."""

import sys
import os
import math
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))

from components.utils import safe_get, safe_format_pct, safe_format_dollar


class TestSafeGet:
    """Tests for the safe_get NaN-guard helper."""

    def test_returns_value_for_normal_float(self):
        assert safe_get({"key": 1.5}, "key") == 1.5

    def test_returns_default_for_nan(self):
        assert safe_get({"key": float("nan")}, "key", 0.0) == 0.0

    def test_returns_default_for_missing_key(self):
        assert safe_get({}, "key", "fallback") == "fallback"

    def test_returns_none_for_missing_key_no_default(self):
        assert safe_get({}, "key") is None

    def test_returns_default_for_none_value(self):
        assert safe_get({"key": None}, "key", 42) == 42

    def test_returns_string_value_unchanged(self):
        assert safe_get({"key": "hello"}, "key") == "hello"

    def test_returns_list_value_unchanged(self):
        assert safe_get({"key": [1, 2]}, "key") == [1, 2]

    def test_returns_zero_float_not_treated_as_nan(self):
        assert safe_get({"key": 0.0}, "key", 999) == 0.0

    def test_returns_negative_float_unchanged(self):
        assert safe_get({"key": -3.14}, "key") == -3.14

    def test_works_with_pandas_series(self):
        import pandas as pd
        row = pd.Series({"val": float("nan"), "ok": 42})
        assert safe_get(row, "val", 0) == 0
        assert safe_get(row, "ok", 0) == 42

    def test_returns_bool_unchanged(self):
        assert safe_get({"key": True}, "key") is True
        assert safe_get({"key": False}, "key") is False


class TestSafeFormatPct:
    """Tests for safe_format_pct."""

    def test_formats_positive_float(self):
        assert safe_format_pct(2.5) == "+2.50%"

    def test_formats_negative_float(self):
        assert safe_format_pct(-1.23) == "-1.23%"

    def test_returns_dash_for_none(self):
        assert safe_format_pct(None) == "--"

    def test_returns_dash_for_nan(self):
        assert safe_format_pct(float("nan")) == "--"

    def test_formats_zero(self):
        assert safe_format_pct(0.0) == "+0.00%"

    def test_custom_format(self):
        assert safe_format_pct(5.0, fmt=".1f") == "5.0%"


class TestSafeFormatDollar:
    """Tests for safe_format_dollar."""

    def test_formats_positive_amount(self):
        assert safe_format_dollar(1234.0) == "$+1,234"

    def test_formats_negative_amount(self):
        assert safe_format_dollar(-500.0) == "$-500"

    def test_returns_dash_for_none(self):
        assert safe_format_dollar(None) == "--"

    def test_returns_dash_for_nan(self):
        assert safe_format_dollar(float("nan")) == "--"

    def test_formats_zero(self):
        assert safe_format_dollar(0.0) == "$+0"

    def test_custom_format_no_sign(self):
        assert safe_format_dollar(1234.0, fmt=",.0f") == "$1,234"
```

### Modified test file: `shit_tests/shit/market_data/test_outcome_calculator.py`

Update `TestExtractSentiment` class to test the new per-asset behavior:

```python
class TestExtractSentiment:
    def test_extracts_first_sentiment_when_no_asset(self, calculator):
        result = calculator._extract_sentiment({"AAPL": "Bullish"})
        assert result == "bullish"

    def test_returns_none_for_empty_dict(self, calculator):
        assert calculator._extract_sentiment({}) is None

    def test_returns_none_for_none(self, calculator):
        assert calculator._extract_sentiment(None) is None

    def test_lowercases_sentiment(self, calculator):
        result = calculator._extract_sentiment({"TSLA": "BEARISH"})
        assert result == "bearish"

    def test_multi_asset_returns_first_when_no_asset_specified(self, calculator):
        result = calculator._extract_sentiment({"AAPL": "bullish", "TSLA": "bearish"})
        assert result in ("bullish", "bearish")  # dict ordering

    # --- New per-asset tests ---

    def test_per_asset_exact_match(self, calculator):
        mi = {"AAPL": "bullish", "TSLA": "bearish"}
        assert calculator._extract_sentiment(mi, asset="AAPL") == "bullish"
        assert calculator._extract_sentiment(mi, asset="TSLA") == "bearish"

    def test_per_asset_case_insensitive(self, calculator):
        mi = {"AAPL": "bullish", "TSLA": "bearish"}
        assert calculator._extract_sentiment(mi, asset="aapl") == "bullish"
        assert calculator._extract_sentiment(mi, asset="tsla") == "bearish"

    def test_per_asset_falls_back_to_first_when_not_found(self, calculator):
        mi = {"AAPL": "bullish"}
        result = calculator._extract_sentiment(mi, asset="GOOG")
        assert result == "bullish"  # fallback to first

    def test_per_asset_handles_mixed_case_keys(self, calculator):
        mi = {"Aapl": "bullish"}
        assert calculator._extract_sentiment(mi, asset="AAPL") == "bullish"
```

### Modified test: verify per-asset sentiment flows through `calculate_outcome_for_prediction`

Add a new test to `TestCalculateOutcomeForPrediction`:

```python
def test_passes_per_asset_sentiment(self, calculator, mock_session):
    """Verify each asset gets its own sentiment from market_impact."""
    pred = _make_prediction(
        assets=["AAPL", "TSLA"],
        market_impact={"AAPL": "bullish", "TSLA": "bearish"},
    )
    mock_session.query.return_value.filter.return_value.first.return_value = pred

    mock_outcome = MagicMock(spec=PredictionOutcome)
    calculator._calculate_single_outcome = MagicMock(return_value=mock_outcome)

    calculator.calculate_outcome_for_prediction(1)

    calls = calculator._calculate_single_outcome.call_args_list
    assert len(calls) == 2
    # First call: AAPL should get "bullish"
    assert calls[0].kwargs.get("sentiment") == "bullish" or calls[0][1].get("sentiment") == "bullish"
    # Second call: TSLA should get "bearish"
    assert calls[1].kwargs.get("sentiment") == "bearish" or calls[1][1].get("sentiment") == "bearish"
```

**Note**: The `_calculate_single_outcome` is called with keyword arguments, so check `call_args_list[N]` using kwargs:
```python
    calls = calculator._calculate_single_outcome.call_args_list
    assert len(calls) == 2
    assert calls[0].kwargs["sentiment"] == "bullish"
    assert calls[1].kwargs["sentiment"] == "bearish"
```

### Modified test file: `shit_tests/shitty_ui/test_cards.py`

Add NaN-resilience tests:

```python
class TestNanResilience:
    """Verify cards don't render 'nan' when row values are NaN."""

    def test_timeline_card_nan_return(self):
        """Timeline card should show '--' not '+nan%' when return_t7 is NaN."""
        card = create_prediction_timeline_card(
            _make_timeline_row(return_t7=float("nan"), pnl_t7=float("nan"))
        )
        text = _extract_text(card)
        assert "nan" not in text.lower()
        assert "--" in text

    def test_timeline_card_nan_price(self):
        """Timeline card handles NaN prices without crashing."""
        card = create_prediction_timeline_card(
            _make_timeline_row(
                price_at_prediction=float("nan"),
                price_t7=float("nan"),
            )
        )
        text = _extract_text(card)
        assert "nan" not in text.lower()

    def test_hero_card_nan_confidence(self):
        """Hero card handles NaN confidence without crashing."""
        card = create_hero_signal_card(_make_row(confidence=float("nan")))
        text = _extract_text(card)
        assert "nan" not in text.lower()

    def test_signal_card_nan_pnl(self):
        """Signal card handles NaN pnl_t7 without crashing."""
        card = create_signal_card(_make_row(pnl_t7=float("nan")))
        text = _extract_text(card)
        assert "nan" not in text.lower()

    def test_unified_card_nan_total_pnl(self):
        """Unified card handles NaN total_pnl_t7 without crashing."""
        card = create_unified_signal_card(
            _make_row(total_pnl_t7=float("nan"))
        )
        text = _extract_text(card)
        assert "nan" not in text.lower()

    def test_feed_card_nan_return(self):
        """Feed card handles NaN return_t7 without crashing."""
        card = create_feed_signal_card(_make_row(return_t7=float("nan")))
        text = _extract_text(card)
        assert "nan" not in text.lower()

    def test_related_asset_link_nan_return(self):
        """Related asset link handles NaN avg_return_t7."""
        card = create_related_asset_link({
            "related_symbol": "TSLA",
            "co_occurrence_count": 3,
            "avg_return_t7": float("nan"),
        })
        text = _extract_text(card)
        assert "nan" not in text.lower()
        assert "--" in text
```

### Existing tests to verify pass

Run the full test suite to ensure no regressions:
```bash
source venv/bin/activate && pytest shit_tests/shit/market_data/test_outcome_calculator.py -v
source venv/bin/activate && pytest shit_tests/shitty_ui/test_cards.py -v
source venv/bin/activate && pytest shit_tests/shitty_ui/test_utils.py -v
source venv/bin/activate && pytest -v
```

## Documentation Updates

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Fixed
- **Sentiment Extraction Bug** - Per-asset sentiment now correctly looked up from `market_impact` dict instead of applying first sentiment to all assets
  - `OutcomeCalculator._extract_sentiment()` accepts optional `asset` parameter for case-insensitive lookup
  - Sentiment extraction moved inside the asset loop in `calculate_outcome_for_prediction()`
  - Added `fix-sentiments` CLI command to recalculate affected multi-asset outcomes
- **NaN Display Guards** - Extracted `safe_get()` from feed.py to shared `components/utils.py` and applied across all UI card components
  - Added `safe_format_pct()` and `safe_format_dollar()` formatting helpers
  - Applied NaN guards to: timeline.py, hero.py, signal.py, content.py, assets.py
  - Dashboard KPI cards and asset stat cards no longer show "+nan%" or "$nan"
```

## Stress Testing & Edge Cases

### Sentiment extraction edge cases
- **Single asset prediction**: `_extract_sentiment({"AAPL": "bullish"}, asset="AAPL")` -- direct match
- **Asset not in market_impact**: `_extract_sentiment({"AAPL": "bullish"}, asset="GOOG")` -- falls back to first
- **Empty market_impact**: `_extract_sentiment({}, asset="AAPL")` -- returns None
- **None market_impact**: `_extract_sentiment(None, asset="AAPL")` -- returns None
- **Case mismatch**: `_extract_sentiment({"aapl": "bullish"}, asset="AAPL")` -- case-insensitive match
- **Non-string sentiment value**: `_extract_sentiment({"AAPL": 123})` -- guard against non-string; `isinstance` check returns None on fall-through

### NaN edge cases
- `float('nan')` in numeric fields (`return_t7`, `pnl_t7`, `confidence`)
- `float('nan')` in price fields (`price_at_prediction`, `price_t7`)
- `None` values (already handled by most code, but `safe_get` unifies the behavior)
- Mixed NaN and valid values in the same row
- `0.0` values (must NOT be treated as NaN)
- Boolean `False` (must NOT be treated as NaN)
- Pandas `pd.NA` (would fail `isinstance(value, float)` check -- passes through unchanged, which is correct since it is not `float('nan')`)

## Verification Checklist

- [ ] `_extract_sentiment({"AAPL": "bullish", "TSLA": "bearish"}, asset="TSLA")` returns `"bearish"`
- [ ] `_extract_sentiment({"AAPL": "bullish", "TSLA": "bearish"}, asset="AAPL")` returns `"bullish"`
- [ ] `_extract_sentiment({"AAPL": "bullish"})` still returns `"bullish"` (backward compat, no asset arg)
- [ ] All existing `TestExtractSentiment` tests pass
- [ ] New per-asset sentiment tests pass
- [ ] `safe_get({"x": float("nan")}, "x", 0)` returns `0`
- [ ] `safe_get({"x": 0.0}, "x", 999)` returns `0.0` (not 999)
- [ ] No card component renders "nan" in its text output
- [ ] Dashboard KPI cards display "--" instead of "+nan%" when data is missing
- [ ] Asset page stat cards display "--" instead of "$nan" when data is missing
- [ ] Full test suite passes: `source venv/bin/activate && pytest -v`
- [ ] Linting passes: `source venv/bin/activate && python -m ruff check .`
- [ ] `fix-sentiments` CLI command runs without error (dry-run against production)

## What NOT To Do

1. **Do NOT change the `_extract_sentiment()` return type or None semantics.** It currently returns `Optional[str]`. The callers expect `None` for empty/missing impact. Do not change this to return `"neutral"` -- that would mask missing data.

2. **Do NOT apply `safe_get` to `post.py`.** The post card (`shitty_ui/components/cards/post.py`) does not display float metrics (return_t7, pnl_t7). It uses `row.get()` for string/list fields where NaN is not a risk. Touching this file adds unnecessary churn.

3. **Do NOT change the data layer queries** to coalesce NaN at the SQL level. The NaN problem comes from Pandas converting SQL NULL to NaN. The fix belongs at the display layer (`safe_get`), not the data layer, because (a) the data layer correctly returns `None`/0.0 from dict results, and (b) DataFrame rows naturally contain NaN for NULL columns.

4. **Do NOT run `fix-sentiments` in production without user approval.** It calls `force_refresh=True` which will re-fetch market prices and rewrite outcome rows. Follow the CLAUDE.md safety rules.

5. **`_safe_get` backward-compat alias is NOT needed.** It was always private (`_` prefix). Replace with `safe_get` cleanly — no alias.

6. **Do NOT use `pd.isna()` or `pd.isnull()` in the utility.** The `math.isnan()` approach is correct because `safe_get` receives individual values, not Series. Using `pd.isna()` would add a pandas dependency to a generic utility and behave differently for `pd.NA` vs `float('nan')`.
```

---

- Wrote: /Users/chris/Projects/shitpost-alpha/documentation/planning/phases/alpha-quality_2026-03-04/02_fix-sentiment-bug-nan-guards.md
- PR title: fix: per-asset sentiment extraction and NaN display guards
- Effort: Low (2-3 hours)
- Risk: Low
- Files modified: 8 | Files created: 2
- Dependencies: None
- Unlocks: Phase 01 (Outcome Maturation Pipeline)

### Critical Files for Implementation
- `/Users/chris/Projects/shitpost-alpha/shit/market_data/outcome_calculator.py` - Core bug: `_extract_sentiment()` needs per-asset lookup and must be called inside the asset loop
- `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/cards/feed.py` - Source of `_safe_get()` pattern to extract to shared utility
- `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/utils.py` - New file: shared `safe_get`, `safe_format_pct`, `safe_format_dollar` utilities
- `/Users/chris/Projects/shitpost-alpha/shitty_ui/components/cards/timeline.py` - Worst NaN offender: bare `row.get()` for `return_t7` renders "+nan%"
- `/Users/chris/Projects/shitpost-alpha/shitty_ui/pages/dashboard_callbacks/content.py` - KPI format strings need NaN-safe formatting helpers