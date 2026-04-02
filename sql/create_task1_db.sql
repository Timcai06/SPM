CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS raw_documents (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'text_source',
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    publish_time TIMESTAMP NOT NULL,
    url TEXT NOT NULL UNIQUE,
    symbol_or_subject TEXT,
    content_hash TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_raw_documents_publish_time
    ON raw_documents (publish_time DESC);

CREATE INDEX IF NOT EXISTS idx_raw_documents_source
    ON raw_documents (source);

CREATE INDEX IF NOT EXISTS idx_raw_documents_content_hash
    ON raw_documents (content_hash);

CREATE INDEX IF NOT EXISTS idx_raw_documents_title_trgm
    ON raw_documents
    USING gin (title gin_trgm_ops);

CREATE TABLE IF NOT EXISTS event_candidates (
    id BIGSERIAL PRIMARY KEY,
    raw_document_id BIGINT NOT NULL REFERENCES raw_documents(id) ON DELETE CASCADE,
    dedup_key TEXT NOT NULL,
    duplicate_group_size INTEGER NOT NULL,
    is_event BOOLEAN NOT NULL,
    filter_reason TEXT NOT NULL,
    evidence TEXT,
    score_hint INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (raw_document_id)
);

CREATE INDEX IF NOT EXISTS idx_event_candidates_is_event
    ON event_candidates (is_event);

CREATE INDEX IF NOT EXISTS idx_event_candidates_dedup_key
    ON event_candidates (dedup_key);

CREATE TABLE IF NOT EXISTS structured_events (
    id BIGSERIAL PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE,
    candidate_id BIGINT NOT NULL REFERENCES event_candidates(id) ON DELETE CASCADE,
    event_name TEXT NOT NULL,
    event_date DATE NOT NULL,
    source TEXT NOT NULL,
    event_subject_type TEXT NOT NULL,
    duration_type TEXT NOT NULL,
    predictability_type TEXT NOT NULL,
    industry_type TEXT NOT NULL,
    sentiment TEXT NOT NULL,
    heat_score INTEGER NOT NULL,
    intensity_score INTEGER NOT NULL,
    impact_scope TEXT NOT NULL,
    event_summary TEXT NOT NULL,
    subject_entities JSONB NOT NULL DEFAULT '[]'::jsonb,
    raw_text_ref TEXT NOT NULL,
    classification_evidence TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (candidate_id)
);

CREATE INDEX IF NOT EXISTS idx_structured_events_event_date
    ON structured_events (event_date DESC);

CREATE INDEX IF NOT EXISTS idx_structured_events_subject_type
    ON structured_events (event_subject_type);

CREATE INDEX IF NOT EXISTS idx_structured_events_industry_type
    ON structured_events (industry_type);

CREATE INDEX IF NOT EXISTS idx_structured_events_sentiment
    ON structured_events (sentiment);

CREATE TABLE IF NOT EXISTS label_dictionary (
    id BIGSERIAL PRIMARY KEY,
    label_group TEXT NOT NULL,
    label_value TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (label_group, label_value)
);

INSERT INTO label_dictionary (label_group, label_value, description) VALUES
    ('event_subject_type', '政策类', '政策法规、通知、实施方案等'),
    ('event_subject_type', '公司类', '公告、合同、并购、回购等公司事件'),
    ('event_subject_type', '行业类', '行业供需、景气、技术突破等'),
    ('event_subject_type', '宏观类', '经济数据、财政、货币等宏观事件'),
    ('event_subject_type', '地缘类', '战争、冲突、国际局势等'),
    ('duration_type', '脉冲型', '影响集中在短周期'),
    ('duration_type', '中期型', '影响持续数周到数月'),
    ('duration_type', '长尾型', '影响长期存在'),
    ('predictability_type', '突发型', '事前较难预测'),
    ('predictability_type', '预披露型', '可从公告或安排提前获知'),
    ('industry_type', '军工', '军工产业链'),
    ('industry_type', '新能源', '新能源与储能'),
    ('industry_type', '科技', '科技、AI、机器人、芯片'),
    ('industry_type', '消费', '消费、零售、旅游'),
    ('industry_type', '其他', '未归入核心行业')
ON CONFLICT (label_group, label_value) DO NOTHING;
