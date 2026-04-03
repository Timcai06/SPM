#!/usr/bin/env python3
"""Optional Tushare adapter for event-study analysis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional


@dataclass
class DailySeries:
    returns: Dict[str, float]
    source: str


def load_tushare() -> Optional[object]:
    try:
        import tushare as ts  # type: ignore
    except Exception:
        return None
    return ts


def normalize_trade_date(value: str) -> str:
    value = str(value).strip()
    if len(value) == 8 and value.isdigit():
        return datetime.strptime(value, "%Y%m%d").strftime("%Y-%m-%d")
    return value


def fetch_stock_returns(ts_module: object, token: str, ts_code: str, start_date: str, end_date: str) -> DailySeries:
    ts_module.set_token(token)
    pro = ts_module.pro_api(token)
    df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
    if df is None or df.empty:
        return DailySeries(returns={}, source="tushare.daily")
    returns: Dict[str, float] = {}
    for _, row in df.iterrows():
        date_key = normalize_trade_date(str(row["trade_date"]))
        pct_chg = row.get("pct_chg")
        if pct_chg is None:
            continue
        returns[date_key] = float(pct_chg) / 100.0
    return DailySeries(returns=returns, source="tushare.daily")


def fetch_index_returns(ts_module: object, token: str, index_code: str, start_date: str, end_date: str) -> DailySeries:
    ts_module.set_token(token)
    pro = ts_module.pro_api(token)
    df = pro.index_daily(ts_code=index_code, start_date=start_date, end_date=end_date)
    if df is None or df.empty:
        return DailySeries(returns={}, source="tushare.index_daily")
    returns: Dict[str, float] = {}
    for _, row in df.iterrows():
        date_key = normalize_trade_date(str(row["trade_date"]))
        pct_chg = row.get("pct_chg")
        if pct_chg is None:
            continue
        returns[date_key] = float(pct_chg) / 100.0
    return DailySeries(returns=returns, source="tushare.index_daily")
