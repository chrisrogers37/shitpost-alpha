-- 008_schema_cleanup.sql
-- Data model audit WS-D: schema cleanup
-- Run on production Neon DB before deploying the corresponding code changes.

-- 1. Add CHECK constraint on prediction_outcomes.prediction_sentiment
ALTER TABLE prediction_outcomes
    ADD CONSTRAINT ck_prediction_outcomes_sentiment
    CHECK (prediction_sentiment IN ('bullish', 'bearish', 'neutral') OR prediction_sentiment IS NULL);

-- 2. Add FK from prediction_outcomes.symbol to ticker_registry.symbol
-- (all existing symbols should already be in ticker_registry; verify first)
-- SELECT DISTINCT po.symbol FROM prediction_outcomes po
--   LEFT JOIN ticker_registry tr ON po.symbol = tr.symbol
--   WHERE tr.symbol IS NULL;
ALTER TABLE prediction_outcomes
    ADD CONSTRAINT fk_prediction_outcomes_symbol
    FOREIGN KEY (symbol) REFERENCES ticker_registry(symbol);

-- 3. Add FK from price_snapshots.symbol to ticker_registry.symbol
ALTER TABLE price_snapshots
    ADD CONSTRAINT fk_price_snapshots_symbol
    FOREIGN KEY (symbol) REFERENCES ticker_registry(symbol);

-- 4. Drop dead columns from prediction_outcomes
ALTER TABLE prediction_outcomes DROP COLUMN IF EXISTS market_volatility;
ALTER TABLE prediction_outcomes DROP COLUMN IF EXISTS notes;
