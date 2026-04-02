#!/usr/bin/env python3
"""Unified CLI entrypoint for Task 1."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, cwd=str(ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Task 1 command entrypoint.")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="collect -> classify -> load -> validate")
    run_parser.add_argument("--limit", type=int, default=8)
    run_parser.add_argument("--db", default="stock_event_mining")
    run_parser.add_argument("--skip-collect", action="store_true")
    run_parser.add_argument("--skip-validate", action="store_true")

    collect_parser = sub.add_parser("collect", help="collect source data")
    collect_parser.add_argument("--limit", type=int, default=10)
    collect_parser.add_argument("--include-non-keyword", action="store_true")

    classify_parser = sub.add_parser("classify", help="classify and structure events")
    classify_parser.add_argument("--db", default="stock_event_mining")
    classify_parser.add_argument("--skip-db-load", action="store_true")

    sub.add_parser("check", help="validate output datasets")

    quality_parser = sub.add_parser("quality", help="build quality sample/report")
    quality_parser.add_argument("--sample-size", type=int, default=30)

    feature_parser = sub.add_parser("feature", help="run feature-return analysis")
    feature_parser.add_argument("--db", default="stock_event_mining")
    feature_parser.add_argument("--min-link-score", type=float, default=0.35)

    sub.add_parser("view", help="open streamlit data viewer")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "run":
        cmd = ["python3", "src/pipelines/task1.py", "--limit", str(args.limit), "--db", args.db]
        if args.skip_collect:
            cmd.append("--skip-collect")
        if args.skip_validate:
            cmd.append("--skip-validate")
        run(cmd)
        return

    if args.command == "collect":
        cmd = ["python3", "src/capabilities/collectors/run.py", "--limit", str(args.limit)]
        if args.include_non_keyword:
            cmd.append("--include-non-keyword")
        run(cmd)
        return

    if args.command == "classify":
        cmd = ["python3", "src/capabilities/events/classify.py", "--db", args.db]
        if args.skip_db_load:
            cmd.append("--skip-db-load")
        run(cmd)
        return

    if args.command == "check":
        run(["python3", "src/capabilities/quality/check.py"])
        return

    if args.command == "quality":
        run(["python3", "src/capabilities/quality/quality_report.py", "--sample-size", str(args.sample_size)])
        return

    if args.command == "feature":
        run(
            [
                "python3",
                "src/capabilities/analysis/feature_return.py",
                "--db",
                args.db,
                "--min-link-score",
                str(args.min_link_score),
            ]
        )
        return

    if args.command == "view":
        run(["streamlit", "run", "src/apps/view.py"])
        return


if __name__ == "__main__":
    main()
