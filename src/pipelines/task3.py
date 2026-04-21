#!/usr/bin/env python3
"""Prepare Task 3 graph edges and propagation links."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from modules.graph.jobs import load_relations_job
from modules.graph.jobs import propagate_links_job

ROOT = Path(__file__).resolve().parents[2]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run task3 graph preparation workflow.")
    parser.add_argument("--db", default="stock_event_mining")
    parser.add_argument("--input", default="output/seeds/company_relations_seed.csv")
    parser.add_argument("--min-source-score", type=float, default=0.35)
    parser.add_argument("--min-propagation-score", type=float, default=0.20)
    parser.add_argument("--canonical-map", default="output/event_canonical_map.csv")
    return parser.parse_args(argv)

def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    load_relations_job.main(["--db", args.db, "--input", args.input])
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
    print(f"Task 3 preparation workflow completed for database: {args.db}")


if __name__ == "__main__":
    main()
