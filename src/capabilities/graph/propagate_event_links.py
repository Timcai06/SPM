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


DEFAULT_DB = "stock_event_mining"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Propagate task2 links through company graph.")
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--min-source-score", type=float, default=0.35)
    parser.add_argument("--min-propagation-score", type=float, default=0.20)
    parser.add_argument("--lock-timeout-sec", type=int, default=120)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
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
                source_links = cur.fetchall()
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
                        source_score = float(link["final_link_score"] or 0)
                        relation_strength = float(relation["relation_strength"] or 0)
                        propagation_score = round(source_score * relation_strength, 4)
                        if propagation_score < args.min_propagation_score:
                            continue
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
                                link["structured_event_id"],
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
