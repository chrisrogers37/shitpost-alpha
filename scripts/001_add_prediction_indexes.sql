-- Migration: Add missing indexes on predictions table
-- Date: 2026-03-26
-- Context: predictions.shitpost_id is joined in ~25 queries with no index.
--          PostgreSQL does NOT auto-index FK columns.
-- Run: psql $DATABASE_URL -f scripts/001_add_prediction_indexes.sql

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_predictions_shitpost_id
    ON predictions (shitpost_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_predictions_signal_id
    ON predictions (signal_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_predictions_analysis_status
    ON predictions (analysis_status);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_predictions_created_at
    ON predictions (created_at);
