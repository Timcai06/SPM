#!/usr/bin/env python3
"""Unified CLI entrypoint for Task 1."""

from __future__ import annotations

import argparse
import sys
from contextlib import contextmanager
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.analysis import build_model_samples, feature_return
from capabilities.collectors import run as collector_run
from capabilities.events import canonicalize, classify
from capabilities.quality import check, quality_report
from capabilities.storage import load_task1_canonical
from pipelines import task1 as task1_pipeline

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


@contextmanager
def patched_argv(argv: list[str]):
    old = sys.argv[:]
    sys.argv = argv
    try:
        yield
    finally:
        sys.argv = old


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Task 1 command entrypoint.")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="collect -> classify -> load -> validate")
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

    collect_parser = sub.add_parser("collect", help="collect source data")
    collect_parser.add_argument("--limit", type=int, default=10)
    collect_parser.add_argument("--include-non-keyword", action="store_true")

    classify_parser = sub.add_parser("classify", help="classify and structure events")
    classify_parser.add_argument("--db", default="stock_event_mining")
    classify_parser.add_argument("--skip-db-load", action="store_true")

    sub.add_parser("canonicalize", help="build canonical event clusters")
    canonical_load_parser = sub.add_parser("canonical-load", help="load canonical events into PostgreSQL")
    canonical_load_parser.add_argument("--db", default="stock_event_mining")
    canonical_load_parser.add_argument("--canonical-events", default="output/canonical_events.csv")
    canonical_load_parser.add_argument("--canonical-map", default="output/event_canonical_map.csv")

    sub.add_parser("check", help="validate output datasets")

    quality_parser = sub.add_parser("quality", help="build quality sample/report")
    quality_parser.add_argument("--sample-size", type=int, default=50)
    quality_parser.add_argument("--run-id", default="")

    feature_parser = sub.add_parser("feature", help="run feature-return analysis")
    feature_parser.add_argument("--db", default="stock_event_mining")
    feature_parser.add_argument("--min-link-score", type=float, default=0.35)
    feature_parser.add_argument("--analysis-mode", default="event-study")
    feature_parser.add_argument("--benchmark", default="hs300")
    feature_parser.add_argument("--event-windows", default="1,3,5")
    feature_parser.add_argument("--tushare-token", default="")
    feature_parser.add_argument("--tushare-token-file", default="")
    feature_parser.add_argument("--run-id", default="")
    feature_parser.add_argument("--time-budget-sec", type=int, default=300)
    feature_parser.add_argument("--max-rows", type=int, default=300)
    feature_parser.add_argument("--dataset-path", default="output/task1_event_return_dataset.csv")
    feature_parser.add_argument("--report-path", default="output/task1_feature_return_report.md")

    train_sample_parser = sub.add_parser("train-samples", help="build model-ready training samples into DB")
    train_sample_parser.add_argument("--db", default="stock_event_mining")
    train_sample_parser.add_argument("--min-link-score", type=float, default=0.35)
    train_sample_parser.add_argument("--label-dataset", default="output/task1_event_return_dataset.csv")
    train_sample_parser.add_argument("--run-id", default="")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "run":
        argv = ["task1.py", "--limit", str(args.limit), "--db", args.db]
        if args.skip_collect:
            argv.append("--skip-collect")
        if args.skip_validate:
            argv.append("--skip-validate")
        if args.with_analysis:
            argv.append("--with-analysis")
        argv.extend(
            [
                "--analysis-mode",
                args.analysis_mode,
                "--benchmark",
                args.benchmark,
                "--event-windows",
                args.event_windows,
                "--time-budget-sec",
                str(args.time_budget_sec),
                "--max-analysis-rows",
                str(args.max_analysis_rows),
            ]
        )
        with patched_argv(argv):
            task1_pipeline.main()
        return

    if args.command == "collect":
        argv = ["run.py", "--limit", str(args.limit)]
        if args.include_non_keyword:
            argv.append("--include-non-keyword")
        with patched_argv(argv):
            collector_run.main()
        return

    if args.command == "classify":
        argv = ["classify.py", "--db", args.db]
        for input_file in CLASSIFY_INPUT_FILES:
            argv.extend(["--input", input_file])
        if args.skip_db_load:
            argv.append("--skip-db-load")
        with patched_argv(argv):
            classify.main()
        return

    if args.command == "check":
        with patched_argv(["check.py"]):
            check.main()
        return

    if args.command == "canonicalize":
        with patched_argv(["canonicalize.py"]):
            canonicalize.main()
        return

    if args.command == "canonical-load":
        with patched_argv(
            [
                "load_task1_canonical.py",
                "--db",
                args.db,
                "--canonical-events",
                args.canonical_events,
                "--canonical-map",
                args.canonical_map,
            ]
        ):
            load_task1_canonical.main()
        return

    if args.command == "quality":
        argv = ["quality_report.py", "--sample-size", str(args.sample_size)]
        if args.run_id:
            argv.extend(["--run-id", args.run_id])
        with patched_argv(argv):
            quality_report.main()
        return

    if args.command == "feature":
        argv = [
            "feature_return.py",
            "--db",
            args.db,
            "--min-link-score",
            str(args.min_link_score),
            "--analysis-mode",
            args.analysis_mode,
            "--benchmark",
            args.benchmark,
            "--event-windows",
            args.event_windows,
            "--time-budget-sec",
            str(args.time_budget_sec),
            "--max-rows",
            str(args.max_rows),
            "--dataset-path",
            args.dataset_path,
            "--report-path",
            args.report_path,
        ]
        if args.tushare_token:
            argv.extend(["--tushare-token", args.tushare_token])
        if args.tushare_token_file:
            argv.extend(["--tushare-token-file", args.tushare_token_file])
        if args.run_id:
            argv.extend(["--run-id", args.run_id])
        with patched_argv(argv):
            feature_return.main()
        return

    if args.command == "train-samples":
        argv = [
            "build_model_samples.py",
            "--db",
            args.db,
            "--min-link-score",
            str(args.min_link_score),
            "--label-dataset",
            args.label_dataset,
        ]
        if args.run_id:
            argv.extend(["--run-id", args.run_id])
        with patched_argv(argv):
            build_model_samples.main()
        return

if __name__ == "__main__":
    main()
