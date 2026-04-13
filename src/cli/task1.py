#!/usr/bin/env python3
"""Unified CLI entrypoint for Task 1."""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import psycopg

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.analysis import build_model_samples, feature_return
from capabilities.collectors import run as collector_run
from capabilities.events import canonicalize, classify
from capabilities.quality import check, quality_report
from capabilities.storage import load_task1_canonical
from capabilities.storage.db_guard import dsn_for
from pipelines import task1 as task1_pipeline

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
    run_parser.add_argument("--api-timeout-sec", type=float, default=20.0)
    run_parser.add_argument("--progress-every", type=int, default=10)
    run_parser.add_argument("--use-llm", action="store_true")
    run_parser.add_argument("--llm-max-rows", type=int, default=20)

    collect_parser = sub.add_parser("collect", help="collect source data")
    collect_parser.add_argument("--limit", type=int, default=10)
    collect_parser.add_argument("--include-non-keyword", action="store_true")

    classify_parser = sub.add_parser("classify", help="classify and structure events")
    classify_parser.add_argument("--db", default="stock_event_mining")
    classify_parser.add_argument("--skip-db-load", action="store_true")
    classify_parser.add_argument("--use-llm", action="store_true")
    classify_parser.add_argument("--llm-max-rows", type=int, default=20)

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

    train_sample_parser = sub.add_parser("train-samples", help="build model-ready training samples into DB")
    train_sample_parser.add_argument("--db", default="stock_event_mining")
    train_sample_parser.add_argument("--min-link-score", type=float, default=0.35)
    train_sample_parser.add_argument("--label-dataset", default="output/task1_event_return_dataset.csv")
    train_sample_parser.add_argument("--run-id", default="")

    db_status_parser = sub.add_parser("db-status", help="show core table row counts")
    db_status_parser.add_argument("--db", default="stock_event_mining")

    qa_parser = sub.add_parser("qa", help="show batch quality summary with deltas")
    qa_parser.add_argument("--db", default="stock_event_mining")
    qa_parser.add_argument("--snapshot-path", default=str(DEFAULT_QA_SNAPSHOT))
    qa_parser.add_argument("--collector-report", default=str(DEFAULT_COLLECTOR_REPORT))
    qa_parser.add_argument("--feature-report", default=str(DEFAULT_FEATURE_REPORT))

    return parser.parse_args()


def print_db_status(db_name: str) -> None:
    table_names = [
        "raw_documents",
        "int_event_candidates",
        "structured_events",
        "int_canonical_events",
        "int_event_canonical_links",
        "int_company_stats",
        "model_event_samples",
        "int_model_non_event_samples",
    ]
    print(f"Database status for: {db_name}")
    with psycopg.connect(dsn_for(db_name)) as conn:
        with conn.cursor() as cur:
            for table in table_names:
                cur.execute("SELECT to_regclass(%s)", (f"public.{table}",))
                exists = cur.fetchone()[0]
                if exists is None:
                    print(f"- {table}: missing")
                    continue
                cur.execute(f"SELECT count(*) FROM {table}")
                count = cur.fetchone()[0]
                print(f"- {table}: {count}")


def parse_feature_top_reasons(path: Path, top_n: int = 3) -> list[tuple[str, int]]:
    if not path.exists():
        return []
    reasons: list[tuple[str, int]] = []
    in_section = False
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if text.startswith("## 三、不可计算样本原因"):
            in_section = True
            continue
        if in_section and text.startswith("## "):
            break
        if in_section and text.startswith("- ") and ":" in text:
            key, value = text[2:].split(":", 1)
            try:
                reasons.append((key.strip(), int(value.strip())))
            except Exception:
                continue
    reasons.sort(key=lambda x: x[1], reverse=True)
    return reasons[:top_n]


def parse_collector_failures(path: Path, top_n: int = 3) -> list[tuple[str, int]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    counter: dict[str, int] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        if str(item.get("success", "")).lower() == "true":
            continue
        category = str(item.get("failure_category") or "unknown").strip() or "unknown"
        counter[category] = counter.get(category, 0) + 1
    pairs = sorted(counter.items(), key=lambda x: x[1], reverse=True)
    return pairs[:top_n]


def print_qa_summary(db_name: str, snapshot_path: Path, collector_report: Path, feature_report: Path) -> None:
    keys = [
        "raw_documents",
        "structured_events",
        "event_company_links",
        "int_event_propagation_links",
        "model_event_samples",
        "int_model_non_event_samples",
        "int_company_stats",
    ]
    counts: dict[str, int] = {}
    labeled = 0
    with psycopg.connect(dsn_for(db_name)) as conn:
        with conn.cursor() as cur:
            for table in keys:
                cur.execute("SELECT to_regclass(%s)", (f"public.{table}",))
                exists = cur.fetchone()[0]
                if exists is None:
                    counts[table] = -1
                    continue
                cur.execute(f"SELECT count(*) FROM {table}")
                counts[table] = int(cur.fetchone()[0])
            cur.execute(
                """
                SELECT count(*)
                FROM model_event_samples
                WHERE label_car_w1 IS NOT NULL OR label_car_w3 IS NOT NULL OR label_car_w5 IS NOT NULL
                """
            )
            labeled = int(cur.fetchone()[0])

    prev_counts: dict[str, int] = {}
    if snapshot_path.exists():
        try:
            payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
            prev_counts = {str(k): int(v) for k, v in payload.get("counts", {}).items()}
        except Exception:
            prev_counts = {}

    total_samples = counts.get("model_event_samples", 0)
    label_ratio = (labeled / total_samples) if total_samples > 0 else 0.0
    print(f"QA summary for: {db_name}")
    for key in keys:
        current = counts.get(key, -1)
        prev = prev_counts.get(key)
        if current < 0:
            print(f"- {key}: missing")
            continue
        if prev is None:
            print(f"- {key}: {current} (delta: n/a)")
        else:
            print(f"- {key}: {current} (delta: {current - prev:+d})")
    print(f"- labeled_samples: {labeled}")
    print(f"- label_ratio: {label_ratio:.2%}")

    collector_top = parse_collector_failures(collector_report, top_n=3)
    feature_top = parse_feature_top_reasons(feature_report, top_n=3)
    if collector_top:
        text = ", ".join(f"{k}:{v}" for k, v in collector_top)
        print(f"- collector_fail_top3: {text}")
    else:
        print("- collector_fail_top3: none")
    if feature_top:
        text = ", ".join(f"{k}:{v}" for k, v in feature_top)
        print(f"- feature_reason_top3: {text}")
    else:
        print("- feature_reason_top3: none")

    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(
        json.dumps(
            {
                "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "db": db_name,
                "counts": counts,
                "labeled_samples": labeled,
                "label_ratio": label_ratio,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


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
                "--api-timeout-sec",
                str(args.api_timeout_sec),
                "--progress-every",
                str(args.progress_every),
            ]
        )
        if args.use_llm:
            argv.extend(["--use-llm", "--llm-max-rows", str(args.llm_max_rows)])
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
        if args.use_llm:
            argv.extend(["--use-llm", "--llm-max-rows", str(args.llm_max_rows)])
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
            "--api-timeout-sec",
            str(args.api_timeout_sec),
            "--progress-every",
            str(args.progress_every),
            "--market-max-rows",
            str(args.market_max_rows),
            "--dataset-path",
            args.dataset_path,
            "--report-path",
            args.report_path,
        ]
        if args.tushare_token:
            argv.extend(["--tushare-token", args.tushare_token])
        if args.tushare_token_file:
            argv.extend(["--tushare-token-file", args.tushare_token_file])
        if args.disable_tushare:
            argv.append("--disable-tushare")
        if args.disable_cache:
            argv.append("--disable-cache")
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

    if args.command == "db-status":
        print_db_status(args.db)
        return

    if args.command == "qa":
        print_qa_summary(
            db_name=args.db,
            snapshot_path=Path(args.snapshot_path).resolve(),
            collector_report=Path(args.collector_report).resolve(),
            feature_report=Path(args.feature_report).resolve(),
        )
        return

if __name__ == "__main__":
    main()
