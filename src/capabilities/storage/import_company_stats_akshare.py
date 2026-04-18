#!/usr/bin/env python3
"""Fetch company daily stats from AKShare and write normalized CSV."""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import akshare as ak
import psycopg

from capabilities.storage.db_guard import dsn_for


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "output" / "seeds" / "company_stats.csv"
DEFAULT_QUOTES_OUTPUT = ROOT / "output" / "seeds" / "stock_daily_quotes.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import company daily stats from AKShare.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--quotes-output", default=str(DEFAULT_QUOTES_OUTPUT))
    parser.add_argument("--days", type=int, default=30, help="Recent trading-day span target.")
    parser.add_argument("--max-symbols", type=int, default=300, help="Max stock symbols to fetch.")
    parser.add_argument("--offset", type=int, default=0, help="Offset into the sorted company symbol list.")
    parser.add_argument("--sleep-sec", type=float, default=0.05, help="Sleep between symbol requests.")
    parser.add_argument("--progress-every", type=int, default=20, help="Print progress every N symbols.")
    parser.add_argument("--timeout-sec", type=float, default=12.0, help="Timeout for each symbol request.")
    parser.add_argument("--retries", type=int, default=2, help="Retries per symbol on transient failures.")
    parser.add_argument("--failure-backoff-sec", type=float, default=0.8, help="Base backoff seconds after a failed symbol fetch.")
    parser.add_argument("--resume-existing", action="store_true", help="Skip ts_codes that already exist in output/quotes-output.")
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


def board_limit_pct(ts_code: str) -> float:
    text = str(ts_code or "").strip().upper()
    if text.endswith(".BJ"):
        return 0.30
    code = text.split(".", 1)[0]
    if code.startswith(("300", "301", "688")):
        return 0.20
    return 0.10


def is_limit_up(ts_code: str, pct_chg: Optional[float]) -> bool:
    if pct_chg is None:
        return False
    return pct_chg >= board_limit_pct(ts_code) * 100.0 - 0.3


def is_limit_down(ts_code: str, pct_chg: Optional[float]) -> bool:
    if pct_chg is None:
        return False
    return pct_chg <= -(board_limit_pct(ts_code) * 100.0 - 0.3)


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


def _call_with_timeout(callable_obj, timeout_seconds: float):
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(callable_obj)
        return future.result(timeout=timeout_seconds)


def fetch_hist(symbol: str, start_date: str, end_date: str, timeout_sec: float):
    return _call_with_timeout(
        lambda: ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",
        ),
        timeout_seconds=timeout_sec,
    )


def read_existing_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def existing_ts_codes(stats_path: Path, quotes_path: Path) -> set[str]:
    codes: set[str] = set()
    for path in (stats_path, quotes_path):
        for row in read_existing_rows(path):
            ts_code = str(row.get("ts_code") or "").strip().upper()
            if ts_code:
                codes.add(ts_code)
    return codes


def dedupe_rows(rows: list[dict[str, str]], key_fields: tuple[str, ...]) -> list[dict[str, str]]:
    deduped: dict[tuple[str, ...], dict[str, str]] = {}
    for row in rows:
        key = tuple(str(row.get(field) or "") for field in key_fields)
        deduped[key] = row
    return sorted(deduped.values(), key=lambda item: tuple(str(item.get(field) or "") for field in key_fields))


def build_rows(
    days: int,
    max_symbols: int,
    offset: int,
    sleep_sec: float,
    progress_every: int,
    db_name: str,
    timeout_sec: float,
    retries: int,
    failure_backoff_sec: float,
    skip_ts_codes: set[str] | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    target_start = (datetime.now().date() - timedelta(days=days * 3)).strftime("%Y%m%d")
    target_end = datetime.now().date().strftime("%Y%m%d")
    symbols = get_symbols_from_db(db_name=db_name, max_symbols=max_symbols + max(offset, 0))
    if offset > 0:
        symbols = symbols[offset:]
    symbols = symbols[:max_symbols]
    skip_ts_codes = skip_ts_codes or set()
    if symbols:
        print(f"[akshare-stats] loaded {len(symbols)} symbols from database companies")
    else:
        print("[akshare-stats] companies table unavailable/empty, fallback to AKShare spot symbols")
        symbols = get_symbols_from_spot(max_symbols=max_symbols)
    total_symbols = len(symbols)
    rows: list[dict[str, str]] = []
    quote_rows: list[dict[str, str]] = []
    fail_count = 0
    for idx, symbol in enumerate(symbols, start=1):
        if progress_every > 0 and (idx == 1 or idx % progress_every == 0):
            print(f"[akshare-stats] progress {idx}/{total_symbols}, rows={len(rows)}, fails={fail_count}")
        ts_code = symbol_to_ts_code(symbol)
        if not ts_code:
            continue
        if ts_code in skip_ts_codes:
            continue
        hist = None
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                hist = fetch_hist(symbol=symbol, start_date=target_start, end_date=target_end, timeout_sec=timeout_sec)
                break
            except TimeoutError as exc:
                last_error = exc
            except Exception as exc:
                last_error = exc
            if attempt < retries:
                time.sleep(failure_backoff_sec * (attempt + 1))
        if hist is None:
            fail_count += 1
            if progress_every > 0 and (idx == 1 or idx % progress_every == 0):
                reason = type(last_error).__name__ if last_error else "unknown"
                print(f"[akshare-stats] fail {idx}/{total_symbols} {ts_code} reason={reason}")
            time.sleep(max(sleep_sec, failure_backoff_sec))
            continue
        if hist is None or hist.empty:
            time.sleep(sleep_sec)
            continue

        date_col = pick_column(hist, ["日期", "date"])
        ret_col = pick_column(hist, ["涨跌幅", "pct_chg"])
        turnover_col = pick_column(hist, ["换手率", "turnover_rate"])
        volume_col = pick_column(hist, ["成交量", "volume"])
        amount_col = pick_column(hist, ["成交额", "amount"])
        open_col = pick_column(hist, ["开盘", "open"])
        high_col = pick_column(hist, ["最高", "high"])
        low_col = pick_column(hist, ["最低", "low"])
        close_col = pick_column(hist, ["收盘", "close"])
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
            pct_chg = None
            if ret_col:
                pct_chg = safe_float(row.get(ret_col))
                if pct_chg is not None:
                    daily_ret = pct_chg / 100.0
            turnover_rate = safe_float(row.get(turnover_col)) if turnover_col else None
            volume = safe_float(row.get(volume_col)) if volume_col else None
            amount = safe_float(row.get(amount_col)) if amount_col else None
            open_price = safe_float(row.get(open_col)) if open_col else None
            high_price = safe_float(row.get(high_col)) if high_col else None
            low_price = safe_float(row.get(low_col)) if low_col else None
            close_price = safe_float(row.get(close_col)) if close_col else None
            parsed.append(
                {
                    "trade_date": trade_date,
                    "daily_return": daily_ret,
                    "pct_chg": pct_chg,
                    "turnover_rate": turnover_rate,
                    "volume": volume,
                    "amount": amount,
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,
                }
            )

        parsed.sort(key=lambda item: item["trade_date"])
        if len(parsed) < 2:
            time.sleep(sleep_sec)
            continue

        volumes = [item["volume"] for item in parsed]
        for j, item in enumerate(parsed):
            hist_returns_5 = [x["daily_return"] for x in parsed[max(0, j - 4) : j + 1] if x["daily_return"] is not None]
            hist_returns = [x["daily_return"] for x in parsed[max(0, j - 19) : j + 1] if x["daily_return"] is not None]
            hist_returns_60 = [x["daily_return"] for x in parsed[max(0, j - 59) : j + 1] if x["daily_return"] is not None]
            future_1 = compound([x["daily_return"] for x in parsed[j + 1 : j + 2] if x["daily_return"] is not None])
            future_3 = compound([x["daily_return"] for x in parsed[j + 1 : j + 4] if x["daily_return"] is not None])
            future_5 = compound([x["daily_return"] for x in parsed[j + 1 : j + 6] if x["daily_return"] is not None])
            trailing_5 = compound(hist_returns_5[-5:]) if hist_returns_5 else None
            trailing_20 = compound(hist_returns[-20:]) if hist_returns else None
            trailing_60 = compound(hist_returns_60[-60:]) if hist_returns_60 else None
            vol_5 = statistics.stdev(hist_returns_5[-5:]) if len(hist_returns_5[-5:]) >= 2 else None
            vol_20 = statistics.stdev(hist_returns[-20:]) if len(hist_returns[-20:]) >= 2 else None
            vol_60 = statistics.stdev(hist_returns_60[-60:]) if len(hist_returns_60[-60:]) >= 2 else None
            up_days_20 = len([x for x in hist_returns[-20:] if x is not None and x > 0]) if hist_returns else None

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
                    "data_source": "akshare",
                }
            )
            prev_close = parsed[j - 1]["close"] if j > 0 else None
            quote_rows.append(
                {
                    "ts_code": ts_code,
                    "trade_date": item["trade_date"],
                    "open": "" if item["open"] is None else f"{item['open']:.4f}",
                    "high": "" if item["high"] is None else f"{item['high']:.4f}",
                    "low": "" if item["low"] is None else f"{item['low']:.4f}",
                    "close": "" if item["close"] is None else f"{item['close']:.4f}",
                    "pre_close": "" if prev_close is None else f"{prev_close:.4f}",
                    "pct_chg": "" if item["pct_chg"] is None else f"{item['pct_chg']:.6f}",
                    "volume": "" if item["volume"] is None else f"{item['volume']:.4f}",
                    "amount": "" if item["amount"] is None else f"{item['amount']:.4f}",
                    "turnover_rate": "" if item["turnover_rate"] is None else f"{item['turnover_rate']:.4f}",
                    "adj_factor": "",
                    "is_suspended": "false",
                    "is_st": "false",
                    "is_limit_up": "true" if is_limit_up(ts_code, item["pct_chg"]) else "false",
                    "is_limit_down": "true" if is_limit_down(ts_code, item["pct_chg"]) else "false",
                    "data_source": "akshare",
                }
            )
        time.sleep(sleep_sec)
    rows.sort(key=lambda item: (item["trade_date"], item["ts_code"]))
    quote_rows.sort(key=lambda item: (item["trade_date"], item["ts_code"]))
    return rows, quote_rows


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


_STATS_FIELDS = [
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

_QUOTES_FIELDS = [
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


def main() -> None:
    args = parse_args()
    output_path = Path(args.output).resolve()
    quotes_output_path = Path(args.quotes_output).resolve()
    skip_ts_codes = existing_ts_codes(output_path, quotes_output_path) if args.resume_existing else set()
    if skip_ts_codes:
        print(f"[akshare-stats] resume-existing enabled, skipping {len(skip_ts_codes)} ts_codes already present in seed outputs")
    rows, quote_rows = build_rows(
        days=args.days,
        max_symbols=args.max_symbols,
        offset=args.offset,
        sleep_sec=args.sleep_sec,
        progress_every=args.progress_every,
        db_name=args.db,
        timeout_sec=args.timeout_sec,
        retries=args.retries,
        failure_backoff_sec=args.failure_backoff_sec,
        skip_ts_codes=skip_ts_codes,
    )
    if not rows and not quote_rows:
        raise RuntimeError(
            "AKShare returned zero company stat rows and zero stock quote rows. "
            "Upstream may be unavailable or rejecting requests; retry later or fall back to Sina/local CSV."
        )
    if args.resume_existing:
        rows = dedupe_rows(read_existing_rows(output_path) + rows, ("ts_code", "trade_date"))
        quote_rows = dedupe_rows(read_existing_rows(quotes_output_path) + quote_rows, ("ts_code", "trade_date"))
    write_csv(output_path, rows, _STATS_FIELDS)
    write_csv(quotes_output_path, quote_rows, _QUOTES_FIELDS)
    print(f"Wrote {len(rows)} company stat rows to {output_path}")
    print(f"Wrote {len(quote_rows)} stock quote rows to {quotes_output_path}")
    print("Source: akshare")


if __name__ == "__main__":
    main()
