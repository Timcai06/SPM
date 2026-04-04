#!/usr/bin/env python3
"""Build one-hop event propagation links on top of task2 links."""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

import psycopg

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.storage.db_guard import dsn_for, write_guard
from capabilities.events.canonical_utils import load_canonical_map_from_csv, load_canonical_map_from_db


DEFAULT_DB = "stock_event_mining"
ROOT = Path(__file__).resolve().parents[3]
CANONICAL_MAP_PATH = ROOT / "output" / "event_canonical_map.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Propagate task2 links through company graph.")
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--min-source-score", type=float, default=0.35)
    parser.add_argument("--min-propagation-score", type=float, default=0.20)
    parser.add_argument("--lock-timeout-sec", type=int, default=120)
    parser.add_argument("--canonical-map", default=str(CANONICAL_MAP_PATH), help="Optional event canonical map CSV.")
    return parser.parse_args()


def build_cluster_links(source_links: list[dict], event_to_cluster: dict[str, dict]) -> list[dict]:
    if not event_to_cluster:
        return [
            {
                **link,
                "canonical_event_id": link["event_id"],
                "member_structured_event_ids": [link["structured_event_id"]],
                "cluster_size": 1,
            }
            for link in source_links
        ]

    grouped: dict[tuple[str, int], list[dict]] = {}
    for link in source_links:
        cluster = event_to_cluster.get(link["event_id"])
        canonical_event_id = cluster["canonical_event_id"] if cluster else link["event_id"]
        grouped.setdefault((canonical_event_id, link["source_company_id"]), []).append(link)

    built: list[dict] = []
    for (canonical_event_id, source_company_id), links in grouped.items():
        representative = max(links, key=lambda row: float(row["final_link_score"] or 0))
        member_structured_event_ids = sorted({int(row["structured_event_id"]) for row in links})
        built.append(
            {
                **representative,
                "canonical_event_id": canonical_event_id,
                "member_structured_event_ids": member_structured_event_ids,
                "cluster_size": len({row["event_id"] for row in links}),
                "event_name": " | ".join(dict.fromkeys(row["event_name"] for row in links if row.get("event_name"))),
                "source_link_score_agg": max(float(row["final_link_score"] or 0) for row in links),
            }
        )
    return built


def main() -> None:
    args = parse_args()
    canonical_map = load_canonical_map_from_csv(Path(args.canonical_map).resolve())
    with write_guard(
        db_name=args.db,
        required_tables=["event_company_links", "company_relations", "event_propagation_links"],
        lock_timeout_sec=args.lock_timeout_sec,
    ):
        with psycopg.connect(dsn_for(args.db), row_factory=psycopg.rows.dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE event_propagation_links RESTART IDENTITY")
                cur.execute(
                    """
                    SELECT l.structured_event_id,
                           e.event_id,
                           l.company_id AS source_company_id,
                           l.final_link_score,
                           e.event_name,
                           c.company_name AS source_company_name
                    FROM event_company_links l
                    JOIN structured_events e ON e.id = l.structured_event_id
                    JOIN companies c ON c.id = l.company_id
                    WHERE l.final_link_score >= %s
                    """,
                    (args.min_source_score,),
                )
                source_rows = cur.fetchall()
                if not canonical_map:
                    canonical_map = load_canonical_map_from_db(cur)
                source_links = build_cluster_links(source_rows, canonical_map)
                inserted = 0
                for link in source_links:
                    cur.execute(
                        """
                        SELECT r.id,
                               r.source_company_id,
                               r.target_company_id,
                               r.relation_type,
                               r.relation_strength,
                               r.direction,
                               c.company_name AS target_company_name
                        FROM company_relations r
                        JOIN companies c ON c.id = r.target_company_id
                        WHERE r.source_company_id = %s
                        UNION ALL
                        SELECT r.id,
                               r.target_company_id AS source_company_id,
                               r.source_company_id AS target_company_id,
                               r.relation_type,
                               r.relation_strength,
                               r.direction,
                               c.company_name AS target_company_name
                        FROM company_relations r
                        JOIN companies c ON c.id = r.source_company_id
                        WHERE r.target_company_id = %s
                          AND r.direction = 'undirected'
                        """,
                        (link["source_company_id"], link["source_company_id"]),
                    )
                    relations = cur.fetchall()
                    for relation in relations:
                        if relation["target_company_id"] == link["source_company_id"]:
                            continue
                        source_score = float(link.get("source_link_score_agg", link["final_link_score"]) or 0)
                        relation_strength = float(relation["relation_strength"] or 0)
                        propagation_score = round(source_score * relation_strength, 4)
                        if propagation_score < args.min_propagation_score:
                            continue
                        for structured_event_id in link["member_structured_event_ids"]:
                            cur.execute(
                                """
                                INSERT INTO event_propagation_links (
                                    structured_event_id, source_company_id, target_company_id, relation_id,
                                    hop_count, propagation_type, source_link_score, relation_strength,
                                    propagation_score, propagation_path, evidence
                                )
                                VALUES (%s, %s, %s, %s, 1, 'one_hop', %s, %s, %s, %s, %s::jsonb)
                                ON CONFLICT (structured_event_id, source_company_id, target_company_id, propagation_type)
                                DO UPDATE
                                SET relation_id = EXCLUDED.relation_id,
                                    source_link_score = EXCLUDED.source_link_score,
                                    relation_strength = EXCLUDED.relation_strength,
                                    propagation_score = EXCLUDED.propagation_score,
                                    propagation_path = EXCLUDED.propagation_path,
                                    evidence = EXCLUDED.evidence,
                                    updated_at = NOW()
                                """,
                                (
                                    structured_event_id,
                                    link["source_company_id"],
                                    relation["target_company_id"],
                                    relation["id"],
                                    Decimal(str(source_score)),
                                    Decimal(str(relation_strength)),
                                    Decimal(str(propagation_score)),
                                    f'{link["event_name"]} -> {link["source_company_name"]} -> {relation["relation_type"]} -> {relation["target_company_name"]}',
                                    json.dumps(
                                        {
                                            "event_name": link["event_name"],
                                            "relation_type": relation["relation_type"],
                                            "direction": relation["direction"],
                                            "canonical_event_id": link["canonical_event_id"],
                                            "canonical_cluster_size": link["cluster_size"],
                                            "canonical_propagation_mode": "cluster_aggregated",
                                        },
                                        ensure_ascii=False,
                                    ),
                                ),
                            )
                            inserted += 1
            conn.commit()
    print(f"Inserted {inserted} event propagation links into {args.db}")


if __name__ == "__main__":
    main()
