# Market Data Architecture & Backfill Guide

**Last Updated**: 2026-02-10

> **Note**: Row counts in this document are illustrative. Run `python -m shitvault stats` and `python -m shit.market_data price-stats` for current numbers.

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      PREDICTION VALIDATION FLOW                  │
└─────────────────────────────────────────────────────────────────┘

  ┌──────────────┐
  │  Trump Posts │
  │  Truth Social│
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐       ┌─────────────┐
  │  Harvester   │──────>│  S3 Bucket  │
  │  (Scheduled) │       │  Raw Posts  │
  └──────────────┘       └──────┬──────┘
                                │
                                ▼
                         ┌─────────────┐
                         │  PostgreSQL         │
                         │  truth_social_      │
                         │  shitposts          │
                         └──────┬──────┘
                                │
                                ▼
                         ┌─────────────┐
                         │  LLM Analyzer│
                         │  GPT-4      │
                         └──────┬──────┘
                                │
                                ▼
                         ┌─────────────┐
                         │ predictions │
                         │   table     │
                         └──────┬──────┘
                                │
                ┌───────────────┼───────────────┐
                │               │               │
                ▼               ▼               ▼
         [AAPL, TSLA]    [GOOGL, META]   [SPY, QQQ]
         Mentioned       Mentioned       Mentioned
         Assets          Assets          Assets
                │               │               │
                └───────────────┼───────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ MARKET DATA FETCHER   │  <── NEW! This is what we built
                    │ (yfinance)            │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │  market_prices        │
                    │  (OHLCV data)         │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ OUTCOME CALCULATOR    │  <── NEW! This is what we built
                    │ (Compare predictions  │
                    │  with actual results) │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ prediction_outcomes   │
                    │ (Accuracy tracking)   │
                    └───────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │  ACCURACY METRICS     │
                    │  - Win rate           │
                    │  - Returns by asset   │
                    │  - Confidence calib.  │
                    └───────────────────────┘
```

---

## 📚 Data Model Detail

### **Table 1: `predictions`** (Existing - from LLM analysis)
```sql
CREATE TABLE predictions (
    id SERIAL PRIMARY KEY,
    shitpost_id VARCHAR(255),  -- Links to truth_social_shitposts
    assets JSONB,              -- ["AAPL", "TSLA", "GOOGL"]
    market_impact JSONB,       -- {"AAPL": "bullish", "TSLA": "bearish"}
    confidence FLOAT,          -- 0.0 to 1.0
    thesis TEXT,               -- LLM reasoning
    analysis_status VARCHAR,   -- 'completed', 'bypassed', 'pending'
    created_at TIMESTAMP
);
```

**Example assets**: AAPL, TSLA, GOOGL, SPY, DIA, AMD, META, etc.

---

### **Table 2: `market_prices`** (NEW - stores price history)
```sql
CREATE TABLE market_prices (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20),        -- "AAPL"
    date DATE,                 -- 2026-01-26

    -- OHLCV (standard finance data)
    open FLOAT,                -- Opening price
    high FLOAT,                -- Highest price
    low FLOAT,                 -- Lowest price
    close FLOAT,               -- Closing price (primary)
    volume BIGINT,             -- Trading volume
    adjusted_close FLOAT,      -- Adjusted for splits/dividends

    -- Metadata
    source VARCHAR(50),        -- "yfinance"
    last_updated TIMESTAMP,    -- When we fetched this
    is_market_open BOOLEAN,
    has_split BOOLEAN,
    has_dividend BOOLEAN,

    created_at TIMESTAMP,
    updated_at TIMESTAMP,

    UNIQUE(symbol, date)       -- One record per symbol per day
);
```

**Purpose:**
- Store historical price data so we don't re-fetch from yfinance constantly
- Enables fast outcome calculations without API calls
- Serves as data lake for dashboard visualizations

---

### **Table 3: `prediction_outcomes`** (NEW - tracks prediction accuracy)
```sql
CREATE TABLE prediction_outcomes (
    id SERIAL PRIMARY KEY,
    prediction_id INTEGER,     -- Links to predictions.id
    symbol VARCHAR(20),        -- "AAPL" (one outcome per asset per prediction)

    -- Prediction snapshot (denormalized for performance)
    prediction_date DATE,
    prediction_sentiment VARCHAR(20),  -- "bullish", "bearish", "neutral"
    prediction_confidence FLOAT,

    -- Price evolution
    price_at_prediction FLOAT, -- $246.70 (when prediction was made)
    price_t1 FLOAT,            -- $247.65 (after 1 day)
    price_t3 FLOAT,            -- $248.35 (after 3 days)
    price_t7 FLOAT,            -- $255.41 (after 7 days)
    price_t30 FLOAT,           -- $??? (after 30 days)

    -- Returns (percentage change)
    return_t1 FLOAT,           -- 0.38%
    return_t3 FLOAT,           -- 0.67%
    return_t7 FLOAT,           -- 3.53%
    return_t30 FLOAT,          -- NULL (pending)

    -- Validation (was prediction correct?)
    correct_t1 BOOLEAN,        -- TRUE (bullish + positive = correct)
    correct_t3 BOOLEAN,        -- TRUE
    correct_t7 BOOLEAN,        -- TRUE
    correct_t30 BOOLEAN,       -- NULL (pending)

    -- P&L simulation ($1000 position size)
    pnl_t1 FLOAT,              -- $3.80
    pnl_t3 FLOAT,              -- $6.70
    pnl_t7 FLOAT,              -- $35.30
    pnl_t30 FLOAT,             -- NULL (pending)

    -- Status tracking
    is_complete BOOLEAN,       -- All timeframes have data?
    last_price_update DATE,

    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**Purpose:**
- Track whether predictions were actually correct
- Calculate accuracy metrics by confidence level
- Generate P&L simulations for portfolio tracking
- Power the dashboard performance visualizations

---

## 🔄 How It Works: Step-by-Step

### **Step 1: Extract Assets from Predictions**
```python
# Get all unique assets mentioned in predictions
SELECT DISTINCT jsonb_array_elements_text(assets) as asset
FROM predictions
WHERE analysis_status = 'completed'
```

**Result:** 187 unique symbols (AAPL, TSLA, GOOGL, ...)

---

### **Step 2: Fetch Price History for Each Asset**
```python
# For each asset, fetch OHLCV data from yfinance
import yfinance as yf

ticker = yf.Ticker("AAPL")
hist = ticker.history(start="2025-01-01", end="2026-01-26")

# Store each day as a row in market_prices
for date, row in hist.iterrows():
    MarketPrice(
        symbol="AAPL",
        date=date,
        open=row['Open'],
        high=row['High'],
        low=row['Low'],
        close=row['Close'],
        volume=row['Volume'],
        adjusted_close=row['Close'],
        source="yfinance"
    )
```

**Handles:**
- ✅ Deduplication (UNIQUE constraint on symbol+date)
- ✅ Market closed days (weekends, holidays)
- ✅ Stock splits (uses adjusted_close)
- ✅ Dividends (uses adjusted_close)
- ✅ Missing data (graceful fallback with lookback)

---

### **Step 3: Calculate Outcomes for Each Prediction**
```python
# For each completed prediction:
prediction = Prediction(
    id=123,
    assets=["AAPL", "TSLA"],
    market_impact={"AAPL": "bullish", "TSLA": "bearish"},
    confidence=0.85,
    created_at="2026-01-20"
)

# For each asset in prediction:
for asset in prediction.assets:
    outcome = PredictionOutcome(
        prediction_id=prediction.id,
        symbol=asset,
        prediction_date="2026-01-20",
        prediction_sentiment="bullish",
        prediction_confidence=0.85
    )

    # Get prices from database
    price_t0 = get_price_on_date("AAPL", "2026-01-20")  # $246.70
    price_t1 = get_price_on_date("AAPL", "2026-01-21")  # $247.65
    price_t7 = get_price_on_date("AAPL", "2026-01-27")  # $255.41

    # Calculate returns
    outcome.return_t1 = (247.65 - 246.70) / 246.70 * 100  # 0.38%
    outcome.return_t7 = (255.41 - 246.70) / 246.70 * 100  # 3.53%

    # Determine correctness
    # Bullish + positive return = CORRECT ✅
    outcome.correct_t1 = True  # 0.38% > 0
    outcome.correct_t7 = True  # 3.53% > 0

    # Calculate P&L
    outcome.pnl_t7 = 0.0353 * 1000  # $35.30 profit
```

---

## 🚀 Backfill Process (Recommended)

### **Phase 1: Backfill All Asset Prices** ⏱️ ~10-15 minutes

Run the comprehensive backfill via the CLI:
```bash
# Backfill ALL assets from earliest prediction to today
python -m shit.market_data backfill-all-missing

# Or update prices for all predicted assets (recent window)
python -m shit.market_data update-all-prices --days 365
```

**What this does:**
1. Queries all predictions to extract unique assets (187 symbols)
2. Filters out invalid symbols (Korean exchange, etc.)
3. Determines earliest prediction date
4. For each asset:
   - Fetches OHLCV data from yfinance
   - Stores in `market_prices` table
   - Shows progress bar
5. Reports success/error counts

**Expected Result:**
- ~173 new symbols added to `market_prices`
- ~17,000-25,000 new price records (173 symbols × ~100-150 days)
- Some symbols may fail (delisted stocks, invalid tickers, etc.)

---

### **Phase 2: Calculate All Outcomes** ⏱️ ~5-10 minutes

After prices are backfilled:
```bash
# Calculate outcomes for ALL completed predictions
python -m shit.market_data calculate-outcomes --days 365

# Or process in batches
python -m shit.market_data calculate-outcomes --limit 500
python -m shit.market_data calculate-outcomes --limit 500 --skip 500
```

**What this does:**
1. Queries all completed predictions
2. For each prediction:
   - Extracts assets and sentiment
   - Looks up prices from `market_prices` table (fast!)
   - Calculates returns at T+1, T+3, T+7, T+30
   - Determines correctness
   - Stores in `prediction_outcomes` table
3. Shows progress

**Expected Result:**
- ~1,539 new outcomes created
- Some may be incomplete (pending future dates for T+30)
- Some may fail (asset not in market_prices)

---

### **Phase 3: Generate Accuracy Report** ⏱️ Instant

Once outcomes are calculated:
```bash
# Overall accuracy
python -m shit.market_data accuracy-report --timeframe t7

# Breakdown by confidence level
python -m shit.market_data accuracy-report --timeframe t7 --by-confidence

# Different timeframes
python -m shit.market_data accuracy-report --timeframe t1  # 1 day
python -m shit.market_data accuracy-report --timeframe t3  # 3 days
python -m shit.market_data accuracy-report --timeframe t30 # 30 days
```

**Sample Output:**
```
Accuracy by Confidence Level (t7)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Confidence Level    Total  Correct  Incorrect  Accuracy
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Low (0%-60%)        123    65       58         52.8%
Medium (60%-75%)    456    312      144        68.4%
High (75%-100%)     287    234      53         81.5%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 📊 Data Quality Considerations

### **Assets That May Fail:**

1. **Korean Exchange (KRX:)**:
   - yfinance doesn't support Korean stocks well
   - Example: `KRX:005380`, `KRX:000660`
   - **Solution**: Skip these for now

2. **Futures/Commodities**:
   - Example: `CL=F` (crude oil), `NG=F` (natural gas)
   - May have different data formats
   - **Solution**: Manual verification needed

3. **Delisted Stocks**:
   - Companies that went bankrupt or merged
   - **Solution**: yfinance returns empty data, we skip

4. **Invalid Tickers**:
   - LLM might hallucinate ticker symbols
   - Example: Wrong format, company names instead of tickers
   - **Solution**: Filter out during backfill

---

## 🔧 Maintenance & Updates

### **Automated Updates (Production)**

A Railway cron service runs every 15 minutes:
```bash
python -m shit.market_data auto-pipeline --days-back 30
```

This automatically:
1. Backfills prices for any new tickers from recent predictions
2. Recalculates outcomes for predictions in the last 30 days (filling in T+1, T+3, T+7, T+30 as time passes)

See `railway.json` for the service definition (`market-data` service).

---

## 💡 Advanced Queries

### **Find Best Performing Assets**
```sql
SELECT
    symbol,
    COUNT(*) as predictions,
    AVG(return_t7) as avg_return,
    SUM(CASE WHEN correct_t7 THEN 1 ELSE 0 END)::FLOAT /
        COUNT(*)::FLOAT * 100 as accuracy
FROM prediction_outcomes
WHERE correct_t7 IS NOT NULL
GROUP BY symbol
HAVING COUNT(*) >= 3  -- At least 3 predictions
ORDER BY accuracy DESC, avg_return DESC
LIMIT 10;
```

### **Find Best Performing Confidence Ranges**
```sql
SELECT
    CASE
        WHEN prediction_confidence < 0.6 THEN 'Low'
        WHEN prediction_confidence < 0.75 THEN 'Medium'
        ELSE 'High'
    END as confidence_level,
    COUNT(*) as total,
    SUM(CASE WHEN correct_t7 THEN 1 ELSE 0 END) as correct,
    AVG(return_t7) as avg_return,
    AVG(pnl_t7) as avg_pnl
FROM prediction_outcomes
WHERE correct_t7 IS NOT NULL
GROUP BY confidence_level
ORDER BY avg_pnl DESC;
```

---

## Summary

**Infrastructure:**
- ✅ Standard OHLCV price storage (`market_prices`)
- ✅ Prediction outcome tracking (`prediction_outcomes`)
- ✅ Automated fetcher using yfinance
- ✅ Outcome calculator with multiple timeframes
- ✅ CLI tools for backfill and reporting (`python -m shit.market_data`)
- ✅ Automated Railway cron (every 15 min) for ongoing updates

**Data Model:** Standard finance architecture
- Separate price storage from analysis
- Denormalized outcomes for fast queries
- Multiple timeframes for different trading strategies
- P&L simulation for portfolio tracking
