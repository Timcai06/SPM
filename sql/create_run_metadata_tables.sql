CREATE TABLE IF NOT EXISTS etl_runs (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL UNIQUE,
    command_group TEXT NOT NULL,
    command_name TEXT NOT NULL,
    db_name TEXT,
    status TEXT NOT NULL CHECK (status IN ('running', 'success', 'failed')),
    argv JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT NOT NULL DEFAULT '',
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_etl_runs_group_name_started
    ON etl_runs (command_group, command_name, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_etl_runs_status_started
    ON etl_runs (status, started_at DESC);

CREATE TABLE IF NOT EXISTS etl_run_steps (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES etl_runs(run_id) ON DELETE CASCADE,
    step_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'success', 'failed')),
    row_count BIGINT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT NOT NULL DEFAULT '',
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMP,
    UNIQUE (run_id, step_name)
);

CREATE INDEX IF NOT EXISTS idx_etl_run_steps_run_id
    ON etl_run_steps (run_id, started_at DESC);

CREATE TABLE IF NOT EXISTS dataset_versions (
    id BIGSERIAL PRIMARY KEY,
    dataset_key TEXT NOT NULL,
    dataset_path TEXT NOT NULL,
    producer_run_id TEXT REFERENCES etl_runs(run_id) ON DELETE SET NULL,
    db_name TEXT,
    row_count BIGINT,
    file_size_bytes BIGINT,
    content_hash TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (dataset_key, dataset_path, producer_run_id)
);

CREATE INDEX IF NOT EXISTS idx_dataset_versions_dataset_key_created
    ON dataset_versions (dataset_key, created_at DESC);
