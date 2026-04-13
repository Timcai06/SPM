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
    source_credibility_score TEXT,
    event_subject_type TEXT NOT NULL,
    event_subject_subtype TEXT,
    duration_type TEXT NOT NULL,
    predictability_type TEXT NOT NULL,
    industry_type TEXT NOT NULL,
    sentiment TEXT NOT NULL,
    event_stage TEXT,
    shock_source_type TEXT,
    trigger_word_score TEXT,
    explicitness_score TEXT,
    uncertainty_score TEXT,
    novelty_score TEXT,
    event_code TEXT,
    heat_score TEXT NOT NULL,
    intensity_score TEXT NOT NULL,
    impact_scope TEXT NOT NULL,
    event_summary TEXT NOT NULL,
    subject_entities TEXT NOT NULL,
    classification_evidence TEXT
);

ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS source_type TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS source_credibility_score TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS event_subject_subtype TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS event_stage TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS shock_source_type TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS trigger_word_score TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS explicitness_score TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS uncertainty_score TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS novelty_score TEXT;
ALTER TABLE int_structured_events_stage ADD COLUMN IF NOT EXISTS event_code TEXT;
