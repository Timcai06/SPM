#!/usr/bin/env python3
"""Build company seed CSV from collected public announcement sources."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "data" / "companies_public.csv"
SOURCE_FILES = [
    ROOT / "data" / "source_sse.csv",
    ROOT / "data" / "source_szse.csv",
    ROOT / "data" / "source_cninfo.csv",
    ROOT / "data" / "source_szse_suspension.csv",
]

CODE_RE = re.compile(r"^[0-9]{6}$")
SHORT_NAME_RE = re.compile(r"证券简称[:：]\s*([A-Za-z0-9\u4e00-\u9fa5*STST退]+)")
FULL_NAME_SSE_RE = re.compile(r"^(.+?股份有限公司)")
SHORT_NAME_SZSE_RE = re.compile(r"^([^：:\s]{2,20})[：:]")
BOARD_RE = re.compile(r"板块[:：]\s*([A-Z]+)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build public company seed CSV from collected sources.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        cleaned = (line.replace("\x00", "") for line in f)
        return list(csv.DictReader(cleaned))


def exchange_from_code(code: str) -> str:
    if code.startswith(("600", "601", "603", "605", "688", "900")):
        return "SSE"
    if code.startswith(("000", "001", "002", "003", "300", "301", "200")):
        return "SZSE"
    if code.startswith(("430", "440", "830", "831", "832", "833", "834", "835", "836", "837", "838", "839", "870", "871", "872", "873", "874", "875", "876", "877", "878", "879")):
        return "BSE"
    return ""


def ts_code_from_code(code: str) -> str:
    exchange = exchange_from_code(code)
    if exchange == "SSE":
        return f"{code}.SH"
    if exchange == "SZSE":
        return f"{code}.SZ"
    if exchange == "BSE":
        return f"{code}.BJ"
    return code


def infer_industry_l1(text: str) -> str:
    text = text or ""
    clean_text = text.replace("证券代码", "").replace("证券简称", "")
    if any(x in clean_text for x in ["军工", "航空", "导弹", "无人机", "国防", "战机"]):
        return "军工"
    if any(x in clean_text for x in ["储能", "电池", "光伏", "电网", "新能源", "输变电"]):
        return "新能源"
    if any(x in clean_text for x in ["人工智能", "AI", "算力", "芯片", "机器人", "软件", "数字"]):
        return "科技"
    if any(x in clean_text for x in ["消费", "旅游", "酒店", "饮料", "食品", "保险"]):
        return "消费"
    if any(x in clean_text for x in ["银行", "保险", "金融"]):
        return "金融"
    return "其他"


def extract_short_name(row: dict[str, str]) -> str:
    title = (row.get("title") or "").strip()
    content = (row.get("content") or "").strip()
    m = SHORT_NAME_RE.search(content)
    if m:
        return m.group(1).strip()
    m = SHORT_NAME_SZSE_RE.match(title)
    if m:
        return m.group(1).strip()
    return ""


def extract_full_name(row: dict[str, str]) -> str:
    title = (row.get("title") or "").strip()
    content = (row.get("content") or "").strip()
    m = FULL_NAME_SSE_RE.match(title)
    if m:
        return m.group(1).strip()
    if "股份有限公司" in content:
        prefix = content.split("；", 1)[0]
        if "股份有限公司" in prefix:
            return prefix.strip()
    return ""


def extract_industry_l2(row: dict[str, str]) -> str:
    text = " ".join([row.get("source", ""), row.get("title", ""), row.get("content", "")])
    return infer_industry_l1(text)


def concept_tags(row: dict[str, str], short_name: str, full_name: str, industry_l1: str) -> list[str]:
    tags: list[str] = []
    for item in [industry_l1, short_name, full_name]:
        item = (item or "").strip()
        if item and item not in tags:
            tags.append(item)
    return tags


def merge_record(existing: dict[str, str], incoming: dict[str, str]) -> dict[str, str]:
    result = dict(existing)
    for key in ["company_name", "business_scope", "core_products", "exchange", "industry_l1", "industry_l2"]:
        if (not result.get(key)) and incoming.get(key):
            result[key] = incoming[key]
    old_tags = json.loads(result.get("concept_tags", "[]"))
    new_tags = json.loads(incoming.get("concept_tags", "[]"))
    merged_tags = []
    for tag in old_tags + new_tags:
        if tag and tag not in merged_tags:
            merged_tags.append(tag)
    result["concept_tags"] = json.dumps(merged_tags, ensure_ascii=False)
    return result


def main() -> None:
    args = parse_args()
    records: dict[str, dict[str, str]] = {}

    for source_file in SOURCE_FILES:
        if not source_file.exists():
            continue
        for row in read_csv(source_file):
            code = (row.get("symbol_or_subject") or "").strip()
            if not CODE_RE.match(code):
                continue
            short_name = extract_short_name(row)
            full_name = extract_full_name(row)
            industry_l1 = infer_industry_l1(" ".join([row.get("source", ""), row.get("title", ""), row.get("content", "")]))
            incoming = {
                "ts_code": ts_code_from_code(code),
                "company_name": short_name or full_name or code,
                "exchange": exchange_from_code(code),
                "industry_l1": industry_l1,
                "industry_l2": extract_industry_l2(row),
                "business_scope": full_name or short_name or "",
                "core_products": industry_l1,
                "concept_tags": json.dumps(concept_tags(row, short_name, full_name, industry_l1), ensure_ascii=False),
            }
            if incoming["ts_code"] in records:
                records[incoming["ts_code"]] = merge_record(records[incoming["ts_code"]], incoming)
            else:
                records[incoming["ts_code"]] = incoming

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["ts_code", "company_name", "exchange", "industry_l1", "industry_l2", "business_scope", "core_products", "concept_tags"]
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for ts_code in sorted(records):
            writer.writerow(records[ts_code])
    print(f"Wrote {len(records)} public company rows to {output_path}")


if __name__ == "__main__":
    main()
