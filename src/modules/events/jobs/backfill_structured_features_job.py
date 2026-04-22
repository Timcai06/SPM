#!/usr/bin/env python3
"""Backfill newly added structured-event feature columns for existing rows."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys
from typing import Any, Dict, List

import psycopg

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from modules.events.domain.classification_rules import SUBTYPE_RULES
from modules.events.domain.event_taxonomy import IMPACT_SCOPES, SHOCK_SOURCE_TYPES
from modules.events.domain.industry_mapping import SW_L1_NAMES
from modules.events.services.structured_feature_service import enrich_row
from modules.events.services.llm_enrichment_service import (
    AsyncLLMClient,
    AsyncOllamaClient,
    normalize_llm_choice,
)
from modules.runtime.adapters.db import dsn_for, write_guard


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill structured_events feature columns.")
    parser.add_argument("--db", default="stock_event_mining")
    parser.add_argument("--batch-size", type=int, default=5000)
    parser.add_argument("--max-batches", type=int, default=0, help="0 means all.")
    parser.add_argument("--start-date", default="")
    parser.add_argument("--end-date", default="")
    parser.add_argument("--only-needy", action="store_true")
    parser.add_argument("--use-llm", action="store_true")
    parser.add_argument("--local-llm-only", action="store_true")
    parser.add_argument("--llm-max-rows", type=int, default=200)
    parser.add_argument("--llm-confidence-threshold", type=float, default=0.70)
    parser.add_argument("--llm-progress-every", type=int, default=10)
    parser.add_argument("--lock-timeout-sec", type=int, default=120)
    return parser.parse_args()


def load_batch(
    cur: psycopg.Cursor,
    batch_size: int,
    offset: int,
    start_date: str,
    end_date: str,
    only_needy: bool,
    confidence_threshold: float,
) -> List[Dict[str, Any]]:
    filters = []
    params: list[Any] = []
    if start_date:
        filters.append("se.event_date >= %s::date")
        params.append(start_date)
    if end_date:
        filters.append("se.event_date < %s::date")
        params.append(end_date)
    if only_needy:
        filters.append(
            "("
            "se.sw_l1_industry = '其他' "
            "OR COALESCE(se.industry_count, 0) = 0 "
            "OR se.shock_source_type = '其他' "
            "OR se.event_subject_subtype IN ('未细分','公司事项','行业跟踪','政策动态','宏观跟踪','地缘事件') "
            "OR COALESCE(se.classification_confidence, 0) < %s"
            ")"
        )
        params.append(confidence_threshold)
    where_sql = f"WHERE {' AND '.join(filters)}" if filters else ""
    cur.execute(
        f"""
        SELECT
            se.id, se.event_name, se.event_summary, se.classification_evidence, se.subject_entities,
            se.sentiment, se.source_type, se.authority_level, se.predictability_type, se.shock_source_type,
            se.event_subject_subtype, se.sw_l1_industry, se.impact_scope,
            rd.title AS raw_title, rd.content AS raw_content
        FROM structured_events se
        JOIN event_candidates c ON c.id = se.candidate_id
        JOIN raw_documents rd ON rd.id = c.raw_document_id
        {where_sql}
        ORDER BY se.id
        OFFSET %s LIMIT %s
        """,
        tuple(params + [offset, batch_size]),
    )
    return [dict(row) for row in cur.fetchall()]


def build_update(row: Dict[str, Any]) -> Dict[str, Any]:
    enriched = enrich_row(
        {
            "event_name": row["event_name"] or "",
            "event_summary": " ".join(
                [row.get("event_summary") or "", row.get("raw_title") or "", row.get("raw_content") or ""]
            ),
            "classification_evidence": row.get("classification_evidence") or "",
            "subject_entities": row.get("subject_entities") or "[]",
            "sentiment": row.get("sentiment") or "中性",
            "source_type": row.get("source_type") or "其他来源",
            "authority_level": row.get("authority_level") or "general_media",
            "predictability_type": row.get("predictability_type") or "预披露型",
            "shock_source_type": row.get("shock_source_type") or "其他",
            "impact_scope": row.get("impact_scope") or "行业面",
        }
    )
    return {
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
        "event_subject_subtype": row.get("event_subject_subtype") or "未细分",
        "llm_confidence": 0.0,
    }


def should_use_llm(update: Dict[str, Any], threshold: float) -> bool:
    return (
        update["sw_l1_industry"] == "其他"
        or update["industry_count"] == 0
        or update["shock_source_type"] == "其他"
        or update["event_subject_subtype"] in {"未细分", "公司事项", "行业跟踪", "政策动态", "宏观跟踪", "地缘事件"}
        or float(update["classification_confidence"]) < threshold
    )


async def apply_llm_to_updates(
    rows: List[Dict[str, Any]],
    updates: List[Dict[str, Any]],
    llm_max_rows: int,
    progress_every: int,
    local_llm_only: bool,
) -> Dict[str, int]:
    client = AsyncLLMClient()
    ollama = AsyncOllamaClient()
    budget = 0
    success = 0
    improved = 0
    total = min(len(rows), llm_max_rows)
    for row, update in zip(rows, updates):
        if budget >= llm_max_rows:
            break
        current = {
            "sw_l1_industry": update["sw_l1_industry"],
            "event_subject_subtype": update["event_subject_subtype"],
            "shock_source_type": update["shock_source_type"],
            "impact_scope": update["impact_scope"],
        }
        llm_data = {}
        if client.api_key and not local_llm_only:
            llm_data = await client.extract_feature_data(
                row.get("raw_title") or row.get("event_name") or "",
                row.get("raw_content") or row.get("event_summary") or "",
                current,
            )
        if not llm_data:
            llm_data = await ollama.extract_feature_data(
                row.get("raw_title") or row.get("event_name") or "",
                row.get("raw_content") or row.get("event_summary") or "",
                current,
            )
        if not llm_data:
            continue
        success += 1
        before = (
            update["sw_l1_industry"],
            update["event_subject_subtype"],
            update["shock_source_type"],
            update["impact_scope"],
            update["classification_confidence"],
        )
        update["sw_l1_industry"] = normalize_llm_choice(
            llm_data.get("sw_l1_industry", ""),
            update["sw_l1_industry"],
            ("其他",) + SW_L1_NAMES,
        )
        update["event_subject_subtype"] = normalize_llm_choice(
            llm_data.get("event_subject_subtype", ""),
            update["event_subject_subtype"],
            SUBTYPE_RULES.keys(),
        )
        update["shock_source_type"] = normalize_llm_choice(
            llm_data.get("shock_source_type", ""),
            update["shock_source_type"],
            SHOCK_SOURCE_TYPES,
        )
        update["impact_scope"] = normalize_llm_choice(
            llm_data.get("impact_scope", ""),
            update["impact_scope"],
            IMPACT_SCOPES,
        )
        llm_conf = float(llm_data.get("confidence") or 0.0)
        if llm_conf > update["classification_confidence"]:
            update["classification_confidence"] = round(min(0.99, llm_conf), 4)
        update["llm_confidence"] = llm_conf
        after = (
            update["sw_l1_industry"],
            update["event_subject_subtype"],
            update["shock_source_type"],
            update["impact_scope"],
            update["classification_confidence"],
        )
        if after != before:
            improved += 1
        budget += 1
        if progress_every > 0 and (
            budget == 1 or budget % progress_every == 0 or budget == total
        ):
            print(
                f"[backfill-structured-features][llm] progress {budget}/{total} "
                f"success={success} improved={improved}",
                flush=True,
            )
    return {"attempted": budget, "success": success, "improved": improved}


def update_rows(cur: psycopg.Cursor, updates: List[Dict[str, Any]]) -> None:
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
            event_subject_subtype = %(event_subject_subtype)s,
            shock_source_type = %(shock_source_type)s,
            impact_scope = %(impact_scope)s
        WHERE id = %(id)s
        """,
        updates,
    )


def main() -> None:
    args = parse_args()
    with write_guard(
        db_name=args.db,
        required_tables=["structured_events", "event_candidates", "raw_documents"],
        lock_timeout_sec=args.lock_timeout_sec,
    ):
        with psycopg.connect(dsn_for(args.db)) as conn:
            total_updated = 0
            batch_idx = 0
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                while True:
                    if args.max_batches > 0 and batch_idx >= args.max_batches:
                        break
                    rows = load_batch(
                        cur,
                        args.batch_size,
                        batch_idx * args.batch_size,
                        args.start_date,
                        args.end_date,
                        args.only_needy,
                        args.llm_confidence_threshold,
                    )
                    if not rows:
                        break
                    updates = [build_update(row) for row in rows]
                    llm_candidate_count = 0
                    llm_stats = {"attempted": 0, "success": 0, "improved": 0}
                    if args.use_llm and args.llm_max_rows > 0:
                        llm_rows = [
                            (row, update)
                            for row, update in zip(rows, updates)
                            if should_use_llm(update, args.llm_confidence_threshold)
                        ]
                        llm_candidate_count = len(llm_rows)
                        if llm_rows:
                            print(
                                f"[backfill-structured-features] batch={batch_idx + 1} "
                                f"llm_start candidates={llm_candidate_count} "
                                f"max_rows={args.llm_max_rows} "
                                f"threshold={args.llm_confidence_threshold}",
                                flush=True,
                            )
                            llm_stats = asyncio.run(
                                apply_llm_to_updates(
                                    [row for row, _ in llm_rows],
                                    [update for _, update in llm_rows],
                                    args.llm_max_rows,
                                    args.llm_progress_every,
                                    args.local_llm_only,
                                )
                            )
                    update_rows(cur, updates)
                    conn.commit()
                    batch_idx += 1
                    total_updated += len(updates)
                    print(
                        f"[backfill-structured-features] batch={batch_idx} rows={len(updates)} "
                        f"llm_candidates={llm_candidate_count} llm_attempted={llm_stats['attempted']} "
                        f"llm_success={llm_stats['success']} llm_improved={llm_stats['improved']} "
                        f"total_updated={total_updated}",
                        flush=True,
                    )
            print(f"[backfill-structured-features] finished total_updated={total_updated}")


if __name__ == "__main__":
    main()
