#!/usr/bin/env python3
"""Database access used by event classification jobs."""

from __future__ import annotations

from typing import Dict, List

import psycopg

from modules.events.services.event_persistence_service import insert_final_rows, load_stage_rows
from modules.runtime.adapters.db import dsn_for


def load_rows_from_db(db: str) -> List[Dict[str, str]]:
    sql = """
        SELECT source, title, content, publish_time::text, url, symbol_or_subject
        FROM raw_documents
        ORDER BY publish_time DESC
    """
    with psycopg.connect(dsn_for(db)) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]


def load_pending_raw_documents(db_name: str, batch_size: int) -> List[Dict[str, str]]:
    with psycopg.connect(dsn_for(db_name), row_factory=psycopg.rows.dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT d.source,
                       d.title,
                       d.content,
                       d.publish_time::text AS publish_time,
                       d.url,
                       COALESCE(d.symbol_or_subject, '') AS symbol_or_subject
                FROM raw_documents d
                LEFT JOIN event_candidates c ON c.raw_document_id = d.id
                WHERE c.id IS NULL
                ORDER BY d.publish_time, d.id
                LIMIT %s
                """,
                (batch_size,),
            )
            return [dict(row) for row in cur.fetchall()]


def load_source_raw_documents(
    db_name: str, source: str, batch_size: int, offset: int
) -> List[Dict[str, str]]:
    with psycopg.connect(dsn_for(db_name), row_factory=psycopg.rows.dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT source,
                       title,
                       content,
                       publish_time::text AS publish_time,
                       url,
                       COALESCE(symbol_or_subject, '') AS symbol_or_subject
                FROM raw_documents
                WHERE source = %s
                ORDER BY publish_time, id
                OFFSET %s
                LIMIT %s
                """,
                (source, offset, batch_size),
            )
            return [dict(row) for row in cur.fetchall()]


def load_event_stage_rows(
    db_name: str,
    raw_documents: list[dict[str, str]],
    raw_candidates: list[dict[str, str]],
    structured_events: list[dict[str, str]],
) -> None:
    load_stage_rows(db_name, raw_documents, raw_candidates, structured_events)


def insert_event_final_rows(db_name: str) -> None:
    insert_final_rows(db_name)
