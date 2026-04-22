#!/usr/bin/env python3
"""Load Task 1 CSV outputs into PostgreSQL."""

from __future__ import annotations

import argparse
import csv
import hashlib
import subprocess
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.storage.db_guard import dsn_for, write_guard
from modules.collectors.services.raw_document_loading_service import (
    safe_normalize_datetime,
    sanitize_text,
    upsert_raw_documents as module_upsert_raw_documents,
)
from modules.events.services.event_persistence_service import (
    insert_final_rows as module_insert_final_rows,
    load_stage_rows as module_load_stage_rows,
)


ROOT = Path(__file__).resolve().parents[3]
RAW_SOURCE_FILES = [
    ROOT / "output" / "sources" / "source_gov.csv",
    ROOT / "output" / "sources" / "source_ndrc.csv",
    ROOT / "output" / "sources" / "source_csrc.csv",
    ROOT / "output" / "sources" / "source_sse.csv",
    ROOT / "output" / "sources" / "source_cninfo.csv",
    ROOT / "output" / "sources" / "source_szse.csv",
    ROOT / "output" / "sources" / "source_szse_suspension.csv",
    ROOT / "output" / "sources" / "source_yicai.csv",
    ROOT / "output" / "sources" / "source_eastmoney.csv",
    ROOT / "output" / "sources" / "source_36kr.csv",
    ROOT / "output" / "sources" / "source_caixin.csv",
    ROOT / "output" / "sources" / "source_miit.csv",
    ROOT / "output" / "seeds" / "manual_news.csv",
]
RAW_CANDIDATES_PATH = ROOT / "output" / "raw_event_candidates.csv"
STRUCTURED_EVENTS_PATH = ROOT / "output" / "structured_events.csv"
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load Task 1 outputs into PostgreSQL.")
    parser.add_argument("--db", default="stock_event_mining", help="Target PostgreSQL database name.")
    parser.add_argument("--quiet", action="store_true", help="Reduce non-essential output.")
    parser.add_argument("--lock-timeout-sec", type=int, default=120, help="Max seconds to wait for DB write lock.")
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        cleaned_lines = (line.replace("\x00", "") for line in f)
        return list(csv.DictReader(cleaned_lines))


def load_raw_documents() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in RAW_SOURCE_FILES:
        if not path.exists():
            continue
        for row in read_csv(path):
            if row.get("url") == "local://manual-seed":
                continue
            title = (row.get("title") or "").strip()
            content = (row.get("content") or "").strip()
            if not content:
                content = title or "(empty)"
            content_hash = hashlib.md5(
                f"{title}::{content}".encode("utf-8")
            ).hexdigest()
            rows.append(
                {
                    "source": row.get("source", "unknown"),
                    "source_type": "text_source",
                    "title": title,
                    "content": content,
                    "publish_time": safe_normalize_datetime(row.get("publish_time", "")),
                    "url": row.get("url", ""),
                    "symbol_or_subject": row.get("symbol_or_subject", ""),
                    "content_hash": content_hash,
                }
            )
    return rows

def run_psql(db: str, sql: str) -> None:
    subprocess.run(
        ["psql", "-d", db, "-v", "ON_ERROR_STOP=1", "-c", sql],
        check=True,
        cwd=str(ROOT),
    )

def upsert_raw_documents(db: str, rows: list[dict[str, str]]) -> None:
    module_upsert_raw_documents(db, rows)


def load_stage_tables(db: str, raw_documents: list[dict[str, str]], raw_candidates: list[dict[str, str]], structured_events: list[dict[str, str]]) -> None:
    module_load_stage_rows(db, raw_documents, raw_candidates, structured_events)


def insert_final_tables(db: str) -> None:
    module_insert_final_rows(db)


def main() -> None:
    args = parse_args()
    db = args.db

    with write_guard(
        db_name=db,
        required_tables=[
            "raw_documents",
            "event_candidates",
            "structured_events",
            "stg_event_candidates",
            "stg_structured_events",
        ],
        lock_timeout_sec=args.lock_timeout_sec,
    ):
        raw_documents = load_raw_documents()
        raw_candidates = read_csv(RAW_CANDIDATES_PATH)
        structured_events = read_csv(STRUCTURED_EVENTS_PATH)
        load_stage_tables(db, raw_documents, raw_candidates, structured_events)
        insert_final_tables(db)

    if not args.quiet:
        print(f"Loaded {len(raw_documents)} raw documents into {db}")
        print(f"Loaded {len(raw_candidates)} event candidates into {db}")
        print(f"Loaded {len(structured_events)} structured events into {db}")


if __name__ == "__main__":
    main()
