#!/usr/bin/env python3
"""Collector-facing database access helpers.

This module centralizes raw_documents writes and candidate selection used by
collector services. It lets services depend on a stable adapter boundary
instead of importing legacy storage functions or inlining SQL directly.
"""

from __future__ import annotations

from typing import Any

import psycopg

from modules.collectors.services.raw_document_loading_service import upsert_raw_documents
from modules.runtime.adapters.db import dsn_for


def upsert_raw_document_rows(db_name: str, rows: list[dict[str, str]]) -> int:
    if not rows:
        return 0
    upsert_raw_documents(db_name, rows)
    return len(rows)


def load_cninfo_fulltext_backfill_candidates(
    db_name: str,
    source: str,
    start_date: str,
    end_date: str,
    max_rows: int,
    offset: int,
    id_min: int,
    id_max: int,
    shard_count: int,
    shard_index: int,
) -> list[dict[str, Any]]:
    sql = """
        WITH candidates AS (
            SELECT
                id,
                title,
                url,
                publish_time,
                row_number() OVER (ORDER BY id) AS rn
            FROM raw_documents
            WHERE source = %s
              AND publish_time >= %s::timestamp
              AND publish_time < %s::timestamp
              AND (%s <= 0 OR id >= %s)
              AND (%s <= 0 OR id < %s)
              AND url LIKE 'http%%/new/disclosure/detail?%%'
              AND (
                length(coalesce(content, '')) < 300
                OR btrim(coalesce(content, '')) = btrim(title)
                OR btrim(coalesce(content, '')) = btrim(regexp_replace(title, '^[^：:]+[：:]', ''))
              )
        )
        SELECT id, title, url, publish_time
        FROM candidates
        WHERE (%s <= 1 OR mod(rn - 1, %s) = %s)
        ORDER BY id
        OFFSET %s
        LIMIT %s
    """
    shard_count = int(shard_count)
    shard_index = int(shard_index)
    shard_divisor = max(shard_count, 1)
    with psycopg.connect(dsn_for(db_name)) as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    source,
                    start_date,
                    end_date,
                    int(id_min),
                    int(id_min),
                    int(id_max),
                    int(id_max),
                    shard_count,
                    shard_divisor,
                    max(shard_index, 0),
                    max(offset, 0),
                    max_rows,
                ),
            )
            rows = cur.fetchall()
    return [
        {"id": row_id, "title": title or "", "url": url or "", "publish_time": publish_time}
        for row_id, title, url, publish_time in rows
    ]


def update_raw_document_contents(db_name: str, updates: list[dict[str, str]]) -> int:
    if not updates:
        return 0
    sql = """
        UPDATE raw_documents
        SET content = %(content)s,
            content_hash = %(content_hash)s
        WHERE id = %(id)s
    """
    with psycopg.connect(dsn_for(db_name)) as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, updates)
        conn.commit()
    return len(updates)
