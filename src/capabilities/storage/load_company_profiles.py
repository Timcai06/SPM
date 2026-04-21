#!/usr/bin/env python3
"""Load company profile snapshots from the companies dimension into PostgreSQL."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.storage.db_guard import write_guard


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = "stock_event_mining"
DEFAULT_SNAPSHOT_DATE = datetime.now().date().isoformat()
DEFAULT_INPUT = ROOT / "output" / "seeds" / "company_profiles_seed.csv"
FALLBACK_INPUTS = [
    DEFAULT_INPUT,
    ROOT / "output" / "seeds" / "companies_a_share.csv",
    ROOT / "output" / "seeds" / "companies_public.csv",
    ROOT / "output" / "seeds" / "companies_seed.csv",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load company profiles into PostgreSQL.")
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--snapshot-date", default=DEFAULT_SNAPSHOT_DATE)
    parser.add_argument(
        "--input",
        default="",
        help="Optional company profile seed CSV. If omitted, loader auto-discovers common seed files.",
    )
    parser.add_argument("--lock-timeout-sec", type=int, default=120, help="Max seconds to wait for DB write lock.")
    return parser.parse_args(argv)


def normalize_snapshot_date(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return DEFAULT_SNAPSHOT_DATE
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except Exception:
        return DEFAULT_SNAPSHOT_DATE


def resolve_input_path(value: str) -> Path | None:
    text = (value or "").strip()
    if text:
        path = Path(text).expanduser().resolve()
        return path if path.exists() else None
    for candidate in FALLBACK_INPUTS:
        if candidate.exists():
            return candidate.resolve()
    return None


def read_seed_rows(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None or not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    output: dict[str, dict[str, str]] = {}
    for row in rows:
        ts_code = (row.get("ts_code") or "").strip().upper()
        if ts_code:
            output[ts_code] = row
    return output


def normalize_date(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except Exception:
            continue
    return None


def normalize_int(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(float(text.replace(",", "")))
    except Exception:
        return None


def normalize_numeric(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text.replace(",", ""))
    except Exception:
        return None


def normalize_bool(value: Any) -> bool | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    if text in {"1", "true", "t", "yes", "y", "是", "国企", "央企", "央国企"}:
        return True
    if text in {"0", "false", "f", "no", "n", "否", "民企", "非国企"}:
        return False
    return None


def normalize_json_list(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return cleaned or None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = None
    if isinstance(parsed, list):
        cleaned = [str(item).strip() for item in parsed if str(item).strip()]
        return cleaned or None
    parts = [part.strip() for part in raw.replace("；", ";").replace("、", ",").replace("|", ",").replace(";", ",").split(",")]
    cleaned = [part for part in parts if part]
    return cleaned or None


def normalize_region(seed_row: dict[str, str]) -> str | None:
    for key in ("region", "area"):
        text = str(seed_row.get(key) or "").strip()
        if text:
            return text
    province = str(seed_row.get("province") or "").strip()
    city = str(seed_row.get("city") or "").strip()
    if province and city and city != province:
        return f"{province}-{city}"
    if province:
        return province
    if city:
        return city
    return None


def infer_company_type(exchange: str, seed_row: dict[str, str]) -> str:
    for key in ("company_type", "market"):
        text = str(seed_row.get(key) or "").strip()
        if text:
            return text
    if exchange == "SSE":
        return "沪市A股"
    if exchange == "SZSE":
        return "深市A股"
    if exchange == "BSE":
        return "北交所"
    return "A股"


def pick_text(*values: Any) -> str | None:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return None


def build_company_profile_rows(
    companies: list[dict[str, Any]],
    snapshot_date: str,
    seed_rows: dict[str, dict[str, str]],
    seed_path: Path | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seed_source = seed_path.stem if seed_path else "companies_table"
    for company in companies:
        ts_code = str(company["ts_code"]).strip().upper()
        seed_row = seed_rows.get(ts_code, {})
        company_concepts = normalize_json_list(company.get("concept_tags")) or []
        seed_concepts = normalize_json_list(seed_row.get("concept_tags")) or []
        concept_tags = seed_concepts or company_concepts
        core_products = (
            normalize_json_list(seed_row.get("core_products"))
            or normalize_json_list(company.get("core_products"))
            or [company.get("industry_l1") or "其他"]
        )
        main_customers = normalize_json_list(seed_row.get("main_customers")) or []
        main_suppliers = normalize_json_list(seed_row.get("main_suppliers")) or []
        data_source = seed_source if seed_row else "companies_table"
        rows.append(
            {
                "ts_code": ts_code,
                "snapshot_date": snapshot_date,
                "company_name": pick_text(seed_row.get("company_name"), company.get("company_name")) or ts_code,
                "exchange": pick_text(seed_row.get("exchange"), company.get("exchange")),
                "industry_l1": pick_text(seed_row.get("industry_l1"), company.get("industry_l1")),
                "industry_l2": pick_text(seed_row.get("industry_l2"), company.get("industry_l2")),
                "concept_tags": Jsonb(concept_tags),
                "region": normalize_region(seed_row),
                "list_date": normalize_date(seed_row.get("list_date")),
                "state_owned_flag": normalize_bool(seed_row.get("state_owned_flag")),
                "company_type": infer_company_type(str(company.get("exchange") or ""), seed_row),
                "business_scope": pick_text(seed_row.get("business_scope"), seed_row.get("main_business"), company.get("business_scope")),
                "core_products": Jsonb(core_products),
                "main_customers": Jsonb(main_customers),
                "main_suppliers": Jsonb(main_suppliers),
                "employees": normalize_int(seed_row.get("employees")),
                "total_shares": normalize_numeric(seed_row.get("total_shares")),
                "float_shares": normalize_numeric(seed_row.get("float_shares")),
                "data_source": data_source,
            }
        )
    return rows


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    snapshot_date = normalize_snapshot_date(args.snapshot_date)
    seed_path = resolve_input_path(args.input)
    seed_rows = read_seed_rows(seed_path)

    with write_guard(
        db_name=args.db,
        required_tables=["companies", "company_profiles"],
        lock_timeout_sec=args.lock_timeout_sec,
    ) as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(
                """
                SELECT
                    ts_code, company_name, exchange, industry_l1, industry_l2,
                    business_scope, core_products, concept_tags
                FROM companies
                WHERE is_active = TRUE
                ORDER BY ts_code
                """
            )
            companies = list(cur.fetchall())
            rows = build_company_profile_rows(
                companies=companies,
                snapshot_date=snapshot_date,
                seed_rows=seed_rows,
                seed_path=seed_path,
            )
            cur.executemany(
                """
                INSERT INTO company_profiles (
                    ts_code, snapshot_date, company_name, exchange, industry_l1, industry_l2,
                    concept_tags, region, list_date, state_owned_flag, company_type,
                    business_scope, core_products, main_customers, main_suppliers,
                    employees, total_shares, float_shares, data_source
                )
                VALUES (
                    %(ts_code)s, %(snapshot_date)s::date, %(company_name)s, %(exchange)s, %(industry_l1)s, %(industry_l2)s,
                    %(concept_tags)s, %(region)s, %(list_date)s::date, %(state_owned_flag)s, %(company_type)s,
                    %(business_scope)s, %(core_products)s, %(main_customers)s, %(main_suppliers)s,
                    %(employees)s, %(total_shares)s, %(float_shares)s, %(data_source)s
                )
                ON CONFLICT (ts_code, snapshot_date) DO UPDATE
                SET
                    company_name = EXCLUDED.company_name,
                    exchange = EXCLUDED.exchange,
                    industry_l1 = EXCLUDED.industry_l1,
                    industry_l2 = EXCLUDED.industry_l2,
                    concept_tags = EXCLUDED.concept_tags,
                    region = COALESCE(EXCLUDED.region, company_profiles.region),
                    list_date = COALESCE(EXCLUDED.list_date, company_profiles.list_date),
                    state_owned_flag = COALESCE(EXCLUDED.state_owned_flag, company_profiles.state_owned_flag),
                    company_type = COALESCE(EXCLUDED.company_type, company_profiles.company_type),
                    business_scope = COALESCE(EXCLUDED.business_scope, company_profiles.business_scope),
                    core_products = COALESCE(EXCLUDED.core_products, company_profiles.core_products),
                    main_customers = CASE
                        WHEN EXCLUDED.data_source <> 'companies_table'
                             OR company_profiles.main_customers = '[]'::jsonb
                        THEN EXCLUDED.main_customers
                        ELSE company_profiles.main_customers
                    END,
                    main_suppliers = CASE
                        WHEN EXCLUDED.data_source <> 'companies_table'
                             OR company_profiles.main_suppliers = '[]'::jsonb
                        THEN EXCLUDED.main_suppliers
                        ELSE company_profiles.main_suppliers
                    END,
                    employees = COALESCE(EXCLUDED.employees, company_profiles.employees),
                    total_shares = COALESCE(EXCLUDED.total_shares, company_profiles.total_shares),
                    float_shares = COALESCE(EXCLUDED.float_shares, company_profiles.float_shares),
                    data_source = CASE
                        WHEN EXCLUDED.data_source <> 'companies_table' THEN EXCLUDED.data_source
                        ELSE company_profiles.data_source
                    END,
                    updated_at = NOW()
                """,
                rows,
            )
        conn.commit()

    seed_text = str(seed_path) if seed_path else "none"
    print(
        f"Loaded company profiles snapshot for {args.db}: "
        f"snapshot_date={snapshot_date}, seed={seed_text}, rows={len(companies)}"
    )


if __name__ == "__main__":
    main()
