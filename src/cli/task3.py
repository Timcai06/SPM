#!/usr/bin/env python3
"""Unified CLI entrypoint for Task 3 preparation."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, cwd=str(ROOT))


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
        run(
            [
                "python3",
                "src/pipelines/task3.py",
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
        return

    if args.command == "load-relations":
        run(
            [
                "python3",
                "src/capabilities/storage/load_task3_relations.py",
                "--db",
                args.db,
                "--input",
                args.input,
            ]
        )
        return

    if args.command == "propagate":
        run(
            [
                "python3",
                "src/capabilities/graph/propagate_event_links.py",
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


if __name__ == "__main__":
    main()
