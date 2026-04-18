#!/usr/bin/env python3
"""Backfill cluster-level stats onto structured_events."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import psycopg

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.storage.db_guard import dsn_for, write_guard


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh cluster-level stats for structured_events.")
    parser.add_argument("--db", default="stock_event_mining")
    parser.add_argument("--lock-timeout-sec", type=int, default=120)
    return parser.parse_args()


def refresh_cluster_stats(db_name: str, lock_timeout_sec: int = 120) -> int:
    sql = """
    CREATE TEMP TABLE se_cluster_base ON COMMIT DROP AS
    SELECT
        se.id, se.event_date, se.source, se.sentiment,
        md5(regexp_replace(lower(coalesce(se.event_name, '')), '\\s+', '', 'g')
            || '|' || coalesce(se.event_subject_type, '')
            || '|' || coalesce(se.industry_type, '')) AS cluster_key
    FROM structured_events se;
    CREATE INDEX ON se_cluster_base (cluster_key, event_date);

    CREATE TEMP TABLE se_cluster_daily ON COMMIT DROP AS
    SELECT cluster_key, event_date, count(*) AS reports, count(DISTINCT source) AS media_cov,
           count(*) FILTER (WHERE sentiment = '利好') AS pos_cnt,
           count(*) FILTER (WHERE sentiment = '中性') AS neu_cnt,
           count(*) FILTER (WHERE sentiment = '利空') AS neg_cnt
    FROM se_cluster_base
    GROUP BY cluster_key, event_date;

    CREATE TEMP TABLE se_cluster_global ON COMMIT DROP AS
    SELECT cluster_key, sum(reports) AS report_count,
           count(*) FILTER (WHERE reports > 0) AS heat_duration_days
    FROM se_cluster_daily
    GROUP BY cluster_key;

    CREATE TEMP TABLE se_source_cov ON COMMIT DROP AS
    SELECT cluster_key, count(DISTINCT source) AS media_coverage_count
    FROM se_cluster_base
    GROUP BY cluster_key;

    CREATE TEMP TABLE se_cluster_enriched ON COMMIT DROP AS
    SELECT b.id, g.report_count, s.media_coverage_count, g.heat_duration_days,
           CASE WHEN prev.reports IS NULL THEN 0::numeric
                ELSE round((curr.reports - prev.reports)::numeric / (prev.reports + 1), 6)
           END AS heat_growth_rate,
           CASE WHEN curr.reports <= 0 THEN 0::numeric
                ELSE round(
                    (CASE WHEN curr.pos_cnt > 0 THEN -(curr.pos_cnt::numeric / curr.reports) * ln(curr.pos_cnt::numeric / curr.reports) ELSE 0 END
                   + CASE WHEN curr.neu_cnt > 0 THEN -(curr.neu_cnt::numeric / curr.reports) * ln(curr.neu_cnt::numeric / curr.reports) ELSE 0 END
                   + CASE WHEN curr.neg_cnt > 0 THEN -(curr.neg_cnt::numeric / curr.reports) * ln(curr.neg_cnt::numeric / curr.reports) ELSE 0 END), 6)
           END AS disagreement_score
    FROM se_cluster_base b
    JOIN se_cluster_daily curr
      ON curr.cluster_key = b.cluster_key AND curr.event_date = b.event_date
    LEFT JOIN se_cluster_daily prev
      ON prev.cluster_key = b.cluster_key AND prev.event_date = (b.event_date - INTERVAL '1 day')::date
    JOIN se_cluster_global g ON g.cluster_key = b.cluster_key
    JOIN se_source_cov s ON s.cluster_key = b.cluster_key;

    UPDATE structured_events se
    SET report_count = e.report_count,
        media_coverage_count = e.media_coverage_count,
        heat_duration_days = e.heat_duration_days,
        heat_growth_rate = e.heat_growth_rate,
        disagreement_score = e.disagreement_score
    FROM se_cluster_enriched e
    WHERE se.id = e.id;
    """
    with write_guard(db_name=db_name, required_tables=["structured_events"], lock_timeout_sec=lock_timeout_sec):
        with psycopg.connect(dsn_for(db_name)) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                updated = cur.rowcount if cur.rowcount is not None else 0
            conn.commit()
    return updated


def main() -> None:
    args = parse_args()
    updated = refresh_cluster_stats(args.db, args.lock_timeout_sec)
    print(f"[cluster-stats] updated_rows={updated}")


if __name__ == "__main__":
    main()

