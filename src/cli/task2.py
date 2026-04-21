#!/usr/bin/env python3
"""Unified CLI entrypoint for Task 2."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from modules.linking.jobs import relink_job
from modules.analysis.jobs import negative_samples_job
from modules.companies.jobs import (
    board_industries_job,
    import_companies_public_job,
    import_companies_tushare_job,
    import_companies_job,
    import_profiles_job,
    import_stats_job,
    import_stats_local_job,
    load_companies_job,
    load_market_environment_job,
    load_profiles_job,
    load_sentiment_propagation_job,
    load_stats_job,
    standard_industries_job,
)
from pipelines import task2 as task2_pipeline
from cli.task2_parser import build_parser


def parse_args() -> argparse.Namespace:
    return build_parser().parse_args()


def run_pipeline_command(args: argparse.Namespace) -> None:
    task2_pipeline.main(
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


def run_link_events_command(args: argparse.Namespace) -> None:
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
            "--progress-every",
            str(args.progress_every),
        ]
    )


COMMAND_HANDLERS: dict[str, Callable[[argparse.Namespace], None]] = {
    "run": run_pipeline_command,
    "link-events": run_link_events_command,
}


def main() -> None:
    args = parse_args()
    handler = COMMAND_HANDLERS.get(args.command)
    if handler is not None:
        handler(args)
        return

    if args.command == "load-companies":
        load_companies_job.main(["--db", args.db, "--input", args.input])
        return

    if args.command == "import-companies":
        argv = ["--output", args.output]
        if args.tushare_token:
            argv.extend(["--tushare-token", args.tushare_token])
        if args.tushare_token_file:
            argv.extend(["--tushare-token-file", args.tushare_token_file])
        import_companies_tushare_job.main(argv)
        return

    if args.command == "import-companies-all-a":
        import_companies_job.main(
            [
                "--db",
                args.db,
                "--max-symbols",
                str(args.max_symbols),
                "--offset",
                str(args.offset),
                "--lock-timeout-sec",
                str(args.lock_timeout_sec),
            ]
        )
        return

    if args.command == "import-company-industries":
        board_industries_job.main(
            [
                "--db",
                args.db,
                "--max-industries",
                str(args.max_industries),
                "--offset",
                str(args.offset),
                "--sleep-sec",
                str(args.sleep_sec),
                "--progress-every",
                str(args.progress_every),
                "--lock-timeout-sec",
                str(args.lock_timeout_sec),
            ]
        )
        return

    if args.command == "import-company-standard-industries":
        argv = [
            "--db",
            args.db,
            "--max-symbols",
            str(args.max_symbols),
            "--offset",
            str(args.offset),
            "--start-date",
            args.start_date,
            "--end-date",
            args.end_date,
            "--sleep-sec",
            str(args.sleep_sec),
            "--progress-every",
            str(args.progress_every),
            "--lock-timeout-sec",
            str(args.lock_timeout_sec),
            "--retries",
            str(args.retries),
            "--failure-backoff-sec",
            str(args.failure_backoff_sec),
        ]
        if args.only_dirty:
            argv.append("--only-dirty")
        if args.skip_legacy:
            argv.append("--skip-legacy")
        standard_industries_job.main(argv)
        return

    if args.command == "import-companies-public":
        import_companies_public_job.main(["--output", args.output])
        return

    if args.command == "import-company-profiles":
        import_profiles_job.main(
            [
                "--db",
                args.db,
                "--input",
                args.input,
                "--output",
                args.output,
                "--max-symbols",
                str(args.max_symbols),
                "--sleep-sec",
                str(args.sleep_sec),
                "--progress-every",
                str(args.progress_every),
            ]
            + (["--with-holders"] if args.with_holders else [])
        )
        return

    if args.command == "import-company-stats":
        if args.source == "sina":
            argv = [
                "--output",
                args.output,
                "--quotes-output",
                args.quotes_output,
                "--db",
                args.db,
                "--days",
                str(args.days),
                "--max-symbols",
                str(args.max_symbols),
                "--max-rows",
                str(args.max_rows),
                "--sleep-sec",
                str(args.sleep_sec),
                "--progress-every",
                str(args.progress_every),
                "--timeout-sec",
                str(args.timeout_sec),
            ]
            import_stats_job.run_sina(argv)
            return

        def run_akshare_import() -> None:
            argv = [
                "--output",
                args.output,
                "--quotes-output",
                args.quotes_output,
                "--db",
                args.db,
                "--days",
                str(args.days),
                "--max-symbols",
                str(args.max_symbols),
                "--offset",
                str(args.offset),
                "--sleep-sec",
                str(args.sleep_sec),
                "--progress-every",
                str(args.progress_every),
                "--timeout-sec",
                str(args.timeout_sec),
                "--retries",
                str(args.retries),
                "--failure-backoff-sec",
                str(args.failure_backoff_sec),
            ]
            if args.resume_existing:
                argv.append("--resume-existing")
            import_stats_job.run_akshare(argv)

        if args.source in ("tushare", "auto"):
            argv = [
                "--output",
                args.output,
                "--quotes-output",
                args.quotes_output,
                "--db",
                args.db,
                "--days",
                str(args.days),
                "--max-symbols",
                str(args.max_symbols),
            ]
            if args.tushare_token:
                argv.extend(["--tushare-token", args.tushare_token])
            if args.tushare_token_file:
                argv.extend(["--tushare-token-file", args.tushare_token_file])
            try:
                import_stats_job.run_tushare(argv)
                return
            except (Exception, SystemExit) as exc:
                if args.source == "tushare":
                    raise
                print(
                    f"[import-company-stats] tushare failed, fallback to akshare: {exc}"
                )
            try:
                run_akshare_import()
                return
            except (Exception, SystemExit) as exc:
                print(f"[import-company-stats] akshare failed, fallback to sina: {exc}")
                argv = [
                    "--output",
                    args.output,
                    "--quotes-output",
                    args.quotes_output,
                    "--db",
                    args.db,
                    "--days",
                    str(args.days),
                    "--max-symbols",
                    str(args.max_symbols),
                    "--max-rows",
                    str(args.max_rows),
                    "--sleep-sec",
                    str(args.sleep_sec),
                    "--progress-every",
                    str(args.progress_every),
                    "--timeout-sec",
                    str(args.timeout_sec),
                ]
                import_stats_job.run_sina(argv)
                return
        run_akshare_import()
        return

    if args.command == "import-company-stats-local":
        import_stats_local_job.main(
            [
                "--input",
                args.input,
                "--output",
                args.output,
                "--quotes-output",
                args.quotes_output,
            ]
        )
        return

    if args.command == "load-company-stats":
        load_stats_job.main(
            [
                "--db",
                args.db,
                "--input",
                args.input,
                "--quotes-input",
                args.quotes_input,
            ]
        )
        return

    if args.command == "load-company-profiles":
        load_profiles_job.main(
            [
                "--db",
                args.db,
                "--snapshot-date",
                args.snapshot_date,
                "--input",
                args.input,
                "--lock-timeout-sec",
                str(args.lock_timeout_sec),
            ]
        )
        return

    if args.command == "load-market-environment":
        load_market_environment_job.main(
            [
                "--db",
                args.db,
                "--benchmark",
                args.benchmark,
                "--input",
                args.input,
                "--timeout-sec",
                str(args.timeout_sec),
                "--lock-timeout-sec",
                str(args.lock_timeout_sec),
            ]
        )
        return

    if args.command == "load-sentiment-propagation":
        argv = [
            "--db",
            args.db,
            "--lock-timeout-sec",
            str(args.lock_timeout_sec),
        ]
        if args.quiet:
            argv.append("--quiet")
        load_sentiment_propagation_job.main(argv)
        return

    if args.command == "build-negative-samples":
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
        if args.run_id:
            argv.extend(["--run-id", args.run_id])
        negative_samples_job.main(argv)
        return


if __name__ == "__main__":
    main()
