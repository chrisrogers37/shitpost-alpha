-- 007: Create price_snapshots table for real-time price capture at prediction time
-- Run against production Neon DB

CREATE TABLE IF NOT EXISTS price_snapshots (
    id SERIAL PRIMARY KEY,
    prediction_id INTEGER NOT NULL REFERENCES predictions(id),
    symbol VARCHAR(20) NOT NULL,
    price DOUBLE PRECISION NOT NULL CHECK (price > 0),
    captured_at TIMESTAMP WITH TIME ZONE NOT NULL,
    post_published_at TIMESTAMP WITH TIME ZONE,
    source VARCHAR(50) DEFAULT 'yfinance_fast_info',
    market_status VARCHAR(20),
    previous_close DOUBLE PRECISION,
    day_high DOUBLE PRECISION,
    day_low DOUBLE PRECISION,
    volume BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT uq_price_snapshot_pred_symbol UNIQUE (prediction_id, symbol)
);

CREATE INDEX IF NOT EXISTS idx_price_snapshot_prediction_id
    ON price_snapshots (prediction_id);

CREATE INDEX IF NOT EXISTS idx_price_snapshot_symbol_captured
    ON price_snapshots (symbol, captured_at);
