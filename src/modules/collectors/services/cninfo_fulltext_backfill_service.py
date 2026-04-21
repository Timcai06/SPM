#!/usr/bin/env python3
"""Backfill CNInfo fulltext into existing raw_documents rows by detail URL."""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from modules.collectors.adapters import cninfo
from modules.collectors.adapters.db_repository import (
    load_cninfo_fulltext_backfill_candidates,
    update_raw_document_contents,
)


DEFAULT_DB = "stock_event_mining"
DEFAULT_SOURCE = "巨潮资讯网/历史公告"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill CNInfo PDF fulltext into existing raw_documents rows.")
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("--start-date", default="2025-01-01")
    parser.add_argument("--end-date", default="2026-01-01")
    parser.add_argument("--max-rows", type=int, default=5000)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--id-min", type=int, default=0)
    parser.add_argument("--id-max", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=0)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--sleep-sec", type=float, default=0.02)
    parser.add_argument("--db-flush-every", type=int, default=100)
    parser.add_argument("--fulltext-max-chars", type=int, default=12000)
    parser.add_argument("--skip-db-load", action="store_true")
    return parser.parse_args(argv)


def normalize_date(value: str) -> str:
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text[:19], fmt).date().isoformat()
        except Exception:
            continue
    return text[:10]


def load_candidates(
    db_name: str,
    source: str,
    start_date: str,
    end_date: str,
    max_rows: int,
    offset: int,
    id_min: int,
    id_max: int,
    shard_count: int,
    shard_index: int,
) -> list[dict[str, Any]]:
    return load_cninfo_fulltext_backfill_candidates(
        db_name=db_name,
        source=source,
        start_date=start_date,
        end_date=end_date,
        max_rows=max_rows,
        offset=offset,
        id_min=id_min,
        id_max=id_max,
        shard_count=shard_count,
        shard_index=shard_index,
    )


def fetch_with_retry(row: dict[str, Any], retries: int, sleep_sec: float, max_chars: int) -> tuple[int, str, str]:
    row_id = int(row["id"])
    title = str(row["title"] or "")
    url = str(row["url"] or "")
    last_error = ""
    for attempt in range(retries + 1):
        try:
            content = cninfo.extract_fulltext_from_detail_url(url, max_chars=max_chars)
            if content and content.strip() and content.strip() != title.strip():
                return row_id, content, ""
            return row_id, "", "empty_fulltext"
        except Exception as exc:
            last_error = f"{exc.__class__.__name__}: {exc}"
            if attempt < retries:
                time.sleep(sleep_sec * (attempt + 1))
    return row_id, "", last_error


def make_update(row: dict[str, Any], content: str) -> dict[str, str]:
    title = str(row["title"] or "").strip()
    normalized = " ".join(str(content or "").split()).strip()
    return {
        "id": str(row["id"]),
        "content": normalized,
        "content_hash": hashlib.md5(f"{title}::{normalized}".encode("utf-8")).hexdigest(),
    }


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    start_date = normalize_date(args.start_date)
    end_date = normalize_date(args.end_date)
    candidates = load_candidates(
        args.db,
        source=args.source,
        start_date=start_date,
        end_date=end_date,
        max_rows=args.max_rows,
        offset=args.offset,
        id_min=args.id_min,
        id_max=args.id_max,
        shard_count=args.shard_count,
        shard_index=args.shard_index,
    )
    started = time.time()
    print(
        f"[cninfo-backfill] source={args.source} rows={len(candidates)} offset={args.offset} "
        f"id_range={args.id_min or '-'}..{args.id_max or '-'} "
        f"shard={args.shard_index}/{args.shard_count or '-'} "
        f"range={start_date}..{end_date} workers={args.workers}",
        flush=True,
    )
    if not candidates:
        print("[cninfo-backfill] nothing_to_do", flush=True)
        return

    by_id = {int(row["id"]): row for row in candidates}
    failures: list[tuple[int, str]] = []
    pending_updates: list[dict[str, str]] = []
    updated_rows = 0
    flushes = 0
    success_rows = 0

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [
            pool.submit(fetch_with_retry, row, args.retries, args.sleep_sec, args.fulltext_max_chars)
            for row in candidates
        ]
        for idx, future in enumerate(as_completed(futures), start=1):
            row_id, content, error = future.result()
            if error:
                failures.append((row_id, error))
            elif content:
                success_rows += 1
                pending_updates.append(make_update(by_id[row_id], content))
            if not args.skip_db_load and len(pending_updates) >= max(1, args.db_flush_every):
                flushed = update_raw_document_contents(args.db, pending_updates)
                flushes += 1
                updated_rows += flushed
                print(f"[cninfo-backfill] db_flush {flushes} rows={flushed} cumulative={updated_rows}", flush=True)
                pending_updates.clear()
            if idx == 1 or idx % 50 == 0 or idx == len(futures):
                elapsed = int(time.time() - started)
                print(
                    f"[cninfo-backfill] progress {idx}/{len(futures)} success={success_rows} "
                    f"updated={updated_rows} failures={len(failures)} elapsed={elapsed}s",
                    flush=True,
                )

    if not args.skip_db_load and pending_updates:
        flushed = update_raw_document_contents(args.db, pending_updates)
        flushes += 1
        updated_rows += flushed
        print(f"[cninfo-backfill] db_flush {flushes} rows={flushed} cumulative={updated_rows}", flush=True)

    if args.skip_db_load:
        print(f"[cninfo-backfill] db_load=skipped success={success_rows} failures={len(failures)}", flush=True)
    else:
        print(
            f"[cninfo-backfill] db_load=done flushes={flushes} updated={updated_rows} "
            f"success={success_rows} failures={len(failures)}",
            flush=True,
        )
    if failures:
        print(
            "[cninfo-backfill] first failures: "
            + "; ".join(f"{row_id}:{err[:80]}" for row_id, err in failures[:5]),
            flush=True,
        )


if __name__ == "__main__":
    main()
