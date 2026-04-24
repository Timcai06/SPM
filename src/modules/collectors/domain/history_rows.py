from __future__ import annotations

import csv
import hashlib
from pathlib import Path


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["source", "title", "content", "publish_time", "url", "symbol_or_subject"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def dedupe_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    unique: dict[str, dict[str, str]] = {}
    for row in rows:
        url = row.get("url") or ""
        if not url:
            digest = hashlib.md5(f"{row.get('title')}::{row.get('publish_time')}".encode("utf-8")).hexdigest()
            url = f"local://history/{row.get('source', 'unknown')}/{digest}"
            row["url"] = url
        unique[url] = row
    return sorted(unique.values(), key=lambda item: (item["publish_time"], item["url"]))


def has_quality_body(row: dict[str, str], min_content_length: int) -> bool:
    title = str(row.get("title") or "").strip()
    content = str(row.get("content") or "").strip()
    if not content or len(content) < max(1, min_content_length):
        return False
    if title and content == title:
        return False
    if title and content.startswith(title) and len(content) <= len(title) + 40:
        return False
    return True


def filter_quality_rows(rows: list[dict[str, str]], min_content_length: int) -> list[dict[str, str]]:
    return [row for row in rows if has_quality_body(row, min_content_length=min_content_length)]
