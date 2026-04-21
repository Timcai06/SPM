#!/usr/bin/env python3
"""Market data fetch and normalization helpers for feature-return analysis."""

from __future__ import annotations

import json
from typing import Dict, List, Optional

import requests


def ts_to_sina_symbol(ts_code: str) -> Optional[str]:
    ts_code = ts_code.strip().upper()
    if not ts_code or "." not in ts_code:
        return None
    code, exch = ts_code.split(".", 1)
    if exch == "SZ":
        return f"sz{code}"
    if exch == "SH":
        return f"sh{code}"
    if exch == "BJ":
        return f"bj{code}"
    return None


def ts_to_eastmoney_secid(ts_code: str) -> Optional[str]:
    ts_code = ts_code.strip().upper()
    if not ts_code or "." not in ts_code:
        return None
    code, exch = ts_code.split(".", 1)
    if exch == "SZ":
        return f"0.{code}"
    if exch == "SH":
        return f"1.{code}"
    if exch == "BJ":
        return f"0.{code}"
    return None


def fetch_sina_kline(symbol: str, max_rows: int = 800, timeout_seconds: float = 20.0) -> List[Dict[str, str]]:
    url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
    params = {"symbol": symbol, "scale": "240", "ma": "no", "datalen": str(max_rows)}
    resp = requests.get(url, params=params, timeout=timeout_seconds)
    resp.raise_for_status()
    text = resp.text.strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    return [row for row in data if row.get("day") and row.get("close")]


def fetch_eastmoney_kline(
    secid: str, max_rows: int = 800, timeout_seconds: float = 20.0
) -> List[Dict[str, str]]:
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5",
        "fields2": "f51,f52,f53,f54,f55,f56,f57",
        "klt": "101",
        "fqt": "1",
        "beg": "0",
        "end": "0",
        "lmt": str(max_rows),
    }
    resp = requests.get(url, params=params, timeout=timeout_seconds)
    resp.raise_for_status()
    payload = resp.json()
    data = payload.get("data") or {}
    klines = data.get("klines") or []
    rows: List[Dict[str, str]] = []
    for line in klines:
        parts = str(line).split(",")
        if len(parts) < 3:
            continue
        day = parts[0].strip()
        close = parts[2].strip()
        if day and close:
            rows.append({"day": day, "close": close})
    return rows


def close_series_to_returns(kline: List[Dict[str, str]]) -> Dict[str, float]:
    rows = sorted(kline, key=lambda x: x["day"])
    result: Dict[str, float] = {}
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
