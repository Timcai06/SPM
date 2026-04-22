DO $$
DECLARE
    rec record;
BEGIN
    FOR rec IN
        SELECT *
        FROM (
            VALUES
                ('raw_documents', 'Raw fact layer: ingested source documents with original publish time, URL, and content.'),
                ('event_candidates', 'Intermediate fact layer: event candidacy screening results derived from raw_documents.'),
                ('stg_event_candidates', 'Staging layer: transient rows used to load event_candidates safely.'),
                ('structured_events', 'Curated event layer: normalized event records with classification and event features.'),
                ('stg_structured_events', 'Staging layer: transient rows used to load structured_events safely.'),
                ('canonical_event_clusters', 'Event clustering layer: canonical event clusters that group related structured events.'),
                ('canonical_event_memberships', 'Event clustering layer: membership links from structured_events into canonical_event_clusters.'),
                ('companies', 'Security master layer: listed security universe keyed by ts_code with issuer-level descriptive fields.'),
                ('company_profiles', 'Snapshot enrichment layer: sparse point-in-time company profile snapshots and descriptive metadata.'),
                ('stock_daily_quotes', 'Market fact layer: daily OHLCV and trading state for each listed security.'),
                ('market_environment_daily', 'Market context layer: benchmark, breadth, flow, and cross-market daily aggregates.'),
                ('sentiment_propagation_daily', 'Market sentiment layer: daily sentiment and propagation context aggregates.'),
                ('security_features_daily', 'Research panel layer: daily point-in-time security market features.'),
                ('security_forward_labels_daily', 'Research label layer: daily forward-return labels keyed by security and trade_date.'),
                ('event_company_links', 'Linking layer: scored mappings from structured_events to listed securities.'),
                ('company_relations', 'Graph layer: relation edges between listed securities or issuers.'),
                ('event_propagation_edges', 'Graph layer: propagated event-to-security edges derived from company_relations.'),
                ('event_research_samples', 'Research sample layer: event-linked supervised samples for return and direction studies.'),
                ('control_research_samples', 'Research sample layer: non-event control samples aligned to event_research_samples.'),
                ('label_dictionary', 'Reference layer: label taxonomy and dictionary values used by classification and reporting.'),
                ('etl_runs', 'Runtime governance layer: top-level ETL and research command runs.'),
                ('etl_run_steps', 'Runtime governance layer: step-level lineage and status records within an etl_run.'),
                ('dataset_versions', 'Runtime governance layer: registered dataset artifacts produced by ETL or research runs.')
        ) AS t(table_name, table_comment)
    LOOP
        IF to_regclass(format('public.%s', rec.table_name)) IS NOT NULL THEN
            EXECUTE format('COMMENT ON TABLE public.%I IS %L', rec.table_name, rec.table_comment);
        END IF;
    END LOOP;
END $$;
