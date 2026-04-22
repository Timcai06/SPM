CREATE TABLE IF NOT EXISTS event_research_samples (
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
    event_subject_subtype TEXT,
    source_type TEXT,
    authority_level TEXT,
    source_credibility_score NUMERIC(4,2),
    duration_type TEXT NOT NULL,
    predictability_type TEXT NOT NULL,
    event_industry_type TEXT NOT NULL,
    sentiment TEXT NOT NULL,
    time_orientation TEXT,
    event_stage TEXT,
    shock_source_type TEXT,
    region_scope TEXT,
    trigger_word_score INTEGER,
    explicitness_score INTEGER,
    uncertainty_score INTEGER,
    novelty_score INTEGER,
    amount_scale TEXT,
    event_code TEXT,
    heat_score INTEGER NOT NULL,
    intensity_score INTEGER NOT NULL,
    impact_scope TEXT NOT NULL,
    impact_level_score INTEGER,
    affected_company_count INTEGER,
    affected_industry_count INTEGER,
    relation_rank_in_event INTEGER,
    industry_match_score NUMERIC(8,4),
    concept_match_count INTEGER,
    event_age_days INTEGER,
    event_trade_alignment_type TEXT,
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

CREATE INDEX IF NOT EXISTS idx_event_research_samples_event_date
    ON event_research_samples (event_date DESC);

CREATE INDEX IF NOT EXISTS idx_event_research_samples_ts_code
    ON event_research_samples (ts_code);

CREATE INDEX IF NOT EXISTS idx_event_research_samples_subject
    ON event_research_samples (event_subject_type);

CREATE INDEX IF NOT EXISTS idx_event_research_samples_final_link
    ON event_research_samples (final_link_score DESC);
