CREATE TABLE IF NOT EXISTS canonical_events (
    id BIGSERIAL PRIMARY KEY,
    canonical_event_id TEXT NOT NULL UNIQUE,
    canonical_event_name TEXT NOT NULL,
    cluster_size INTEGER NOT NULL,
    date_start DATE NOT NULL,
    date_end DATE NOT NULL,
    event_subject_type TEXT NOT NULL,
    industry_type TEXT NOT NULL,
    impact_scope TEXT NOT NULL,
    representative_event_id TEXT NOT NULL,
    representative_source TEXT NOT NULL,
    max_heat_score INTEGER NOT NULL DEFAULT 0,
    max_intensity_score INTEGER NOT NULL DEFAULT 0,
    member_event_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    subject_entities JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_distribution JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_canonical_events_date_start
    ON canonical_events (date_start DESC);

CREATE INDEX IF NOT EXISTS idx_canonical_events_subject_type
    ON canonical_events (event_subject_type);

CREATE TABLE IF NOT EXISTS event_canonical_links (
    id BIGSERIAL PRIMARY KEY,
    structured_event_id BIGINT NOT NULL UNIQUE REFERENCES structured_events(id) ON DELETE CASCADE,
    canonical_event_id TEXT NOT NULL REFERENCES canonical_events(canonical_event_id) ON DELETE CASCADE,
    is_representative BOOLEAN NOT NULL DEFAULT FALSE,
    cluster_size INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_event_canonical_links_canonical_event
    ON event_canonical_links (canonical_event_id);
