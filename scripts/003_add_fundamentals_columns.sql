-- Migration: Add company fundamentals columns to ticker_registry
-- Date: 2026-03-26
-- Context: ORM defines these columns (populated by FundamentalsProvider)
--          but they may not exist in production yet.
-- Run: psql $DATABASE_URL -f scripts/003_add_fundamentals_columns.sql

ALTER TABLE ticker_registry ADD COLUMN IF NOT EXISTS company_name VARCHAR(255);
ALTER TABLE ticker_registry ADD COLUMN IF NOT EXISTS sector VARCHAR(100);
ALTER TABLE ticker_registry ADD COLUMN IF NOT EXISTS industry VARCHAR(100);
ALTER TABLE ticker_registry ADD COLUMN IF NOT EXISTS market_cap BIGINT;
ALTER TABLE ticker_registry ADD COLUMN IF NOT EXISTS pe_ratio FLOAT;
ALTER TABLE ticker_registry ADD COLUMN IF NOT EXISTS forward_pe FLOAT;
ALTER TABLE ticker_registry ADD COLUMN IF NOT EXISTS dividend_yield FLOAT;
ALTER TABLE ticker_registry ADD COLUMN IF NOT EXISTS beta FLOAT;
ALTER TABLE ticker_registry ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE ticker_registry ADD COLUMN IF NOT EXISTS fundamentals_updated_at TIMESTAMP;

-- Add sector index for dashboard queries
CREATE INDEX IF NOT EXISTS idx_ticker_registry_sector
    ON ticker_registry (sector);
