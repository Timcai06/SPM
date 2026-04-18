#!/usr/bin/env python3
"""Event feature service wrappers used by pipelines/adapters."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from capabilities.domain.events.feature_enrichment import enrich_structured_event_row


def enrich_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return enrich_structured_event_row(row)


def enrich_rows(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [enrich_structured_event_row(row) for row in rows]

