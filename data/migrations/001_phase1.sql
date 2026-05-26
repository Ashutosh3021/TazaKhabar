-- Migration: Add 'direction' column to 'trends' and create 'trend_predictions' table
-- Generated: 2026-05-26

-- Upgrade: add column and table if not exists
BEGIN;

-- Add column 'direction' to 'trends' if it doesn't exist
ALTER TABLE trends ADD COLUMN IF NOT EXISTS direction VARCHAR DEFAULT 'neutral';

-- Create trend_predictions table if not exists
CREATE TABLE IF NOT EXISTS trend_predictions (
    id VARCHAR(36) PRIMARY KEY,
    keyword VARCHAR(200) NOT NULL,
    horizon_weeks INTEGER NOT NULL,
    predicted_count INTEGER NOT NULL,
    confidence FLOAT DEFAULT 0.0,
    predicted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMIT;

-- Downgrade: drop added artifacts
-- To rollback, run the statements below (manual rollback):
-- BEGIN;
-- ALTER TABLE trends DROP COLUMN IF EXISTS direction;
-- DROP TABLE IF EXISTS trend_predictions;
-- COMMIT;

-- BUG FIX [C4]: Provide DB migration to add 'direction' and create 'trend_predictions' table
