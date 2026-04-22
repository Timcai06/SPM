#!/usr/bin/env python3
"""Shared database guard helpers for module-layer code."""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.conninfo import make_conninfo


WRITE_LOCK_KEY = 9042026


def dsn_for(db_name: str) -> str:
    direct_dsn = os.getenv("STOCK_EVENT_MINING_DSN")
    if direct_dsn:
        return direct_dsn

    return make_conninfo(
        dbname=db_name or os.getenv("PGDATABASE") or "stock_event_mining",
        user=os.getenv("PGUSER") or "tim",
        password=os.getenv("PGPASSWORD") or None,
        host=os.getenv("PGHOST") or "127.0.0.1",
        port=os.getenv("PGPORT") or "5432",
    )


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
def write_guard(
    db_name: str,
    required_tables: list[str],
    lock_timeout_sec: int = 120,
) -> Iterator[psycopg.Connection]:
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
            if conn.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
                conn.rollback()
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_unlock(%s)", (WRITE_LOCK_KEY,))
        conn.close()


__all__ = ["dsn_for", "write_guard", "ensure_tables_exist", "WRITE_LOCK_KEY"]
