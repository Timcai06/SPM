#!/usr/bin/env python3
"""Service orchestration for event-company linking."""

from __future__ import annotations

import time
from pathlib import Path

import psycopg

from capabilities.storage.db_guard import dsn_for, write_guard
from modules.events.domain.canonical_matching import load_canonical_map_from_csv, load_canonical_map_from_db
from modules.linking.adapters.db_repository import (
    delete_stale_links,
    load_companies,
    load_structured_events,
    upsert_link,
)
from modules.linking.domain.scoring import is_generic_event, score_link
from modules.linking.services.cluster_service import build_cluster_events


def run_linking(db: str, top_k: int, min_score: float, canonical_map_path: str, progress_every: int, lock_timeout_sec: int) -> tuple[int, int]:
    canonical_map = load_canonical_map_from_csv(Path(canonical_map_path).resolve())
    with write_guard(db_name=db, required_tables=["companies", "structured_events", "event_company_links"], lock_timeout_sec=lock_timeout_sec):
        with psycopg.connect(dsn_for(db), row_factory=psycopg.rows.dict_row) as conn:
            with conn.cursor() as cur:
                events = load_structured_events(cur)
                if not canonical_map:
                    canonical_map = load_canonical_map_from_db(cur)
                cluster_events = build_cluster_events(events, canonical_map)
                companies = load_companies(cur)
                total_events = len(cluster_events)
                started_at = time.time()
                print(f"[link-events] start clustered_events={total_events}, companies={len(companies)}, top_k={top_k}, min_score={min_score}", flush=True)

                upserted = 0
                touched_structured_event_ids: set[int] = set()
                current_keys: list[tuple[int, int, str]] = []
                for event_idx, event in enumerate(cluster_events, start=1):
                    scored = []
                    for company in companies:
                        final_score, details = score_link(event, company)
                        event_min_score = max(min_score, 0.45) if is_generic_event(event) and event.get("industry_type") == "其他" else min_score
                        if final_score >= event_min_score:
                            scored.append((final_score, company, details))
                    scored.sort(key=lambda item: item[0], reverse=True)
                    if is_generic_event(event) and all(item[2]["direct_symbol_score"] < 1 and item[2]["direct_name_score"] < 1 for item in scored[:1]):
                        limit_k = min(top_k, 2 if event.get("industry_type") == "其他" else 4)
                    else:
                        limit_k = top_k

                    for final_score, company, details in scored[:limit_k]:
                        link_type = (
                            "direct_match"
                            if details["direct_symbol_score"] >= 1 or details["direct_name_score"] >= 1
                            else ("industry_match" if details["industry_match_score"] >= 1 else "candidate")
                        )
                        for structured_event_id in event["member_ids"]:
                            sid = int(structured_event_id)
                            upsert_link(cur, sid, company, link_type, event, details, final_score)
                            upserted += 1
                            touched_structured_event_ids.add(sid)
                            current_keys.append((sid, int(company["id"]), str(link_type)))

                    if progress_every > 0 and (event_idx == 1 or event_idx % progress_every == 0 or event_idx == total_events):
                        elapsed = int(time.time() - started_at)
                        print(f"[link-events] progress {event_idx}/{total_events}, candidate_links={upserted}, touched_events={len(touched_structured_event_ids)}, elapsed={elapsed}s", flush=True)

                stale_deleted = delete_stale_links(cur, touched_structured_event_ids, current_keys)
            conn.commit()
    return upserted, stale_deleted

