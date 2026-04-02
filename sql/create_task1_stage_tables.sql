CREATE TABLE IF NOT EXISTS event_candidates_stage (
    raw_document_url TEXT NOT NULL,
    dedup_key TEXT NOT NULL,
    duplicate_group_size TEXT NOT NULL,
    is_event TEXT NOT NULL,
    filter_reason TEXT NOT NULL,
    evidence TEXT,
    score_hint TEXT
);

CREATE TABLE IF NOT EXISTS structured_events_stage (
    event_id TEXT NOT NULL,
    raw_text_ref TEXT NOT NULL,
    event_name TEXT NOT NULL,
    event_date TEXT NOT NULL,
    source TEXT NOT NULL,
    event_subject_type TEXT NOT NULL,
    duration_type TEXT NOT NULL,
    predictability_type TEXT NOT NULL,
    industry_type TEXT NOT NULL,
    sentiment TEXT NOT NULL,
    heat_score TEXT NOT NULL,
    intensity_score TEXT NOT NULL,
    impact_scope TEXT NOT NULL,
    event_summary TEXT NOT NULL,
    subject_entities TEXT NOT NULL,
    classification_evidence TEXT
);
