\pset pager off

\echo '=== Raw Coverage Window ==='
SELECT
  :'start_date' AS start_date_inclusive,
  :'end_date' AS end_date_exclusive,
  :top_n AS top_n;

\echo ''
\echo '=== Source Family Summary (2025/2026 focus) ==='
WITH windowed AS (
  SELECT
    source,
    count(*) FILTER (
      WHERE publish_time >= timestamp :'start_date'
        AND publish_time < timestamp :'end_date'
    ) AS rows_2025_2026,
    count(*) FILTER (
      WHERE publish_time >= timestamp :'start_date'
        AND publish_time < timestamp :'end_date'
        AND length(coalesce(content, '')) >= 300
        AND btrim(coalesce(content, '')) <> btrim(title)
        AND btrim(coalesce(content, '')) <> btrim(regexp_replace(title, '^[^：:]+[：:]', ''))
    ) AS qualified_fulltext_rows
  FROM raw_documents
  GROUP BY source
),
family AS (
  SELECT
    CASE
      WHEN source = '巨潮资讯网/历史公告' THEN 'CNInfo 历史公告'
      WHEN source = '巨潮资讯网/最新公告' THEN 'CNInfo 最新公告'
      WHEN source IN ('上交所/最新公告', '上交所') THEN '上交所公告'
      WHEN source = '深交所/上市公司公告' THEN '深交所公告'
      WHEN source = '深交所/停复牌公告' THEN '深交所停复牌'
      WHEN source LIKE '中国政府网/%' OR source = '中国政府网' THEN '中国政府网'
      WHEN source LIKE '国家发改委/%' THEN '国家发改委'
      WHEN source LIKE '中国证监会/%' THEN '中国证监会'
      WHEN source LIKE '工信部/%' THEN '工信部'
      WHEN source IN ('东方财富/行业资讯', '东方财富网') THEN '东方财富行业资讯'
      WHEN source LIKE '36氪/%' OR source = '36氪' THEN '36氪'
      WHEN source LIKE '财新网/%' OR source = '财新网' THEN '财新网'
      WHEN source LIKE '第一财经/%' OR source = '第一财经' THEN '第一财经'
      WHEN source LIKE 'AKShare/EastMoney/%' THEN 'AKShare/EastMoney 新闻聚合'
      ELSE '其他'
    END AS source_family,
    rows_2025_2026,
    qualified_fulltext_rows
  FROM windowed
)
SELECT
  source_family,
  sum(rows_2025_2026) AS rows_2025_2026,
  sum(qualified_fulltext_rows) AS qualified_fulltext_rows,
  round(100.0 * sum(qualified_fulltext_rows) / nullif(sum(rows_2025_2026), 0), 2) AS qualified_pct
FROM family
WHERE rows_2025_2026 > 0
GROUP BY source_family
ORDER BY rows_2025_2026 DESC, source_family;

\echo ''
\echo '=== Non-CNInfo Source Balance Snapshot ==='
WITH base AS (
  SELECT
    source,
    count(*) FILTER (
      WHERE publish_time >= timestamp :'start_date'
        AND publish_time < timestamp :'end_date'
    ) AS rows_2025_2026
  FROM raw_documents
  GROUP BY source
)
SELECT
  min(rows_2025_2026) AS min_rows,
  max(rows_2025_2026) AS max_rows,
  percentile_cont(0.5) WITHIN GROUP (ORDER BY rows_2025_2026) AS median_rows,
  percentile_cont(0.75) WITHIN GROUP (ORDER BY rows_2025_2026) AS p75_rows
FROM base
WHERE rows_2025_2026 > 0
  AND source <> '巨潮资讯网/历史公告';

\echo ''
\echo '=== Source Coverage (raw_documents) ==='
WITH base AS (
  SELECT
    source,
    count(*) FILTER (
      WHERE publish_time >= timestamp :'start_date'
        AND publish_time < timestamp :'end_date'
    ) AS rows_2025_2026,
    count(*) FILTER (
      WHERE publish_time >= timestamp :'start_date'
        AND publish_time < timestamp :'end_date'
        AND nullif(btrim(coalesce(content, '')), '') IS NOT NULL
    ) AS nonempty_content_rows,
    count(*) FILTER (
      WHERE publish_time >= timestamp :'start_date'
        AND publish_time < timestamp :'end_date'
        AND length(coalesce(content, '')) >= 300
        AND btrim(coalesce(content, '')) <> btrim(title)
        AND btrim(coalesce(content, '')) <> btrim(regexp_replace(title, '^[^：:]+[：:]', ''))
    ) AS qualified_fulltext_rows
  FROM raw_documents
  GROUP BY source
)
SELECT
  source,
  rows_2025_2026,
  nonempty_content_rows,
  qualified_fulltext_rows,
  round(100.0 * qualified_fulltext_rows / nullif(rows_2025_2026, 0), 2) AS qualified_pct,
  CASE
    WHEN source = '巨潮资讯网/历史公告' THEN 'keep_fulltext_backfill_for_2025_2026'
    WHEN rows_2025_2026 < 50 THEN 'expand_2025_2026_collection'
    WHEN qualified_fulltext_rows = 0 THEN 'source_is_thin_or_has_no_detail_backfill'
    WHEN round(100.0 * qualified_fulltext_rows / nullif(rows_2025_2026, 0), 2) < 50 THEN 'improve_fulltext_fill_rate'
    ELSE 'keep_collecting'
  END AS action_hint
FROM base
WHERE rows_2025_2026 > 0
ORDER BY rows_2025_2026 DESC, source
LIMIT :top_n;
