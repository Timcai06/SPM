#!/usr/bin/env python3
"""Parser helpers for event normalization commands."""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLASSIFY_INPUT_FILES = [
    "output/sources/source_gov.csv",
    "output/sources/source_ndrc.csv",
    "output/sources/source_csrc.csv",
    "output/sources/source_sse.csv",
    "output/sources/source_cninfo.csv",
    "output/sources/source_szse.csv",
    "output/sources/source_szse_suspension.csv",
    "output/sources/source_yicai.csv",
    "output/sources/source_eastmoney.csv",
    "output/sources/source_36kr.csv",
    "output/sources/source_caixin.csv",
    "output/sources/source_miit.csv",
    "output/seeds/manual_news.csv",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Event normalization entrypoint.")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="collect live data, normalize events, and optionally analyze")
    run_parser.add_argument("--limit", type=int, default=8)
    run_parser.add_argument("--db", default="stock_event_mining")
    run_parser.add_argument("--skip-collect", action="store_true")
    run_parser.add_argument("--skip-validate", action="store_true")
    run_parser.add_argument("--with-analysis", action="store_true")
    run_parser.add_argument("--analysis-mode", default="event-study")
    run_parser.add_argument("--benchmark", default="hs300")
    run_parser.add_argument("--event-windows", default="1,3,5")
    run_parser.add_argument("--time-budget-sec", type=int, default=300)
    run_parser.add_argument("--max-analysis-rows", type=int, default=300)
    run_parser.add_argument("--api-timeout-sec", type=float, default=20.0)
    run_parser.add_argument("--progress-every", type=int, default=10)
    run_parser.add_argument("--use-llm", action="store_true")
    run_parser.add_argument("--llm-max-rows", type=int, default=20)

    classify_parser = sub.add_parser("classify", help="classify and structure events")
    classify_parser.add_argument("--db", default="stock_event_mining")
    classify_parser.add_argument("--skip-db-load", action="store_true")
    classify_parser.add_argument("--use-llm", action="store_true")
    classify_parser.add_argument("--llm-max-rows", type=int, default=20)

    classify_pending_parser = sub.add_parser(
        "classify-pending",
        help="classify raw_documents not yet in event_candidates",
    )
    classify_pending_parser.add_argument("--db", default="stock_event_mining")
    classify_pending_parser.add_argument("--batch-size", type=int, default=2000)
    classify_pending_parser.add_argument("--max-batches", type=int, default=1)
    classify_pending_parser.add_argument("--use-llm", action="store_true")
    classify_pending_parser.add_argument("--llm-max-rows", type=int, default=20)

    reclassify_parser = sub.add_parser("reclassify-source", help="reclassify raw_documents for one source")
    reclassify_parser.add_argument("--db", default="stock_event_mining")
    reclassify_parser.add_argument("--source", required=True)
    reclassify_parser.add_argument("--batch-size", type=int, default=3000)
    reclassify_parser.add_argument("--max-batches", type=int, default=1)
    reclassify_parser.add_argument("--use-llm", action="store_true")
    reclassify_parser.add_argument("--llm-max-rows", type=int, default=20)

    sub.add_parser("canonicalize", help="build canonical event clusters")

    canonical_load_parser = sub.add_parser("canonical-load", help="load canonical events into PostgreSQL")
    canonical_load_parser.add_argument("--db", default="stock_event_mining")
    canonical_load_parser.add_argument("--canonical-events", default="output/canonical_events.csv")
    canonical_load_parser.add_argument("--canonical-map", default="output/event_canonical_map.csv")
    return parser

