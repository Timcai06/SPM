#!/usr/bin/env python3
"""Bridge raw-document writes behind a module service boundary."""

from __future__ import annotations

from capabilities.storage.load_task1 import upsert_raw_documents as legacy_upsert_raw_documents


def upsert_raw_documents(db_name: str, rows: list[dict[str, str]]) -> None:
    legacy_upsert_raw_documents(db_name, rows)
