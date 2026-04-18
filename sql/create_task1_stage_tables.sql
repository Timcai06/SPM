CREATE TABLE IF NOT EXISTS int_event_candidates_stage (
    raw_document_url TEXT NOT NULL,
    dedup_key TEXT NOT NULL,
    duplicate_group_size TEXT NOT NULL,
    is_event TEXT NOT NULL,
    filter_reason TEXT NOT NULL,
    evidence TEXT,
    score_hint TEXT
);

CREATE TABLE IF NOT EXISTS int_structured_events_stage (
    event_id TEXT NOT NULL,
    raw_text_ref TEXT NOT NULL,
    event_name TEXT NOT NULL,
    event_date TEXT NOT NULL,
    source TEXT NOT NULL,
    source_type TEXT,
    authority_level TEXT,
    source_credibility_score TEXT,
    event_subject_type TEXT NOT NULL,
    event_subject_subtype TEXT,
    duration_type TEXT NOT NULL,
    predictability_type TEXT NOT NULL,
    industry_type TEXT NOT NULL,
    sentiment TEXT NOT NULL,
    time_orientation TEXT,
    event_stage TEXT,
    shock_source_type TEXT,
    region_scope TEXT,
    trigger_word_score TEXT,
    explicitness_score TEXT,
    uncertainty_score TEXT,
    novelty_score TEXT,
    amount_scale TEXT,
    amount_max_rmb TEXT,
    amount_log_rmb TEXT,
    event_code TEXT,
    sw_l1_industry TEXT,
    sw_l1_industry_code TEXT,
    sentiment_score_0_100 TEXT,
    source_credibility_type TEXT,
    company_count TEXT,
    industry_count TEXT,
    province_count TEXT,
    city_count TEXT,
    country_count TEXT,
    chain_stage_count TEXT,
    chain_stages TEXT,
    report_count TEXT,
    media_coverage_count TEXT,
    heat_growth_rate TEXT,
    heat_duration_days TEXT,
    disagreement_score TEXT,
    classification_confidence TEXT,
    heat_score TEXT NOT NULL,
    intensity_score TEXT NOT NULL,
    impact_scope TEXT NOT NULL,
    event_summary TEXT NOT NULL,
    subject_entities TEXT NOT NULL,
    classification_evidence TEXT
);

ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS source_type TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS authority_level TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS source_credibility_score TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS event_subject_subtype TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS time_orientation TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS event_stage TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS shock_source_type TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS region_scope TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS trigger_word_score TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS explicitness_score TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS uncertainty_score TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS novelty_score TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS amount_scale TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS amount_max_rmb TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS amount_log_rmb TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS event_code TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS sw_l1_industry TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS sw_l1_industry_code TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS sentiment_score_0_100 TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS source_credibility_type TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS company_count TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS industry_count TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS province_count TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS city_count TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS country_count TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS chain_stage_count TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS chain_stages TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS report_count TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS media_coverage_count TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS heat_growth_rate TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS heat_duration_days TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS disagreement_score TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS classification_confidence TEXT;
