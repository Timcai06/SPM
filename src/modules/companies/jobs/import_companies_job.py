#!/usr/bin/env python3
"""Import A-share company universe from AKShare into PostgreSQL."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import akshare as ak
import psycopg

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.storage.db_guard import dsn_for, write_guard
from modules.companies.domain.company_identity import concept_json, exchange_from_code, ts_code_from_code


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import A-share companies from AKShare into PostgreSQL.")
    parser.add_argument("--db", default="stock_event_mining")
    parser.add_argument("--max-symbols", type=int, default=0)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--lock-timeout-sec", type=int, default=120)
    return parser.parse_args(argv)


def load_akshare_rows(offset: int, max_symbols: int) -> list[dict[str, str]]:
    df = ak.stock_zh_a_spot_em()
    code_col = "代码" if "代码" in df.columns else "code"
    name_col = "名称" if "名称" in df.columns else "name"
    rows: list[dict[str, str]] = []
    for _, row in df.iterrows():
        code = str(row.get(code_col) or "").strip()
        name = str(row.get(name_col) or "").strip()
        if len(code) != 6 or not code.isdigit() or not name:
            continue
        ts_code = ts_code_from_code(code)
        exchange = exchange_from_code(code)
        if not ts_code or not exchange:
            continue
        rows.append(
            {
                "ts_code": ts_code,
                "company_name": name,
                "exchange": exchange,
                "industry_l1": "其他",
                "industry_l2": "其他",
                "business_scope": name,
                "core_products": "其他",
                "concept_tags": concept_json(["其他", name]),
            }
        )
    rows.sort(key=lambda item: item["ts_code"])
    start = max(offset, 0)
    end = None if max_symbols <= 0 else start + max_symbols
    return rows[start:end]


def upsert_companies(db_name: str, rows: list[dict[str, str]], lock_timeout_sec: int) -> None:
    with write_guard(db_name=db_name, required_tables=["companies"], lock_timeout_sec=lock_timeout_sec):
        with psycopg.connect(dsn_for(db_name)) as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO companies (
                        ts_code, company_name, exchange, industry_l1, industry_l2,
                        business_scope, core_products, concept_tags, is_active
                    )
                    VALUES (
                        %(ts_code)s, %(company_name)s, %(exchange)s, %(industry_l1)s, %(industry_l2)s,
                        %(business_scope)s, %(core_products)s, %(concept_tags)s::jsonb, TRUE
                    )
                    ON CONFLICT (ts_code) DO UPDATE
                    SET company_name = CASE WHEN EXCLUDED.company_name <> '' THEN EXCLUDED.company_name ELSE companies.company_name END,
                        exchange = CASE WHEN EXCLUDED.exchange <> '' THEN EXCLUDED.exchange ELSE companies.exchange END,
                        industry_l1 = CASE WHEN companies.industry_l1 IS NULL OR companies.industry_l1 = '' THEN EXCLUDED.industry_l1 ELSE companies.industry_l1 END,
                        industry_l2 = CASE WHEN companies.industry_l2 IS NULL OR companies.industry_l2 = '' THEN EXCLUDED.industry_l2 ELSE companies.industry_l2 END,
                        business_scope = CASE WHEN companies.business_scope IS NULL OR companies.business_scope = '' THEN EXCLUDED.business_scope ELSE companies.business_scope END,
                        core_products = CASE WHEN companies.core_products IS NULL OR companies.core_products = '' THEN EXCLUDED.core_products ELSE companies.core_products END,
                        concept_tags = CASE WHEN companies.concept_tags = '[]'::jsonb THEN EXCLUDED.concept_tags ELSE companies.concept_tags END,
                        is_active = TRUE,
                        updated_at = NOW()
                    """,
                    rows,
                )
            conn.commit()


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    rows = load_akshare_rows(args.offset, args.max_symbols)
    if not rows:
        raise RuntimeError("AKShare returned zero A-share companies.")
    upsert_companies(args.db, rows, args.lock_timeout_sec)
    print(f"Imported {len(rows)} A-share companies into {args.db}")


if __name__ == "__main__":
    main()
