CREATE TABLE IF NOT EXISTS companies (
    id BIGSERIAL PRIMARY KEY,
    ts_code TEXT NOT NULL UNIQUE,
    company_name TEXT NOT NULL,
    exchange TEXT,
    industry_l1 TEXT,
    industry_l2 TEXT,
    business_scope TEXT,
    core_products TEXT,
    concept_tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_companies_company_name_trgm
    ON companies
    USING gin (company_name gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_companies_industry_l1
    ON companies (industry_l1);

CREATE INDEX IF NOT EXISTS idx_companies_industry_l2
    ON companies (industry_l2);

CREATE TABLE IF NOT EXISTS event_company_links (
    id BIGSERIAL PRIMARY KEY,
    structured_event_id BIGINT NOT NULL REFERENCES structured_events(id) ON DELETE CASCADE,
    company_id BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    link_type TEXT NOT NULL DEFAULT 'candidate',
    relation_path TEXT,
    text_similarity_score NUMERIC(6,4),
    industry_match_score NUMERIC(6,4),
    chain_position_score NUMERIC(6,4),
    event_match_score NUMERIC(6,4),
    final_link_score NUMERIC(6,4),
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_manual_override BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (structured_event_id, company_id, link_type)
);

CREATE INDEX IF NOT EXISTS idx_event_company_links_event
    ON event_company_links (structured_event_id);

CREATE INDEX IF NOT EXISTS idx_event_company_links_company
    ON event_company_links (company_id);

CREATE INDEX IF NOT EXISTS idx_event_company_links_final_score
    ON event_company_links (final_link_score DESC);

CREATE INDEX IF NOT EXISTS idx_event_company_links_link_type
    ON event_company_links (link_type);
