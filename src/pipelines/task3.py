#!/usr/bin/env python3
"""Prepare Task 3 graph edges and propagation links."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run task3 graph preparation workflow.")
    parser.add_argument("--db", default="stock_event_mining")
    parser.add_argument("--input", default="data/company_relations_seed.csv")
    parser.add_argument("--min-source-score", type=float, default=0.35)
    parser.add_argument("--min-propagation-score", type=float, default=0.20)
    return parser.parse_args()


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, cwd=str(ROOT))


def main() -> None:
    args = parse_args()
    run(["python3", "src/capabilities/storage/load_task3_relations.py", "--db", args.db, "--input", args.input])
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
        ]
    )
    print(f"Task 3 preparation workflow completed for database: {args.db}")


if __name__ == "__main__":
    main()
