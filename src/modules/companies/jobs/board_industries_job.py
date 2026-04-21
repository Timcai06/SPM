#!/usr/bin/env python3
"""Backfill company industry_l2 and concept_tags from EastMoney boards."""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path
import sys

import akshare as ak
import psycopg

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.storage.db_guard import dsn_for, write_guard
from modules.companies.domain.company_identity import concept_json, market_suffix


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill company industries from EastMoney board members.")
    parser.add_argument("--db", default="stock_event_mining")
    parser.add_argument("--max-industries", type=int, default=0)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--sleep-sec", type=float, default=0.05)
    parser.add_argument("--progress-every", type=int, default=20)
    parser.add_argument("--lock-timeout-sec", type=int, default=120)
    return parser.parse_args(argv)


def ts_code_from_code(code: str) -> str:
    suffix = market_suffix(code)
    return f"{code}.{suffix}" if suffix else ""


def load_industry_names(offset: int, max_industries: int) -> list[str]:
    df = ak.stock_board_industry_name_em()
    names = [str(value).strip() for value in df["板块名称"].tolist() if str(value).strip()]
    start = max(offset, 0)
    end = None if max_industries <= 0 else start + max_industries
    return names[start:end]


def collect_members(industry_names: list[str], sleep_sec: float, progress_every: int) -> dict[str, list[str]]:
    by_code: dict[str, list[str]] = defaultdict(list)
    started = time.time()
    for idx, industry in enumerate(industry_names, start=1):
        try:
            df = ak.stock_board_industry_cons_em(symbol=industry)
        except Exception:
            time.sleep(sleep_sec)
            continue
        if df is not None and not df.empty and "代码" in df.columns:
            for _, row in df.iterrows():
                code = str(row.get("代码") or "").strip()
                ts_code = ts_code_from_code(code)
                if ts_code and industry not in by_code[ts_code]:
                    by_code[ts_code].append(industry)
        if progress_every > 0 and (idx == 1 or idx % progress_every == 0 or idx == len(industry_names)):
            elapsed = int(time.time() - started)
            print(f"[industry-backfill] progress {idx}/{len(industry_names)}, matched_companies={len(by_code)}, elapsed={elapsed}s", flush=True)
        time.sleep(sleep_sec)
    return by_code


def update_companies(db_name: str, by_code: dict[str, list[str]], lock_timeout_sec: int) -> int:
    rows = []
    for ts_code, industries in by_code.items():
        if industries:
            rows.append(
                {
                    "ts_code": ts_code,
                    "industry_l2": industries[0],
                    "concept_tags": concept_json(industries[:8]),
                }
            )
    if not rows:
        return 0
    with write_guard(db_name=db_name, required_tables=["companies"], lock_timeout_sec=lock_timeout_sec):
        with psycopg.connect(dsn_for(db_name)) as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    UPDATE companies
                    SET industry_l2 = %(industry_l2)s,
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
    industry_names = load_industry_names(args.offset, args.max_industries)
    print(f"[industry-backfill] industries={len(industry_names)} offset={args.offset}", flush=True)
    by_code = collect_members(industry_names, args.sleep_sec, args.progress_every)
    updated = update_companies(args.db, by_code, args.lock_timeout_sec)
    print(f"[industry-backfill] updated_companies={updated}, matched_companies={len(by_code)}")


if __name__ == "__main__":
    main()
