#!/usr/bin/env python3
"""One-shot Task 1 workflow: collect -> classify -> load -> validate."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = "stock_event_mining"


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
    parser.add_argument("--time-budget-sec", type=int, default=300, help="Time budget for analysis step.")
    parser.add_argument("--max-analysis-rows", type=int, default=300, help="Max rows for analysis step.")
    parser.add_argument("--api-timeout-sec", type=float, default=20.0, help="Per request timeout for analysis fetch.")
    parser.add_argument("--progress-every", type=int, default=10, help="Print analysis progress every N rows.")
    parser.add_argument("--use-llm", action="store_true", help="Enable LLM enrichment for a small rule-positive subset.")
    parser.add_argument("--llm-max-rows", type=int, default=20, help="Max rows to enrich with LLM in one run.")
    return parser.parse_args()

from modules.collectors.services.collect_service import collect_all_async
from modules.events.jobs.classify_job import run_classification_pipeline
from modules.events.jobs.canonicalize_job import run_canonicalization_pipeline
from modules.quality.services.validation_service import run_validation_pipeline
from capabilities.storage.load_task1_canonical import run_loading_pipeline
from capabilities.storage.load_task1 import upsert_raw_documents
from modules.analysis.jobs.feature_return_job import main as analysis_main


def main() -> None:
    args = parse_args()
    db = args.db

    # 1. Collection
    if not args.skip_collect:
        print(f"--- Phase 1: Asynchronous Collection (limit={args.limit}) ---")
        all_rows = asyncio.run(collect_all_async(args.limit, include_non_keyword=False))
        print(f"Collected {len(all_rows)} documents in memory.")
        
        # 2. Storage Upsert
        if all_rows:
            print(f"Upserting {len(all_rows)} documents to database '{db}'...")
            upsert_raw_documents(db, all_rows)
    else:
        print("Skipping collection phase.")

    # 3. Classification
    print(f"--- Phase 2: Identification & Classification (DB: {db}) ---")
    candidate_rows, structured_rows = asyncio.run(
        run_classification_pipeline(db, use_llm=args.use_llm, llm_max_rows=args.llm_max_rows)
    )
    print(f"Identified {len(structured_rows)} structured events from candidates.")

    # 4. Canonicalization
    print("--- Phase 3: Canonicalization (Grouping) ---")
    canonical_rows, mapping_rows = run_canonicalization_pipeline(db=db)
    print(f"Grouped into {len(canonical_rows)} canonical event clusters.")

    # 5. Loading Canonical Layer
    print("--- Phase 4: Loading Canonical Layer ---")
    run_loading_pipeline(
        db=db,
        canonical_event_rows=canonical_rows,
        canonical_link_rows=mapping_rows,
        quiet=False
    )

    # 6. Validation
    if not args.skip_validate:
        print("--- Phase 5: Validation ---")
        success = run_validation_pipeline(candidate_rows, structured_rows)
        if not success:
            print("[WARN] Validation failed, but continuing.")

    # 7. Analysis (Optional)
    if args.with_analysis:
        print("--- Phase 6: Event Analysis (Event Study) ---")
        # For analysis_main, we might still need patched_argv if it's not refactored yet,
        # but let's try to keep it simple for now or use the existing one if it works.
        # Actually, let's keep it as is since it's an optional extension.
        from contextlib import contextmanager
        @contextmanager
        def patched_argv(argv: list[str]):
            old = sys.argv[:]
            sys.argv = argv
            try:
                yield
            finally:
                sys.argv = old
        
        with patched_argv(
            [
                "feature_return.py",
                "--db", db,
                "--analysis-mode", args.analysis_mode,
                "--benchmark", args.benchmark,
                "--event-windows", args.event_windows,
                "--time-budget-sec", str(args.time_budget_sec),
                "--max-rows", str(args.max_analysis_rows),
                "--api-timeout-sec", str(args.api_timeout_sec),
                "--progress-every", str(args.progress_every),
            ]
        ):
            analysis_main()

    print(f"\nTask 1 workflow completed successfully for database: {db}")


if __name__ == "__main__":
    main()
