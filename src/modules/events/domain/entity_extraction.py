#!/usr/bin/env python3
"""Entity extraction helpers for structured events."""

from __future__ import annotations

import re
from typing import List

ENTITY_PATTERN = re.compile(
    r"[0-9]{6}\.(?:SZ|SH|BJ)|"
    r"[0-9]{6}|"
    r"[\u4e00-\u9fa5A-Za-z0-9\*]{2,20}(?:股份有限公司|集团股份有限公司|集团有限公司|有限公司|集团|银行|证券|保险|医药|科技|电力|动力|航空|生物|智农|制药|能源)|"
    r"印巴|克什米尔|歼\-?10CE|中航成飞|霍尔木兹|中东"
)
GENERIC_ENTITY_PREFIXES = {
    "关于", "公司", "行业", "本次", "有关", "今日", "今年",
    "一季度", "二季度", "三季度", "四季度", "年度",
}
GENERIC_ENTITY_TOKENS = (
    "LC", "ST", "SZCY", "SZZB", "TOP50", "SK", "CP", "CMG", "CCTV",
    "IPO", "IRGC", "CRU", "CPU", "CPO", "ESG", "AI",
)


def normalize_entity_candidate(text: str) -> str:
    candidate = re.sub(r"\s+", "", text.strip())
    candidate = candidate.strip("：:，。；;（）()[]【】")
    if not candidate or candidate in GENERIC_ENTITY_TOKENS:
        return ""
    if any(candidate.startswith(prefix) for prefix in GENERIC_ENTITY_PREFIXES):
        return ""
    if len(candidate) < 2 or len(candidate) > 24:
        return ""
    return candidate


def extract_subject_entities(text: str, symbol_or_subject: str = "", title: str = "") -> List[str]:
    seen: List[str] = []
    if title:
        title_prefix = re.split(r"[：:]", title, maxsplit=1)[0]
        prefix_candidate = normalize_entity_candidate(title_prefix)
        if prefix_candidate and prefix_candidate not in seen:
            seen.append(prefix_candidate)
    symbol_candidate = normalize_entity_candidate(symbol_or_subject)
    if symbol_candidate and symbol_candidate not in seen:
        seen.append(symbol_candidate)
    for match in ENTITY_PATTERN.findall(text):
        candidate = normalize_entity_candidate(match)
        if candidate and candidate not in seen:
            seen.append(candidate)
    return seen

