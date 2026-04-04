#!/usr/bin/env python3
"""Optional Tushare adapter for event-study analysis."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
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


def _call_with_timeout(callable_obj, timeout_seconds: float):
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(callable_obj)
        return future.result(timeout=timeout_seconds)


def _call_with_retry(callable_obj, retries: int = 2, wait_seconds: float = 1.2, timeout_seconds: float = 20.0):
    last_exc: Optional[Exception] = None
    for idx in range(retries + 1):
        try:
            return _call_with_timeout(callable_obj, timeout_seconds=timeout_seconds)
        except FutureTimeoutError:
            last_exc = TimeoutError(f"tushare call timeout after {timeout_seconds}s")
            if idx >= retries:
                break
            time.sleep(wait_seconds * (idx + 1))
        except Exception as exc:  # pragma: no cover
            msg = str(exc)
            # Invalid token should fail fast instead of retrying.
            if "token不对" in msg or "token" in msg.lower() and "invalid" in msg.lower():
                raise exc
            last_exc = exc
            if idx >= retries:
                break
            time.sleep(wait_seconds * (idx + 1))
    if last_exc:
        raise last_exc
    return None


def _build_pro(ts_module: object, token: str):
    ts_module.set_token(token)
    return ts_module.pro_api(token)


def fetch_stock_returns(
    ts_module: object,
    token: str,
    ts_code: str,
    start_date: str,
    end_date: str,
    timeout_seconds: float = 20.0,
) -> DailySeries:
    pro = _call_with_retry(lambda: _build_pro(ts_module, token), timeout_seconds=timeout_seconds)
    df = _call_with_retry(
        lambda: pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date),
        timeout_seconds=timeout_seconds,
    )
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


def fetch_index_returns(
    ts_module: object,
    token: str,
    index_code: str,
    start_date: str,
    end_date: str,
    timeout_seconds: float = 20.0,
) -> DailySeries:
    pro = _call_with_retry(lambda: _build_pro(ts_module, token), timeout_seconds=timeout_seconds)
    df = _call_with_retry(
        lambda: pro.index_daily(ts_code=index_code, start_date=start_date, end_date=end_date),
        timeout_seconds=timeout_seconds,
    )
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
