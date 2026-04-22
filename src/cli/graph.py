#!/usr/bin/env python3
"""Graph-relation and propagation CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from modules.graph.jobs import load_relations_job, propagate_links_job
from modules.runtime.services.run_metadata_service import logged_run
from pipelines import graph as graph_pipeline
from cli.graph_parser import build_parser


def parse_args() -> argparse.Namespace:
    return build_parser().parse_args()


def run_pipeline_command(args: argparse.Namespace) -> None:
    argv = [
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
    with logged_run(db_name=args.db, command_group="graph", command_name="run", argv=argv) as run_id:
        argv.extend(["--run-id", run_id])
        graph_pipeline.main(argv)


def run_load_relations_command(args: argparse.Namespace) -> None:
    argv = ["--db", args.db, "--input", args.input]
    with logged_run(db_name=args.db, command_group="graph", command_name="load-relations", argv=argv):
        load_relations_job.main(argv)


def run_propagate_command(args: argparse.Namespace) -> None:
    argv = [
        "--db",
        args.db,
        "--min-source-score",
        str(args.min_source_score),
        "--min-propagation-score",
        str(args.min_propagation_score),
        "--canonical-map",
        args.canonical_map,
    ]
    with logged_run(db_name=args.db, command_group="graph", command_name="propagate", argv=argv):
        propagate_links_job.main(argv)


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
