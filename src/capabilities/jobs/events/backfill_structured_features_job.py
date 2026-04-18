#!/usr/bin/env python3
"""Backfill newly added structured-event feature columns for existing rows."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any, Dict, List

import psycopg

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.services.events.structured_event_features import enrich_row
from capabilities.storage.db_guard import dsn_for, write_guard


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill structured_events feature columns.")
    parser.add_argument("--db", default="stock_event_mining")
    parser.add_argument("--batch-size", type=int, default=5000)
    parser.add_argument("--max-batches", type=int, default=0, help="0 means all.")
    parser.add_argument("--lock-timeout-sec", type=int, default=120)
    return parser.parse_args()


def load_batch(cur: psycopg.Cursor, batch_size: int, offset: int) -> List[Dict[str, Any]]:
    cur.execute(
        """
        SELECT
            se.id, se.event_name, se.event_summary, se.classification_evidence, se.subject_entities,
            se.sentiment, se.source_type, se.authority_level, se.predictability_type, se.shock_source_type,
            rd.title AS raw_title, rd.content AS raw_content
        FROM structured_events se
        JOIN int_event_candidates c ON c.id = se.candidate_id
        JOIN raw_documents rd ON rd.id = c.raw_document_id
        ORDER BY se.id
        OFFSET %s LIMIT %s
        """,
        (offset, batch_size),
    )
    return [dict(row) for row in cur.fetchall()]


def main() -> None:
    args = parse_args()
    with write_guard(
        db_name=args.db,
        required_tables=["structured_events", "int_event_candidates", "raw_documents"],
        lock_timeout_sec=args.lock_timeout_sec,
    ):
        with psycopg.connect(dsn_for(args.db)) as conn:
            total_updated = 0
            batch_idx = 0
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                while True:
                    if args.max_batches > 0 and batch_idx >= args.max_batches:
                        break
                    offset = batch_idx * args.batch_size
                    rows = load_batch(cur, args.batch_size, offset)
                    if not rows:
                        break

                    updates = []
                    for row in rows:
                        enriched = enrich_row(
                            {
                                "event_name": row["event_name"] or "",
                                "event_summary": " ".join([
                                    row.get("event_summary") or "",
                                    row.get("raw_title") or "",
                                    row.get("raw_content") or "",
                                ]),
                                "classification_evidence": row.get("classification_evidence") or "",
                                "subject_entities": row.get("subject_entities") or "[]",
                                "sentiment": row.get("sentiment") or "中性",
                                "source_type": row.get("source_type") or "其他来源",
                                "authority_level": row.get("authority_level") or "general_media",
                                "predictability_type": row.get("predictability_type") or "预披露型",
                                "shock_source_type": row.get("shock_source_type") or "其他",
                                "impact_scope": "行业面",
                            }
                        )
                        updates.append(
                            {
                                "id": row["id"],
                                "sw_l1_industry": enriched.get("sw_l1_industry", "其他"),
                                "sw_l1_industry_code": enriched.get("sw_l1_industry_code", ""),
                                "sentiment_score_0_100": int(enriched.get("sentiment_score_0_100", "50")),
                                "source_credibility_type": enriched.get("source_credibility_type", "单一媒体"),
                                "amount_max_rmb": enriched.get("amount_max_rmb") or None,
                                "amount_log_rmb": enriched.get("amount_log_rmb") or None,
                                "company_count": int(enriched.get("company_count", "0")),
                                "industry_count": int(enriched.get("industry_count", "0")),
                                "province_count": int(enriched.get("province_count", "0")),
                                "city_count": int(enriched.get("city_count", "0")),
                                "country_count": int(enriched.get("country_count", "0")),
                                "chain_stage_count": int(enriched.get("chain_stage_count", "0")),
                                "chain_stages": enriched.get("chain_stages", "[]"),
                                "classification_confidence": float(enriched.get("classification_confidence", "0.5")),
                                "predictability_type": enriched.get("predictability_type", "预披露型"),
                                "shock_source_type": enriched.get("shock_source_type", "其他"),
                                "impact_scope": enriched.get("impact_scope", "行业面"),
                            }
                        )

                    cur.executemany(
                        """
                        UPDATE structured_events
                        SET sw_l1_industry = %(sw_l1_industry)s,
                            sw_l1_industry_code = %(sw_l1_industry_code)s,
                            sentiment_score_0_100 = %(sentiment_score_0_100)s,
                            source_credibility_type = %(source_credibility_type)s,
                            amount_max_rmb = %(amount_max_rmb)s::numeric,
                            amount_log_rmb = %(amount_log_rmb)s::numeric,
                            company_count = %(company_count)s,
                            industry_count = %(industry_count)s,
                            province_count = %(province_count)s,
                            city_count = %(city_count)s,
                            country_count = %(country_count)s,
                            chain_stage_count = %(chain_stage_count)s,
                            chain_stages = %(chain_stages)s::jsonb,
                            classification_confidence = %(classification_confidence)s::numeric,
                            predictability_type = %(predictability_type)s,
                            shock_source_type = %(shock_source_type)s,
                            impact_scope = %(impact_scope)s
                        WHERE id = %(id)s
                        """,
                        updates,
                    )
                    conn.commit()
                    batch_idx += 1
                    total_updated += len(updates)
                    print(
                        f"[backfill-structured-features] batch={batch_idx} rows={len(updates)} total_updated={total_updated}",
                        flush=True,
                    )
            print(f"[backfill-structured-features] finished total_updated={total_updated}")


if __name__ == "__main__":
    main()

