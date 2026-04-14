#!/usr/bin/env python3
"""Load company profile snapshots from the companies dimension into PostgreSQL."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import psycopg

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.storage.db_guard import dsn_for, write_guard


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = "stock_event_mining"
DEFAULT_SNAPSHOT_DATE = datetime.now().date().isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load company profiles into PostgreSQL.")
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--snapshot-date", default=DEFAULT_SNAPSHOT_DATE)
    parser.add_argument("--lock-timeout-sec", type=int, default=120, help="Max seconds to wait for DB write lock.")
    return parser.parse_args()


def normalize_snapshot_date(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return DEFAULT_SNAPSHOT_DATE
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except Exception:
        return DEFAULT_SNAPSHOT_DATE


def main() -> None:
    args = parse_args()
    snapshot_date = normalize_snapshot_date(args.snapshot_date)

    with write_guard(
        db_name=args.db,
        required_tables=["companies", "company_profiles"],
        lock_timeout_sec=args.lock_timeout_sec,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO company_profiles (
                    ts_code, snapshot_date, company_name, exchange, industry_l1, industry_l2,
                    concept_tags, region, list_date, state_owned_flag, company_type,
                    business_scope, core_products, main_customers, main_suppliers,
                    employees, total_shares, float_shares, data_source
                )
                SELECT
                    c.ts_code,
                    %s::date,
                    c.company_name,
                    c.exchange,
                    c.industry_l1,
                    c.industry_l2,
                    c.concept_tags,
                    NULL,
                    NULL,
                    NULL,
                    CASE
                        WHEN c.exchange = 'SSE' THEN '沪市A股'
                        WHEN c.exchange = 'SZSE' THEN '深市A股'
                        WHEN c.exchange = 'BSE' THEN '北交所'
                        ELSE 'A股'
                    END,
                    c.business_scope,
                    CASE
                        WHEN COALESCE(NULLIF(c.core_products, ''), '') = '' THEN '[]'::jsonb
                        ELSE to_jsonb(ARRAY[c.core_products])
                    END,
                    '[]'::jsonb,
                    '[]'::jsonb,
                    NULL,
                    NULL,
                    NULL,
                    'companies_table'
                FROM companies c
                WHERE c.is_active = TRUE
                ON CONFLICT (ts_code, snapshot_date) DO UPDATE
                SET
                    company_name = EXCLUDED.company_name,
                    exchange = EXCLUDED.exchange,
                    industry_l1 = EXCLUDED.industry_l1,
                    industry_l2 = EXCLUDED.industry_l2,
                    concept_tags = EXCLUDED.concept_tags,
                    region = EXCLUDED.region,
                    list_date = EXCLUDED.list_date,
                    state_owned_flag = EXCLUDED.state_owned_flag,
                    company_type = EXCLUDED.company_type,
                    business_scope = EXCLUDED.business_scope,
                    core_products = EXCLUDED.core_products,
                    main_customers = EXCLUDED.main_customers,
                    main_suppliers = EXCLUDED.main_suppliers,
                    employees = EXCLUDED.employees,
                    total_shares = EXCLUDED.total_shares,
                    float_shares = EXCLUDED.float_shares,
                    data_source = EXCLUDED.data_source,
                    updated_at = NOW()
                """,
                (snapshot_date,),
            )
        conn.commit()

    print(f"Loaded company profiles snapshot for {args.db}: snapshot_date={snapshot_date}")


if __name__ == "__main__":
    main()
