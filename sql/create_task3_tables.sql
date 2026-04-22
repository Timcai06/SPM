CREATE TABLE IF NOT EXISTS company_relations (
    id BIGSERIAL PRIMARY KEY,
    source_company_id BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    target_company_id BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL,
    relation_strength NUMERIC(6,4) NOT NULL DEFAULT 0.5000,
    direction TEXT NOT NULL DEFAULT 'undirected',
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_manual_override BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (source_company_id, target_company_id, relation_type)
);

CREATE INDEX IF NOT EXISTS idx_company_relations_source
    ON company_relations (source_company_id);

CREATE INDEX IF NOT EXISTS idx_company_relations_target
    ON company_relations (target_company_id);

CREATE INDEX IF NOT EXISTS idx_company_relations_type
    ON company_relations (relation_type);

CREATE INDEX IF NOT EXISTS idx_company_relations_strength
    ON company_relations (relation_strength DESC);

CREATE TABLE IF NOT EXISTS event_propagation_edges (
    id BIGSERIAL PRIMARY KEY,
    structured_event_id BIGINT NOT NULL REFERENCES structured_events(id) ON DELETE CASCADE,
    source_company_id BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    target_company_id BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    relation_id BIGINT REFERENCES company_relations(id) ON DELETE SET NULL,
    hop_count INTEGER NOT NULL DEFAULT 1,
    propagation_type TEXT NOT NULL DEFAULT 'one_hop',
    source_link_score NUMERIC(6,4),
    relation_strength NUMERIC(6,4),
    propagation_score NUMERIC(6,4),
    propagation_path TEXT,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (structured_event_id, source_company_id, target_company_id, propagation_type)
);

CREATE INDEX IF NOT EXISTS idx_event_propagation_edges_event
    ON event_propagation_edges (structured_event_id);

CREATE INDEX IF NOT EXISTS idx_event_propagation_edges_source
    ON event_propagation_edges (source_company_id);

CREATE INDEX IF NOT EXISTS idx_event_propagation_edges_target
    ON event_propagation_edges (target_company_id);

CREATE INDEX IF NOT EXISTS idx_event_propagation_edges_score
    ON event_propagation_edges (propagation_score DESC);
