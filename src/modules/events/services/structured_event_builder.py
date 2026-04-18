#!/usr/bin/env python3
"""Candidate row and structured row builders."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from modules.events.domain.classification_rules import (
    DURATION_DEFAULT, DURATION_ENUM, EVENT_SUBJECT_ENUM, HEAT_DUPLICATE_CAP,
    HEAT_DUPLICATE_PER_COUNT, HEAT_SOURCE_MULTIPLIER, HEAT_TITLE_CAP, HEAT_TITLE_PER_HIT,
    HEAT_TOTAL_CAP, IMPACT_SCOPE_DEFAULT, IMPACT_SCOPE_ENUM, IMPACT_WIDE_KEYWORDS,
    INDUSTRY_DEFAULT, INDUSTRY_ENUM, INTENSITY_BASE_BY_SUBJECT, INTENSITY_DEFAULT_BASE,
    INTENSITY_POLICY_BONUS, INTENSITY_POLICY_KEYWORDS, INTENSITY_SHOCK_BONUS,
    INTENSITY_SHOCK_KEYWORDS, INTENSITY_SURPRISE_BONUS, INTENSITY_TOTAL_CAP,
    PREDICTABILITY_DEFAULT, PREDICTABILITY_ENUM, RULE_VERSION, SENTIMENT_ENUM,
    SOURCE_WEIGHT_DEFAULT, SOURCE_WEIGHT_TOKENS, SUBJECT_DEFAULT, TITLE_EMPHASIS_WORDS,
)
from modules.events.domain.entity_extraction import extract_subject_entities
from modules.events.domain.runtime_rules import (
    ACTIVE_DURATION_RULES,
    ACTIVE_INDUSTRY_RULES,
    ACTIVE_PREDICTABILITY_RULES,
    ACTIVE_SUBJECT_RULES,
)


def keyword_hits(text: str, keywords: Iterable[str]) -> List[str]:
    return [kw for kw in keywords if kw in text]


def freeze_enum(value: str, allowed: Iterable[str], default: str) -> str:
    return value if value in set(allowed) else default


def choose_label(text: str, rules: Dict[str, List[str]], default: str) -> Tuple[str, List[str]]:
    scores = [(label, keyword_hits(text, keywords)) for label, keywords in rules.items()]
    scores.sort(key=lambda item: len(item[1]), reverse=True)
    best_label, hits = scores[0]
    return (best_label, hits) if hits else (default, [])


def choose_first_label(text: str, rules: Any, default: str) -> str:
    items = rules.items() if hasattr(rules, "items") else rules
    for label, keywords in items:
        if any(keyword in text for keyword in keywords):
            return label
    return default


def resolve_source_weight(source: str) -> float:
    for token, weight in SOURCE_WEIGHT_TOKENS:
        if token in source:
            return weight
    return SOURCE_WEIGHT_DEFAULT


def compute_sentiment(text: str, positive_words: Iterable[str], negative_words: Iterable[str]) -> str:
    pos = len(keyword_hits(text, positive_words))
    neg = len(keyword_hits(text, negative_words))
    if pos > neg:
        return freeze_enum("利好", SENTIMENT_ENUM, "中性")
    if neg > pos:
        return freeze_enum("利空", SENTIMENT_ENUM, "中性")
    return freeze_enum("中性", SENTIMENT_ENUM, "中性")


def compute_heat_score(title: str, source: str, duplicate_group_size: int) -> int:
    source_score = int(resolve_source_weight(source) * HEAT_SOURCE_MULTIPLIER)
    title_score = min(len(keyword_hits(title, TITLE_EMPHASIS_WORDS)) * HEAT_TITLE_PER_HIT, HEAT_TITLE_CAP)
    duplicate_score = min(duplicate_group_size * HEAT_DUPLICATE_PER_COUNT, HEAT_DUPLICATE_CAP)
    return min(source_score + title_score + duplicate_score, HEAT_TOTAL_CAP)


def compute_intensity_score(text: str, subject_type: str, predictability_type: str) -> int:
    base = INTENSITY_BASE_BY_SUBJECT.get(subject_type, INTENSITY_DEFAULT_BASE)
    if predictability_type == "突发型":
        base += INTENSITY_SURPRISE_BONUS
    if any(word in text for word in INTENSITY_SHOCK_KEYWORDS):
        base += INTENSITY_SHOCK_BONUS
    if any(word in text for word in INTENSITY_POLICY_KEYWORDS):
        base += INTENSITY_POLICY_BONUS
    return min(base, INTENSITY_TOTAL_CAP)


def compute_impact_scope(subject_type: str, industry_type: str, text: str) -> str:
    if subject_type in {"宏观类", "政策类"} and any(word in text for word in IMPACT_WIDE_KEYWORDS):
        return freeze_enum("全市场", IMPACT_SCOPE_ENUM, IMPACT_SCOPE_DEFAULT)
    if subject_type in {"地缘类", "行业类", "政策类"}:
        return freeze_enum("行业", IMPACT_SCOPE_ENUM, IMPACT_SCOPE_DEFAULT)
    if subject_type == "公司类":
        return freeze_enum("个股链条", IMPACT_SCOPE_ENUM, IMPACT_SCOPE_DEFAULT)
    default_scope = "行业" if industry_type != "其他" else "个股链条"
    return freeze_enum(default_scope, IMPACT_SCOPE_ENUM, IMPACT_SCOPE_DEFAULT)


def compute_source_type(source: str, source_type_rules: Any) -> str:
    return choose_first_label(source, source_type_rules, "其他来源")


def compute_authority_level(source: str, source_type: str, authority_rules: Any) -> str:
    level = choose_first_label(source, authority_rules, "")
    if level:
        return level
    return "general_media"


def compute_source_credibility_score(source_type: str) -> int:
    if source_type in {"官方文件", "监管/交易所", "公司公告"}:
        return 3
    if source_type in {"主流财经媒体", "行业协会/机构"}:
        return 2
    return 1


def compute_event_subject_subtype(text: str, subject_type: str, subtype_rules: Dict[str, Iterable[str]], fallbacks: Dict[str, str]) -> str:
    subtype = choose_first_label(text, subtype_rules, "未细分")
    return subtype if subtype != "未细分" else fallbacks.get(subject_type, "未细分")


def compute_explicitness_score(text: str) -> int:
    score = 0
    if re.search(r"\d+(?:\.\d+)?\s*(?:万亿|亿|万元|亿元|万美元|亿美元)", text):
        score += 1
    if re.search(r"\d+(?:\.\d+)?\s*%", text):
        score += 1
    if re.search(r"20\d{2}年|\d{1,2}月\d{1,2}日|截至|到期|期限", text):
        score += 1
    if extract_subject_entities(text) or re.search(r"公司|企业|行业|部门|机构", text):
        score += 1
    return score


def compute_novelty_score(duplicate_group_size: int) -> int:
    return max(20, 90 - max(duplicate_group_size - 1, 0) * 15)


def compute_amount_scale(text: str) -> str:
    amounts: List[float] = []
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*(万亿|亿|万元|亿元|万美元|亿美元)", text):
        value = float(match.group(1))
        unit = match.group(2)
        if "万亿" in unit:
            value *= 10000
        if value >= 1000:
            amounts.append(value)
            continue
        if "万元" in unit or "万美元" in unit:
            amounts.append(value / 10000)
        else:
            amounts.append(value)
    if not amounts:
        return "none"
    amount = max(amounts)
    if amount >= 1000:
        return "huge"
    if amount >= 100:
        return "large"
    if amount >= 10:
        return "medium"
    return "small"


def compute_event_code(subject_type: str, subtype: str, duration_type: str, impact_scope: str, shock_source_type: str) -> str:
    return "-".join(part.replace("/", "") for part in [subject_type, subtype, duration_type, impact_scope, shock_source_type] if part)


def build_summary(title: str, content: str) -> str:
    return f"{title}。{content[:70].rstrip('，。；; ')}"


def build_event_name(title: str, subject_entities: List[str]) -> str:
    return f"{subject_entities[0]}相关事件" if subject_entities else title[:24]


def event_id(result: Any) -> str:
    raw = f"{result.normalized_publish_time}|{result.row['source']}|{result.row['title']}"
    return "EVT-" + hashlib.md5(raw.encode("utf-8")).hexdigest()[:10]


def canonical_text(text: str) -> str:
    cleaned = re.sub(r"\s+", "", text)
    cleaned = re.sub(r"[，。、“”‘’!！?？:：;；,\.]", "", cleaned)
    return cleaned.lower()


def dedup_key(row: Dict[str, str]) -> str:
    base = canonical_text(row["title"])[:80] + "::" + canonical_text(row["content"])[:160]
    return hashlib.md5(base.encode("utf-8")).hexdigest()[:12]


def normalize_datetime(value: str) -> str:
    value = value.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    raise ValueError(f"Unsupported publish_time format: {value}")


def ensure_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)


def write_csv(path: Path, rows: List[Dict[str, object]], fieldnames: List[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_candidate_row(row: Dict[str, str], result: Any) -> Dict[str, object]:
    full_text = f"{row['title']} {row['content']}"
    _, subject_hits = choose_label(full_text, ACTIVE_SUBJECT_RULES, SUBJECT_DEFAULT)
    _, industry_hits = choose_label(full_text, ACTIVE_INDUSTRY_RULES, INDUSTRY_DEFAULT)
    _, predictability_hits = choose_label(full_text, ACTIVE_PREDICTABILITY_RULES, PREDICTABILITY_DEFAULT)
    _, duration_hits = choose_label(full_text, ACTIVE_DURATION_RULES, DURATION_DEFAULT)
    evidence = result.evidence + f"; rule_version={RULE_VERSION}; dimensions=" + "|".join(
        [
            "subject:" + (",".join(subject_hits) if subject_hits else "none"),
            "industry:" + (",".join(industry_hits) if industry_hits else "none"),
            "predictability:" + (",".join(predictability_hits) if predictability_hits else "none"),
            "duration:" + (",".join(duration_hits) if duration_hits else "none"),
        ]
    )
    return {
        "source": row["source"],
        "title": row["title"],
        "publish_time": result.normalized_publish_time,
        "url": row["url"],
        "symbol_or_subject": row["symbol_or_subject"],
        "dedup_key": result.dedup_key,
        "duplicate_group_size": result.duplicate_group_size,
        "is_event": str(result.is_event).lower(),
        "filter_reason": result.filter_reason,
        "evidence": evidence,
        "score_hint": result.score_hint,
        "event_score": result.event_score,
        "event_threshold": result.event_threshold,
        "rule_version": RULE_VERSION,
    }


def build_structured_row(row: Dict[str, str], result: Any, config: Dict[str, Any]) -> Dict[str, object]:
    full_text = f"{row['title']} {row['content']}"
    subject_type, subject_hits = choose_label(full_text, ACTIVE_SUBJECT_RULES, SUBJECT_DEFAULT)
    industry_type, industry_hits = choose_label(full_text, ACTIVE_INDUSTRY_RULES, INDUSTRY_DEFAULT)
    predictability_type, predictability_hits = choose_label(full_text, ACTIVE_PREDICTABILITY_RULES, PREDICTABILITY_DEFAULT)
    duration_type, duration_hits = choose_label(full_text, ACTIVE_DURATION_RULES, DURATION_DEFAULT)
    subject_type = freeze_enum(subject_type, EVENT_SUBJECT_ENUM, SUBJECT_DEFAULT)
    industry_type = freeze_enum(industry_type, INDUSTRY_ENUM, INDUSTRY_DEFAULT)
    predictability_type = freeze_enum(predictability_type, PREDICTABILITY_ENUM, PREDICTABILITY_DEFAULT)
    duration_type = freeze_enum(duration_type, DURATION_ENUM, DURATION_DEFAULT)
    subject_entities = extract_subject_entities(full_text, row.get("symbol_or_subject", ""), row.get("title", ""))
    sentiment = compute_sentiment(full_text, config["positive_words"], config["negative_words"])
    heat_score = compute_heat_score(row["title"], row["source"], result.duplicate_group_size)
    intensity_score = compute_intensity_score(full_text, subject_type, predictability_type)
    impact_scope = compute_impact_scope(subject_type, industry_type, full_text)
    source_type = compute_source_type(row["source"], config["source_type_rules"])
    authority_level = compute_authority_level(row["source"], source_type, config["authority_level_rules"])
    event_subject_subtype = compute_event_subject_subtype(full_text, subject_type, config["subtype_rules"], config["subtype_fallbacks"])
    time_orientation = choose_first_label(full_text, config["time_orientation_rules"], "current_confirmed")
    event_stage = choose_first_label(full_text, config["stage_rules"], "确认")
    shock_source_type = choose_first_label(full_text, config["shock_source_rules"], "其他")
    region_scope = choose_first_label(full_text, config["region_scope_rules"], "domestic")
    trigger_word_score = sum(1 for keyword in config["strong_trigger_words"] if keyword in full_text)
    explicitness_score = compute_explicitness_score(full_text)
    uncertainty_score = sum(1 for keyword in config["uncertainty_words"] if keyword in full_text)
    novelty_score = compute_novelty_score(result.duplicate_group_size)
    amount_scale = compute_amount_scale(full_text)
    return {
        "event_id": event_id(result),
        "event_name": build_event_name(row["title"], subject_entities),
        "event_date": result.normalized_publish_time.split(" ")[0],
        "source": row["source"],
        "source_type": source_type,
        "authority_level": authority_level,
        "source_credibility_score": compute_source_credibility_score(source_type),
        "event_subject_type": subject_type,
        "event_subject_subtype": event_subject_subtype,
        "duration_type": duration_type,
        "predictability_type": predictability_type,
        "industry_type": industry_type,
        "sentiment": sentiment,
        "time_orientation": time_orientation,
        "event_stage": event_stage,
        "shock_source_type": shock_source_type,
        "region_scope": region_scope,
        "trigger_word_score": trigger_word_score,
        "explicitness_score": explicitness_score,
        "uncertainty_score": uncertainty_score,
        "novelty_score": novelty_score,
        "amount_scale": amount_scale,
        "event_code": compute_event_code(subject_type, event_subject_subtype, duration_type, impact_scope, shock_source_type),
        "heat_score": heat_score,
        "intensity_score": intensity_score,
        "impact_scope": impact_scope,
        "event_summary": build_summary(row["title"], row["content"]),
        "subject_entities": json.dumps(subject_entities, ensure_ascii=False),
        "raw_text_ref": row["url"],
        "classification_evidence": "|".join(
            [
                f"rule_version={RULE_VERSION}",
                "subject=" + (",".join(subject_hits) if subject_hits else "none"),
                "industry=" + (",".join(industry_hits) if industry_hits else "none"),
                "predictability=" + (",".join(predictability_hits) if predictability_hits else "none"),
                "duration=" + (",".join(duration_hits) if duration_hits else "none"),
            ]
        ),
    }

