#!/usr/bin/env python3
"""Unified CLI entrypoint for Task 1."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

import psycopg

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from modules.analysis.jobs import feature_return_job, train_samples_job
from modules.collectors.jobs import cninfo_fulltext_backfill_job, collect_job, history_job
from modules.events.jobs import (
    canonicalize_job,
    classify_job,
    classify_pending_job,
    reclassify_source_job,
)
from modules.events.services.canonical_loading_service import load_canonical_rows
from modules.quality.jobs import check_job, delivery_status_job, quality_report_job
from capabilities.storage.db_guard import dsn_for
from pipelines import task1 as task1_pipeline
from cli.task1_parser import CLASSIFY_INPUT_FILES, ROOT, build_parser

def parse_args() -> argparse.Namespace:
    return build_parser().parse_args()


def print_db_status(db_name: str) -> None:
    table_names = [
        "raw_documents",
        "structured_events",
        "company_relations",
        "company_profiles",
        "stock_daily_quotes",
        "market_environment_daily",
        "sentiment_propagation_daily",
        "model_event_samples",
        "int_event_candidates",
        "int_canonical_events",
        "int_event_canonical_links",
        "int_company_stats",
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
        "company_relations",
        "company_profiles",
        "stock_daily_quotes",
        "market_environment_daily",
        "sentiment_propagation_daily",
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


def run_pipeline_command(args: argparse.Namespace) -> None:
    argv = ["--limit", str(args.limit), "--db", args.db]
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
    task1_pipeline.main(argv)


def run_collect_command(args: argparse.Namespace) -> None:
    argv = ["--limit", str(args.limit)]
    if args.include_non_keyword:
        argv.append("--include-non-keyword")
    collect_job.main(argv)


def run_collect_history_command(args: argparse.Namespace) -> None:
    argv = [
        "--db",
        args.db,
        "--source",
        args.source,
        "--symbol-source",
        args.symbol_source,
        "--symbol-file",
        args.symbol_file,
        "--start-date",
        args.start_date,
        "--end-date",
        args.end_date,
        "--max-symbols",
        str(args.max_symbols),
        "--offset",
        str(args.offset),
        "--limit-per-symbol",
        str(args.limit_per_symbol),
        "--workers",
        str(args.workers),
        "--retries",
        str(args.retries),
        "--sleep-sec",
        str(args.sleep_sec),
        "--db-flush-every",
        str(args.db_flush_every),
        "--output-dir",
        args.output_dir,
    ]
    if args.skip_db_load:
        argv.append("--skip-db-load")
    if args.cninfo_fulltext:
        argv.append("--cninfo-fulltext")
    argv.extend(["--cninfo-fulltext-max-chars", str(args.cninfo_fulltext_max_chars)])
    history_job.main(argv)


def run_cninfo_backfill_command(args: argparse.Namespace) -> None:
    argv = [
        "--db",
        args.db,
        "--source",
        args.source,
        "--start-date",
        args.start_date,
        "--end-date",
        args.end_date,
        "--max-rows",
        str(args.max_rows),
        "--offset",
        str(args.offset),
        "--id-min",
        str(args.id_min),
        "--id-max",
        str(args.id_max),
        "--shard-count",
        str(args.shard_count),
        "--shard-index",
        str(args.shard_index),
        "--workers",
        str(args.workers),
        "--retries",
        str(args.retries),
        "--sleep-sec",
        str(args.sleep_sec),
        "--db-flush-every",
        str(args.db_flush_every),
        "--fulltext-max-chars",
        str(args.fulltext_max_chars),
    ]
    if args.skip_db_load:
        argv.append("--skip-db-load")
    cninfo_fulltext_backfill_job.main(argv)


def run_classify_command(args: argparse.Namespace) -> None:
    argv = ["--db", args.db]
    existing_inputs = [input_file for input_file in CLASSIFY_INPUT_FILES if (ROOT / input_file).exists()]
    for input_file in existing_inputs:
        argv.extend(["--input", input_file])
    if args.skip_db_load:
        argv.append("--skip-db-load")
    if args.use_llm:
        argv.extend(["--use-llm", "--llm-max-rows", str(args.llm_max_rows)])
    classify_job.main(argv)


def run_feature_command(args: argparse.Namespace) -> None:
    argv = [
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
    feature_return_job.main(argv)


def run_classify_pending_command(args: argparse.Namespace) -> None:
    argv = [
        "--db",
        args.db,
        "--batch-size",
        str(args.batch_size),
        "--max-batches",
        str(args.max_batches),
    ]
    if args.use_llm:
        argv.extend(["--use-llm", "--llm-max-rows", str(args.llm_max_rows)])
    classify_pending_job.main(argv)


def run_reclassify_source_command(args: argparse.Namespace) -> None:
    argv = [
        "--db",
        args.db,
        "--source",
        args.source,
        "--batch-size",
        str(args.batch_size),
        "--max-batches",
        str(args.max_batches),
    ]
    if args.use_llm:
        argv.extend(["--use-llm", "--llm-max-rows", str(args.llm_max_rows)])
    reclassify_source_job.main(argv)


def run_check_command(_args: argparse.Namespace) -> None:
    check_job.main([])


def run_canonicalize_command(_args: argparse.Namespace) -> None:
    canonicalize_job.main([])


def run_canonical_load_command(args: argparse.Namespace) -> None:
    load_canonical_rows(
        db=args.db,
        canonical_event_rows=None,
        canonical_link_rows=None,
        canonical_events_path=args.canonical_events,
        canonical_map_path=args.canonical_map,
        quiet=False,
    )


def run_quality_command(args: argparse.Namespace) -> None:
    argv = ["--sample-size", str(args.sample_size)]
    if args.run_id:
        argv.extend(["--run-id", args.run_id])
    quality_report_job.main(argv)


def run_train_samples_command(args: argparse.Namespace) -> None:
    argv = [
        "--db",
        args.db,
        "--min-link-score",
        str(args.min_link_score),
        "--label-dataset",
        args.label_dataset,
    ]
    if args.run_id:
        argv.extend(["--run-id", args.run_id])
    train_samples_job.main(argv)


def run_db_status_command(args: argparse.Namespace) -> None:
    print_db_status(args.db)


def run_qa_command(args: argparse.Namespace) -> None:
    print_qa_summary(
        db_name=args.db,
        snapshot_path=Path(args.snapshot_path).resolve(),
        collector_report=Path(args.collector_report).resolve(),
        feature_report=Path(args.feature_report).resolve(),
    )


def run_delivery_status_command(args: argparse.Namespace) -> None:
    argv = ["--db", args.db]
    if args.output:
        argv.extend(["--output", args.output])
    if args.fail_on_blockers:
        argv.append("--fail-on-blockers")
    delivery_status_job.main(argv)


COMMAND_HANDLERS: dict[str, Callable[[argparse.Namespace], None]] = {
    "run": run_pipeline_command,
    "collect": run_collect_command,
    "collect-history": run_collect_history_command,
    "backfill-cninfo-fulltext": run_cninfo_backfill_command,
    "classify": run_classify_command,
    "classify-pending": run_classify_pending_command,
    "reclassify-source": run_reclassify_source_command,
    "check": run_check_command,
    "canonicalize": run_canonicalize_command,
    "canonical-load": run_canonical_load_command,
    "quality": run_quality_command,
    "feature": run_feature_command,
    "train-samples": run_train_samples_command,
    "db-status": run_db_status_command,
    "qa": run_qa_command,
    "delivery-status": run_delivery_status_command,
}


def main() -> None:
    args = parse_args()
    handler = COMMAND_HANDLERS.get(args.command)
    if handler is None:
        raise ValueError(f"Unsupported command: {args.command}")
    handler(args)

if __name__ == "__main__":
    main()
