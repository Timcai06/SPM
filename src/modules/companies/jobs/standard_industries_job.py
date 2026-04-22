#!/usr/bin/env python3
"""Backfill CNInfo standard industry_l1 into companies."""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path
import sys

import akshare as ak
import psycopg

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from modules.companies.adapters.db_repository import load_active_companies
from modules.companies.domain.company_identity import safe_text
from modules.runtime.adapters.db import dsn_for, write_guard

STANDARD_L1_CODE_PATTERN = re.compile(r"^[A-Y][0-9]{2}$")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill standard industry_l1 from CNInfo.")
    parser.add_argument("--db", default="stock_event_mining")
    parser.add_argument("--max-symbols", type=int, default=200)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--start-date", default="19900101")
    parser.add_argument("--end-date", default="20251231")
    parser.add_argument("--sleep-sec", type=float, default=0.05)
    parser.add_argument("--progress-every", type=int, default=20)
    parser.add_argument("--only-dirty", action="store_true")
    parser.add_argument("--skip-legacy", action="store_true")
    parser.add_argument("--lock-timeout-sec", type=int, default=120)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--failure-backoff-sec", type=float, default=0.8)
    return parser.parse_args(argv)


def normalize_code(ts_code: str) -> str:
    return str(ts_code or "").split(".", 1)[0]


def latest_standard_industry(ts_code: str, start_date: str, end_date: str) -> dict[str, str] | None:
    code = normalize_code(ts_code)
    if not code:
        return None
    df = ak.stock_industry_change_cninfo(symbol=code, start_date=start_date, end_date=end_date)
    if df is None or df.empty:
        return None
    preferred = df
    if "分类标准编码" in df.columns:
        preferred = df[df["分类标准编码"].astype(str) == "008001"]
    if preferred.empty and "分类标准" in df.columns:
        preferred = df[df["分类标准"].astype(str).str.contains("上市公司协会", na=False)]
    if preferred.empty:
        preferred = df
    row = preferred.sort_values("变更日期").iloc[-1].to_dict()
    industry_code = safe_text(row.get("行业编码"))
    industry_major = safe_text(row.get("行业大类"))
    industry_category = safe_text(row.get("行业门类"))
    if not industry_code or not industry_major or not STANDARD_L1_CODE_PATTERN.match(industry_code):
        return None
    return {
        "industry_l1": f"{industry_code}{industry_major}",
        "industry_code": industry_code,
        "industry_major": industry_major,
        "industry_category": industry_category,
    }


def merge_tags(existing_tags: object, additions: list[str]) -> str:
    tags: list[str] = []
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


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    companies = load_active_companies(
        args.db,
        max_symbols=args.max_symbols,
        offset=args.offset,
        only_dirty_l1=args.only_dirty,
        skip_legacy=args.skip_legacy,
    )
    print(f"[standard-industry] companies={len(companies)} offset={args.offset}", flush=True)
    rows: list[dict[str, str]] = []
    failures = 0
    failure_reasons: Counter[str] = Counter()
    started = time.time()
    for idx, company in enumerate(companies, start=1):
        ts_code = company["ts_code"]
        industry = None
        last_reason = ""
        for attempt in range(max(args.retries, 0) + 1):
            try:
                industry = latest_standard_industry(ts_code, args.start_date, args.end_date)
                break
            except Exception as exc:
                last_reason = type(exc).__name__
                if attempt < max(args.retries, 0):
                    time.sleep(max(args.failure_backoff_sec, 0.0))
        if industry is None:
            failures += 1
            failure_reasons[last_reason or "no_data"] += 1
        else:
            rows.append(
                {
                    "ts_code": ts_code,
                    "industry_l1": industry["industry_l1"],
                    "concept_tags": merge_tags(
                        company.get("concept_tags"),
                        [industry["industry_l1"], industry["industry_code"], industry["industry_major"], industry["industry_category"]],
                    ),
                }
            )
        if args.progress_every > 0 and (idx == 1 or idx % args.progress_every == 0 or idx == len(companies)):
            elapsed = int(time.time() - started)
            print(f"[standard-industry] progress {idx}/{len(companies)}, ready={len(rows)}, failures={failures}, elapsed={elapsed}s", flush=True)
        time.sleep(args.sleep_sec)
    updated = update_companies(args.db, rows, args.lock_timeout_sec)
    print(f"[standard-industry] updated_companies={updated}, failures={failures}")
    if failure_reasons:
        print("[standard-industry] failure_reasons=" + ", ".join(f"{k}:{v}" for k, v in failure_reasons.most_common(5)))


if __name__ == "__main__":
    main()
