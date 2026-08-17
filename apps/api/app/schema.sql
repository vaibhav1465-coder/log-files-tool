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
CREATE UNIQUE INDEX IF NOT EXISTS one_source_file_per_run ON source_files(run_id);

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
