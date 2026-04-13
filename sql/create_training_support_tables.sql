CREATE TABLE IF NOT EXISTS int_company_stats (
    id BIGSERIAL PRIMARY KEY,
    ts_code TEXT NOT NULL REFERENCES companies(ts_code) ON DELETE CASCADE,
    trade_date DATE NOT NULL,
    total_mv NUMERIC(18,4),
    circ_mv NUMERIC(18,4),
    pe_ttm NUMERIC(18,4),
    pb NUMERIC(18,4),
    turnover_rate NUMERIC(18,4),
    volume_ratio NUMERIC(18,4),
    daily_return NUMERIC(12,6),
    trailing_return_5d NUMERIC(12,6),
    trailing_return_20d NUMERIC(12,6),
    trailing_return_60d NUMERIC(12,6),
    volatility_5d NUMERIC(12,6),
    volatility_20d NUMERIC(12,6),
    volatility_60d NUMERIC(12,6),
    up_days_20d INTEGER,
    forward_return_1d NUMERIC(12,6),
    forward_return_3d NUMERIC(12,6),
    forward_return_5d NUMERIC(12,6),
    data_source TEXT NOT NULL DEFAULT 'tushare',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (ts_code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_int_company_stats_ts_code_trade_date
    ON int_company_stats (ts_code, trade_date DESC);

CREATE INDEX IF NOT EXISTS idx_int_company_stats_trade_date
    ON int_company_stats (trade_date DESC);

ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS source_type TEXT NOT NULL DEFAULT '其他来源';
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS source_credibility_score NUMERIC(4,2) NOT NULL DEFAULT 1;
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS event_subject_subtype TEXT NOT NULL DEFAULT '未细分';
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS event_stage TEXT NOT NULL DEFAULT '确认';
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS shock_source_type TEXT NOT NULL DEFAULT '其他';
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS trigger_word_score INTEGER NOT NULL DEFAULT 0;
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS explicitness_score INTEGER NOT NULL DEFAULT 0;
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS uncertainty_score INTEGER NOT NULL DEFAULT 0;
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS novelty_score INTEGER NOT NULL DEFAULT 50;
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS event_code TEXT NOT NULL DEFAULT '';

ALTER TABLE int_company_stats ADD COLUMN IF NOT EXISTS trailing_return_5d NUMERIC(12,6);
ALTER TABLE int_company_stats ADD COLUMN IF NOT EXISTS trailing_return_60d NUMERIC(12,6);
ALTER TABLE int_company_stats ADD COLUMN IF NOT EXISTS volatility_5d NUMERIC(12,6);
ALTER TABLE int_company_stats ADD COLUMN IF NOT EXISTS volatility_60d NUMERIC(12,6);
ALTER TABLE int_company_stats ADD COLUMN IF NOT EXISTS up_days_20d INTEGER;

ALTER TABLE model_event_samples ADD COLUMN IF NOT EXISTS company_stat_date DATE;
ALTER TABLE model_event_samples ADD COLUMN IF NOT EXISTS event_subject_subtype TEXT;
ALTER TABLE model_event_samples ADD COLUMN IF NOT EXISTS source_type TEXT;
ALTER TABLE model_event_samples ADD COLUMN IF NOT EXISTS source_credibility_score NUMERIC(4,2);
ALTER TABLE model_event_samples ADD COLUMN IF NOT EXISTS event_stage TEXT;
ALTER TABLE model_event_samples ADD COLUMN IF NOT EXISTS shock_source_type TEXT;
ALTER TABLE model_event_samples ADD COLUMN IF NOT EXISTS trigger_word_score INTEGER;
ALTER TABLE model_event_samples ADD COLUMN IF NOT EXISTS explicitness_score INTEGER;
ALTER TABLE model_event_samples ADD COLUMN IF NOT EXISTS uncertainty_score INTEGER;
ALTER TABLE model_event_samples ADD COLUMN IF NOT EXISTS novelty_score INTEGER;
ALTER TABLE model_event_samples ADD COLUMN IF NOT EXISTS event_code TEXT;
ALTER TABLE model_event_samples ADD COLUMN IF NOT EXISTS impact_level_score INTEGER;
ALTER TABLE model_event_samples ADD COLUMN IF NOT EXISTS affected_company_count INTEGER;
ALTER TABLE model_event_samples ADD COLUMN IF NOT EXISTS affected_industry_count INTEGER;
ALTER TABLE model_event_samples ADD COLUMN IF NOT EXISTS relation_rank_in_event INTEGER;
ALTER TABLE model_event_samples ADD COLUMN IF NOT EXISTS total_mv NUMERIC(18,4);
ALTER TABLE model_event_samples ADD COLUMN IF NOT EXISTS circ_mv NUMERIC(18,4);
ALTER TABLE model_event_samples ADD COLUMN IF NOT EXISTS pe_ttm NUMERIC(18,4);
ALTER TABLE model_event_samples ADD COLUMN IF NOT EXISTS pb NUMERIC(18,4);
ALTER TABLE model_event_samples ADD COLUMN IF NOT EXISTS turnover_rate NUMERIC(18,4);
ALTER TABLE model_event_samples ADD COLUMN IF NOT EXISTS volume_ratio NUMERIC(18,4);
ALTER TABLE model_event_samples ADD COLUMN IF NOT EXISTS trailing_return_5d NUMERIC(12,6);
ALTER TABLE model_event_samples ADD COLUMN IF NOT EXISTS trailing_return_20d NUMERIC(12,6);
ALTER TABLE model_event_samples ADD COLUMN IF NOT EXISTS trailing_return_60d NUMERIC(12,6);
ALTER TABLE model_event_samples ADD COLUMN IF NOT EXISTS volatility_5d NUMERIC(12,6);
ALTER TABLE model_event_samples ADD COLUMN IF NOT EXISTS volatility_20d NUMERIC(12,6);
ALTER TABLE model_event_samples ADD COLUMN IF NOT EXISTS volatility_60d NUMERIC(12,6);
ALTER TABLE model_event_samples ADD COLUMN IF NOT EXISTS up_days_20d INTEGER;

CREATE TABLE IF NOT EXISTS int_model_non_event_samples (
    id BIGSERIAL PRIMARY KEY,
    sample_key TEXT NOT NULL UNIQUE,
    sample_run_id TEXT NOT NULL,
    sample_date DATE NOT NULL,
    company_id BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    ts_code TEXT NOT NULL,
    company_name TEXT NOT NULL,
    company_industry_l1 TEXT,
    company_industry_l2 TEXT,
    concept_tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    company_stat_date DATE,
    total_mv NUMERIC(18,4),
    circ_mv NUMERIC(18,4),
    pe_ttm NUMERIC(18,4),
    pb NUMERIC(18,4),
    turnover_rate NUMERIC(18,4),
    volume_ratio NUMERIC(18,4),
    trailing_return_5d NUMERIC(12,6),
    trailing_return_20d NUMERIC(12,6),
    trailing_return_60d NUMERIC(12,6),
    volatility_5d NUMERIC(12,6),
    volatility_20d NUMERIC(12,6),
    volatility_60d NUMERIC(12,6),
    up_days_20d INTEGER,
    label_ret_w1 NUMERIC(12,6),
    label_ret_w3 NUMERIC(12,6),
    label_ret_w5 NUMERIC(12,6),
    label_up_w1 BOOLEAN,
    label_up_w3 BOOLEAN,
    label_up_w5 BOOLEAN,
    label_source TEXT NOT NULL DEFAULT 'int_company_stats',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_int_model_non_event_samples_sample_date
    ON int_model_non_event_samples (sample_date DESC);

CREATE INDEX IF NOT EXISTS idx_int_model_non_event_samples_ts_code
    ON int_model_non_event_samples (ts_code);

ALTER TABLE int_model_non_event_samples ADD COLUMN IF NOT EXISTS trailing_return_5d NUMERIC(12,6);
ALTER TABLE int_model_non_event_samples ADD COLUMN IF NOT EXISTS trailing_return_60d NUMERIC(12,6);
ALTER TABLE int_model_non_event_samples ADD COLUMN IF NOT EXISTS volatility_5d NUMERIC(12,6);
ALTER TABLE int_model_non_event_samples ADD COLUMN IF NOT EXISTS volatility_60d NUMERIC(12,6);
ALTER TABLE int_model_non_event_samples ADD COLUMN IF NOT EXISTS up_days_20d INTEGER;
