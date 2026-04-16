#!/usr/bin/env python3
"""Load company relation edges for Task 3 graph preparation."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Optional

import psycopg

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.storage.db_guard import dsn_for, write_guard


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = "stock_event_mining"
DEFAULT_INPUT = ROOT / "output" / "seeds" / "company_relations_seed.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load task3 company relation edges.")
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--lock-timeout-sec", type=int, default=120)
    return parser.parse_args()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def normalize_direction(value: str) -> str:
    text = (value or "").strip().lower()
    return "directed" if text == "directed" else "undirected"


def normalize_strength(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "0.5000"
    try:
        number = float(text)
    except Exception:
        return "0.5000"
    number = max(0.0, min(1.0, number))
    return f"{number:.4f}"


def normalize_bool(value: Any) -> bool | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    if text in {"1", "true", "t", "yes", "y", "是"}:
        return True
    if text in {"0", "false", "f", "no", "n", "否"}:
        return False
    return None


def pick_text(*values: Any) -> str | None:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return None


def resolve_company(cur, ts_code: str, company_name: str) -> Optional[dict[str, Any]]:
    ts_code_text = (ts_code or "").strip().upper()
    if ts_code_text:
        cur.execute("SELECT id, ts_code, company_name FROM companies WHERE ts_code = %s", (ts_code_text,))
        row = cur.fetchone()
        if row:
            return row
    company_name_text = (company_name or "").strip()
    if company_name_text:
        cur.execute("SELECT id, ts_code, company_name FROM companies WHERE company_name = %s", (company_name_text,))
        row = cur.fetchone()
        if row:
            return row
    return None


def build_evidence(row: dict[str, str], source: dict[str, Any], target: dict[str, Any]) -> str:
    evidence = {
        "evidence_note": row.get("evidence_note", ""),
        "source_ts_code": source["ts_code"],
        "target_ts_code": target["ts_code"],
        "source_company_name": source["company_name"],
        "target_company_name": target["company_name"],
    }
    extra_mappings = {
        "data_source": pick_text(row.get("data_source"), row.get("source")),
        "confidence": pick_text(row.get("confidence")),
        "effective_date": pick_text(row.get("effective_date")),
        "expiry_date": pick_text(row.get("expiry_date")),
        "relation_group": pick_text(row.get("relation_group")),
    }
    for key, value in extra_mappings.items():
        if value:
            evidence[key] = value
    for key in ("same_controller_flag", "same_industry_flag", "same_concept_flag"):
        bool_value = normalize_bool(row.get(key))
        if bool_value is not None:
            evidence[key] = bool_value
    return json.dumps(evidence, ensure_ascii=False)


def main() -> None:
    args = parse_args()
    rows = read_rows(Path(args.input).resolve())
    inserted = 0
    updated = 0
    skipped = 0

    with write_guard(
        db_name=args.db,
        required_tables=["companies", "company_relations"],
        lock_timeout_sec=args.lock_timeout_sec,
    ):
        with psycopg.connect(dsn_for(args.db), row_factory=psycopg.rows.dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM company_relations WHERE is_manual_override = TRUE")
                for row in rows:
                    relation_type = (row.get("relation_type") or "").strip()
                    if not relation_type:
                        skipped += 1
                        continue
                    source = resolve_company(cur, row.get("source_ts_code", ""), row.get("source_company_name", ""))
                    target = resolve_company(cur, row.get("target_ts_code", ""), row.get("target_company_name", ""))
                    if not source or not target:
                        skipped += 1
                        continue
                    source_id = source["id"]
                    target_id = target["id"]
                    direction = normalize_direction(row.get("direction", "undirected"))
                    if direction == "undirected" and source_id > target_id:
                        source_id, target_id = target_id, source_id
                        source, target = target, source
                    cur.execute(
                        """
                        INSERT INTO company_relations (
                            source_company_id, target_company_id, relation_type,
                            relation_strength, direction, evidence, is_manual_override
                        )
                        VALUES (%s, %s, %s, %s, %s, %s::jsonb, TRUE)
                        ON CONFLICT (source_company_id, target_company_id, relation_type) DO UPDATE
                        SET relation_strength = EXCLUDED.relation_strength,
                            direction = EXCLUDED.direction,
                            evidence = EXCLUDED.evidence,
                            is_manual_override = TRUE,
                            updated_at = NOW()
                        """,
                        (
                            source_id,
                            target_id,
                            relation_type,
                            normalize_strength(row.get("relation_strength", "0.5000")),
                            direction,
                            build_evidence(row, source, target),
                        ),
                    )
                    if cur.rowcount == 1:
                        inserted += 1
                    else:
                        updated += 1
            conn.commit()
    print(
        f"Processed {len(rows)} relation rows into {args.db} "
        f"(inserted_or_updated={inserted + updated}, skipped={skipped})"
    )


if __name__ == "__main__":
    main()
