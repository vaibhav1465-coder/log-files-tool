CREATE TABLE IF NOT EXISTS analysis_runs (
    id UUID PRIMARY KEY,
    publication TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN ('cdn', 'origin')),
    status TEXT NOT NULL CHECK (status IN ('uploading', 'verifying', 'queued', 'processing', 'aggregating', 'completed', 'failed', 'cancelled')),
    phase TEXT NOT NULL,
    progress_percent NUMERIC(5,2),
    evidence_state TEXT NOT NULL DEFAULT 'no_data',
    processed_lines BIGINT NOT NULL DEFAULT 0,
    accepted_lines BIGINT NOT NULL DEFAULT 0,
    rejected_lines BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_code TEXT,
    error_message TEXT,
    calculation_version TEXT NOT NULL DEFAULT 'log-v1'
);

CREATE TABLE IF NOT EXISTS source_files (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES analysis_runs(id),
    original_name TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    sha256 TEXT NOT NULL,
    source_type TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, sha256)
);

CREATE TABLE IF NOT EXISTS status_aggregates (
    run_id UUID NOT NULL REFERENCES analysis_runs(id),
    status_code INTEGER NOT NULL CHECK (status_code BETWEEN 100 AND 599),
    request_count BIGINT NOT NULL,
    unique_url_count BIGINT NOT NULL,
    response_bytes BIGINT,
    PRIMARY KEY (run_id, status_code)
);

CREATE TABLE IF NOT EXISTS url_aggregates (
    run_id UUID NOT NULL REFERENCES analysis_runs(id),
    normalized_url TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    request_count BIGINT NOT NULL,
    first_seen TIMESTAMPTZ NOT NULL,
    last_seen TIMESTAMPTZ NOT NULL,
    response_bytes BIGINT,
    googlebot_request_count BIGINT NOT NULL DEFAULT 0,
    googlebot_first_seen TIMESTAMPTZ,
    googlebot_last_seen TIMESTAMPTZ,
    PRIMARY KEY (run_id, normalized_url, status_code)
);

ALTER TABLE url_aggregates ADD COLUMN IF NOT EXISTS googlebot_first_seen TIMESTAMPTZ;
ALTER TABLE url_aggregates ADD COLUMN IF NOT EXISTS googlebot_last_seen TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_analysis_runs_created ON analysis_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analysis_runs_status_created ON analysis_runs(status,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_url_aggregates_status ON url_aggregates(run_id, status_code);
CREATE INDEX IF NOT EXISTS idx_url_aggregates_googlebot ON url_aggregates(run_id,googlebot_request_count DESC) WHERE googlebot_request_count > 0;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_url_aggregates_search ON url_aggregates USING gin(normalized_url gin_trgm_ops);

ALTER TABLE analysis_runs DROP CONSTRAINT IF EXISTS analysis_runs_status_check;
ALTER TABLE analysis_runs ADD CONSTRAINT analysis_runs_status_check CHECK (status IN ('uploading', 'verifying', 'queued', 'processing', 'aggregating', 'completed', 'failed', 'cancelled'));

ALTER TABLE source_files ADD COLUMN IF NOT EXISTS upload_offset BIGINT NOT NULL DEFAULT 0;
ALTER TABLE source_files ADD COLUMN IF NOT EXISTS expected_size BIGINT;
ALTER TABLE source_files ADD COLUMN IF NOT EXISTS upload_complete BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE source_files ADD COLUMN IF NOT EXISTS upload_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
DROP INDEX IF EXISTS one_source_file_per_run;

CREATE TABLE IF NOT EXISTS gsc_properties (
    id UUID PRIMARY KEY,
    publication TEXT NOT NULL UNIQUE,
    site_url TEXT NOT NULL UNIQUE,
    timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    last_sync_at TIMESTAMPTZ,
    last_sync_status TEXT NOT NULL DEFAULT 'connector_pending',
    last_error TEXT,
    quota_daily_limit INTEGER NOT NULL DEFAULT 2000,
    quota_used_today INTEGER NOT NULL DEFAULT 0,
    quota_date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS gsc_daily_performance (
    property_id UUID NOT NULL REFERENCES gsc_properties(id),
    data_date DATE NOT NULL,
    page TEXT NOT NULL,
    clicks DOUBLE PRECISION NOT NULL DEFAULT 0,
    impressions DOUBLE PRECISION NOT NULL DEFAULT 0,
    ctr DOUBLE PRECISION NOT NULL DEFAULT 0,
    position DOUBLE PRECISION NOT NULL DEFAULT 0,
    extracted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (property_id, data_date, page)
);

CREATE TABLE IF NOT EXISTS gsc_sitemaps (
    property_id UUID NOT NULL REFERENCES gsc_properties(id),
    path TEXT NOT NULL,
    last_submitted TIMESTAMPTZ,
    last_downloaded TIMESTAMPTZ,
    is_pending BOOLEAN,
    warnings BIGINT,
    errors BIGINT,
    contents JSONB NOT NULL DEFAULT '[]'::jsonb,
    extracted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (property_id, path)
);

CREATE TABLE IF NOT EXISTS gsc_inspections (
    id UUID PRIMARY KEY,
    property_id UUID NOT NULL REFERENCES gsc_properties(id),
    inspection_url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled',
    verdict TEXT,
    coverage_state TEXT,
    indexing_state TEXT,
    page_fetch_state TEXT,
    robots_txt_state TEXT,
    last_crawl_time TIMESTAMPTZ,
    google_canonical TEXT,
    user_canonical TEXT,
    raw_result JSONB,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_gsc_inspection_property_status ON gsc_inspections(property_id,status,requested_at);

CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT,
    result TEXT NOT NULL,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS analysis_limit_bytes BIGINT;
ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS eta_low_seconds INTEGER;
ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS eta_likely_seconds INTEGER;
ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS eta_high_seconds INTEGER;
ALTER TABLE analysis_runs DROP CONSTRAINT IF EXISTS analysis_limit_positive;
ALTER TABLE analysis_runs ADD CONSTRAINT analysis_limit_positive CHECK (analysis_limit_bytes IS NULL OR analysis_limit_bytes > 0);

CREATE TABLE IF NOT EXISTS app_users (
    id UUID PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'analyst' CHECK (role IN ('analyst','admin')),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES app_users(id),
    token_hash TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    user_agent_hash TEXT NOT NULL,
    client_ip_hash TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_user_sessions_active ON user_sessions(user_id,expires_at DESC) WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_audit_events_created ON audit_events(created_at DESC);


ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS remote_source_id TEXT;
ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS created_by_email TEXT;
ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS selected_day DATE;
ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS start_hour_utc SMALLINT;
ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS end_hour_utc SMALLINT;
ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS selected_bytes BIGINT;
ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS estimated_transfer_cost_usd NUMERIC(12,6);
ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ;
ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS cancelled_by TEXT;
ALTER TABLE app_users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE analysis_runs DROP CONSTRAINT IF EXISTS analysis_runs_status_check;
ALTER TABLE analysis_runs ADD CONSTRAINT analysis_runs_status_check CHECK (status IN ('uploading','verifying','queued','processing','aggregating','cancelling','completed','failed','cancelled'));
ALTER TABLE analysis_runs DROP CONSTRAINT IF EXISTS analysis_runs_remote_hours_check;
ALTER TABLE analysis_runs ADD CONSTRAINT analysis_runs_remote_hours_check CHECK (
    (start_hour_utc IS NULL AND end_hour_utc IS NULL)
    OR (start_hour_utc >= 0 AND start_hour_utc < end_hour_utc AND end_hour_utc <= 24)
);
