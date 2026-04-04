#!/usr/bin/env python3
"""Fetch company daily stats from Tushare and write normalized CSV."""

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

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "output" / "seeds" / "company_stats.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import company daily stats from Tushare.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--tushare-token", default="")
    parser.add_argument("--tushare-token-file", default="")
    parser.add_argument("--days", type=int, default=30, help="Recent trading-day span target.")
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


def build_rows(pro, days: int) -> list[dict[str, str]]:
    stats_by_code: dict[str, dict[str, dict[str, Optional[float] | str]]] = {}
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
                fields="ts_code,trade_date,pct_chg",
            )
        )

        if daily_basic is not None and not daily_basic.empty:
            for _, row in daily_basic.iterrows():
                ts_code = str(row.get("ts_code") or "").strip()
                if not ts_code:
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
                ts_code = str(row.get("ts_code") or "").strip()
                if not ts_code:
                    continue
                returns_by_code.setdefault(ts_code, {})
                pct_chg = safe_float(row.get("pct_chg"))
                if pct_chg is not None:
                    returns_by_code[ts_code][trade_date] = pct_chg / 100.0

    out_rows: list[dict[str, str]] = []
    for ts_code, dated_stats in stats_by_code.items():
        trade_dates = sorted(dated_stats.keys())
        daily_ret_map = returns_by_code.get(ts_code, {})
        for idx, trade_date in enumerate(trade_dates):
            hist_dates = trade_dates[max(0, idx - 19) : idx + 1]
            hist_rets = [daily_ret_map[d] for d in hist_dates if d in daily_ret_map]
            future_1 = compound([daily_ret_map[d] for d in trade_dates[idx + 1 : idx + 2] if d in daily_ret_map])
            future_3 = compound([daily_ret_map[d] for d in trade_dates[idx + 1 : idx + 4] if d in daily_ret_map])
            future_5 = compound([daily_ret_map[d] for d in trade_dates[idx + 1 : idx + 6] if d in daily_ret_map])
            trailing_20 = compound(hist_rets[-20:]) if hist_rets else None
            vol_20 = statistics.stdev(hist_rets[-20:]) if len(hist_rets[-20:]) >= 2 else None
            base = dated_stats[trade_date]
            out_rows.append(
                {
                    "ts_code": ts_code,
                    "trade_date": datetime.strptime(trade_date, "%Y%m%d").strftime("%Y-%m-%d"),
                    "total_mv": "" if base["total_mv"] is None else f"{float(base['total_mv']):.4f}",
                    "circ_mv": "" if base["circ_mv"] is None else f"{float(base['circ_mv']):.4f}",
                    "pe_ttm": "" if base["pe_ttm"] is None else f"{float(base['pe_ttm']):.4f}",
                    "pb": "" if base["pb"] is None else f"{float(base['pb']):.4f}",
                    "turnover_rate": "" if base["turnover_rate"] is None else f"{float(base['turnover_rate']):.4f}",
                    "volume_ratio": "" if base["volume_ratio"] is None else f"{float(base['volume_ratio']):.4f}",
                    "daily_return": "" if trade_date not in daily_ret_map else f"{daily_ret_map[trade_date]:.6f}",
                    "trailing_return_20d": "" if trailing_20 is None else f"{trailing_20:.6f}",
                    "volatility_20d": "" if vol_20 is None else f"{vol_20:.6f}",
                    "forward_return_1d": "" if future_1 is None else f"{future_1:.6f}",
                    "forward_return_3d": "" if future_3 is None else f"{future_3:.6f}",
                    "forward_return_5d": "" if future_5 is None else f"{future_5:.6f}",
                    "data_source": "tushare",
                }
            )
    out_rows.sort(key=lambda item: (item["trade_date"], item["ts_code"]))
    return out_rows


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
    token, token_source = resolve_tushare_token(args)
    if not token:
        raise SystemExit("Missing Tushare token. Provide --tushare-token, --tushare-token-file, or TUSHARE_TOKEN.")

    ts = load_tushare()
    ts.set_token(token)
    pro = ts.pro_api(token)
    rows = build_rows(pro, args.days)
    output_path = Path(args.output).resolve()
    write_csv(output_path, rows)
    print(f"Wrote {len(rows)} company stat rows to {output_path}")
    print(f"Tushare token source: {token_source}")


if __name__ == "__main__":
    main()
