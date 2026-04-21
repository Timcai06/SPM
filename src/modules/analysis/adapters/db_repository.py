#!/usr/bin/env python3
"""Database access helpers for analysis jobs."""

from __future__ import annotations

from typing import Dict, List

import psycopg

from capabilities.storage.db_guard import dsn_for


def run_query_rows(db: str, sql: str) -> List[Dict[str, str]]:
    with psycopg.connect(dsn_for(db), row_factory=psycopg.rows.dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
    normalized: List[Dict[str, str]] = []
    for row in rows:
        normalized.append({str(k): ("" if v is None else str(v)) for k, v in row.items()})
    return normalized


def fetch_company_stats_returns(db: str, ts_code: str) -> Dict[str, float]:
    sql = """
        SELECT trade_date::text AS trade_date, daily_return
        FROM int_company_stats
        WHERE ts_code = %s
          AND daily_return IS NOT NULL
        ORDER BY trade_date
    """
    with psycopg.connect(dsn_for(db), row_factory=psycopg.rows.dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (ts_code,))
            rows = cur.fetchall()
    returns: Dict[str, float] = {}
    for row in rows:
        try:
            returns[str(row["trade_date"])] = float(row["daily_return"])
        except Exception:
            continue
    return returns
