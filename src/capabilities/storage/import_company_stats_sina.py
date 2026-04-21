#!/usr/bin/env python3
"""Fetch company daily stats from Sina K-line API and write normalized CSV."""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import psycopg

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.storage.db_guard import dsn_for
from modules.analysis.services.market_data_service import fetch_sina_kline, ts_to_sina_symbol


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "output" / "seeds" / "company_stats.csv"
DEFAULT_QUOTES_OUTPUT = ROOT / "output" / "seeds" / "stock_daily_quotes.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import company daily stats from Sina K-line API.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--quotes-output", default=str(DEFAULT_QUOTES_OUTPUT))
    parser.add_argument("--days", type=int, default=120, help="Reserved for compatibility; rows are limited by max-rows.")
    parser.add_argument("--max-symbols", type=int, default=300, help="Max stock symbols to fetch.")
    parser.add_argument("--max-rows", type=int, default=1200, help="Max K-line rows fetched per symbol.")
    parser.add_argument("--sleep-sec", type=float, default=0.05, help="Sleep between symbol requests.")
    parser.add_argument("--progress-every", type=int, default=20, help="Print progress every N symbols.")
    parser.add_argument("--timeout-sec", type=float, default=12.0, help="Timeout per HTTP request.")
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

def get_ts_codes_from_db(db_name: str, max_symbols: int) -> list[str]:
    rows: list[str] = []
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
                (max_symbols,),
            )
            for (ts_code,) in cur.fetchall():
                text = str(ts_code or "").strip().upper()
                if text:
                    rows.append(text)
    return rows

def build_rows(
    db_name: str,
    max_symbols: int,
    max_rows: int,
    timeout_sec: float,
    sleep_sec: float,
    progress_every: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    ts_codes = get_ts_codes_from_db(db_name=db_name, max_symbols=max_symbols)
    total = len(ts_codes)
    out_rows: list[dict[str, str]] = []
    quote_rows: list[dict[str, str]] = []
    fail_count = 0
    success_count = 0
    started_at = time.time()

    print(
        f"[sina-stats] start symbols={total}, max_rows={max_rows}, timeout_sec={timeout_sec}, "
        f"sleep_sec={sleep_sec}, progress_every={progress_every}",
        flush=True,
    )

    for idx, ts_code in enumerate(ts_codes, start=1):
        sina_symbol = ts_to_sina_symbol(ts_code)
        before_rows = len(out_rows)
        if not sina_symbol:
            fail_count += 1
            if progress_every > 0 and (idx == 1 or idx % progress_every == 0):
                elapsed = int(time.time() - started_at)
                print(
                    f"[sina-stats] progress {idx}/{total}, current={ts_code}, rows={len(out_rows)}, "
                    f"added=0, success={success_count}, fails={fail_count}, elapsed={elapsed}s, reason=bad_symbol",
                    flush=True,
                )
            continue

        try:
            kline = fetch_sina_kline(sina_symbol, max_rows=max_rows, timeout_seconds=timeout_sec)
        except Exception as exc:
            fail_count += 1
            if progress_every > 0 and (idx == 1 or idx % progress_every == 0):
                elapsed = int(time.time() - started_at)
                print(
                    f"[sina-stats] progress {idx}/{total}, current={ts_code}/{sina_symbol}, rows={len(out_rows)}, "
                    f"added=0, success={success_count}, fails={fail_count}, elapsed={elapsed}s, "
                    f"reason={type(exc).__name__}",
                    flush=True,
                )
            time.sleep(sleep_sec)
            continue

        parsed = []
        for row in kline:
            trade_date = str(row.get("day", "")).strip().split(" ", 1)[0]
            close = safe_float(row.get("close"))
            volume = safe_float(row.get("volume"))
            if not trade_date or close is None:
                continue
            open_price = safe_float(row.get("open"))
            high_price = safe_float(row.get("high"))
            low_price = safe_float(row.get("low"))
            parsed.append(
                {
                    "trade_date": trade_date,
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close,
                    "volume": volume,
                }
            )

        parsed.sort(key=lambda item: item["trade_date"])
        if len(parsed) < 2:
            if progress_every > 0 and (idx == 1 or idx % progress_every == 0):
                elapsed = int(time.time() - started_at)
                print(
                    f"[sina-stats] progress {idx}/{total}, current={ts_code}/{sina_symbol}, rows={len(out_rows)}, "
                    f"added=0, success={success_count}, fails={fail_count}, elapsed={elapsed}s, reason=short_series",
                    flush=True,
                )
            time.sleep(sleep_sec)
            continue

        returns: list[Optional[float]] = []
        prev_close: Optional[float] = None
        for item in parsed:
            daily_ret = None
            if prev_close and prev_close != 0:
                daily_ret = (item["close"] - prev_close) / prev_close
            prev_close = item["close"]
            returns.append(daily_ret)

        for j, item in enumerate(parsed):
            hist_returns_5 = [x for x in returns[max(0, j - 4) : j + 1] if x is not None]
            hist_returns = [x for x in returns[max(0, j - 19) : j + 1] if x is not None]
            hist_returns_60 = [x for x in returns[max(0, j - 59) : j + 1] if x is not None]
            future_1 = compound([x for x in returns[j + 1 : j + 2] if x is not None])
            future_3 = compound([x for x in returns[j + 1 : j + 4] if x is not None])
            future_5 = compound([x for x in returns[j + 1 : j + 6] if x is not None])
            trailing_5 = compound(hist_returns_5[-5:]) if hist_returns_5 else None
            trailing_20 = compound(hist_returns[-20:]) if hist_returns else None
            trailing_60 = compound(hist_returns_60[-60:]) if hist_returns_60 else None
            vol_5 = statistics.stdev(hist_returns_5[-5:]) if len(hist_returns_5[-5:]) >= 2 else None
            vol_20 = statistics.stdev(hist_returns[-20:]) if len(hist_returns[-20:]) >= 2 else None
            vol_60 = statistics.stdev(hist_returns_60[-60:]) if len(hist_returns_60[-60:]) >= 2 else None
            up_days_20 = len([x for x in hist_returns[-20:] if x is not None and x > 0]) if hist_returns else None

            volume_ratio = None
            cur_volume = item["volume"]
            hist_vols = [x["volume"] for x in parsed[max(0, j - 4) : j] if x["volume"] is not None]
            if cur_volume is not None and hist_vols:
                avg_vol = sum(hist_vols) / len(hist_vols)
                if avg_vol:
                    volume_ratio = cur_volume / avg_vol

            daily_ret = returns[j]
            prev_close = parsed[j - 1]["close"] if j > 0 else None
            pct_chg = daily_ret
            open_val = item.get("open") if item.get("open") is not None else prev_close
            quote_rows.append(
                {
                    "ts_code": ts_code,
                    "trade_date": item["trade_date"],
                    "open": "" if open_val is None else f"{open_val:.4f}",
                    "high": "" if item.get("high") is None else f"{item['high']:.4f}",
                    "low": "" if item.get("low") is None else f"{item['low']:.4f}",
                    "close": f"{item['close']:.4f}",
                    "pre_close": "" if prev_close is None else f"{prev_close:.4f}",
                    "pct_chg": "" if pct_chg is None else f"{pct_chg * 100:.4f}",
                    "volume": "" if item["volume"] is None else f"{item['volume']:.4f}",
                    "amount": "",
                    "turnover_rate": "",
                    "adj_factor": "",
                    "is_suspended": "false",
                    "is_st": "false",
                    "is_limit_up": "false",
                    "is_limit_down": "false",
                    "data_source": "sina",
                }
            )
            out_rows.append(
                {
                    "ts_code": ts_code,
                    "trade_date": item["trade_date"],
                    "total_mv": "",
                    "circ_mv": "",
                    "pe_ttm": "",
                    "pb": "",
                    "turnover_rate": "",
                    "volume_ratio": "" if volume_ratio is None else f"{volume_ratio:.6f}",
                    "daily_return": "" if daily_ret is None else f"{daily_ret:.6f}",
                    "trailing_return_5d": "" if trailing_5 is None else f"{trailing_5:.6f}",
                    "trailing_return_20d": "" if trailing_20 is None else f"{trailing_20:.6f}",
                    "trailing_return_60d": "" if trailing_60 is None else f"{trailing_60:.6f}",
                    "volatility_5d": "" if vol_5 is None else f"{vol_5:.6f}",
                    "volatility_20d": "" if vol_20 is None else f"{vol_20:.6f}",
                    "volatility_60d": "" if vol_60 is None else f"{vol_60:.6f}",
                    "up_days_20d": "" if up_days_20 is None else str(up_days_20),
                    "forward_return_1d": "" if future_1 is None else f"{future_1:.6f}",
                    "forward_return_3d": "" if future_3 is None else f"{future_3:.6f}",
                    "forward_return_5d": "" if future_5 is None else f"{future_5:.6f}",
                    "data_source": "sina",
                }
            )
        success_count += 1
        if progress_every > 0 and (idx == 1 or idx % progress_every == 0):
            elapsed = int(time.time() - started_at)
            print(
                f"[sina-stats] progress {idx}/{total}, current={ts_code}/{sina_symbol}, rows={len(out_rows)}, "
                f"added={len(out_rows) - before_rows}, success={success_count}, fails={fail_count}, elapsed={elapsed}s",
                flush=True,
            )
        time.sleep(sleep_sec)

    out_rows.sort(key=lambda item: (item["trade_date"], item["ts_code"]))
    elapsed = int(time.time() - started_at)
    print(
        f"[sina-stats] done symbols={total}, success={success_count}, fails={fail_count}, rows={len(out_rows)}, "
        f"elapsed={elapsed}s",
        flush=True,
    )
    return out_rows, quote_rows


def write_stats_csv(path: Path, rows: list[dict[str, str]]) -> None:
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
        "trailing_return_5d",
        "trailing_return_20d",
        "trailing_return_60d",
        "volatility_5d",
        "volatility_20d",
        "volatility_60d",
        "up_days_20d",
        "forward_return_1d",
        "forward_return_3d",
        "forward_return_5d",
        "data_source",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_quotes_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "ts_code",
        "trade_date",
        "open",
        "high",
        "low",
        "close",
        "pre_close",
        "pct_chg",
        "volume",
        "amount",
        "turnover_rate",
        "adj_factor",
        "is_suspended",
        "is_st",
        "is_limit_up",
        "is_limit_down",
        "data_source",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    rows, quote_rows = build_rows(
        db_name=args.db,
        max_symbols=args.max_symbols,
        max_rows=args.max_rows,
        timeout_sec=args.timeout_sec,
        sleep_sec=args.sleep_sec,
        progress_every=args.progress_every,
    )
    output_path = Path(args.output).resolve()
    quotes_output_path = Path(args.quotes_output).resolve()
    write_stats_csv(output_path, rows)
    write_quotes_csv(quotes_output_path, quote_rows)
    print(f"Wrote {len(rows)} company stat rows to {output_path}")
    print(f"Wrote {len(quote_rows)} stock quote rows to {quotes_output_path}")
    print("Source: sina")


if __name__ == "__main__":
    main()
