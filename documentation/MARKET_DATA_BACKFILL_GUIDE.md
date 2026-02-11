# Market Data & Equities Backfill Guide

How to set up, backfill, and operate the market data pipeline that tracks actual stock prices against predictions and calculates whether the LLM was right.

---

## How It Works

```
LLM predicts: "AAPL bullish, 85% confidence"
    ↓
Market data pipeline fetches AAPL prices from Yahoo Finance
    ↓
After 1, 3, 7, and 30 days, calculates:
    - Did AAPL go up? (return %)
    - Was the prediction correct? (bullish + went up = correct)
    - What was the P&L? ($1000 simulated position)
    ↓
Stored in prediction_outcomes table
    ↓
Dashboard shows accuracy, Telegram /stats shows win rate
```

**Data source**: Yahoo Finance via `yfinance` library. **Free, no API key required**, no rate limits to worry about.

---

## Prerequisites

The market data pipeline needs only two things:

1. **Database access** — `DATABASE_URL` in your `.env` (you already have this)
2. **yfinance installed** — Already in `requirements.txt`

No API keys, no paid services, no external accounts needed.

Verify your environment:

```bash
# Check yfinance is available
python -c "import yfinance; print('yfinance OK')"

# Check database connection
python -m shitvault stats
```

---

## Database Tables

Two tables power the market data system:

### `market_prices` — Historical price data

Stores OHLCV data for every ticker the system tracks.

| Column | Type | Description |
|--------|------|-------------|
| `symbol` | String | Ticker symbol (e.g., `AAPL`, `BTC-USD`) |
| `date` | Date | Trading date |
| `open` | Float | Opening price |
| `high` | Float | Day's high |
| `low` | Float | Day's low |
| `close` | Float | Closing price |
| `volume` | BigInt | Trading volume |
| `adjusted_close` | Float | Split/dividend adjusted close |
| `source` | String | Always `yfinance` |

Unique constraint on `(symbol, date)` — one row per ticker per day.

### `prediction_outcomes` — Did the prediction work?

Links each prediction to actual price movement.

| Column | Type | Description |
|--------|------|-------------|
| `prediction_id` | Integer | FK to `predictions` |
| `symbol` | String | Ticker being tracked |
| `prediction_date` | Date | When the prediction was made |
| `prediction_sentiment` | String | `bullish`, `bearish`, `neutral` |
| `prediction_confidence` | Float | 0.0 - 1.0 |
| `price_at_prediction` | Float | Price when prediction was made |
| `price_t1` / `price_t3` / `price_t7` / `price_t30` | Float | Price at T+N days |
| `return_t1` / `return_t3` / `return_t7` / `return_t30` | Float | % return at T+N |
| `correct_t1` / `correct_t3` / `correct_t7` / `correct_t30` | Boolean | Was prediction correct? |
| `pnl_t1` / `pnl_t3` / `pnl_t7` / `pnl_t30` | Float | $ P&L on simulated $1000 position |
| `is_complete` | Boolean | All timeframes calculated? |

**Correctness logic** (0.5% threshold):
- **Bullish** prediction + return > 0.5% = correct
- **Bearish** prediction + return < -0.5% = correct
- **Neutral** prediction + |return| <= 0.5% = correct

---

## Initial Backfill (First Time Setup)

If you're starting fresh or have existing predictions without market data, run the one-time comprehensive backfill.

### Step 1: Check what you're working with

```bash
# See how many predictions exist and their date range
python -m shitvault stats

# See price data coverage
python -m shit.market_data price-stats
```

### Step 2: Backfill all missing assets

This fetches historical prices for every unique ticker in every prediction that doesn't already have price data:

```bash
python -m shit.market_data backfill-all-missing
```

**What it does**:
1. Scans all predictions for unique asset tickers
2. Filters out invalid symbols (Korean exchanges, blanks, > 10 chars)
3. For each missing ticker, fetches up to 365 days of history from Yahoo Finance
4. Stores prices in `market_prices` table

**How long**: Depends on how many unique tickers. ~1-2 seconds per ticker. For 50 tickers, expect ~2 minutes.

### Step 3: Calculate outcomes for all predictions

```bash
python -m shit.market_data calculate-outcomes
```

**What it does**:
1. Finds all predictions with assets that have price data
2. For each prediction + asset pair, calculates T+1, T+3, T+7, T+30 outcomes
3. Determines correctness and simulated P&L
4. Stores results in `prediction_outcomes`

**Note**: Outcomes at future timeframes (e.g., T+30 for a prediction made 5 days ago) will be `NULL` until enough time passes. The cron job fills these in automatically.

### Step 4: Verify

```bash
# Check accuracy at 7-day window
python -m shit.market_data accuracy-report -t t7

# Check by confidence tier
python -m shit.market_data accuracy-report -t t7 --by-confidence

# High-confidence only
python -m shit.market_data accuracy-report -t t7 --min-confidence 0.8
```

---

## Ongoing Operation (Production)

Once backfilled, the pipeline runs automatically on Railway every 15 minutes.

### What runs in production

From `railway.json`:

```json
{
  "market-data": {
    "startCommand": "python -m shit.market_data auto-pipeline --days-back 30",
    "cronSchedule": "*/15 * * * *"
  }
}
```

The `auto-pipeline` command runs two steps:

1. **Backfill recent** — Fetches prices for any new tickers from predictions in the last 30 days
2. **Calculate outcomes** — Recalculates outcomes for all predictions in the last 30 days, filling in T+1, T+3, T+7, T+30 as time passes

### Production data flow

```
Every 5 min:  Pipeline creates new predictions (LLM analysis)
                  ↓
Every 15 min: Market data cron runs auto-pipeline
                  ↓ Step 1: Sees new ticker "AAPL" → fetches AAPL prices
                  ↓ Step 2: Calculates T+0 price, T+1 if available
                  ↓
Next day:     Cron recalculates → fills in T+1 return & correctness
3 days later: Cron recalculates → fills in T+3
7 days later: Cron recalculates → fills in T+7
30 days later: Cron recalculates → fills in T+30, marks is_complete=true
```

No manual intervention needed once production cron is active.

---

## CLI Command Reference

All commands are run via `python -m shit.market_data <command>`.

### `fetch-prices` — Fetch one ticker

```bash
python -m shit.market_data fetch-prices --symbol AAPL --days 30
python -m shit.market_data fetch-prices -s TSLA -d 90 --force
```

| Flag | Default | Description |
|------|---------|-------------|
| `-s` / `--symbol` | Required | Ticker symbol |
| `-d` / `--days` | 30 | Days of history to fetch |
| `-f` / `--force` | False | Re-fetch even if data exists |

### `update-all-prices` — Fetch all prediction tickers

```bash
python -m shit.market_data update-all-prices --days 7
python -m shit.market_data update-all-prices --days 30 --limit 50
```

| Flag | Default | Description |
|------|---------|-------------|
| `-d` / `--days` | 30 | Days of history |
| `-l` / `--limit` | None | Max predictions to scan |

### `calculate-outcomes` — Score predictions

```bash
python -m shit.market_data calculate-outcomes
python -m shit.market_data calculate-outcomes --days 7 --force
```

| Flag | Default | Description |
|------|---------|-------------|
| `-l` / `--limit` | None | Max predictions to process |
| `-d` / `--days` | None | Only predictions from last N days |
| `-f` / `--force` | False | Recalculate existing outcomes |

### `accuracy-report` — See how predictions performed

```bash
python -m shit.market_data accuracy-report
python -m shit.market_data accuracy-report -t t7 --min-confidence 0.8 --by-confidence
```

| Flag | Default | Description |
|------|---------|-------------|
| `-t` / `--timeframe` | t7 | Evaluation window: `t1`, `t3`, `t7`, `t30` |
| `-c` / `--min-confidence` | None | Only predictions above this threshold |
| `-b` / `--by-confidence` | False | Break down accuracy by confidence tier |

### `price-stats` — Data coverage overview

```bash
python -m shit.market_data price-stats
python -m shit.market_data price-stats --symbol AAPL
```

### `auto-pipeline` — Full refresh (what production runs)

```bash
python -m shit.market_data auto-pipeline --days-back 30
python -m shit.market_data auto-pipeline --days-back 7 --limit 100
```

| Flag | Default | Description |
|------|---------|-------------|
| `-d` / `--days-back` | 7 | Process predictions from last N days |
| `-l` / `--limit` | None | Max predictions to process |

### `auto-backfill` — Fetch prices only (no outcome calc)

```bash
python -m shit.market_data auto-backfill --days 7
```

### `backfill-all-missing` — One-time comprehensive backfill

```bash
python -m shit.market_data backfill-all-missing
```

No flags. Scans all predictions ever and backfills any missing tickers.

---

## Supported Asset Types

yfinance supports a wide range of instruments:

| Type | Example Symbols | Notes |
|------|----------------|-------|
| US Stocks | `AAPL`, `TSLA`, `GOOGL`, `MSFT` | Most common |
| Crypto | `BTC-USD`, `ETH-USD`, `SOL-USD` | Use `-USD` suffix |
| ETFs | `SPY`, `QQQ`, `GLD`, `USO` | Indexes, commodities |
| Indexes | `^GSPC` (S&P 500), `^IXIC` (NASDAQ) | Use `^` prefix |
| International | `BABA`, `TSM`, `NVO` | US-listed ADRs work |

**Filtered out automatically**: Korean exchange tickers (KRX:), symbols > 10 chars, blank entries.

---

## Common Scenarios

### "I just deployed for the first time"

```bash
# 1. Fetch prices for all predicted assets
python -m shit.market_data backfill-all-missing

# 2. Calculate all outcomes
python -m shit.market_data calculate-outcomes

# 3. Check results
python -m shit.market_data accuracy-report -t t7

# 4. Verify production cron is set up in railway.json
```

### "I want to see how accurate predictions are"

```bash
# Overall accuracy at 7-day window
python -m shit.market_data accuracy-report -t t7

# Only high-confidence predictions
python -m shit.market_data accuracy-report -t t7 --min-confidence 0.8

# Broken down by confidence tier
python -m shit.market_data accuracy-report -t t7 --by-confidence

# At different time horizons
python -m shit.market_data accuracy-report -t t1   # Next day
python -m shit.market_data accuracy-report -t t30  # 30 days
```

### "New predictions aren't getting price data"

```bash
# Check if auto-pipeline cron is running
# In Railway dashboard, check the market-data service logs

# Manual run to catch up
python -m shit.market_data auto-pipeline --days-back 7

# Check what's missing
python -m shit.market_data price-stats
```

### "I want to force-refresh everything"

```bash
# Re-fetch all prices (even existing ones)
python -m shit.market_data update-all-prices --days 30

# Recalculate all outcomes
python -m shit.market_data calculate-outcomes --force
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `No module named 'yfinance'` | `pip install yfinance` (should be in requirements.txt) |
| Empty results for a ticker | Check if the symbol is valid on Yahoo Finance. Some OTC/penny stocks aren't available. |
| Outcomes all NULL | Need to wait for time to pass. T+7 outcomes require 7 days after prediction. |
| "No price data found" | Market may have been closed (weekends/holidays). The system looks back up to 7 days. |
| Crypto prices missing | Use `-USD` suffix: `BTC-USD` not `BTC` |
| Very slow backfill | yfinance fetches one ticker at a time. 100 tickers ≈ 3-4 minutes. Normal. |
| Railway cron not running | Verify `railway.json` has the `market-data` service defined. Check Railway dashboard for service status. |

---

## Cost

**$0/month.** Yahoo Finance via yfinance is completely free with no API key required. The only cost is the database storage (negligible on Neon free tier) and Railway compute time for the cron job.
