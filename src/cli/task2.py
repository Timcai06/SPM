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
    import_companies_akshare,
    import_companies_public,
    import_companies_tushare,
    import_company_profiles_akshare,
    import_company_stats_akshare,
    import_company_stats_local,
    import_company_stats_sina,
    import_company_stats_tushare,
    load_company_profiles,
    load_market_environment,
    load_sentiment_propagation,
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

    import_all_a_parser = sub.add_parser("import-companies-all-a", help="import A-share company universe directly into DB")
    import_all_a_parser.add_argument("--db", default="stock_event_mining")
    import_all_a_parser.add_argument("--max-symbols", type=int, default=0)
    import_all_a_parser.add_argument("--offset", type=int, default=0)
    import_all_a_parser.add_argument("--lock-timeout-sec", type=int, default=120)

    import_public_parser = sub.add_parser("import-companies-public", help="build company seed from collected public sources")
    import_public_parser.add_argument("--output", default="output/seeds/companies_public.csv")

    import_profiles_parser = sub.add_parser("import-company-profiles", help="build company profile seed from public sources")
    import_profiles_parser.add_argument("--db", default="stock_event_mining")
    import_profiles_parser.add_argument("--input", default="output/seeds/company_profiles_seed.csv")
    import_profiles_parser.add_argument("--output", default="output/seeds/company_profiles_seed.csv")
    import_profiles_parser.add_argument("--max-symbols", type=int, default=0)
    import_profiles_parser.add_argument("--sleep-sec", type=float, default=0.05)
    import_profiles_parser.add_argument("--progress-every", type=int, default=10)
    import_profiles_parser.add_argument("--with-holders", action="store_true")

    import_stats_parser = sub.add_parser("import-company-stats", help="import company stats from Tushare or AKShare")
    import_stats_parser.add_argument("--db", default="stock_event_mining")
    import_stats_parser.add_argument("--output", default="output/seeds/company_stats.csv")
    import_stats_parser.add_argument("--quotes-output", default="output/seeds/stock_daily_quotes.csv")
    import_stats_parser.add_argument("--source", choices=["auto", "tushare", "akshare", "sina"], default="auto")
    import_stats_parser.add_argument("--tushare-token", default="")
    import_stats_parser.add_argument("--tushare-token-file", default="")
    import_stats_parser.add_argument("--days", type=int, default=30)
    import_stats_parser.add_argument("--max-symbols", type=int, default=300)
    import_stats_parser.add_argument("--offset", type=int, default=0)
    import_stats_parser.add_argument("--sleep-sec", type=float, default=0.05)
    import_stats_parser.add_argument("--progress-every", type=int, default=20)
    import_stats_parser.add_argument("--timeout-sec", type=float, default=12.0)
    import_stats_parser.add_argument("--max-rows", type=int, default=1200)
    import_stats_parser.add_argument("--retries", type=int, default=2)
    import_stats_parser.add_argument("--failure-backoff-sec", type=float, default=0.8)
    import_stats_parser.add_argument("--resume-existing", action="store_true")

    import_local_parser = sub.add_parser("import-company-stats-local", help="import company stats from local price CSV")
    import_local_parser.add_argument("--input", required=True)
    import_local_parser.add_argument("--output", default="output/seeds/company_stats.csv")
    import_local_parser.add_argument("--quotes-output", default="output/seeds/stock_daily_quotes.csv")

    load_stats_parser = sub.add_parser("load-company-stats", help="load company stats csv")
    load_stats_parser.add_argument("--db", default="stock_event_mining")
    load_stats_parser.add_argument("--input", default="output/seeds/company_stats.csv")
    load_stats_parser.add_argument("--quotes-input", default="output/seeds/stock_daily_quotes.csv")

    load_profiles_parser = sub.add_parser("load-company-profiles", help="load company profiles snapshot from companies table")
    load_profiles_parser.add_argument("--db", default="stock_event_mining")
    load_profiles_parser.add_argument("--snapshot-date", default="")
    load_profiles_parser.add_argument("--input", default="")
    load_profiles_parser.add_argument("--lock-timeout-sec", type=int, default=120)

    load_market_parser = sub.add_parser("load-market-environment", help="load market environment daily rows from stock quotes")
    load_market_parser.add_argument("--db", default="stock_event_mining")
    load_market_parser.add_argument("--benchmark", default="hs300")
    load_market_parser.add_argument("--input", default="")
    load_market_parser.add_argument("--timeout-sec", type=float, default=12.0)
    load_market_parser.add_argument("--lock-timeout-sec", type=int, default=120)

    load_sentiment_parser = sub.add_parser("load-sentiment-propagation", help="load sentiment propagation daily rows")
    load_sentiment_parser.add_argument("--db", default="stock_event_mining")
    load_sentiment_parser.add_argument("--lock-timeout-sec", type=int, default=120)
    load_sentiment_parser.add_argument("--quiet", action="store_true")

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

    if args.command == "import-companies-all-a":
        with patched_argv(
            [
                "import_companies_akshare.py",
                "--db",
                args.db,
                "--max-symbols",
                str(args.max_symbols),
                "--offset",
                str(args.offset),
                "--lock-timeout-sec",
                str(args.lock_timeout_sec),
            ]
        ):
            import_companies_akshare.main()
        return

    if args.command == "import-companies-public":
        with patched_argv(["import_companies_public.py", "--output", args.output]):
            import_companies_public.main()
        return

    if args.command == "import-company-profiles":
        with patched_argv(
            [
                "import_company_profiles_akshare.py",
                "--db",
                args.db,
                "--input",
                args.input,
                "--output",
                args.output,
                "--max-symbols",
                str(args.max_symbols),
                "--sleep-sec",
                str(args.sleep_sec),
                "--progress-every",
                str(args.progress_every),
            ]
            + (["--with-holders"] if args.with_holders else [])
        ):
            import_company_profiles_akshare.main()
        return

    if args.command == "import-company-stats":
        if args.source == "sina":
            argv = [
                "import_company_stats_sina.py",
                "--output",
                args.output,
                "--quotes-output",
                args.quotes_output,
                "--db",
                args.db,
                "--days",
                str(args.days),
                "--max-symbols",
                str(args.max_symbols),
                "--max-rows",
                str(args.max_rows),
                "--sleep-sec",
                str(args.sleep_sec),
                "--progress-every",
                str(args.progress_every),
                "--timeout-sec",
                str(args.timeout_sec),
            ]
            with patched_argv(argv):
                import_company_stats_sina.main()
            return
        def run_akshare_import() -> None:
            argv = [
                "import_company_stats_akshare.py",
                "--output",
                args.output,
                "--quotes-output",
                args.quotes_output,
                "--db",
                args.db,
                "--days",
                str(args.days),
                "--max-symbols",
                str(args.max_symbols),
                "--offset",
                str(args.offset),
                "--sleep-sec",
                str(args.sleep_sec),
                "--progress-every",
                str(args.progress_every),
                "--timeout-sec",
                str(args.timeout_sec),
                "--retries",
                str(args.retries),
                "--failure-backoff-sec",
                str(args.failure_backoff_sec),
            ]
            if args.resume_existing:
                argv.append("--resume-existing")
            with patched_argv(argv):
                import_company_stats_akshare.main()

        if args.source in ("tushare", "auto"):
            argv = [
                "import_company_stats_tushare.py",
                "--output",
                args.output,
                "--quotes-output",
                args.quotes_output,
                "--db",
                args.db,
                "--days",
                str(args.days),
                "--max-symbols",
                str(args.max_symbols),
            ]
            if args.tushare_token:
                argv.extend(["--tushare-token", args.tushare_token])
            if args.tushare_token_file:
                argv.extend(["--tushare-token-file", args.tushare_token_file])
            try:
                with patched_argv(argv):
                    import_company_stats_tushare.main()
                return
            except (Exception, SystemExit) as exc:
                if args.source == "tushare":
                    raise
                print(f"[import-company-stats] tushare failed, fallback to akshare: {exc}")
            try:
                run_akshare_import()
                return
            except (Exception, SystemExit) as exc:
                print(f"[import-company-stats] akshare failed, fallback to sina: {exc}")
                argv = [
                    "import_company_stats_sina.py",
                    "--output",
                    args.output,
                    "--quotes-output",
                    args.quotes_output,
                    "--db",
                    args.db,
                    "--days",
                    str(args.days),
                    "--max-symbols",
                    str(args.max_symbols),
                    "--max-rows",
                    str(args.max_rows),
                    "--sleep-sec",
                    str(args.sleep_sec),
                    "--progress-every",
                    str(args.progress_every),
                    "--timeout-sec",
                    str(args.timeout_sec),
                ]
                with patched_argv(argv):
                    import_company_stats_sina.main()
                return
        run_akshare_import()
        return

    if args.command == "import-company-stats-local":
        with patched_argv(
            [
                "import_company_stats_local.py",
                "--input",
                args.input,
                "--output",
                args.output,
                "--quotes-output",
                args.quotes_output,
            ]
        ):
            import_company_stats_local.main()
        return

    if args.command == "load-company-stats":
        with patched_argv(
            [
                "load_company_stats.py",
                "--db",
                args.db,
                "--input",
                args.input,
                "--quotes-input",
                args.quotes_input,
            ]
        ):
            load_company_stats.main()
        return

    if args.command == "load-company-profiles":
        with patched_argv(
            [
                "load_company_profiles.py",
                "--db",
                args.db,
                "--snapshot-date",
                args.snapshot_date,
                "--input",
                args.input,
                "--lock-timeout-sec",
                str(args.lock_timeout_sec),
            ]
        ):
            load_company_profiles.main()
        return

    if args.command == "load-market-environment":
        with patched_argv(
            [
                "load_market_environment.py",
                "--db",
                args.db,
                "--benchmark",
                args.benchmark,
                "--input",
                args.input,
                "--timeout-sec",
                str(args.timeout_sec),
                "--lock-timeout-sec",
                str(args.lock_timeout_sec),
            ]
        ):
            load_market_environment.main()
        return

    if args.command == "load-sentiment-propagation":
        argv = [
            "load_sentiment_propagation.py",
            "--db",
            args.db,
            "--lock-timeout-sec",
            str(args.lock_timeout_sec),
        ]
        if args.quiet:
            argv.append("--quiet")
        with patched_argv(argv):
            load_sentiment_propagation.main()
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
