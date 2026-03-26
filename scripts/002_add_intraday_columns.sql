-- Migration: Add intraday columns to prediction_outcomes
-- Date: 2026-03-26
-- Context: ORM defines these columns but they may not exist in production yet.
--          FastAPI queries reference them, causing potential runtime errors.
-- Run: psql $DATABASE_URL -f scripts/002_add_intraday_columns.sql

-- Post publication timestamp (full datetime for intraday calculations)
ALTER TABLE prediction_outcomes ADD COLUMN IF NOT EXISTS post_published_at TIMESTAMP;

-- Intraday snapshot prices
ALTER TABLE prediction_outcomes ADD COLUMN IF NOT EXISTS price_at_post FLOAT;
ALTER TABLE prediction_outcomes ADD COLUMN IF NOT EXISTS price_at_next_close FLOAT;
ALTER TABLE prediction_outcomes ADD COLUMN IF NOT EXISTS price_1h_after FLOAT;

-- Intraday returns
ALTER TABLE prediction_outcomes ADD COLUMN IF NOT EXISTS return_same_day FLOAT;
ALTER TABLE prediction_outcomes ADD COLUMN IF NOT EXISTS return_1h FLOAT;

-- Intraday accuracy
ALTER TABLE prediction_outcomes ADD COLUMN IF NOT EXISTS correct_same_day BOOLEAN;
ALTER TABLE prediction_outcomes ADD COLUMN IF NOT EXISTS correct_1h BOOLEAN;

-- Intraday P&L
ALTER TABLE prediction_outcomes ADD COLUMN IF NOT EXISTS pnl_same_day FLOAT;
ALTER TABLE prediction_outcomes ADD COLUMN IF NOT EXISTS pnl_1h FLOAT;

-- Trading-day price snapshots (if not already present)
ALTER TABLE prediction_outcomes ADD COLUMN IF NOT EXISTS price_t1 FLOAT;
ALTER TABLE prediction_outcomes ADD COLUMN IF NOT EXISTS price_t3 FLOAT;
ALTER TABLE prediction_outcomes ADD COLUMN IF NOT EXISTS price_t7 FLOAT;
ALTER TABLE prediction_outcomes ADD COLUMN IF NOT EXISTS price_t30 FLOAT;
