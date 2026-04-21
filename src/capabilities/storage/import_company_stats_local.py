#!/usr/bin/env python3
"""Build company_stats CSV from local daily price data."""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "output" / "seeds" / "company_stats.csv"
DEFAULT_QUOTES_OUTPUT = ROOT / "output" / "seeds" / "stock_daily_quotes.csv"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import company stats from local CSV.")
    parser.add_argument("--input", required=True, help="Local CSV with daily price data.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--quotes-output", default=str(DEFAULT_QUOTES_OUTPUT))
    return parser.parse_args(argv)


def parse_date(value: str) -> Optional[str]:
    text = (value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    return None


def safe_float(value) -> Optional[float]:
    try:
        if value is None:
            return None
        text = str(value).strip()
        if text == "":
            return None
        return float(text)
    except Exception:
        return None


def trailing_return(values: list[Optional[float]]) -> Optional[float]:
    rets = [v for v in values if v is not None]
    if len(rets) < 2:
        return None
    result = 1.0
    for v in rets:
        result *= 1.0 + v
    return result - 1.0


def volatility(values: list[Optional[float]]) -> Optional[float]:
    rets = [v for v in values if v is not None]
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((v - mean) ** 2 for v in rets) / (len(rets) - 1)
    return var ** 0.5


def normalize_bool(value) -> Optional[bool]:
    text = str(value or "").strip().lower()
    if not text:
        return None
    if text in {"1", "true", "t", "yes", "y", "是"}:
        return True
    if text in {"0", "false", "f", "no", "n", "否"}:
        return False
    return None


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    quotes_output_path = Path(args.quotes_output).resolve()
    rows = []
    with input_path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            ts_code = (row.get("ts_code") or row.get("symbol") or "").strip().upper()
            trade_date = parse_date(row.get("trade_date") or row.get("date") or "")
            if not ts_code or not trade_date:
                continue
            rows.append(
                {
                    "ts_code": ts_code,
                    "trade_date": trade_date,
                    "close": safe_float(row.get("close")),
                    "pct_chg": safe_float(row.get("pct_chg")),
                    "daily_return": safe_float(row.get("daily_return")),
                    "turnover_rate": safe_float(row.get("turnover_rate")),
                    "volume_ratio": safe_float(row.get("volume_ratio")),
                    "volume": safe_float(row.get("volume")),
                    "amount": safe_float(row.get("amount")),
                    "open": safe_float(row.get("open")),
                    "high": safe_float(row.get("high")),
                    "low": safe_float(row.get("low")),
                    "pre_close": safe_float(row.get("pre_close")),
                    "adj_factor": safe_float(row.get("adj_factor")),
                    "is_suspended": normalize_bool(row.get("is_suspended")),
                    "is_st": normalize_bool(row.get("is_st")),
                    "is_limit_up": normalize_bool(row.get("is_limit_up")),
                    "is_limit_down": normalize_bool(row.get("is_limit_down")),
                    "total_mv": safe_float(row.get("total_mv")),
                    "circ_mv": safe_float(row.get("circ_mv")),
                    "pe_ttm": safe_float(row.get("pe_ttm")),
                    "pb": safe_float(row.get("pb")),
                }
            )

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["ts_code"]].append(row)
    for items in grouped.values():
        items.sort(key=lambda r: r["trade_date"])

    output_rows: list[dict[str, str]] = []
    quote_rows: list[dict[str, str]] = []
    for ts_code, items in grouped.items():
        prev_close: Optional[float] = None
        computed_returns: list[Optional[float]] = []
        for row in items:
            daily_return = row["daily_return"]
            if daily_return is None and row["pct_chg"] is not None:
                daily_return = row["pct_chg"] / 100.0
            if daily_return is None and row["close"] is not None and prev_close:
                daily_return = (row["close"] - prev_close) / prev_close
            if row["close"] is not None:
                prev_close = row["close"]
            computed_returns.append(daily_return)

        for idx, row in enumerate(items):
            daily_return = computed_returns[idx]

            hist_returns_5 = computed_returns[max(0, idx - 4) : idx + 1]
            hist_returns = computed_returns[max(0, idx - 19) : idx + 1]
            hist_returns_60 = computed_returns[max(0, idx - 59) : idx + 1]
            trailing_ret_5 = trailing_return(hist_returns_5)
            trailing_ret = trailing_return(hist_returns)
            trailing_ret_60 = trailing_return(hist_returns_60)
            vol_5 = volatility(hist_returns_5)
            vol_20 = volatility(hist_returns)
            vol_60 = volatility(hist_returns_60)
            up_days_20 = len([x for x in hist_returns if x is not None and x > 0]) if hist_returns else None

            forward_1 = trailing_return(computed_returns[idx + 1 : idx + 2])
            forward_3 = trailing_return(computed_returns[idx + 1 : idx + 4])
            forward_5 = trailing_return(computed_returns[idx + 1 : idx + 6])

            volume_ratio = row["volume_ratio"]
            if volume_ratio is None and row["volume"] is not None:
                hist_vols = [items[i].get("volume") for i in range(max(0, idx - 19), idx + 1)]
                hist_vols = [v for v in hist_vols if v is not None]
                if hist_vols:
                    avg_vol = sum(hist_vols) / len(hist_vols)
                    if avg_vol != 0:
                        volume_ratio = row["volume"] / avg_vol

            output_rows.append(
                {
                    "ts_code": ts_code,
                    "trade_date": row["trade_date"],
                    "total_mv": "" if row["total_mv"] is None else f"{row['total_mv']:.6f}",
                    "circ_mv": "" if row["circ_mv"] is None else f"{row['circ_mv']:.6f}",
                    "pe_ttm": "" if row["pe_ttm"] is None else f"{row['pe_ttm']:.6f}",
                    "pb": "" if row["pb"] is None else f"{row['pb']:.6f}",
                    "turnover_rate": "" if row["turnover_rate"] is None else f"{row['turnover_rate']:.6f}",
                    "volume_ratio": "" if volume_ratio is None else f"{volume_ratio:.6f}",
                    "daily_return": "" if daily_return is None else f"{daily_return:.6f}",
                    "trailing_return_5d": "" if trailing_ret_5 is None else f"{trailing_ret_5:.6f}",
                    "trailing_return_20d": "" if trailing_ret is None else f"{trailing_ret:.6f}",
                    "trailing_return_60d": "" if trailing_ret_60 is None else f"{trailing_ret_60:.6f}",
                    "volatility_5d": "" if vol_5 is None else f"{vol_5:.6f}",
                    "volatility_20d": "" if vol_20 is None else f"{vol_20:.6f}",
                    "volatility_60d": "" if vol_60 is None else f"{vol_60:.6f}",
                    "up_days_20d": "" if up_days_20 is None else str(up_days_20),
                    "forward_return_1d": "" if forward_1 is None else f"{forward_1:.6f}",
                    "forward_return_3d": "" if forward_3 is None else f"{forward_3:.6f}",
                    "forward_return_5d": "" if forward_5 is None else f"{forward_5:.6f}",
                    "data_source": "local_csv",
                }
            )
            close_value = row["close"]
            pre_close = row["pre_close"]
            if pre_close is None and idx > 0:
                pre_close = items[idx - 1]["close"]
            pct_chg = row["pct_chg"]
            if pct_chg is None and daily_return is not None:
                pct_chg = daily_return * 100.0
            open_price = row["open"] if row["open"] is not None else close_value
            high_price = row["high"] if row["high"] is not None else close_value
            low_price = row["low"] if row["low"] is not None else close_value
            quote_rows.append(
                {
                    "ts_code": ts_code,
                    "trade_date": row["trade_date"],
                    "open": "" if open_price is None else f"{open_price:.4f}",
                    "high": "" if high_price is None else f"{high_price:.4f}",
                    "low": "" if low_price is None else f"{low_price:.4f}",
                    "close": "" if close_value is None else f"{close_value:.4f}",
                    "pre_close": "" if pre_close is None else f"{pre_close:.4f}",
                    "pct_chg": "" if pct_chg is None else f"{pct_chg:.6f}",
                    "volume": "" if row["volume"] is None else f"{row['volume']:.4f}",
                    "amount": "" if row["amount"] is None else f"{row['amount']:.4f}",
                    "turnover_rate": "" if row["turnover_rate"] is None else f"{row['turnover_rate']:.6f}",
                    "adj_factor": "" if row["adj_factor"] is None else f"{row['adj_factor']:.6f}",
                    "is_suspended": "true" if row["is_suspended"] else "false",
                    "is_st": "true" if row["is_st"] else "false",
                    "is_limit_up": "true" if row["is_limit_up"] else "false",
                    "is_limit_down": "true" if row["is_limit_down"] else "false",
                    "data_source": "local_csv",
                }
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
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
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)
    quotes_output_path.parent.mkdir(parents=True, exist_ok=True)
    with quotes_output_path.open("w", encoding="utf-8", newline="") as f:
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
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(quote_rows)
    print(f"Wrote {len(output_rows)} company stat rows to {output_path}")
    print(f"Wrote {len(quote_rows)} stock quote rows to {quotes_output_path}")


if __name__ == "__main__":
    main()
