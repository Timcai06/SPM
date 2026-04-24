from __future__ import annotations

from datetime import datetime
from typing import Any


def normalize_date(value: str) -> str:
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text[:19], fmt).date().isoformat()
        except Exception:
            continue
    return text[:10]


def normalize_datetime(value: Any) -> str:
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text[:19], fmt).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            continue
    return "1970-01-01 00:00:00"


def in_date_range(value: str, start_date: str, end_date: str) -> bool:
    date_text = normalize_date(value)
    if not date_text:
        return False
    return start_date <= date_text <= end_date


def in_date_window_exclusive(value: str, start_date: str, end_date_exclusive: str) -> bool:
    date_text = normalize_date(value)
    if not date_text:
        return False
    return start_date <= date_text < end_date_exclusive


def direct_history_limit(max_pages: int, page_size: int) -> int:
    return max(1, max_pages) * max(1, page_size)


def chunked_rows(rows: list[dict[str, str]], chunk_size: int) -> list[list[dict[str, str]]]:
    size = max(1, chunk_size)
    return [rows[idx : idx + size] for idx in range(0, len(rows), size)]
