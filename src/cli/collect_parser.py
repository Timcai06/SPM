#!/usr/bin/env python3
"""Parser helpers for collection and fulltext backfill commands."""

from __future__ import annotations

import argparse
from datetime import datetime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collection and fulltext backfill entrypoint.")
    sub = parser.add_subparsers(dest="command", required=True)

    collect_parser = sub.add_parser("collect", help="collect live source data")
    collect_parser.add_argument("--limit", type=int, default=10)
    collect_parser.add_argument("--include-non-keyword", action="store_true")

    history_parser = sub.add_parser("collect-history", help="historically backfill raw documents")
    history_parser.add_argument("--db", default="stock_event_mining")
    history_parser.add_argument("--source", choices=["akshare-news", "cninfo-disclosure"], default="akshare-news")
    history_parser.add_argument("--symbol-source", choices=["db", "all-a"], default="db")
    history_parser.add_argument("--symbol-file", default="")
    history_parser.add_argument("--start-date", default="2020-01-01")
    history_parser.add_argument("--end-date", default=datetime.now().date().isoformat())
    history_parser.add_argument("--max-symbols", type=int, default=200)
    history_parser.add_argument("--offset", type=int, default=0)
    history_parser.add_argument("--limit-per-symbol", type=int, default=20)
    history_parser.add_argument("--workers", type=int, default=4)
    history_parser.add_argument("--retries", type=int, default=2)
    history_parser.add_argument("--sleep-sec", type=float, default=0.05)
    history_parser.add_argument("--output-dir", default="output/history")
    history_parser.add_argument("--skip-db-load", action="store_true")
    history_parser.add_argument("--db-flush-every", type=int, default=100)
    history_parser.add_argument("--cninfo-fulltext", action="store_true")
    history_parser.add_argument("--cninfo-fulltext-max-chars", type=int, default=12000)

    backfill_parser = sub.add_parser(
        "backfill-cninfo-fulltext",
        help="backfill CNInfo fulltext using existing raw_documents URLs",
    )
    backfill_parser.add_argument("--db", default="stock_event_mining")
    backfill_parser.add_argument("--source", default="巨潮资讯网/历史公告")
    backfill_parser.add_argument("--start-date", default="2025-01-01")
    backfill_parser.add_argument("--end-date", default="2026-01-01")
    backfill_parser.add_argument("--max-rows", type=int, default=5000)
    backfill_parser.add_argument("--offset", type=int, default=0)
    backfill_parser.add_argument("--id-min", type=int, default=0)
    backfill_parser.add_argument("--id-max", type=int, default=0)
    backfill_parser.add_argument("--shard-count", type=int, default=0)
    backfill_parser.add_argument("--shard-index", type=int, default=0)
    backfill_parser.add_argument("--workers", type=int, default=8)
    backfill_parser.add_argument("--retries", type=int, default=3)
    backfill_parser.add_argument("--sleep-sec", type=float, default=0.02)
    backfill_parser.add_argument("--progress-every", type=int, default=10)
    backfill_parser.add_argument("--heartbeat-sec", type=float, default=5.0)
    backfill_parser.add_argument("--detail-timeout-sec", type=float, default=20.0)
    backfill_parser.add_argument("--pdf-timeout-sec", type=float, default=20.0)
    backfill_parser.add_argument("--db-flush-every", type=int, default=100)
    backfill_parser.add_argument("--fulltext-max-chars", type=int, default=12000)
    backfill_parser.add_argument("--skip-db-load", action="store_true")
    return parser
