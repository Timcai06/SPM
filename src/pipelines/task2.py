#!/usr/bin/env python3
"""Load companies and generate minimal event-company links."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from modules.companies.jobs import load_companies_job
from modules.linking.jobs import relink_job
from capabilities.storage.db_guard import dsn_for

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = "stock_event_mining"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run minimal Task 2 workflow.")
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--min-score", type=float, default=0.35)
    parser.add_argument("--input", default="output/seeds/companies_seed.csv")
    parser.add_argument("--canonical-map", default="output/event_canonical_map.csv")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    seed_path = Path(args.input).resolve()
    if seed_path.exists():
        load_companies_job.main(["--db", args.db, "--input", str(seed_path)])
    else:
        with psycopg.connect(dsn_for(args.db)) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM companies WHERE is_active = TRUE")
                company_count = int(cur.fetchone()[0])
        if company_count > 0:
            print(
                f"[task2] seed not found: {seed_path}. "
                f"Use existing companies in DB (is_active={company_count})."
            )
        else:
            raise FileNotFoundError(
                f"Company seed file not found: {seed_path}. "
                "And no active companies found in DB. "
                "Please run import/load companies first."
            )
    relink_job.main(
        [
            "--db",
            args.db,
            "--top-k",
            str(args.top_k),
            "--min-score",
            str(args.min_score),
            "--canonical-map",
            args.canonical_map,
        ]
    )
    print(f"Task 2 workflow completed for database: {args.db}")


if __name__ == "__main__":
    main()
