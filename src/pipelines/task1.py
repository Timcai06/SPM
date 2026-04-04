#!/usr/bin/env python3
"""One-shot Task 1 workflow: collect -> classify -> load -> validate."""

from __future__ import annotations

import argparse
import sys
from contextlib import contextmanager
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.analysis import feature_return
from capabilities.collectors import run as collector_run
from capabilities.events import canonicalize, classify
from capabilities.quality import check
from capabilities.storage import load_task1_canonical

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = "stock_event_mining"
CLASSIFY_INPUT_FILES = [
    "data/demo_news.csv",
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
    "data/manual_news.csv",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full Task 1 workflow.")
    parser.add_argument("--limit", type=int, default=8, help="Max rows to collect per live source.")
    parser.add_argument("--db", default=DEFAULT_DB, help="PostgreSQL database name.")
    parser.add_argument(
        "--skip-collect",
        action="store_true",
        help="Skip live source collection and only run classification/loading.",
    )
    parser.add_argument(
        "--skip-validate",
        action="store_true",
        help="Skip validation after loading.",
    )
    parser.add_argument("--with-analysis", action="store_true", help="Run event-study analysis after validation.")
    parser.add_argument("--analysis-mode", default="event-study", help="Analysis mode for feature step.")
    parser.add_argument("--benchmark", default="hs300", help="Benchmark id for analysis.")
    parser.add_argument("--event-windows", default="1,3,5", help="Event windows for analysis.")
    return parser.parse_args()


@contextmanager
def patched_argv(argv: list[str]):
    old = sys.argv[:]
    sys.argv = argv
    try:
        yield
    finally:
        sys.argv = old


def build_classify_argv(db: str) -> list[str]:
    argv = ["classify.py", "--db", db]
    for input_file in CLASSIFY_INPUT_FILES:
        argv.extend(["--input", input_file])
    return argv


def main() -> None:
    args = parse_args()

    if not args.skip_collect:
        with patched_argv(["run.py", "--limit", str(args.limit)]):
            collector_run.main()

    with patched_argv(build_classify_argv(args.db)):
        classify.main()

    with patched_argv(["canonicalize.py"]):
        canonicalize.main()

    with patched_argv(
        [
            "load_task1_canonical.py",
            "--db",
            args.db,
            "--canonical-events",
            "output/canonical_events.csv",
            "--canonical-map",
            "output/event_canonical_map.csv",
            "--quiet",
        ]
    ):
        load_task1_canonical.main()

    if not args.skip_validate:
        with patched_argv(["check.py"]):
            check.main()

    if args.with_analysis:
        with patched_argv(
            [
                "feature_return.py",
                "--db",
                args.db,
                "--analysis-mode",
                args.analysis_mode,
                "--benchmark",
                args.benchmark,
                "--event-windows",
                args.event_windows,
            ]
        ):
            feature_return.main()

    print(f"Task 1 workflow completed for database: {args.db}")


if __name__ == "__main__":
    main()
