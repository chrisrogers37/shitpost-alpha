-- Migration: Drop dead tables (zero code references)
-- Date: 2026-03-26
-- Context: subscribers (SMS, never activated) and llm_feedback (never activated)
--          have zero code references. Models removed from ORM.
-- Run: psql $DATABASE_URL -f scripts/006_drop_dead_tables.sql

DROP TABLE IF EXISTS subscribers;
DROP TABLE IF EXISTS llm_feedback;
