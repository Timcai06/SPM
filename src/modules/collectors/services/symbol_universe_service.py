from __future__ import annotations

import csv
from pathlib import Path

import akshare as ak
import psycopg

from modules.runtime.adapters.db import dsn_for


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
