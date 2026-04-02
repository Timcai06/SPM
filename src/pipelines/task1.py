#!/usr/bin/env python3
"""One-shot Task 1 workflow: collect -> classify -> load -> validate."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = "stock_event_mining"
CLASSIFY_INPUT_FILES = [
    "data/demo_news.csv",
    "data/source_gov.csv",
    "data/source_ndrc.csv",
    "data/source_csrc.csv",
    "data/source_sse.csv",
    "data/source_cninfo.csv",
    "data/source_szse.csv",
    "data/source_yicai.csv",
    "data/source_eastmoney.csv",
    "data/source_36kr.csv",
    "data/source_caixin.csv",
    "data/source_miit.csv",
    "data/manual_news.csv",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full Task 1 workflow.")
    parser.add_argument("--limit", type=int, default=8, help="Max rows to collect per live source.")
    parser.add_argument("--db", default=DEFAULT_DB, help="PostgreSQL database name.")
    parser.add_argument(
        "--skip-collect",
        action="store_true",
        help="Skip live source collection and only run classification/loading.",
    )
    parser.add_argument(
        "--skip-validate",
        action="store_true",
        help="Skip validation after loading.",
    )
    return parser.parse_args()


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, cwd=str(ROOT))


def build_classify_cmd(db: str) -> list[str]:
    cmd = ["python3", "src/capabilities/events/classify.py", "--db", db]
    for input_file in CLASSIFY_INPUT_FILES:
        cmd.extend(["--input", input_file])
    return cmd


def main() -> None:
    args = parse_args()

    if not args.skip_collect:
        run(["python3", "src/capabilities/collectors/run.py", "--limit", str(args.limit)])

    run(build_classify_cmd(args.db))

    if not args.skip_validate:
        run(["python3", "src/capabilities/quality/check.py"])

    print(f"Task 1 workflow completed for database: {args.db}")


if __name__ == "__main__":
    main()
