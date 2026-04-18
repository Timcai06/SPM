#!/usr/bin/env python3
"""Service wrappers for structured event feature extraction."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from modules.events.domain.feature_extraction import enrich_structured_event_row


def enrich_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return enrich_structured_event_row(row)


def enrich_rows(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [enrich_structured_event_row(row) for row in rows]

