#!/usr/bin/env python3
"""Parser helpers for research commands."""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Research and sample-building entrypoint.")
    sub = parser.add_subparsers(dest="command", required=True)

    feature_parser = sub.add_parser("feature", help="run feature-return analysis")
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
    feature_parser.add_argument("--dataset-path", default="output/event_return_dataset.csv")
    feature_parser.add_argument("--report-path", default="output/feature_return_report.md")
    feature_parser.add_argument("--market-max-rows", type=int, default=1200)

    train_parser = sub.add_parser("train-samples", help="build model-ready training samples into DB")
    train_parser.add_argument("--db", default="stock_event_mining")
    train_parser.add_argument("--min-link-score", type=float, default=0.35)
    train_parser.add_argument("--label-dataset", default="output/event_return_dataset.csv")
    train_parser.add_argument("--run-id", default="")

    negative_parser = sub.add_parser("build-negative-samples", help="build non-event training samples")
    negative_parser.add_argument("--db", default="stock_event_mining")
    negative_parser.add_argument("--start-date", default="")
    negative_parser.add_argument("--end-date", default="")
    negative_parser.add_argument("--max-per-day", type=int, default=100)
    negative_parser.add_argument("--min-link-score", type=float, default=0.35)
    negative_parser.add_argument("--run-id", default="")
    return parser
