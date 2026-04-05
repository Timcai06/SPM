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
from capabilities.analysis import build_negative_samples
from capabilities.storage import (
    import_companies_public,
    import_companies_tushare,
    import_company_stats_akshare,
    import_company_stats_local,
    import_company_stats_tushare,
    load_companies,
    load_company_stats,
)
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
    load_parser.add_argument("--input", default="output/seeds/companies_seed.csv")

    import_parser = sub.add_parser("import-companies", help="import company basics from Tushare")
    import_parser.add_argument("--output", default="output/seeds/companies_a_share.csv")
    import_parser.add_argument("--tushare-token", default="")
    import_parser.add_argument("--tushare-token-file", default="")

    import_public_parser = sub.add_parser("import-companies-public", help="build company seed from collected public sources")
    import_public_parser.add_argument("--output", default="output/seeds/companies_public.csv")

    import_stats_parser = sub.add_parser("import-company-stats", help="import company stats from Tushare or AKShare")
    import_stats_parser.add_argument("--db", default="stock_event_mining")
    import_stats_parser.add_argument("--output", default="output/seeds/company_stats.csv")
    import_stats_parser.add_argument("--source", choices=["auto", "tushare", "akshare"], default="auto")
    import_stats_parser.add_argument("--tushare-token", default="")
    import_stats_parser.add_argument("--tushare-token-file", default="")
    import_stats_parser.add_argument("--days", type=int, default=30)
    import_stats_parser.add_argument("--max-symbols", type=int, default=300)
    import_stats_parser.add_argument("--sleep-sec", type=float, default=0.05)
    import_stats_parser.add_argument("--progress-every", type=int, default=20)
    import_stats_parser.add_argument("--timeout-sec", type=float, default=12.0)

    import_local_parser = sub.add_parser("import-company-stats-local", help="import company stats from local price CSV")
    import_local_parser.add_argument("--input", required=True)
    import_local_parser.add_argument("--output", default="output/seeds/company_stats.csv")

    load_stats_parser = sub.add_parser("load-company-stats", help="load company stats csv")
    load_stats_parser.add_argument("--db", default="stock_event_mining")
    load_stats_parser.add_argument("--input", default="output/seeds/company_stats.csv")

    link_parser = sub.add_parser("link-events", help="generate event-company links")
    link_parser.add_argument("--db", default="stock_event_mining")
    link_parser.add_argument("--top-k", type=int, default=3)
    link_parser.add_argument("--min-score", type=float, default=0.35)
    link_parser.add_argument("--canonical-map", default="output/event_canonical_map.csv")

    negative_parser = sub.add_parser("build-negative-samples", help="build non-event training samples")
    negative_parser.add_argument("--db", default="stock_event_mining")
    negative_parser.add_argument("--start-date", default="")
    negative_parser.add_argument("--end-date", default="")
    negative_parser.add_argument("--max-per-day", type=int, default=100)
    negative_parser.add_argument("--min-link-score", type=float, default=0.35)
    negative_parser.add_argument("--run-id", default="")
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

    if args.command == "import-company-stats":
        if args.source in ("tushare", "auto"):
            argv = ["import_company_stats_tushare.py", "--output", args.output, "--days", str(args.days)]
            if args.tushare_token:
                argv.extend(["--tushare-token", args.tushare_token])
            if args.tushare_token_file:
                argv.extend(["--tushare-token-file", args.tushare_token_file])
            try:
                with patched_argv(argv):
                    import_company_stats_tushare.main()
                return
            except Exception as exc:
                if args.source == "tushare":
                    raise
                print(f"[import-company-stats] tushare failed, fallback to akshare: {exc}")
        argv = [
            "import_company_stats_akshare.py",
            "--output",
            args.output,
            "--db",
            args.db,
            "--days",
            str(args.days),
            "--max-symbols",
            str(args.max_symbols),
            "--sleep-sec",
            str(args.sleep_sec),
            "--progress-every",
            str(args.progress_every),
            "--timeout-sec",
            str(args.timeout_sec),
        ]
        with patched_argv(argv):
            import_company_stats_akshare.main()
        return

    if args.command == "import-company-stats-local":
        with patched_argv(["import_company_stats_local.py", "--input", args.input, "--output", args.output]):
            import_company_stats_local.main()
        return

    if args.command == "load-company-stats":
        with patched_argv(["load_company_stats.py", "--db", args.db, "--input", args.input]):
            load_company_stats.main()
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

    if args.command == "build-negative-samples":
        argv = [
            "build_negative_samples.py",
            "--db",
            args.db,
            "--start-date",
            args.start_date,
            "--end-date",
            args.end_date,
            "--max-per-day",
            str(args.max_per_day),
            "--min-link-score",
            str(args.min_link_score),
        ]
        if args.run_id:
            argv.extend(["--run-id", args.run_id])
        with patched_argv(argv):
            build_negative_samples.main()
        return


if __name__ == "__main__":
    main()
