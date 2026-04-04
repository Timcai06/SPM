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
    run_parser.add_argument("--canonical-map", default="output/event_canonical_map.csv")

    load_parser = sub.add_parser("load-companies", help="load company seed")
    load_parser.add_argument("--db", default="stock_event_mining")
    load_parser.add_argument("--input", default="data/companies_seed.csv")

    import_parser = sub.add_parser("import-companies", help="import company basics from Tushare")
    import_parser.add_argument("--output", default="data/companies_a_share.csv")
    import_parser.add_argument("--tushare-token", default="")
    import_parser.add_argument("--tushare-token-file", default="")

    import_public_parser = sub.add_parser("import-companies-public", help="build company seed from collected public sources")
    import_public_parser.add_argument("--output", default="data/companies_public.csv")

    link_parser = sub.add_parser("link-events", help="generate event-company links")
    link_parser.add_argument("--db", default="stock_event_mining")
    link_parser.add_argument("--top-k", type=int, default=3)
    link_parser.add_argument("--min-score", type=float, default=0.35)
    link_parser.add_argument("--canonical-map", default="output/event_canonical_map.csv")
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
                "--canonical-map",
                args.canonical_map,
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

    if args.command == "import-companies":
        cmd = [
            "python3",
            "src/capabilities/storage/import_companies_tushare.py",
            "--output",
            args.output,
        ]
        if args.tushare_token:
            cmd.extend(["--tushare-token", args.tushare_token])
        if args.tushare_token_file:
            cmd.extend(["--tushare-token-file", args.tushare_token_file])
        run(cmd)
        return

    if args.command == "import-companies-public":
        run(
            [
                "python3",
                "src/capabilities/storage/import_companies_public.py",
                "--output",
                args.output,
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
                "--canonical-map",
                args.canonical_map,
            ]
        )
        return


if __name__ == "__main__":
    main()
