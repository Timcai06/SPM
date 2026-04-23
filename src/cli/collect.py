#!/usr/bin/env python3
"""Collection and CNInfo backfill CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from cli.collect_parser import build_parser
from modules.collectors.jobs import cninfo_fulltext_backfill_job, collect_job, history_job
from modules.runtime.services.network_env_service import without_process_proxies
from modules.runtime.services.run_metadata_service import logged_run


def parse_args() -> argparse.Namespace:
    return build_parser().parse_args()


def run_collect_command(args: argparse.Namespace) -> None:
    argv = ["--limit", str(args.limit)]
    if args.include_non_keyword:
        argv.append("--include-non-keyword")
    with without_process_proxies():
        collect_job.main(argv)


def run_collect_history_command(args: argparse.Namespace) -> None:
    argv = [
        "--db",
        args.db,
        "--source",
        args.source,
        "--symbol-source",
        args.symbol_source,
        "--symbol-file",
        args.symbol_file,
        "--start-date",
        args.start_date,
        "--end-date",
        args.end_date,
        "--max-symbols",
        str(args.max_symbols),
        "--offset",
        str(args.offset),
        "--limit-per-symbol",
        str(args.limit_per_symbol),
        "--workers",
        str(args.workers),
        "--retries",
        str(args.retries),
        "--sleep-sec",
        str(args.sleep_sec),
        "--db-flush-every",
        str(args.db_flush_every),
        "--output-dir",
        args.output_dir,
    ]
    if args.skip_db_load:
        argv.append("--skip-db-load")
    if args.cninfo_fulltext:
        argv.append("--cninfo-fulltext")
    argv.extend(["--cninfo-fulltext-max-chars", str(args.cninfo_fulltext_max_chars)])
    with logged_run(
        db_name=args.db,
        command_group="collect",
        command_name="collect-history",
        argv=argv,
        metadata={"source": args.source, "symbol_source": args.symbol_source},
    ):
        with without_process_proxies():
            history_job.main(argv)


def run_cninfo_backfill_command(args: argparse.Namespace) -> None:
    argv = [
        "--db",
        args.db,
        "--source",
        args.source,
        "--start-date",
        args.start_date,
        "--end-date",
        args.end_date,
        "--max-rows",
        str(args.max_rows),
        "--offset",
        str(args.offset),
        "--id-min",
        str(args.id_min),
        "--id-max",
        str(args.id_max),
        "--shard-count",
        str(args.shard_count),
        "--shard-index",
        str(args.shard_index),
        "--workers",
        str(args.workers),
        "--retries",
        str(args.retries),
        "--sleep-sec",
        str(args.sleep_sec),
        "--progress-every",
        str(args.progress_every),
        "--heartbeat-sec",
        str(args.heartbeat_sec),
        "--detail-timeout-sec",
        str(args.detail_timeout_sec),
        "--pdf-timeout-sec",
        str(args.pdf_timeout_sec),
        "--db-flush-every",
        str(args.db_flush_every),
        "--fulltext-max-chars",
        str(args.fulltext_max_chars),
    ]
    if args.skip_db_load:
        argv.append("--skip-db-load")
    with logged_run(
        db_name=args.db,
        command_group="collect",
        command_name="backfill-cninfo-fulltext",
        argv=argv,
        metadata={"source": args.source, "start_date": args.start_date, "end_date": args.end_date},
    ):
        with without_process_proxies():
            cninfo_fulltext_backfill_job.main(argv)


COMMAND_HANDLERS: dict[str, Callable[[argparse.Namespace], None]] = {
    "collect": run_collect_command,
    "collect-history": run_collect_history_command,
    "backfill-cninfo-fulltext": run_cninfo_backfill_command,
}


def main() -> None:
    args = parse_args()
    handler = COMMAND_HANDLERS.get(args.command)
    if handler is None:
        raise ValueError(f"Unsupported command: {args.command}")
    handler(args)


if __name__ == "__main__":
    main()
