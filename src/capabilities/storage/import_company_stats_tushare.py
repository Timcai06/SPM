#!/usr/bin/env python3
"""Fetch company daily stats from Tushare and write normalized CSV outputs."""

from __future__ import annotations

import argparse
import csv
import os
import statistics
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import psycopg

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.storage.db_guard import dsn_for


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "output" / "seeds" / "company_stats.csv"
DEFAULT_QUOTES_OUTPUT = ROOT / "output" / "seeds" / "stock_daily_quotes.csv"
DEFAULT_DB = "stock_event_mining"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import company daily stats from Tushare.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--quotes-output", default=str(DEFAULT_QUOTES_OUTPUT))
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--tushare-token", default="")
    parser.add_argument("--tushare-token-file", default="")
    parser.add_argument("--days", type=int, default=30, help="Recent trading-day span target.")
    parser.add_argument("--max-symbols", type=int, default=300, help="Max company symbols loaded from DB.")
    return parser.parse_args()


def resolve_tushare_token(args: argparse.Namespace) -> tuple[str, str]:
    if args.tushare_token.strip():
        return args.tushare_token.strip(), "cli_arg"
    if args.tushare_token_file.strip():
        token_path = Path(args.tushare_token_file).expanduser().resolve()
        if token_path.exists():
            content = token_path.read_text(encoding="utf-8").strip()
            if content:
                return content, f"file:{token_path.name}"
    default_paths = [
        ROOT / ".secrets" / "tushare_token.txt",
        Path.home() / ".config" / "stock_event_mining" / "tushare_token.txt",
    ]
    for token_path in default_paths:
        if token_path.exists():
            content = token_path.read_text(encoding="utf-8").strip()
            if content:
                return content, f"file:{token_path.name}"
    env_token = os.getenv("TUSHARE_TOKEN", "").strip()
    if env_token:
        return env_token, "env:TUSHARE_TOKEN"
    return "", "missing"


def load_tushare() -> object:
    import tushare as ts  # type: ignore

    return ts


def call_with_retry(fn, retries: int = 2, wait_seconds: float = 1.0):
    last_exc = None
    for idx in range(retries + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if idx >= retries:
                break
            time.sleep(wait_seconds * (idx + 1))
    raise last_exc  # type: ignore[misc]


def recent_dates(days: int) -> list[str]:
    today = datetime.now().date()
    dates = []
    for offset in range(days * 2):
        dates.append((today - timedelta(days=offset)).strftime("%Y%m%d"))
    return dates


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


def build_rows(pro, days: int, ts_codes: list[str]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    if not ts_codes:
        raise SystemExit("No active company symbols found in DB. Please load companies first.")

    ts_code_set = set(ts_codes)
    stats_by_code: dict[str, dict[str, dict[str, Optional[float] | str]]] = {}
    quotes_by_code: dict[str, dict[str, dict[str, Optional[float] | str | bool]]] = {}
    returns_by_code: dict[str, dict[str, float]] = {}

    for trade_date in recent_dates(days):
        daily_basic = call_with_retry(
            lambda td=trade_date: pro.daily_basic(
                trade_date=td,
                fields="ts_code,trade_date,total_mv,circ_mv,pe_ttm,pb,turnover_rate,volume_ratio",
            )
        )
        daily = call_with_retry(
            lambda td=trade_date: pro.daily(
                trade_date=td,
                fields="ts_code,trade_date,open,high,low,close,pre_close,pct_chg,vol,amount",
            )
        )
        adj = call_with_retry(
            lambda td=trade_date: pro.adj_factor(
                trade_date=td,
                fields="ts_code,trade_date,adj_factor",
            )
        )

        adj_map: dict[tuple[str, str], float] = {}
        if adj is not None and not adj.empty:
            for _, row in adj.iterrows():
                ts_code = str(row.get("ts_code") or "").strip().upper()
                row_trade_date = str(row.get("trade_date") or "").strip()
                if ts_code not in ts_code_set or not row_trade_date:
                    continue
                adj_factor = safe_float(row.get("adj_factor"))
                if adj_factor is not None:
                    adj_map[(ts_code, row_trade_date)] = adj_factor

        if daily_basic is not None and not daily_basic.empty:
            for _, row in daily_basic.iterrows():
                ts_code = str(row.get("ts_code") or "").strip().upper()
                if ts_code not in ts_code_set:
                    continue
                stats_by_code.setdefault(ts_code, {})
                stats_by_code[ts_code][trade_date] = {
                    "trade_date": trade_date,
                    "total_mv": safe_float(row.get("total_mv")),
                    "circ_mv": safe_float(row.get("circ_mv")),
                    "pe_ttm": safe_float(row.get("pe_ttm")),
                    "pb": safe_float(row.get("pb")),
                    "turnover_rate": safe_float(row.get("turnover_rate")),
                    "volume_ratio": safe_float(row.get("volume_ratio")),
                }

        if daily is not None and not daily.empty:
            for _, row in daily.iterrows():
                ts_code = str(row.get("ts_code") or "").strip().upper()
                if ts_code not in ts_code_set:
                    continue
                pct_chg = safe_float(row.get("pct_chg"))
                daily_return = pct_chg / 100.0 if pct_chg is not None else None
                if daily_return is not None:
                    returns_by_code.setdefault(ts_code, {})
                    returns_by_code[ts_code][trade_date] = daily_return
                quotes_by_code.setdefault(ts_code, {})
                quotes_by_code[ts_code][trade_date] = {
                    "trade_date": trade_date,
                    "open": safe_float(row.get("open")),
                    "high": safe_float(row.get("high")),
                    "low": safe_float(row.get("low")),
                    "close": safe_float(row.get("close")),
                    "pre_close": safe_float(row.get("pre_close")),
                    "pct_chg": pct_chg,
                    "volume": safe_float(row.get("vol")),
                    "amount": safe_float(row.get("amount")),
                    "adj_factor": adj_map.get((ts_code, trade_date)),
                    "is_suspended": False,
                    "is_st": False,
                    "is_limit_up": is_limit_up(ts_code, pct_chg),
                    "is_limit_down": is_limit_down(ts_code, pct_chg),
                }

    stats_rows: list[dict[str, str]] = []
    quote_rows: list[dict[str, str]] = []

    for ts_code in sorted(ts_code_set):
        dated_stats = stats_by_code.get(ts_code, {})
        dated_quotes = quotes_by_code.get(ts_code, {})
        if not dated_quotes:
            continue
        trade_dates = sorted(dated_quotes.keys())
        daily_ret_map = returns_by_code.get(ts_code, {})
        for idx, trade_date in enumerate(trade_dates):
            hist_dates_5 = trade_dates[max(0, idx - 4) : idx + 1]
            hist_dates_20 = trade_dates[max(0, idx - 19) : idx + 1]
            hist_dates_60 = trade_dates[max(0, idx - 59) : idx + 1]
            hist_rets_5 = [daily_ret_map[d] for d in hist_dates_5 if d in daily_ret_map]
            hist_rets_20 = [daily_ret_map[d] for d in hist_dates_20 if d in daily_ret_map]
            hist_rets_60 = [daily_ret_map[d] for d in hist_dates_60 if d in daily_ret_map]
            future_1 = compound([daily_ret_map[d] for d in trade_dates[idx + 1 : idx + 2] if d in daily_ret_map])
            future_3 = compound([daily_ret_map[d] for d in trade_dates[idx + 1 : idx + 4] if d in daily_ret_map])
            future_5 = compound([daily_ret_map[d] for d in trade_dates[idx + 1 : idx + 6] if d in daily_ret_map])
            trailing_5 = compound(hist_rets_5[-5:]) if hist_rets_5 else None
            trailing_20 = compound(hist_rets_20[-20:]) if hist_rets_20 else None
            trailing_60 = compound(hist_rets_60[-60:]) if hist_rets_60 else None
            vol_5 = statistics.stdev(hist_rets_5[-5:]) if len(hist_rets_5[-5:]) >= 2 else None
            vol_20 = statistics.stdev(hist_rets_20[-20:]) if len(hist_rets_20[-20:]) >= 2 else None
            vol_60 = statistics.stdev(hist_rets_60[-60:]) if len(hist_rets_60[-60:]) >= 2 else None
            up_days_20 = len([x for x in hist_rets_20[-20:] if x > 0]) if hist_rets_20 else None
            stat_base = dated_stats.get(trade_date, {})
            quote_base = dated_quotes[trade_date]
            stats_rows.append(
                {
                    "ts_code": ts_code,
                    "trade_date": datetime.strptime(trade_date, "%Y%m%d").strftime("%Y-%m-%d"),
                    "total_mv": "" if stat_base.get("total_mv") is None else f"{float(stat_base['total_mv']):.4f}",
                    "circ_mv": "" if stat_base.get("circ_mv") is None else f"{float(stat_base['circ_mv']):.4f}",
                    "pe_ttm": "" if stat_base.get("pe_ttm") is None else f"{float(stat_base['pe_ttm']):.4f}",
                    "pb": "" if stat_base.get("pb") is None else f"{float(stat_base['pb']):.4f}",
                    "turnover_rate": "" if stat_base.get("turnover_rate") is None else f"{float(stat_base['turnover_rate']):.4f}",
                    "volume_ratio": "" if stat_base.get("volume_ratio") is None else f"{float(stat_base['volume_ratio']):.4f}",
                    "daily_return": "" if trade_date not in daily_ret_map else f"{daily_ret_map[trade_date]:.6f}",
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
                    "data_source": "tushare",
                }
            )
            quote_rows.append(
                {
                    "ts_code": ts_code,
                    "trade_date": datetime.strptime(trade_date, "%Y%m%d").strftime("%Y-%m-%d"),
                    "open": "" if quote_base.get("open") is None else f"{float(quote_base['open']):.4f}",
                    "high": "" if quote_base.get("high") is None else f"{float(quote_base['high']):.4f}",
                    "low": "" if quote_base.get("low") is None else f"{float(quote_base['low']):.4f}",
                    "close": "" if quote_base.get("close") is None else f"{float(quote_base['close']):.4f}",
                    "pre_close": "" if quote_base.get("pre_close") is None else f"{float(quote_base['pre_close']):.4f}",
                    "pct_chg": "" if quote_base.get("pct_chg") is None else f"{float(quote_base['pct_chg']):.6f}",
                    "volume": "" if quote_base.get("volume") is None else f"{float(quote_base['volume']):.4f}",
                    "amount": "" if quote_base.get("amount") is None else f"{float(quote_base['amount']):.4f}",
                    "turnover_rate": "" if stat_base.get("turnover_rate") is None else f"{float(stat_base['turnover_rate']):.4f}",
                    "adj_factor": "" if quote_base.get("adj_factor") is None else f"{float(quote_base['adj_factor']):.6f}",
                    "is_suspended": "true" if quote_base.get("is_suspended") else "false",
                    "is_st": "true" if quote_base.get("is_st") else "false",
                    "is_limit_up": "true" if quote_base.get("is_limit_up") else "false",
                    "is_limit_down": "true" if quote_base.get("is_limit_down") else "false",
                    "data_source": "tushare",
                }
            )

    stats_rows.sort(key=lambda item: (item["trade_date"], item["ts_code"]))
    quote_rows.sort(key=lambda item: (item["trade_date"], item["ts_code"]))
    return stats_rows, quote_rows


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


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)



def main() -> None:
    args = parse_args()
    token, token_source = resolve_tushare_token(args)
    if not token:
        raise SystemExit("Missing Tushare token. Provide --tushare-token, --tushare-token-file, or TUSHARE_TOKEN.")

    ts_codes = get_ts_codes_from_db(db_name=args.db, max_symbols=args.max_symbols)
    ts = load_tushare()
    ts.set_token(token)
    pro = ts.pro_api(token)
    stats_rows, quote_rows = build_rows(pro, args.days, ts_codes)
    output_path = Path(args.output).resolve()
    quotes_output_path = Path(args.quotes_output).resolve()
    write_csv(output_path, stats_rows, _STATS_FIELDS)
    write_csv(quotes_output_path, quote_rows, _QUOTES_FIELDS)
    print(f"Wrote {len(stats_rows)} company stat rows to {output_path}")
    print(f"Wrote {len(quote_rows)} stock quote rows to {quotes_output_path}")
    print(f"Tushare token source: {token_source}")


if __name__ == "__main__":
    main()
