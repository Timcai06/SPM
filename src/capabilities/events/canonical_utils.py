#!/usr/bin/env python3
"""Shared utilities for canonical event map loading."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def _build_event_to_cluster(rows: list[dict[str, Any]], representative_value: str) -> dict[str, dict]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["canonical_event_id"]), []).append(row)

    event_to_cluster: dict[str, dict] = {}
    for canonical_event_id, members in grouped.items():
        representative = next((row for row in members if str(row.get("is_representative", "")).lower() == representative_value), members[0])
        cluster = {
            "canonical_event_id": canonical_event_id,
            "representative_event_id": str(representative["event_id"]),
            "member_event_ids": [str(row["event_id"]) for row in members],
            "cluster_size": len(members),
        }
        for row in members:
            event_to_cluster[str(row["event_id"])] = cluster
    return event_to_cluster


def load_canonical_map_from_csv(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return {}
    return _build_event_to_cluster(rows, "true")


def load_canonical_map_from_db(cur) -> dict[str, dict]:
    cur.execute(
        """
        SELECT se.event_id,
               l.canonical_event_id,
               l.is_representative
        FROM int_event_canonical_links l
        JOIN structured_events se ON se.id = l.structured_event_id
        """
    )
    rows = cur.fetchall()
    if not rows:
        return {}
    return _build_event_to_cluster(rows, "true")
