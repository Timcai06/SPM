#!/usr/bin/env python3
"""Parser helpers for quality and delivery commands."""

from __future__ import annotations

import argparse

from cli.quality_support import DEFAULT_COLLECTOR_REPORT, DEFAULT_FEATURE_REPORT, DEFAULT_QA_SNAPSHOT


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Quality and delivery entrypoint.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="validate output datasets")

    quality_parser = sub.add_parser("quality", aliases=["sample"], help="build quality sample/report")
    quality_parser.add_argument("--sample-size", type=int, default=50)
    quality_parser.add_argument("--run-id", default="")

    db_status_parser = sub.add_parser("db-status", aliases=["db"], help="show core table row counts")
    db_status_parser.add_argument("--db", default="stock_event_mining")

    qa_parser = sub.add_parser("qa", aliases=["summary"], help="show batch quality summary with deltas")
    qa_parser.add_argument("--db", default="stock_event_mining")
    qa_parser.add_argument("--snapshot-path", default=str(DEFAULT_QA_SNAPSHOT))
    qa_parser.add_argument("--collector-report", default=str(DEFAULT_COLLECTOR_REPORT))
    qa_parser.add_argument("--feature-report", default=str(DEFAULT_FEATURE_REPORT))

    storage_parser = sub.add_parser("storage-audit", help="show database storage footprint")
    storage_parser.add_argument("--db", default="stock_event_mining")

    clean_stage_parser = sub.add_parser("clean-stage", help="truncate rebuildable stage tables")
    clean_stage_parser.add_argument("--db", default="stock_event_mining")
    clean_stage_parser.add_argument("--lock-timeout-sec", type=int, default=120)
    clean_stage_parser.add_argument("--yes", action="store_true")

    delivery_parser = sub.add_parser("delivery-status", help="check formal data-delivery table readiness")
    delivery_parser.add_argument("--db", default="stock_event_mining")
    delivery_parser.add_argument("--output", default="")
    delivery_parser.add_argument("--fail-on-blockers", action="store_true")
    return parser
