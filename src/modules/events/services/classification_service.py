#!/usr/bin/env python3
"""Async classification flow for candidate and structured event rows."""

from __future__ import annotations

import asyncio
from collections import Counter
from typing import Dict, List, Tuple

from modules.events.domain.classification_rules import (
    EVENT_SUBJECT_ENUM,
    GEO_SUBJECT_ANCHOR_KEYWORDS,
    INDUSTRY_ANCHOR_RULES,
    INDUSTRY_ENUM,
    SENTIMENT_ENUM,
    SUBJECT_DEFAULT,
)
from modules.events.domain.detection_rules import detect_event
from modules.events.services.llm_enrichment_service import (
    AsyncLLMClient,
    AsyncOllamaClient,
    can_llm_promote,
    normalize_llm_industry,
    normalize_llm_sentiment,
    normalize_llm_subject,
    promote_candidate_result,
    should_trigger_llm,
)
from modules.events.services.structured_event_builder import (
    build_candidate_row,
    build_structured_row,
    dedup_key,
)


def anchored_subject_type(row: Dict[str, str], current_subject: str) -> str:
    text = f"{row.get('title', '')} {row.get('content', '')}"
    return "地缘类" if any(token in text for token in GEO_SUBJECT_ANCHOR_KEYWORDS) else current_subject


def anchored_industry_type(row: Dict[str, str], current_industry: str, rule_industry: str, anchor_rules: Dict[str, tuple]) -> str:
    text = f"{row.get('title', '')} {row.get('content', '')}"
    anchored = current_industry
    for label, keywords in anchor_rules.items():
        if any(token in text for token in keywords):
            anchored = label
            break
    if anchored == "其他" and rule_industry and rule_industry != "其他":
        return rule_industry
    return anchored


async def classify_rows_async(
    rows: List[Dict[str, str]],
    builder_config: Dict[str, object],
    use_llm: bool = False,
    llm_max_rows: int = 20,
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    client = AsyncLLMClient()
    ollama_client = AsyncOllamaClient()
    semaphore = asyncio.Semaphore(5)
    duplicate_counts = Counter(dedup_key(row) for row in rows)
    candidate_results = [detect_event(row, duplicate_counts[dedup_key(row)]) for row in rows]
    llm_budget = 0

    async def process_one(row, res, allow_llm: bool):
        structured_preview = build_structured_row(row, res, builder_config)
        llm_trigger, llm_reasons = should_trigger_llm(row, res, structured_preview, SUBJECT_DEFAULT)

        async def handle_llm(llm_data: dict, reason_suffix: str, backend: str):
            effective_result = res
            if (not res.is_event and llm_data.get("is_event") and res.event_score >= res.event_threshold - 1 and can_llm_promote(res)):
                effective_result = promote_candidate_result(res, reason_suffix)
            candidate_row = build_candidate_row(row, effective_result)
            structured_row = build_structured_row(row, effective_result, builder_config) if effective_result.is_event else None
            if structured_row is None:
                return candidate_row, None
            llm_subject = normalize_llm_subject(llm_data.get("subject_type", ""), structured_row["event_subject_type"], EVENT_SUBJECT_ENUM)
            llm_industry = normalize_llm_industry(llm_data.get("industry", ""), structured_row["industry_type"], INDUSTRY_ENUM)
            llm_sentiment = normalize_llm_sentiment(llm_data.get("sentiment", ""), structured_row["sentiment"], SENTIMENT_ENUM)
            llm_summary = (llm_data.get("summary") or structured_row["event_summary"]).strip()[:120]
            llm_event_name = (llm_data.get("event_name") or structured_row["event_name"]).strip()[:80]
            llm_subject = anchored_subject_type(row, llm_subject)
            llm_industry = anchored_industry_type(row, llm_industry, structured_row["industry_type"], INDUSTRY_ANCHOR_RULES)
            structured_row.update(
                {
                    "event_name": llm_event_name,
                    "event_subject_type": llm_subject,
                    "industry_type": llm_industry,
                    "sentiment": llm_sentiment,
                    "event_summary": llm_summary,
                    "classification_evidence": structured_row["classification_evidence"] + f"|llm=1|llm_backend={backend}|llm_trigger={','.join(llm_reasons)}|llm_subject={llm_subject}|llm_industry={llm_industry}|llm_sentiment={llm_sentiment}",
                }
            )
            return candidate_row, structured_row

        if allow_llm and llm_trigger and use_llm and client.api_key:
            async with semaphore:
                llm_data = await client.extract_event_data(row["title"], row["content"])
                if llm_data:
                    return await handle_llm(llm_data, "remote_llm_borderline", "remote")

        if allow_llm and llm_trigger and use_llm:
            async with semaphore:
                llm_data = await ollama_client.extract_event_data(row["title"], row["content"])
                if llm_data:
                    return await handle_llm(llm_data, "ollama_llm_borderline", "ollama")

        return build_candidate_row(row, res), (structured_preview if res.is_event else None)

    tasks = []
    for row, res in zip(rows, candidate_results):
        preview = build_structured_row(row, res, builder_config)
        trigger, _ = should_trigger_llm(row, res, preview, SUBJECT_DEFAULT)
        allow_llm = trigger and llm_budget < llm_max_rows
        if allow_llm:
            llm_budget += 1
        tasks.append(process_one(row, res, allow_llm))

    results = await asyncio.gather(*tasks)
    candidate_rows: List[Dict[str, object]] = []
    structured_rows: List[Dict[str, object]] = []
    seen_structured_dedup_keys = set()
    for row, (cand, struct) in zip(rows, results):
        candidate_rows.append(cand)
        if struct:
            d_key = dedup_key(row)
            if d_key not in seen_structured_dedup_keys:
                seen_structured_dedup_keys.add(d_key)
                structured_rows.append(struct)
    return candidate_rows, structured_rows
