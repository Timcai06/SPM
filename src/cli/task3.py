#!/usr/bin/env python3
"""Unified CLI entrypoint for Task 3 preparation."""

from __future__ import annotations

import argparse
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Callable

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from modules.graph.jobs import propagate_links_job
from capabilities.storage import load_task3_relations
from pipelines import task3 as task3_pipeline
from cli.task3_parser import build_parser


@contextmanager
def patched_argv(argv: list[str]):
    old = sys.argv[:]
    sys.argv = argv
    try:
        yield
    finally:
        sys.argv = old


def parse_args() -> argparse.Namespace:
    return build_parser().parse_args()


def run_pipeline_command(args: argparse.Namespace) -> None:
    task3_pipeline.main(
        [
            "--db",
            args.db,
            "--input",
            args.input,
            "--min-source-score",
            str(args.min_source_score),
            "--min-propagation-score",
            str(args.min_propagation_score),
            "--canonical-map",
            args.canonical_map,
        ]
    )


def run_load_relations_command(args: argparse.Namespace) -> None:
    with patched_argv(["load_task3_relations.py", "--db", args.db, "--input", args.input]):
        load_task3_relations.main()


def run_propagate_command(args: argparse.Namespace) -> None:
    propagate_links_job.main(
        [
            "--db",
            args.db,
            "--min-source-score",
            str(args.min_source_score),
            "--min-propagation-score",
            str(args.min_propagation_score),
            "--canonical-map",
            args.canonical_map,
        ]
    )


COMMAND_HANDLERS: dict[str, Callable[[argparse.Namespace], None]] = {
    "run": run_pipeline_command,
    "load-relations": run_load_relations_command,
    "propagate": run_propagate_command,
}


def main() -> None:
    args = parse_args()
    handler = COMMAND_HANDLERS.get(args.command)
    if handler is None:
        raise ValueError(f"Unsupported command: {args.command}")
    handler(args)


if __name__ == "__main__":
    main()
