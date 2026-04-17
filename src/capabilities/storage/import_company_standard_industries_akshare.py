#!/usr/bin/env python3
"""Backfill standard listed-company industries from CNInfo classification."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import akshare as ak
import psycopg

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.storage.db_guard import dsn_for, write_guard


DEFAULT_DB = "stock_event_mining"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill standard industry_l1 from CNInfo industry classification.")
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--max-symbols", type=int, default=200)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--start-date", default="20230101")
    parser.add_argument("--end-date", default="20251231")
    parser.add_argument("--sleep-sec", type=float, default=0.05)
    parser.add_argument("--progress-every", type=int, default=20)
    parser.add_argument("--lock-timeout-sec", type=int, default=120)
    return parser.parse_args()


def get_company_symbols(db_name: str, max_symbols: int, offset: int) -> list[dict[str, str]]:
    with psycopg.connect(dsn_for(db_name), row_factory=psycopg.rows.dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ts_code, company_name, industry_l2, concept_tags
                FROM companies
                WHERE is_active = TRUE
                ORDER BY ts_code
                OFFSET %s
                LIMIT %s
                """,
                (max(offset, 0), max_symbols),
            )
            return [dict(row) for row in cur.fetchall()]


def normalize_code(ts_code: str) -> str:
    return str(ts_code or "").split(".", 1)[0]


def safe_text(value: object) -> str:
    text = str(value or "").strip()
    return "" if text.lower() == "nan" else text


def latest_standard_industry(ts_code: str, start_date: str, end_date: str) -> dict[str, str] | None:
    code = normalize_code(ts_code)
    if not code:
        return None
    df = ak.stock_industry_change_cninfo(symbol=code, start_date=start_date, end_date=end_date)
    if df is None or df.empty:
        return None
    row = df.sort_values("变更日期").iloc[-1].to_dict()
    industry_code = safe_text(row.get("行业编码"))
    industry_major = safe_text(row.get("行业大类"))
    industry_category = safe_text(row.get("行业门类"))
    standard = safe_text(row.get("分类标准"))
    if not industry_code or not industry_major:
        return None
    return {
        "industry_l1": f"{industry_code}{industry_major}",
        "industry_code": industry_code,
        "industry_major": industry_major,
        "industry_category": industry_category,
        "standard": standard,
    }


def merge_tags(existing_tags: object, additions: list[str]) -> str:
    tags: list[str] = []
    if isinstance(existing_tags, list):
        tags.extend(str(item).strip() for item in existing_tags if str(item).strip())
    else:
        raw = safe_text(existing_tags)
        if raw:
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = []
            if isinstance(parsed, list):
                tags.extend(str(item).strip() for item in parsed if str(item).strip())
    for item in additions:
        text = safe_text(item)
        if text and text not in tags:
            tags.append(text)
    return json.dumps(tags[:12], ensure_ascii=False)


def update_companies(db_name: str, rows: list[dict[str, str]], lock_timeout_sec: int) -> int:
    if not rows:
        return 0
    with write_guard(db_name=db_name, required_tables=["companies"], lock_timeout_sec=lock_timeout_sec):
        with psycopg.connect(dsn_for(db_name)) as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    UPDATE companies
                    SET industry_l1 = %(industry_l1)s,
                        concept_tags = %(concept_tags)s::jsonb,
                        updated_at = NOW()
                    WHERE ts_code = %(ts_code)s
                    """,
                    rows,
                )
                updated = cur.rowcount
            conn.commit()
    return updated


def main() -> None:
    args = parse_args()
    companies = get_company_symbols(args.db, max_symbols=args.max_symbols, offset=args.offset)
    print(f"[standard-industry] companies={len(companies)} offset={args.offset}", flush=True)
    rows: list[dict[str, str]] = []
    failures = 0
    started = time.time()
    for idx, company in enumerate(companies, start=1):
        ts_code = company["ts_code"]
        try:
            industry = latest_standard_industry(ts_code, args.start_date, args.end_date)
        except Exception:
            industry = None
        if industry is None:
            failures += 1
        else:
            concept_tags = merge_tags(
                company.get("concept_tags"),
                [industry["industry_l1"], industry["industry_code"], industry["industry_major"], industry["industry_category"]],
            )
            rows.append({"ts_code": ts_code, "industry_l1": industry["industry_l1"], "concept_tags": concept_tags})
        if args.progress_every > 0 and (idx == 1 or idx % args.progress_every == 0 or idx == len(companies)):
            elapsed = int(time.time() - started)
            print(f"[standard-industry] progress {idx}/{len(companies)}, ready={len(rows)}, failures={failures}, elapsed={elapsed}s", flush=True)
        time.sleep(args.sleep_sec)
    updated = update_companies(args.db, rows, lock_timeout_sec=args.lock_timeout_sec)
    print(f"[standard-industry] updated_companies={updated}, failures={failures}")


if __name__ == "__main__":
    main()
