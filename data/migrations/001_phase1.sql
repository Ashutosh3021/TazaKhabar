-- Phase 1: core tables (matches backend/src/db/models.py, excluding trend_predictions).
-- Apply in Supabase SQL Editor before 002_trend_direction_predictions.sql.
-- Idempotent: safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS jobs (
    id VARCHAR(36) PRIMARY KEY,
    hn_item_id INTEGER UNIQUE,
    title VARCHAR(500) NOT NULL,
    company VARCHAR(200) NOT NULL,
    location VARCHAR(200) NOT NULL DEFAULT 'N/A',
    tags JSONB NOT NULL DEFAULT '[]',
    email_contact VARCHAR(500),
    apply_link VARCHAR(1000),
    is_ghost_job BOOLEAN NOT NULL DEFAULT FALSE,
    deadline VARCHAR(50),
    posted_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    scraped_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc'),
    report_version VARCHAR(10) NOT NULL DEFAULT '2',
    cleaned_title VARCHAR(500),
    cleaned_company VARCHAR(200),
    role VARCHAR(100),
    description TEXT,
    processed BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS ix_jobs_hn_item_id ON jobs (hn_item_id);

CREATE TABLE IF NOT EXISTS news (
    id VARCHAR(36) PRIMARY KEY,
    hn_item_id INTEGER NOT NULL UNIQUE,
    type VARCHAR(20) NOT NULL,
    title VARCHAR(1000) NOT NULL,
    url VARCHAR(2000),
    score INTEGER NOT NULL DEFAULT 0,
    comment_count INTEGER NOT NULL DEFAULT 0,
    summary VARCHAR(2000),
    summarized BOOLEAN NOT NULL DEFAULT FALSE,
    summarized_at TIMESTAMP WITHOUT TIME ZONE,
    scraped_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc'),
    report_version VARCHAR(10) NOT NULL DEFAULT '2'
);
CREATE INDEX IF NOT EXISTS ix_news_hn_item_id ON news (hn_item_id);

CREATE TABLE IF NOT EXISTS trends (
    id VARCHAR(36) PRIMARY KEY,
    keyword VARCHAR(100) NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    week_start TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    week_end TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    percentage_change DOUBLE PRECISION NOT NULL DEFAULT 0.0
);
CREATE INDEX IF NOT EXISTS ix_trends_keyword ON trends (keyword);

CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    email VARCHAR(500),
    roles JSONB NOT NULL DEFAULT '[]',
    experience_level VARCHAR(10) NOT NULL DEFAULT 'I',
    resume_path VARCHAR(500),
    resume_text TEXT,
    ats_score INTEGER,
    ats_critical_issues JSONB NOT NULL DEFAULT '[]',
    ats_missing_keywords JSONB NOT NULL DEFAULT '[]',
    ats_suggested_additions JSONB NOT NULL DEFAULT '[]',
    last_analysis_at TIMESTAMP WITHOUT TIME ZONE,
    preferences JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);

CREATE TABLE IF NOT EXISTS rate_limits (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36),
    date VARCHAR(10) NOT NULL,
    request_count INTEGER NOT NULL DEFAULT 0,
    last_request_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS ix_rate_limits_user_id ON rate_limits (user_id);

CREATE TABLE IF NOT EXISTS reports (
    id VARCHAR(36) PRIMARY KEY,
    version VARCHAR(10) NOT NULL,
    run_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc'),
    items_collected INTEGER NOT NULL DEFAULT 0,
    new_items INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'running'
);

CREATE TABLE IF NOT EXISTS observations (
    id VARCHAR(36) PRIMARY KEY,
    week_start TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    text VARCHAR(2000) NOT NULL,
    generated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);

CREATE TABLE IF NOT EXISTS embeddings (
    id VARCHAR(36) PRIMARY KEY,
    item_id VARCHAR(36) NOT NULL,
    item_type VARCHAR(20) NOT NULL,
    embedding BYTEA NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS ix_embeddings_item_id ON embeddings (item_id);

CREATE TABLE IF NOT EXISTS notifications (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    job_id VARCHAR(36) NOT NULL,
    match_score INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc'),
    sent_at TIMESTAMP WITHOUT TIME ZONE
);
CREATE INDEX IF NOT EXISTS ix_notifications_user_id ON notifications (user_id);

COMMIT;
