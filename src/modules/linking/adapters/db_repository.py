#!/usr/bin/env python3
"""Database helpers for linking jobs."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Iterable

import psycopg

from capabilities.storage.db_guard import dsn_for


def load_structured_events(cur) -> list[dict]:
    cur.execute(
        """
        SELECT se.id,
               se.event_id,
               se.event_name,
               se.event_subject_type,
               se.industry_type,
               se.event_summary,
               rd.title AS raw_title,
               rd.content AS raw_content,
               rd.symbol_or_subject AS raw_symbol
        FROM structured_events se
        JOIN int_event_candidates ec ON ec.id = se.candidate_id
        JOIN raw_documents rd ON rd.id = ec.raw_document_id
        ORDER BY se.id
        """
    )
    return cur.fetchall()


def load_companies(cur) -> list[dict]:
    cur.execute(
        """
        SELECT id, ts_code, company_name, industry_l1, industry_l2, business_scope, core_products, concept_tags
        FROM companies
        WHERE is_active = TRUE
        ORDER BY id
        """
    )
    return cur.fetchall()


def upsert_link(
    cur,
    structured_event_id: int,
    company: dict,
    link_type: str,
    event: dict,
    details: dict,
    final_score: float,
) -> None:
    evidence = {
        **details["evidence"],
        "canonical_event_id": event["canonical_event_id"],
        "canonical_cluster_size": event["cluster_size"],
        "canonical_link_mode": "cluster_aggregated",
    }
    cur.execute(
        """
        INSERT INTO event_company_links (
            structured_event_id, company_id, link_type, relation_path,
            text_similarity_score, industry_match_score, chain_position_score,
            event_match_score, final_link_score, evidence
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (structured_event_id, company_id, link_type) DO UPDATE
        SET relation_path = EXCLUDED.relation_path,
            text_similarity_score = EXCLUDED.text_similarity_score,
            industry_match_score = EXCLUDED.industry_match_score,
            chain_position_score = EXCLUDED.chain_position_score,
            event_match_score = EXCLUDED.event_match_score,
            final_link_score = EXCLUDED.final_link_score,
            evidence = EXCLUDED.evidence,
            updated_at = NOW()
        """,
        (
            structured_event_id,
            company["id"],
            link_type,
            f"{event['event_name']} -> {company['industry_l2']} -> {company['company_name']}",
            Decimal(str(details["text_similarity_score"])),
            Decimal(str(details["industry_match_score"])),
            Decimal(str(details["chain_position_score"])),
            Decimal(str(details["event_match_score"])),
            Decimal(str(final_score)),
            json.dumps(evidence, ensure_ascii=False),
        ),
    )


def delete_stale_links(cur, touched_structured_event_ids: set[int], current_keys: list[tuple[int, int, str]]) -> int:
    if not touched_structured_event_ids:
        return 0
    cur.execute(
        """
        CREATE TEMP TABLE current_event_company_link_keys (
            structured_event_id BIGINT NOT NULL,
            company_id BIGINT NOT NULL,
            link_type TEXT NOT NULL,
            PRIMARY KEY (structured_event_id, company_id, link_type)
        ) ON COMMIT DROP
        """
    )
    if current_keys:
        cur.executemany(
            """
            INSERT INTO current_event_company_link_keys (structured_event_id, company_id, link_type)
            VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            current_keys,
        )
    cur.execute(
        """
        DELETE FROM event_company_links l
        WHERE l.structured_event_id = ANY(%s)
          AND NOT EXISTS (
              SELECT 1
              FROM current_event_company_link_keys k
              WHERE k.structured_event_id = l.structured_event_id
                AND k.company_id = l.company_id
                AND k.link_type = l.link_type
          )
        """,
        (list(touched_structured_event_ids),),
    )
    return cur.rowcount

