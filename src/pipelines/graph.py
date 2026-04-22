#!/usr/bin/env python3
"""Prepare graph edges and propagation links."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from modules.graph.jobs import load_relations_job
from modules.graph.jobs import propagate_links_job
from modules.runtime.services.run_metadata_service import logged_step

ROOT = Path(__file__).resolve().parents[2]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run graph preparation workflow.")
    parser.add_argument("--db", default="stock_event_mining")
    parser.add_argument("--input", default="output/seeds/company_relations_seed.csv")
    parser.add_argument("--min-source-score", type=float, default=0.35)
    parser.add_argument("--min-propagation-score", type=float, default=0.20)
    parser.add_argument("--canonical-map", default="output/event_canonical_map.csv")
    parser.add_argument("--run-id", default="", help="Optional parent run id for step-level provenance.")
    return parser.parse_args(argv)

def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    with logged_step(args.db, args.run_id, "load_relations", {"input": args.input}):
        load_relations_job.main(["--db", args.db, "--input", args.input])
    with logged_step(
        args.db,
        args.run_id,
        "propagate_links",
        {"min_source_score": args.min_source_score, "min_propagation_score": args.min_propagation_score},
    ):
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
    print(f"Graph preparation workflow completed for database: {args.db}")


if __name__ == "__main__":
    main()
