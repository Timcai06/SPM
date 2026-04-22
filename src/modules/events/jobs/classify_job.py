#!/usr/bin/env python3
"""Task1 event classification jobs.

This module owns command/job orchestration. The legacy classify module still
provides the core algorithm until the remaining domain functions are split.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from modules.events.adapters.file_inputs import load_rows_from_inputs
from modules.events.adapters.db_repository import (
    insert_event_final_rows,
    load_event_stage_rows,
    load_rows_from_db,
)
from modules.events.domain.classification_rules import (
    AUTHORITY_LEVEL_RULES,
    NEGATIVE_WORDS,
    POSITIVE_WORDS,
    REGION_SCOPE_RULES,
    SHOCK_SOURCE_RULES,
    SOURCE_TYPE_RULES,
    STAGE_RULES,
    STRONG_TRIGGER_WORDS,
    SUBTYPE_FALLBACK_BY_SUBJECT,
    SUBTYPE_RULES,
    TIME_ORIENTATION_RULES,
    UNCERTAINTY_WORDS,
)
from modules.events.domain.classification_schema import RAW_CANDIDATE_FIELDS, STRUCTURED_EVENT_FIELDS
from modules.events.services.classification_service import classify_rows_async
from modules.events.services.structured_event_builder import ensure_output_dir, write_csv

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DB_NAME = "stock_event_mining"
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
STRUCTURED_BUILDER_CONFIG = {
    "positive_words": POSITIVE_WORDS,
    "negative_words": NEGATIVE_WORDS,
    "source_type_rules": SOURCE_TYPE_RULES,
    "authority_level_rules": AUTHORITY_LEVEL_RULES,
    "subtype_rules": SUBTYPE_RULES,
    "subtype_fallbacks": SUBTYPE_FALLBACK_BY_SUBJECT,
    "time_orientation_rules": TIME_ORIENTATION_RULES,
    "stage_rules": STAGE_RULES,
    "shock_source_rules": SHOCK_SOURCE_RULES,
    "region_scope_rules": REGION_SCOPE_RULES,
    "strong_trigger_words": STRONG_TRIGGER_WORDS,
    "uncertainty_words": UNCERTAINTY_WORDS,
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the event structuring pipeline.")
    parser.add_argument("--input", action="append", dest="inputs")
    parser.add_argument("--output-dir", default=str(ROOT / "output"))
    parser.add_argument("--db", default=DEFAULT_DB_NAME)
    parser.add_argument("--skip-db-load", action="store_true")
    parser.add_argument("--use-llm", action="store_true")
    parser.add_argument("--llm-max-rows", type=int, default=20)
    return parser.parse_args(argv)

async def run_classification_pipeline(
    db: str,
    input_rows: Optional[List[Dict[str, str]]] = None,
    use_llm: bool = False,
    llm_max_rows: int = 20,
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    rows = input_rows if input_rows is not None else load_rows_from_db(db)
    if not rows:
        print("No documents found for classification.")
        return [], []

    candidate_rows, structured_rows = await classify_rows_async(
        rows,
        builder_config=STRUCTURED_BUILDER_CONFIG,
        use_llm=use_llm,
        llm_max_rows=llm_max_rows,
    )
    load_event_stage_rows(db, [], candidate_rows, structured_rows)
    insert_event_final_rows(db)
    return candidate_rows, structured_rows


def run_file_classification(args: argparse.Namespace) -> None:
    async def _run() -> None:
        if args.inputs:
            input_paths = [Path(p).resolve() for p in args.inputs]
        else:
            input_paths = [ROOT / p for p in CLASSIFY_INPUT_FILES if (ROOT / p).exists()]

        if input_paths:
            rows = load_rows_from_inputs(input_paths)
            print(f"Loaded {len(rows)} rows from {len(input_paths)} input file(s)")
            candidate_rows, structured_rows = await classify_rows_async(
                rows,
                builder_config=STRUCTURED_BUILDER_CONFIG,
                use_llm=args.use_llm,
                llm_max_rows=args.llm_max_rows,
            )
        elif args.skip_db_load:
            rows = load_rows_from_db(args.db)
            candidate_rows, structured_rows = await classify_rows_async(
                rows,
                builder_config=STRUCTURED_BUILDER_CONFIG,
                use_llm=args.use_llm,
                llm_max_rows=args.llm_max_rows,
            )
        else:
            candidate_rows, structured_rows = await run_classification_pipeline(
                args.db, use_llm=args.use_llm, llm_max_rows=args.llm_max_rows
            )

        output_dir = Path(args.output_dir).resolve()
        ensure_output_dir(output_dir)
        write_csv(
            output_dir / "raw_event_candidates.csv",
            candidate_rows,
            RAW_CANDIDATE_FIELDS,
        )
        write_csv(
            output_dir / "structured_events.csv",
            structured_rows,
            STRUCTURED_EVENT_FIELDS,
        )
        print(f"Wrote {len(candidate_rows)} raw candidates to {output_dir / 'raw_event_candidates.csv'}")
        print(f"Wrote {len(structured_rows)} structured events to {output_dir / 'structured_events.csv'}")

    asyncio.run(_run())


def main(argv: list[str] | None = None) -> None:
    run_file_classification(parse_args(argv))


if __name__ == "__main__":
    main()
