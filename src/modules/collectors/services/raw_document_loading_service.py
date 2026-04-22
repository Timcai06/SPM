#!/usr/bin/env python3
"""Raw-document write helpers owned by the module layer."""

from __future__ import annotations

import hashlib
from datetime import datetime

import psycopg

from modules.runtime.adapters.db import dsn_for


def sanitize_text(value: str) -> str:
    if not value:
        return ""
    value = value.replace("\x00", "")
    return "".join(ch for ch in value if (ord(ch) >= 32 or ch in "\t\n\r"))


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


def upsert_raw_documents(db_name: str, rows: list[dict[str, str]]) -> None:
    if not rows:
        return

    data_to_insert: list[dict[str, str]] = []
    for row in rows:
        title = sanitize_text((row.get("title") or "")).strip()
        content = sanitize_text((row.get("content") or "")).strip()
        if not content:
            content = title or "(empty)"
        content_hash = hashlib.md5(f"{title}::{content}".encode("utf-8")).hexdigest()
        data_to_insert.append(
            {
                "source": sanitize_text(row.get("source", "unknown")),
                "source_type": "text_source",
                "title": title,
                "content": content,
                "publish_time": safe_normalize_datetime(row.get("publish_time", "")),
                "url": sanitize_text(row.get("url", "")),
                "symbol_or_subject": sanitize_text(row.get("symbol_or_subject", "")),
                "content_hash": content_hash,
            }
        )

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
    with psycopg.connect(dsn_for(db_name)) as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, data_to_insert)
        conn.commit()
