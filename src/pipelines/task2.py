#!/usr/bin/env python3
"""Load companies and generate minimal event-company links."""

from __future__ import annotations

import argparse
import sys
from contextlib import contextmanager
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.linking import link_events
from capabilities.storage import load_companies

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = "stock_event_mining"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run minimal Task 2 workflow.")
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--min-score", type=float, default=0.35)
    parser.add_argument("--input", default="output/seeds/companies_seed.csv")
    parser.add_argument("--canonical-map", default="output/event_canonical_map.csv")
    return parser.parse_args()


@contextmanager
def patched_argv(argv: list[str]):
    old = sys.argv[:]
    sys.argv = argv
    try:
        yield
    finally:
        sys.argv = old


def main() -> None:
    args = parse_args()
    with patched_argv(["load_companies.py", "--db", args.db, "--input", args.input]):
        load_companies.main()
    with patched_argv(
        [
            "link_events.py",
            "--db",
            args.db,
            "--top-k",
            str(args.top_k),
            "--min-score",
            str(args.min_score),
            "--canonical-map",
            args.canonical_map,
        ]
    ):
        link_events.main()
    print(f"Task 2 workflow completed for database: {args.db}")


if __name__ == "__main__":
    main()
