BEGIN;

-- Drop compatibility views if a prior migration attempt created them.
DO $$
DECLARE
    name TEXT;
BEGIN
    FOREACH name IN ARRAY ARRAY[
        'event_candidates',
        'event_candidates_stage',
        'structured_events_stage',
        'canonical_events',
        'event_canonical_links',
        'company_stats',
        'model_non_event_samples',
        'event_propagation_links'
    ]
    LOOP
        IF EXISTS (
            SELECT 1
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relname = name
              AND c.relkind = 'v'
        ) THEN
            EXECUTE format('DROP VIEW %I CASCADE', name);
        END IF;
    END LOOP;
END $$;

-- Group 1: candidate and stage tables
DO $$
BEGIN
    IF to_regclass('public.event_candidates') IS NOT NULL AND to_regclass('public.int_event_candidates') IS NULL THEN
        EXECUTE 'ALTER TABLE event_candidates RENAME TO int_event_candidates';
    END IF;
    IF to_regclass('public.event_candidates_id_seq') IS NOT NULL AND to_regclass('public.int_event_candidates_id_seq') IS NULL THEN
        EXECUTE 'ALTER SEQUENCE event_candidates_id_seq RENAME TO int_event_candidates_id_seq';
    END IF;
END $$;

ALTER TABLE IF EXISTS int_event_candidates RENAME CONSTRAINT event_candidates_pkey TO int_event_candidates_pkey;
ALTER TABLE IF EXISTS int_event_candidates RENAME CONSTRAINT event_candidates_raw_document_id_key TO int_event_candidates_raw_document_id_key;
ALTER INDEX IF EXISTS idx_event_candidates_is_event RENAME TO idx_int_event_candidates_is_event;
ALTER INDEX IF EXISTS idx_event_candidates_dedup_key RENAME TO idx_int_event_candidates_dedup_key;

DO $$
BEGIN
    IF to_regclass('public.event_candidates_stage') IS NOT NULL AND to_regclass('public.int_event_candidates_stage') IS NULL THEN
        EXECUTE 'ALTER TABLE event_candidates_stage RENAME TO int_event_candidates_stage';
    END IF;
    IF to_regclass('public.structured_events_stage') IS NOT NULL AND to_regclass('public.int_structured_events_stage') IS NULL THEN
        EXECUTE 'ALTER TABLE structured_events_stage RENAME TO int_structured_events_stage';
    END IF;
END $$;

-- Group 2: canonical internal tables
DO $$
BEGIN
    IF to_regclass('public.canonical_events') IS NOT NULL AND to_regclass('public.int_canonical_events') IS NULL THEN
        EXECUTE 'ALTER TABLE canonical_events RENAME TO int_canonical_events';
    END IF;
    IF to_regclass('public.canonical_events_id_seq') IS NOT NULL AND to_regclass('public.int_canonical_events_id_seq') IS NULL THEN
        EXECUTE 'ALTER SEQUENCE canonical_events_id_seq RENAME TO int_canonical_events_id_seq';
    END IF;
    IF to_regclass('public.event_canonical_links') IS NOT NULL AND to_regclass('public.int_event_canonical_links') IS NULL THEN
        EXECUTE 'ALTER TABLE event_canonical_links RENAME TO int_event_canonical_links';
    END IF;
    IF to_regclass('public.event_canonical_links_id_seq') IS NOT NULL AND to_regclass('public.int_event_canonical_links_id_seq') IS NULL THEN
        EXECUTE 'ALTER SEQUENCE event_canonical_links_id_seq RENAME TO int_event_canonical_links_id_seq';
    END IF;
END $$;

ALTER TABLE IF EXISTS int_canonical_events RENAME CONSTRAINT canonical_events_pkey TO int_canonical_events_pkey;
ALTER TABLE IF EXISTS int_canonical_events RENAME CONSTRAINT canonical_events_canonical_event_id_key TO int_canonical_events_canonical_event_id_key;
ALTER INDEX IF EXISTS idx_canonical_events_date_start RENAME TO idx_int_canonical_events_date_start;
ALTER INDEX IF EXISTS idx_canonical_events_subject_type RENAME TO idx_int_canonical_events_subject_type;

ALTER TABLE IF EXISTS int_event_canonical_links RENAME CONSTRAINT event_canonical_links_pkey TO int_event_canonical_links_pkey;
ALTER TABLE IF EXISTS int_event_canonical_links RENAME CONSTRAINT event_canonical_links_structured_event_id_key TO int_event_canonical_links_structured_event_id_key;
ALTER TABLE IF EXISTS int_event_canonical_links RENAME CONSTRAINT event_canonical_links_structured_event_id_fkey TO int_event_canonical_links_structured_event_id_fkey;
ALTER TABLE IF EXISTS int_event_canonical_links RENAME CONSTRAINT event_canonical_links_canonical_event_id_fkey TO int_event_canonical_links_canonical_event_id_fkey;
ALTER INDEX IF EXISTS idx_event_canonical_links_canonical_event RENAME TO idx_int_event_canonical_links_canonical_event;

-- Group 3: feature and negative sample internal tables
DO $$
BEGIN
    IF to_regclass('public.company_stats') IS NOT NULL AND to_regclass('public.int_company_stats') IS NULL THEN
        EXECUTE 'ALTER TABLE company_stats RENAME TO int_company_stats';
    END IF;
    IF to_regclass('public.company_stats_id_seq') IS NOT NULL AND to_regclass('public.int_company_stats_id_seq') IS NULL THEN
        EXECUTE 'ALTER SEQUENCE company_stats_id_seq RENAME TO int_company_stats_id_seq';
    END IF;
    IF to_regclass('public.model_non_event_samples') IS NOT NULL AND to_regclass('public.int_model_non_event_samples') IS NULL THEN
        EXECUTE 'ALTER TABLE model_non_event_samples RENAME TO int_model_non_event_samples';
    END IF;
    IF to_regclass('public.model_non_event_samples_id_seq') IS NOT NULL AND to_regclass('public.int_model_non_event_samples_id_seq') IS NULL THEN
        EXECUTE 'ALTER SEQUENCE model_non_event_samples_id_seq RENAME TO int_model_non_event_samples_id_seq';
    END IF;
END $$;

ALTER TABLE IF EXISTS int_company_stats RENAME CONSTRAINT company_stats_pkey TO int_company_stats_pkey;
ALTER TABLE IF EXISTS int_company_stats RENAME CONSTRAINT company_stats_ts_code_trade_date_key TO int_company_stats_ts_code_trade_date_key;
ALTER TABLE IF EXISTS int_company_stats RENAME CONSTRAINT company_stats_ts_code_fkey TO int_company_stats_ts_code_fkey;
ALTER INDEX IF EXISTS idx_company_stats_trade_date RENAME TO idx_int_company_stats_trade_date;
ALTER INDEX IF EXISTS idx_company_stats_ts_code_trade_date RENAME TO idx_int_company_stats_ts_code_trade_date;

ALTER TABLE IF EXISTS int_model_non_event_samples RENAME CONSTRAINT model_non_event_samples_pkey TO int_model_non_event_samples_pkey;
ALTER TABLE IF EXISTS int_model_non_event_samples RENAME CONSTRAINT model_non_event_samples_sample_key_key TO int_model_non_event_samples_sample_key_key;
ALTER TABLE IF EXISTS int_model_non_event_samples RENAME CONSTRAINT model_non_event_samples_company_id_fkey TO int_model_non_event_samples_company_id_fkey;
ALTER INDEX IF EXISTS idx_model_non_event_samples_sample_date RENAME TO idx_int_model_non_event_samples_sample_date;
ALTER INDEX IF EXISTS idx_model_non_event_samples_ts_code RENAME TO idx_int_model_non_event_samples_ts_code;

-- Group 4: graph enhancement internal table
DO $$
BEGIN
    IF to_regclass('public.event_propagation_links') IS NOT NULL AND to_regclass('public.int_event_propagation_links') IS NULL THEN
        EXECUTE 'ALTER TABLE event_propagation_links RENAME TO int_event_propagation_links';
    END IF;
    IF to_regclass('public.event_propagation_links_id_seq') IS NOT NULL AND to_regclass('public.int_event_propagation_links_id_seq') IS NULL THEN
        EXECUTE 'ALTER SEQUENCE event_propagation_links_id_seq RENAME TO int_event_propagation_links_id_seq';
    END IF;
END $$;

ALTER TABLE IF EXISTS int_event_propagation_links RENAME CONSTRAINT event_propagation_links_pkey TO int_event_propagation_links_pkey;
ALTER TABLE IF EXISTS int_event_propagation_links RENAME CONSTRAINT event_propagation_links_structured_event_id_source_company__key TO int_event_propagation_links_unique_key;
ALTER TABLE IF EXISTS int_event_propagation_links RENAME CONSTRAINT event_propagation_links_relation_id_fkey TO int_event_propagation_links_relation_id_fkey;
ALTER TABLE IF EXISTS int_event_propagation_links RENAME CONSTRAINT event_propagation_links_source_company_id_fkey TO int_event_propagation_links_source_company_id_fkey;
ALTER TABLE IF EXISTS int_event_propagation_links RENAME CONSTRAINT event_propagation_links_structured_event_id_fkey TO int_event_propagation_links_structured_event_id_fkey;
ALTER TABLE IF EXISTS int_event_propagation_links RENAME CONSTRAINT event_propagation_links_target_company_id_fkey TO int_event_propagation_links_target_company_id_fkey;
ALTER INDEX IF EXISTS idx_event_propagation_links_event RENAME TO idx_int_event_propagation_links_event;
ALTER INDEX IF EXISTS idx_event_propagation_links_source RENAME TO idx_int_event_propagation_links_source;
ALTER INDEX IF EXISTS idx_event_propagation_links_target RENAME TO idx_int_event_propagation_links_target;
ALTER INDEX IF EXISTS idx_event_propagation_links_score RENAME TO idx_int_event_propagation_links_score;

COMMIT;

\i sql/create_readable_views.sql
