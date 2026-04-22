#!/usr/bin/env python3
"""Event normalization CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from cli.events_parser import CLASSIFY_INPUT_FILES, ROOT, build_parser
from modules.events.jobs import canonicalize_job, classify_job, classify_pending_job, reclassify_source_job
from modules.events.services.canonical_loading_service import load_canonical_rows
from modules.runtime.services.run_metadata_service import logged_run
from pipelines import events as events_pipeline


def parse_args() -> argparse.Namespace:
    return build_parser().parse_args()


def run_pipeline_command(args: argparse.Namespace) -> None:
    argv = ["--limit", str(args.limit), "--db", args.db]
    if args.skip_collect:
        argv.append("--skip-collect")
    if args.skip_validate:
        argv.append("--skip-validate")
    if args.with_analysis:
        argv.append("--with-analysis")
    argv.extend(
        [
            "--analysis-mode",
            args.analysis_mode,
            "--benchmark",
            args.benchmark,
            "--event-windows",
            args.event_windows,
            "--time-budget-sec",
            str(args.time_budget_sec),
            "--max-analysis-rows",
            str(args.max_analysis_rows),
            "--api-timeout-sec",
            str(args.api_timeout_sec),
            "--progress-every",
            str(args.progress_every),
        ]
    )
    if args.use_llm:
        argv.extend(["--use-llm", "--llm-max-rows", str(args.llm_max_rows)])
    with logged_run(
        db_name=args.db,
        command_group="events",
        command_name="run",
        argv=argv,
        metadata={"with_analysis": args.with_analysis, "use_llm": args.use_llm},
    ) as run_id:
        argv.extend(["--run-id", run_id])
        events_pipeline.main(argv)


def run_classify_command(args: argparse.Namespace) -> None:
    argv = ["--db", args.db]
    existing_inputs = [input_file for input_file in CLASSIFY_INPUT_FILES if (ROOT / input_file).exists()]
    for input_file in existing_inputs:
        argv.extend(["--input", input_file])
    if args.skip_db_load:
        argv.append("--skip-db-load")
    if args.use_llm:
        argv.extend(["--use-llm", "--llm-max-rows", str(args.llm_max_rows)])
    with logged_run(
        db_name=args.db,
        command_group="events",
        command_name="classify",
        argv=argv,
        metadata={"use_llm": args.use_llm, "input_count": len(existing_inputs)},
    ):
        classify_job.main(argv)


def run_classify_pending_command(args: argparse.Namespace) -> None:
    argv = ["--db", args.db, "--batch-size", str(args.batch_size), "--max-batches", str(args.max_batches)]
    if args.use_llm:
        argv.extend(["--use-llm", "--llm-max-rows", str(args.llm_max_rows)])
    with logged_run(
        db_name=args.db,
        command_group="events",
        command_name="classify-pending",
        argv=argv,
        metadata={"use_llm": args.use_llm},
    ):
        classify_pending_job.main(argv)


def run_reclassify_source_command(args: argparse.Namespace) -> None:
    argv = ["--db", args.db, "--source", args.source, "--batch-size", str(args.batch_size), "--max-batches", str(args.max_batches)]
    if args.use_llm:
        argv.extend(["--use-llm", "--llm-max-rows", str(args.llm_max_rows)])
    with logged_run(
        db_name=args.db,
        command_group="events",
        command_name="reclassify-source",
        argv=argv,
        metadata={"source": args.source, "use_llm": args.use_llm},
    ):
        reclassify_source_job.main(argv)


def run_canonicalize_command(_args: argparse.Namespace) -> None:
    canonicalize_job.main([])


def run_canonical_load_command(args: argparse.Namespace) -> None:
    argv = [
        "--db",
        args.db,
        "--canonical-events",
        args.canonical_events,
        "--canonical-map",
        args.canonical_map,
    ]
    with logged_run(
        db_name=args.db,
        command_group="events",
        command_name="canonical-load",
        argv=argv,
    ):
        load_canonical_rows(
            db=args.db,
            canonical_event_rows=None,
            canonical_link_rows=None,
            canonical_events_path=args.canonical_events,
            canonical_map_path=args.canonical_map,
            quiet=False,
        )


COMMAND_HANDLERS: dict[str, Callable[[argparse.Namespace], None]] = {
    "run": run_pipeline_command,
    "classify": run_classify_command,
    "classify-pending": run_classify_pending_command,
    "reclassify-source": run_reclassify_source_command,
    "canonicalize": run_canonicalize_command,
    "canonical-load": run_canonical_load_command,
}


def main() -> None:
    args = parse_args()
    handler = COMMAND_HANDLERS.get(args.command)
    if handler is None:
        raise ValueError(f"Unsupported command: {args.command}")
    handler(args)


if __name__ == "__main__":
    main()
