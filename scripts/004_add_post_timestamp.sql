-- Migration: Add denormalized post_timestamp to predictions
-- Date: 2026-03-26
-- Context: Eliminates N+1 lazy loading in OutcomeCalculator._get_source_datetime()
--          which traverses prediction.shitpost.timestamp for every prediction in a batch.
-- Run: psql $DATABASE_URL -f scripts/004_add_post_timestamp.sql

-- Add column
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS post_timestamp TIMESTAMPTZ;

-- Backfill from truth_social_shitposts (legacy FK path)
UPDATE predictions p
SET post_timestamp = tss.timestamp
FROM truth_social_shitposts tss
WHERE p.shitpost_id = tss.shitpost_id
  AND p.post_timestamp IS NULL;

-- Backfill from signals (new FK path)
UPDATE predictions p
SET post_timestamp = s.published_at
FROM signals s
WHERE p.signal_id = s.signal_id
  AND p.post_timestamp IS NULL;
