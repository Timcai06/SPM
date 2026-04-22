#!/usr/bin/env python3
"""Bridge to legacy Tushare return-fetch helpers."""

from __future__ import annotations

from capabilities.analysis.tushare_adapter import fetch_index_returns, fetch_stock_returns

__all__ = ["fetch_index_returns", "fetch_stock_returns"]
