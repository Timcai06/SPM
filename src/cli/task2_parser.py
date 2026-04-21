#!/usr/bin/env python3
"""Parser helpers for Task 2 CLI."""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
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

    import_all_a_parser = sub.add_parser(
        "import-companies-all-a",
        help="import A-share company universe directly into DB",
    )
    import_all_a_parser.add_argument("--db", default="stock_event_mining")
    import_all_a_parser.add_argument("--max-symbols", type=int, default=0)
    import_all_a_parser.add_argument("--offset", type=int, default=0)
    import_all_a_parser.add_argument("--lock-timeout-sec", type=int, default=120)

    import_industries_parser = sub.add_parser(
        "import-company-industries",
        help="backfill company industries from public board constituents",
    )
    import_industries_parser.add_argument("--db", default="stock_event_mining")
    import_industries_parser.add_argument("--max-industries", type=int, default=0)
    import_industries_parser.add_argument("--offset", type=int, default=0)
    import_industries_parser.add_argument("--sleep-sec", type=float, default=0.05)
    import_industries_parser.add_argument("--progress-every", type=int, default=20)
    import_industries_parser.add_argument("--lock-timeout-sec", type=int, default=120)

    import_standard_industries_parser = sub.add_parser(
        "import-company-standard-industries",
        help="backfill standard company industry_l1 from CNInfo classification",
    )
    import_standard_industries_parser.add_argument("--db", default="stock_event_mining")
    import_standard_industries_parser.add_argument("--max-symbols", type=int, default=200)
    import_standard_industries_parser.add_argument("--offset", type=int, default=0)
    import_standard_industries_parser.add_argument("--start-date", default="19900101")
    import_standard_industries_parser.add_argument("--end-date", default="20251231")
    import_standard_industries_parser.add_argument("--sleep-sec", type=float, default=0.05)
    import_standard_industries_parser.add_argument("--progress-every", type=int, default=20)
    import_standard_industries_parser.add_argument("--lock-timeout-sec", type=int, default=120)
    import_standard_industries_parser.add_argument("--retries", type=int, default=2)
    import_standard_industries_parser.add_argument("--failure-backoff-sec", type=float, default=0.8)
    import_standard_industries_parser.add_argument("--only-dirty", action="store_true")
    import_standard_industries_parser.add_argument("--skip-legacy", action="store_true")

    import_public_parser = sub.add_parser(
        "import-companies-public",
        help="build company seed from collected public sources",
    )
    import_public_parser.add_argument("--output", default="output/seeds/companies_public.csv")

    import_profiles_parser = sub.add_parser(
        "import-company-profiles",
        help="build company profile seed from public sources",
    )
    import_profiles_parser.add_argument("--db", default="stock_event_mining")
    import_profiles_parser.add_argument("--input", default="output/seeds/company_profiles_seed.csv")
    import_profiles_parser.add_argument("--output", default="output/seeds/company_profiles_seed.csv")
    import_profiles_parser.add_argument("--max-symbols", type=int, default=0)
    import_profiles_parser.add_argument("--sleep-sec", type=float, default=0.05)
    import_profiles_parser.add_argument("--progress-every", type=int, default=10)
    import_profiles_parser.add_argument("--with-holders", action="store_true")

    import_stats_parser = sub.add_parser(
        "import-company-stats",
        help="import company stats from Tushare or AKShare",
    )
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

    import_local_parser = sub.add_parser(
        "import-company-stats-local",
        help="import company stats from local price CSV",
    )
    import_local_parser.add_argument("--input", required=True)
    import_local_parser.add_argument("--output", default="output/seeds/company_stats.csv")
    import_local_parser.add_argument("--quotes-output", default="output/seeds/stock_daily_quotes.csv")

    load_stats_parser = sub.add_parser("load-company-stats", help="load company stats csv")
    load_stats_parser.add_argument("--db", default="stock_event_mining")
    load_stats_parser.add_argument("--input", default="output/seeds/company_stats.csv")
    load_stats_parser.add_argument("--quotes-input", default="output/seeds/stock_daily_quotes.csv")

    load_profiles_parser = sub.add_parser(
        "load-company-profiles",
        help="load company profiles snapshot from companies table",
    )
    load_profiles_parser.add_argument("--db", default="stock_event_mining")
    load_profiles_parser.add_argument("--snapshot-date", default="")
    load_profiles_parser.add_argument("--input", default="")
    load_profiles_parser.add_argument("--lock-timeout-sec", type=int, default=120)

    load_market_parser = sub.add_parser(
        "load-market-environment",
        help="load market environment daily rows from stock quotes",
    )
    load_market_parser.add_argument("--db", default="stock_event_mining")
    load_market_parser.add_argument("--benchmark", default="hs300")
    load_market_parser.add_argument("--input", default="")
    load_market_parser.add_argument("--timeout-sec", type=float, default=12.0)
    load_market_parser.add_argument("--lock-timeout-sec", type=int, default=120)

    load_sentiment_parser = sub.add_parser(
        "load-sentiment-propagation",
        help="load sentiment propagation daily rows",
    )
    load_sentiment_parser.add_argument("--db", default="stock_event_mining")
    load_sentiment_parser.add_argument("--lock-timeout-sec", type=int, default=120)
    load_sentiment_parser.add_argument("--quiet", action="store_true")

    link_parser = sub.add_parser("link-events", help="generate event-company links")
    link_parser.add_argument("--db", default="stock_event_mining")
    link_parser.add_argument("--top-k", type=int, default=3)
    link_parser.add_argument("--min-score", type=float, default=0.35)
    link_parser.add_argument("--canonical-map", default="output/event_canonical_map.csv")
    link_parser.add_argument("--progress-every", type=int, default=250)

    negative_parser = sub.add_parser(
        "build-negative-samples",
        help="build non-event training samples",
    )
    negative_parser.add_argument("--db", default="stock_event_mining")
    negative_parser.add_argument("--start-date", default="")
    negative_parser.add_argument("--end-date", default="")
    negative_parser.add_argument("--max-per-day", type=int, default=100)
    negative_parser.add_argument("--min-link-score", type=float, default=0.35)
    negative_parser.add_argument("--run-id", default="")
    return parser
