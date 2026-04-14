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

import psycopg

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.storage.db_guard import dsn_for, write_guard


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
TASK1_DB_SQL_PATH = ROOT / "sql" / "create_task1_db.sql"
TASK1_STAGE_SQL_PATH = ROOT / "sql" / "create_task1_stage_tables.sql"
RAW_DOCUMENT_FIELDS = ["source", "source_type", "title", "content", "publish_time", "url", "symbol_or_subject", "content_hash"]
CANDIDATE_STAGE_FIELDS = ["raw_document_url", "dedup_key", "duplicate_group_size", "is_event", "filter_reason", "evidence", "score_hint"]
STRUCTURED_STAGE_FIELDS = [
    "event_id",
    "raw_text_ref",
    "event_name",
    "event_date",
    "source",
    "source_type",
    "authority_level",
    "source_credibility_score",
    "event_subject_type",
    "event_subject_subtype",
    "duration_type",
    "predictability_type",
    "industry_type",
    "sentiment",
    "time_orientation",
    "event_stage",
    "shock_source_type",
    "region_scope",
    "trigger_word_score",
    "explicitness_score",
    "uncertainty_score",
    "novelty_score",
    "amount_scale",
    "event_code",
    "heat_score",
    "intensity_score",
    "impact_scope",
    "event_summary",
    "subject_entities",
    "classification_evidence",
]


def sanitize_text(value: str) -> str:
    """Remove characters that PostgreSQL text fields cannot store safely."""
    if not value:
        return ""
    # PostgreSQL rejects NUL bytes in text/varchar columns.
    value = value.replace("\x00", "")
    # Keep common whitespace while dropping other control characters.
    return "".join(ch for ch in value if (ord(ch) >= 32 or ch in "\t\n\r"))


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


def normalize_datetime(value: str) -> str:
    value = sanitize_text(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    raise ValueError(f"Unsupported datetime format: {value}")


def safe_normalize_datetime(value: str) -> str:
    try:
        return normalize_datetime(value)
    except Exception:
        return "1970-01-01 00:00:00"


def run_psql(db: str, sql: str) -> None:
    subprocess.run(
        ["psql", "-d", db, "-v", "ON_ERROR_STOP=1", "-c", sql],
        check=True,
        cwd=str(ROOT),
    )


def ensure_task1_schema(db: str) -> None:
    sql = TASK1_DB_SQL_PATH.read_text(encoding="utf-8") + "\n" + TASK1_STAGE_SQL_PATH.read_text(encoding="utf-8")
    run_psql(db, sql)


def copy_csv_to_table(db: str, rows: list[dict[str, str]], fieldnames: list[str], table_name: str, truncate: bool = True) -> None:
    with NamedTemporaryFile("w", encoding="utf-8", newline="", suffix=".csv", delete=False) as tmp:
        writer = csv.DictWriter(tmp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        temp_path = tmp.name
    try:
        if truncate:
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


def upsert_raw_documents(db: str, rows: list[dict[str, str]]) -> None:
    """Upsert collected rows into raw_documents table.
    
    Rows should have keys: source, title, content, publish_time, url, symbol_or_subject.
    """
    if not rows:
        return
    
    data_to_insert = []
    for row in rows:
        title = sanitize_text((row.get("title") or "")).strip()
        content = sanitize_text((row.get("content") or "")).strip()
        if not content:
            content = title or "(empty)"
            
        content_hash = hashlib.md5(f"{title}::{content}".encode("utf-8")).hexdigest()
        
        data_to_insert.append({
            "source": sanitize_text(row.get("source", "unknown")),
            "source_type": "text_source",
            "title": title,
            "content": content,
            "publish_time": safe_normalize_datetime(row.get("publish_time", "")),
            "url": sanitize_text(row.get("url", "")),
            "symbol_or_subject": sanitize_text(row.get("symbol_or_subject", "")),
            "content_hash": content_hash,
        })

    sql = """
        INSERT INTO raw_documents (source, source_type, title, content, publish_time, url, symbol_or_subject, content_hash)
        VALUES (%(source)s, %(source_type)s, %(title)s, %(content)s, %(publish_time)s, %(url)s, %(symbol_or_subject)s, %(content_hash)s)
        ON CONFLICT (url) DO UPDATE
        SET source = EXCLUDED.source,
            source_type = EXCLUDED.source_type,
            title = EXCLUDED.title,
            content = EXCLUDED.content,
            publish_time = EXCLUDED.publish_time,
            symbol_or_subject = EXCLUDED.symbol_or_subject,
            content_hash = EXCLUDED.content_hash;
    """
    with psycopg.connect(dsn_for(db)) as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, data_to_insert)
        conn.commit()


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
                "source_type": row.get("source_type", "其他来源"),
                "authority_level": row.get("authority_level", "general_media"),
                "source_credibility_score": row.get("source_credibility_score", "1"),
                "event_subject_type": row["event_subject_type"],
                "event_subject_subtype": row.get("event_subject_subtype", "未细分"),
                "duration_type": row["duration_type"],
                "predictability_type": row["predictability_type"],
                "industry_type": row["industry_type"],
                "sentiment": row["sentiment"],
                "time_orientation": row.get("time_orientation", "current_confirmed"),
                "event_stage": row.get("event_stage", "确认"),
                "shock_source_type": row.get("shock_source_type", "其他"),
                "region_scope": row.get("region_scope", "domestic"),
                "trigger_word_score": row.get("trigger_word_score", "0"),
                "explicitness_score": row.get("explicitness_score", "0"),
                "uncertainty_score": row.get("uncertainty_score", "0"),
                "novelty_score": row.get("novelty_score", "50"),
                "amount_scale": row.get("amount_scale", "none"),
                "event_code": row.get("event_code", ""),
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
    ensure_task1_schema(db)
    upsert_raw_documents(db, raw_documents)
    copy_csv_to_table(
        db,
        build_candidate_stage_rows(raw_candidates, raw_documents),
        CANDIDATE_STAGE_FIELDS,
        "int_event_candidates_stage",
        truncate=True,
    )
    copy_csv_to_table(
        db,
        build_structured_stage_rows(structured_events),
        STRUCTURED_STAGE_FIELDS,
        "int_structured_events_stage",
        truncate=True,
    )


def insert_final_tables(db: str) -> None:
    run_psql(
        db,
        """
        INSERT INTO int_event_candidates (raw_document_id, dedup_key, duplicate_group_size, is_event, filter_reason, evidence, score_hint)
        SELECT d.id,
               s.dedup_key,
               s.duplicate_group_size::integer,
               s.is_event::boolean,
               s.filter_reason,
               s.evidence,
               NULLIF(s.score_hint, '')::integer
        FROM int_event_candidates_stage s
        JOIN raw_documents d ON d.url = s.raw_document_url
        ORDER BY d.id
        ON CONFLICT (raw_document_id) DO UPDATE
        SET dedup_key = EXCLUDED.dedup_key,
            duplicate_group_size = EXCLUDED.duplicate_group_size,
            is_event = EXCLUDED.is_event,
            filter_reason = EXCLUDED.filter_reason,
            evidence = EXCLUDED.evidence,
            score_hint = EXCLUDED.score_hint;
        """,
    )
    run_psql(
        db,
        """
        INSERT INTO structured_events (
            event_id, candidate_id, event_name, event_date, source,
            source_type, authority_level, source_credibility_score, event_subject_type, event_subject_subtype,
            duration_type, predictability_type, industry_type, sentiment,
            time_orientation, event_stage, shock_source_type, region_scope, trigger_word_score, explicitness_score,
            uncertainty_score, novelty_score, amount_scale, event_code, heat_score, intensity_score,
            impact_scope, event_summary, subject_entities, raw_text_ref,
            classification_evidence
        )
        SELECT s.event_id,
               c.id,
               s.event_name,
               s.event_date::date,
               s.source,
               COALESCE(NULLIF(s.source_type, ''), '其他来源'),
               COALESCE(NULLIF(s.authority_level, ''), 'general_media'),
               COALESCE(NULLIF(s.source_credibility_score, '')::numeric, 1),
               s.event_subject_type,
               COALESCE(NULLIF(s.event_subject_subtype, ''), '未细分'),
               s.duration_type,
               s.predictability_type,
               s.industry_type,
               s.sentiment,
               COALESCE(NULLIF(s.time_orientation, ''), 'current_confirmed'),
               COALESCE(NULLIF(s.event_stage, ''), '确认'),
               COALESCE(NULLIF(s.shock_source_type, ''), '其他'),
               COALESCE(NULLIF(s.region_scope, ''), 'domestic'),
               COALESCE(NULLIF(s.trigger_word_score, '')::integer, 0),
               COALESCE(NULLIF(s.explicitness_score, '')::integer, 0),
               COALESCE(NULLIF(s.uncertainty_score, '')::integer, 0),
               COALESCE(NULLIF(s.novelty_score, '')::integer, 50),
               COALESCE(NULLIF(s.amount_scale, ''), 'none'),
               COALESCE(s.event_code, ''),
               s.heat_score::integer,
               s.intensity_score::integer,
               s.impact_scope,
               s.event_summary,
               s.subject_entities::jsonb,
               s.raw_text_ref,
               s.classification_evidence
        FROM int_structured_events_stage s
        JOIN raw_documents d ON d.url = s.raw_text_ref
        JOIN int_event_candidates c ON c.raw_document_id = d.id
        ORDER BY c.id
        ON CONFLICT (candidate_id) DO UPDATE
        SET event_id = EXCLUDED.event_id,
            event_name = EXCLUDED.event_name,
            event_date = EXCLUDED.event_date,
            source = EXCLUDED.source,
            source_type = EXCLUDED.source_type,
            authority_level = EXCLUDED.authority_level,
            source_credibility_score = EXCLUDED.source_credibility_score,
            event_subject_type = EXCLUDED.event_subject_type,
            event_subject_subtype = EXCLUDED.event_subject_subtype,
            duration_type = EXCLUDED.duration_type,
            predictability_type = EXCLUDED.predictability_type,
            industry_type = EXCLUDED.industry_type,
            sentiment = EXCLUDED.sentiment,
            time_orientation = EXCLUDED.time_orientation,
            event_stage = EXCLUDED.event_stage,
            shock_source_type = EXCLUDED.shock_source_type,
            region_scope = EXCLUDED.region_scope,
            trigger_word_score = EXCLUDED.trigger_word_score,
            explicitness_score = EXCLUDED.explicitness_score,
            uncertainty_score = EXCLUDED.uncertainty_score,
            novelty_score = EXCLUDED.novelty_score,
            amount_scale = EXCLUDED.amount_scale,
            event_code = EXCLUDED.event_code,
            heat_score = EXCLUDED.heat_score,
            intensity_score = EXCLUDED.intensity_score,
            impact_scope = EXCLUDED.impact_scope,
            event_summary = EXCLUDED.event_summary,
            subject_entities = EXCLUDED.subject_entities,
            raw_text_ref = EXCLUDED.raw_text_ref,
            classification_evidence = EXCLUDED.classification_evidence;
        """,
    )
    run_psql(
        db,
        """
        DELETE FROM structured_events se
        USING int_event_candidates ec
        WHERE se.candidate_id = ec.id
          AND ec.id IN (
              SELECT c.id
              FROM int_event_candidates_stage s
              JOIN raw_documents d ON d.url = s.raw_document_url
              JOIN int_event_candidates c ON c.raw_document_id = d.id
          )
          AND ec.is_event = false;
        """,
    )


def main() -> None:
    args = parse_args()
    db = args.db

    with write_guard(
        db_name=db,
        required_tables=[
            "raw_documents",
            "int_event_candidates",
            "structured_events",
            "int_event_candidates_stage",
            "int_structured_events_stage",
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
