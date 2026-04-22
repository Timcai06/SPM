#!/usr/bin/env python3
"""Company and event-linking CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from modules.linking.jobs import relink_job
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
from modules.runtime.services.run_metadata_service import logged_run
from pipelines import linking as linking_pipeline
from cli.linking_parser import build_parser


def parse_args() -> argparse.Namespace:
    return build_parser().parse_args()


def run_pipeline_command(args: argparse.Namespace) -> None:
    argv = [
        "--db",
        args.db,
        "--top-k",
        str(args.top_k),
        "--min-score",
        str(args.min_score),
        "--canonical-map",
        args.canonical_map,
    ]
    with logged_run(
        db_name=args.db,
        command_group="linking",
        command_name="run",
        argv=argv,
    ) as run_id:
        argv.extend(["--run-id", run_id])
        linking_pipeline.main(argv)


def run_link_events_command(args: argparse.Namespace) -> None:
    argv = [
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
    with logged_run(
        db_name=args.db,
        command_group="linking",
        command_name="link-events",
        argv=argv,
    ):
        relink_job.main(argv)


def run_load_companies_command(args: argparse.Namespace) -> None:
    argv = ["--db", args.db, "--input", args.input]
    with logged_run(db_name=args.db, command_group="linking", command_name="load-companies", argv=argv):
        load_companies_job.main(argv)


def run_import_companies_command(args: argparse.Namespace) -> None:
    argv = ["--output", args.output]
    if args.tushare_token:
        argv.extend(["--tushare-token", args.tushare_token])
    if args.tushare_token_file:
        argv.extend(["--tushare-token-file", args.tushare_token_file])
    import_companies_tushare_job.main(argv)


def run_import_companies_all_a_command(args: argparse.Namespace) -> None:
    argv = [
        "--db",
        args.db,
        "--max-symbols",
        str(args.max_symbols),
        "--offset",
        str(args.offset),
        "--lock-timeout-sec",
        str(args.lock_timeout_sec),
    ]
    with logged_run(db_name=args.db, command_group="linking", command_name="import-companies-all-a", argv=argv):
        import_companies_job.main(argv)


def run_import_company_industries_command(args: argparse.Namespace) -> None:
    argv = [
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
    with logged_run(db_name=args.db, command_group="linking", command_name="import-company-industries", argv=argv):
        board_industries_job.main(argv)


def run_import_company_standard_industries_command(args: argparse.Namespace) -> None:
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
    with logged_run(db_name=args.db, command_group="linking", command_name="import-company-standard-industries", argv=argv):
        standard_industries_job.main(argv)


def run_import_companies_public_command(args: argparse.Namespace) -> None:
    import_companies_public_job.main(["--output", args.output])


def run_import_company_profiles_command(args: argparse.Namespace) -> None:
    argv = [
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
    ] + (["--with-holders"] if args.with_holders else [])
    with logged_run(db_name=args.db, command_group="linking", command_name="import-company-profiles", argv=argv):
        import_profiles_job.main(argv)


def run_import_company_stats_command(args: argparse.Namespace) -> None:
    base_metadata = {"source": args.source, "days": args.days, "max_symbols": args.max_symbols}
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
        with logged_run(db_name=args.db, command_group="linking", command_name="import-company-stats", argv=argv, metadata=base_metadata):
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
        with logged_run(db_name=args.db, command_group="linking", command_name="import-company-stats", argv=argv, metadata=base_metadata):
            try:
                import_stats_job.run_tushare(argv)
                return
            except (Exception, SystemExit) as exc:
                if args.source == "tushare":
                    raise
                print(f"[import-company-stats] tushare failed, fallback to akshare: {exc}")
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
        return
    with logged_run(db_name=args.db, command_group="linking", command_name="import-company-stats", argv=["--db", args.db, "--source", args.source], metadata=base_metadata):
        run_akshare_import()


def run_import_company_stats_local_command(args: argparse.Namespace) -> None:
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


def run_load_company_stats_command(args: argparse.Namespace) -> None:
    argv = [
        "--db",
        args.db,
        "--input",
        args.input,
        "--quotes-input",
        args.quotes_input,
    ]
    with logged_run(db_name=args.db, command_group="linking", command_name="load-company-stats", argv=argv):
        load_stats_job.main(argv)


def run_load_company_profiles_command(args: argparse.Namespace) -> None:
    argv = [
        "--db",
        args.db,
        "--snapshot-date",
        args.snapshot_date,
        "--input",
        args.input,
        "--lock-timeout-sec",
        str(args.lock_timeout_sec),
    ]
    with logged_run(db_name=args.db, command_group="linking", command_name="load-company-profiles", argv=argv):
        load_profiles_job.main(argv)


def run_load_market_environment_command(args: argparse.Namespace) -> None:
    argv = [
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
    with logged_run(db_name=args.db, command_group="linking", command_name="load-market-environment", argv=argv):
        load_market_environment_job.main(argv)


def run_load_sentiment_propagation_command(args: argparse.Namespace) -> None:
    argv = [
        "--db",
        args.db,
        "--lock-timeout-sec",
        str(args.lock_timeout_sec),
    ]
    if args.quiet:
        argv.append("--quiet")
    with logged_run(db_name=args.db, command_group="linking", command_name="load-sentiment-propagation", argv=argv):
        load_sentiment_propagation_job.main(argv)


COMMAND_HANDLERS: dict[str, Callable[[argparse.Namespace], None]] = {
    "run": run_pipeline_command,
    "link-events": run_link_events_command,
    "load-companies": run_load_companies_command,
    "import-companies": run_import_companies_command,
    "import-companies-all-a": run_import_companies_all_a_command,
    "import-company-industries": run_import_company_industries_command,
    "import-company-standard-industries": run_import_company_standard_industries_command,
    "import-companies-public": run_import_companies_public_command,
    "import-company-profiles": run_import_company_profiles_command,
    "import-company-stats": run_import_company_stats_command,
    "import-company-stats-local": run_import_company_stats_local_command,
    "load-company-stats": run_load_company_stats_command,
    "load-company-profiles": run_load_company_profiles_command,
    "load-market-environment": run_load_market_environment_command,
    "load-sentiment-propagation": run_load_sentiment_propagation_command,
}


def main() -> None:
    args = parse_args()
    handler = COMMAND_HANDLERS.get(args.command)
    if handler is None:
        raise ValueError(f"Unsupported command: {args.command}")
    handler(args)

if __name__ == "__main__":
    main()
