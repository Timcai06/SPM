#!/usr/bin/env python3
"""Research and sample-building CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from cli.research_parser import build_parser
from modules.analysis.jobs import feature_return_job, negative_samples_job, train_samples_job
from modules.runtime.services.run_metadata_service import logged_run, register_output_artifact


def parse_args() -> argparse.Namespace:
    return build_parser().parse_args()


def run_feature_command(args: argparse.Namespace) -> None:
    argv = [
        "--db",
        args.db,
        "--min-link-score",
        str(args.min_link_score),
        "--analysis-mode",
        args.analysis_mode,
        "--benchmark",
        args.benchmark,
        "--event-windows",
        args.event_windows,
        "--time-budget-sec",
        str(args.time_budget_sec),
        "--max-rows",
        str(args.max_rows),
        "--api-timeout-sec",
        str(args.api_timeout_sec),
        "--progress-every",
        str(args.progress_every),
        "--market-max-rows",
        str(args.market_max_rows),
        "--dataset-path",
        args.dataset_path,
        "--report-path",
        args.report_path,
    ]
    if args.tushare_token:
        argv.extend(["--tushare-token", args.tushare_token])
    if args.tushare_token_file:
        argv.extend(["--tushare-token-file", args.tushare_token_file])
    if args.disable_tushare:
        argv.append("--disable-tushare")
    if args.disable_cache:
        argv.append("--disable-cache")
    with logged_run(
        db_name=args.db,
        command_group="research",
        command_name="feature",
        argv=argv,
        explicit_run_id=args.run_id,
        metadata={"benchmark": args.benchmark, "analysis_mode": args.analysis_mode},
    ) as run_id:
        argv.extend(["--run-id", run_id])
        feature_return_job.main(argv)
        register_output_artifact(
            db_name=args.db,
            run_id=run_id,
            dataset_key="research.feature.dataset",
            output_path=args.dataset_path,
            metadata={"analysis_mode": args.analysis_mode, "benchmark": args.benchmark},
        )
        register_output_artifact(
            db_name=args.db,
            run_id=run_id,
            dataset_key="research.feature.report",
            output_path=args.report_path,
            metadata={"analysis_mode": args.analysis_mode, "benchmark": args.benchmark},
        )


def run_train_samples_command(args: argparse.Namespace) -> None:
    argv = [
        "--db",
        args.db,
        "--min-link-score",
        str(args.min_link_score),
        "--label-dataset",
        args.label_dataset,
    ]
    with logged_run(
        db_name=args.db,
        command_group="research",
        command_name="train-samples",
        argv=argv,
        explicit_run_id=args.run_id,
        metadata={"label_dataset": args.label_dataset},
    ) as run_id:
        argv.extend(["--run-id", run_id])
        train_samples_job.main(argv)


def run_negative_samples_command(args: argparse.Namespace) -> None:
    argv = [
        "--db",
        args.db,
        "--start-date",
        args.start_date,
        "--end-date",
        args.end_date,
        "--max-per-day",
        str(args.max_per_day),
        "--min-link-score",
        str(args.min_link_score),
    ]
    with logged_run(
        db_name=args.db,
        command_group="research",
        command_name="build-negative-samples",
        argv=argv,
        explicit_run_id=args.run_id,
        metadata={"start_date": args.start_date, "end_date": args.end_date},
    ) as run_id:
        argv.extend(["--run-id", run_id])
        negative_samples_job.main(argv)


COMMAND_HANDLERS: dict[str, Callable[[argparse.Namespace], None]] = {
    "feature": run_feature_command,
    "train-samples": run_train_samples_command,
    "train": run_train_samples_command,
    "build-negative-samples": run_negative_samples_command,
    "negative-samples": run_negative_samples_command,
    "controls": run_negative_samples_command,
}


def main() -> None:
    args = parse_args()
    handler = COMMAND_HANDLERS.get(args.command)
    if handler is None:
        raise ValueError(f"Unsupported command: {args.command}")
    handler(args)


if __name__ == "__main__":
    main()
