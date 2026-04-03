#!/usr/bin/env python3
"""Database write guard: advisory lock + required-table preflight check."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator

import psycopg


WRITE_LOCK_KEY = 9042026


def dsn_for(db_name: str) -> str:
    return f"dbname={db_name} user=tim host=127.0.0.1 port=5432"


def ensure_tables_exist(conn: psycopg.Connection, required_tables: list[str]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT tablename
            FROM pg_catalog.pg_tables
            WHERE schemaname = 'public'
              AND tablename = ANY(%s)
            """,
            (required_tables,),
        )
        existing = {row[0] for row in cur.fetchall()}
    missing = [table for table in required_tables if table not in existing]
    if missing:
        missing_text = ", ".join(missing)
        raise RuntimeError(
            f"Database preflight failed: missing required tables: {missing_text}. "
            "Please initialize schema before running write jobs."
        )


@contextmanager
def write_guard(db_name: str, required_tables: list[str], lock_timeout_sec: int = 120) -> Iterator[psycopg.Connection]:
    conn = psycopg.connect(dsn_for(db_name))
    locked = False
    try:
        ensure_tables_exist(conn, required_tables)
        deadline = time.time() + lock_timeout_sec
        while time.time() < deadline:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_try_advisory_lock(%s)", (WRITE_LOCK_KEY,))
                locked = bool(cur.fetchone()[0])
            if locked:
                break
            time.sleep(1)
        if not locked:
            raise RuntimeError(
                f"Database write lock timeout after {lock_timeout_sec}s. "
                "Another write task is running; wait for it to finish and retry."
            )
        yield conn
    finally:
        if locked:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_unlock(%s)", (WRITE_LOCK_KEY,))
        conn.close()

