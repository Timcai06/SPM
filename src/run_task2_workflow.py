#!/usr/bin/env python3
"""Load companies and generate minimal event-company links."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = "stock_event_mining"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run minimal Task 2 workflow.")
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--min-score", type=float, default=0.35)
    return parser.parse_args()


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, cwd=str(ROOT))


def main() -> None:
    args = parse_args()
    run(["python3", "src/load_companies_to_postgres.py", "--db", args.db])
    run(
        [
            "python3",
            "src/generate_event_company_links.py",
            "--db",
            args.db,
            "--top-k",
            str(args.top_k),
            "--min-score",
            str(args.min_score),
        ]
    )
    print(f"Task 2 workflow completed for database: {args.db}")


if __name__ == "__main__":
    main()
