-- Migration: add Trend.direction column and trend_predictions table
-- Generated: 2026-05-27

/*
This SQL migration adds a 'direction' column to the 'trends' table and creates
a 'trend_predictions' table to store simple predictions.

This file should be applied manually if Alembic is not configured in this project.
*/

BEGIN;

-- Add 'direction' column to 'trends' (non-nullable with default 'neutral')
ALTER TABLE trends
ADD COLUMN IF NOT EXISTS direction VARCHAR(20) NOT NULL DEFAULT 'neutral';

-- Create 'trend_predictions' table
CREATE TABLE IF NOT EXISTS trend_predictions (
    id VARCHAR(36) PRIMARY KEY,
    keyword VARCHAR(100) NOT NULL,
    horizon_weeks INTEGER,
    predicted_count INTEGER,
    confidence DOUBLE PRECISION,
    predicted_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_trend_predictions_keyword ON trend_predictions(keyword);

COMMIT;

-- Downgrade SQL (manual rollback):
-- DROP INDEX IF EXISTS ix_trend_predictions_keyword;
-- DROP TABLE IF EXISTS trend_predictions;
-- ALTER TABLE trends DROP COLUMN IF EXISTS direction;
