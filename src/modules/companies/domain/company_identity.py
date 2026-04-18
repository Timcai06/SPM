#!/usr/bin/env python3
"""Shared company identity helpers."""

from __future__ import annotations

import json


def exchange_from_code(code: str) -> str:
    if code.startswith(("600", "601", "603", "605", "688", "900")):
        return "SSE"
    if code.startswith(("000", "001", "002", "003", "200", "300", "301", "302")):
        return "SZSE"
    if code.startswith(
        (
            "430", "440", "830", "831", "832", "833", "834", "835",
            "836", "837", "838", "839", "870", "871", "872", "873",
            "874", "875", "876", "877", "878", "879",
        )
    ):
        return "BSE"
    return ""


def market_suffix(code: str) -> str:
    exchange = exchange_from_code(code)
    return {"SSE": "SH", "SZSE": "SZ", "BSE": "BJ"}.get(exchange, "")


def ts_code_from_code(code: str) -> str:
    suffix = market_suffix(code)
    return f"{code}.{suffix}" if suffix else ""


def safe_text(value: object) -> str:
    text = str(value or "").strip()
    return "" if text.lower() == "nan" else text


def concept_json(items: list[str]) -> str:
    unique: list[str] = []
    for item in items:
        text = safe_text(item)
        if text and text not in unique:
            unique.append(text)
    return json.dumps(unique, ensure_ascii=False)

