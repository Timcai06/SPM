BEGIN;

DO $$
DECLARE
    view_name text;
BEGIN
    FOREACH view_name IN ARRAY ARRAY[
        'document_facts',
        'event_candidate_facts',
        'event_records',
        'event_cluster_records',
        'event_cluster_memberships',
        'security_master',
        'security_profile_snapshots',
        'security_quotes_daily',
        'market_context_daily',
        'sentiment_network_daily',
        'security_market_features_daily',
        'security_features_daily',
        'security_forward_labels_daily',
        'event_security_links',
        'security_relation_edges',
        'event_propagation_edges',
        'event_research_samples',
        'control_research_samples',
        'run_registry',
        'run_step_registry',
        'dataset_registry',
        'event_candidates',
        'event_candidates_stage',
        'structured_events_stage',
        'canonical_events',
        'event_canonical_links',
        'company_stats',
        'model_non_event_samples',
        'event_propagation_links',
        'events_raw',
        'events_candidates',
        'events_structured',
        'events_canonical',
        'stock_companies',
        'stock_company_stats',
        'event_stock_links',
        'stock_relations',
        'event_propagations',
        'structured_events_delivery_cn',
        '事件原文',
        '事件候选',
        '结构化事件',
        '标准事件簇',
        '公司主数据',
        '公司衍生特征',
        '事件公司关联',
        '公司关系边',
        '事件传播边'
    ]
    LOOP
        IF EXISTS (
            SELECT 1
            FROM pg_views
            WHERE schemaname = 'public'
              AND viewname = view_name
        ) THEN
            EXECUTE format('DROP VIEW public.%I CASCADE', view_name);
        END IF;
    END LOOP;
END $$;

DO $$
BEGIN
    IF to_regclass('public.int_event_candidates') IS NOT NULL
       AND to_regclass('public.event_candidates') IS NULL THEN
        EXECUTE 'ALTER TABLE public.int_event_candidates RENAME TO event_candidates';
    END IF;

    IF to_regclass('public.int_event_candidates_stage') IS NOT NULL
       AND to_regclass('public.stg_event_candidates') IS NULL THEN
        EXECUTE 'ALTER TABLE public.int_event_candidates_stage RENAME TO stg_event_candidates';
    END IF;

    IF to_regclass('public.int_structured_events_stage') IS NOT NULL
       AND to_regclass('public.stg_structured_events') IS NULL THEN
        EXECUTE 'ALTER TABLE public.int_structured_events_stage RENAME TO stg_structured_events';
    END IF;

    IF to_regclass('public.int_canonical_events') IS NOT NULL
       AND to_regclass('public.canonical_event_clusters') IS NULL THEN
        EXECUTE 'ALTER TABLE public.int_canonical_events RENAME TO canonical_event_clusters';
    END IF;

    IF to_regclass('public.int_event_canonical_links') IS NOT NULL
       AND to_regclass('public.canonical_event_memberships') IS NULL THEN
        EXECUTE 'ALTER TABLE public.int_event_canonical_links RENAME TO canonical_event_memberships';
    END IF;

    IF to_regclass('public.int_company_stats') IS NOT NULL
       AND to_regclass('public.security_features_daily') IS NULL THEN
        EXECUTE 'ALTER TABLE public.int_company_stats RENAME TO security_features_daily';
    END IF;

    IF to_regclass('public.int_event_propagation_links') IS NOT NULL
       AND to_regclass('public.event_propagation_edges') IS NULL THEN
        EXECUTE 'ALTER TABLE public.int_event_propagation_links RENAME TO event_propagation_edges';
    END IF;

    IF to_regclass('public.model_event_samples') IS NOT NULL
       AND to_regclass('public.event_research_samples') IS NULL THEN
        EXECUTE 'ALTER TABLE public.model_event_samples RENAME TO event_research_samples';
    END IF;

    IF to_regclass('public.int_model_non_event_samples') IS NOT NULL
       AND to_regclass('public.control_research_samples') IS NULL THEN
        EXECUTE 'ALTER TABLE public.int_model_non_event_samples RENAME TO control_research_samples';
    END IF;
END $$;

ALTER INDEX IF EXISTS public.int_event_candidates_pkey RENAME TO event_candidates_pkey;
ALTER INDEX IF EXISTS public.int_event_candidates_raw_document_id_key RENAME TO event_candidates_raw_document_id_key;
ALTER INDEX IF EXISTS public.idx_int_event_candidates_is_event RENAME TO idx_event_candidates_is_event;
ALTER INDEX IF EXISTS public.idx_int_event_candidates_dedup_key RENAME TO idx_event_candidates_dedup_key;

ALTER INDEX IF EXISTS public.int_company_stats_pkey RENAME TO security_features_daily_pkey;
ALTER INDEX IF EXISTS public.int_company_stats_ts_code_trade_date_key RENAME TO security_features_daily_ts_code_trade_date_key;
ALTER INDEX IF EXISTS public.idx_int_company_stats_trade_date RENAME TO idx_security_features_daily_trade_date;
ALTER INDEX IF EXISTS public.idx_int_company_stats_ts_code_trade_date RENAME TO idx_security_features_daily_ts_code_trade_date;

ALTER INDEX IF EXISTS public.model_event_samples_pkey RENAME TO event_research_samples_pkey;
ALTER INDEX IF EXISTS public.model_event_samples_sample_key_key RENAME TO event_research_samples_sample_key_key;
ALTER INDEX IF EXISTS public.idx_model_event_samples_event_date RENAME TO idx_event_research_samples_event_date;
ALTER INDEX IF EXISTS public.idx_model_event_samples_ts_code RENAME TO idx_event_research_samples_ts_code;
ALTER INDEX IF EXISTS public.idx_model_event_samples_subject RENAME TO idx_event_research_samples_subject;
ALTER INDEX IF EXISTS public.idx_model_event_samples_final_link RENAME TO idx_event_research_samples_final_link;

ALTER INDEX IF EXISTS public.int_model_non_event_samples_pkey RENAME TO control_research_samples_pkey;
ALTER INDEX IF EXISTS public.int_model_non_event_samples_sample_key_key RENAME TO control_research_samples_sample_key_key;
ALTER INDEX IF EXISTS public.idx_int_model_non_event_samples_sample_date RENAME TO idx_control_research_samples_sample_date;
ALTER INDEX IF EXISTS public.idx_int_model_non_event_samples_ts_code RENAME TO idx_control_research_samples_ts_code;

ALTER INDEX IF EXISTS public.int_canonical_events_pkey RENAME TO canonical_event_clusters_pkey;
ALTER INDEX IF EXISTS public.int_canonical_events_canonical_event_id_key RENAME TO canonical_event_clusters_canonical_event_id_key;
ALTER INDEX IF EXISTS public.idx_int_canonical_events_date_start RENAME TO idx_canonical_event_clusters_date_start;
ALTER INDEX IF EXISTS public.idx_int_canonical_events_subject_type RENAME TO idx_canonical_event_clusters_subject_type;

ALTER INDEX IF EXISTS public.int_event_canonical_links_pkey RENAME TO canonical_event_memberships_pkey;
ALTER INDEX IF EXISTS public.int_event_canonical_links_structured_event_id_key RENAME TO canonical_event_memberships_structured_event_id_key;
ALTER INDEX IF EXISTS public.idx_int_event_canonical_links_canonical_event RENAME TO idx_canonical_event_memberships_canonical_event;

ALTER INDEX IF EXISTS public.int_event_propagation_links_pkey RENAME TO event_propagation_edges_pkey;
ALTER INDEX IF EXISTS public.int_event_propagation_links_unique_key RENAME TO event_propagation_edges_unique_key;
ALTER INDEX IF EXISTS public.idx_int_event_propagation_links_event RENAME TO idx_event_propagation_edges_event;
ALTER INDEX IF EXISTS public.idx_int_event_propagation_links_source RENAME TO idx_event_propagation_edges_source;
ALTER INDEX IF EXISTS public.idx_int_event_propagation_links_target RENAME TO idx_event_propagation_edges_target;
ALTER INDEX IF EXISTS public.idx_int_event_propagation_links_score RENAME TO idx_event_propagation_edges_score;

COMMIT;
