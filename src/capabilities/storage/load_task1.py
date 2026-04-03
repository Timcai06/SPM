#!/usr/bin/env python3
"""Load Task 1 CSV outputs into PostgreSQL."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.storage.db_guard import write_guard


ROOT = Path(__file__).resolve().parents[3]
RAW_SOURCE_FILES = [
    ROOT / "data" / "demo_news.csv",
    ROOT / "data" / "source_gov.csv",
    ROOT / "data" / "source_ndrc.csv",
    ROOT / "data" / "source_csrc.csv",
    ROOT / "data" / "source_sse.csv",
    ROOT / "data" / "source_cninfo.csv",
    ROOT / "data" / "source_szse.csv",
    ROOT / "data" / "source_szse_suspension.csv",
    ROOT / "data" / "source_yicai.csv",
    ROOT / "data" / "source_eastmoney.csv",
    ROOT / "data" / "source_36kr.csv",
    ROOT / "data" / "source_caixin.csv",
    ROOT / "data" / "source_miit.csv",
    ROOT / "data" / "manual_news.csv",
]
RAW_CANDIDATES_PATH = ROOT / "output" / "raw_event_candidates.csv"
STRUCTURED_EVENTS_PATH = ROOT / "output" / "structured_events.csv"
RAW_DOCUMENT_FIELDS = ["source", "source_type", "title", "content", "publish_time", "url", "symbol_or_subject", "content_hash"]
CANDIDATE_STAGE_FIELDS = ["raw_document_url", "dedup_key", "duplicate_group_size", "is_event", "filter_reason", "evidence", "score_hint"]
STRUCTURED_STAGE_FIELDS = [
    "event_id",
    "raw_text_ref",
    "event_name",
    "event_date",
    "source",
    "event_subject_type",
    "duration_type",
    "predictability_type",
    "industry_type",
    "sentiment",
    "heat_score",
    "intensity_score",
    "impact_scope",
    "event_summary",
    "subject_entities",
    "classification_evidence",
]


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
            content_hash = hashlib.md5(
                f'{row["title"]}::{row["content"]}'.encode("utf-8")
            ).hexdigest()
            rows.append(
                {
                    "source": row["source"],
                    "source_type": "text_source",
                    "title": row["title"],
                    "content": row["content"],
                    "publish_time": normalize_datetime(row["publish_time"]),
                    "url": row["url"],
                    "symbol_or_subject": row.get("symbol_or_subject", ""),
                    "content_hash": content_hash,
                }
            )
    return rows


def normalize_datetime(value: str) -> str:
    value = value.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    raise ValueError(f"Unsupported datetime format: {value}")


def run_psql(db: str, sql: str) -> None:
    subprocess.run(
        ["psql", "-d", db, "-v", "ON_ERROR_STOP=1", "-c", sql],
        check=True,
        cwd=str(ROOT),
    )


def copy_csv_to_table(db: str, rows: list[dict[str, str]], fieldnames: list[str], table_name: str) -> None:
    with NamedTemporaryFile("w", encoding="utf-8", newline="", suffix=".csv", delete=False) as tmp:
        writer = csv.DictWriter(tmp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        temp_path = tmp.name
    try:
        run_psql(db, f"TRUNCATE TABLE {table_name} RESTART IDENTITY CASCADE;")
        sql = (
            f"\\copy {table_name} ({', '.join(fieldnames)}) "
            f"FROM '{temp_path}' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')"
        )
        subprocess.run(
            ["psql", "-d", db, "-v", "ON_ERROR_STOP=1", "-c", sql],
            check=True,
            cwd=str(ROOT),
        )
    finally:
        Path(temp_path).unlink(missing_ok=True)


def build_candidate_stage_rows(raw_candidates: list[dict[str, str]], raw_documents: list[dict[str, str]]) -> list[dict[str, str]]:
    stage_rows = []
    for row in raw_candidates:
        stage_rows.append(
            {
                "raw_document_url": row["url"],
                "dedup_key": row["dedup_key"],
                "duplicate_group_size": row["duplicate_group_size"],
                "is_event": row["is_event"],
                "filter_reason": row["filter_reason"],
                "evidence": row["evidence"],
                "score_hint": row["score_hint"] or "",
            }
        )
    return stage_rows


def build_structured_stage_rows(structured_events: list[dict[str, str]]) -> list[dict[str, str]]:
    stage_rows = []
    for row in structured_events:
        stage_rows.append(
            {
                "event_id": row["event_id"],
                "raw_text_ref": row["raw_text_ref"],
                "event_name": row["event_name"],
                "event_date": row["event_date"],
                "source": row["source"],
                "event_subject_type": row["event_subject_type"],
                "duration_type": row["duration_type"],
                "predictability_type": row["predictability_type"],
                "industry_type": row["industry_type"],
                "sentiment": row["sentiment"],
                "heat_score": row["heat_score"],
                "intensity_score": row["intensity_score"],
                "impact_scope": row["impact_scope"],
                "event_summary": row["event_summary"],
                "subject_entities": row["subject_entities"] or "[]",
                "classification_evidence": row.get("classification_evidence", ""),
            }
        )
    return stage_rows


def load_stage_tables(db: str, raw_documents: list[dict[str, str]], raw_candidates: list[dict[str, str]], structured_events: list[dict[str, str]]) -> None:
    copy_csv_to_table(db, raw_documents, RAW_DOCUMENT_FIELDS, "raw_documents")
    copy_csv_to_table(
        db,
        build_candidate_stage_rows(raw_candidates, raw_documents),
        CANDIDATE_STAGE_FIELDS,
        "event_candidates_stage",
    )
    copy_csv_to_table(
        db,
        build_structured_stage_rows(structured_events),
        STRUCTURED_STAGE_FIELDS,
        "structured_events_stage",
    )


def insert_final_tables(db: str) -> None:
    run_psql(
        db,
        """
        INSERT INTO event_candidates (raw_document_id, dedup_key, duplicate_group_size, is_event, filter_reason, evidence, score_hint)
        SELECT d.id,
               s.dedup_key,
               s.duplicate_group_size::integer,
               s.is_event::boolean,
               s.filter_reason,
               s.evidence,
               NULLIF(s.score_hint, '')::integer
        FROM event_candidates_stage s
        JOIN raw_documents d ON d.url = s.raw_document_url
        ORDER BY d.id;
        """,
    )
    run_psql(
        db,
        """
        INSERT INTO structured_events (
            event_id, candidate_id, event_name, event_date, source,
            event_subject_type, duration_type, predictability_type,
            industry_type, sentiment, heat_score, intensity_score,
            impact_scope, event_summary, subject_entities, raw_text_ref,
            classification_evidence
        )
        SELECT s.event_id,
               c.id,
               s.event_name,
               s.event_date::date,
               s.source,
               s.event_subject_type,
               s.duration_type,
               s.predictability_type,
               s.industry_type,
               s.sentiment,
               s.heat_score::integer,
               s.intensity_score::integer,
               s.impact_scope,
               s.event_summary,
               s.subject_entities::jsonb,
               s.raw_text_ref,
               s.classification_evidence
        FROM structured_events_stage s
        JOIN raw_documents d ON d.url = s.raw_text_ref
        JOIN event_candidates c ON c.raw_document_id = d.id
        ORDER BY c.id;
        """,
    )


def main() -> None:
    args = parse_args()
    db = args.db

    with write_guard(
        db_name=db,
        required_tables=[
            "raw_documents",
            "event_candidates",
            "structured_events",
            "event_candidates_stage",
            "structured_events_stage",
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
