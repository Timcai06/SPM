#!/usr/bin/env python3
"""Build market environment daily rows from stock quotes and benchmark fallback."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import psycopg
import requests

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.storage.db_guard import dsn_for, write_guard


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = "stock_event_mining"
DEFAULT_INPUT = ROOT / "output" / "seeds" / "market_environment_seed.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load market environment daily rows into PostgreSQL.")
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--benchmark", default="hs300")
    parser.add_argument(
        "--input",
        default="",
        help="Optional market environment seed CSV for northbound flow / benchmark overlay.",
    )
    parser.add_argument("--timeout-sec", type=float, default=12.0)
    parser.add_argument("--lock-timeout-sec", type=int, default=120)
    return parser.parse_args()


def fetch_sina_kline(symbol: str, max_rows: int = 1200, timeout_seconds: float = 20.0) -> list[dict[str, str]]:
    url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
    params = {"symbol": symbol, "scale": "240", "ma": "no", "datalen": str(max_rows)}
    resp = requests.get(url, params=params, timeout=timeout_seconds)
    resp.raise_for_status()
    text = resp.text.strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except Exception:
        return []
    return [row for row in payload if row.get("day") and row.get("close")]


def close_series_to_returns(kline: list[dict[str, str]]) -> dict[str, float]:
    rows = sorted(kline, key=lambda x: x["day"])
    result: dict[str, float] = {}
    prev_close: Optional[float] = None
    for row in rows:
        day = str(row.get("day") or "").strip().split(" ", 1)[0]
        if not day:
            continue
        try:
            close = float(row["close"])
        except Exception:
            prev_close = None
            continue
        if prev_close and prev_close != 0:
            result[day] = (close - prev_close) / prev_close
        prev_close = close
    return result


def get_trade_rows(conn: psycopg.Connection) -> list[dict[str, object]]:
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(
            """
            SELECT q.trade_date::text AS trade_date,
                   q.ts_code,
                   q.close,
                   q.volume,
                   q.amount,
                   q.pct_chg,
                   q.turnover_rate,
                   q.is_limit_up,
                   q.is_limit_down,
                   c.industry_l1
            FROM stock_daily_quotes q
            LEFT JOIN companies c ON c.ts_code = q.ts_code
            ORDER BY q.trade_date, q.ts_code
            """
        )
        return list(cur.fetchall())


def resolve_input_path(value: str) -> Path | None:
    text = (value or "").strip()
    if text:
        path = Path(text).expanduser().resolve()
        return path if path.exists() else None
    return DEFAULT_INPUT.resolve() if DEFAULT_INPUT.exists() else None


def safe_float(value: Any) -> Optional[float]:
    try:
        text = str(value or "").strip()
        if not text:
            return None
        number = float(text.replace(",", ""))
        if math.isnan(number):
            return None
        return number
    except Exception:
        return None


def read_seed_rows(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None or not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return {
            (row.get("trade_date") or "").strip(): row
            for row in csv.DictReader(f)
            if (row.get("trade_date") or "").strip()
        }


def build_market_rows(
    trade_rows: list[dict[str, object]],
    benchmark: str,
    timeout_sec: float,
    seed_rows: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    seed_rows = seed_rows or {}
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in trade_rows:
        grouped[str(row["trade_date"])].append(row)

    benchmark_symbol_map = {"hs300": "sh000300"}
    benchmark_returns: dict[str, float] = {}
    if benchmark.lower() in benchmark_symbol_map:
        try:
            benchmark_returns = close_series_to_returns(
                fetch_sina_kline(benchmark_symbol_map[benchmark.lower()], timeout_seconds=timeout_sec)
            )
        except Exception:
            benchmark_returns = {}

    output_rows: list[dict[str, str]] = []
    sorted_dates = sorted(grouped.keys())
    benchmark_ret_values = [benchmark_returns.get(d) for d in sorted_dates if benchmark_returns.get(d) is not None]
    for idx, trade_date in enumerate(sorted_dates):
        rows = grouped[trade_date]
        returns = []
        up_count = 0
        down_count = 0
        limit_up_count = 0
        limit_down_count = 0
        volume_proxy = 0.0
        industry_returns: defaultdict[str, list[float]] = defaultdict(list)
        for row in rows:
            pct = row.get("pct_chg")
            close = row.get("close")
            volume = row.get("volume")
            amount = row.get("amount")
            industry = str(row.get("industry_l1") or "其他").strip() or "其他"
            if pct is not None:
                try:
                    ret = float(pct) / 100.0
                    returns.append(ret)
                    industry_returns[industry].append(ret)
                    if ret > 0:
                        up_count += 1
                    elif ret < 0:
                        down_count += 1
                    if row.get("is_limit_up") is True:
                        limit_up_count += 1
                    elif ret >= 0.095:
                        limit_up_count += 1
                    if row.get("is_limit_down") is True:
                        limit_down_count += 1
                    elif ret <= -0.095:
                        limit_down_count += 1
                except Exception:
                    pass
            elif close is not None:
                try:
                    close_val = float(close)
                    if close_val > 0:
                        returns.append(0.0)
                except Exception:
                    pass
            if amount is not None:
                try:
                    volume_proxy += float(amount)
                    continue
                except Exception:
                    pass
            if volume is not None and close is not None:
                try:
                    volume_proxy += float(volume) * float(close)
                except Exception:
                    pass

        benchmark_ret_1d = benchmark_returns.get(trade_date)
        if benchmark_ret_1d is None and idx > 0:
            prev_date = sorted_dates[idx - 1]
            benchmark_ret_1d = benchmark_returns.get(prev_date)

        hist_dates = sorted_dates[max(0, idx - 19) : idx + 1]
        benchmark_hist = [benchmark_returns.get(d) for d in hist_dates if benchmark_returns.get(d) is not None]
        benchmark_ret_5d = None
        if benchmark_hist:
            prod = 1.0
            for value in benchmark_hist[-5:]:
                prod *= 1.0 + float(value)
            benchmark_ret_5d = prod - 1.0
        benchmark_vol_20d = None
        if len(benchmark_hist) >= 2:
            benchmark_vol_20d = statistics.stdev([float(v) for v in benchmark_hist])

        sector_hotness = []
        for ind, vals in sorted(industry_returns.items(), key=lambda item: len(item[1]), reverse=True)[:10]:
            mean_ret = statistics.mean(vals) if vals else 0.0
            sector_hotness.append({"industry": ind, "avg_return": mean_ret, "count": len(vals)})

        total = len(rows)
        risk_on_off = None
        if total > 0:
            risk_on_off = 50.0 + 50.0 * ((up_count - down_count) / total)
            risk_on_off = max(0.0, min(100.0, risk_on_off))

        seed_row = seed_rows.get(trade_date, {})
        benchmark_code = (seed_row.get("benchmark_code") or "").strip() or "000300.SH"
        benchmark_name = (seed_row.get("benchmark_name") or "").strip() or "沪深300"
        northbound_net_flow = safe_float(seed_row.get("northbound_net_flow"))

        output_rows.append(
            {
                "trade_date": trade_date,
                "benchmark_code": benchmark_code,
                "benchmark_name": benchmark_name,
                "index_return_1d": "" if benchmark_ret_1d is None else f"{benchmark_ret_1d:.6f}",
                "index_return_5d": "" if benchmark_ret_5d is None else f"{benchmark_ret_5d:.6f}",
                "index_volatility_20d": "" if benchmark_vol_20d is None else f"{benchmark_vol_20d:.6f}",
                "market_turnover": f"{volume_proxy:.4f}" if volume_proxy else "",
                "up_count": str(up_count),
                "down_count": str(down_count),
                "limit_up_count": str(limit_up_count),
                "limit_down_count": str(limit_down_count),
                "northbound_net_flow": "" if northbound_net_flow is None else f"{northbound_net_flow:.4f}",
                "sector_hotness": json.dumps(sector_hotness, ensure_ascii=False),
                "cross_market_count": str(len(sector_hotness)),
                "risk_on_off_score": "" if risk_on_off is None else f"{risk_on_off:.6f}",
            }
        )

    return output_rows


def main() -> None:
    args = parse_args()
    seed_path = resolve_input_path(args.input)
    seed_rows = read_seed_rows(seed_path)

    with write_guard(
        db_name=args.db,
        required_tables=["stock_daily_quotes", "market_environment_daily", "companies"],
        lock_timeout_sec=args.lock_timeout_sec,
    ) as conn:
        trade_rows = get_trade_rows(conn)
        market_rows = build_market_rows(
            trade_rows,
            benchmark=args.benchmark,
            timeout_sec=args.timeout_sec,
            seed_rows=seed_rows,
        )
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE market_environment_daily RESTART IDENTITY CASCADE;")
            for row in market_rows:
                cur.execute(
                    """
                    INSERT INTO market_environment_daily (
                        trade_date, benchmark_code, benchmark_name, index_return_1d, index_return_5d,
                        index_volatility_20d, market_turnover, up_count, down_count,
                        limit_up_count, limit_down_count, northbound_net_flow,
                        sector_hotness, cross_market_count, risk_on_off_score
                    )
                    VALUES (
                        %s::date, %s, %s, NULLIF(%s, '')::numeric, NULLIF(%s, '')::numeric,
                        NULLIF(%s, '')::numeric, NULLIF(%s, '')::numeric, NULLIF(%s, '')::int, NULLIF(%s, '')::int,
                        NULLIF(%s, '')::int, NULLIF(%s, '')::int, NULLIF(%s, '')::numeric,
                        %s::jsonb, NULLIF(%s, '')::int, NULLIF(%s, '')::numeric
                    )
                    ON CONFLICT (trade_date) DO UPDATE
                    SET
                        benchmark_code = EXCLUDED.benchmark_code,
                        benchmark_name = EXCLUDED.benchmark_name,
                        index_return_1d = EXCLUDED.index_return_1d,
                        index_return_5d = EXCLUDED.index_return_5d,
                        index_volatility_20d = EXCLUDED.index_volatility_20d,
                        market_turnover = EXCLUDED.market_turnover,
                        up_count = EXCLUDED.up_count,
                        down_count = EXCLUDED.down_count,
                        limit_up_count = EXCLUDED.limit_up_count,
                        limit_down_count = EXCLUDED.limit_down_count,
                        northbound_net_flow = EXCLUDED.northbound_net_flow,
                        sector_hotness = EXCLUDED.sector_hotness,
                        cross_market_count = EXCLUDED.cross_market_count,
                        risk_on_off_score = EXCLUDED.risk_on_off_score,
                        updated_at = NOW()
                    """,
                    (
                        row["trade_date"],
                        row["benchmark_code"],
                        row["benchmark_name"],
                        row["index_return_1d"],
                        row["index_return_5d"],
                        row["index_volatility_20d"],
                        row["market_turnover"],
                        row["up_count"],
                        row["down_count"],
                        row["limit_up_count"],
                        row["limit_down_count"],
                        row["northbound_net_flow"],
                        row["sector_hotness"],
                        row["cross_market_count"],
                        row["risk_on_off_score"],
                    ),
                )
        conn.commit()

    seed_text = str(seed_path) if seed_path else "none"
    print(f"Loaded market_environment_daily rows into {args.db}: {len(market_rows)} (seed={seed_text})")


if __name__ == "__main__":
    main()
