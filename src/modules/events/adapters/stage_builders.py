#!/usr/bin/env python3
"""Row builders for task1 staging tables."""

from __future__ import annotations

from typing import Dict, List

from modules.events.services.structured_feature_service import enrich_row


def build_candidate_stage_rows(raw_candidates: List[Dict[str, str]]) -> List[Dict[str, str]]:
    stage_rows: List[Dict[str, str]] = []
    for row in raw_candidates:
        stage_rows.append(
            {
                "raw_document_url": row["url"],
                "dedup_key": row["dedup_key"],
                "duplicate_group_size": row["duplicate_group_size"],
                "is_event": row["is_event"],
                "filter_reason": row["filter_reason"],
                "evidence": row["evidence"],
                "score_hint": row["score_hint"] or "",
            }
        )
    return stage_rows


def build_structured_stage_rows(structured_events: List[Dict[str, str]]) -> List[Dict[str, str]]:
    stage_rows: List[Dict[str, str]] = []
    for row in structured_events:
        enriched = enrich_row(row)
        stage_rows.append(
            {
                "event_id": enriched["event_id"],
                "raw_text_ref": enriched["raw_text_ref"],
                "event_name": enriched["event_name"],
                "event_date": enriched["event_date"],
                "source": enriched["source"],
                "source_type": enriched.get("source_type", "其他来源"),
                "authority_level": enriched.get("authority_level", "general_media"),
                "source_credibility_score": enriched.get("source_credibility_score", "1"),
                "event_subject_type": enriched["event_subject_type"],
                "event_subject_subtype": enriched.get("event_subject_subtype", "未细分"),
                "duration_type": enriched["duration_type"],
                "predictability_type": enriched["predictability_type"],
                "industry_type": enriched["industry_type"],
                "sentiment": enriched["sentiment"],
                "time_orientation": enriched.get("time_orientation", "current_confirmed"),
                "event_stage": enriched.get("event_stage", "确认"),
                "shock_source_type": enriched.get("shock_source_type", "其他"),
                "region_scope": enriched.get("region_scope", "domestic"),
                "trigger_word_score": enriched.get("trigger_word_score", "0"),
                "explicitness_score": enriched.get("explicitness_score", "0"),
                "uncertainty_score": enriched.get("uncertainty_score", "0"),
                "novelty_score": enriched.get("novelty_score", "50"),
                "amount_scale": enriched.get("amount_scale", "none"),
                "amount_max_rmb": enriched.get("amount_max_rmb", ""),
                "amount_log_rmb": enriched.get("amount_log_rmb", ""),
                "event_code": enriched.get("event_code", ""),
                "sw_l1_industry": enriched.get("sw_l1_industry", "其他"),
                "sw_l1_industry_code": enriched.get("sw_l1_industry_code", ""),
                "sentiment_score_0_100": enriched.get("sentiment_score_0_100", "50"),
                "source_credibility_type": enriched.get("source_credibility_type", "单一媒体"),
                "company_count": enriched.get("company_count", "0"),
                "industry_count": enriched.get("industry_count", "0"),
                "province_count": enriched.get("province_count", "0"),
                "city_count": enriched.get("city_count", "0"),
                "country_count": enriched.get("country_count", "0"),
                "chain_stage_count": enriched.get("chain_stage_count", "0"),
                "chain_stages": enriched.get("chain_stages", "[]"),
                "report_count": enriched.get("report_count", "0"),
                "media_coverage_count": enriched.get("media_coverage_count", "0"),
                "heat_growth_rate": enriched.get("heat_growth_rate", "0"),
                "heat_duration_days": enriched.get("heat_duration_days", "0"),
                "disagreement_score": enriched.get("disagreement_score", "0"),
                "classification_confidence": enriched.get("classification_confidence", "0.5"),
                "heat_score": enriched["heat_score"],
                "intensity_score": enriched["intensity_score"],
                "impact_scope": enriched["impact_scope"],
                "event_summary": enriched["event_summary"],
                "subject_entities": enriched["subject_entities"] or "[]",
                "classification_evidence": enriched.get("classification_evidence", ""),
            }
        )
    return stage_rows

