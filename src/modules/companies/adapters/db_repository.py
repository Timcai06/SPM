#!/usr/bin/env python3
"""Database access helpers for company jobs."""

from __future__ import annotations

from typing import Any

import psycopg

from modules.runtime.adapters.db import dsn_for


def load_active_companies(
    db_name: str,
    *,
    max_symbols: int = 0,
    offset: int = 0,
    only_dirty_l1: bool = False,
    skip_legacy: bool = False,
) -> list[dict[str, Any]]:
    with psycopg.connect(dsn_for(db_name), row_factory=psycopg.rows.dict_row) as conn:
        with conn.cursor() as cur:
            where = "WHERE is_active = TRUE"
            if only_dirty_l1:
                where += " AND (industry_l1 IS NULL OR industry_l1 = '其他' OR industry_l1 !~ '^[A-Y]\\d{2}')"
            if skip_legacy:
                where += " AND company_name !~ '(退|^PT|^\\*ST|^ST|^S\\*ST)'"
            limit_clause = "" if max_symbols <= 0 else f"LIMIT {int(max_symbols)}"
            cur.execute(
                f"""
                SELECT ts_code, company_name, exchange, industry_l1, industry_l2,
                       business_scope, core_products, concept_tags
                FROM companies
                {where}
                ORDER BY ts_code
                OFFSET %s
                {limit_clause}
                """,
                (max(offset, 0),),
            )
            return [dict(row) for row in cur.fetchall()]
