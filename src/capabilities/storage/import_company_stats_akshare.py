#!/usr/bin/env python3
"""Fetch company daily stats from AKShare and write normalized CSV."""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import akshare as ak
import psycopg

from capabilities.storage.db_guard import dsn_for


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "output" / "seeds" / "company_stats.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import company daily stats from AKShare.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--days", type=int, default=30, help="Recent trading-day span target.")
    parser.add_argument("--max-symbols", type=int, default=300, help="Max stock symbols to fetch.")
    parser.add_argument("--sleep-sec", type=float, default=0.05, help="Sleep between symbol requests.")
    parser.add_argument("--progress-every", type=int, default=20, help="Print progress every N symbols.")
    parser.add_argument("--db", default="stock_event_mining", help="Database used to load symbols from companies table.")
    return parser.parse_args()


def safe_float(value) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def compound(values: list[float]) -> Optional[float]:
    if not values:
        return None
    result = 1.0
    for v in values:
        result *= 1.0 + v
    return result - 1.0


def symbol_to_ts_code(symbol: str) -> Optional[str]:
    code = symbol.strip()
    if not (len(code) == 6 and code.isdigit()):
        return None
    if code.startswith(("6", "9", "5")):
        return f"{code}.SH"
    if code.startswith(("0", "2", "3")):
        return f"{code}.SZ"
    if code.startswith(("4", "8")):
        return f"{code}.BJ"
    return None


def pick_column(df, candidates: list[str]) -> Optional[str]:
    for name in candidates:
        if name in df.columns:
            return name
    return None


def get_symbols_from_db(db_name: str, max_symbols: int) -> list[str]:
    symbols: list[str] = []
    try:
        with psycopg.connect(dsn_for(db_name)) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT ts_code
                    FROM companies
                    WHERE ts_code IS NOT NULL AND ts_code <> ''
                    ORDER BY ts_code
                    LIMIT %s
                    """,
                    (max_symbols * 2,),
                )
                for (ts_code,) in cur.fetchall():
                    code = str(ts_code).split(".", 1)[0].strip()
                    if len(code) == 6 and code.isdigit():
                        symbols.append(code)
    except Exception:
        return []
    return sorted(set(symbols))[:max_symbols]


def get_symbols_from_spot(max_symbols: int) -> list[str]:
    spot = ak.stock_zh_a_spot_em()
    code_col = pick_column(spot, ["代码", "symbol", "代码 "])
    if not code_col:
        return []
    symbols = []
    for value in spot[code_col].tolist():
        code = str(value).strip()
        if len(code) == 6 and code.isdigit():
            symbols.append(code)
    symbols = sorted(set(symbols))
    return symbols[:max_symbols]


def fetch_hist(symbol: str, start_date: str, end_date: str):
    return ak.stock_zh_a_hist(
        symbol=symbol,
        period="daily",
        start_date=start_date,
        end_date=end_date,
        adjust="",
    )


def build_rows(days: int, max_symbols: int, sleep_sec: float, progress_every: int, db_name: str) -> list[dict[str, str]]:
    target_start = (datetime.now().date() - timedelta(days=days * 3)).strftime("%Y%m%d")
    target_end = datetime.now().date().strftime("%Y%m%d")
    symbols = get_symbols_from_db(db_name=db_name, max_symbols=max_symbols)
    if symbols:
        print(f"[akshare-stats] loaded {len(symbols)} symbols from database companies")
    else:
        print("[akshare-stats] companies table unavailable/empty, fallback to AKShare spot symbols")
        symbols = get_symbols_from_spot(max_symbols=max_symbols)
    total_symbols = len(symbols)
    rows: list[dict[str, str]] = []
    fail_count = 0
    for idx, symbol in enumerate(symbols, start=1):
        if progress_every > 0 and (idx == 1 or idx % progress_every == 0):
            print(f"[akshare-stats] progress {idx}/{total_symbols}, rows={len(rows)}, fails={fail_count}")
        ts_code = symbol_to_ts_code(symbol)
        if not ts_code:
            continue
        try:
            hist = fetch_hist(symbol=symbol, start_date=target_start, end_date=target_end)
        except Exception:
            fail_count += 1
            time.sleep(sleep_sec)
            continue
        if hist is None or hist.empty:
            time.sleep(sleep_sec)
            continue

        date_col = pick_column(hist, ["日期", "date"])
        ret_col = pick_column(hist, ["涨跌幅", "pct_chg"])
        turnover_col = pick_column(hist, ["换手率", "turnover_rate"])
        volume_col = pick_column(hist, ["成交量", "volume"])
        if not date_col:
            fail_count += 1
            time.sleep(sleep_sec)
            continue

        parsed = []
        for _, row in hist.iterrows():
            date_text = str(row.get(date_col, "")).strip()
            if not date_text:
                continue
            try:
                trade_date = datetime.strptime(date_text, "%Y-%m-%d").strftime("%Y-%m-%d")
            except Exception:
                try:
                    trade_date = datetime.strptime(date_text, "%Y%m%d").strftime("%Y-%m-%d")
                except Exception:
                    continue
            daily_ret = None
            if ret_col:
                pct = safe_float(row.get(ret_col))
                if pct is not None:
                    daily_ret = pct / 100.0
            turnover_rate = safe_float(row.get(turnover_col)) if turnover_col else None
            volume = safe_float(row.get(volume_col)) if volume_col else None
            parsed.append(
                {
                    "trade_date": trade_date,
                    "daily_return": daily_ret,
                    "turnover_rate": turnover_rate,
                    "volume": volume,
                }
            )

        parsed.sort(key=lambda item: item["trade_date"])
        if len(parsed) < 2:
            time.sleep(sleep_sec)
            continue

        volumes = [item["volume"] for item in parsed]
        for j, item in enumerate(parsed):
            hist_returns = [x["daily_return"] for x in parsed[max(0, j - 19) : j + 1] if x["daily_return"] is not None]
            future_1 = compound([x["daily_return"] for x in parsed[j + 1 : j + 2] if x["daily_return"] is not None])
            future_3 = compound([x["daily_return"] for x in parsed[j + 1 : j + 4] if x["daily_return"] is not None])
            future_5 = compound([x["daily_return"] for x in parsed[j + 1 : j + 6] if x["daily_return"] is not None])
            trailing_20 = compound(hist_returns[-20:]) if hist_returns else None
            vol_20 = statistics.stdev(hist_returns[-20:]) if len(hist_returns[-20:]) >= 2 else None

            volume_ratio = None
            cur_volume = volumes[j]
            hist_vols = [v for v in volumes[max(0, j - 4) : j] if v is not None]
            if cur_volume is not None and hist_vols:
                avg_vol = sum(hist_vols) / len(hist_vols)
                if avg_vol:
                    volume_ratio = cur_volume / avg_vol

            rows.append(
                {
                    "ts_code": ts_code,
                    "trade_date": item["trade_date"],
                    "total_mv": "",
                    "circ_mv": "",
                    "pe_ttm": "",
                    "pb": "",
                    "turnover_rate": "" if item["turnover_rate"] is None else f"{item['turnover_rate']:.4f}",
                    "volume_ratio": "" if volume_ratio is None else f"{volume_ratio:.4f}",
                    "daily_return": "" if item["daily_return"] is None else f"{item['daily_return']:.6f}",
                    "trailing_return_20d": "" if trailing_20 is None else f"{trailing_20:.6f}",
                    "volatility_20d": "" if vol_20 is None else f"{vol_20:.6f}",
                    "forward_return_1d": "" if future_1 is None else f"{future_1:.6f}",
                    "forward_return_3d": "" if future_3 is None else f"{future_3:.6f}",
                    "forward_return_5d": "" if future_5 is None else f"{future_5:.6f}",
                    "data_source": "akshare",
                }
            )
        time.sleep(sleep_sec)
    rows.sort(key=lambda item: (item["trade_date"], item["ts_code"]))
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "ts_code",
        "trade_date",
        "total_mv",
        "circ_mv",
        "pe_ttm",
        "pb",
        "turnover_rate",
        "volume_ratio",
        "daily_return",
        "trailing_return_20d",
        "volatility_20d",
        "forward_return_1d",
        "forward_return_3d",
        "forward_return_5d",
        "data_source",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    rows = build_rows(
        days=args.days,
        max_symbols=args.max_symbols,
        sleep_sec=args.sleep_sec,
        progress_every=args.progress_every,
        db_name=args.db,
    )
    output_path = Path(args.output).resolve()
    write_csv(output_path, rows)
    print(f"Wrote {len(rows)} company stat rows to {output_path}")
    print("Source: akshare")


if __name__ == "__main__":
    main()
