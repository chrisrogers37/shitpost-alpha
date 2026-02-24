# Phase 04: Split data.py into domain query modules

**Status:** ✅ COMPLETE (PR #90)

| Field | Value |
|-------|-------|
| **PR Title** | refactor: split 2865-line data.py into domain query modules |
| **Risk Level** | Medium |
| **Effort** | High (~4-6 hours) |
| **Files Created** | 5 |
| **Files Modified** | 1 |
| **Files Deleted** | 1 |

## Context

`shitty_ui/data.py` is a 2,865-line monolith containing 40+ public functions across 5 distinct business domains: signal/post queries, performance/KPI metrics, asset-specific queries, signal feed with filtering/pagination, and dynamic insight generation. Every function follows the same boilerplate pattern (date filter, execute_query, try/except, logger.error), making the file extremely difficult to navigate, review, and reason about.

This refactoring splits the monolith into focused domain modules inside a `shitty_ui/data/` package while maintaining **perfect backward compatibility**. The `data/__init__.py` re-exports every public function, so all existing `from data import X` statements -- across 5 application files and 4 test files -- continue to work without modification. All `@patch("data.execute_query")` and `@patch("data.get_xxx")` decorators in tests continue to resolve correctly because Python's module system treats `data/__init__.py` as the `data` module.

This is a **pure refactor** -- no logic changes, no query changes, no API changes. The only observable difference is improved developer experience.

## Dependencies

- **Depends on**: Phase 01 (fix conftest pytest_plugins blocker so tests can be run to verify the refactoring)
- **Unlocks**: None

---

## Complete Function-to-Module Mapping

This is the authoritative mapping. Every public function in the current `data.py` appears exactly once in a target module below.

### `data/base.py` (lines 1-73, 1245-1261 of current data.py)

Infrastructure shared by all other modules.

| Function / Symbol | Current Line | Type |
|---|---|---|
| `logger` (module-level) | 17 | Variable |
| `SIGNALS_TABLE` | 20 | Constant |
| `ttl_cache` | 24-60 | Decorator |
| `execute_query` | 63-72 | Function |

### `data/signal_queries.py` (lines 75-218, 318-379, 1634-1806, 2103-2378, 2421-2560)

Signal loading, filtering, active signals, unified feed, signal feed with pagination/CSV, and price+signal combos.

| Function | Current Line | Cached? |
|---|---|---|
| `load_recent_posts` | 75-108 | No |
| `load_filtered_posts` | 111-218 | No |
| `get_recent_signals` | 318-378 | No |
| `get_active_signals` | 1634-1690 | No |
| `get_active_signals_with_fallback` | 1772-1805 | No |
| `get_unified_feed` | 1693-1769 | No |
| `get_weekly_signal_count` | 1808-1830 | No |
| `get_signal_feed` | 2103-2206 | No |
| `get_signal_feed_count` | 2209-2274 | No |
| `get_new_signals_since` | 2277-2310 | No |
| `get_signal_feed_csv` | 2313-2377 | No |
| `get_price_with_signals` | 2421-2511 | No |
| `get_multi_asset_signals` | 2514-2560 | No |

### `data/performance_queries.py` (lines 222-265, 267-504, 535-633, 918-974, 977-1003, 1006-1237, 1833-1877, 1880-1916, 1919-2095, 2380-2418)

KPIs, accuracy breakdowns, cumulative P&L, rolling metrics, streaks, calibration, backtesting.

| Function | Current Line | Cached? |
|---|---|---|
| `get_available_assets` | 222-264 | Yes (600s) |
| `get_prediction_stats` | 268-315 | Yes (300s) |
| `get_performance_metrics` | 382-440 | Yes (300s) |
| `get_dashboard_kpis` | 444-504 | Yes (300s) |
| `get_dashboard_kpis_with_fallback` | 507-531 | No (calls cached `get_dashboard_kpis`) |
| `get_accuracy_by_confidence` | 535-587 | Yes (300s) |
| `get_accuracy_by_asset` | 591-632 | Yes (300s) |
| `get_sentiment_distribution` | 919-954 | Yes (300s) |
| `get_active_assets_from_db` | 958-974 | Yes (600s) |
| `get_top_predicted_asset` | 978-1003 | Yes (600s) |
| `get_cumulative_pnl` | 1011-1049 | No |
| `get_rolling_accuracy` | 1052-1099 | No |
| `get_win_loss_streaks` | 1102-1154 | No |
| `get_confidence_calibration` | 1157-1199 | No |
| `get_monthly_performance` | 1202-1237 | No |
| `get_high_confidence_metrics` | 1834-1877 | Yes (300s) |
| `get_empty_state_context` | 1881-1916 | Yes (300s) |
| `get_best_performing_asset` | 1920-1966 | Yes (300s) |
| `get_accuracy_over_time` | 1969-2008 | No |
| `get_backtest_simulation` | 2012-2095 | Yes (300s) |
| `get_sentiment_accuracy` | 2380-2418 | No |

### `data/asset_queries.py` (lines 636-763, 766-821, 824-915, 1269-1631)

Asset screener, sparklines, asset predictions, stats, price history, related assets, predictions with outcomes, similar predictions.

| Function | Current Line | Cached? |
|---|---|---|
| `get_asset_screener_data` | 636-707 | Yes (300s) |
| `get_screener_sparkline_prices` | 711-763 | Yes (300s) |
| `get_similar_predictions` | 766-821 | No |
| `get_predictions_with_outcomes` | 824-915 | No |
| `get_asset_price_history` | 1269-1309 | No |
| `get_sparkline_prices` | 1313-1391 | Yes (300s) |
| `get_asset_predictions` | 1394-1452 | No |
| `get_asset_stats` | 1456-1576 | Yes (300s) |
| `get_related_assets` | 1579-1631 | No |

### `data/insight_queries.py` (lines 2568-2865)

Dynamic insight card generation.

| Function | Current Line | Cached? |
|---|---|---|
| `get_dynamic_insights` | 2568-2865 | Yes (300s) |

### `data/__init__.py` (new)

Re-exports every public symbol for backward compatibility.

---

## Detailed Implementation Plan

### Step 1: Create the `data/` package directory

Convert the file `shitty_ui/data.py` into a package `shitty_ui/data/`. Since a file and directory cannot coexist at the same path, first rename the old file, then create the package.

```bash
# From the repo root:
cd shitty_ui
git mv data.py data_legacy.py
mkdir data
```

After all new files are created and verified, delete `data_legacy.py`:
```bash
git rm shitty_ui/data_legacy.py
```

### Step 2: Create `shitty_ui/data/base.py`

This module contains all shared infrastructure that other modules import.

**Full content of `shitty_ui/data/base.py`:**

```python
"""
Shared infrastructure for the data query layer.

Contains the database query executor, TTL cache decorator, logger,
and table constants used by all domain query modules.
"""

import time
import pandas as pd
from datetime import datetime, timedelta
from functools import wraps
from sqlalchemy import text
from typing import List, Dict, Any, Optional, Callable

from shit.db.sync_session import SessionLocal, DATABASE_URL
from shit.logging import get_service_logger

logger = get_service_logger("dashboard_data")

# Table reference -- will be changed to "signals" after full migration
SIGNALS_TABLE = "truth_social_shitposts"


# Simple TTL cache decorator
def ttl_cache(ttl_seconds: int = 300):
    """
    Cache function results for a given number of seconds.
    Uses function arguments as cache key.

    Args:
        ttl_seconds: How long to cache results (default 5 minutes)
    """

    def decorator(func: Callable) -> Callable:
        cache: Dict[tuple, tuple] = {}

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

        wrapper.clear_cache = clear_cache  # type: ignore
        return wrapper

    return decorator


def execute_query(query, params=None):
    """Execute query using appropriate session type."""
    try:
        with SessionLocal() as session:
            result = session.execute(query, params or {})
            return result.fetchall(), result.keys()
    except Exception as e:
        logger.error(f"Database query error: {e}")
        logger.debug("Query failed against configured database")
        raise
```

**Verification**: This file is a verbatim copy of lines 1-72 of the current `data.py`. The only change is the module docstring. No logic changes.

### Step 3: Create `shitty_ui/data/signal_queries.py`

This module contains all signal/post loading and feed functions.

**File header and imports:**

```python
"""
Signal and post query functions.

Handles loading, filtering, and paginating Truth Social posts and their
associated predictions. Includes the signal feed, unified feed, CSV export,
and price+signal combination queries.
"""

import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import text
from typing import List, Dict, Any, Optional

from data.base import (
    execute_query,
    logger,
    DATABASE_URL,
    SIGNALS_TABLE,
)
```

**Functions to include** (copy verbatim from current `data.py`):

1. `load_recent_posts` -- lines 75-108
2. `load_filtered_posts` -- lines 111-218
3. `get_recent_signals` -- lines 318-378
4. `get_active_signals` -- lines 1634-1690
5. `get_active_signals_with_fallback` -- lines 1772-1805
6. `get_unified_feed` -- lines 1693-1769
7. `get_weekly_signal_count` -- lines 1808-1830
8. `get_signal_feed` -- lines 2103-2206
9. `get_signal_feed_count` -- lines 2209-2274
10. `get_new_signals_since` -- lines 2277-2310
11. `get_signal_feed_csv` -- lines 2313-2377
12. `get_price_with_signals` -- lines 2421-2511
13. `get_multi_asset_signals` -- lines 2514-2560

**Copy rules**: Every function body is copied verbatim. No logic changes. No query changes. The only change is the import section at the top.

**Note on `get_signal_feed_csv`**: This function calls `get_signal_feed()` internally (line 2329). Since both are in the same module after the split, the call resolves locally. No import change needed.

**Note on `get_active_signals_with_fallback`**: This function calls `get_active_signals()` internally (lines 1785-1801). Both are in the same module. No import change needed.

### Step 4: Create `shitty_ui/data/performance_queries.py`

This module contains all KPI, accuracy, and performance metric functions.

**File header and imports:**

```python
"""
Performance and KPI query functions.

Handles dashboard KPIs, accuracy breakdowns, cumulative P&L, rolling metrics,
win/loss streaks, confidence calibration, backtesting simulation, and
aggregate statistics.
"""

import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import text
from typing import List, Dict, Any, Optional

from data.base import (
    execute_query,
    ttl_cache,
    logger,
    DATABASE_URL,
)
```

**Functions to include** (copy verbatim from current `data.py`):

1. `get_available_assets` -- lines 222-264 (has `@ttl_cache(ttl_seconds=600)`)
2. `get_prediction_stats` -- lines 268-315 (has `@ttl_cache(ttl_seconds=300)`)
3. `get_performance_metrics` -- lines 382-440 (has `@ttl_cache(ttl_seconds=300)`)
4. `get_dashboard_kpis` -- lines 444-504 (has `@ttl_cache(ttl_seconds=300)`)
5. `get_dashboard_kpis_with_fallback` -- lines 507-531
6. `get_accuracy_by_confidence` -- lines 535-587 (has `@ttl_cache(ttl_seconds=300)`)
7. `get_accuracy_by_asset` -- lines 591-632 (has `@ttl_cache(ttl_seconds=300)`)
8. `get_sentiment_distribution` -- lines 919-954 (has `@ttl_cache(ttl_seconds=300)`)
9. `get_active_assets_from_db` -- lines 958-974 (has `@ttl_cache(ttl_seconds=600)`)
10. `get_top_predicted_asset` -- lines 978-1003 (has `@ttl_cache(ttl_seconds=600)`)
11. `get_cumulative_pnl` -- lines 1011-1049
12. `get_rolling_accuracy` -- lines 1052-1099
13. `get_win_loss_streaks` -- lines 1102-1154
14. `get_confidence_calibration` -- lines 1157-1199
15. `get_monthly_performance` -- lines 1202-1237
16. `get_high_confidence_metrics` -- lines 1834-1877 (has `@ttl_cache(ttl_seconds=300)`)
17. `get_empty_state_context` -- lines 1881-1916 (has `@ttl_cache(ttl_seconds=300)`)
18. `get_best_performing_asset` -- lines 1920-1966 (has `@ttl_cache(ttl_seconds=300)`)
19. `get_accuracy_over_time` -- lines 1969-2008
20. `get_backtest_simulation` -- lines 2012-2095 (has `@ttl_cache(ttl_seconds=300)`)
21. `get_sentiment_accuracy` -- lines 2380-2418

**Note on `get_dashboard_kpis_with_fallback`**: This calls `get_dashboard_kpis()` internally (lines 519, 528). Both are in the same module. No import change needed.

### Step 5: Create `shitty_ui/data/asset_queries.py`

This module contains asset-specific queries for the screener and asset detail pages.

**File header and imports:**

```python
"""
Asset query functions.

Handles asset screener data, sparkline price loading, per-asset predictions,
asset statistics, price history, related assets, and predictions with outcomes.
"""

import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import text
from typing import List, Dict, Any, Optional

from data.base import (
    execute_query,
    ttl_cache,
    logger,
)
```

**Functions to include** (copy verbatim from current `data.py`):

1. `get_asset_screener_data` -- lines 636-707 (has `@ttl_cache(ttl_seconds=300)`)
2. `get_screener_sparkline_prices` -- lines 711-763 (has `@ttl_cache(ttl_seconds=300)`)
3. `get_similar_predictions` -- lines 766-821
4. `get_predictions_with_outcomes` -- lines 824-915
5. `get_asset_price_history` -- lines 1269-1309
6. `get_sparkline_prices` -- lines 1313-1391 (has `@ttl_cache(ttl_seconds=300)`)
7. `get_asset_predictions` -- lines 1394-1452
8. `get_asset_stats` -- lines 1456-1576 (has `@ttl_cache(ttl_seconds=300)`)
9. `get_related_assets` -- lines 1579-1631

### Step 6: Create `shitty_ui/data/insight_queries.py`

This module contains the dynamic insight card generation.

**File header and imports:**

```python
"""
Dynamic insight query functions.

Generates a pool of insight candidates for dashboard cards by running
multiple targeted queries and formatting results with personality-driven copy.
"""

import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import text
from typing import List, Dict, Any

from data.base import (
    execute_query,
    ttl_cache,
    logger,
)
```

**Functions to include** (copy verbatim from current `data.py`):

1. `get_dynamic_insights` -- lines 2568-2865 (has `@ttl_cache(ttl_seconds=300)`)

### Step 7: Create `shitty_ui/data/__init__.py`

This is the **critical** backward-compatibility layer. Every public function must be re-exported here so that all existing `from data import X` statements continue to work.

**Full content of `shitty_ui/data/__init__.py`:**

```python
"""
Database access layer for Shitty UI Dashboard.

This package re-exports all query functions for backward compatibility.
All existing `from data import X` statements continue to work unchanged.

Internal structure:
    data/base.py              -- execute_query, ttl_cache, logger
    data/signal_queries.py    -- Signal loading, feed, filtering
    data/performance_queries.py -- KPIs, accuracy, P&L, streaks
    data/asset_queries.py     -- Screener, sparklines, asset stats
    data/insight_queries.py   -- Dynamic insight cards
"""

# --- Base infrastructure ---
from data.base import (  # noqa: F401
    execute_query,
    ttl_cache,
    logger,
    SIGNALS_TABLE,
    DATABASE_URL,
)

# --- Signal queries ---
from data.signal_queries import (  # noqa: F401
    load_recent_posts,
    load_filtered_posts,
    get_recent_signals,
    get_active_signals,
    get_active_signals_with_fallback,
    get_unified_feed,
    get_weekly_signal_count,
    get_signal_feed,
    get_signal_feed_count,
    get_new_signals_since,
    get_signal_feed_csv,
    get_price_with_signals,
    get_multi_asset_signals,
)

# --- Performance queries ---
from data.performance_queries import (  # noqa: F401
    get_available_assets,
    get_prediction_stats,
    get_performance_metrics,
    get_dashboard_kpis,
    get_dashboard_kpis_with_fallback,
    get_accuracy_by_confidence,
    get_accuracy_by_asset,
    get_sentiment_distribution,
    get_active_assets_from_db,
    get_top_predicted_asset,
    get_cumulative_pnl,
    get_rolling_accuracy,
    get_win_loss_streaks,
    get_confidence_calibration,
    get_monthly_performance,
    get_high_confidence_metrics,
    get_empty_state_context,
    get_best_performing_asset,
    get_accuracy_over_time,
    get_backtest_simulation,
    get_sentiment_accuracy,
)

# --- Asset queries ---
from data.asset_queries import (  # noqa: F401
    get_asset_screener_data,
    get_screener_sparkline_prices,
    get_similar_predictions,
    get_predictions_with_outcomes,
    get_asset_price_history,
    get_sparkline_prices,
    get_asset_predictions,
    get_asset_stats,
    get_related_assets,
)

# --- Insight queries ---
from data.insight_queries import (  # noqa: F401
    get_dynamic_insights,
)


def clear_all_caches() -> None:
    """Clear all data layer caches. Call when forcing a full refresh.

    Wires up clear_cache() calls for every @ttl_cache-decorated function
    across all submodules.
    """
    # Performance queries (11 cached functions)
    get_prediction_stats.clear_cache()  # type: ignore
    get_performance_metrics.clear_cache()  # type: ignore
    get_dashboard_kpis.clear_cache()  # type: ignore
    get_accuracy_by_confidence.clear_cache()  # type: ignore
    get_accuracy_by_asset.clear_cache()  # type: ignore
    get_sentiment_distribution.clear_cache()  # type: ignore
    get_active_assets_from_db.clear_cache()  # type: ignore
    get_available_assets.clear_cache()  # type: ignore
    get_high_confidence_metrics.clear_cache()  # type: ignore
    get_best_performing_asset.clear_cache()  # type: ignore
    get_backtest_simulation.clear_cache()  # type: ignore
    get_top_predicted_asset.clear_cache()  # type: ignore
    get_empty_state_context.clear_cache()  # type: ignore

    # Asset queries (3 cached functions)
    get_asset_stats.clear_cache()  # type: ignore
    get_asset_screener_data.clear_cache()  # type: ignore
    get_screener_sparkline_prices.clear_cache()  # type: ignore
    get_sparkline_prices.clear_cache()  # type: ignore

    # Insight queries (1 cached function)
    get_dynamic_insights.clear_cache()  # type: ignore


__all__ = [
    # Base
    "execute_query",
    "ttl_cache",
    "logger",
    "SIGNALS_TABLE",
    "DATABASE_URL",
    "clear_all_caches",
    # Signal queries
    "load_recent_posts",
    "load_filtered_posts",
    "get_recent_signals",
    "get_active_signals",
    "get_active_signals_with_fallback",
    "get_unified_feed",
    "get_weekly_signal_count",
    "get_signal_feed",
    "get_signal_feed_count",
    "get_new_signals_since",
    "get_signal_feed_csv",
    "get_price_with_signals",
    "get_multi_asset_signals",
    # Performance queries
    "get_available_assets",
    "get_prediction_stats",
    "get_performance_metrics",
    "get_dashboard_kpis",
    "get_dashboard_kpis_with_fallback",
    "get_accuracy_by_confidence",
    "get_accuracy_by_asset",
    "get_sentiment_distribution",
    "get_active_assets_from_db",
    "get_top_predicted_asset",
    "get_cumulative_pnl",
    "get_rolling_accuracy",
    "get_win_loss_streaks",
    "get_confidence_calibration",
    "get_monthly_performance",
    "get_high_confidence_metrics",
    "get_empty_state_context",
    "get_best_performing_asset",
    "get_accuracy_over_time",
    "get_backtest_simulation",
    "get_sentiment_accuracy",
    # Asset queries
    "get_asset_screener_data",
    "get_screener_sparkline_prices",
    "get_similar_predictions",
    "get_predictions_with_outcomes",
    "get_asset_price_history",
    "get_sparkline_prices",
    "get_asset_predictions",
    "get_asset_stats",
    "get_related_assets",
    # Insight queries
    "get_dynamic_insights",
]
```

### Step 8: Verify `DATABASE_URL` import in `base.py`

The current `data.py` line 14 imports `DATABASE_URL` from `shit.db.sync_session`:

```python
from shit.db.sync_session import SessionLocal, DATABASE_URL
```

This is used in two places:
- `execute_query()` in base.py (indirectly via `SessionLocal`)
- `get_available_assets()` in performance_queries.py (line 228: `if DATABASE_URL.startswith("sqlite"):`)
- `get_prediction_stats()` in performance_queries.py (line 270: `if DATABASE_URL.startswith("sqlite"):`)

Both `base.py` and `performance_queries.py` need access to `DATABASE_URL`. The solution:
- `base.py` exports `DATABASE_URL` (it imports it from `shit.db.sync_session`)
- `performance_queries.py` imports `DATABASE_URL` from `data.base`

This is already reflected in the import sections above.

### Step 9: Verify no application or test files need modification

**Application files** -- all use `from data import X`:

| File | Current Import | Change Needed? |
|---|---|---|
| `shitty_ui/layout.py:43` | `from data import (get_recent_signals, ...)` | **No** -- `data/__init__.py` re-exports |
| `shitty_ui/pages/dashboard.py:30` | `from data import (get_asset_screener_data, ...)` | **No** -- `data/__init__.py` re-exports |
| `shitty_ui/pages/assets.py:19` | `from data import (get_asset_price_history, ...)` | **No** -- `data/__init__.py` re-exports |
| `shitty_ui/callbacks/alerts.py:9` | `from data import get_available_assets` | **No** -- `data/__init__.py` re-exports |

**Test files** -- all use `from data import X` and `@patch("data.execute_query")`:

| File | Pattern | Change Needed? |
|---|---|---|
| `shit_tests/shitty_ui/test_data.py` | `from data import get_xxx` | **No** -- `data/__init__.py` re-exports |
| `shit_tests/shitty_ui/test_data.py` | `@patch("data.execute_query")` | **No** -- see explanation below |
| `shit_tests/shitty_ui/test_data_screener.py` | `from data import get_asset_screener_data` | **No** -- re-exported |
| `shit_tests/shitty_ui/test_data_screener.py` | `@patch("data.execute_query")` | **No** -- see explanation below |
| `shit_tests/shitty_ui/test_insights.py` | `from data import get_dynamic_insights` | **No** -- re-exported |
| `shit_tests/shitty_ui/test_insights.py` | `@patch("data.execute_query")` | **No** -- see explanation below |
| `shit_tests/shitty_ui/test_layout.py` | `@patch("data.get_prediction_stats")` | **No** -- see explanation below |

**Why `@patch("data.execute_query")` continues to work:**

When Python encounters `from data import execute_query` in `data/__init__.py`, it creates a binding `data.execute_query` that points to the function object. When a submodule like `data.signal_queries` does `from data.base import execute_query`, it gets a direct reference to the same function object.

However, `@patch("data.execute_query")` replaces the `execute_query` attribute on the `data` module (i.e., `data/__init__.py`). The submodules (`signal_queries.py`, etc.) import `execute_query` from `data.base`, NOT from `data/__init__.py`. This means the submodule's local reference is **not** affected by patching `data.execute_query`.

**This is a critical issue.** The existing tests use `@patch("data.execute_query")`, which patches the reference in `data/__init__.py`. But the actual call sites in submodules import from `data.base`. The patch would not intercept those calls.

**Solution**: Each submodule must import `execute_query` from `data.base`, and the test patches must target where the function is **looked up**, not where it is defined. Since the submodules use `from data.base import execute_query`, the function is bound as a local name in each submodule. To make `@patch("data.execute_query")` work, we need the submodules to look up `execute_query` through the `data` package at call time, OR we patch at the submodule level.

The **simplest solution** that requires **zero test changes** is:

**Each submodule must NOT use `from data.base import execute_query`. Instead, import the `base` module and call `base.execute_query()`.**

Wait -- that would change every function body. A simpler approach:

**Each submodule imports `execute_query` as a module-level name from `data.base`. The patch must target `data.signal_queries.execute_query`, `data.performance_queries.execute_query`, etc. But the tests use `@patch("data.execute_query")`.**

The cleanest zero-change solution is to have the submodules import `execute_query` from the package itself:

```python
# In data/signal_queries.py:
from data.base import logger, DATABASE_URL, SIGNALS_TABLE
import data  # for execute_query at call time
```

No -- this creates circular imports (`data/__init__.py` imports `signal_queries`, which imports `data`).

**Correct solution**: Use `patch.object` or change the import strategy. Since we need zero test changes, the right approach is:

**Have each submodule use a module-level import of `data.base` and access `execute_query` as an attribute at call time:**

```python
# In data/signal_queries.py:
from data import base as _base

# In each function:
rows, columns = _base.execute_query(query, params)
```

This way, `@patch("data.base.execute_query")` would work. But the tests use `@patch("data.execute_query")`, not `@patch("data.base.execute_query")`.

**Final correct solution**: We make `execute_query` a thin wrapper in `__init__.py` that delegates to `base.execute_query`. No -- that defeats the purpose.

**The real answer**: After the refactoring, `@patch("data.execute_query")` patches the attribute on the `data` package's `__init__.py` module. The submodules import `execute_query` directly from `data.base` at import time, binding it as a local name. So the patch does NOT affect them.

**However**, the tests import functions like `from data import get_prediction_stats` and then call them. The function `get_prediction_stats` lives in `data.performance_queries` and has its own local binding to `execute_query` from `data.base`. Patching `data.execute_query` does not affect `data.performance_queries.execute_query`.

**The fix is straightforward**: Each submodule should import `execute_query` from the `data` package (not from `data.base`), but that creates a circular import.

**The ACTUAL fix**: Add a late-binding import inside `__init__.py` that patches the submodule attributes, OR use the pattern where submodules don't import `execute_query` at all but instead access it through a shared module reference.

After careful analysis, the **simplest solution that requires zero changes to 3,260 lines of tests** is:

**Submodules import `base` as a module and call `base.execute_query()` in every function body.** This means every call site changes from:

```python
rows, columns = execute_query(query, params)
```

to:

```python
rows, columns = base.execute_query(query, params)
```

And we patch it as `@patch("data.base.execute_query")`. But this STILL requires changing 100+ test decorators from `@patch("data.execute_query")` to `@patch("data.base.execute_query")`.

**The TRULY zero-change solution**: Keep `execute_query` in `__init__.py` directly (not imported from a submodule). The submodules import it from the package.

Wait -- that circular import issue. Let's think again...

Actually, there is NO circular import if the submodules import from `data.base` and `data/__init__.py` imports from the submodules. The issue is only with patching.

**THE DEFINITIVE SOLUTION:**

Make each submodule import `execute_query` through a **late-binding module reference**. Specifically, each submodule does:

```python
import data.base as _base
```

And every call to `execute_query` becomes `_base.execute_query(...)`.

Then in `__init__.py`, we re-export `execute_query` from `base`:

```python
from data.base import execute_query  # noqa: F401
```

And **add one line** to `__init__.py` that patches the submodule references after import:

No. This is getting too complicated. Let's use the simplest correct approach:

**SOLUTION: Keep `execute_query` defined directly in `__init__.py` and have submodules import it from the parent package using a deferred import pattern. BUT circular imports make this impossible.**

**FINAL DEFINITIVE SOLUTION:**

The correct approach that requires **zero changes to test files** is:

1. Define `execute_query` and `logger` in `data/base.py`
2. Each submodule does `from data.base import execute_query, logger` etc.
3. `data/__init__.py` re-exports everything
4. **Add a monkeypatch** at the bottom of `__init__.py` that replaces each submodule's local `execute_query` binding with the `__init__` module's own binding:

```python
# At the bottom of __init__.py, after all imports:
import data.signal_queries as _sq
import data.performance_queries as _pq
import data.asset_queries as _aq
import data.insight_queries as _iq

# Wire up so @patch("data.execute_query") affects all submodules
for _mod in (_sq, _pq, _aq, _iq):
    _mod.execute_query = execute_query
    _mod.logger = logger
```

**Why this works**: When a test does `@patch("data.execute_query")`, it replaces `data.execute_query` (in `__init__.py`) with a mock. But the submodules have their own local binding. The monkeypatch at the bottom of `__init__.py` sets each submodule's `execute_query` to be the **same object** as `data.execute_query`. When `@patch("data.execute_query")` runs, it replaces `sys.modules["data"].execute_query` with a mock. But the submodule still holds the original reference.

**This still doesn't work** because `@patch` replaces the attribute on the module object, but the submodule's local `execute_query` name is a separate binding.

OK, let me re-examine the actual test pattern:

```python
@patch("data.execute_query")
def test_returns_stats_dict(self, mock_execute):
    from data import get_prediction_stats
    # ...
    result = get_prediction_stats()
```

`@patch("data.execute_query")` temporarily sets `sys.modules["data"].execute_query = Mock()`. When `get_prediction_stats()` runs, it calls `execute_query(query, params)`. The question is: which `execute_query` does it resolve to?

If `get_prediction_stats` is defined in `data/performance_queries.py` with `from data.base import execute_query`, then its local `execute_query` binding was set at import time to the real function. Patching `data.execute_query` does NOT affect it.

**THE REAL FIX**: Each submodule should access `execute_query` through a module attribute lookup, not a local binding. The standard way:

```python
# In data/performance_queries.py:
import data.base as _base

def get_prediction_stats():
    # ...
    rows, columns = _base.execute_query(query, params)
```

And tests patch `data.base.execute_query`. But tests use `@patch("data.execute_query")`.

**OK. The only way to make `@patch("data.execute_query")` work without changing tests is to keep `execute_query` as a function defined directly in `data/__init__.py` that the submodules call.** Circular import? Let's check:

- `data/__init__.py` defines `execute_query` at the top, BEFORE importing submodules
- Submodules import `execute_query` from the `data` package

```python
# data/__init__.py (TOP of file):
from data.base import execute_query, ttl_cache, logger, SIGNALS_TABLE, DATABASE_URL

# Then import submodules (which import from data package):
from data.signal_queries import (...)
```

```python
# data/signal_queries.py:
from data import execute_query, logger
```

**Circular import check**: When Python processes `data/__init__.py`:
1. It starts executing `__init__.py`
2. Line 1: `from data.base import execute_query` -- this works because `data.base` has no dependency on `data`
3. At this point, `data.execute_query` is defined in the partially-initialized `data` module
4. Next lines: `from data.signal_queries import (...)` -- this triggers loading `signal_queries.py`
5. `signal_queries.py` line 1: `from data import execute_query` -- at this point `data` is partially initialized, but `execute_query` IS already defined (from step 2). **This works.**

**This is the solution.** Python handles partial module initialization correctly as long as the names exist at the point of the circular import. Since `__init__.py` imports from `base.py` first (defining all shared names), and THEN imports from submodules, the submodules can safely `from data import execute_query`.

**And `@patch("data.execute_query")` works** because the submodule's `execute_query` is a local binding that was set to `data.execute_query` at import time. Wait -- no. `from data import execute_query` creates a local binding `execute_query` that is a direct reference to the function. `@patch("data.execute_query")` replaces the attribute on the `data` module, but doesn't affect existing local bindings.

**This is fundamentally a Python binding issue.** There is no magic fix without either:
1. Changing all test patches from `@patch("data.execute_query")` to `@patch("data.base.execute_query")` -- changes ~130 test decorators
2. Having submodules use `import data.base as _base; _base.execute_query()` pattern and patching `data.base.execute_query` -- same issue with test decorators
3. Having submodules NOT import `execute_query` locally but access it through `sys.modules` -- ugly and slow

**Actually, option 3 has a clean variant:**

```python
# In data/signal_queries.py:
import data.base as _base

def load_recent_posts(limit: int = 100):
    # ...
    rows, columns = _base.execute_query(query, {"limit": limit})
```

With `@patch("data.base.execute_query")`. But tests use `@patch("data.execute_query")`.

**THE PRACTICAL DECISION:**

Given the constraint of zero test changes across 3,260 lines, there are two viable approaches:

**Approach A (Recommended): Global find-replace in test files**

Change `@patch("data.execute_query")` to `@patch("data.base.execute_query")` across all test files. This is a mechanical find-replace -- ~130 occurrences across 3 files. No logic changes. Submodules import from `data.base`.

Similarly, change `@patch("data.get_xxx")` to the correct submodule path. But wait -- `@patch("data.get_prediction_stats")` patches the attribute on the `data` module. If `get_prediction_stats` was imported into `data/__init__.py` via `from data.performance_queries import get_prediction_stats`, then `data.get_prediction_stats` IS the same object. When we patch it with `@patch("data.get_prediction_stats")`, we replace the attribute on the `data` module. But the code that CALLS `get_prediction_stats` imports it from `data` package too (e.g., `layout.py` does `from data import get_prediction_stats`). Since `layout.py` binds it locally at import time, the patch doesn't affect layout.py's local binding either.

But **the tests** import the function inside the test method body:

```python
@patch("data.execute_query")
def test_returns_stats_dict(self, mock_execute):
    from data import get_prediction_stats
    result = get_prediction_stats()
```

The function `get_prediction_stats` was imported from `data`, which got it from `data.performance_queries`. The function's own code calls `execute_query`, which was bound at import time from `data.base`. The mock replaces `data.execute_query` but NOT `data.performance_queries.execute_query` and NOT `data.base.execute_query`.

**Approach B (Simplest, truly zero test changes): Keep everything in `__init__.py` but organize with imports**

Actually wait. What if the submodules don't import `execute_query` at all, but instead, we define the functions in submodules that accept `execute_query` as a parameter? No, that's insane.

**Approach C: Property-based module access**

What if each submodule accesses `execute_query` through the `data` package at runtime? We can avoid the circular import using lazy access:

```python
# data/signal_queries.py:
import sys

def load_recent_posts(limit: int = 100):
    execute_query = sys.modules["data"].execute_query
    # ...
```

This is ugly but works perfectly -- `@patch("data.execute_query")` would be intercepted because we look up `execute_query` on the `data` module at call time, not at import time.

**But this is fragile and ugly.** Let me think about this differently.

**Approach D (CORRECT ANSWER): Use `from data.base import execute_query` in submodules, and fix the test patches**

The test decorators need to patch where the function is **used**, not where it's **defined**. The correct patch target for tests of functions in `performance_queries.py` is:

```python
@patch("data.performance_queries.execute_query")
```

But the tests currently use `@patch("data.execute_query")`.

**The implementer MUST update the test patches.** This is a mechanical find-replace but needs to be done per-submodule, targeting the correct submodule path based on which function is being tested.

However, there is a MUCH simpler approach that I overlooked:

**Approach E: Global `execute_query` via module-level reference in submodules**

```python
# data/signal_queries.py:
import data.base as _base

def load_recent_posts(limit: int = 100):
    rows, columns = _base.execute_query(query, {"limit": limit})
```

Test patches: `@patch("data.base.execute_query")` -- one global find-replace.

Every test file that has `@patch("data.execute_query")` changes to `@patch("data.base.execute_query")`. This is a single find-replace across the test files. The string `"data.execute_query"` appears only in `@patch` decorators.

For `@patch("data.get_prediction_stats")` and similar in `test_layout.py`, these patch the data package's attribute. Since `test_layout.py` tests the LAYOUT module (which imports `from data import get_prediction_stats`), the patch needs to target where the function is used. Currently `@patch("data.get_prediction_stats")` patches the `data` module's attribute. When layout.py does `from data import get_prediction_stats` at import time, it gets a local binding. The mock doesn't affect it.

**Wait -- how do the existing tests work at ALL with `@patch("data.get_prediction_stats")`?**

Looking at `test_layout.py:146`:
```python
@patch("data.get_prediction_stats")
```

This works because `layout.py` uses `from data import get_prediction_stats` and `get_prediction_stats` is accessed via the `data` module at the module level. When `@patch` replaces `data.get_prediction_stats`, and the test imports layout.py AFTER the patch is applied... Actually, layout.py is already imported. The `from data import get_prediction_stats` already ran. So the local binding in layout.py should be unaffected by the patch.

But the tests clearly WORK today. Let me re-examine... The `test_layout.py` tests likely work because the callbacks are called indirectly through Dash, which re-resolves function references. Or because the layout module hasn't been imported yet when the patch is applied.

Actually, looking more carefully: `test_layout.py` tests the layout callbacks. The callbacks are registered with Dash and when invoked, they call functions that were imported at module level. If `layout.py` was imported after the patch... but in a test suite, module imports happen at import time.

I think the tests work because of the `sys.path` manipulation in the test conftest -- `shitty_ui` is added to `sys.path`, and when the test does `@patch("data.get_prediction_stats")`, it patches the `data` module. The Dash callbacks in layout.py access `get_prediction_stats` through the local binding, which was set at import time. But the patch replaces the module attribute BEFORE layout.py imports it (because the patch context manager runs before the test body).

Actually, `@patch` as a decorator replaces the attribute for the duration of the test method, then restores it. The layout module is imported once. The local binding in layout.py is set once. Patches after that don't affect local bindings.

**The key insight**: In the test files like `test_data.py`, the import happens INSIDE the test method:

```python
@patch("data.execute_query")
def test_returns_stats_dict(self, mock_execute):
    from data import get_prediction_stats
    result = get_prediction_stats()
```

The `from data import get_prediction_stats` runs inside the method, while the patch is active. It imports `get_prediction_stats` from the `data` module, getting the REAL function (since `get_prediction_stats` is not patched, only `execute_query` is). When `get_prediction_stats()` runs, it calls `execute_query` which was bound at the time `data.py` (or `performance_queries.py`) was imported -- i.e., the REAL `execute_query`.

**But the tests pass today!** How? Because today, `data.py` is a single module. When `get_prediction_stats` is defined in `data.py`, the `execute_query` it calls is the same `execute_query` from the same module. `@patch("data.execute_query")` replaces `data.execute_query` on the module. When `get_prediction_stats` calls `execute_query()`, it resolves the name `execute_query` in its enclosing module's namespace -- which IS `data`. So it finds the patched version.

**THIS is why the tests work today**: In a single-module file, function calls to other functions in the same module go through the module's namespace at call time. Python resolves `execute_query` by looking it up in the function's `__globals__` dict, which is the module's `__dict__`. So `@patch("data.execute_query")` replaces the entry in `data.__dict__["execute_query"]`, and when `get_prediction_stats` calls `execute_query()`, it looks up `execute_query` in `data.__dict__` and finds the mock.

**After the split**, `get_prediction_stats` is defined in `data/performance_queries.py`. Its `__globals__` is `data.performance_queries.__dict__`. When it calls `execute_query()`, Python looks up `execute_query` in `data.performance_queries.__dict__`. If `performance_queries.py` does `from data.base import execute_query`, then `data.performance_queries.__dict__["execute_query"]` = the real function. `@patch("data.execute_query")` changes `data.__dict__["execute_query"]` but NOT `data.performance_queries.__dict__["execute_query"]`. So the mock is NOT used. **Tests break.**

**THE FIX**: Patch at the submodule level: `@patch("data.performance_queries.execute_query")`. Or, make the submodule access `execute_query` through a module reference that can be patched.

**Given this analysis, the correct implementation plan is:**

**Strategy: Have submodules access `execute_query` through `data.base` module attribute lookup (not local binding), and do a global find-replace on test patches.**

Each submodule does:
```python
from data import base as _base
# Access as: _base.execute_query(query, params)
```

Tests change from `@patch("data.execute_query")` to `@patch("data.base.execute_query")`.

**Alternatively (and this is simpler for the function bodies):**

Each submodule does:
```python
from data.base import execute_query, logger, ttl_cache
```

And tests change from `@patch("data.execute_query")` to `@patch("data.<submodule>.execute_query")`. But this requires knowing which submodule each test targets.

**The simplest approach for the implementer:**

1. Submodules use `from data.base import execute_query, logger, ttl_cache` (clean imports)
2. **Test patches change from `@patch("data.execute_query")` to `@patch("data.base.execute_query")`** -- a single global find-replace across all test files
3. Test patches like `@patch("data.get_prediction_stats")` change to `@patch("data.performance_queries.get_prediction_stats")` -- requires knowing the target module but is deterministic from the function-to-module mapping
4. Test `from data import X` statements remain unchanged (re-exports work)

**Wait -- I need to check `@patch("data.get_signal_feed")` and similar.** These appear in `test_data.py`:

```python
@patch("data.get_signal_feed")
def test_csv_export_basic(self, mock_feed):
    from data import get_signal_feed_csv
    # ...
```

`get_signal_feed_csv` calls `get_signal_feed` internally. Both are in `signal_queries.py`. After the split, `get_signal_feed_csv`'s `__globals__` is `data.signal_queries.__dict__`. When it calls `get_signal_feed()`, it looks up in `data.signal_queries.__dict__`. If `get_signal_feed` is defined in the same module, the lookup finds it locally. `@patch("data.get_signal_feed")` patches `data.__dict__`, not `data.signal_queries.__dict__`. So the test BREAKS.

**Fix**: `@patch("data.signal_queries.get_signal_feed")`

And for `@patch("data.get_dashboard_kpis")` (used in tests of `get_dashboard_kpis_with_fallback`):
**Fix**: `@patch("data.performance_queries.get_dashboard_kpis")`

And for `@patch("data.get_active_signals")` (used in tests of `get_active_signals_with_fallback`):
**Fix**: `@patch("data.signal_queries.get_active_signals")`

---

OK. With this full analysis complete, let me now document the comprehensive plan clearly.

---

## Revised Step 9: Required Test File Changes

### 9a. Patch target changes for `execute_query`

Every `@patch("data.execute_query")` in every test file must change to the correct submodule path. Since almost all functions in a single test file call `execute_query` from the same submodule, and the tests import the function under test from `data` (which still works), the patch target must change.

**Global replacement** across all test files:

```
@patch("data.execute_query")  -->  @patch("data.base.execute_query")
```

This works because all submodules import `execute_query` from `data.base`, and `@patch("data.base.execute_query")` patches the `execute_query` attribute on the `data.base` module object -- which IS the `__globals__` lookup target for every submodule.

**Wait -- is this correct?** If `performance_queries.py` does `from data.base import execute_query`, then `execute_query` is a LOCAL NAME in `performance_queries`'s namespace. `@patch("data.base.execute_query")` replaces `data.base.__dict__["execute_query"]` but NOT `data.performance_queries.__dict__["execute_query"]`.

**No, this still doesn't work.** `from X import Y` creates a local binding. Patching `X.Y` doesn't affect the local binding.

**THE CORRECT APPROACH** that actually works for `execute_query`:

Each submodule must use `import data.base as _base` and access as `_base.execute_query()`. Then `@patch("data.base.execute_query")` works because it patches the attribute on the `_base` module object, and the submodule does attribute lookup at call time.

```python
# data/signal_queries.py:
import data.base as _base
from data.base import ttl_cache, SIGNALS_TABLE, DATABASE_URL  # These don't need patching

def load_recent_posts(limit: int = 100):
    # ...
    rows, columns = _base.execute_query(query, {"limit": limit})
    # ...
```

And `logger` too -- since `logger` doesn't need patching (it's never mocked), it can stay as a local import:

```python
import data.base as _base
from data.base import ttl_cache, SIGNALS_TABLE, DATABASE_URL, logger
```

Only `execute_query` needs the module-level attribute lookup pattern because it's the one that gets patched.

**Test change**: Global find-replace:
```
@patch("data.execute_query")  -->  @patch("data.base.execute_query")
```

**Affected files and approximate occurrence counts:**
- `shit_tests/shitty_ui/test_data.py` -- ~120 occurrences
- `shit_tests/shitty_ui/test_data_screener.py` -- ~11 occurrences
- `shit_tests/shitty_ui/test_insights.py` -- ~7 occurrences

### 9b. Patch target changes for inter-function mocking

Some tests mock a data function to test another data function that calls it. These need submodule-aware patch targets:

**In `test_data.py`:**

| Current Patch Target | Used To Test | New Patch Target |
|---|---|---|
| `@patch("data.get_signal_feed")` | `get_signal_feed_csv` tests | `@patch("data.signal_queries.get_signal_feed")` |
| `@patch("data.get_dashboard_kpis")` | `get_dashboard_kpis_with_fallback` tests | `@patch("data.performance_queries.get_dashboard_kpis")` |
| `@patch("data.get_active_signals")` | `get_active_signals_with_fallback` tests | `@patch("data.signal_queries.get_active_signals")` |

**In `test_layout.py`:**

The `@patch("data.get_prediction_stats")` decorators patch the function that layout.py uses. Since layout.py does `from data import get_prediction_stats`, the local binding in layout.py is NOT affected by patching `data.get_prediction_stats`. This means these patches DON'T ACTUALLY WORK as expected... unless layout.py re-imports each time. Let me check:

Actually, the Dash callbacks in layout.py call these functions directly from their local scope. The `from data import get_prediction_stats` at the top of layout.py creates a local binding. Patching `data.get_prediction_stats` does NOT affect layout.py's local binding.

But the `test_layout.py` tests appear to work today. This must mean that either:
1. layout.py has not been imported yet when the test starts, so the first import during the test picks up the mocked version
2. The callbacks access functions through some re-resolution mechanism

Looking at `test_layout.py`, the tests likely create the Dash app within the test, which triggers the import. If `layout.py` is imported for the first time during the test while the patch is active, then `from data import get_prediction_stats` picks up the mock. Since `test_data.py` imports functions inside each test method (`from data import get_xxx`), and the patch is active, it gets the real function (not mocked -- the patch is on `execute_query`, not on the function itself).

The `test_layout.py` patches are on a higher level -- they mock entire functions. Since layout.py is imported DURING the test while the patch is active, the local binding in layout.py IS the mock.

**After the split**: `from data import get_prediction_stats` still works because `data/__init__.py` re-exports it. During the test, when the patch is active, `data.get_prediction_stats` is replaced with the mock. Then `layout.py` runs `from data import get_prediction_stats` and gets the mock (because `data.__dict__["get_prediction_stats"]` is the mock). **This still works.**

**But wait -- would `from data import get_prediction_stats` get the mock?** Yes! `from data import get_prediction_stats` looks up `get_prediction_stats` in `data.__dict__` at import time. If the patch is active, `data.__dict__["get_prediction_stats"]` is the mock. So the import gets the mock. **No changes needed for `test_layout.py`.**

Similarly, in `test_data.py`:

```python
@patch("data.get_signal_feed")
def test_csv_export_basic(self, mock_feed):
    from data import get_signal_feed_csv
```

`get_signal_feed_csv` is imported from `data` -- this gets the real function (since `get_signal_feed_csv` is not mocked). But `get_signal_feed_csv` internally calls `get_signal_feed()`. After the split, both are in `signal_queries.py`. The call `get_signal_feed()` inside `get_signal_feed_csv` resolves through `signal_queries.__globals__["get_signal_feed"]`, which is the real function. The patch on `data.get_signal_feed` doesn't affect it.

**Fix for inter-function patches**: Change the patch target to the submodule:

```
@patch("data.get_signal_feed")  -->  @patch("data.signal_queries.get_signal_feed")
@patch("data.get_dashboard_kpis")  -->  @patch("data.performance_queries.get_dashboard_kpis")
@patch("data.get_active_signals")  -->  @patch("data.signal_queries.get_active_signals")
```

**Summary of ALL required test changes:**

| Find | Replace | Files | Count |
|---|---|---|---|
| `@patch("data.execute_query")` | `@patch("data.base.execute_query")` | test_data.py, test_data_screener.py, test_insights.py | ~138 |
| `@patch("data.get_signal_feed")` | `@patch("data.signal_queries.get_signal_feed")` | test_data.py | ~5 |
| `@patch("data.get_dashboard_kpis")` | `@patch("data.performance_queries.get_dashboard_kpis")` | test_data.py | ~4 |
| `@patch("data.get_active_signals")` | `@patch("data.signal_queries.get_active_signals")` | test_data.py | ~5 |

The `test_layout.py` patches (`@patch("data.get_prediction_stats")` etc.) do NOT need to change because they patch the data module attribute BEFORE layout.py imports it in the test context.

---

## Revised Step-by-Step Implementation Plan (Consolidated)

### Step 1: Rename `data.py` and create package directory

```bash
cd /Users/chris/Projects/shitpost-alpha/shitty_ui
git mv data.py data_legacy.py
mkdir data
```

### Step 2: Create `shitty_ui/data/base.py`

Copy lines 1-72 of `data_legacy.py` verbatim. The file content is specified in the earlier section (Step 2).

### Step 3: Create `shitty_ui/data/signal_queries.py`

**Header:**

```python
"""
Signal and post query functions.

Handles loading, filtering, and paginating Truth Social posts and their
associated predictions. Includes the signal feed, unified feed, CSV export,
and price+signal combination queries.
"""

import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import text
from typing import List, Dict, Any, Optional

import data.base as _base
from data.base import logger
```

**For every function body**, replace every occurrence of `execute_query(` with `_base.execute_query(` (the `logger` reference can stay as a local import since it's never mocked).

Copy these functions (listed in the mapping above) from `data_legacy.py`, making only the `execute_query` -> `_base.execute_query` replacement in each function body.

**Example** -- `load_recent_posts` before/after:

Before (in data_legacy.py):
```python
    rows, columns = execute_query(query, {"limit": limit})
```

After (in signal_queries.py):
```python
    rows, columns = _base.execute_query(query, {"limit": limit})
```

**Count of `execute_query` call sites in signal_queries.py functions**: 15 (one per function, except `get_price_with_signals` which has 2, and `get_signal_feed_csv` which has 0 since it calls `get_signal_feed`).

### Step 4: Create `shitty_ui/data/performance_queries.py`

**Header:**

```python
"""
Performance and KPI query functions.

Handles dashboard KPIs, accuracy breakdowns, cumulative P&L, rolling metrics,
win/loss streaks, confidence calibration, backtesting simulation, and
aggregate statistics.
"""

import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import text
from typing import List, Dict, Any, Optional

import data.base as _base
from data.base import ttl_cache, logger, DATABASE_URL
```

Copy the 21 functions listed in the mapping above from `data_legacy.py`, replacing `execute_query(` with `_base.execute_query(` in each function body.

**Count of `execute_query` call sites**: ~22 (one per function, `get_dashboard_kpis_with_fallback` has 0 since it calls other functions).

### Step 5: Create `shitty_ui/data/asset_queries.py`

**Header:**

```python
"""
Asset query functions.

Handles asset screener data, sparkline price loading, per-asset predictions,
asset statistics, price history, related assets, and predictions with outcomes.
"""

import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import text
from typing import List, Dict, Any, Optional

import data.base as _base
from data.base import ttl_cache, logger
```

Copy the 9 functions listed in the mapping above from `data_legacy.py`, replacing `execute_query(` with `_base.execute_query(`.

**Count of `execute_query` call sites**: ~10.

### Step 6: Create `shitty_ui/data/insight_queries.py`

**Header:**

```python
"""
Dynamic insight query functions.

Generates a pool of insight candidates for dashboard cards by running
multiple targeted queries and formatting results with personality-driven copy.
"""

from datetime import datetime, timedelta
from sqlalchemy import text
from typing import List, Dict, Any

import data.base as _base
from data.base import ttl_cache, logger
```

Copy `get_dynamic_insights` from `data_legacy.py` (lines 2568-2865), replacing `execute_query(` with `_base.execute_query(`.

**Count of `execute_query` call sites in `get_dynamic_insights`**: 5 (one per insight query).

### Step 7: Create `shitty_ui/data/__init__.py`

The full content is specified in the earlier section (Step 7). This file re-exports every public function and defines `clear_all_caches()`.

### Step 8: Delete `data_legacy.py`

```bash
git rm /Users/chris/Projects/shitpost-alpha/shitty_ui/data_legacy.py
```

### Step 9: Update test patch targets

**File: `shit_tests/shitty_ui/test_data.py`**

Global find-replace #1 (execute_query):
```
Find:    @patch("data.execute_query")
Replace: @patch("data.base.execute_query")
```
Approximately 120 occurrences.

Find-replace #2 (inter-function: get_signal_feed):
```
Find:    @patch("data.get_signal_feed")
Replace: @patch("data.signal_queries.get_signal_feed")
```
Lines: 2788, 2830, 2842, 2878, 2960 (5 occurrences).

Find-replace #3 (inter-function: get_dashboard_kpis):
```
Find:    @patch("data.get_dashboard_kpis")
Replace: @patch("data.performance_queries.get_dashboard_kpis")
```
Lines: 3029, 3046, 3063, 3078 (4 occurrences).

Find-replace #4 (inter-function: get_active_signals):
```
Find:    @patch("data.get_active_signals")
Replace: @patch("data.signal_queries.get_active_signals")
```
Lines: 3101, 3112, 3126, 3141, 3157 (5 occurrences).

**File: `shit_tests/shitty_ui/test_data_screener.py`**

Global find-replace:
```
Find:    @patch("data.execute_query")
Replace: @patch("data.base.execute_query")
```
Approximately 11 occurrences (lines 29, 58, 76, 86, 92, 98, 129, 145, 159, 165, 171).

**File: `shit_tests/shitty_ui/test_insights.py`**

Global find-replace:
```
Find:    @patch("data.execute_query")
Replace: @patch("data.base.execute_query")
```
Approximately 7 occurrences (lines 15, 26, 73, 115, 132, 150, 201).

**File: `shit_tests/shitty_ui/test_layout.py`**

**NO CHANGES NEEDED.** The `@patch("data.get_prediction_stats")` decorators work correctly because they patch the `data` package's attribute BEFORE layout.py imports the function during test setup.

### Step 10: Verify `from data import` statements in tests still work

All test files use `from data import get_xxx` inside test methods. After the split, `data/__init__.py` re-exports everything, so these imports continue to work. **No changes needed.**

---

## Test Plan

### Existing Tests (must all pass unchanged except patch targets)

| Test File | Tests | Changes |
|---|---|---|
| `shit_tests/shitty_ui/test_data.py` | ~120 tests | Patch target updates only |
| `shit_tests/shitty_ui/test_data_screener.py` | ~11 tests | Patch target updates only |
| `shit_tests/shitty_ui/test_insights.py` | ~8 tests | Patch target updates only |
| `shit_tests/shitty_ui/test_layout.py` | ~50 tests | No changes |

### New Tests to Add

Add a new test file `shit_tests/shitty_ui/test_data_init.py` to verify the package re-export contract:

```python
"""
Tests for data package re-export contract.

Verifies that all public functions are accessible via `from data import X`
after the split into submodules.
"""

import sys
import os
import pytest

# Add shitty_ui to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shitty_ui"))


class TestDataPackageExports:
    """Verify every public function is re-exported from data/__init__.py."""

    def test_all_signal_query_functions_exported(self):
        """Signal query functions accessible from data package."""
        from data import (
            load_recent_posts,
            load_filtered_posts,
            get_recent_signals,
            get_active_signals,
            get_active_signals_with_fallback,
            get_unified_feed,
            get_weekly_signal_count,
            get_signal_feed,
            get_signal_feed_count,
            get_new_signals_since,
            get_signal_feed_csv,
            get_price_with_signals,
            get_multi_asset_signals,
        )
        assert callable(load_recent_posts)
        assert callable(get_signal_feed)

    def test_all_performance_query_functions_exported(self):
        """Performance query functions accessible from data package."""
        from data import (
            get_available_assets,
            get_prediction_stats,
            get_performance_metrics,
            get_dashboard_kpis,
            get_dashboard_kpis_with_fallback,
            get_accuracy_by_confidence,
            get_accuracy_by_asset,
            get_sentiment_distribution,
            get_active_assets_from_db,
            get_top_predicted_asset,
            get_cumulative_pnl,
            get_rolling_accuracy,
            get_win_loss_streaks,
            get_confidence_calibration,
            get_monthly_performance,
            get_high_confidence_metrics,
            get_empty_state_context,
            get_best_performing_asset,
            get_accuracy_over_time,
            get_backtest_simulation,
            get_sentiment_accuracy,
        )
        assert callable(get_prediction_stats)
        assert callable(get_dashboard_kpis)

    def test_all_asset_query_functions_exported(self):
        """Asset query functions accessible from data package."""
        from data import (
            get_asset_screener_data,
            get_screener_sparkline_prices,
            get_similar_predictions,
            get_predictions_with_outcomes,
            get_asset_price_history,
            get_sparkline_prices,
            get_asset_predictions,
            get_asset_stats,
            get_related_assets,
        )
        assert callable(get_asset_screener_data)
        assert callable(get_asset_stats)

    def test_all_insight_query_functions_exported(self):
        """Insight query functions accessible from data package."""
        from data import get_dynamic_insights
        assert callable(get_dynamic_insights)

    def test_base_infrastructure_exported(self):
        """Base infrastructure accessible from data package."""
        from data import execute_query, ttl_cache, clear_all_caches, logger
        assert callable(execute_query)
        assert callable(ttl_cache)
        assert callable(clear_all_caches)

    def test_clear_all_caches_runs_without_error(self):
        """clear_all_caches() should not raise even with empty caches."""
        from data import clear_all_caches
        clear_all_caches()  # Should not raise

    def test_dunder_all_matches_exports(self):
        """__all__ should list every re-exported name."""
        import data
        for name in data.__all__:
            assert hasattr(data, name), f"{name} in __all__ but not accessible"
```

### Verification Commands

Run the full test suite after the refactoring:

```bash
cd /Users/chris/Projects/shitpost-alpha
./venv/bin/python -m pytest shit_tests/shitty_ui/test_data.py -v
./venv/bin/python -m pytest shit_tests/shitty_ui/test_data_screener.py -v
./venv/bin/python -m pytest shit_tests/shitty_ui/test_data_init.py -v
./venv/bin/python -m pytest shit_tests/shitty_ui/test_insights.py -v
./venv/bin/python -m pytest shit_tests/shitty_ui/test_layout.py -v
./venv/bin/python -m pytest shit_tests/shitty_ui/ -v
```

---

## Documentation Updates

### CHANGELOG.md

Add under `## [Unreleased]`:

```markdown
### Changed
- **Data Layer Architecture** -- Split monolithic `shitty_ui/data.py` (2,865 lines) into 5 focused modules under `shitty_ui/data/` package
  - `data/base.py` -- shared infrastructure (execute_query, ttl_cache, logger)
  - `data/signal_queries.py` -- signal loading, feed, filtering, CSV export
  - `data/performance_queries.py` -- KPIs, accuracy, P&L, streaks, backtesting
  - `data/asset_queries.py` -- screener, sparklines, asset stats, price history
  - `data/insight_queries.py` -- dynamic insight card generation
  - `data/__init__.py` re-exports all public functions for zero breaking changes
```

### CLAUDE.md

Update the directory structure section to reflect the new package layout:

```
├── shitty_ui/              # Prediction performance dashboard
│   ├── app.py              # Dash application entry point
│   ├── layout.py           # App factory, router & callback registration
│   ├── data/               # Database query layer (split by domain)
│   │   ├── __init__.py     # Re-exports all functions (backward compat)
│   │   ├── base.py         # execute_query, ttl_cache, logger
│   │   ├── signal_queries.py    # Signal loading, feed, filtering
│   │   ├── performance_queries.py  # KPIs, accuracy, P&L, streaks
│   │   ├── asset_queries.py     # Screener, sparklines, asset stats
│   │   └── insight_queries.py   # Dynamic insight cards
│   ├── pages/              # Page modules (dashboard, assets)
│   ├── components/         # Reusable UI components
│   └── callbacks/          # Callback groups (alerts, navigation, clientside)
```

---

## Stress Testing & Edge Cases

### Circular Import Risk

The `data/__init__.py` imports from submodules, and submodules use `import data.base as _base`. This creates a dependency chain:

```
data/__init__.py  -->  data.base (first, no dependencies on data)
data/__init__.py  -->  data.signal_queries  -->  data.base (already loaded)
data/__init__.py  -->  data.performance_queries  -->  data.base (already loaded)
data/__init__.py  -->  data.asset_queries  -->  data.base (already loaded)
data/__init__.py  -->  data.insight_queries  -->  data.base (already loaded)
```

**No circular imports** because submodules import from `data.base`, not from `data`. The `data` package (`__init__.py`) imports `data.base` first, then imports from submodules. Submodules never import from `data` (the package).

### Import Order Sensitivity

All submodules MUST import `execute_query` via `import data.base as _base` (module attribute lookup), NOT via `from data.base import execute_query` (local binding). The module attribute lookup is essential for `@patch("data.base.execute_query")` to work in tests.

### Cache Wiring

`clear_all_caches()` in `__init__.py` must call `.clear_cache()` on every `@ttl_cache`-decorated function. The current implementation (lines 1245-1261) clears 15 caches. After the split, the same 15 functions plus 2 additional ones (`get_asset_screener_data`, `get_screener_sparkline_prices`) added in the dashboard redesign must be wired. The complete list in the `__init__.py` above includes all 18 cached functions.

### Python Path Resolution

The Dash app (`shitty_ui/app.py`) and tests add `shitty_ui/` to `sys.path`. With the split, `data` becomes a package directory. Python's import system resolves `from data import X` to `shitty_ui/data/__init__.py`, which re-exports everything. No path changes needed.

---

## Verification Checklist

- [ ] `shitty_ui/data.py` no longer exists (replaced by `shitty_ui/data/` directory)
- [ ] `shitty_ui/data/__init__.py` exists and imports all public functions
- [ ] `shitty_ui/data/base.py` exists with `execute_query`, `ttl_cache`, `logger`, `SIGNALS_TABLE`, `DATABASE_URL`
- [ ] `shitty_ui/data/signal_queries.py` exists with all 13 signal functions
- [ ] `shitty_ui/data/performance_queries.py` exists with all 21 performance functions
- [ ] `shitty_ui/data/asset_queries.py` exists with all 9 asset functions
- [ ] `shitty_ui/data/insight_queries.py` exists with `get_dynamic_insights`
- [ ] Every `execute_query(` call in submodules is `_base.execute_query(`
- [ ] Every submodule starts with `import data.base as _base` (NOT `from data.base import execute_query`)
- [ ] `clear_all_caches()` in `__init__.py` wires up all 18 cached functions
- [ ] `__all__` in `__init__.py` lists every re-exported name
- [ ] All `@patch("data.execute_query")` changed to `@patch("data.base.execute_query")` in test files
- [ ] Inter-function patches updated to submodule paths in `test_data.py`
- [ ] `test_data_init.py` created with re-export contract tests
- [ ] `./venv/bin/python -m pytest shit_tests/shitty_ui/ -v` passes
- [ ] `./venv/bin/python -m ruff check shitty_ui/data/` passes
- [ ] `./venv/bin/python -m ruff format shitty_ui/data/` passes
- [ ] No application files (`layout.py`, `pages/`, `callbacks/`, `components/`) were modified
- [ ] CHANGELOG.md updated
- [ ] CLAUDE.md directory structure updated
- [ ] Dashboard loads successfully at localhost (manual check)

---

## What NOT To Do

1. **Do NOT use `from data.base import execute_query` in submodules.** This creates a local binding that `@patch("data.base.execute_query")` cannot intercept. Use `import data.base as _base` and access as `_base.execute_query()` instead. This is the single most important rule in this refactoring.

2. **Do NOT change any SQL queries.** This is a pure structural refactoring. Every query string must be byte-for-byte identical to the original. If you spot a query improvement opportunity, save it for a separate PR.

3. **Do NOT change any function signatures.** Every parameter name, default value, type hint, and return type must be identical to the original.

4. **Do NOT change any function logic.** The try/except blocks, the date filter patterns, the pandas operations -- all must remain identical.

5. **Do NOT modify any application files** (`layout.py`, `pages/dashboard.py`, `pages/assets.py`, `callbacks/alerts.py`, `components/insights.py`). The entire point of the `__init__.py` re-export layer is to avoid touching consumers.

6. **Do NOT forget to update the inter-function mock patches.** The `@patch("data.get_signal_feed")`, `@patch("data.get_dashboard_kpis")`, and `@patch("data.get_active_signals")` decorators in `test_data.py` must be updated to their submodule paths. Missing these will cause ~14 tests to pass with mocks not actually intercepting the calls, leading to real database connection attempts and test failures.

7. **Do NOT add new imports to submodules beyond what the functions need.** For example, `signal_queries.py` does not need `ttl_cache` because none of its functions are cached. Importing it unnecessarily clutters the module.

8. **Do NOT create a `data/utils.py` or `data/helpers.py`.** The shared infrastructure lives in `base.py`. There is no justification for another shared module.

9. **Do NOT add `__init__.py` files to test directories.** The test files use `sys.path` manipulation to find the `data` module, not package-relative imports.

10. **Do NOT skip the `__all__` list in `__init__.py`.** Without it, `from data import *` would import submodule names like `base`, `signal_queries`, etc. The `__all__` list ensures only public functions are exported.

11. **Do NOT use `from data import execute_query` in submodules (circular import).** Submodules importing from the `data` package creates a circular dependency because `data/__init__.py` imports from the submodules. Always import from `data.base`.
