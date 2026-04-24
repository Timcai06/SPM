#!/usr/bin/env python3
"""Historical document backfill collectors."""

from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from modules.collectors.adapters.db_repository import upsert_raw_document_rows
from modules.collectors.domain.history_dates import normalize_date
from modules.collectors.domain.history_rows import dedupe_rows, filter_quality_rows, write_csv
from modules.collectors.domain.source_profiles import history_source_choices, symbol_history_source_choices
from modules.collectors.services.direct_history_collect_service import iter_direct_source_history_batches
from modules.collectors.services.symbol_history_collect_service import collect_with_retry
from modules.collectors.services.symbol_universe_service import resolve_symbols


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = "stock_event_mining"
DEFAULT_OUTPUT = ROOT / "output" / "history"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect historical raw documents.")
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--source", choices=history_source_choices(), default="akshare-news")
    parser.add_argument("--symbol-source", choices=["db", "all-a"], default="db")
    parser.add_argument("--symbol-file", default="", help="Optional CSV/text file with ts_code/code and optional company_name/name columns.")
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--end-date", default=datetime.now().date().isoformat())
    parser.add_argument("--max-symbols", type=int, default=200)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit-per-symbol", type=int, default=20)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--sleep-sec", type=float, default=0.05)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--skip-db-load", action="store_true")
    parser.add_argument("--cninfo-fulltext", action="store_true", help="Download CNInfo PDF attachments and extract text into content.")
    parser.add_argument("--cninfo-fulltext-max-chars", type=int, default=12000)
    parser.add_argument("--db-flush-every", type=int, default=100, help="Incrementally upsert every N collected rows.")
    parser.add_argument("--max-pages", type=int, default=20, help="For direct source history collectors, cap page iterations.")
    parser.add_argument("--page-size", type=int, default=50, help="For direct source history collectors, cap rows per page or total page fetch size.")
    parser.add_argument("--quality-body-only", action="store_true", help="Only keep rows with article-like body content.")
    parser.add_argument("--min-content-length", type=int, default=300, help="Minimum content length when --quality-body-only is enabled.")
    return parser.parse_args(argv)


def is_symbol_history_source(source: str) -> bool:
    return source in symbol_history_source_choices()


def flush_rows_to_db(db: str, pending_rows: list[dict[str, str]]) -> int:
    rows = dedupe_rows(pending_rows)
    return upsert_raw_document_rows(db, rows)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    start_date = normalize_date(args.start_date)
    end_date = normalize_date(args.end_date)
    today = datetime.now().date().isoformat()
    effective_end_date = min(end_date, today)
    if effective_end_date != end_date:
        print(
            f"[history] clamp end-date {end_date} -> {effective_end_date} to avoid future-dated raw rows",
            flush=True,
        )
        end_date = effective_end_date
    if not is_symbol_history_source(args.source):
        started = time.time()
        print(
            f"[history] source={args.source} mode=direct range={start_date}..{end_date} "
            f"max_pages={args.max_pages} page_size={args.page_size} workers={args.workers}",
            flush=True,
        )
        batch_rows = iter_direct_source_history_batches(
            source=args.source,
            start_date=start_date,
            end_date=end_date,
            max_pages=args.max_pages,
            page_size=args.page_size,
            workers=args.workers,
        )
        rows: list[dict[str, str]] = []
        db_flushes = 0
        db_rows_upserted = 0
        for batch_idx, batch in enumerate(batch_rows, start=1):
            if args.quality_body_only:
                batch = filter_quality_rows(batch, min_content_length=args.min_content_length)
            rows.extend(batch)
            if args.skip_db_load:
                print(
                    f"[history] progress batch {batch_idx}/{len(batch_rows)} rows={len(rows)} elapsed={int(time.time() - started)}s",
                    flush=True,
                )
                continue
            if batch:
                flushed = flush_rows_to_db(args.db, batch)
                db_flushes += 1
                db_rows_upserted += flushed
                print(
                    f"[history] db_flush {db_flushes} rows={flushed} cumulative={db_rows_upserted} "
                    f"batch={batch_idx}/{len(batch_rows)} elapsed={int(time.time() - started)}s",
                    flush=True,
                )
        out = (
            Path(args.output_dir).resolve()
            / f"history_{args.source}_{start_date}_{end_date}_pages{args.max_pages}_size{args.page_size}.csv"
        )
        rows = dedupe_rows(rows)
        write_csv(out, rows)
        if args.skip_db_load:
            print(f"[history] db_load=skipped rows={len(rows)} elapsed={int(time.time() - started)}s", flush=True)
        else:
            print(
                f"[history] db_load=done flushes={db_flushes} upserted={db_rows_upserted} rows={len(rows)} elapsed={int(time.time() - started)}s",
                flush=True,
            )
        print(f"[history] wrote {len(rows)} unique rows to {out}", flush=True)
        return

    symbols = resolve_symbols(
        args.db,
        max_symbols=args.max_symbols,
        offset=args.offset,
        symbol_source=args.symbol_source,
        symbol_file=args.symbol_file,
    )
    started = time.time()
    all_rows: list[dict[str, str]] = []
    pending_flush_rows: list[dict[str, str]] = []
    failures: list[tuple[str, str]] = []
    db_flushes = 0
    db_rows_upserted = 0
    print(
        f"[history] source={args.source} symbol_source={args.symbol_source} symbols={len(symbols)} offset={args.offset} "
        f"range={start_date}..{end_date} limit_per_symbol={args.limit_per_symbol} workers={args.workers}",
        flush=True,
    )
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [
            pool.submit(
                collect_with_retry,
                args.source,
                symbol,
                start_date,
                end_date,
                args.limit_per_symbol,
                args.retries,
                args.sleep_sec,
                args.cninfo_fulltext,
                args.cninfo_fulltext_max_chars,
            )
            for symbol in symbols
        ]
        for idx, future in enumerate(as_completed(futures), start=1):
            ts_code, rows, error = future.result()
            if error:
                failures.append((ts_code, error))
            if args.quality_body_only:
                rows = filter_quality_rows(rows, min_content_length=args.min_content_length)
            all_rows.extend(rows)
            if not args.skip_db_load:
                pending_flush_rows.extend(rows)
                if len(pending_flush_rows) >= max(1, args.db_flush_every):
                    flushed = flush_rows_to_db(args.db, pending_flush_rows)
                    db_flushes += 1
                    db_rows_upserted += flushed
                    print(
                        f"[history] db_flush {db_flushes} rows={flushed} cumulative={db_rows_upserted}",
                        flush=True,
                    )
                    pending_flush_rows.clear()
            if idx == 1 or idx % 20 == 0 or idx == len(futures):
                elapsed = int(time.time() - started)
                print(
                    f"[history] progress {idx}/{len(futures)} rows={len(all_rows)} failures={len(failures)} elapsed={elapsed}s",
                    flush=True,
                )

    rows = dedupe_rows(all_rows)
    out = Path(args.output_dir).resolve() / f"history_{args.source}_{start_date}_{end_date}_o{args.offset}_n{args.max_symbols}.csv"
    write_csv(out, rows)
    if not args.skip_db_load:
        if pending_flush_rows:
            flushed = flush_rows_to_db(args.db, pending_flush_rows)
            db_flushes += 1
            db_rows_upserted += flushed
            print(
                f"[history] db_flush {db_flushes} rows={flushed} cumulative={db_rows_upserted}",
                flush=True,
            )
            pending_flush_rows.clear()
    print(f"[history] wrote {len(rows)} unique rows to {out}")
    if args.skip_db_load:
        print(f"[history] db_load=skipped failures={len(failures)}")
    else:
        print(f"[history] db_load=done flushes={db_flushes} upserted={db_rows_upserted} failures={len(failures)}")
    if failures:
        print("[history] first failures: " + "; ".join(f"{code}:{err[:80]}" for code, err in failures[:5]))


if __name__ == "__main__":
    main()
