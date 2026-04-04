CREATE TABLE IF NOT EXISTS model_event_samples (
    id BIGSERIAL PRIMARY KEY,
    sample_key TEXT NOT NULL UNIQUE,
    sample_run_id TEXT NOT NULL,
    structured_event_id BIGINT NOT NULL REFERENCES structured_events(id) ON DELETE CASCADE,
    company_id BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    canonical_event_id TEXT,
    event_id TEXT NOT NULL,
    event_date DATE NOT NULL,
    ts_code TEXT NOT NULL,
    company_name TEXT NOT NULL,
    event_subject_type TEXT NOT NULL,
    duration_type TEXT NOT NULL,
    predictability_type TEXT NOT NULL,
    event_industry_type TEXT NOT NULL,
    sentiment TEXT NOT NULL,
    heat_score INTEGER NOT NULL,
    intensity_score INTEGER NOT NULL,
    impact_scope TEXT NOT NULL,
    link_type TEXT NOT NULL,
    final_link_score NUMERIC(6,4) NOT NULL,
    company_industry_l1 TEXT,
    company_industry_l2 TEXT,
    concept_tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    label_car_w1 NUMERIC(12,6),
    label_car_w3 NUMERIC(12,6),
    label_car_w5 NUMERIC(12,6),
    label_up_w1 BOOLEAN,
    label_up_w3 BOOLEAN,
    label_up_w5 BOOLEAN,
    label_source TEXT NOT NULL DEFAULT 'none',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_model_event_samples_event_date
    ON model_event_samples (event_date DESC);

CREATE INDEX IF NOT EXISTS idx_model_event_samples_ts_code
    ON model_event_samples (ts_code);

CREATE INDEX IF NOT EXISTS idx_model_event_samples_subject
    ON model_event_samples (event_subject_type);

CREATE INDEX IF NOT EXISTS idx_model_event_samples_final_link
    ON model_event_samples (final_link_score DESC);
