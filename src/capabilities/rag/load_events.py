"""Load events from database for RAG."""

import psycopg
from typing import Iterator
from dataclasses import dataclass

from .config import DB_NAME


@dataclass
class EventChunk:
    content: str
    metadata: dict


def load_structured_events() -> Iterator[EventChunk]:
    """Load structured_events as text chunks."""
    conn = psycopg.connect(f"dbname={DB_NAME} user=tim host=127.0.0.1 port=5432")
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    e.id,
                    e.title,
                    e.content,
                    e.event_date,
                    e.category,
                    e.source,
                    COALESCE(string_agg(DISTINCT c.name, ', '), '') as companies
                FROM structured_events e
                LEFT JOIN event_company_links ecl ON ecl.event_id = e.id
                LEFT JOIN companies c ON c.id = ecl.company_id
                GROUP BY e.id, e.title, e.content, e.event_date, e.category, e.source
                ORDER BY e.event_date DESC
            """)
            for row in cur:
                chunk = f"""事件ID: {row[0]}
标题: {row[1]}
内容: {row[2]}
时间: {row[3]}
分类: {row[4]}
来源: {row[5]}
关联公司: {row[6]}"""
                yield EventChunk(content=chunk, metadata={"type": "structured_event", "id": row[0]})
    finally:
        conn.close()


def load_canonical_events() -> Iterator[EventChunk]:
    """Load canonical_events as text chunks."""
    conn = psycopg.connect(f"dbname={DB_NAME} user=tim host=127.0.0.1 port=5432")
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    ce.id,
                    ce.canonical_title,
                    ce.category,
                    ce.first_date,
                    ce.last_date,
                    ce.event_count,
                    COALESCE(string_agg(DISTINCT c.name, ', '), '') as companies
                FROM canonical_events ce
                LEFT JOIN event_canonical_links ecl ON ecl.canonical_event_id = ce.id
                LEFT JOIN structured_events se ON se.id = ecl.event_id
                LEFT JOIN event_company_links ecl2 ON ecl2.event_id = se.id
                LEFT JOIN companies c ON c.id = ecl2.company_id
                GROUP BY ce.id, ce.canonical_title, ce.category, ce.first_date, ce.last_date, ce.event_count
                ORDER BY ce.first_date DESC
            """)
            for row in cur:
                chunk = f"""归并事件ID: {row[0]}
归并标题: {row[1]}
分类: {row[2]}
首次出现: {row[3]}
最新出现: {row[4]}
包含事件数: {row[5]}
关联公司: {row[6]}"""
                yield EventChunk(content=chunk, metadata={"type": "canonical_event", "id": row[0]})
    finally:
        conn.close()


def load_all_events() -> Iterator[EventChunk]:
    """Load all events from database."""
    yield from load_structured_events()
    yield from load_canonical_events()