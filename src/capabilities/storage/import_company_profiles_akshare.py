#!/usr/bin/env python3
"""Enrich company profile seed CSV from AKShare public company endpoints."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import akshare as ak
import psycopg

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.storage.db_guard import dsn_for
from capabilities.storage.import_companies_tushare import map_industry_l1


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = "stock_event_mining"
DEFAULT_INPUT = ROOT / "output" / "seeds" / "company_profiles_seed.csv"
DEFAULT_OUTPUT = ROOT / "output" / "seeds" / "company_profiles_seed.csv"

FIELDNAMES = [
    "ts_code",
    "company_name",
    "exchange",
    "industry_l1",
    "industry_l2",
    "business_scope",
    "core_products",
    "concept_tags",
    "region",
    "list_date",
    "state_owned_flag",
    "company_type",
    "employees",
    "total_shares",
    "float_shares",
    "main_customers",
    "main_suppliers",
]

PROVINCES = [
    "北京",
    "天津",
    "上海",
    "重庆",
    "河北",
    "山西",
    "辽宁",
    "吉林",
    "黑龙江",
    "江苏",
    "浙江",
    "安徽",
    "福建",
    "江西",
    "山东",
    "河南",
    "湖北",
    "湖南",
    "广东",
    "海南",
    "四川",
    "贵州",
    "云南",
    "陕西",
    "甘肃",
    "青海",
    "台湾",
    "内蒙古",
    "广西",
    "西藏",
    "宁夏",
    "新疆",
    "香港",
    "澳门",
]

STATE_OWNER_KEYWORDS = [
    "国务院",
    "国资委",
    "中央企业",
    "中国航空工业",
    "中国兵器",
    "中国电子",
    "中国移动",
    "中国电信",
    "中国联通",
    "中国石油",
    "中国石化",
    "国家电网",
    "南方电网",
    "国药集团",
    "招商局",
    "华润",
    "中粮",
    "保利集团",
    "中国中车",
    "中国船舶",
    "中国建筑",
    "中国交通建设",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import company profile seed rows from AKShare public endpoints.")
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Existing seed to preserve manual fields from.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--max-symbols", type=int, default=0, help="Optional limit for smoke tests.")
    parser.add_argument("--sleep-sec", type=float, default=0.05)
    parser.add_argument("--progress-every", type=int, default=10)
    parser.add_argument("--with-holders", action="store_true", help="Also query top holders for state-owned heuristics.")
    return parser.parse_args(argv)


def read_seed(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return {(row.get("ts_code") or "").strip().upper(): row for row in rows if (row.get("ts_code") or "").strip()}


def write_seed(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def load_companies(db_name: str, max_symbols: int) -> list[dict[str, str]]:
    with psycopg.connect(dsn_for(db_name), row_factory=psycopg.rows.dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ts_code, company_name, exchange, industry_l1, industry_l2,
                       business_scope, core_products, concept_tags
                FROM companies
                WHERE is_active = TRUE
                ORDER BY ts_code
                """
            )
            rows = [dict(row) for row in cur.fetchall()]
    if max_symbols > 0:
        return rows[:max_symbols]
    return rows


def code_part(ts_code: str) -> str:
    return str(ts_code or "").split(".", 1)[0]


def safe_text(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text.lower() == "nan" else text


def parse_date(value: Any) -> str:
    text = safe_text(value)
    if not text:
        return ""
    digits = re.sub(r"[^0-9]", "", text)
    if len(digits) >= 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return text


def parse_json_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [safe_text(item) for item in value if safe_text(item)]
    text = safe_text(value)
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except Exception:
        parsed = None
    if isinstance(parsed, list):
        return [safe_text(item) for item in parsed if safe_text(item)]
    parts = re.split(r"[,，、;；|]", text)
    return [part.strip() for part in parts if part.strip()]


def json_list(items: list[str]) -> str:
    unique: list[str] = []
    for item in items:
        text = safe_text(item)
        if text and text not in unique:
            unique.append(text)
    return json.dumps(unique, ensure_ascii=False)


def info_em_map(symbol: str) -> dict[str, Any]:
    df = ak.stock_individual_info_em(symbol=symbol)
    result: dict[str, Any] = {}
    for _, row in df.iterrows():
        key = safe_text(row.get("item"))
        if key:
            result[key] = row.get("value")
    return result


def profile_cninfo_map(symbol: str) -> dict[str, Any]:
    df = ak.stock_profile_cninfo(symbol=symbol)
    if df is None or df.empty:
        return {}
    return {str(key): value for key, value in df.iloc[0].to_dict().items()}


def infer_region(address: str) -> str:
    text = safe_text(address)
    if not text:
        return ""
    for province in PROVINCES:
        if text.startswith(province) or province in text[:8]:
            remainder = re.sub(rf"^.*?{re.escape(province)}(?:省|市|自治区|壮族自治区|回族自治区|维吾尔自治区)?", "", text)
            city_match = re.search(r"([\u4e00-\u9fa5]{2,8})市", remainder)
            if city_match and city_match.group(1) != province:
                return f"{province}-{city_match.group(1)}"
            return province
    return ""


def infer_company_type(market: str, exchange: str) -> str:
    text = safe_text(market)
    if text:
        return text
    if exchange == "SSE":
        return "沪市A股"
    if exchange == "SZSE":
        return "深市A股"
    if exchange == "BSE":
        return "北交所"
    return "A股"


def infer_state_owned(profile: dict[str, Any], holder_names: list[str]) -> str:
    text = " ".join(
        [
            safe_text(profile.get("公司名称")),
            safe_text(profile.get("机构简介")),
            safe_text(profile.get("注册地址")),
            " ".join(holder_names[:3]),
        ]
    )
    if any(keyword in text for keyword in STATE_OWNER_KEYWORDS):
        return "true"
    return ""


def fetch_top_holder_names(symbol: str) -> list[str]:
    try:
        df = ak.stock_main_stock_holder(stock=symbol)
    except Exception:
        return []
    if df is None or df.empty or "股东名称" not in df.columns:
        return []
    return [safe_text(value) for value in df["股东名称"].head(5).tolist() if safe_text(value)]


def first_non_empty(*values: Any) -> str:
    for value in values:
        text = safe_text(value)
        if text:
            return text
    return ""


def build_row(
    company: dict[str, Any],
    seed: dict[str, str],
    info: dict[str, Any],
    profile: dict[str, Any],
    holder_names: list[str],
) -> dict[str, str]:
    ts_code = safe_text(company.get("ts_code")).upper()
    exchange = first_non_empty(seed.get("exchange"), company.get("exchange"))
    industry_l2 = first_non_empty(profile.get("所属行业"), info.get("行业"), seed.get("industry_l2"), company.get("industry_l2"))
    industry_l1 = first_non_empty(seed.get("industry_l1"), company.get("industry_l1"), map_industry_l1(industry_l2))
    if industry_l1 == "其他":
        industry_l1 = map_industry_l1(industry_l2)
    business_scope = first_non_empty(profile.get("经营范围"), seed.get("business_scope"), company.get("business_scope"))
    core_products = first_non_empty(profile.get("主营业务"), seed.get("core_products"), industry_l2, industry_l1)
    concept_tags = parse_json_list(seed.get("concept_tags")) + parse_json_list(company.get("concept_tags"))
    concept_tags.extend([industry_l1, industry_l2, safe_text(info.get("股票简称"))])
    region = first_non_empty(seed.get("region"), infer_region(safe_text(profile.get("注册地址"))), infer_region(safe_text(profile.get("办公地址"))))
    state_owned = first_non_empty(seed.get("state_owned_flag"), infer_state_owned(profile, holder_names))
    return {
        "ts_code": ts_code,
        "company_name": first_non_empty(profile.get("A股简称"), info.get("股票简称"), seed.get("company_name"), company.get("company_name")),
        "exchange": exchange,
        "industry_l1": industry_l1,
        "industry_l2": industry_l2 or industry_l1,
        "business_scope": business_scope,
        "core_products": core_products,
        "concept_tags": json_list(concept_tags),
        "region": region,
        "list_date": first_non_empty(parse_date(profile.get("上市日期")), parse_date(info.get("上市时间")), seed.get("list_date")),
        "state_owned_flag": state_owned,
        "company_type": first_non_empty(seed.get("company_type"), infer_company_type(safe_text(profile.get("所属市场")), exchange)),
        "employees": first_non_empty(seed.get("employees")),
        "total_shares": first_non_empty(info.get("总股本"), seed.get("total_shares")),
        "float_shares": first_non_empty(info.get("流通股"), seed.get("float_shares")),
        "main_customers": seed.get("main_customers") or "[]",
        "main_suppliers": seed.get("main_suppliers") or "[]",
    }


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    seed_rows = read_seed(Path(args.input).resolve())
    companies = load_companies(args.db, args.max_symbols)
    output_rows: list[dict[str, str]] = []
    failures: list[str] = []
    for idx, company in enumerate(companies, start=1):
        ts_code = safe_text(company.get("ts_code")).upper()
        symbol = code_part(ts_code)
        if args.progress_every > 0 and (idx == 1 or idx % args.progress_every == 0):
            print(f"[profiles-akshare] progress {idx}/{len(companies)}, failures={len(failures)}")
        try:
            info = info_em_map(symbol)
        except Exception:
            info = {}
        try:
            profile = profile_cninfo_map(symbol)
        except Exception:
            profile = {}
        holder_names = fetch_top_holder_names(symbol) if args.with_holders else []
        if not info and not profile:
            failures.append(ts_code)
        output_rows.append(build_row(company, seed_rows.get(ts_code, {}), info, profile, holder_names))
        time.sleep(args.sleep_sec)

    write_seed(Path(args.output).resolve(), output_rows)
    print(f"Wrote {len(output_rows)} company profile seed rows to {Path(args.output).resolve()}")
    if failures:
        print(f"Rows without public profile enrichment: {len(failures)}")
        print("Failed symbols: " + ", ".join(failures[:20]))


if __name__ == "__main__":
    main()
