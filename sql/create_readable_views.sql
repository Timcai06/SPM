-- Readable layer for PostgreSQL:
-- 1) Keep base table names unchanged for pipeline safety.
-- 2) Add table comments for pgAdmin readability.
-- 3) Add simple English views and Chinese alias views for human inspection.

BEGIN;

-- ----------------------------
-- Table comments (Task 1/2/3)
-- ----------------------------
COMMENT ON TABLE raw_documents IS '任务1：原始文本表（采集后的新闻/公告/政策正文）';
COMMENT ON TABLE event_candidates IS '任务1：事件候选表（is_event 判定与证据）';
COMMENT ON TABLE structured_events IS '任务1：结构化事件表（标准化分类与量化特征）';
COMMENT ON TABLE companies IS '任务2：公司主数据表（股票代码、行业、主营与概念）';
COMMENT ON TABLE event_company_links IS '任务2：事件-公司关联表（关联类型与关联强度）';
COMMENT ON TABLE company_relations IS '任务3：公司关系边表（供应链/同产业链等）';
COMMENT ON TABLE event_propagation_links IS '任务3：事件传播边表（一跳或多跳传播结果）';

-- ---------------------------------
-- Simple English views (no behavior)
-- ---------------------------------
CREATE OR REPLACE VIEW events_raw AS
SELECT * FROM raw_documents;

CREATE OR REPLACE VIEW events_candidates AS
SELECT * FROM event_candidates;

CREATE OR REPLACE VIEW events_structured AS
SELECT * FROM structured_events;

CREATE OR REPLACE VIEW stock_companies AS
SELECT * FROM companies;

CREATE OR REPLACE VIEW event_stock_links AS
SELECT * FROM event_company_links;

CREATE OR REPLACE VIEW stock_relations AS
SELECT * FROM company_relations;

CREATE OR REPLACE VIEW event_propagations AS
SELECT * FROM event_propagation_links;

-- ------------------------------------
-- Chinese alias views for UI readability
-- ------------------------------------
CREATE OR REPLACE VIEW "事件原文" AS
SELECT * FROM raw_documents;

CREATE OR REPLACE VIEW "事件候选" AS
SELECT * FROM event_candidates;

CREATE OR REPLACE VIEW "结构化事件" AS
SELECT * FROM structured_events;

CREATE OR REPLACE VIEW "公司主数据" AS
SELECT * FROM companies;

CREATE OR REPLACE VIEW "事件公司关联" AS
SELECT * FROM event_company_links;

CREATE OR REPLACE VIEW "公司关系边" AS
SELECT * FROM company_relations;

CREATE OR REPLACE VIEW "事件传播边" AS
SELECT * FROM event_propagation_links;

COMMIT;
