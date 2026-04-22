#!/usr/bin/env python3
"""Bridge event staging/final-load persistence behind module services."""

from __future__ import annotations

from capabilities.storage.load_task1 import (
    insert_final_tables as legacy_insert_final_tables,
    load_stage_tables as legacy_load_stage_tables,
)


def load_stage_rows(
    db_name: str,
    raw_documents: list[dict[str, str]],
    raw_candidates: list[dict[str, str]],
    structured_events: list[dict[str, str]],
) -> None:
    legacy_load_stage_tables(db_name, raw_documents, raw_candidates, structured_events)


def insert_final_rows(db_name: str) -> None:
    legacy_insert_final_tables(db_name)
