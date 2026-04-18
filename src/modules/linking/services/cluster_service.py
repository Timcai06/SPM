#!/usr/bin/env python3
"""Cluster projection helpers for linking."""

from __future__ import annotations


def build_cluster_events(events: list[dict], event_to_cluster: dict[str, dict]) -> list[dict]:
    if not event_to_cluster:
        return [{**event, "canonical_event_id": event["event_id"], "member_ids": [event["id"]], "cluster_size": 1} for event in events]

    event_by_event_id = {event["event_id"]: event for event in events}
    built = []
    seen_clusters = set()
    for event in events:
        cluster = event_to_cluster.get(event["event_id"])
        if not cluster:
            built.append({**event, "canonical_event_id": event["event_id"], "member_ids": [event["id"]], "cluster_size": 1})
            continue
        canonical_event_id = cluster["canonical_event_id"]
        if canonical_event_id in seen_clusters:
            continue
        seen_clusters.add(canonical_event_id)
        members = [event_by_event_id[event_id] for event_id in cluster["member_event_ids"] if event_id in event_by_event_id]
        representative = event_by_event_id.get(cluster["representative_event_id"], members[0] if members else event)
        raw_title = " | ".join(dict.fromkeys(member["raw_title"] for member in members if member.get("raw_title")))
        raw_content = " | ".join(dict.fromkeys(member["raw_content"] for member in members if member.get("raw_content")))
        raw_symbol = " | ".join(dict.fromkeys((member.get("raw_symbol") or "").strip() for member in members if (member.get("raw_symbol") or "").strip()))
        event_summary = " | ".join(dict.fromkeys(member["event_summary"] for member in members if member.get("event_summary")))
        built.append(
            {
                **representative,
                "canonical_event_id": canonical_event_id,
                "member_ids": [member["id"] for member in members] or [event["id"]],
                "cluster_size": len(members) or 1,
                "raw_title": raw_title or representative.get("raw_title") or "",
                "raw_content": raw_content or representative.get("raw_content") or "",
                "raw_symbol": raw_symbol or representative.get("raw_symbol") or "",
                "event_summary": event_summary or representative.get("event_summary") or "",
            }
        )
    return built

