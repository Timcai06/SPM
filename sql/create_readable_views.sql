-- Readable layer for PostgreSQL:
-- 1) Internal physical tables use int_ prefix.
-- 2) Old internal table names remain as read-only compatibility views.
-- 3) Add readable comments and helper alias views for pgAdmin inspection.

BEGIN;

-- ----------------------------
-- Table comments (Task 1/2/3)
-- ----------------------------
COMMENT ON TABLE raw_documents IS '任务1：原始文本表（采集后的新闻/公告/政策正文）';
COMMENT ON TABLE int_event_candidates IS '任务1内部层：事件候选表（is_event 判定与证据）';
COMMENT ON TABLE structured_events IS '任务1：结构化事件表（标准化分类与量化特征）';
COMMENT ON TABLE companies IS '任务2：公司主数据表（股票代码、行业、主营与概念）';
COMMENT ON TABLE event_company_links IS '任务2：事件-公司关联表（关联类型与关联强度）';
COMMENT ON TABLE company_relations IS '任务3：公司关系边表（供应链/同产业链等）';
COMMENT ON TABLE int_event_propagation_links IS '任务3内部层：事件传播边表（一跳或多跳传播结果）';
COMMENT ON TABLE int_canonical_events IS '任务1内部层：标准事件簇表';
COMMENT ON TABLE int_event_canonical_links IS '任务1内部层：结构化事件与标准事件映射表';
COMMENT ON TABLE int_company_stats IS '内部层：公司日频衍生特征表';
COMMENT ON TABLE int_model_non_event_samples IS '内部层：非事件负样本表';

-- ----------------------------------------
-- Compatibility views for renamed internals
-- ----------------------------------------
CREATE OR REPLACE VIEW event_candidates AS
SELECT * FROM int_event_candidates;

CREATE OR REPLACE VIEW event_candidates_stage AS
SELECT * FROM int_event_candidates_stage;

CREATE OR REPLACE VIEW structured_events_stage AS
SELECT * FROM int_structured_events_stage;

CREATE OR REPLACE VIEW canonical_events AS
SELECT * FROM int_canonical_events;

CREATE OR REPLACE VIEW event_canonical_links AS
SELECT * FROM int_event_canonical_links;

CREATE OR REPLACE VIEW company_stats AS
SELECT * FROM int_company_stats;

CREATE OR REPLACE VIEW model_non_event_samples AS
SELECT * FROM int_model_non_event_samples;

CREATE OR REPLACE VIEW event_propagation_links AS
SELECT * FROM int_event_propagation_links;

-- ---------------------------------
-- Simple English views (no behavior)
-- ---------------------------------
CREATE OR REPLACE VIEW events_raw AS
SELECT * FROM raw_documents;

CREATE OR REPLACE VIEW events_candidates AS
SELECT * FROM int_event_candidates;

CREATE OR REPLACE VIEW events_structured AS
SELECT * FROM structured_events;

CREATE OR REPLACE VIEW events_canonical AS
SELECT * FROM int_canonical_events;

CREATE OR REPLACE VIEW stock_companies AS
SELECT * FROM companies;

CREATE OR REPLACE VIEW stock_company_stats AS
SELECT * FROM int_company_stats;

CREATE OR REPLACE VIEW event_stock_links AS
SELECT * FROM event_company_links;

CREATE OR REPLACE VIEW stock_relations AS
SELECT * FROM company_relations;

CREATE OR REPLACE VIEW event_propagations AS
SELECT * FROM int_event_propagation_links;

-- ------------------------------------
-- Chinese alias views for UI readability
-- ------------------------------------
CREATE OR REPLACE VIEW "事件原文" AS
SELECT * FROM raw_documents;

CREATE OR REPLACE VIEW "事件候选" AS
SELECT * FROM int_event_candidates;

CREATE OR REPLACE VIEW "结构化事件" AS
SELECT * FROM structured_events;

CREATE OR REPLACE VIEW "标准事件簇" AS
SELECT * FROM int_canonical_events;

CREATE OR REPLACE VIEW "公司主数据" AS
SELECT * FROM companies;

CREATE OR REPLACE VIEW "公司衍生特征" AS
SELECT * FROM int_company_stats;

CREATE OR REPLACE VIEW "事件公司关联" AS
SELECT * FROM event_company_links;

CREATE OR REPLACE VIEW "公司关系边" AS
SELECT * FROM company_relations;

CREATE OR REPLACE VIEW "事件传播边" AS
SELECT * FROM int_event_propagation_links;

COMMIT;
