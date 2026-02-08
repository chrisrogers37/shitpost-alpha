# Phase 0: Dashboard Stabilization Runbook

**Date**: 2026-02-08
**Prerequisite**: Run from an environment with access to the production Neon PostgreSQL database and outbound internet (Yahoo Finance API).
**Branch**: `claude/stabilize-dashboard-ui-63UMX` (code changes already merged)

---

## Context

The dashboard is deployed but non-functional because the data tables it queries are nearly empty:

| Table | Expected | Actual | Coverage |
|-------|----------|--------|----------|
| `truth_social_shitposts` | ~28,000 | ~28,000 | 100% |
| `predictions` | ~2,983 | ~2,983 | 100% |
| `market_prices` | ~187 assets | **14 assets** | **7.5%** |
| `prediction_outcomes` | ~1,548+ | **~9** | **0.6%** |

The code fixes (BUG-01, BUG-02, BUG-05) are already committed on the branch. What remains is populating the two empty tables from a properly configured environment.

---

## Step 1: Verify Environment

```bash
# Activate your virtualenv
source venv/bin/activate

# Confirm DB connectivity
python -m shitvault show-stats

# Confirm market data tooling loads
python -m shit.market_data price-stats
```

You should see the 14 symbols with existing price data and the overall prediction counts. If either command fails with a connection error, fix DATABASE_URL in your `.env` first.

---

## Step 2: Backfill market_prices

**What this does**: Queries all ~187 unique assets from the `predictions` table, then fetches historical OHLCV price data from Yahoo Finance for each asset and stores it in the `market_prices` table.

**External APIs hit**: Yahoo Finance (yfinance). Free, no API key required, but has rate limits.

**Estimated time**: 10-20 minutes depending on yfinance rate limiting.

**Estimated cost**: Free (Yahoo Finance is free).

### Option A: CLI (recommended)

```bash
python -m shit.market_data backfill-all-missing
```

This runs `AutoBackfillService.process_all_missing_assets()` which:
1. Extracts all unique assets from `predictions`
2. Checks which ones are already in `market_prices`
3. Fetches history for missing ones (365 days default)
4. Prints a summary with success/failure counts

### Option B: Direct script

```bash
python -c "from shit.market_data.backfill_prices import backfill_all_prediction_assets; backfill_all_prediction_assets()"
```

This fetches from the earliest prediction date to today (wider range, but may duplicate less).

### Verify

```bash
python -m shit.market_data price-stats
```

You should now see 150+ symbols (some tickers like Korean exchange `KRX:*` symbols will be filtered out as invalid).

---

## Step 3: Calculate prediction outcomes

**What this does**: For every completed prediction, looks up the actual market price at prediction time and at T+1, T+3, T+7, and T+30 days. Determines whether the prediction was correct and calculates P&L for a hypothetical $1,000 position. Writes results to `prediction_outcomes`.

**External APIs hit**: None. Reads from `market_prices` (populated in Step 2) and `predictions`, writes to `prediction_outcomes`.

**Database writes**: Creates ~1,500+ rows in `prediction_outcomes`.

**Estimated time**: 1-3 minutes.

### Run it

```bash
python -m shit.market_data calculate-outcomes
```

### To force-recalculate existing outcomes

```bash
python -m shit.market_data calculate-outcomes --force
```

### To limit scope (test first)

```bash
# Process only the 10 most recent predictions
python -m shit.market_data calculate-outcomes --limit 10

# Process only last 30 days
python -m shit.market_data calculate-outcomes --days 30
```

### Verify

```bash
python -m shitvault show-stats
```

You should see `prediction_outcomes` count jump from ~9 to ~1,500+.

---

## Step 4: Generate accuracy report

After outcomes are calculated, generate the accuracy report to confirm the data makes sense:

```bash
# Overall accuracy at T+7
python -m shit.market_data accuracy-report

# Breakdown by confidence level
python -m shit.market_data accuracy-report --by-confidence

# Different timeframes
python -m shit.market_data accuracy-report --timeframe t1
python -m shit.market_data accuracy-report --timeframe t30
```

---

## Step 5: Verify the dashboard

```bash
cd shitty_ui && python app.py
```

Open the dashboard URL (default `http://localhost:8050`) and confirm:

| Section | Should Now Show |
|---------|----------------|
| Performance Metrics Row | 4 metric cards with real accuracy, P&L, returns |
| Accuracy by Confidence Chart | Bar chart with 3 confidence buckets |
| Performance by Asset Chart | Bar chart with top assets |
| Recent Signals | Signal cards with outcome badges (Correct/Incorrect) |
| **Latest Posts** (new) | Trump's posts with LLM analysis, sentiment, assets |
| Data Table | Filterable table; confidence slider and date picker work |
| Asset Deep Dive | Candlestick charts with prediction overlays |
| Alert Assets Dropdown | Full list of ~187 assets from DB |

---

## Step 6: Run tests

```bash
# From project root
pytest shit_tests/shitty_ui/ -v
```

All 187 tests should pass.

---

## Troubleshooting

### "No price data found for SYMBOL"
Some assets won't have Yahoo Finance data (crypto tickers, foreign exchanges, delisted stocks). These are expected failures. The backfill will skip them and continue.

### yfinance rate limiting
If you see repeated timeout errors, yfinance is rate-limiting you. Wait 60 seconds and resume. The backfill is idempotent -- re-running it will skip assets that already have data.

### Outcomes show "0 created"
This means either:
- `market_prices` is still empty (run Step 2 first)
- All outcomes already exist (use `--force` to recalculate)

### Dashboard still shows empty charts
1. Clear the data cache: the dashboard has a 5-minute TTL cache. Either wait or click the period selector buttons to force a refresh.
2. Check the browser console for JavaScript errors.
3. Check `logs/` for Python errors.

---

## What the code changes did (already on the branch)

These are committed and don't need to be re-done. They'll take effect once the data is populated:

1. **BUG-01 - Post Feed**: Added `create_post_card()` and `update_post_feed()` callback that wires `load_recent_posts()` to a new "Latest Posts" section on the dashboard.

2. **BUG-05 - Filter Passthrough**: `update_predictions_table()` now passes the confidence slider range and date picker values through to `get_predictions_with_outcomes()`, which accepts `confidence_min`, `confidence_max`, `start_date`, `end_date`.

3. **BUG-02 - Dynamic Asset List**: `get_available_assets()` now queries the `predictions` table's JSONB `assets` column instead of returning a hardcoded 31-ticker list. Cached for 10 minutes.

4. **DATABASE_URL Fix**: Both `data.py` and `sync_session.py` strip literal quotes from `DATABASE_URL` to handle `.env` files with quoted values.
