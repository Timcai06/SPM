#!/usr/bin/env python3
"""Generate minimal event-company links and write them into PostgreSQL."""

from __future__ import annotations

import argparse
import json
from decimal import Decimal

import psycopg


DEFAULT_DB = "stock_event_mining"

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate minimal event-company links.")
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--top-k", type=int, default=3, help="Max companies per event.")
    parser.add_argument("--min-score", type=float, default=0.35)
    return parser.parse_args()


def score_link(event: dict, company: dict) -> tuple[float, dict]:
    event_text = " ".join(
        [
            event["event_name"] or "",
            event["event_summary"] or "",
            event["industry_type"] or "",
            event["event_subject_type"] or "",
        ]
    )
    company_text = " ".join(
        [
            company["company_name"] or "",
            company["industry_l1"] or "",
            company["industry_l2"] or "",
            company["business_scope"] or "",
            company["core_products"] or "",
            " ".join(company["concept_tags"] or []),
        ]
    )

    industry_match = 1.0 if EVENT_INDUSTRY_TO_COMPANY.get(event["industry_type"], event["industry_type"]) == company["industry_l1"] else 0.0
    text_hits = [kw for kw in EVENT_KEYWORDS.get(event["industry_type"], EVENT_KEYWORDS["其他"]) if kw and kw in company_text]
    event_hits = [kw for kw in EVENT_KEYWORDS.get(event["industry_type"], EVENT_KEYWORDS["其他"]) if kw and kw in event_text]

    text_similarity = min(len(text_hits) / 3.0, 1.0)
    chain_position = 1.0 if company["company_name"] in event_text else (0.7 if text_hits else 0.2)
    event_match = min((len(event_hits) + len(text_hits)) / 6.0, 1.0)

    final_score = round(
        0.45 * industry_match + 0.25 * text_similarity + 0.15 * chain_position + 0.15 * event_match,
        4,
    )
    evidence = {
        "matched_keywords": text_hits,
        "industry_match": bool(industry_match),
        "event_keywords": event_hits,
    }
    return final_score, {
        "text_similarity_score": round(text_similarity, 4),
        "industry_match_score": round(industry_match, 4),
        "chain_position_score": round(chain_position, 4),
        "event_match_score": round(event_match, 4),
        "evidence": evidence,
    }


def main() -> None:
    args = parse_args()
    with psycopg.connect(f"dbname={args.db} user=tim host=127.0.0.1 port=5432", row_factory=psycopg.rows.dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE event_company_links RESTART IDENTITY")
            cur.execute(
                """
                SELECT id, event_name, event_subject_type, industry_type, event_summary
                FROM structured_events
                ORDER BY id
                """
            )
            events = cur.fetchall()
            cur.execute(
                """
                SELECT id, ts_code, company_name, industry_l1, industry_l2, business_scope, core_products, concept_tags
                FROM companies
                WHERE is_active = TRUE
                ORDER BY id
                """
            )
            companies = cur.fetchall()

            inserted = 0
            for event in events:
                scored = []
                for company in companies:
                    final_score, details = score_link(event, company)
                    if final_score >= args.min_score:
                        scored.append((final_score, company, details))
                scored.sort(key=lambda item: item[0], reverse=True)
                for final_score, company, details in scored[: args.top_k]:
                    link_type = "industry_match" if details["industry_match_score"] >= 1 else "candidate"
                    cur.execute(
                        """
                        INSERT INTO event_company_links (
                            structured_event_id, company_id, link_type, relation_path,
                            text_similarity_score, industry_match_score, chain_position_score,
                            event_match_score, final_link_score, evidence
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                        """,
                        (
                            event["id"],
                            company["id"],
                            link_type,
                            f'{event["event_name"]} -> {company["industry_l2"]} -> {company["company_name"]}',
                            Decimal(str(details["text_similarity_score"])),
                            Decimal(str(details["industry_match_score"])),
                            Decimal(str(details["chain_position_score"])),
                            Decimal(str(details["event_match_score"])),
                            Decimal(str(final_score)),
                            json.dumps(details["evidence"], ensure_ascii=False),
                        ),
                    )
                    inserted += 1
    print(f"Inserted {inserted} event-company links into {args.db}")


if __name__ == "__main__":
    main()
