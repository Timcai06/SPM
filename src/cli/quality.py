#!/usr/bin/env python3
"""Quality and delivery CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from cli.quality_parser import build_parser
from cli.quality_support import print_db_status, print_qa_summary
from modules.quality.jobs import check_job, delivery_status_job, quality_report_job, storage_governance_job
from modules.runtime.services.run_metadata_service import logged_run


def parse_args() -> argparse.Namespace:
    return build_parser().parse_args()


def run_check_command(_args: argparse.Namespace) -> None:
    check_job.main([])


def run_quality_command(args: argparse.Namespace) -> None:
    argv = ["--sample-size", str(args.sample_size)]
    with logged_run(
        db_name=None,
        command_group="quality",
        command_name="quality",
        argv=argv,
        explicit_run_id=args.run_id,
        metadata={"sample_size": args.sample_size},
    ) as run_id:
        argv.extend(["--run-id", run_id])
        quality_report_job.main(argv)


def run_db_status_command(args: argparse.Namespace) -> None:
    with logged_run(
        db_name=args.db,
        command_group="quality",
        command_name="db-status",
        argv=["--db", args.db],
    ):
        print_db_status(args.db)


def run_storage_audit_command(args: argparse.Namespace) -> None:
    argv = ["--db", args.db]
    with logged_run(
        db_name=args.db,
        command_group="quality",
        command_name="storage-audit",
        argv=argv,
    ):
        storage_governance_job.run_storage_audit(argv)


def run_raw_coverage_command(args: argparse.Namespace) -> None:
    argv = [
        "--db",
        args.db,
        "--start-date",
        args.start_date,
        "--end-date",
        args.end_date,
        "--top-n",
        str(args.top_n),
    ]
    with logged_run(
        db_name=args.db,
        command_group="quality",
        command_name="raw-coverage",
        argv=argv,
        metadata={"start_date": args.start_date, "end_date": args.end_date, "top_n": args.top_n},
    ):
        storage_governance_job.run_raw_source_coverage(argv)


def run_normalize_raw_categories_command(args: argparse.Namespace) -> None:
    argv = ["--db", args.db, "--lock-timeout-sec", str(args.lock_timeout_sec)]
    if args.start_date:
        argv.extend(["--start-date", args.start_date])
    if args.end_date:
        argv.extend(["--end-date", args.end_date])
    with logged_run(
        db_name=args.db,
        command_group="quality",
        command_name="normalize-raw-categories",
        argv=argv,
        metadata={"start_date": args.start_date, "end_date": args.end_date},
    ):
        storage_governance_job.run_normalize_raw_categories(argv)


def run_clean_stage_command(args: argparse.Namespace) -> None:
    argv = ["--db", args.db, "--lock-timeout-sec", str(args.lock_timeout_sec)]
    if args.yes:
        argv.append("--yes")
    with logged_run(
        db_name=args.db,
        command_group="quality",
        command_name="clean-stage",
        argv=argv,
        metadata={"destructive": True, "target": "stage_tables"},
    ):
        storage_governance_job.run_clean_stage(argv)


def run_qa_command(args: argparse.Namespace) -> None:
    argv = [
        "--db",
        args.db,
        "--snapshot-path",
        args.snapshot_path,
        "--collector-report",
        args.collector_report,
        "--feature-report",
        args.feature_report,
    ]
    with logged_run(
        db_name=args.db,
        command_group="quality",
        command_name="qa",
        argv=argv,
    ):
        print_qa_summary(
            db_name=args.db,
            snapshot_path=Path(args.snapshot_path).resolve(),
            collector_report=Path(args.collector_report).resolve(),
            feature_report=Path(args.feature_report).resolve(),
        )


def run_delivery_status_command(args: argparse.Namespace) -> None:
    argv = ["--db", args.db]
    if args.output:
        argv.extend(["--output", args.output])
    if args.fail_on_blockers:
        argv.append("--fail-on-blockers")
    with logged_run(
        db_name=args.db,
        command_group="quality",
        command_name="delivery-status",
        argv=argv,
    ):
        delivery_status_job.main(argv)


COMMAND_HANDLERS: dict[str, Callable[[argparse.Namespace], None]] = {
    "check": run_check_command,
    "quality": run_quality_command,
    "sample": run_quality_command,
    "db-status": run_db_status_command,
    "db": run_db_status_command,
    "storage-audit": run_storage_audit_command,
    "raw-coverage": run_raw_coverage_command,
    "sources": run_raw_coverage_command,
    "raw": run_raw_coverage_command,
    "normalize-raw-categories": run_normalize_raw_categories_command,
    "raw-categories": run_normalize_raw_categories_command,
    "clean-stage": run_clean_stage_command,
    "qa": run_qa_command,
    "summary": run_qa_command,
    "delivery-status": run_delivery_status_command,
}


def main() -> None:
    args = parse_args()
    handler = COMMAND_HANDLERS.get(args.command)
    if handler is None:
        raise ValueError(f"Unsupported command: {args.command}")
    handler(args)


if __name__ == "__main__":
    main()
