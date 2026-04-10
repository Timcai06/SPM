#!/usr/bin/env python3
"""Build non-event training samples from company stats."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import psycopg

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.storage.db_guard import write_guard


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = "stock_event_mining"
CREATE_SQL_PATH = ROOT / "sql" / "create_training_support_tables.sql"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build non-event samples for training.")
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--start-date", default="", help="Optional lower bound YYYY-MM-DD.")
    parser.add_argument("--end-date", default="", help="Optional upper bound YYYY-MM-DD.")
    parser.add_argument("--max-per-day", type=int, default=100, help="Max negative samples per trade date.")
    parser.add_argument("--min-link-score", type=float, default=0.35, help="Event-company link score threshold for exclusion.")
    parser.add_argument("--run-id", default="", help="Optional run id.")
    parser.add_argument("--lock-timeout-sec", type=int, default=120)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_id = args.run_id or datetime.now().strftime("%Y%m%d_%H%M%S")

    where_parts = []
    params: list[object] = [args.min_link_score]
    if args.start_date:
        where_parts.append("cs.trade_date >= %s")
        params.append(args.start_date)
    if args.end_date:
        where_parts.append("cs.trade_date <= %s")
        params.append(args.end_date)
    where_sql = f"AND {' AND '.join(where_parts)}" if where_parts else ""

    with write_guard(
        db_name=args.db,
        required_tables=["companies", "event_company_links", "structured_events", "model_event_samples"],
        lock_timeout_sec=args.lock_timeout_sec,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_SQL_PATH.read_text(encoding="utf-8"))
            cur.execute(
                f"""
                WITH candidate_rows AS (
                    SELECT
                        cs.trade_date,
                        c.id AS company_id,
                        c.ts_code,
                        c.company_name,
                        c.industry_l1,
                        c.industry_l2,
                        c.concept_tags,
                        cs.total_mv,
                        cs.circ_mv,
                        cs.pe_ttm,
                        cs.pb,
                        cs.turnover_rate,
                        cs.volume_ratio,
                        cs.trailing_return_5d,
                        cs.trailing_return_20d,
                        cs.trailing_return_60d,
                        cs.volatility_5d,
                        cs.volatility_20d,
                        cs.volatility_60d,
                        cs.up_days_20d,
                        cs.forward_return_1d,
                        cs.forward_return_3d,
                        cs.forward_return_5d,
                        ROW_NUMBER() OVER (PARTITION BY cs.trade_date ORDER BY cs.turnover_rate DESC NULLS LAST, c.id) AS rn
                    FROM company_stats cs
                    JOIN companies c ON c.ts_code = cs.ts_code
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM event_company_links l
                        JOIN structured_events se ON se.id = l.structured_event_id
                        WHERE l.company_id = c.id
                          AND l.final_link_score >= %s
                          AND se.event_date = cs.trade_date
                    )
                    {where_sql}
                )
                SELECT *
                FROM candidate_rows
                WHERE rn <= %s
                ORDER BY trade_date DESC, rn
                """,
                params + [args.max_per_day],
            )
            rows = cur.fetchall()

            upserted = 0
            for row in rows:
                (
                    trade_date,
                    company_id,
                    ts_code,
                    company_name,
                    industry_l1,
                    industry_l2,
                    concept_tags,
                    total_mv,
                    circ_mv,
                    pe_ttm,
                    pb,
                    turnover_rate,
                    volume_ratio,
                    trailing_return_20d,
                    trailing_return_5d,
                    trailing_return_60d,
                    volatility_5d,
                    volatility_20d,
                    volatility_60d,
                    up_days_20d,
                    forward_return_1d,
                    forward_return_3d,
                    forward_return_5d,
                    _rn,
                ) = row
                sample_key = f"{trade_date}:{company_id}"
                cur.execute(
                    """
                    INSERT INTO model_non_event_samples (
                        sample_key, sample_run_id, sample_date, company_id, ts_code, company_name,
                        company_industry_l1, company_industry_l2, concept_tags, company_stat_date,
                        total_mv, circ_mv, pe_ttm, pb, turnover_rate, volume_ratio,
                        trailing_return_5d, trailing_return_20d, trailing_return_60d,
                        volatility_5d, volatility_20d, volatility_60d, up_days_20d,
                        label_ret_w1, label_ret_w3, label_ret_w5,
                        label_up_w1, label_up_w3, label_up_w5, label_source, updated_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s::jsonb, %s,
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, 'company_stats', NOW()
                    )
                    ON CONFLICT (sample_key) DO UPDATE
                    SET
                        sample_run_id = EXCLUDED.sample_run_id,
                        ts_code = EXCLUDED.ts_code,
                        company_name = EXCLUDED.company_name,
                        company_industry_l1 = EXCLUDED.company_industry_l1,
                        company_industry_l2 = EXCLUDED.company_industry_l2,
                        concept_tags = EXCLUDED.concept_tags,
                        company_stat_date = EXCLUDED.company_stat_date,
                        total_mv = EXCLUDED.total_mv,
                        circ_mv = EXCLUDED.circ_mv,
                        pe_ttm = EXCLUDED.pe_ttm,
                        pb = EXCLUDED.pb,
                        turnover_rate = EXCLUDED.turnover_rate,
                        volume_ratio = EXCLUDED.volume_ratio,
                        trailing_return_5d = EXCLUDED.trailing_return_5d,
                        trailing_return_20d = EXCLUDED.trailing_return_20d,
                        trailing_return_60d = EXCLUDED.trailing_return_60d,
                        volatility_5d = EXCLUDED.volatility_5d,
                        volatility_20d = EXCLUDED.volatility_20d,
                        volatility_60d = EXCLUDED.volatility_60d,
                        up_days_20d = EXCLUDED.up_days_20d,
                        label_ret_w1 = EXCLUDED.label_ret_w1,
                        label_ret_w3 = EXCLUDED.label_ret_w3,
                        label_ret_w5 = EXCLUDED.label_ret_w5,
                        label_up_w1 = EXCLUDED.label_up_w1,
                        label_up_w3 = EXCLUDED.label_up_w3,
                        label_up_w5 = EXCLUDED.label_up_w5,
                        updated_at = NOW()
                    """,
                    (
                        sample_key,
                        run_id,
                        trade_date,
                        company_id,
                        ts_code,
                        company_name,
                        industry_l1,
                        industry_l2,
                        json.dumps(concept_tags or [], ensure_ascii=False),
                        trade_date,
                        total_mv,
                        circ_mv,
                        pe_ttm,
                        pb,
                        turnover_rate,
                        volume_ratio,
                        trailing_return_5d,
                        trailing_return_20d,
                        trailing_return_60d,
                        volatility_5d,
                        volatility_20d,
                        volatility_60d,
                        up_days_20d,
                        forward_return_1d,
                        forward_return_3d,
                        forward_return_5d,
                        None if forward_return_1d is None else forward_return_1d > 0,
                        None if forward_return_3d is None else forward_return_3d > 0,
                        None if forward_return_5d is None else forward_return_5d > 0,
                    ),
                )
                upserted += 1
        conn.commit()
    print(f"Built model_non_event_samples for db={args.db}: upserted={upserted}, run_id={run_id}")


if __name__ == "__main__":
    main()
