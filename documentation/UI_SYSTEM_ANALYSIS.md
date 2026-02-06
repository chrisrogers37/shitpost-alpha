# UI System Analysis: Bugs, Gaps, and Enhancement Opportunities

**Date**: 2026-02-06
**Scope**: Full review of `shitty_ui/` module and its data dependencies
**Status**: The UI layer is deployed but largely non-functional. Most dashboard sections display empty states or error cards rather than meaningful data.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Symptom Inventory](#2-symptom-inventory)
3. [Root Cause Analysis](#3-root-cause-analysis)
4. [Bug Inventory](#4-bug-inventory)
5. [Architecture Gaps](#5-architecture-gaps)
6. [Data Pipeline Gaps](#6-data-pipeline-gaps)
7. [Code Quality Issues](#7-code-quality-issues)
8. [Testing Gaps](#8-testing-gaps)
9. [Enhancement Opportunities](#9-enhancement-opportunities)
10. [Recommended Fix Order](#10-recommended-fix-order)
11. [Appendix: File-by-File Analysis](#11-appendix-file-by-file-analysis)

---

## 1. Executive Summary

The Shitpost Alpha dashboard was designed to provide three things:

1. **A feed of Truth Social posts** with the LLM's analysis
2. **Directional predictions** (bullish/bearish/neutral) with confidence levels
3. **Actual stock performance** compared against those predictions

**Current reality**: Almost none of this works. A user visiting the dashboard sees mostly empty cards, blank charts, and "No data available" messages. The small feed of old Truth Social posts that does appear only shows raw posts without LLM analysis, predictions, or performance data.

### Why?

The root cause is **not the UI code itself** -- it's the data behind it. The codebase contains ~6,700 lines of well-structured Dash UI code with error handling, loading states, and responsive design. But the queries powering this UI rely on tables that are nearly empty:

| Table | Expected Rows | Actual Rows | Coverage |
|-------|--------------|-------------|----------|
| `truth_social_shitposts` | ~28,000 | ~28,000 | 100% |
| `predictions` | ~2,983 | ~2,983 | 100% |
| `prediction_outcomes` | ~1,548+ | **~9** | **0.6%** |
| `market_prices` | ~187 assets | **14 assets** | **7.5%** |

The dashboard queries `prediction_outcomes` for virtually every metric (accuracy, P&L, returns, confidence calibration). With only 9 rows, every chart and metric card renders empty.

---

## 2. Symptom Inventory

### What a user sees today:

| Dashboard Section | Expected Behavior | Actual Behavior | Severity |
|-------------------|-------------------|-----------------|----------|
| Performance Metrics Row | 4 metric cards (accuracy, P&L, returns, count) | Empty/zero values or error cards | CRITICAL |
| Accuracy by Confidence Chart | Bar chart with 3 confidence levels | Empty chart: "No outcome data available" | CRITICAL |
| Performance by Asset Chart | Bar chart with top 10 assets | Empty chart: "No outcome data available" | CRITICAL |
| Recent Signals | 10 signal cards with outcomes | Cards show but returns/outcomes are null | HIGH |
| Asset Deep Dive (drilldown) | Historical predictions with P&L | Empty or partial data | HIGH |
| Asset Page (candlestick) | Price chart with prediction overlays | "No price data available" for most assets | HIGH |
| Data Table | Paginated table with filters | Mostly empty; filters have no effect | MODERATE |
| Alert System | Detects new predictions and notifies | Never fires (no new prediction_outcomes) | MODERATE |
| Post Feed (load_recent_posts) | Posts with LLM analysis attached | **Not connected to any callback** -- dead code | CRITICAL |

### What actually loads:
- The header and footer render correctly
- Time period buttons render and respond to clicks
- The Recent Signals section shows some cards (from `predictions` JOIN, not `prediction_outcomes`), but without return/outcome data
- Error boundaries catch failures gracefully, so the page doesn't crash -- it just shows empty states

---

## 3. Root Cause Analysis

### Primary Cause: Empty `prediction_outcomes` Table

The `prediction_outcomes` table is the single most important table for the dashboard. It contains the validated results of predictions: was the prediction correct? What was the actual return? What was the P&L?

**The table has ~9 rows.** The dashboard expects ~1,548+ (one row per completed prediction per asset).

**Why it's empty**: The outcome calculation pipeline (`shit/market_data/outcome_calculator.py`) exists and is functional, but it has not been run against the full dataset. The market data backfill has only been executed for 14 out of ~187 unique assets.

**Impact**: Every function that reads from `prediction_outcomes` returns empty or near-zero results:
- `get_performance_metrics()` → accuracy 0%, P&L $0, returns 0%
- `get_accuracy_by_confidence()` → empty DataFrame
- `get_accuracy_by_asset()` → empty DataFrame
- `get_recent_signals()` → signals show but without outcomes
- `get_active_assets_from_db()` → returns only the few assets with outcomes
- `get_cumulative_pnl()` → empty equity curve
- `get_rolling_accuracy()` → empty
- `get_confidence_calibration()` → empty

### Secondary Cause: Sparse `market_prices` Table

The `market_prices` table powers the Asset Deep Dive page's candlestick charts and provides the base data for calculating prediction outcomes.

**Current state**: ~528 rows across 14 assets. ~173 assets have no price data at all.

**Impact**:
- Asset pages show "No price data available for {symbol}" for 93% of assets
- Outcome calculator can't compute returns without base prices
- Asset Deep Dive drilldown shows predictions but not price performance

### Tertiary Cause: Dead Code / Disconnected Features

- `load_recent_posts()` and `load_filtered_posts()` -- the functions that load the Truth Social post feed with LLM predictions -- **are not called by any Dash callback**. They exist in `data.py` but no UI component invokes them. This is why users only see a "small feed" or nothing at all.
- `get_available_assets()` returns a **hardcoded list of 31 tickers** rather than querying the actual assets in the database. This means the asset filter may show assets that don't exist in the data and miss assets that do.

---

## 4. Bug Inventory

### BUG-01: Post feed is disconnected from the UI [CRITICAL]

**File**: `shitty_ui/data.py:133-166` (load_recent_posts), `data.py:169-277` (load_filtered_posts)

**Description**: The `load_recent_posts()` and `load_filtered_posts()` functions query `truth_social_shitposts` LEFT JOIN `predictions` to provide a post feed with LLM analysis. These functions are fully implemented and return correct DataFrames. However, **no Dash callback in `layout.py` calls either function**. The dashboard has no component that displays the raw post feed with attached LLM analysis.

**Impact**: The core feature -- "see what Trump posted and what the LLM thinks" -- doesn't appear on the dashboard.

**Fix**: Add a "Post Feed" section to the dashboard layout with a callback that invokes `load_recent_posts()` and renders the results as cards.

---

### BUG-02: Hardcoded asset list [MODERATE]

**File**: `shitty_ui/data.py:279-317` (get_available_assets)

**Description**: `get_available_assets()` returns a hardcoded list of 31 common tickers instead of querying the database. Meanwhile, `get_active_assets_from_db()` does query the database but only returns assets present in `prediction_outcomes`, which has ~9 rows.

**Impact**: The asset filter dropdown may show irrelevant tickers and miss assets that actually have predictions. When the `prediction_outcomes` table is populated, `get_active_assets_from_db()` will work correctly, but `get_available_assets()` will still be stale.

**Fix**: Replace the hardcoded list with a query against the `predictions` table's `assets` JSONB column, or merge logic with `get_active_assets_from_db()`.

---

### BUG-03: Recent Signals show without outcome context [HIGH]

**File**: `shitty_ui/layout.py:2534-2554` (signal rendering), `data.py:388-440` (get_recent_signals)

**Description**: `get_recent_signals()` LEFT JOINs `prediction_outcomes`, so signals appear even when no outcome exists. But the signal cards display `return_t7` and `correct_t7` which are NULL for most rows, resulting in signals that show a direction (bullish/bearish) but no information about whether the prediction was right.

**Impact**: Users see directional arrows and confidence levels but no performance feedback. The "clock" icon (pending) is shown for virtually every signal.

**Fix**: This resolves automatically once `prediction_outcomes` is populated. Optionally, add a visual distinction between "outcome pending" and "outcome not yet calculated."

---

### BUG-04: Alert system never fires [MODERATE]

**File**: `shitty_ui/alerts.py`, `layout.py:3612-3665` (run_alert_check)

**Description**: The alert check callback calls `get_new_predictions_since(last_check)` which queries the `predictions` table for new entries. However, the alert matching logic then compares against `prediction_outcomes` data. With the outcomes table nearly empty, alerts never match.

Additionally, the alert system relies on environment variables for email (SMTP) and SMS (Twilio) that are not configured in the Railway deployment.

**Impact**: Users can configure alerts, save preferences, and even test browser notifications, but real alerts never trigger from actual prediction data.

**Fix**: (1) Populate `prediction_outcomes`; (2) Configure SMTP/Twilio env vars in Railway; (3) Run E2E alert test.

---

### BUG-05: Confidence slider filter not applied to table query [LOW]

**File**: `shitty_ui/layout.py:2816-2921` (update_predictions_table)

**Description**: The table callback receives `confidence_range` from the slider and `start_date`/`end_date` from the date picker, but `get_predictions_with_outcomes(limit)` only accepts a `limit` parameter. The filter values are received but never passed to the query.

**Impact**: Changing the confidence slider or date range has no effect on the table data. The table always shows the same unfiltered results.

**Fix**: Extend `get_predictions_with_outcomes()` to accept confidence range and date range parameters, and pass them in the callback.

---

### BUG-06: `layout.py` is a 3,862-line monolith [MODERATE, Architectural]

**File**: `shitty_ui/layout.py`

**Description**: All page layouts, component factories, and ~25 callbacks live in a single file. This makes it difficult to:
- Navigate to specific sections
- Test individual pages in isolation
- Avoid callback ID collisions
- Enable concurrent development

**Impact**: Development velocity is reduced. Bug triage is harder because everything is interleaved.

**Fix**: Extract into a `pages/` module structure:
```
shitty_ui/
├── app.py
├── pages/
│   ├── dashboard.py      # Main dashboard layout + callbacks
│   ├── assets.py         # Asset deep dive page
│   ├── performance.py    # Performance page (future)
│   └── components.py     # Shared components (metric card, signal card, etc.)
├── data.py
├── alerts.py
└── telegram_bot.py
```

---

## 5. Architecture Gaps

### GAP-01: No Post Feed Component

The dashboard was designed to show prediction performance but lacks the foundational component: **a feed of the actual Truth Social posts with their LLM analysis**. This is what users expect first -- "What did Trump post? What does the LLM think?" The functions exist (`load_recent_posts`, `load_filtered_posts`) but are not wired to any UI.

**Recommendation**: Add a "Signal Feed" or "Post Feed" card to the dashboard that shows the latest posts alongside their LLM analysis (assets mentioned, sentiment, confidence, thesis).

---

### GAP-02: No Performance Page

The data layer has all the functions needed for a `/performance` page (equity curve, rolling accuracy, streaks, confidence calibration, monthly summary), but no page or route exists.

**Recommendation**: Create `pages/performance.py` with:
- Equity curve chart (`get_cumulative_pnl()`)
- Rolling accuracy line chart (`get_rolling_accuracy()`)
- Confidence calibration scatter plot (`get_confidence_calibration()`)
- Monthly performance table (`get_monthly_performance()`)
- Win/loss streak metrics (`get_win_loss_streaks()`)

---

### GAP-03: No Connection Between Posts and Market Impact

The user should be able to see a post, the LLM's prediction, and then the actual stock price movement in a single view. Currently these are spread across disconnected sections:
- Posts are in `load_recent_posts()` (disconnected)
- Predictions are in `get_recent_signals()` (partial)
- Outcomes are in `prediction_outcomes` (nearly empty)
- Prices are in `market_prices` (sparse)

**Recommendation**: Create a unified "Signal Detail" view that shows:
1. The original post text
2. LLM analysis (sentiment, confidence, thesis, assets)
3. Price chart for mentioned assets at prediction time ± 7 days
4. Whether the prediction was correct

---

### GAP-04: No Data Freshness Indicators

Users have no way to know how fresh the data is beyond the 5-minute refresh countdown. There's no indication of:
- When the last post was harvested
- When the last LLM analysis ran
- When market prices were last updated
- When outcomes were last calculated

**Recommendation**: Add a "Pipeline Status" footer or indicator showing:
- Last harvested post timestamp
- Last analysis timestamp
- Last market data update
- Total predictions awaiting outcomes

---

### GAP-05: No `/performance` Route or Page

The URL routing in `layout.py` only handles two patterns:
- `/` → Dashboard page
- `/assets/{symbol}` → Asset deep dive page

There is no `/performance` route, even though the data layer functions for it are fully built.

---

## 6. Data Pipeline Gaps

### PIPELINE-01: Market Price Backfill Incomplete

**Current**: 14 of ~187 assets have price data (528 total rows)
**Needed**: All assets with predictions need price history from the prediction date through at least T+30 days
**Tool**: `python -m shit.market_data update-prices` (already built)
**Estimate**: Single batch run needed; yfinance rate limits may require batching

### PIPELINE-02: Outcome Calculator Not Run at Scale

**Current**: 9 prediction outcomes computed
**Needed**: ~1,548+ completed predictions need outcomes calculated
**Tool**: `shit/market_data/outcome_calculator.py` (already built)
**Dependency**: Requires PIPELINE-01 (market prices) to be complete first

### PIPELINE-03: No Automated Outcome Calculation

**Current**: Outcome calculation is manual. Must be explicitly triggered.
**Needed**: Automated daily/hourly job to:
1. Check for predictions that are T+1, T+3, T+7, T+30 days old
2. Fetch current market prices for those assets
3. Calculate returns and correctness
4. Write to `prediction_outcomes`

**Recommendation**: Add outcome calculation to the main orchestrator cron job (`shitpost_alpha.py`).

### PIPELINE-04: No Price Data Auto-Backfill for New Assets

**Current**: When a new post mentions a new ticker (e.g., "PLTR"), no market data is automatically fetched
**Needed**: When a new prediction is created mentioning an asset not in `market_prices`, automatically queue price data fetching

**Note**: `shit/market_data/auto_backfill_service.py` exists but may not be integrated into the pipeline.

---

## 7. Code Quality Issues

### CQ-01: Inconsistent Error Handling Patterns

`layout.py` uses per-section try/except blocks in `update_dashboard()` (good), but the asset page callback (`update_asset_page`) has a single try/except wrapping everything. A failure in `get_asset_stats()` means the entire asset page shows an error, even if `get_asset_price_history()` would have succeeded.

**Recommendation**: Apply the same per-section graceful degradation pattern used in `update_dashboard()` to `update_asset_page()`.

### CQ-02: SQL Queries in `data.py` Use Raw `text()` Instead of SQLAlchemy ORM

All 20+ query functions use raw SQL via `sqlalchemy.text()`. This is not inherently wrong, but it:
- Bypasses the SQLAlchemy models defined in `shitvault/shitpost_models.py`
- Makes schema changes risky (no compile-time validation)
- Duplicates column knowledge across data.py and models

**Recommendation**: For new functions, consider using the ORM. For existing functions, this is a refactor-when-convenient item.

### CQ-03: `get_available_assets()` Is Hardcoded

As described in BUG-02. A 31-item hardcoded list in a data access layer is a code smell.

### CQ-04: Unused Imports and Dead Code

- `load_recent_posts()` and `load_filtered_posts()` are never called from any callback
- `get_sentiment_distribution()` is defined but not used in any dashboard callback
- The `confidence_range`, `start_date`, and `end_date` parameters in `update_predictions_table()` are received but ignored (BUG-05)

### CQ-05: `layout.py` Handles Too Many Responsibilities

A 3,862-line file containing:
- Color constants
- 15+ component factory functions
- Page layout builders
- ~25 callback registrations (including clientside JS)
- Alert system callbacks

This violates single-responsibility and makes the file difficult to reason about.

---

## 8. Testing Gaps

### Current Test Coverage

| Module | Tests | Coverage | Notes |
|--------|-------|----------|-------|
| `test_data.py` | 34 | ~75% | All functions tested with mocks |
| `test_layout.py` | 33 | ~65% | Component and basic callback tests |
| `test_alerts.py` | ~40 | Good | Alert logic well-tested with mocks |
| `test_telegram.py` | ~43 | Good | Telegram bot well-tested with mocks |
| **Integration** | **0** | **0%** | **No E2E tests at all** |

### Critical Testing Gaps

1. **No integration test verifies the dashboard actually renders with real data**. All tests use mocked data. A test that starts the Dash server, connects to a test database with realistic data, and verifies each section renders would have caught the empty-data issue immediately.

2. **No test verifies that `data.py` query functions return data matching what `layout.py` expects**. The mocks in `conftest.py` return well-formed data, but nobody verified the actual SQL queries return DataFrames with the expected column names and types.

3. **No smoke test for the deployed dashboard**. A simple HTTP request to the Railway URL with a check that the response doesn't contain "Error" would be valuable.

4. **Alert system E2E**: No test sends a real email, SMS, or browser notification. All channels are tested with mocks.

5. **Callback interaction chains**: No test verifies that clicking a bar chart -> selecting an asset -> loading drilldown data works as a complete flow. Individual callbacks are tested but not the chain.

### Recommended Test Additions

```
Priority 1 (Immediate):
  - Integration test: Start app with test DB, verify dashboard renders
  - Data validation test: Run each data.py function against real schema
  - Smoke test: HTTP GET / returns 200 and contains expected strings

Priority 2 (Soon):
  - Callback chain test: Period change -> dashboard update -> data refresh
  - Asset page test: Navigate to /assets/AAPL, verify sections populate
  - Alert dispatch test: Create mock prediction, verify alert triggers

Priority 3 (Nice to have):
  - Performance test: Dashboard load time with large dataset
  - Mobile rendering test: Viewport-specific layout checks
```

---

## 9. Enhancement Opportunities

### HIGH IMPACT

#### ENH-01: Add a "Latest Posts" Feed Section

**Impact**: This is the single most impactful missing feature. Users visit the dashboard to see Trump's posts and the LLM's take. Without this, the dashboard feels like a trading terminal with no content.

**Implementation**: Add a card to the dashboard that calls `load_recent_posts(limit=20)` and renders each post as a card showing:
- Post timestamp and text
- LLM analysis status (completed/bypassed/pending)
- If completed: assets, sentiment, confidence, thesis excerpt
- Engagement metrics (replies, reblogs, favourites)

**Effort**: Low -- the data function and card component patterns already exist.

#### ENH-02: Signal-to-Outcome Comparison View

**Impact**: The core value proposition. Show each prediction alongside its actual result.

**Implementation**: For each signal card, add an expandable section showing:
- Price at prediction time
- Price at T+1, T+3, T+7
- Percentage return at each timeframe
- Whether the prediction direction was correct
- Mini sparkline chart of price movement

**Effort**: Medium -- requires `prediction_outcomes` to be populated.

#### ENH-03: Pipeline Health Dashboard

**Impact**: Helps operators understand why data is missing and what needs attention.

**Implementation**: Small status bar showing:
- Posts harvested (last 24h)
- Predictions completed (last 24h)
- Outcomes calculated (last 24h)
- Assets missing price data (count)
- Oldest unprocessed prediction

**Effort**: Low -- simple count queries.

### MEDIUM IMPACT

#### ENH-04: Performance Page

**Impact**: Lets users evaluate the system's overall track record. Builds trust.

**Implementation**: New `/performance` route with equity curve, rolling accuracy, confidence calibration, monthly summary. All data layer functions already exist.

**Effort**: Medium -- UI components need to be built but data is ready.

#### ENH-05: CSV/JSON Data Export

**Impact**: Power users want to download the raw data for their own analysis.

**Implementation**: Add download buttons to the data table and signal feed. Use Dash's `dcc.Download` component.

**Effort**: Low.

#### ENH-06: Improved Signal Cards with Asset Price Context

**Impact**: Signal cards currently show text + sentiment but no price context.

**Implementation**: When a signal mentions an asset, show the current price and a tiny inline sparkline. This gives immediate context for the prediction.

**Effort**: Medium -- requires `market_prices` data.

### LOWER IMPACT (NICE TO HAVE)

#### ENH-07: Shareable URLs with State

Currently, the time period selection and asset drilldown state are lost on page reload. Using URL query parameters to persist state would allow bookmarking and sharing.

#### ENH-08: Dark/Light Theme Toggle

The dashboard uses a hardcoded dark theme. Some users may prefer light mode. This is cosmetic but shows polish.

#### ENH-09: WebSocket Real-Time Updates

Replace 5-minute polling with WebSocket push for truly real-time signals. Only worth doing after the data pipeline runs frequently.

---

## 10. Recommended Fix Order

### Phase 0: Make It Work (Immediate)

This is the critical path to a functioning dashboard.

```
Step 1: Backfill market_prices for all ~187 assets
        Tool: python -m shit.market_data update-prices

Step 2: Run outcome calculator for all historical predictions
        Tool: shit/market_data/outcome_calculator.py
        Dependency: Step 1

Step 3: Verify data.py queries return non-empty results
        Method: Run each function in a Python shell against prod DB

Step 4: Wire up load_recent_posts() to a dashboard callback
        Files: layout.py (add Post Feed section)

Step 5: Deploy and smoke test
        Method: Hit Railway URL, verify each section has data
```

**Expected outcome**: Dashboard shows real metrics, charts with bars, signals with outcomes, and a post feed.

### Phase 1: Fix Bugs

```
Step 6: Replace hardcoded get_available_assets() with DB query
Step 7: Pass filter params in update_predictions_table()
Step 8: Apply per-section error handling to update_asset_page()
Step 9: Add outcome calculation to orchestrator cron job
```

### Phase 2: Enhance

```
Step 10: Build /performance page (data layer is ready)
Step 11: Split layout.py into pages/ module
Step 12: Add integration tests (at least one smoke test)
Step 13: Add data export (CSV download)
Step 14: Pipeline health indicator
```

### Phase 3: Polish

```
Step 15: Signal-to-outcome comparison view
Step 16: Shareable URLs
Step 17: Alert system E2E testing with real channels
```

---

## 11. Appendix: File-by-File Analysis

### `shitty_ui/app.py` (25 lines)
**Status**: Working correctly
**Issues**: None. Clean entry point.

### `shitty_ui/layout.py` (3,862 lines)
**Status**: Partially functional
**Issues**:
- Monolith architecture (CQ-05)
- No post feed component (GAP-01)
- Asset page has single try/except instead of per-section (CQ-01)
- Table filter params not passed through (BUG-05)
- Overall structure is sound: error boundaries, loading states, responsive design all present

### `shitty_ui/data.py` (1,360 lines)
**Status**: Functional but returns empty data
**Issues**:
- `load_recent_posts()` and `load_filtered_posts()` are dead code (BUG-01)
- `get_available_assets()` is hardcoded (BUG-02)
- All `prediction_outcomes` queries return near-empty results (PIPELINE-01/02)
- Raw SQL instead of ORM (CQ-02, low priority)
- TTL cache implementation is clean and correct
- Connection pool configuration is appropriate

### `shitty_ui/alerts.py` (716 lines)
**Status**: Code complete, untested E2E
**Issues**:
- Depends on `prediction_outcomes` data (PIPELINE-02)
- Email/SMS dispatch requires environment variables not configured in Railway
- Quiet hours logic is well-implemented
- Rate limiting is implemented
- Alert matching logic is sound

### `shitty_ui/telegram_bot.py` (806 lines)
**Status**: Code complete, untested E2E
**Issues**:
- Requires `TELEGRAM_BOT_TOKEN` environment variable
- Multi-tenant subscription model is well-designed
- Rate limiting and error handling present
- Never tested with a real Telegram bot

---

## Summary

The Shitpost Alpha dashboard is **architecturally sound but starved of data**. The UI code is well-written with error handling, loading states, caching, and responsive design. The problem is entirely upstream: the data pipeline stops short of populating the tables the dashboard depends on.

**The fix is not in the UI code -- it's in the data pipeline.** Run the market price backfill, execute the outcome calculator, and the dashboard should come alive. The remaining bugs (dead code, hardcoded assets, unused filters) are real but secondary to getting data flowing.

Once the data pipeline is complete, the high-impact enhancements (post feed, signal-to-outcome view, performance page) can be layered on to deliver the full product vision.
