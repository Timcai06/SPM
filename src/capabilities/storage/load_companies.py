#!/usr/bin/env python3
"""Load seed companies into PostgreSQL task2 table."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import psycopg

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.storage.db_guard import dsn_for, write_guard


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = "stock_event_mining"
DEFAULT_SEED = ROOT / "data" / "companies_seed.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load company seed data into PostgreSQL.")
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--input", default=str(DEFAULT_SEED))
    parser.add_argument("--lock-timeout-sec", type=int, default=120, help="Max seconds to wait for DB write lock.")
    return parser.parse_args()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    args = parse_args()
    rows = read_rows(Path(args.input).resolve())

    with write_guard(
        db_name=args.db,
        required_tables=["companies"],
        lock_timeout_sec=args.lock_timeout_sec,
    ):
        with psycopg.connect(dsn_for(args.db)) as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE companies RESTART IDENTITY CASCADE")
                for row in rows:
                    cur.execute(
                        """
                        INSERT INTO companies (
                            ts_code, company_name, exchange, industry_l1, industry_l2,
                            business_scope, core_products, concept_tags
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                        """,
                        (
                            row["ts_code"],
                            row["company_name"],
                            row["exchange"],
                            row["industry_l1"],
                            row["industry_l2"],
                            row["business_scope"],
                            row["core_products"],
                            row["concept_tags"],
                        ),
                    )
    print(f"Loaded {len(rows)} companies into {args.db}")


if __name__ == "__main__":
    main()
