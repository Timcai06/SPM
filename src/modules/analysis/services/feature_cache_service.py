#!/usr/bin/env python3
"""Cache and token helpers for feature-return analysis."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict


def resolve_tushare_token(
    *,
    disable_tushare: bool,
    tushare_token: str,
    tushare_token_file: str,
    root: Path,
) -> tuple[str, str]:
    if disable_tushare:
        return "", "disabled"
    if tushare_token.strip():
        return tushare_token.strip(), "cli_arg"
    if tushare_token_file.strip():
        token_path = Path(tushare_token_file).expanduser().resolve()
        if token_path.exists():
            content = token_path.read_text(encoding="utf-8").strip()
            if content:
                return content, f"file:{token_path.name}"
    default_paths = [
        root / ".secrets" / "tushare_token.txt",
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


def load_market_cache(path: Path) -> dict:
    if not path.exists():
        return {"series": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"series": {}}
    if not isinstance(payload, dict):
        return {"series": {}}
    series = payload.get("series")
    if not isinstance(series, dict):
        payload["series"] = {}
    return payload


def save_market_cache(path: Path, cache_payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cache_payload["saved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    path.write_text(json.dumps(cache_payload, ensure_ascii=False), encoding="utf-8")


def get_cached_series(cache_payload: dict, key: str) -> tuple[Dict[str, float], str]:
    series = cache_payload.get("series", {}).get(key)
    if not isinstance(series, dict):
        return {}, "none"
    returns = series.get("returns")
    if not isinstance(returns, dict):
        return {}, "none"
    normalized: Dict[str, float] = {}
    for date_key, value in returns.items():
        try:
            normalized[str(date_key)] = float(value)
        except Exception:
            continue
    source = str(series.get("source") or "cache")
    return normalized, source


def put_cached_series(cache_payload: dict, key: str, returns: Dict[str, float], source: str) -> None:
    cache_payload.setdefault("series", {})
    cache_payload["series"][key] = {
        "source": source,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "returns": returns,
    }
