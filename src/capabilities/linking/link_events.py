#!/usr/bin/env python3
"""Generate minimal event-company links and write them into PostgreSQL."""

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

EVENT_INDUSTRY_TO_COMPANY = {
    "军工": "军工",
    "新能源": "新能源",
    "科技": "科技",
    "消费": "消费",
}

EVENT_KEYWORDS = {
    "军工": ["军工", "战机", "导弹", "无人机", "航空", "空战", "低空"],
    "新能源": ["新能源", "储能", "电池", "电网", "光伏", "输变电"],
    "科技": ["AI", "人工智能", "机器人", "算力", "芯片", "数字化", "招标投标"],
    "消费": ["消费", "旅游", "酒店", "饮料", "保险"],
    "其他": ["政策", "方案", "通知", "信用"],
}
GENERIC_SYMBOLS = {"政策/宏观", "政策/通知", "行业/市场新闻", "行业/股市快讯", "印巴空战", "印巴冲突", "储能政策", "机器人技术突破"}


def is_specific_symbol(raw_symbol: str) -> bool:
    return raw_symbol.strip().isdigit() and len(raw_symbol.strip()) == 6


def is_generic_event(event: dict) -> bool:
    raw_symbol = (event.get("raw_symbol") or "").strip()
    if raw_symbol in GENERIC_SYMBOLS:
        return True
    return not is_specific_symbol(raw_symbol)


def normalize_tags(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
        except Exception:
            parsed = None
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
        return [item.strip() for item in stripped.replace("，", ",").split(",") if item.strip()]
    return [str(value).strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate minimal event-company links.")
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--top-k", type=int, default=3, help="Max companies per event.")
    parser.add_argument("--min-score", type=float, default=0.35)
    parser.add_argument("--lock-timeout-sec", type=int, default=120, help="Max seconds to wait for DB write lock.")
    parser.add_argument("--canonical-map", default=str(CANONICAL_MAP_PATH), help="Optional event canonical map CSV.")
    return parser.parse_args()


def score_link(event: dict, company: dict) -> tuple[float, dict]:
    raw_title = event.get("raw_title") or ""
    raw_content = event.get("raw_content") or ""
    raw_symbol = (event.get("raw_symbol") or "").strip()
    event_text = " ".join(
        [
            event["event_name"] or "",
            event["event_summary"] or "",
            event["industry_type"] or "",
            event["event_subject_type"] or "",
            raw_title,
            raw_content,
            raw_symbol,
        ]
    )
    company_text = " ".join(
        [
            company["company_name"] or "",
            company["industry_l1"] or "",
            company["industry_l2"] or "",
            company["business_scope"] or "",
            company["core_products"] or "",
            " ".join(normalize_tags(company["concept_tags"])),
        ]
    )

    industry_match = 1.0 if EVENT_INDUSTRY_TO_COMPANY.get(event["industry_type"], event["industry_type"]) == company["industry_l1"] else 0.0
    text_hits = [kw for kw in EVENT_KEYWORDS.get(event["industry_type"], EVENT_KEYWORDS["其他"]) if kw and kw in company_text]
    event_hits = [kw for kw in EVENT_KEYWORDS.get(event["industry_type"], EVENT_KEYWORDS["其他"]) if kw and kw in event_text]
    company_code = (company["ts_code"] or "").split(".", 1)[0]
    direct_symbol_match = 1.0 if company_code and company_code == raw_symbol else 0.0
    direct_name_match = 1.0 if company["company_name"] and company["company_name"] in f"{raw_title} {raw_content}" else 0.0
    title_name_match = 1.0 if company["company_name"] and company["company_name"] in raw_title else 0.0

    text_similarity = min(len(text_hits) / 3.0, 1.0)
    concept_tags = normalize_tags(company["concept_tags"])
    concept_hits = [tag for tag in concept_tags if tag and tag in event_text]
    concept_match = min(len(concept_hits) / 2.0, 1.0)
    title_keyword_hits = [kw for kw in EVENT_KEYWORDS.get(event["industry_type"], EVENT_KEYWORDS["其他"]) if kw and kw in raw_title]
    title_keyword_match = min(len(title_keyword_hits) / 2.0, 1.0)
    chain_position = 1.0 if title_name_match or direct_name_match else (0.9 if direct_symbol_match else (0.7 if text_hits or concept_hits else 0.2))
    event_match = min((len(event_hits) + len(text_hits)) / 6.0, 1.0)
    generic_event = is_generic_event(event)
    specific_symbol_event = is_specific_symbol(raw_symbol)
    generic_other_event = generic_event and event.get("industry_type") == "其他"

    if specific_symbol_event and direct_symbol_match == 0 and direct_name_match == 0:
        final_score = 0.0
    elif generic_event and direct_symbol_match == 0 and direct_name_match == 0:
        if industry_match == 0:
            final_score = 0.0
        elif len(event_hits) < 1 and len(text_hits) < 1 and concept_match == 0 and title_keyword_match == 0:
            final_score = 0.0
        elif generic_other_event and concept_match == 0 and len(text_hits) < 2 and title_name_match == 0:
            final_score = 0.0
        else:
            final_score = round(
                0.24 * industry_match
                + 0.18 * text_similarity
                + 0.18 * concept_match
                + 0.10 * title_keyword_match
                + 0.14 * chain_position
                + 0.10 * event_match,
                4,
            )
    else:
        final_score = round(
            0.28 * industry_match
            + 0.18 * text_similarity
            + 0.10 * concept_match
            + 0.08 * title_keyword_match
            + 0.20 * chain_position
            + 0.14 * event_match
            + 0.06 * direct_symbol_match
            + 0.04 * direct_name_match,
            4,
        )
    evidence = {
        "matched_keywords": text_hits,
        "matched_concepts": concept_hits,
        "title_keyword_hits": title_keyword_hits,
        "industry_match": bool(industry_match),
        "event_keywords": event_hits,
        "direct_symbol_match": bool(direct_symbol_match),
        "direct_name_match": bool(direct_name_match),
        "title_name_match": bool(title_name_match),
        "generic_event": generic_event,
        "generic_other_event": generic_other_event,
        "specific_symbol_event": specific_symbol_event,
    }
    return final_score, {
        "text_similarity_score": round(text_similarity, 4),
        "concept_match_score": round(concept_match, 4),
        "title_keyword_score": round(title_keyword_match, 4),
        "industry_match_score": round(industry_match, 4),
        "chain_position_score": round(chain_position, 4),
        "event_match_score": round(event_match, 4),
        "direct_symbol_score": round(direct_symbol_match, 4),
        "direct_name_score": round(direct_name_match, 4),
        "evidence": evidence,
    }


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


def main() -> None:
    args = parse_args()
    canonical_map = load_canonical_map_from_csv(Path(args.canonical_map).resolve())
    with write_guard(
        db_name=args.db,
        required_tables=["companies", "structured_events", "event_company_links"],
        lock_timeout_sec=args.lock_timeout_sec,
    ):
        with psycopg.connect(dsn_for(args.db), row_factory=psycopg.rows.dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT se.id,
                           se.event_id,
                           se.event_name,
                           se.event_subject_type,
                           se.industry_type,
                           se.event_summary,
                           rd.title AS raw_title,
                           rd.content AS raw_content,
                           rd.symbol_or_subject AS raw_symbol
                    FROM structured_events
                    se
                    JOIN event_candidates ec ON ec.id = se.candidate_id
                    JOIN raw_documents rd ON rd.id = ec.raw_document_id
                    ORDER BY se.id
                    """
                )
                events = cur.fetchall()
                if not canonical_map:
                    canonical_map = load_canonical_map_from_db(cur)
                cluster_events = build_cluster_events(events, canonical_map)
                cur.execute(
                    """
                    SELECT id, ts_code, company_name, industry_l1, industry_l2, business_scope, core_products, concept_tags
                    FROM companies
                    WHERE is_active = TRUE
                    ORDER BY id
                    """
                )
                companies = cur.fetchall()

                upserted = 0
                touched_structured_event_ids: set[int] = set()
                current_keys: list[tuple[int, int, str]] = []
                for event in cluster_events:
                    scored = []
                    for company in companies:
                        final_score, details = score_link(event, company)
                        event_min_score = args.min_score
                        if is_generic_event(event) and event.get("industry_type") == "其他":
                            event_min_score = max(args.min_score, 0.45)
                        if final_score >= event_min_score:
                            scored.append((final_score, company, details))
                    scored.sort(key=lambda item: item[0], reverse=True)
                    if is_generic_event(event) and all(
                        item[2]["direct_symbol_score"] < 1 and item[2]["direct_name_score"] < 1 for item in scored[:1]
                    ):
                        limit_k = min(args.top_k, 2 if event.get("industry_type") == "其他" else 4)
                    else:
                        limit_k = args.top_k
                    for final_score, company, details in scored[: limit_k]:
                        link_type = "direct_match" if details["direct_symbol_score"] >= 1 or details["direct_name_score"] >= 1 else ("industry_match" if details["industry_match_score"] >= 1 else "candidate")
                        for structured_event_id in event["member_ids"]:
                            sid = int(structured_event_id)
                            evidence = {
                                **details["evidence"],
                                "canonical_event_id": event["canonical_event_id"],
                                "canonical_cluster_size": event["cluster_size"],
                                "canonical_link_mode": "cluster_aggregated",
                            }
                            cur.execute(
                                """
                                INSERT INTO event_company_links (
                                    structured_event_id, company_id, link_type, relation_path,
                                    text_similarity_score, industry_match_score, chain_position_score,
                                    event_match_score, final_link_score, evidence
                                )
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                                ON CONFLICT (structured_event_id, company_id, link_type) DO UPDATE
                                SET relation_path = EXCLUDED.relation_path,
                                    text_similarity_score = EXCLUDED.text_similarity_score,
                                    industry_match_score = EXCLUDED.industry_match_score,
                                    chain_position_score = EXCLUDED.chain_position_score,
                                    event_match_score = EXCLUDED.event_match_score,
                                    final_link_score = EXCLUDED.final_link_score,
                                    evidence = EXCLUDED.evidence,
                                    updated_at = NOW()
                                """,
                                (
                                    sid,
                                    company["id"],
                                    link_type,
                                    f'{event["event_name"]} -> {company["industry_l2"]} -> {company["company_name"]}',
                                    Decimal(str(details["text_similarity_score"])),
                                    Decimal(str(details["industry_match_score"])),
                                    Decimal(str(details["chain_position_score"])),
                                    Decimal(str(details["event_match_score"])),
                                    Decimal(str(final_score)),
                                    json.dumps(evidence, ensure_ascii=False),
                                ),
                            )
                            upserted += 1
                            touched_structured_event_ids.add(sid)
                            current_keys.append((sid, int(company["id"]), str(link_type)))

                stale_deleted = 0
                if touched_structured_event_ids:
                    cur.execute(
                        """
                        CREATE TEMP TABLE current_event_company_link_keys (
                            structured_event_id BIGINT NOT NULL,
                            company_id BIGINT NOT NULL,
                            link_type TEXT NOT NULL,
                            PRIMARY KEY (structured_event_id, company_id, link_type)
                        ) ON COMMIT DROP
                        """
                    )
                    if current_keys:
                        cur.executemany(
                            """
                            INSERT INTO current_event_company_link_keys (structured_event_id, company_id, link_type)
                            VALUES (%s, %s, %s)
                            ON CONFLICT DO NOTHING
                            """,
                            current_keys,
                        )
                    cur.execute(
                        """
                        DELETE FROM event_company_links l
                        WHERE l.structured_event_id = ANY(%s)
                          AND NOT EXISTS (
                              SELECT 1
                              FROM current_event_company_link_keys k
                              WHERE k.structured_event_id = l.structured_event_id
                                AND k.company_id = l.company_id
                                AND k.link_type = l.link_type
                          )
                        """,
                        (list(touched_structured_event_ids),),
                    )
                    stale_deleted = cur.rowcount
            conn.commit()
    print(
        f"Upserted {upserted} event-company links into {args.db}; "
        f"deleted stale links: {stale_deleted}"
    )


if __name__ == "__main__":
    main()
