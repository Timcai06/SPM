#!/usr/bin/env python3
"""Unified CLI entrypoint for Task 3 preparation."""

from __future__ import annotations

import argparse
import sys
from contextlib import contextmanager
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.graph import propagate_event_links
from capabilities.storage import load_task3_relations
from pipelines import task3 as task3_pipeline


@contextmanager
def patched_argv(argv: list[str]):
    old = sys.argv[:]
    sys.argv = argv
    try:
        yield
    finally:
        sys.argv = old


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Task 3 command entrypoint.")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="load graph edges and build propagation links")
    run_parser.add_argument("--db", default="stock_event_mining")
    run_parser.add_argument("--input", default="data/company_relations_seed.csv")
    run_parser.add_argument("--min-source-score", type=float, default=0.35)
    run_parser.add_argument("--min-propagation-score", type=float, default=0.20)
    run_parser.add_argument("--canonical-map", default="output/event_canonical_map.csv")

    load_parser = sub.add_parser("load-relations", help="load company graph edges")
    load_parser.add_argument("--db", default="stock_event_mining")
    load_parser.add_argument("--input", default="data/company_relations_seed.csv")

    propagate_parser = sub.add_parser("propagate", help="build one-hop propagated event links")
    propagate_parser.add_argument("--db", default="stock_event_mining")
    propagate_parser.add_argument("--min-source-score", type=float, default=0.35)
    propagate_parser.add_argument("--min-propagation-score", type=float, default=0.20)
    propagate_parser.add_argument("--canonical-map", default="output/event_canonical_map.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "run":
        with patched_argv(
            [
                "task3.py",
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
        ):
            task3_pipeline.main()
        return

    if args.command == "load-relations":
        with patched_argv(["load_task3_relations.py", "--db", args.db, "--input", args.input]):
            load_task3_relations.main()
        return

    if args.command == "propagate":
        with patched_argv(
            [
                "propagate_event_links.py",
                "--db",
                args.db,
                "--min-source-score",
                str(args.min_source_score),
                "--min-propagation-score",
                str(args.min_propagation_score),
                "--canonical-map",
                args.canonical_map,
            ]
        ):
            propagate_event_links.main()


if __name__ == "__main__":
    main()
