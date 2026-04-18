#!/usr/bin/env python3
"""Event detection rules and candidate scoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

from modules.events.domain.classification_rules import (
    ANNOUNCEMENT_TEMPLATE_KEYWORDS,
    COMPANY_ACTION_STRONG_KEYWORDS,
    CSRC_HARD_EVENT_KEYWORDS,
    CSRC_ROUTINE_TITLE_KEYWORDS,
    EVENT_DUPLICATE_BONUS_CAP,
    EVENT_SCORE_THRESHOLD,
    GOV_NARRATIVE_KEYWORDS,
    LISTING_FINANCING_EXCLUSION_KEYWORDS,
    LISTING_FINANCING_STRONG_KEYWORDS,
    MACRO_DATA_KEYWORDS,
    NON_EVENT_KEYWORDS,
    POLICY_ACTION_KEYWORDS,
    ROUTINE_ANNOUNCEMENT_KEYWORDS,
    WEAK_NEUTRAL_KEYWORDS,
)
from modules.events.domain.runtime_rules import ACTIVE_EVENT_KEYWORDS
from modules.events.services.structured_event_builder import dedup_key, normalize_datetime

GENERIC_EVENT_HITS = {"公告"}


@dataclass
class CandidateResult:
    row: Dict[str, str]
    normalized_publish_time: str
    dedup_key: str
    duplicate_group_size: int
    is_event: bool
    filter_reason: str
    evidence: str
    score_hint: int
    event_score: int
    event_threshold: int


def keyword_hits(text: str, keywords: Iterable[str]) -> List[str]:
    return [kw for kw in keywords if kw in text]


def detect_event(row: Dict[str, str], duplicate_group_size: int) -> CandidateResult:
    full_text = f"{row['title']} {row['content']}"
    publish_time = normalize_datetime(row["publish_time"])
    non_event_hits = keyword_hits(full_text, NON_EVENT_KEYWORDS)
    weak_hits = keyword_hits(full_text, WEAK_NEUTRAL_KEYWORDS)
    routine_hits = keyword_hits(full_text, ROUTINE_ANNOUNCEMENT_KEYWORDS)
    template_hits = keyword_hits(full_text, ANNOUNCEMENT_TEMPLATE_KEYWORDS)
    title_narrative_hits = keyword_hits(row["title"], GOV_NARRATIVE_KEYWORDS)
    title_policy_action_hits = keyword_hits(row["title"], POLICY_ACTION_KEYWORDS)
    title_macro_data_hits = keyword_hits(row["title"], MACRO_DATA_KEYWORDS)
    listing_financing_hits = keyword_hits(row["title"], LISTING_FINANCING_STRONG_KEYWORDS)
    listing_financing_exclusion_hits = keyword_hits(row["title"], LISTING_FINANCING_EXCLUSION_KEYWORDS)
    listing_financing_strong = bool(listing_financing_hits) and not listing_financing_exclusion_hits
    csrc_routine_hits = keyword_hits(row["title"], CSRC_ROUTINE_TITLE_KEYWORDS)
    csrc_hard_event_hits = keyword_hits(full_text, CSRC_HARD_EVENT_KEYWORDS)
    event_hits = keyword_hits(full_text, ACTIVE_EVENT_KEYWORDS)
    company_action_hits = keyword_hits(full_text, COMPANY_ACTION_STRONG_KEYWORDS)
    strong_event_hits = [kw for kw in event_hits if kw not in GENERIC_EVENT_HITS] + company_action_hits

    if non_event_hits:
        return CandidateResult(row, publish_time, dedup_key(row), duplicate_group_size, False, "non_financial_noise",
                               "命中非金融关键词: " + "|".join(non_event_hits) + f"; score=0; threshold={EVENT_SCORE_THRESHOLD}", 0, 0, EVENT_SCORE_THRESHOLD)
    if weak_hits and not event_hits:
        return CandidateResult(row, publish_time, dedup_key(row), duplicate_group_size, False, "routine_disclosure_without_signal",
                               "常规披露且无显著事件关键词: " + "|".join(weak_hits) + f"; score=1; threshold={EVENT_SCORE_THRESHOLD}", 1, 1, EVENT_SCORE_THRESHOLD)
    if routine_hits and not strong_event_hits and not listing_financing_strong:
        return CandidateResult(row, publish_time, dedup_key(row), duplicate_group_size, False, "routine_announcement_without_signal",
                               "常规公告且缺少强事件关键词: " + "|".join(routine_hits) + f"; score=1; threshold={EVENT_SCORE_THRESHOLD}", 1, 1, EVENT_SCORE_THRESHOLD)
    if template_hits and not strong_event_hits and not listing_financing_strong:
        return CandidateResult(row, publish_time, dedup_key(row), duplicate_group_size, False, "announcement_template_without_signal",
                               "公告模板词且缺少强事件关键词: " + "|".join(template_hits) + f"; score=1; threshold={EVENT_SCORE_THRESHOLD}", 1, 1, EVENT_SCORE_THRESHOLD)
    if row.get("source", "").startswith(("上交所", "深交所", "巨潮资讯网")) and not strong_event_hits and not listing_financing_strong:
        return CandidateResult(row, publish_time, dedup_key(row), duplicate_group_size, False, "generic_announcement_without_signal",
                               "公告源文本仅含通用披露词; score=1; threshold=" + str(EVENT_SCORE_THRESHOLD), 1, 1, EVENT_SCORE_THRESHOLD)
    if row.get("source", "").startswith(("上交所", "深交所", "巨潮资讯网")) and company_action_hits:
        score_hint = max(EVENT_SCORE_THRESHOLD, len(company_action_hits) + min(duplicate_group_size, EVENT_DUPLICATE_BONUS_CAP))
        return CandidateResult(row, publish_time, dedup_key(row), duplicate_group_size, True, "event_signal_detected",
                               "公告强事项关键词: " + "|".join(company_action_hits) + f"; score={score_hint}; threshold={EVENT_SCORE_THRESHOLD}",
                               score_hint, score_hint, EVENT_SCORE_THRESHOLD)
    if row.get("source", "").startswith("中国政府网") and title_narrative_hits and not title_policy_action_hits and not title_macro_data_hits:
        return CandidateResult(row, publish_time, dedup_key(row), duplicate_group_size, False, "government_narrative_without_action",
                               "官媒叙事型标题且缺少正式政策动作/数据词: " + "|".join(title_narrative_hits) + f"; score=1; threshold={EVENT_SCORE_THRESHOLD}",
                               1, 1, EVENT_SCORE_THRESHOLD)
    if row.get("source", "").startswith("中国证监会"):
        only_csrc_token_signal = bool(event_hits) and set(event_hits) <= {"证监会"}
        if (csrc_routine_hits or only_csrc_token_signal) and not csrc_hard_event_hits and not title_policy_action_hits:
            return CandidateResult(row, publish_time, dedup_key(row), duplicate_group_size, False, "csrc_routine_without_policy_action",
                                   "证监会常规新闻且缺少制度动作词: " + ("|".join(csrc_routine_hits) if csrc_routine_hits else "证监会弱信号") + f"; score=1; threshold={EVENT_SCORE_THRESHOLD}",
                                   1, 1, EVENT_SCORE_THRESHOLD)
    score_hint = len(event_hits) + min(duplicate_group_size, EVENT_DUPLICATE_BONUS_CAP)
    is_event = score_hint >= EVENT_SCORE_THRESHOLD
    return CandidateResult(
        row, publish_time, dedup_key(row), duplicate_group_size, is_event,
        "event_signal_detected" if is_event else "insufficient_signal",
        "命中事件关键词: " + ("|".join(event_hits) if event_hits else "无") + f"; score={score_hint}; threshold={EVENT_SCORE_THRESHOLD}",
        score_hint, score_hint, EVENT_SCORE_THRESHOLD,
    )

