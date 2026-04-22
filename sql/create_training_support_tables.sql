CREATE TABLE IF NOT EXISTS security_forward_labels_daily (
    id BIGSERIAL PRIMARY KEY,
    ts_code TEXT NOT NULL REFERENCES companies(ts_code) ON DELETE CASCADE,
    trade_date DATE NOT NULL,
    forward_return_1d NUMERIC(12,6),
    forward_return_3d NUMERIC(12,6),
    forward_return_5d NUMERIC(12,6),
    data_source TEXT NOT NULL DEFAULT 'tushare',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (ts_code, trade_date)
);

DO $$
BEGIN
    IF to_regclass('public.security_market_features_daily') IS NOT NULL THEN
        INSERT INTO security_forward_labels_daily (
            ts_code,
            trade_date,
            forward_return_1d,
            forward_return_3d,
            forward_return_5d,
            data_source,
            created_at,
            updated_at
        )
        SELECT
            ts_code,
            trade_date,
            forward_return_1d,
            forward_return_3d,
            forward_return_5d,
            data_source,
            created_at,
            updated_at
        FROM security_market_features_daily
        ON CONFLICT (ts_code, trade_date) DO UPDATE
        SET
            forward_return_1d = EXCLUDED.forward_return_1d,
            forward_return_3d = EXCLUDED.forward_return_3d,
            forward_return_5d = EXCLUDED.forward_return_5d,
            data_source = EXCLUDED.data_source,
            updated_at = NOW();

        IF to_regclass('public.security_features_daily') IS NULL THEN
            ALTER TABLE security_market_features_daily RENAME TO security_features_daily;
        ELSE
            INSERT INTO security_features_daily (
                ts_code,
                trade_date,
                total_mv,
                circ_mv,
                pe_ttm,
                pb,
                turnover_rate,
                volume_ratio,
                daily_return,
                trailing_return_5d,
                trailing_return_20d,
                trailing_return_60d,
                volatility_5d,
                volatility_20d,
                volatility_60d,
                up_days_20d,
                data_source,
                created_at,
                updated_at
            )
            SELECT
                ts_code,
                trade_date,
                total_mv,
                circ_mv,
                pe_ttm,
                pb,
                turnover_rate,
                volume_ratio,
                daily_return,
                trailing_return_5d,
                trailing_return_20d,
                trailing_return_60d,
                volatility_5d,
                volatility_20d,
                volatility_60d,
                up_days_20d,
                data_source,
                created_at,
                updated_at
            FROM security_market_features_daily
            ON CONFLICT (ts_code, trade_date) DO UPDATE
            SET
                total_mv = EXCLUDED.total_mv,
                circ_mv = EXCLUDED.circ_mv,
                pe_ttm = EXCLUDED.pe_ttm,
                pb = EXCLUDED.pb,
                turnover_rate = EXCLUDED.turnover_rate,
                volume_ratio = EXCLUDED.volume_ratio,
                daily_return = EXCLUDED.daily_return,
                trailing_return_5d = EXCLUDED.trailing_return_5d,
                trailing_return_20d = EXCLUDED.trailing_return_20d,
                trailing_return_60d = EXCLUDED.trailing_return_60d,
                volatility_5d = EXCLUDED.volatility_5d,
                volatility_20d = EXCLUDED.volatility_20d,
                volatility_60d = EXCLUDED.volatility_60d,
                up_days_20d = EXCLUDED.up_days_20d,
                data_source = EXCLUDED.data_source,
                updated_at = NOW();

            DROP TABLE security_market_features_daily;
        END IF;
    END IF;

    IF to_regclass('public.security_features_daily') IS NOT NULL
       AND EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'security_features_daily'
              AND column_name = 'forward_return_1d'
       ) THEN
        INSERT INTO security_forward_labels_daily (
            ts_code,
            trade_date,
            forward_return_1d,
            forward_return_3d,
            forward_return_5d,
            data_source,
            created_at,
            updated_at
        )
        SELECT
            ts_code,
            trade_date,
            forward_return_1d,
            forward_return_3d,
            forward_return_5d,
            data_source,
            created_at,
            updated_at
        FROM security_features_daily
        ON CONFLICT (ts_code, trade_date) DO UPDATE
        SET
            forward_return_1d = EXCLUDED.forward_return_1d,
            forward_return_3d = EXCLUDED.forward_return_3d,
            forward_return_5d = EXCLUDED.forward_return_5d,
            data_source = EXCLUDED.data_source,
            updated_at = NOW();
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS security_features_daily (
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
    data_source TEXT NOT NULL DEFAULT 'tushare',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (ts_code, trade_date)
);

ALTER INDEX IF EXISTS security_market_features_daily_pkey RENAME TO security_features_daily_pkey;
ALTER INDEX IF EXISTS idx_security_market_features_daily_ts_code_trade_date RENAME TO idx_security_features_daily_ts_code_trade_date;
ALTER INDEX IF EXISTS idx_security_market_features_daily_trade_date RENAME TO idx_security_features_daily_trade_date;

DO $$
BEGIN
    IF to_regclass('public.security_features_daily') IS NOT NULL
       AND EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conrelid = 'public.security_features_daily'::regclass
              AND conname = 'security_market_features_daily_ts_code_trade_date_key'
       ) THEN
        ALTER TABLE security_features_daily
            RENAME CONSTRAINT security_market_features_daily_ts_code_trade_date_key
            TO security_features_daily_ts_code_trade_date_key;
    END IF;

    IF to_regclass('public.security_features_daily') IS NOT NULL
       AND EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conrelid = 'public.security_features_daily'::regclass
              AND conname = 'int_company_stats_ts_code_fkey'
       ) THEN
        ALTER TABLE security_features_daily
            RENAME CONSTRAINT int_company_stats_ts_code_fkey
            TO security_features_daily_ts_code_fkey;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_security_features_daily_ts_code_trade_date
    ON security_features_daily (ts_code, trade_date DESC);

CREATE INDEX IF NOT EXISTS idx_security_features_daily_trade_date
    ON security_features_daily (trade_date DESC);

CREATE INDEX IF NOT EXISTS idx_security_forward_labels_daily_ts_code_trade_date
    ON security_forward_labels_daily (ts_code, trade_date DESC);

CREATE INDEX IF NOT EXISTS idx_security_forward_labels_daily_trade_date
    ON security_forward_labels_daily (trade_date DESC);

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
ALTER TABLE structured_events ADD COLUMN IF NOT EXISTS event_code TEXT NOT NULL DEFAULT '';
ALTER TABLE structured_events DROP CONSTRAINT IF EXISTS structured_events_event_id_key;
CREATE INDEX IF NOT EXISTS idx_structured_events_event_id
    ON structured_events (event_id);

CREATE TABLE IF NOT EXISTS company_profiles (
    id BIGSERIAL PRIMARY KEY,
    ts_code TEXT NOT NULL REFERENCES companies(ts_code) ON DELETE CASCADE,
    snapshot_date DATE NOT NULL,
    company_name TEXT NOT NULL,
    exchange TEXT,
    industry_l1 TEXT,
    industry_l2 TEXT,
    concept_tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    region TEXT,
    list_date DATE,
    state_owned_flag BOOLEAN,
    company_type TEXT,
    business_scope TEXT,
    core_products JSONB NOT NULL DEFAULT '[]'::jsonb,
    main_customers JSONB NOT NULL DEFAULT '[]'::jsonb,
    main_suppliers JSONB NOT NULL DEFAULT '[]'::jsonb,
    employees INTEGER,
    total_shares NUMERIC(18,4),
    float_shares NUMERIC(18,4),
    data_source TEXT NOT NULL DEFAULT 'companies_seed',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (ts_code, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_company_profiles_ts_code
    ON company_profiles (ts_code);

CREATE TABLE IF NOT EXISTS stock_daily_quotes (
    id BIGSERIAL PRIMARY KEY,
    ts_code TEXT NOT NULL REFERENCES companies(ts_code) ON DELETE CASCADE,
    trade_date DATE NOT NULL,
    open NUMERIC(18,4),
    high NUMERIC(18,4),
    low NUMERIC(18,4),
    close NUMERIC(18,4) NOT NULL,
    pre_close NUMERIC(18,4),
    pct_chg NUMERIC(12,6),
    volume NUMERIC(24,4),
    amount NUMERIC(24,4),
    turnover_rate NUMERIC(18,4),
    adj_factor NUMERIC(18,6),
    is_suspended BOOLEAN NOT NULL DEFAULT FALSE,
    is_st BOOLEAN NOT NULL DEFAULT FALSE,
    is_limit_up BOOLEAN NOT NULL DEFAULT FALSE,
    is_limit_down BOOLEAN NOT NULL DEFAULT FALSE,
    data_source TEXT NOT NULL DEFAULT 'sina',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (ts_code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_stock_daily_quotes_trade_date
    ON stock_daily_quotes (trade_date DESC);

CREATE INDEX IF NOT EXISTS idx_stock_daily_quotes_ts_code_trade_date
    ON stock_daily_quotes (ts_code, trade_date DESC);

CREATE TABLE IF NOT EXISTS market_environment_daily (
    id BIGSERIAL PRIMARY KEY,
    trade_date DATE NOT NULL UNIQUE,
    benchmark_code TEXT,
    benchmark_name TEXT,
    index_return_1d NUMERIC(12,6),
    index_return_5d NUMERIC(12,6),
    index_volatility_20d NUMERIC(12,6),
    market_turnover NUMERIC(24,4),
    up_count INTEGER,
    down_count INTEGER,
    limit_up_count INTEGER,
    limit_down_count INTEGER,
    northbound_net_flow NUMERIC(24,4),
    sector_hotness JSONB NOT NULL DEFAULT '{}'::jsonb,
    cross_market_count INTEGER,
    risk_on_off_score NUMERIC(12,6),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sentiment_propagation_daily (
    id BIGSERIAL PRIMARY KEY,
    canonical_event_id TEXT NOT NULL,
    stat_date DATE NOT NULL,
    source_channel TEXT NOT NULL,
    mention_count INTEGER NOT NULL DEFAULT 0,
    media_count INTEGER NOT NULL DEFAULT 0,
    authority_media_count INTEGER NOT NULL DEFAULT 0,
    repost_count INTEGER NOT NULL DEFAULT 0,
    search_index NUMERIC(18,4),
    heat_score NUMERIC(12,6),
    heat_growth_rate NUMERIC(12,6),
    heat_duration_days INTEGER,
    sentiment_pos_count INTEGER NOT NULL DEFAULT 0,
    sentiment_neg_count INTEGER NOT NULL DEFAULT 0,
    sentiment_neu_count INTEGER NOT NULL DEFAULT 0,
    disagreement_score NUMERIC(12,6),
    sentiment_std NUMERIC(12,6),
    source_stance_divergence NUMERIC(12,6),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (canonical_event_id, stat_date, source_channel)
);

CREATE INDEX IF NOT EXISTS idx_sentiment_propagation_daily_event_date
    ON sentiment_propagation_daily (canonical_event_id, stat_date DESC);

ALTER TABLE security_features_daily ADD COLUMN IF NOT EXISTS trailing_return_5d NUMERIC(12,6);
ALTER TABLE security_features_daily ADD COLUMN IF NOT EXISTS trailing_return_60d NUMERIC(12,6);
ALTER TABLE security_features_daily ADD COLUMN IF NOT EXISTS volatility_5d NUMERIC(12,6);
ALTER TABLE security_features_daily ADD COLUMN IF NOT EXISTS volatility_60d NUMERIC(12,6);
ALTER TABLE security_features_daily ADD COLUMN IF NOT EXISTS up_days_20d INTEGER;
ALTER TABLE security_features_daily DROP COLUMN IF EXISTS forward_return_1d;
ALTER TABLE security_features_daily DROP COLUMN IF EXISTS forward_return_3d;
ALTER TABLE security_features_daily DROP COLUMN IF EXISTS forward_return_5d;

ALTER TABLE security_forward_labels_daily ADD COLUMN IF NOT EXISTS forward_return_1d NUMERIC(12,6);
ALTER TABLE security_forward_labels_daily ADD COLUMN IF NOT EXISTS forward_return_3d NUMERIC(12,6);
ALTER TABLE security_forward_labels_daily ADD COLUMN IF NOT EXISTS forward_return_5d NUMERIC(12,6);

ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS company_stat_date DATE;
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS event_subject_subtype TEXT;
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS source_type TEXT;
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS authority_level TEXT;
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS source_credibility_score NUMERIC(4,2);
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS time_orientation TEXT;
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS event_stage TEXT;
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS shock_source_type TEXT;
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS region_scope TEXT;
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS trigger_word_score INTEGER;
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS explicitness_score INTEGER;
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS uncertainty_score INTEGER;
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS novelty_score INTEGER;
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS amount_scale TEXT;
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS event_code TEXT;
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS impact_level_score INTEGER;
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS affected_company_count INTEGER;
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS affected_industry_count INTEGER;
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS relation_rank_in_event INTEGER;
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS industry_match_score NUMERIC(8,4);
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS concept_match_count INTEGER;
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS event_age_days INTEGER;
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS event_trade_alignment_type TEXT;
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS total_mv NUMERIC(18,4);
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS circ_mv NUMERIC(18,4);
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS pe_ttm NUMERIC(18,4);
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS pb NUMERIC(18,4);
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS turnover_rate NUMERIC(18,4);
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS volume_ratio NUMERIC(18,4);
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS trailing_return_5d NUMERIC(12,6);
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS trailing_return_20d NUMERIC(12,6);
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS trailing_return_60d NUMERIC(12,6);
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS volatility_5d NUMERIC(12,6);
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS volatility_20d NUMERIC(12,6);
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS volatility_60d NUMERIC(12,6);
ALTER TABLE event_research_samples ADD COLUMN IF NOT EXISTS up_days_20d INTEGER;

CREATE TABLE IF NOT EXISTS control_research_samples (
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
    label_source TEXT NOT NULL DEFAULT 'security_forward_labels_daily',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_control_research_samples_sample_date
    ON control_research_samples (sample_date DESC);

CREATE INDEX IF NOT EXISTS idx_control_research_samples_ts_code
    ON control_research_samples (ts_code);

ALTER TABLE control_research_samples ADD COLUMN IF NOT EXISTS trailing_return_5d NUMERIC(12,6);
ALTER TABLE control_research_samples ADD COLUMN IF NOT EXISTS trailing_return_60d NUMERIC(12,6);
ALTER TABLE control_research_samples ADD COLUMN IF NOT EXISTS volatility_5d NUMERIC(12,6);
ALTER TABLE control_research_samples ADD COLUMN IF NOT EXISTS volatility_60d NUMERIC(12,6);
ALTER TABLE control_research_samples ADD COLUMN IF NOT EXISTS up_days_20d INTEGER;
ALTER TABLE control_research_samples ALTER COLUMN label_source SET DEFAULT 'security_forward_labels_daily';
UPDATE control_research_samples
SET label_source = 'security_forward_labels_daily'
WHERE label_source = 'security_market_features_daily';
