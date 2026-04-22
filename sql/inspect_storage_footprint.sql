\pset pager off
\echo '=== Database Size ==='
SELECT
  current_database() AS db_name,
  pg_size_pretty(pg_database_size(current_database())) AS db_size;

\echo ''
\echo '=== Largest User Tables ==='
SELECT
  schemaname,
  relname AS table_name,
  n_live_tup AS est_rows,
  pg_size_pretty(pg_total_relation_size(relid)) AS total_size
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 20;

\echo ''
\echo '=== Core Pipeline Tables ==='
SELECT
  relname AS table_name,
  n_live_tup AS est_rows,
  pg_size_pretty(pg_total_relation_size(relid)) AS total_size
FROM pg_stat_user_tables
WHERE relname IN (
  'raw_documents',
  'event_candidates',
  'structured_events',
  'stg_event_candidates',
  'stg_structured_events',
  'event_company_links',
  'security_features_daily',
  'security_forward_labels_daily'
)
ORDER BY pg_total_relation_size(relid) DESC;

\echo ''
\echo '=== raw_documents by Source ==='
SELECT
  source,
  count(*) AS rows,
  pg_size_pretty(sum(pg_column_size(t.*))) AS approx_heap
FROM raw_documents t
GROUP BY source
ORDER BY count(*) DESC
LIMIT 20;

\echo ''
\echo '=== raw_documents by Year ==='
WITH yearly AS (
  SELECT
    date_part('year', publish_time)::int AS year,
    count(*) AS rows,
    count(*) FILTER (
      WHERE length(coalesce(content, '')) >= 300
        AND btrim(coalesce(content, '')) <> btrim(title)
        AND btrim(coalesce(content, '')) <> btrim(regexp_replace(title, '^[^：:]+[：:]', ''))
    ) AS qualified_rows
  FROM raw_documents
  GROUP BY 1
)
SELECT
  year,
  rows,
  qualified_rows,
  round(100.0 * qualified_rows / nullif(rows, 0), 2) AS qualified_pct
FROM yearly
ORDER BY year;
