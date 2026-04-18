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

CREATE TABLE IF NOT EXISTS int_event_candidates (
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

CREATE INDEX IF NOT EXISTS idx_int_event_candidates_is_event
    ON int_event_candidates (is_event);

CREATE INDEX IF NOT EXISTS idx_int_event_candidates_dedup_key
    ON int_event_candidates (dedup_key);

CREATE TABLE IF NOT EXISTS structured_events (
    id BIGSERIAL PRIMARY KEY,
    event_id TEXT NOT NULL,
    candidate_id BIGINT NOT NULL REFERENCES int_event_candidates(id) ON DELETE CASCADE,
    event_name TEXT NOT NULL,
    event_date DATE NOT NULL,
    source TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT '其他来源',
    authority_level TEXT NOT NULL DEFAULT 'general_media',
    source_credibility_score NUMERIC(4,2) NOT NULL DEFAULT 1,
    event_subject_type TEXT NOT NULL,
    event_subject_subtype TEXT NOT NULL DEFAULT '未细分',
    duration_type TEXT NOT NULL,
    predictability_type TEXT NOT NULL,
    industry_type TEXT NOT NULL,
    sentiment TEXT NOT NULL,
    time_orientation TEXT NOT NULL DEFAULT 'current_confirmed',
    event_stage TEXT NOT NULL DEFAULT '确认',
    shock_source_type TEXT NOT NULL DEFAULT '其他',
    region_scope TEXT NOT NULL DEFAULT 'domestic',
    trigger_word_score INTEGER NOT NULL DEFAULT 0,
    explicitness_score INTEGER NOT NULL DEFAULT 0,
    uncertainty_score INTEGER NOT NULL DEFAULT 0,
    novelty_score INTEGER NOT NULL DEFAULT 50,
    amount_scale TEXT NOT NULL DEFAULT 'none',
    amount_max_rmb NUMERIC,
    amount_log_rmb NUMERIC,
    event_code TEXT NOT NULL DEFAULT '',
    sw_l1_industry TEXT NOT NULL DEFAULT '其他',
    sw_l1_industry_code TEXT NOT NULL DEFAULT '',
    sentiment_score_0_100 INTEGER NOT NULL DEFAULT 50,
    source_credibility_type TEXT NOT NULL DEFAULT '单一媒体',
    company_count INTEGER NOT NULL DEFAULT 0,
    industry_count INTEGER NOT NULL DEFAULT 0,
    province_count INTEGER NOT NULL DEFAULT 0,
    city_count INTEGER NOT NULL DEFAULT 0,
    country_count INTEGER NOT NULL DEFAULT 0,
    chain_stage_count INTEGER NOT NULL DEFAULT 0,
    chain_stages JSONB NOT NULL DEFAULT '[]'::jsonb,
    report_count INTEGER NOT NULL DEFAULT 0,
    media_coverage_count INTEGER NOT NULL DEFAULT 0,
    heat_growth_rate NUMERIC(10,6) NOT NULL DEFAULT 0,
    heat_duration_days INTEGER NOT NULL DEFAULT 0,
    disagreement_score NUMERIC(10,6) NOT NULL DEFAULT 0,
    classification_confidence NUMERIC(5,4) NOT NULL DEFAULT 0.5,
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

CREATE INDEX IF NOT EXISTS idx_structured_events_event_id
    ON structured_events (event_id);

CREATE INDEX IF NOT EXISTS idx_structured_events_subject_type
    ON structured_events (event_subject_type);

CREATE INDEX IF NOT EXISTS idx_structured_events_industry_type
    ON structured_events (industry_type);

CREATE INDEX IF NOT EXISTS idx_structured_events_sentiment
    ON structured_events (sentiment);

ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS source_type TEXT NOT NULL DEFAULT '其他来源';
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS authority_level TEXT NOT NULL DEFAULT 'general_media';
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS source_credibility_score NUMERIC(4,2) NOT NULL DEFAULT 1;
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS event_subject_subtype TEXT NOT NULL DEFAULT '未细分';
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS time_orientation TEXT NOT NULL DEFAULT 'current_confirmed';
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS event_stage TEXT NOT NULL DEFAULT '确认';
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS shock_source_type TEXT NOT NULL DEFAULT '其他';
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS region_scope TEXT NOT NULL DEFAULT 'domestic';
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS trigger_word_score INTEGER NOT NULL DEFAULT 0;
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS explicitness_score INTEGER NOT NULL DEFAULT 0;
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS uncertainty_score INTEGER NOT NULL DEFAULT 0;
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS novelty_score INTEGER NOT NULL DEFAULT 50;
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS amount_scale TEXT NOT NULL DEFAULT 'none';
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS amount_max_rmb NUMERIC;
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS amount_log_rmb NUMERIC;
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS event_code TEXT NOT NULL DEFAULT '';
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS sw_l1_industry TEXT NOT NULL DEFAULT '其他';
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS sw_l1_industry_code TEXT NOT NULL DEFAULT '';
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS sentiment_score_0_100 INTEGER NOT NULL DEFAULT 50;
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS source_credibility_type TEXT NOT NULL DEFAULT '单一媒体';
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS company_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS industry_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS province_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS city_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS country_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS chain_stage_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS chain_stages JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS report_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS media_coverage_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS heat_growth_rate NUMERIC(10,6) NOT NULL DEFAULT 0;
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS heat_duration_days INTEGER NOT NULL DEFAULT 0;
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS disagreement_score NUMERIC(10,6) NOT NULL DEFAULT 0;
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS classification_confidence NUMERIC(5,4) NOT NULL DEFAULT 0.5;
CREATE INDEX IF NOT EXISTS idx_structured_events_sw_l1_industry
    ON structured_events (sw_l1_industry);
CREATE INDEX IF NOT EXISTS idx_structured_events_sentiment_score
    ON structured_events (sentiment_score_0_100);
ALTER TABLE structured_events DROP CONSTRAINT IF EXISTS structured_events_event_id_key;
CREATE INDEX IF NOT EXISTS idx_structured_events_event_id
    ON structured_events (event_id);

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
    ('event_subject_subtype', '未细分', '未命中更细分的二级主体'),
    ('event_subject_subtype', '产业政策', '产业政策、实施方案、行动计划'),
    ('event_subject_subtype', '监管政策', '监管规则、交易所或部委监管要求'),
    ('event_subject_subtype', '财政税收', '财政政策、税收调整、专项资金'),
    ('event_subject_subtype', '货币金融', '货币政策、利率、社融、金融条件'),
    ('event_subject_subtype', '补贴政策', '补贴、奖励、支持资金'),
    ('event_subject_subtype', '行业规范', '行业规范、指导意见、标准要求'),
    ('event_subject_subtype', '业绩公告', '业绩预告、财报、经营业绩披露'),
    ('event_subject_subtype', '重大合同', '重大订单、合同、项目签约'),
    ('event_subject_subtype', '产能投产', '扩产、投产、项目落地'),
    ('event_subject_subtype', '产品发布', '新产品、新型号、新服务发布'),
    ('event_subject_subtype', '高管变动', '董事、高管、核心人员变动'),
    ('event_subject_subtype', '股权变动', '股东变更、减持增持、股权转让'),
    ('event_subject_subtype', '诉讼仲裁', '诉讼、仲裁、处罚、追偿'),
    ('event_subject_subtype', '回购增持', '回购、增持、股权激励'),
    ('event_subject_subtype', '供需价格', '供需变化、价格调整、景气变化'),
    ('event_subject_subtype', '展会峰会', '行业展会、峰会、论坛'),
    ('event_subject_subtype', '技术标准', '技术标准、规范、认证'),
    ('event_subject_subtype', '进出口政策', '进出口限制、关税、配额'),
    ('event_subject_subtype', '行业整合', '行业并购、集中度变化、产能出清'),
    ('event_subject_subtype', '宏观数据', 'GDP、CPI、PPI、PMI、就业等数据'),
    ('event_subject_subtype', '贸易摩擦', '贸易争端、关税冲突'),
    ('event_subject_subtype', '国际制裁', '国际制裁、封锁、禁运'),
    ('event_subject_subtype', '区域冲突', '地区战争、边境冲突、军事摩擦'),
    ('event_subject_subtype', '外交关系', '外交关系变化、双边互动'),
    ('event_subject_subtype', '国际公约', '国际协定、公约、条约'),
    ('event_subject_subtype', '公共卫生', '疫情、防疫、公共卫生冲击'),
    ('event_subject_subtype', '安全事故', '事故、爆炸、停产等突发冲击'),
    ('event_subject_subtype', '自然灾害', '地震、洪水、极端天气等'),
    ('event_subject_subtype', '技术系统冲击', '网络、系统、供应链技术故障'),
    ('duration_type', '脉冲型', '影响集中在短周期'),
    ('duration_type', '中期型', '影响持续数周到数月'),
    ('duration_type', '长尾型', '影响长期存在'),
    ('predictability_type', '突发型', '事前较难预测'),
    ('predictability_type', '预披露型', '可从公告或安排提前获知'),
    ('predictability_type', '渐进演化型', '事件非单点爆发而是逐步演化'),
    ('industry_type', '军工', '军工产业链'),
    ('industry_type', '新能源', '新能源与储能'),
    ('industry_type', '科技', '科技、AI、机器人、芯片'),
    ('industry_type', '消费', '消费、零售、旅游'),
    ('industry_type', '其他', '未归入核心行业'),
    ('source_type', '官方文件', '国务院、部委、统计等官方原文'),
    ('source_type', '监管/交易所', '证监会、交易所、监管公告'),
    ('source_type', '公司公告', '上市公司正式公告、财报、官网披露'),
    ('source_type', '主流财经媒体', '权威财经媒体或资讯平台'),
    ('source_type', '行业协会', '行业协会、商会、联盟等机构渠道'),
    ('source_type', '社交媒体转发', '微博、公众号、论坛、二次转述'),
    ('source_type', '其他来源', '无法归类或低结构化来源'),
    ('authority_level', 'central', '中央级官方主体'),
    ('authority_level', 'ministry', '部委级官方主体'),
    ('authority_level', 'exchange', '交易所或监管执行机构'),
    ('authority_level', 'listed_company', '上市公司正式披露'),
    ('authority_level', 'top_media', '头部权威媒体'),
    ('authority_level', 'industry_association', '行业协会或专业机构'),
    ('authority_level', 'general_media', '普通财经媒体或资讯平台'),
    ('authority_level', 'social_media', '社交媒体、自媒体、论坛'),
    ('sentiment', '利好', '对相关资产形成正向影响'),
    ('sentiment', '利空', '对相关资产形成负向影响'),
    ('sentiment', '中性', '影响方向不明确或总体中性'),
    ('time_orientation', 'future_oriented', '事件指向未来预期或计划'),
    ('time_orientation', 'current_confirmed', '事件已确认并正在发生'),
    ('time_orientation', 'retrospective', '事件是回顾、追溯或复盘'),
    ('event_stage', '预期', '政策或事项仍处于预期阶段'),
    ('event_stage', '确认', '事件已明确发生或被正式确认'),
    ('event_stage', '落地/执行', '事件进入执行、实施或兑现阶段'),
    ('event_stage', '反馈', '市场或基本面进入反馈阶段'),
    ('shock_source_type', '自然灾害', '自然环境造成的外生冲击'),
    ('shock_source_type', '公共卫生', '疫情、疾病传播等公共卫生冲击'),
    ('shock_source_type', '安全事故', '事故、爆炸、停产等安全冲击'),
    ('shock_source_type', '地缘政治', '战争、冲突、国际政治摩擦'),
    ('shock_source_type', '政策制度', '政策、制度、监管变化'),
    ('shock_source_type', '金融事件', '金融体系或资本市场冲击'),
    ('shock_source_type', '供应链冲击', '供应链中断、物流阻塞等冲击'),
    ('shock_source_type', '技术革新', '技术创新或替代带来的冲击'),
    ('shock_source_type', '技术系统冲击', '系统故障、网络攻击、技术事故'),
    ('shock_source_type', '其他', '未归入既有冲击源'),
    ('region_scope', 'domestic', '主要影响中国大陆市场'),
    ('region_scope', 'regional', '主要影响国内局部区域或集群'),
    ('region_scope', 'overseas', '主要影响境外区域市场'),
    ('region_scope', 'global', '影响全球或跨主要市场'),
    ('impact_scope', '个股链条', '兼容旧值：影响单一公司或单条产业链'),
    ('impact_scope', '行业', '兼容旧值：影响单一行业或主题板块'),
    ('impact_scope', '全市场', '兼容旧值：影响全市场或大类资产情绪'),
    ('impact_scope', '单主体', '影响单公司/单机构/单项目'),
    ('impact_scope', '多主体', '影响多公司或多机构'),
    ('impact_scope', '产业链面', '影响产业链上下游多个环节'),
    ('impact_scope', '行业面', '影响单一行业'),
    ('impact_scope', '跨行业面', '影响两个及以上行业'),
    ('impact_scope', '区域面', '影响省市或城市群'),
    ('impact_scope', '全国面', '影响全国市场'),
    ('impact_scope', '全球面', '影响全球或跨国市场')
ON CONFLICT (label_group, label_value) DO NOTHING;
