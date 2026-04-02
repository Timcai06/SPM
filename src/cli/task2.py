#!/usr/bin/env python3
"""Unified CLI entrypoint for Task 2."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, cwd=str(ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Task 2 command entrypoint.")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="load companies and generate links")
    run_parser.add_argument("--db", default="stock_event_mining")
    run_parser.add_argument("--top-k", type=int, default=3)
    run_parser.add_argument("--min-score", type=float, default=0.35)

    load_parser = sub.add_parser("load-companies", help="load company seed")
    load_parser.add_argument("--db", default="stock_event_mining")
    load_parser.add_argument("--input", default="data/companies_seed.csv")

    link_parser = sub.add_parser("link-events", help="generate event-company links")
    link_parser.add_argument("--db", default="stock_event_mining")
    link_parser.add_argument("--top-k", type=int, default=3)
    link_parser.add_argument("--min-score", type=float, default=0.35)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "run":
        run(
            [
                "python3",
                "src/pipelines/task2.py",
                "--db",
                args.db,
                "--top-k",
                str(args.top_k),
                "--min-score",
                str(args.min_score),
            ]
        )
        return

    if args.command == "load-companies":
        run(
            [
                "python3",
                "src/capabilities/storage/load_companies.py",
                "--db",
                args.db,
                "--input",
                args.input,
            ]
        )
        return

    if args.command == "link-events":
        run(
            [
                "python3",
                "src/capabilities/linking/link_events.py",
                "--db",
                args.db,
                "--top-k",
                str(args.top_k),
                "--min-score",
                str(args.min_score),
            ]
        )
        return


if __name__ == "__main__":
    main()
