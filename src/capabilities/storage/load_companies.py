#!/usr/bin/env python3
"""Load seed companies into PostgreSQL task2 table."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import psycopg


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = "stock_event_mining"
DEFAULT_SEED = ROOT / "data" / "companies_seed.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load company seed data into PostgreSQL.")
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--input", default=str(DEFAULT_SEED))
    return parser.parse_args()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    args = parse_args()
    rows = read_rows(Path(args.input).resolve())

    with psycopg.connect(f"dbname={args.db} user=tim host=127.0.0.1 port=5432") as conn:
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
