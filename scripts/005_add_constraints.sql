-- Migration: Add CHECK and UNIQUE constraints
-- Date: 2026-03-26
-- Context: 7 business rules enforced only in Python code without DB constraints.
-- NOTE: If existing data violates constraints, fix data first before running.
-- Run: psql $DATABASE_URL -f scripts/005_add_constraints.sql

-- predictions.analysis_status must be a known value
ALTER TABLE predictions
    ADD CONSTRAINT ck_predictions_analysis_status
    CHECK (analysis_status IN ('completed', 'bypassed', 'error', 'pending'))
    NOT VALID;  -- NOT VALID skips checking existing rows, then validate separately
ALTER TABLE predictions VALIDATE CONSTRAINT ck_predictions_analysis_status;

-- predictions.confidence must be in [0, 1] or NULL
ALTER TABLE predictions
    ADD CONSTRAINT ck_predictions_confidence_range
    CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0))
    NOT VALID;
ALTER TABLE predictions VALIDATE CONSTRAINT ck_predictions_confidence_range;

-- predictions must reference either shitpost_id or signal_id
ALTER TABLE predictions
    ADD CONSTRAINT ck_predictions_has_content_ref
    CHECK (shitpost_id IS NOT NULL OR signal_id IS NOT NULL)
    NOT VALID;
ALTER TABLE predictions VALIDATE CONSTRAINT ck_predictions_has_content_ref;

-- ticker_registry.status must be a known value
ALTER TABLE ticker_registry
    ADD CONSTRAINT ck_ticker_registry_status
    CHECK (status IN ('active', 'inactive', 'invalid'))
    NOT VALID;
ALTER TABLE ticker_registry VALIDATE CONSTRAINT ck_ticker_registry_status;

-- prediction_outcomes must have unique (prediction_id, symbol) pairs
ALTER TABLE prediction_outcomes
    ADD CONSTRAINT uq_prediction_outcomes_pred_symbol
    UNIQUE (prediction_id, symbol);
