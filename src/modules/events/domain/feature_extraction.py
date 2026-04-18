#!/usr/bin/env python3
"""Single-row structured event feature extraction."""

from __future__ import annotations

import json
from typing import Any, Dict

from modules.events.domain.amount_extraction import extract_amount_rmb
from modules.events.domain.entity_counts import chain_stages, parse_json_list, region_counts
from modules.events.domain.impact_scope import (
    choose_impact_scope,
    choose_predictability,
    choose_shock_source,
    compute_classification_confidence,
    safe_text,
)
from modules.events.domain.industry_mapping import choose_primary_sw_l1
from modules.events.domain.sentiment_scoring import sentiment_score_0_100
from modules.events.domain.source_scoring import classify_source_credibility


def enrich_structured_event_row(row: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(row)
    title_text = safe_text(row.get("raw_title")) or safe_text(row.get("event_name"))
    summary_text = safe_text(row.get("event_summary"))
    body_text = safe_text(row.get("raw_content"))
    evidence_text = safe_text(row.get("classification_evidence"))
    event_text = " ".join([title_text, summary_text, body_text, evidence_text])

    sw_code, sw_name, industry_count = choose_primary_sw_l1(
        title_text,
        summary_text,
        body_text,
        evidence_text,
        safe_text(row.get("source")),
        safe_text(row.get("industry_type")),
    )
    entities = parse_json_list(row.get("subject_entities"))
    company_count = len(entities)
    province_count, city_count, country_count = region_counts(event_text)
    chain = chain_stages(event_text)
    amount_max, amount_log = extract_amount_rmb(event_text)
    out["sw_l1_industry_code"] = sw_code
    out["sw_l1_industry"] = sw_name
    out["industry_count"] = str(industry_count)
    out["sentiment_score_0_100"] = str(
        sentiment_score_0_100(event_text, safe_text(row.get("sentiment")))
    )
    out["source_credibility_type"] = classify_source_credibility(
        safe_text(row.get("source_type")), safe_text(row.get("authority_level"))
    )
    out["amount_max_rmb"] = "" if amount_max is None else f"{amount_max:.6f}"
    out["amount_log_rmb"] = "" if amount_log is None else f"{amount_log:.6f}"
    out["company_count"] = str(company_count)
    out["province_count"] = str(province_count)
    out["city_count"] = str(city_count)
    out["country_count"] = str(country_count)
    out["chain_stage_count"] = str(len(chain))
    out["chain_stages"] = json.dumps(chain, ensure_ascii=False)
    out["predictability_type"] = choose_predictability(
        event_text, safe_text(row.get("predictability_type"))
    )
    out["shock_source_type"] = choose_shock_source(
        event_text, safe_text(row.get("shock_source_type"))
    )
    out["impact_scope"] = choose_impact_scope(
        event_text, company_count, industry_count, province_count, country_count
    )
    out["classification_confidence"] = str(compute_classification_confidence(out, event_text))
    return out
