#!/usr/bin/env python3
"""Resolve benchmark and stock return series for feature-return analysis."""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Dict, Optional

from capabilities.analysis.tushare_adapter import fetch_index_returns, fetch_stock_returns
from modules.analysis.services.feature_cache_service import get_cached_series, put_cached_series
from modules.analysis.services.market_data_service import (
    close_series_to_returns,
    fetch_eastmoney_kline,
    fetch_sina_kline,
    ts_to_eastmoney_secid,
    ts_to_sina_symbol,
)


def resolve_benchmark_returns(
    *,
    benchmark_key: str,
    index_code_map: Dict[str, str],
    index_sina_symbol_map: Dict[str, str],
    index_eastmoney_secid_map: Dict[str, str],
    cache_payload: dict,
    disable_cache: bool,
    use_tushare: bool,
    ts_module,
    token: str,
    api_timeout_sec: float,
    market_max_rows: int,
    enable_eastmoney_fallback: bool,
    reason_counts: Dict[str, int],
) -> tuple[Dict[str, float], str, bool]:
    def add_reason(key: str) -> None:
        reason_counts[key] = reason_counts.get(key, 0) + 1

    benchmark_returns: Dict[str, float] = {}
    benchmark_source = "none"
    benchmark_cache_key = f"index:{benchmark_key}"
    if not disable_cache:
        benchmark_returns, benchmark_source = get_cached_series(cache_payload, benchmark_cache_key)
        if benchmark_returns:
            benchmark_source = f"cache:{benchmark_source}"
    try:
        if use_tushare and not benchmark_returns:
            ret_obj = fetch_index_returns(
                ts_module,
                token,
                index_code_map[benchmark_key],
                "20200101",
                datetime.now().strftime("%Y%m%d"),
                timeout_seconds=api_timeout_sec,
            )
            benchmark_returns = ret_obj.returns
            benchmark_source = ret_obj.source
            if benchmark_returns and not disable_cache:
                put_cached_series(cache_payload, benchmark_cache_key, benchmark_returns, benchmark_source)
    except Exception as exc:
        benchmark_returns = {}
        add_reason("tushare_index_error")
        if "token不对" in str(exc):
            use_tushare = False
        benchmark_source = f"tushare_failed:{exc.__class__.__name__}"
    if not benchmark_returns and enable_eastmoney_fallback and benchmark_key in index_eastmoney_secid_map:
        secid = index_eastmoney_secid_map[benchmark_key]
        try:
            benchmark_returns = close_series_to_returns(
                fetch_eastmoney_kline(secid, max_rows=market_max_rows, timeout_seconds=api_timeout_sec)
            )
            benchmark_source = "eastmoney_index_fallback"
            if benchmark_returns and not disable_cache:
                put_cached_series(cache_payload, benchmark_cache_key, benchmark_returns, benchmark_source)
        except Exception as exc:
            benchmark_returns = {}
            add_reason(f"eastmoney_index_error:{exc.__class__.__name__}")
            benchmark_source = f"eastmoney_failed:{exc.__class__.__name__}"
    if not benchmark_returns and benchmark_key in index_sina_symbol_map:
        symbol = index_sina_symbol_map[benchmark_key]
        try:
            benchmark_returns = close_series_to_returns(
                fetch_sina_kline(symbol, max_rows=market_max_rows, timeout_seconds=api_timeout_sec)
            )
            benchmark_source = "sina_index_fallback"
            if benchmark_returns and not disable_cache:
                put_cached_series(cache_payload, benchmark_cache_key, benchmark_returns, benchmark_source)
        except Exception as exc:
            benchmark_returns = {}
            add_reason(f"sina_index_error:{exc.__class__.__name__}")
            benchmark_source = f"sina_failed:{exc.__class__.__name__}"
    return benchmark_returns, benchmark_source, use_tushare


def resolve_stock_returns(
    *,
    ts_code: str,
    db: str,
    cache_payload: dict,
    disable_cache: bool,
    use_tushare: bool,
    ts_module,
    token: str,
    api_timeout_sec: float,
    market_max_rows: int,
    enable_eastmoney_fallback: bool,
    reason_counts: Dict[str, int],
    fetch_company_stats_returns_fn: Callable[[str, str], Dict[str, float]],
) -> tuple[Dict[str, float], str]:
    def add_reason(key: str) -> None:
        reason_counts[key] = reason_counts.get(key, 0) + 1

    stock_cache_key = f"stock:{ts_code}"
    returns: Dict[str, float] = {}
    source_name = "none"
    try:
        returns = fetch_company_stats_returns_fn(db, ts_code)
    except Exception as exc:
        returns = {}
        add_reason(f"int_company_stats_error:{exc.__class__.__name__}")
    if returns:
        source_name = "int_company_stats"
    elif not disable_cache:
        returns, source_name = get_cached_series(cache_payload, stock_cache_key)
        if returns:
            source_name = f"cache:{source_name}"
    if use_tushare and not returns:
        try:
            ret_obj = fetch_stock_returns(
                ts_module,
                token,
                ts_code,
                "20200101",
                datetime.now().strftime("%Y%m%d"),
                timeout_seconds=api_timeout_sec,
            )
            returns = ret_obj.returns
            source_name = ret_obj.source
            if returns and not disable_cache:
                put_cached_series(cache_payload, stock_cache_key, returns, source_name)
        except Exception as exc:
            returns = {}
            add_reason(f"tushare_stock_error:{exc.__class__.__name__}")
    if not returns and enable_eastmoney_fallback:
        eastmoney_secid = ts_to_eastmoney_secid(ts_code)
        if eastmoney_secid:
            try:
                returns = close_series_to_returns(
                    fetch_eastmoney_kline(eastmoney_secid, max_rows=market_max_rows, timeout_seconds=api_timeout_sec)
                )
                source_name = "eastmoney_stock_fallback"
                if returns and not disable_cache:
                    put_cached_series(cache_payload, stock_cache_key, returns, source_name)
            except Exception as exc:
                returns = {}
                source_name = "none"
                add_reason(f"eastmoney_stock_error:{exc.__class__.__name__}")
        if not returns:
            sina_symbol = ts_to_sina_symbol(ts_code)
            if sina_symbol:
                try:
                    returns = close_series_to_returns(
                        fetch_sina_kline(sina_symbol, max_rows=market_max_rows, timeout_seconds=api_timeout_sec)
                    )
                    source_name = "sina_stock_fallback"
                    if returns and not disable_cache:
                        put_cached_series(cache_payload, stock_cache_key, returns, source_name)
                except Exception as exc:
                    returns = {}
                    source_name = "none"
                    add_reason(f"sina_stock_error:{exc.__class__.__name__}")
    return returns, source_name
