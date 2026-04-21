#!/usr/bin/env python3
"""Classify pending raw_documents into structured events."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from modules.events.adapters.db_repository import load_pending_raw_documents
from modules.events.jobs.classify_job import run_classification_pipeline


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classify pending raw_documents.")
    parser.add_argument("--db", default="stock_event_mining")
    parser.add_argument("--batch-size", type=int, default=2000)
    parser.add_argument("--max-batches", type=int, default=1)
    parser.add_argument("--use-llm", action="store_true")
    parser.add_argument("--llm-max-rows", type=int, default=20)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    total_candidates = 0
    total_structured = 0
    for batch_idx in range(args.max_batches):
        rows = load_pending_raw_documents(args.db, args.batch_size)
        if not rows:
            print(f"[classify-pending] no pending raw_documents at batch {batch_idx + 1}")
            break
        candidate_rows, structured_rows = asyncio.run(
            run_classification_pipeline(
                args.db,
                input_rows=rows,
                use_llm=args.use_llm,
                llm_max_rows=args.llm_max_rows,
            )
        )
        total_candidates += len(candidate_rows)
        total_structured += len(structured_rows)
        print(
            f"[classify-pending] batch {batch_idx + 1}/{args.max_batches}: "
            f"candidates={len(candidate_rows)}, structured={len(structured_rows)}"
        )
        if len(rows) < args.batch_size:
            break
    print(f"[classify-pending] total candidates={total_candidates}, structured={total_structured}")


if __name__ == "__main__":
    main()
