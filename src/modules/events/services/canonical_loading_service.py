#!/usr/bin/env python3
"""Canonical loading workflows."""

from __future__ import annotations

import csv
from pathlib import Path

from modules.events.adapters.canonical_loading_adapter import run_loading_pipeline


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    csv_path = Path(path).resolve()
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_canonical_rows(
    db: str,
    canonical_event_rows: list[dict[str, str]] | None = None,
    canonical_link_rows: list[dict[str, str]] | None = None,
    canonical_events_path: str | Path | None = None,
    canonical_map_path: str | Path | None = None,
    lock_timeout_sec: int = 120,
    quiet: bool = False,
) -> None:
    if canonical_event_rows is None and canonical_events_path:
        canonical_event_rows = read_csv_rows(canonical_events_path)
    if canonical_link_rows is None and canonical_map_path:
        canonical_link_rows = read_csv_rows(canonical_map_path)
    run_loading_pipeline(
        db=db,
        canonical_event_rows=canonical_event_rows,
        canonical_link_rows=canonical_link_rows,
        lock_timeout_sec=lock_timeout_sec,
        quiet=quiet,
    )
