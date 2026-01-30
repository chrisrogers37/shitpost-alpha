# Data Layer Expansion Specification

> **STATUS: COMPLETE ✅** - All tasks implemented as of 2026-01-30.

## Implementation Context for Engineering Team

### Current State (as of 2026-01-30)

**ALL TASKS COMPLETE:**

| Task | Status | Notes |
|------|--------|-------|
| Task 1: Query Caching | ✅ Complete | `ttl_cache` decorator with 5-10 min TTL |
| Task 2: Time Filtering | ✅ Complete | All 7 functions support `days` param |
| Task 3: New Aggregates | ✅ Complete | 5 new functions for Performance Page |
| Task 4: Connection Pool | ✅ Complete | Pool size 5, overflow 10, 30min recycle |

**Functions with `days` parameter:**

| Function | `days` param | Cached | Notes |
|----------|-------------|--------|-------|
| `get_performance_metrics(days)` | ✅ | ✅ 5min | Full implementation |
| `get_accuracy_by_confidence(days)` | ✅ | ✅ 5min | Full implementation |
| `get_accuracy_by_asset(limit, days)` | ✅ | ✅ 5min | Full implementation |
| `get_recent_signals(limit, conf, days)` | ✅ | ❌ | Real-time signals |
| `get_sentiment_distribution(days)` | ✅ | ✅ 5min | Added 2026-01-30 |
| `get_similar_predictions(asset, limit, days)` | ✅ | ❌ | User-specific |
| `get_predictions_with_outcomes(limit, days)` | ✅ | ❌ | Table data |

**New aggregate functions:**

| Function | Purpose | Status |
|----------|---------|--------|
| `get_cumulative_pnl(days)` | Equity curve data | ✅ Complete |
| `get_rolling_accuracy(window, days)` | Rolling performance | ✅ Complete |
| `get_win_loss_streaks()` | Streak tracking | ✅ Complete |
| `get_confidence_calibration(buckets)` | Calibration chart | ✅ Complete |
| `get_monthly_performance(months)` | Monthly summary | ✅ Complete |
| `clear_all_caches()` | Cache invalidation | ✅ Complete |

**Implementation pattern used:**

```python
date_filter = ""
params = {}
if days is not None:
    date_filter = "WHERE prediction_date >= :start_date"  # or "AND ..."
    params["start_date"] = (datetime.now() - timedelta(days=days)).date()
```

**Cache pattern used:**

```python
@ttl_cache(ttl_seconds=300)  # 5 minutes
def get_performance_metrics(days: int = None) -> Dict[str, Any]:
    ...
```

### Existing `data.py` Functions (13 total)

```python
# Base function
execute_query(query, params)           # Generic executor

# Post loading
load_recent_posts(limit)               # Raw posts
load_filtered_posts(...)               # Advanced filters

# Statistics
get_prediction_stats()                 # Prediction counts
get_performance_metrics(days)          # ✅ Has days param
get_accuracy_by_confidence(days)       # ✅ Has days param
get_accuracy_by_asset(limit, days)     # ✅ Has days param
get_sentiment_distribution()           # Needs days param

# Signals & Predictions
get_recent_signals(limit, conf, days)  # ✅ Has days param
get_similar_predictions(asset, limit)  # Needs days param
get_predictions_with_outcomes(limit)   # Needs days param

# Assets
get_available_assets()                 # Hardcoded list
get_active_assets_from_db()            # From prediction_outcomes
```

---

## Overview

This document specifies improvements to the data layer (`shitty_ui/data.py`). The current data layer queries the database on every page load with no caching, no time filtering, and limited aggregation. These enhancements make the dashboard faster and more feature-rich.

**Estimated Effort**: 2-3 days (reduced due to partial completion)
**Priority**: P1 (Should Have)
**Prerequisites**: None - can be done in parallel with Performance Page (03)

---

## Current State

### Existing Functions in `data.py`

| Function | Purpose | Cached? | Time Filter? |
|----------|---------|---------|--------------|
| `execute_query(query, params)` | Base query executor | No | N/A |
| `load_recent_posts(limit)` | Load posts with predictions | No | No |
| `load_filtered_posts(...)` | Load posts with advanced filters | No | Yes |
| `get_available_assets()` | Hardcoded asset list | N/A | N/A |
| `get_prediction_stats()` | Basic prediction statistics | No | No |
| `get_recent_signals(limit, min_confidence)` | Recent actionable signals | No | No |
| `get_performance_metrics()` | Overall accuracy and P&L | No | No |
| `get_accuracy_by_confidence()` | Accuracy by confidence level | No | No |
| `get_accuracy_by_asset(limit)` | Accuracy by asset | No | No |
| `get_similar_predictions(asset, limit)` | Historical predictions for asset | No | No |
| `get_predictions_with_outcomes(limit)` | Predictions with outcome data | No | No |
| `get_sentiment_distribution()` | Bullish/bearish/neutral counts | No | No |
| `get_active_assets_from_db()` | Assets with outcome data | No | No |

---

## Task 1: Add Query Caching

### Problem

Every 5-minute refresh queries the database 6+ times. Most data doesn't change between refreshes.

### Solution

Add a simple time-based cache using `functools.lru_cache` with a TTL wrapper.

### Implementation

#### Step 1: Create Cache Utility

Add to the top of `data.py`:

```python
import time
from functools import wraps
from typing import Callable, Any

# Simple TTL cache decorator
def ttl_cache(ttl_seconds: int = 300):
    """
    Cache function results for a given number of seconds.
    Uses function arguments as cache key.

    Args:
        ttl_seconds: How long to cache results (default 5 minutes)
    """
    def decorator(func: Callable) -> Callable:
        cache = {}

        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            key = (func.__name__, args, tuple(sorted(kwargs.items())))
            now = time.time()

            # Check if cached result exists and is still valid
            if key in cache:
                result, timestamp = cache[key]
                if now - timestamp < ttl_seconds:
                    return result

            # Call function and cache result
            result = func(*args, **kwargs)
            cache[key] = (result, now)
            return result

        # Add method to manually clear cache
        def clear_cache():
            cache.clear()

        wrapper.clear_cache = clear_cache
        return wrapper

    return decorator
```

#### Step 2: Apply Cache to Expensive Queries

```python
@ttl_cache(ttl_seconds=300)  # Cache for 5 minutes
def get_performance_metrics(days: int = None) -> Dict[str, Any]:
    """Get overall prediction performance metrics."""
    # ... existing implementation
    pass

@ttl_cache(ttl_seconds=300)
def get_accuracy_by_confidence(days: int = None) -> pd.DataFrame:
    """Get accuracy by confidence level."""
    # ... existing implementation
    pass

@ttl_cache(ttl_seconds=300)
def get_accuracy_by_asset(limit: int = 15, days: int = None) -> pd.DataFrame:
    """Get accuracy by asset."""
    # ... existing implementation
    pass

@ttl_cache(ttl_seconds=600)  # Cache for 10 minutes (changes less often)
def get_active_assets_from_db() -> List[str]:
    """Get active assets."""
    # ... existing implementation
    pass

# Don't cache these - they need to be fresh:
# - get_recent_signals (users expect real-time)
# - get_similar_predictions (depends on user input)
# - get_predictions_with_outcomes (table data, filtered)
```

#### Step 3: Add Cache Clear on Refresh

```python
def clear_all_caches():
    """Clear all data layer caches. Call when forcing a full refresh."""
    get_performance_metrics.clear_cache()
    get_accuracy_by_confidence.clear_cache()
    get_accuracy_by_asset.clear_cache()
    get_active_assets_from_db.clear_cache()
    get_prediction_stats.clear_cache()
```

### Tests

```python
class TestTTLCache:
    def test_caches_result(self):
        """Test that repeated calls return cached result."""
        call_count = 0

        @ttl_cache(ttl_seconds=60)
        def expensive_function():
            nonlocal call_count
            call_count += 1
            return "result"

        result1 = expensive_function()
        result2 = expensive_function()

        assert result1 == result2
        assert call_count == 1  # Only called once

    def test_cache_expires(self):
        """Test that cache expires after TTL."""
        call_count = 0

        @ttl_cache(ttl_seconds=0)  # Expire immediately
        def expensive_function():
            nonlocal call_count
            call_count += 1
            return "result"

        expensive_function()
        time.sleep(0.1)
        expensive_function()

        assert call_count == 2  # Called twice

    def test_clear_cache(self):
        """Test that cache can be manually cleared."""
        call_count = 0

        @ttl_cache(ttl_seconds=300)
        def expensive_function():
            nonlocal call_count
            call_count += 1
            return "result"

        expensive_function()
        expensive_function.clear_cache()
        expensive_function()

        assert call_count == 2

    def test_different_args_different_cache(self):
        """Test that different arguments have separate cache entries."""
        @ttl_cache(ttl_seconds=60)
        def get_data(limit):
            return f"data_{limit}"

        assert get_data(10) == "data_10"
        assert get_data(20) == "data_20"
```

---

## Task 2: Add Time Filtering to All Queries

### Problem

Dashboard shows all-time data. Users need to filter by time period (7d, 30d, 90d).

### Solution

Add optional `days` parameter to all query functions.

### Implementation

#### Pattern: Date Filter Helper

```python
def _build_date_filter(days: int = None, date_column: str = "prediction_date") -> tuple:
    """
    Build a SQL date filter clause.

    Args:
        days: Number of days to look back (None = no filter)
        date_column: The column name to filter on

    Returns:
        Tuple of (sql_clause, params_dict)
    """
    if days is None:
        return "", {}

    from datetime import datetime, timedelta
    start_date = datetime.now().date() - timedelta(days=days)

    return f"AND {date_column} >= :start_date", {"start_date": start_date}
```

#### Update get_performance_metrics

```python
@ttl_cache(ttl_seconds=300)
def get_performance_metrics(days: int = None) -> Dict[str, Any]:
    """
    Get overall prediction performance metrics.

    Args:
        days: Number of days to look back (None = all time)
    """
    date_clause, date_params = _build_date_filter(days, "prediction_date")

    query = text(f"""
        SELECT
            COUNT(*) as total_outcomes,
            COUNT(CASE WHEN correct_t7 = true THEN 1 END) as correct_t7,
            COUNT(CASE WHEN correct_t7 = false THEN 1 END) as incorrect_t7,
            COUNT(CASE WHEN correct_t7 IS NOT NULL THEN 1 END) as evaluated_t7,
            AVG(CASE WHEN correct_t7 IS NOT NULL THEN return_t7 END) as avg_return_t7,
            SUM(CASE WHEN pnl_t7 IS NOT NULL THEN pnl_t7 ELSE 0 END) as total_pnl_t7,
            AVG(prediction_confidence) as avg_confidence
        FROM prediction_outcomes
        WHERE 1=1 {date_clause}
    """)

    try:
        rows, columns = execute_query(query, date_params)
        # ... rest unchanged
    except Exception as e:
        print(f"Error loading performance metrics: {e}")

    # ... return defaults
```

#### Update get_accuracy_by_confidence

```python
@ttl_cache(ttl_seconds=300)
def get_accuracy_by_confidence(days: int = None) -> pd.DataFrame:
    """Get accuracy by confidence level with optional time filter."""
    date_clause, date_params = _build_date_filter(days, "prediction_date")

    query = text(f"""
        SELECT
            CASE
                WHEN prediction_confidence < 0.6 THEN 'Low (<60%)'
                WHEN prediction_confidence < 0.75 THEN 'Medium (60-75%)'
                ELSE 'High (>75%)'
            END as confidence_level,
            COUNT(*) as total,
            COUNT(CASE WHEN correct_t7 = true THEN 1 END) as correct,
            COUNT(CASE WHEN correct_t7 = false THEN 1 END) as incorrect,
            ROUND(AVG(CASE WHEN return_t7 IS NOT NULL THEN return_t7 END)::numeric, 2) as avg_return,
            ROUND(SUM(CASE WHEN pnl_t7 IS NOT NULL THEN pnl_t7 ELSE 0 END)::numeric, 2) as total_pnl
        FROM prediction_outcomes
        WHERE correct_t7 IS NOT NULL {date_clause}
        GROUP BY 1
        ORDER BY
            CASE
                WHEN prediction_confidence < 0.6 THEN 1
                WHEN prediction_confidence < 0.75 THEN 2
                ELSE 3
            END
    """)

    try:
        rows, columns = execute_query(query, date_params)
        df = pd.DataFrame(rows, columns=columns)
        if not df.empty:
            df['accuracy'] = (df['correct'] / df['total'] * 100).round(1)
        return df
    except Exception as e:
        print(f"Error loading accuracy by confidence: {e}")
        return pd.DataFrame()
```

#### Apply Same Pattern to Other Functions

Same approach for:
- `get_accuracy_by_asset(limit, days)`
- `get_recent_signals(limit, min_confidence, days)`
- `get_sentiment_distribution(days)`

### Tests

```python
class TestDateFiltering:
    def test_build_date_filter_with_days(self):
        """Test date filter clause generation."""
        from data import _build_date_filter
        clause, params = _build_date_filter(30)
        assert "start_date" in clause
        assert "start_date" in params

    def test_build_date_filter_without_days(self):
        """Test no filter when days is None."""
        from data import _build_date_filter
        clause, params = _build_date_filter(None)
        assert clause == ""
        assert params == {}

    @patch('data.execute_query')
    def test_performance_metrics_with_days(self, mock_execute):
        """Test that days parameter is passed to query."""
        from data import get_performance_metrics
        mock_execute.return_value = (
            [(10, 6, 4, 10, 1.5, 1500.0, 0.7)],
            ['total_outcomes', 'correct_t7', 'incorrect_t7', 'evaluated_t7',
             'avg_return_t7', 'total_pnl_t7', 'avg_confidence']
        )
        result = get_performance_metrics(days=30)
        call_args = mock_execute.call_args
        assert "start_date" in call_args[0][1]
```

---

## Task 3: Add New Aggregate Functions

### Problem

Several dashboard features need data aggregations that don't exist yet.

### Solution

Add new query functions for specific dashboard needs.

### 3a: Cumulative P&L Over Time

```python
def get_cumulative_pnl(days: int = None) -> pd.DataFrame:
    """
    Get cumulative P&L over time for equity curve visualization.

    Returns DataFrame with columns: date, daily_pnl, cumulative_pnl
    """
    date_clause, date_params = _build_date_filter(days, "prediction_date")

    query = text(f"""
        SELECT
            prediction_date,
            SUM(CASE WHEN pnl_t7 IS NOT NULL THEN pnl_t7 ELSE 0 END) as daily_pnl,
            COUNT(*) as predictions_count
        FROM prediction_outcomes
        WHERE correct_t7 IS NOT NULL {date_clause}
        GROUP BY prediction_date
        ORDER BY prediction_date ASC
    """)

    try:
        rows, columns = execute_query(query, date_params)
        df = pd.DataFrame(rows, columns=columns)
        if not df.empty:
            df['cumulative_pnl'] = df['daily_pnl'].cumsum()
        return df
    except Exception as e:
        print(f"Error loading cumulative P&L: {e}")
        return pd.DataFrame()
```

### 3b: Rolling Accuracy

```python
def get_rolling_accuracy(window: int = 30, days: int = None) -> pd.DataFrame:
    """
    Get rolling accuracy over time.

    Args:
        window: Rolling window size in days
        days: Total days to look back

    Returns DataFrame with: date, accuracy, total_predictions
    """
    date_clause, date_params = _build_date_filter(days, "prediction_date")

    query = text(f"""
        SELECT
            prediction_date,
            COUNT(CASE WHEN correct_t7 = true THEN 1 END) as correct,
            COUNT(CASE WHEN correct_t7 IS NOT NULL THEN 1 END) as total
        FROM prediction_outcomes
        WHERE correct_t7 IS NOT NULL {date_clause}
        GROUP BY prediction_date
        ORDER BY prediction_date ASC
    """)

    try:
        rows, columns = execute_query(query, date_params)
        df = pd.DataFrame(rows, columns=columns)
        if not df.empty and len(df) > 0:
            df['rolling_correct'] = df['correct'].rolling(window=window, min_periods=1).sum()
            df['rolling_total'] = df['total'].rolling(window=window, min_periods=1).sum()
            df['rolling_accuracy'] = (df['rolling_correct'] / df['rolling_total'] * 100).round(1)
        return df
    except Exception as e:
        print(f"Error loading rolling accuracy: {e}")
        return pd.DataFrame()
```

### 3c: Win/Loss Streaks

```python
def get_win_loss_streaks() -> Dict[str, Any]:
    """
    Calculate current and max win/loss streaks.

    Returns dict with:
        current_streak: positive for wins, negative for losses
        max_win_streak: longest consecutive correct predictions
        max_loss_streak: longest consecutive incorrect predictions
    """
    query = text("""
        SELECT
            prediction_date,
            correct_t7
        FROM prediction_outcomes
        WHERE correct_t7 IS NOT NULL
        ORDER BY prediction_date ASC, created_at ASC
    """)

    try:
        rows, columns = execute_query(query)
        if not rows:
            return {"current_streak": 0, "max_win_streak": 0, "max_loss_streak": 0}

        outcomes = [row[1] for row in rows]  # List of True/False

        # Calculate streaks
        max_win = 0
        max_loss = 0
        current = 0

        for correct in outcomes:
            if correct:
                if current > 0:
                    current += 1
                else:
                    current = 1
                max_win = max(max_win, current)
            else:
                if current < 0:
                    current -= 1
                else:
                    current = -1
                max_loss = max(max_loss, abs(current))

        return {
            "current_streak": current,
            "max_win_streak": max_win,
            "max_loss_streak": max_loss,
        }
    except Exception as e:
        print(f"Error loading win/loss streaks: {e}")
        return {"current_streak": 0, "max_win_streak": 0, "max_loss_streak": 0}
```

### 3d: Confidence Calibration

```python
def get_confidence_calibration(buckets: int = 10) -> pd.DataFrame:
    """
    Get confidence calibration data (predicted confidence vs actual accuracy).

    Buckets predictions by confidence level and calculates actual
    accuracy for each bucket. A well-calibrated model should show
    predictions with 70% confidence being correct ~70% of the time.

    Args:
        buckets: Number of confidence buckets (default 10 = 0-10%, 10-20%, etc.)

    Returns DataFrame with: bucket, predicted_confidence, actual_accuracy, count
    """
    bucket_size = 1.0 / buckets

    query = text(f"""
        SELECT
            FLOOR(prediction_confidence / :bucket_size) * :bucket_size as bucket_start,
            COUNT(*) as total,
            COUNT(CASE WHEN correct_t7 = true THEN 1 END) as correct,
            AVG(prediction_confidence) as avg_confidence
        FROM prediction_outcomes
        WHERE correct_t7 IS NOT NULL
            AND prediction_confidence IS NOT NULL
        GROUP BY FLOOR(prediction_confidence / :bucket_size)
        ORDER BY bucket_start ASC
    """)

    try:
        rows, columns = execute_query(query, {"bucket_size": bucket_size})
        df = pd.DataFrame(rows, columns=columns)
        if not df.empty:
            df['actual_accuracy'] = (df['correct'] / df['total'] * 100).round(1)
            df['predicted_confidence'] = (df['avg_confidence'] * 100).round(1)
            df['bucket_label'] = df['bucket_start'].apply(
                lambda x: f"{int(x*100)}-{int((x+bucket_size)*100)}%"
            )
        return df
    except Exception as e:
        print(f"Error loading confidence calibration: {e}")
        return pd.DataFrame()
```

### 3e: Monthly Performance Summary

```python
def get_monthly_performance(months: int = 12) -> pd.DataFrame:
    """
    Get monthly performance summary.

    Returns DataFrame with: month, total_predictions, correct, accuracy,
    total_pnl, avg_return
    """
    query = text("""
        SELECT
            DATE_TRUNC('month', prediction_date) as month,
            COUNT(*) as total_predictions,
            COUNT(CASE WHEN correct_t7 = true THEN 1 END) as correct,
            COUNT(CASE WHEN correct_t7 = false THEN 1 END) as incorrect,
            ROUND(AVG(return_t7)::numeric, 2) as avg_return,
            ROUND(SUM(CASE WHEN pnl_t7 IS NOT NULL THEN pnl_t7 ELSE 0 END)::numeric, 2) as total_pnl
        FROM prediction_outcomes
        WHERE correct_t7 IS NOT NULL
        GROUP BY DATE_TRUNC('month', prediction_date)
        ORDER BY month DESC
        LIMIT :months
    """)

    try:
        rows, columns = execute_query(query, {"months": months})
        df = pd.DataFrame(rows, columns=columns)
        if not df.empty:
            df['accuracy'] = (df['correct'] / df['total_predictions'] * 100).round(1)
            df['month'] = pd.to_datetime(df['month']).dt.strftime('%Y-%m')
        return df
    except Exception as e:
        print(f"Error loading monthly performance: {e}")
        return pd.DataFrame()
```

### Tests for New Functions

```python
class TestCumulativePnl:
    @patch('data.execute_query')
    def test_returns_dataframe_with_cumulative(self, mock_execute):
        from data import get_cumulative_pnl
        from datetime import date
        mock_execute.return_value = (
            [
                (date(2024, 1, 1), 100.0, 3),
                (date(2024, 1, 2), -50.0, 2),
                (date(2024, 1, 3), 200.0, 5),
            ],
            ['prediction_date', 'daily_pnl', 'predictions_count']
        )
        result = get_cumulative_pnl()
        assert 'cumulative_pnl' in result.columns
        assert result['cumulative_pnl'].iloc[-1] == 250.0  # 100 - 50 + 200


class TestRollingAccuracy:
    @patch('data.execute_query')
    def test_returns_rolling_accuracy(self, mock_execute):
        from data import get_rolling_accuracy
        from datetime import date
        mock_execute.return_value = (
            [
                (date(2024, 1, 1), 3, 5),
                (date(2024, 1, 2), 4, 5),
            ],
            ['prediction_date', 'correct', 'total']
        )
        result = get_rolling_accuracy(window=2)
        assert 'rolling_accuracy' in result.columns


class TestWinLossStreaks:
    @patch('data.execute_query')
    def test_calculates_streaks(self, mock_execute):
        from data import get_win_loss_streaks
        from datetime import date
        mock_execute.return_value = (
            [
                (date(2024, 1, 1), True),
                (date(2024, 1, 2), True),
                (date(2024, 1, 3), True),
                (date(2024, 1, 4), False),
                (date(2024, 1, 5), False),
            ],
            ['prediction_date', 'correct_t7']
        )
        result = get_win_loss_streaks()
        assert result['max_win_streak'] == 3
        assert result['max_loss_streak'] == 2
        assert result['current_streak'] == -2


class TestConfidenceCalibration:
    @patch('data.execute_query')
    def test_returns_calibration_data(self, mock_execute):
        from data import get_confidence_calibration
        mock_execute.return_value = (
            [
                (0.5, 20, 12, 0.55),
                (0.7, 15, 11, 0.73),
            ],
            ['bucket_start', 'total', 'correct', 'avg_confidence']
        )
        result = get_confidence_calibration()
        assert 'actual_accuracy' in result.columns
        assert 'predicted_confidence' in result.columns


class TestMonthlyPerformance:
    @patch('data.execute_query')
    def test_returns_monthly_data(self, mock_execute):
        from data import get_monthly_performance
        from datetime import datetime
        mock_execute.return_value = (
            [
                (datetime(2024, 1, 1), 50, 30, 20, 1.5, 1500.0),
            ],
            ['month', 'total_predictions', 'correct', 'incorrect', 'avg_return', 'total_pnl']
        )
        result = get_monthly_performance()
        assert 'accuracy' in result.columns
        assert result['accuracy'].iloc[0] == 60.0
```

---

## Task 4: Connection Pool Optimization

### Problem

Each query creates a new database session. For concurrent requests this is inefficient.

### Solution

Configure SQLAlchemy connection pool properly.

### Implementation

```python
# Update engine creation in data.py
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, echo=False, future=True)
else:
    sync_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    sync_url = sync_url.replace("?sslmode=require&channel_binding=require", "")

    engine = create_engine(
        sync_url,
        echo=False,
        future=True,
        pool_size=5,            # Number of persistent connections
        max_overflow=10,        # Extra connections when pool is full
        pool_timeout=30,        # Seconds to wait for a connection
        pool_recycle=1800,      # Recycle connections after 30 minutes
        pool_pre_ping=True,     # Test connections before using
    )

SessionLocal = sessionmaker(engine, expire_on_commit=False)
```

---

## Checklist

- [x] Task 1: Query Caching ✅ COMPLETE
  - [x] Create `ttl_cache` decorator
  - [x] Apply to `get_performance_metrics`
  - [x] Apply to `get_accuracy_by_confidence`
  - [x] Apply to `get_accuracy_by_asset`
  - [x] Apply to `get_active_assets_from_db`
  - [x] Apply to `get_prediction_stats`
  - [x] Apply to `get_sentiment_distribution`
  - [x] Add `clear_all_caches()` function
  - [x] Add cache tests (4 tests)

- [x] Task 2: Time Filtering ✅ COMPLETE
  - [x] Add `days` param to `get_performance_metrics`
  - [x] Add `days` param to `get_accuracy_by_confidence`
  - [x] Add `days` param to `get_accuracy_by_asset`
  - [x] Add `days` param to `get_recent_signals`
  - [x] Add `days` param to `get_sentiment_distribution`
  - [x] Add `days` param to `get_similar_predictions`
  - [x] Add `days` param to `get_predictions_with_outcomes`
  - [x] Add tests for date filtering (9 tests total)

- [x] Task 3: New Aggregate Functions ✅ COMPLETE
  - [x] Implement `get_cumulative_pnl`
  - [x] Implement `get_rolling_accuracy`
  - [x] Implement `get_win_loss_streaks`
  - [x] Implement `get_confidence_calibration`
  - [x] Implement `get_monthly_performance`
  - [x] Add tests for all new functions (15 tests)

- [x] Task 4: Connection Pool ✅ COMPLETE
  - [x] Configure pool settings (pool_size=5, max_overflow=10)
  - [x] Add pool_recycle (30 min) and pool_pre_ping

---

## Definition of Done

- [x] All functions implemented with proper error handling
- [x] All functions have type hints
- [x] All existing tests still pass (57 data layer tests)
- [x] New tests written for every new function (23 new tests)
- [x] Cache works correctly with different parameters
- [x] Date filtering tested for all time periods
- [x] CHANGELOG.md updated
