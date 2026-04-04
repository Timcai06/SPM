#!/usr/bin/env python3
"""Unified CLI entrypoint for Task 2."""

from __future__ import annotations

import argparse
import sys
from contextlib import contextmanager
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.linking import link_events
from capabilities.storage import import_companies_public, import_companies_tushare, load_companies
from pipelines import task2 as task2_pipeline


@contextmanager
def patched_argv(argv: list[str]):
    old = sys.argv[:]
    sys.argv = argv
    try:
        yield
    finally:
        sys.argv = old


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
        with patched_argv(
            [
                "task2.py",
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
            task2_pipeline.main()
        return

    if args.command == "load-companies":
        with patched_argv(["load_companies.py", "--db", args.db, "--input", args.input]):
            load_companies.main()
        return

    if args.command == "import-companies":
        argv = ["import_companies_tushare.py", "--output", args.output]
        if args.tushare_token:
            argv.extend(["--tushare-token", args.tushare_token])
        if args.tushare_token_file:
            argv.extend(["--tushare-token-file", args.tushare_token_file])
        with patched_argv(argv):
            import_companies_tushare.main()
        return

    if args.command == "import-companies-public":
        with patched_argv(["import_companies_public.py", "--output", args.output]):
            import_companies_public.main()
        return

    if args.command == "link-events":
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
        return


if __name__ == "__main__":
    main()
