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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import company stats from local CSV.")
    parser.add_argument("--input", required=True, help="Local CSV with daily price data.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args()


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


def main() -> None:
    args = parse_args()
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
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
    for ts_code, items in grouped.items():
        prev_close: Optional[float] = None
        for idx, row in enumerate(items):
            daily_return = row["daily_return"]
            if daily_return is None and row["pct_chg"] is not None:
                daily_return = row["pct_chg"] / 100.0
            if daily_return is None and row["close"] is not None and prev_close:
                daily_return = (row["close"] - prev_close) / prev_close
            if row["close"] is not None:
                prev_close = row["close"]

            hist_returns = [items[i].get("daily_return") for i in range(max(0, idx - 19), idx + 1)]
            hist_returns = [r if r is not None else daily_return for r in hist_returns]
            trailing_ret = trailing_return(hist_returns)
            vol_20 = volatility(hist_returns)

            forward_1 = trailing_return([items[i].get("daily_return") for i in range(idx + 1, idx + 2)])
            forward_3 = trailing_return([items[i].get("daily_return") for i in range(idx + 1, idx + 4)])
            forward_5 = trailing_return([items[i].get("daily_return") for i in range(idx + 1, idx + 6)])

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
                    "trailing_return_20d": "" if trailing_ret is None else f"{trailing_ret:.6f}",
                    "volatility_20d": "" if vol_20 is None else f"{vol_20:.6f}",
                    "forward_return_1d": "" if forward_1 is None else f"{forward_1:.6f}",
                    "forward_return_3d": "" if forward_3 is None else f"{forward_3:.6f}",
                    "forward_return_5d": "" if forward_5 is None else f"{forward_5:.6f}",
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
            "trailing_return_20d",
            "volatility_20d",
            "forward_return_1d",
            "forward_return_3d",
            "forward_return_5d",
            "data_source",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)
    print(f"Wrote {len(output_rows)} company stat rows to {output_path}")


if __name__ == "__main__":
    main()
