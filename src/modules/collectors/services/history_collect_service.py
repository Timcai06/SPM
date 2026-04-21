#!/usr/bin/env python3
"""Historical document backfill collectors for Task 1."""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

import akshare as ak
import psycopg

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from modules.collectors.adapters import cninfo
from modules.collectors.adapters.db_repository import upsert_raw_document_rows
from capabilities.storage.db_guard import dsn_for


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = "stock_event_mining"
DEFAULT_OUTPUT = ROOT / "output" / "history"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect historical raw documents for Task 1.")
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--source", choices=["akshare-news", "cninfo-disclosure"], default="akshare-news")
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
    return parser.parse_args(argv)


def normalize_date(value: str) -> str:
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text[:19], fmt).date().isoformat()
        except Exception:
            continue
    return text[:10]


def normalize_datetime(value: Any) -> str:
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text[:19], fmt).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            continue
    return "1970-01-01 00:00:00"


def get_symbols_from_db(db_name: str, max_symbols: int, offset: int) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    with psycopg.connect(dsn_for(db_name)) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ts_code, company_name
                FROM companies
                WHERE is_active = TRUE
                  AND ts_code IS NOT NULL
                  AND ts_code <> ''
                ORDER BY ts_code
                OFFSET %s
                LIMIT %s
                """,
                (max(offset, 0), max_symbols),
            )
            rows = [(str(ts_code), str(name or "")) for ts_code, name in cur.fetchall()]
    return rows


def get_symbols_from_akshare(max_symbols: int, offset: int) -> list[tuple[str, str]]:
    try:
        df = ak.stock_zh_a_spot_em()
        code_col = "代码"
        name_col = "名称"
    except Exception:
        df = ak.stock_info_a_code_name()
        code_col = "code" if "code" in df.columns else "代码"
        name_col = "name" if "name" in df.columns else "名称"
    output: list[tuple[str, str]] = []
    for _, row in df.iterrows():
        code = str(row.get(code_col) or "").strip()
        name = str(row.get(name_col) or "").strip()
        if len(code) != 6 or not code.isdigit():
            continue
        if code.startswith(("6", "9", "5")):
            ts_code = f"{code}.SH"
        elif code.startswith(("0", "2", "3")):
            ts_code = f"{code}.SZ"
        elif code.startswith(("4", "8")):
            ts_code = f"{code}.BJ"
        else:
            continue
        output.append((ts_code, name))
    return output[max(offset, 0) : max(offset, 0) + max_symbols]


def normalize_symbol_code(value: str) -> str:
    text = str(value or "").strip().upper()
    if not text:
        return ""
    if "." in text:
        code, suffix = text.split(".", 1)
        if suffix in {"SZ", "SH", "BJ"}:
            return f"{code}.{suffix}"
    code = text
    if len(code) != 6 or not code.isdigit():
        return ""
    if code.startswith(("6", "9", "5")):
        return f"{code}.SH"
    if code.startswith(("0", "2", "3")):
        return f"{code}.SZ"
    if code.startswith(("4", "8")):
        return f"{code}.BJ"
    return ""


def get_symbols_from_file(path: Path, max_symbols: int, offset: int) -> list[tuple[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"symbol file not found: {path}")
    rows: list[tuple[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(2048)
        f.seek(0)
        if "," in sample:
            reader = csv.DictReader(f)
            for row in reader:
                raw_code = row.get("ts_code") or row.get("code") or row.get("symbol") or row.get("股票代码") or row.get("代码")
                ts_code = normalize_symbol_code(str(raw_code or ""))
                name = str(row.get("company_name") or row.get("name") or row.get("股票简称") or row.get("名称") or "").strip()
                if ts_code:
                    rows.append((ts_code, name))
        else:
            for line in f:
                parts = [part.strip() for part in line.strip().split() if part.strip()]
                if not parts:
                    continue
                ts_code = normalize_symbol_code(parts[0])
                name = parts[1] if len(parts) > 1 else ""
                if ts_code:
                    rows.append((ts_code, name))
    seen: set[str] = set()
    deduped: list[tuple[str, str]] = []
    for ts_code, name in rows:
        if ts_code in seen:
            continue
        seen.add(ts_code)
        deduped.append((ts_code, name))
    return deduped[max(offset, 0) : max(offset, 0) + max_symbols]


def resolve_symbols(db_name: str, max_symbols: int, offset: int, symbol_source: str, symbol_file: str) -> list[tuple[str, str]]:
    if symbol_file.strip():
        return get_symbols_from_file(Path(symbol_file).expanduser().resolve(), max_symbols=max_symbols, offset=offset)
    if symbol_source == "all-a":
        return get_symbols_from_akshare(max_symbols=max_symbols, offset=offset)
    return get_symbols_from_db(db_name, max_symbols=max_symbols, offset=offset)


def in_date_range(value: str, start_date: str, end_date: str) -> bool:
    date_text = normalize_date(value)
    if not date_text:
        return False
    return start_date <= date_text <= end_date


def collect_akshare_news_for_symbol(
    ts_code: str,
    company_name: str,
    start_date: str,
    end_date: str,
    limit_per_symbol: int,
) -> list[dict[str, str]]:
    symbol = ts_code.split(".", 1)[0]
    df = ak.stock_news_em(symbol=symbol)
    rows: list[dict[str, str]] = []
    if df is None or df.empty:
        return rows
    for _, row in df.iterrows():
        publish_time = str(row.get("发布时间") or "")
        if not in_date_range(publish_time, start_date=start_date, end_date=end_date):
            continue
        title = str(row.get("新闻标题") or "").strip()
        content = str(row.get("新闻内容") or "").strip() or title
        url = str(row.get("新闻链接") or "").strip()
        source_name = str(row.get("文章来源") or "EastMoney").strip()
        if not title or not url:
            continue
        rows.append(
            {
                "source": f"AKShare/EastMoney/{source_name}",
                "title": title,
                "content": content,
                "publish_time": normalize_datetime(publish_time),
                "url": url,
                "symbol_or_subject": ts_code,
            }
        )
        if len(rows) >= limit_per_symbol:
            break
    return rows


def collect_cninfo_for_symbol(
    ts_code: str,
    company_name: str,
    start_date: str,
    end_date: str,
    limit_per_symbol: int,
    include_fulltext: bool = False,
    fulltext_max_chars: int = 12000,
) -> list[dict[str, str]]:
    return cninfo.collect_history(
        ts_code=ts_code,
        company_name=company_name,
        start_date=start_date,
        end_date=end_date,
        limit_per_symbol=limit_per_symbol,
        include_fulltext=include_fulltext,
        fulltext_max_chars=fulltext_max_chars,
    )


def collect_with_retry(
    source: str,
    symbol: tuple[str, str],
    start_date: str,
    end_date: str,
    limit_per_symbol: int,
    retries: int,
    sleep_sec: float,
    cninfo_fulltext: bool = False,
    cninfo_fulltext_max_chars: int = 12000,
) -> tuple[str, list[dict[str, str]], str]:
    ts_code, company_name = symbol
    last_error = ""
    for attempt in range(retries + 1):
        try:
            if source == "akshare-news":
                rows = collect_akshare_news_for_symbol(ts_code, company_name, start_date, end_date, limit_per_symbol)
            else:
                rows = collect_cninfo_for_symbol(
                    ts_code,
                    company_name,
                    start_date,
                    end_date,
                    limit_per_symbol,
                    include_fulltext=cninfo_fulltext,
                    fulltext_max_chars=cninfo_fulltext_max_chars,
                )
            return ts_code, rows, ""
        except Exception as exc:
            last_error = f"{exc.__class__.__name__}: {exc}"
            if attempt < retries:
                time.sleep(sleep_sec * (attempt + 1))
    return ts_code, [], last_error


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["source", "title", "content", "publish_time", "url", "symbol_or_subject"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def dedupe_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    unique: dict[str, dict[str, str]] = {}
    for row in rows:
        url = row.get("url") or ""
        if not url:
            digest = hashlib.md5(f"{row.get('title')}::{row.get('publish_time')}".encode("utf-8")).hexdigest()
            url = f"local://history/{row.get('source', 'unknown')}/{digest}"
            row["url"] = url
        unique[url] = row
    return sorted(unique.values(), key=lambda item: (item["publish_time"], item["url"]))


def flush_rows_to_db(db: str, pending_rows: list[dict[str, str]]) -> int:
    rows = dedupe_rows(pending_rows)
    return upsert_raw_document_rows(db, rows)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    start_date = normalize_date(args.start_date)
    end_date = normalize_date(args.end_date)
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
