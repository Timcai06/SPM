#!/usr/bin/env python3
"""CSV/output schema for classification artifacts."""

from __future__ import annotations

RAW_CANDIDATE_FIELDS = [
    "source",
    "title",
    "publish_time",
    "url",
    "symbol_or_subject",
    "dedup_key",
    "duplicate_group_size",
    "is_event",
    "filter_reason",
    "evidence",
    "score_hint",
    "event_score",
    "event_threshold",
    "rule_version",
]

STRUCTURED_EVENT_FIELDS = [
    "event_id",
    "event_name",
    "event_date",
    "source",
    "source_type",
    "authority_level",
    "source_credibility_score",
    "event_subject_type",
    "event_subject_subtype",
    "duration_type",
    "predictability_type",
    "industry_type",
    "sentiment",
    "time_orientation",
    "event_stage",
    "shock_source_type",
    "region_scope",
    "trigger_word_score",
    "explicitness_score",
    "uncertainty_score",
    "novelty_score",
    "amount_scale",
    "event_code",
    "heat_score",
    "intensity_score",
    "impact_scope",
    "event_summary",
    "subject_entities",
    "raw_text_ref",
    "classification_evidence",
]

