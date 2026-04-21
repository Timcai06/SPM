#!/usr/bin/env python3
"""Parser construction helpers for Task 1 CLI."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QA_SNAPSHOT = ROOT / "output" / "meta" / "qa_snapshot.json"
DEFAULT_COLLECTOR_REPORT = ROOT / "output" / "collector_report.json"
DEFAULT_FEATURE_REPORT = ROOT / "output" / "task1_feature_return_report.md"
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


def register_pipeline_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    run_parser = subparsers.add_parser("run", help="collect -> classify -> load -> validate")
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


def register_collector_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    collect_parser = subparsers.add_parser("collect", help="collect source data")
    collect_parser.add_argument("--limit", type=int, default=10)
    collect_parser.add_argument("--include-non-keyword", action="store_true")

    collect_history_parser = subparsers.add_parser(
        "collect-history",
        help="historically backfill raw documents",
    )
    collect_history_parser.add_argument("--db", default="stock_event_mining")
    collect_history_parser.add_argument(
        "--source",
        choices=["akshare-news", "cninfo-disclosure"],
        default="akshare-news",
    )
    collect_history_parser.add_argument("--symbol-source", choices=["db", "all-a"], default="db")
    collect_history_parser.add_argument("--symbol-file", default="")
    collect_history_parser.add_argument("--start-date", default="2020-01-01")
    collect_history_parser.add_argument("--end-date", default=datetime.now().date().isoformat())
    collect_history_parser.add_argument("--max-symbols", type=int, default=200)
    collect_history_parser.add_argument("--offset", type=int, default=0)
    collect_history_parser.add_argument("--limit-per-symbol", type=int, default=20)
    collect_history_parser.add_argument("--workers", type=int, default=4)
    collect_history_parser.add_argument("--retries", type=int, default=2)
    collect_history_parser.add_argument("--sleep-sec", type=float, default=0.05)
    collect_history_parser.add_argument("--output-dir", default="output/history")
    collect_history_parser.add_argument("--skip-db-load", action="store_true")
    collect_history_parser.add_argument("--db-flush-every", type=int, default=100)
    collect_history_parser.add_argument("--cninfo-fulltext", action="store_true")
    collect_history_parser.add_argument("--cninfo-fulltext-max-chars", type=int, default=12000)

    cninfo_backfill_parser = subparsers.add_parser(
        "backfill-cninfo-fulltext",
        help="backfill CNInfo fulltext using existing raw_documents URLs",
    )
    cninfo_backfill_parser.add_argument("--db", default="stock_event_mining")
    cninfo_backfill_parser.add_argument("--source", default="巨潮资讯网/历史公告")
    cninfo_backfill_parser.add_argument("--start-date", default="2025-01-01")
    cninfo_backfill_parser.add_argument("--end-date", default="2026-01-01")
    cninfo_backfill_parser.add_argument("--max-rows", type=int, default=5000)
    cninfo_backfill_parser.add_argument("--offset", type=int, default=0)
    cninfo_backfill_parser.add_argument("--id-min", type=int, default=0)
    cninfo_backfill_parser.add_argument("--id-max", type=int, default=0)
    cninfo_backfill_parser.add_argument("--shard-count", type=int, default=0)
    cninfo_backfill_parser.add_argument("--shard-index", type=int, default=0)
    cninfo_backfill_parser.add_argument("--workers", type=int, default=8)
    cninfo_backfill_parser.add_argument("--retries", type=int, default=3)
    cninfo_backfill_parser.add_argument("--sleep-sec", type=float, default=0.02)
    cninfo_backfill_parser.add_argument("--db-flush-every", type=int, default=100)
    cninfo_backfill_parser.add_argument("--fulltext-max-chars", type=int, default=12000)
    cninfo_backfill_parser.add_argument("--skip-db-load", action="store_true")


def register_event_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    classify_parser = subparsers.add_parser("classify", help="classify and structure events")
    classify_parser.add_argument("--db", default="stock_event_mining")
    classify_parser.add_argument("--skip-db-load", action="store_true")
    classify_parser.add_argument("--use-llm", action="store_true")
    classify_parser.add_argument("--llm-max-rows", type=int, default=20)

    classify_pending_parser = subparsers.add_parser(
        "classify-pending",
        help="classify raw_documents not yet in int_event_candidates",
    )
    classify_pending_parser.add_argument("--db", default="stock_event_mining")
    classify_pending_parser.add_argument("--batch-size", type=int, default=2000)
    classify_pending_parser.add_argument("--max-batches", type=int, default=1)
    classify_pending_parser.add_argument("--use-llm", action="store_true")
    classify_pending_parser.add_argument("--llm-max-rows", type=int, default=20)

    reclassify_source_parser = subparsers.add_parser(
        "reclassify-source",
        help="reclassify raw_documents for one source",
    )
    reclassify_source_parser.add_argument("--db", default="stock_event_mining")
    reclassify_source_parser.add_argument("--source", required=True)
    reclassify_source_parser.add_argument("--batch-size", type=int, default=3000)
    reclassify_source_parser.add_argument("--max-batches", type=int, default=1)
    reclassify_source_parser.add_argument("--use-llm", action="store_true")
    reclassify_source_parser.add_argument("--llm-max-rows", type=int, default=20)

    subparsers.add_parser("canonicalize", help="build canonical event clusters")
    canonical_load_parser = subparsers.add_parser(
        "canonical-load",
        help="load canonical events into PostgreSQL",
    )
    canonical_load_parser.add_argument("--db", default="stock_event_mining")
    canonical_load_parser.add_argument("--canonical-events", default="output/canonical_events.csv")
    canonical_load_parser.add_argument("--canonical-map", default="output/event_canonical_map.csv")

    subparsers.add_parser("check", help="validate output datasets")


def register_analysis_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    feature_parser = subparsers.add_parser("feature", help="run feature-return analysis")
    feature_parser.add_argument("--db", default="stock_event_mining")
    feature_parser.add_argument("--min-link-score", type=float, default=0.35)
    feature_parser.add_argument("--analysis-mode", default="event-study")
    feature_parser.add_argument("--benchmark", default="hs300")
    feature_parser.add_argument("--event-windows", default="1,3,5")
    feature_parser.add_argument("--tushare-token", default="")
    feature_parser.add_argument("--tushare-token-file", default="")
    feature_parser.add_argument("--disable-tushare", action="store_true")
    feature_parser.add_argument("--disable-cache", action="store_true")
    feature_parser.add_argument("--run-id", default="")
    feature_parser.add_argument("--time-budget-sec", type=int, default=300)
    feature_parser.add_argument("--max-rows", type=int, default=300)
    feature_parser.add_argument("--api-timeout-sec", type=float, default=20.0)
    feature_parser.add_argument("--progress-every", type=int, default=10)
    feature_parser.add_argument("--dataset-path", default="output/task1_event_return_dataset.csv")
    feature_parser.add_argument("--report-path", default="output/task1_feature_return_report.md")
    feature_parser.add_argument("--market-max-rows", type=int, default=1200)

    train_sample_parser = subparsers.add_parser(
        "train-samples",
        help="build model-ready training samples into DB",
    )
    train_sample_parser.add_argument("--db", default="stock_event_mining")
    train_sample_parser.add_argument("--min-link-score", type=float, default=0.35)
    train_sample_parser.add_argument("--label-dataset", default="output/task1_event_return_dataset.csv")
    train_sample_parser.add_argument("--run-id", default="")


def register_quality_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    quality_parser = subparsers.add_parser("quality", help="build quality sample/report")
    quality_parser.add_argument("--sample-size", type=int, default=50)
    quality_parser.add_argument("--run-id", default="")

    db_status_parser = subparsers.add_parser("db-status", help="show core table row counts")
    db_status_parser.add_argument("--db", default="stock_event_mining")

    qa_parser = subparsers.add_parser("qa", help="show batch quality summary with deltas")
    qa_parser.add_argument("--db", default="stock_event_mining")
    qa_parser.add_argument("--snapshot-path", default=str(DEFAULT_QA_SNAPSHOT))
    qa_parser.add_argument("--collector-report", default=str(DEFAULT_COLLECTOR_REPORT))
    qa_parser.add_argument("--feature-report", default=str(DEFAULT_FEATURE_REPORT))

    delivery_parser = subparsers.add_parser(
        "delivery-status",
        help="check formal data-delivery table readiness",
    )
    delivery_parser.add_argument("--db", default="stock_event_mining")
    delivery_parser.add_argument("--output", default="")
    delivery_parser.add_argument("--fail-on-blockers", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Task 1 command entrypoint.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    register_pipeline_commands(subparsers)
    register_collector_commands(subparsers)
    register_event_commands(subparsers)
    register_analysis_commands(subparsers)
    register_quality_commands(subparsers)
    return parser

