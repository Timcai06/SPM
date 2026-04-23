#!/usr/bin/env python3
"""Database storage audit, raw-source coverage, and stage cleanup jobs."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from modules.runtime.adapters.db import write_guard


ROOT = Path(__file__).resolve().parents[4]
INSPECT_SQL_PATH = ROOT / "sql" / "inspect_storage_footprint.sql"
RAW_COVERAGE_SQL_PATH = ROOT / "sql" / "inspect_raw_source_coverage.sql"


def parse_audit_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect database storage footprint.")
    parser.add_argument("--db", default="stock_event_mining")
    return parser.parse_args(argv)


def parse_clean_stage_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean rebuildable stage tables.")
    parser.add_argument("--db", default="stock_event_mining")
    parser.add_argument("--lock-timeout-sec", type=int, default=120)
    parser.add_argument("--yes", action="store_true", help="Execute cleanup. Required for destructive action.")
    return parser.parse_args(argv)


def parse_raw_coverage_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect raw_documents source coverage for a date window.")
    parser.add_argument("--db", default="stock_event_mining")
    parser.add_argument("--start-date", default="2025-01-01")
    parser.add_argument("--end-date", default="2027-01-01", help="Exclusive upper bound.")
    parser.add_argument("--top-n", type=int, default=200)
    return parser.parse_args(argv)


def run_storage_audit(argv: list[str] | None = None) -> None:
    args = parse_audit_args(argv)
    subprocess.run(["psql", "-d", args.db, "-f", str(INSPECT_SQL_PATH)], check=True)


def run_raw_source_coverage(argv: list[str] | None = None) -> None:
    args = parse_raw_coverage_args(argv)
    subprocess.run(
        [
            "psql",
            "-d",
            args.db,
            "-v",
            f"start_date={args.start_date}",
            "-v",
            f"end_date={args.end_date}",
            "-v",
            f"top_n={args.top_n}",
            "-f",
            str(RAW_COVERAGE_SQL_PATH),
        ],
        check=True,
    )


def run_clean_stage(argv: list[str] | None = None) -> None:
    args = parse_clean_stage_args(argv)
    if not args.yes:
        raise SystemExit("Refusing to truncate stage tables without --yes.")
    with write_guard(
        db_name=args.db,
        required_tables=["stg_event_candidates", "stg_structured_events"],
        lock_timeout_sec=args.lock_timeout_sec,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE stg_event_candidates RESTART IDENTITY CASCADE")
            cur.execute("TRUNCATE TABLE stg_structured_events RESTART IDENTITY CASCADE")
        conn.commit()
    print(f"Cleaned stage tables for db={args.db}: stg_event_candidates, stg_structured_events")
