#!/usr/bin/env python3
"""Fetch A-share company basics from Tushare and write normalized company seed CSV."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "output" / "seeds" / "companies_a_share.csv"


INDUSTRY_L1_KEYWORDS = {
    "军工": ["军工", "航空", "航天", "船舶", "兵器", "国防", "雷达", "导弹"],
    "新能源": ["电池", "储能", "光伏", "风电", "电网", "输变电", "锂", "新能源", "汽车整车"],
    "科技": ["软件", "芯片", "半导体", "通信", "计算机", "电子", "互联网", "传媒", "人工智能"],
    "消费": ["食品", "饮料", "旅游", "酒店", "零售", "家电", "服装", "医美", "白酒"],
    "金融": ["银行", "保险", "证券", "多元金融"],
}
STOCK_BASIC_FIELDS = "ts_code,name,industry,fullname,area,market,list_date"
STOCK_COMPANY_FIELDS = "ts_code,province,city,employees,main_business,business_scope"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import A-share company basics from Tushare.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--tushare-token", default="")
    parser.add_argument("--tushare-token-file", default="")
    parser.add_argument("--list-status", default="L", help="Tushare list_status, default L.")
    return parser.parse_args()


def resolve_tushare_token(args: argparse.Namespace) -> tuple[str, str]:
    if args.tushare_token.strip():
        return args.tushare_token.strip(), "cli_arg"
    if args.tushare_token_file.strip():
        token_path = Path(args.tushare_token_file).expanduser().resolve()
        if token_path.exists():
            content = token_path.read_text(encoding="utf-8").strip()
            if content:
                return content, f"file:{token_path.name}"
    default_paths = [
        ROOT / ".secrets" / "tushare_token.txt",
        Path.home() / ".config" / "stock_event_mining" / "tushare_token.txt",
    ]
    for token_path in default_paths:
        if token_path.exists():
            content = token_path.read_text(encoding="utf-8").strip()
            if content:
                return content, f"file:{token_path.name}"
    env_token = os.getenv("TUSHARE_TOKEN", "").strip()
    if env_token:
        return env_token, "env:TUSHARE_TOKEN"
    return "", "missing"


def load_tushare() -> object:
    import tushare as ts  # type: ignore

    return ts


def call_with_retry(fn, retries: int = 2, wait_seconds: float = 1.0):
    last_exc = None
    for idx in range(retries + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if idx >= retries:
                break
            time.sleep(wait_seconds * (idx + 1))
    raise last_exc  # type: ignore[misc]


def map_exchange(ts_code: str) -> str:
    if ts_code.endswith(".SZ"):
        return "SZSE"
    if ts_code.endswith(".SH"):
        return "SSE"
    if ts_code.endswith(".BJ"):
        return "BSE"
    return ""


def map_industry_l1(industry_name: str) -> str:
    text = (industry_name or "").strip()
    for label, keywords in INDUSTRY_L1_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return label
    return "其他"


def build_concept_tags(industry_l1: str, industry_l2: str, name: str) -> list[str]:
    tags: list[str] = []
    for item in [industry_l1, industry_l2]:
        if item and item not in tags:
            tags.append(item)
    name_text = name or ""
    if "银行" in name_text and "银行" not in tags:
        tags.append("银行")
    if "保险" in name_text and "保险" not in tags:
        tags.append("保险")
    if "芯片" in industry_l2 and "芯片" not in tags:
        tags.append("芯片")
    if "电池" in industry_l2 and "电池" not in tags:
        tags.append("电池")
    return tags


def normalize_company_type(market: str, exchange: str) -> str:
    text = (market or "").strip()
    if text:
        return text
    if exchange == "SZSE":
        return "深市A股"
    if exchange == "SSE":
        return "沪市A股"
    if exchange == "BSE":
        return "北交所"
    return "A股"


def build_profile_map(pro) -> dict[str, dict[str, Any]]:
    profile_map: dict[str, dict[str, Any]] = {}
    for exchange in ("SSE", "SZSE", "BSE"):
        try:
            df = call_with_retry(
                lambda exch=exchange: pro.stock_company(exchange=exch, fields=STOCK_COMPANY_FIELDS)
            )
        except Exception:
            continue
        if df is None or df.empty:
            continue
        for _, row in df.iterrows():
            ts_code = str(row.get("ts_code") or "").strip()
            if not ts_code:
                continue
            profile_map[ts_code] = {
                "province": str(row.get("province") or "").strip(),
                "city": str(row.get("city") or "").strip(),
                "employees": row.get("employees"),
                "main_business": str(row.get("main_business") or "").strip(),
                "business_scope": str(row.get("business_scope") or "").strip(),
            }
    return profile_map


def normalize_region(area: str, province: str, city: str) -> str:
    province_text = (province or "").strip()
    city_text = (city or "").strip()
    area_text = (area or "").strip()
    if province_text and city_text and city_text != province_text:
        return f"{province_text}-{city_text}"
    if province_text:
        return province_text
    if city_text:
        return city_text
    return area_text


def normalize_rows(df, profile_map: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for _, row in df.iterrows():
        ts_code = str(row.get("ts_code") or "").strip()
        if not ts_code or ts_code in seen:
            continue
        seen.add(ts_code)
        company_name = str(row.get("name") or "").strip()
        industry_l2 = str(row.get("industry") or "").strip()
        industry_l1 = map_industry_l1(industry_l2)
        exchange = map_exchange(ts_code)
        area = str(row.get("area") or "").strip()
        market = str(row.get("market") or "").strip()
        list_date = str(row.get("list_date") or "").strip()
        profile = profile_map.get(ts_code, {})
        region = normalize_region(area, str(profile.get("province") or ""), str(profile.get("city") or ""))
        company_type = normalize_company_type(market=market, exchange=exchange)
        business_scope = str(profile.get("business_scope") or "").strip() or str(row.get("fullname") or "").strip()
        main_business = str(profile.get("main_business") or "").strip()
        employees = profile.get("employees")
        rows.append(
            {
                "ts_code": ts_code,
                "company_name": company_name,
                "exchange": exchange,
                "industry_l1": industry_l1,
                "industry_l2": industry_l2 or industry_l1,
                "business_scope": business_scope,
                "core_products": main_business or industry_l2 or industry_l1,
                "concept_tags": json.dumps(build_concept_tags(industry_l1, industry_l2, company_name), ensure_ascii=False),
                "region": region,
                "list_date": list_date,
                "state_owned_flag": "",
                "company_type": company_type,
                "employees": "" if employees in (None, "") else str(employees),
                "total_shares": "",
                "float_shares": "",
                "main_customers": "[]",
                "main_suppliers": "[]",
            }
        )
    rows.sort(key=lambda item: item["ts_code"])
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
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
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    token, token_source = resolve_tushare_token(args)
    if not token:
        raise SystemExit("Missing Tushare token. Provide --tushare-token, --tushare-token-file, or TUSHARE_TOKEN.")

    ts = load_tushare()
    ts.set_token(token)
    pro = ts.pro_api(token)
    df = call_with_retry(
        lambda: pro.stock_basic(
            exchange="",
            list_status=args.list_status,
            fields=STOCK_BASIC_FIELDS,
        )
    )
    profile_map = build_profile_map(pro)
    rows = normalize_rows(df, profile_map)
    output_path = Path(args.output).resolve()
    write_csv(output_path, rows)
    print(f"Wrote {len(rows)} company rows to {output_path}")
    print(f"Tushare token source: {token_source}")


if __name__ == "__main__":
    main()
