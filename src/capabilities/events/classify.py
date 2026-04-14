#!/usr/bin/env python3
"""Task 1 MVP pipeline for event identification and classification.

This implementation intentionally uses only Python's standard library so it
can run in a clean environment. It reads raw text candidates from CSV, applies
deterministic rules for filtering/classification, and writes two outputs:

1. output/raw_event_candidates.csv
2. output/structured_events.csv
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import argparse
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.events.rules import (
    ANNOUNCEMENT_TEMPLATE_KEYWORDS,
    CSRC_HARD_EVENT_KEYWORDS,
    CSRC_ROUTINE_TITLE_KEYWORDS,
    DURATION_DEFAULT,
    DURATION_ENUM,
    DURATION_RULES,
    EVENT_DUPLICATE_BONUS_CAP,
    EVENT_SCORE_THRESHOLD,
    EVENT_SUBJECT_ENUM,
    GOV_NARRATIVE_KEYWORDS,
    HEAT_DUPLICATE_CAP,
    HEAT_DUPLICATE_PER_COUNT,
    HEAT_SOURCE_MULTIPLIER,
    HEAT_TITLE_CAP,
    HEAT_TITLE_PER_HIT,
    HEAT_TOTAL_CAP,
    IMPACT_SCOPE_DEFAULT,
    IMPACT_SCOPE_ENUM,
    IMPACT_WIDE_KEYWORDS,
    GENERIC_ENTITY_TOKENS,
    INDUSTRY_DEFAULT,
    INDUSTRY_ENUM,
    INDUSTRY_RULES,
    INTENSITY_BASE_BY_SUBJECT,
    INTENSITY_DEFAULT_BASE,
    INTENSITY_POLICY_BONUS,
    INTENSITY_POLICY_KEYWORDS,
    INTENSITY_SHOCK_BONUS,
    INTENSITY_SHOCK_KEYWORDS,
    INTENSITY_SURPRISE_BONUS,
    INTENSITY_TOTAL_CAP,
    MACRO_DATA_KEYWORDS,
    NEGATIVE_WORDS,
    NON_EVENT_KEYWORDS,
    POLICY_ACTION_KEYWORDS,
    POSITIVE_WORDS,
    PREDICTABILITY_DEFAULT,
    PREDICTABILITY_ENUM,
    PREDICTABILITY_RULES,
    RULE_VERSION,
    ROUTINE_ANNOUNCEMENT_KEYWORDS,
    LISTING_FINANCING_STRONG_KEYWORDS,
    LISTING_FINANCING_EXCLUSION_KEYWORDS,
    SENTIMENT_ENUM,
    SOURCE_WEIGHT_DEFAULT,
    SOURCE_WEIGHT_TOKENS,
    SUBJECT_DEFAULT,
    SUBJECT_RULES,
    TITLE_EMPHASIS_WORDS,
    WEAK_NEUTRAL_KEYWORDS,
)


ROOT = Path(__file__).resolve().parents[3]
INPUT_PATH = ROOT / "output" / "seeds" / "manual_news.csv"
RULE_FEEDBACK_PATH = ROOT / "output" / "meta" / "rule_feedback_keywords.csv"
OUTPUT_DIR = ROOT / "output"
RAW_OUTPUT_PATH = OUTPUT_DIR / "raw_event_candidates.csv"
STRUCTURED_OUTPUT_PATH = OUTPUT_DIR / "structured_events.csv"
DEFAULT_DB_NAME = "stock_event_mining"
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

ENTITY_PATTERN = re.compile(r"[0-9]{6}\.(?:SZ|SH)|印巴|克什米尔|歼\-?10CE|中航成飞|储能|机器人")
GENERIC_EVENT_HITS = {"公告"}
LLM_SUBJECT_MAP = {
    "macro": "宏观类",
    "policy": "政策类",
    "industry": "行业类",
    "entity": "公司类",
    "company": "公司类",
    "shock": "地缘类",
    "geopolitical": "地缘类",
}
LLM_SENTIMENT_MAP = {
    "positive": "利好",
    "negative": "利空",
    "neutral": "中性",
}
LLM_HIGH_VALUE_SOURCE_TOKENS = ("中国政府网", "国家发展改革委", "中国证监会", "上交所", "深交所", "巨潮资讯网", "财新", "第一财经")
LLM_NO_OVERRIDE_REASONS = {
    "non_financial_noise",
    "routine_disclosure_without_signal",
    "routine_announcement_without_signal",
    "announcement_template_without_signal",
    "generic_announcement_without_signal",
    "government_narrative_without_action",
    "csrc_routine_without_policy_action",
}
GEO_SUBJECT_ANCHOR_KEYWORDS = ("中东", "霍尔木兹", "战事", "停火", "冲突", "空战", "印巴", "克什米尔")
INDUSTRY_ANCHOR_RULES = {
    "消费": ("轻工业", "零售", "餐饮", "文旅", "旅游", "消费"),
    "科技": ("无线电", "卫星", "通信", "物联网", "人工智能", "具身智能"),
}
SOURCE_TYPE_RULES = (
    ("官方文件", ("中国政府网", "国务院", "国家发展改革委", "发改委", "工信部", "商务部", "财政部", "央行")),
    ("监管/交易所", ("中国证监会", "证监会", "上交所", "深交所", "北交所")),
    ("公司公告", ("巨潮资讯网", "公司公告", "公告")),
    ("主流财经媒体", ("财新", "第一财经", "东方财富", "36氪", "证券时报", "中国证券报")),
    ("行业协会/机构", ("协会", "商会", "联盟", "研究院")),
)
AUTHORITY_LEVEL_RULES = (
    ("central", ("中国政府网", "国务院", "新华社", "人民日报", "央视财经")),
    ("ministry", ("国家发展改革委", "发改委", "工信部", "财政部", "央行", "商务部", "国家统计局", "海关总署")),
    ("exchange", ("中国证监会", "证监会", "上交所", "深交所", "北交所")),
    ("listed_company", ("巨潮资讯网", "公司公告", "年度报告", "临时公告")),
    ("top_media", ("财新", "第一财经", "上海证券报", "证券时报", "中国证券报", "Bloomberg", "Reuters")),
)
SUBTYPE_RULES = {
    "产业政策": ("产业政策", "行动计划", "实施方案", "发展方案", "促进", "支持", "补贴"),
    "监管政策": ("监管", "规范", "审查", "处罚", "问询", "征求意见", "规则"),
    "财政税收": ("财政", "税", "减免", "退税", "专项债"),
    "货币金融": ("利率", "降准", "降息", "社融", "信贷", "汇率"),
    "业绩公告": ("业绩", "营收", "净利润", "利润", "财报", "预告"),
    "重大合同": ("合同", "订单", "中标", "采购"),
    "产能投产": ("投产", "扩产", "产能", "开工", "竣工"),
    "产品发布": ("产品发布", "新品", "发布会"),
    "股权变动": ("股权", "增持", "减持", "回购", "并购", "重组"),
    "技术标准": ("技术标准", "行业标准", "标准发布"),
    "供需价格": ("价格", "涨价", "降价", "库存", "供需"),
    "宏观数据": ("GDP", "CPI", "PPI", "PMI", "社融", "失业率", "增加值"),
    "贸易摩擦": ("贸易摩擦", "关税", "制裁", "出口管制"),
    "区域冲突": ("冲突", "战事", "空战", "停火", "中东", "霍尔木兹", "印巴"),
    "自然灾害": ("地震", "洪水", "台风", "灾害"),
    "公共卫生": ("疫情", "公共卫生", "传染病"),
    "安全事故": ("事故", "爆炸", "停产", "罢工"),
}
STAGE_RULES = {
    "预期": ("拟", "计划", "预计", "可能", "或将", "有望", "征求意见"),
    "落地/执行": ("发布", "印发", "实施", "落地", "执行", "正式", "启动"),
    "反馈": ("同比", "增长", "下降", "运行", "成效", "反馈", "数据"),
}
SHOCK_SOURCE_RULES = {
    "自然灾害": ("地震", "洪水", "台风", "灾害"),
    "公共卫生": ("疫情", "公共卫生", "传染病"),
    "安全事故": ("事故", "爆炸", "停产", "罢工"),
    "地缘政治": GEO_SUBJECT_ANCHOR_KEYWORDS,
    "政策制度": ("政策", "监管", "制度", "规则", "方案", "通知", "办法", "标准"),
    "技术系统冲击": ("技术突破", "人工智能", "物联网", "通信", "卫星", "网络安全", "系统故障"),
}
TIME_ORIENTATION_RULES = {
    "future_oriented": ("将", "未来", "明年", "后续", "预计", "有望", "计划", "拟"),
    "retrospective": ("已", "此前", "过去", "去年", "以来", "回顾", "复盘"),
}
REGION_SCOPE_RULES = {
    "global": ("全球", "国际", "世界", "跨市场", "跨资产"),
    "overseas": ("美国", "欧洲", "日韩", "东南亚", "海外", "境外"),
    "regional": ("长三角", "珠三角", "京津冀", "区域", "省内", "本地"),
}
STRONG_TRIGGER_WORDS = ("重大", "首次", "突破", "全面", "紧急", "超预期", "重磅", "落地", "提速", "大幅")
UNCERTAINTY_WORDS = ("拟", "计划", "预计", "可能", "或将", "有望", "研究", "探讨", "征求意见")


def _copy_rules(source: Dict[str, List[str]]) -> Dict[str, List[str]]:
    return {label: list(words) for label, words in source.items()}


def load_feedback_keywords(path: Path) -> Dict[str, Dict[str, List[str]]]:
    result: Dict[str, Dict[str, List[str]]] = {
        "subject": {},
        "industry": {},
        "predictability": {},
        "duration": {},
    }
    if not path.exists():
        return result
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            dimension = row.get("dimension", "").strip().lower()
            label = row.get("label", "").strip()
            keyword = row.get("keyword", "").strip()
            enabled = row.get("enabled", "true").strip().lower()
            if enabled in {"0", "false", "no"}:
                continue
            if dimension not in result or not label or not keyword:
                continue
            result[dimension].setdefault(label, [])
            if keyword not in result[dimension][label]:
                result[dimension][label].append(keyword)
    return result


def merge_rules(base_rules: Dict[str, List[str]], feedback_rules: Dict[str, List[str]]) -> Dict[str, List[str]]:
    merged = _copy_rules(base_rules)
    for label, words in feedback_rules.items():
        merged.setdefault(label, [])
        for word in words:
            if word not in merged[label]:
                merged[label].append(word)
    return merged


_feedback = load_feedback_keywords(RULE_FEEDBACK_PATH)
ACTIVE_SUBJECT_RULES = merge_rules(SUBJECT_RULES, _feedback["subject"])
ACTIVE_INDUSTRY_RULES = merge_rules(INDUSTRY_RULES, _feedback["industry"])
ACTIVE_PREDICTABILITY_RULES = merge_rules(PREDICTABILITY_RULES, _feedback["predictability"])
ACTIVE_DURATION_RULES = merge_rules(DURATION_RULES, _feedback["duration"])
ACTIVE_EVENT_KEYWORDS = sorted({word for words in ACTIVE_SUBJECT_RULES.values() for word in words})


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


def load_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        # Some upstream sources may include unexpected NUL bytes.
        # Strip them at read time to keep the pipeline resilient.
        cleaned_lines = (line.replace("\x00", "") for line in f)
        return list(csv.DictReader(cleaned_lines))


def load_rows_from_inputs(paths: List[Path]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for path in paths:
        if not path.exists():
            continue
        for row in load_rows(path):
            if row.get("url") == "local://manual-seed":
                continue
            rows.append(row)
    return rows


def normalize_datetime(value: str) -> str:
    value = value.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    raise ValueError(f"Unsupported publish_time format: {value}")


def canonical_text(text: str) -> str:
    cleaned = re.sub(r"\s+", "", text)
    cleaned = re.sub(r"[，。、“”‘’!！?？:：;；,\.]", "", cleaned)
    return cleaned.lower()


def dedup_key(row: Dict[str, str]) -> str:
    base = canonical_text(row["title"])[:80] + "::" + canonical_text(row["content"])[:160]
    return hashlib.md5(base.encode("utf-8")).hexdigest()[:12]


def keyword_hits(text: str, keywords: Iterable[str]) -> List[str]:
    return [kw for kw in keywords if kw in text]


def freeze_enum(value: str, allowed: Iterable[str], default: str) -> str:
    return value if value in set(allowed) else default


def resolve_source_weight(source: str) -> float:
    for token, weight in SOURCE_WEIGHT_TOKENS:
        if token in source:
            return weight
    return SOURCE_WEIGHT_DEFAULT


def detect_event(row: Dict[str, str], duplicate_group_size: int) -> CandidateResult:
    full_text = f'{row["title"]} {row["content"]}'
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
    strong_event_hits = [kw for kw in event_hits if kw not in GENERIC_EVENT_HITS]

    if non_event_hits:
        return CandidateResult(
            row=row,
            normalized_publish_time=publish_time,
            dedup_key=dedup_key(row),
            duplicate_group_size=duplicate_group_size,
            is_event=False,
            filter_reason="non_financial_noise",
            evidence="命中非金融关键词: " + "|".join(non_event_hits) + f"; score=0; threshold={EVENT_SCORE_THRESHOLD}",
            score_hint=0,
            event_score=0,
            event_threshold=EVENT_SCORE_THRESHOLD,
        )

    if weak_hits and not event_hits:
        return CandidateResult(
            row=row,
            normalized_publish_time=publish_time,
            dedup_key=dedup_key(row),
            duplicate_group_size=duplicate_group_size,
            is_event=False,
            filter_reason="routine_disclosure_without_signal",
            evidence="常规披露且无显著事件关键词: " + "|".join(weak_hits) + f"; score=1; threshold={EVENT_SCORE_THRESHOLD}",
            score_hint=1,
            event_score=1,
            event_threshold=EVENT_SCORE_THRESHOLD,
        )

    if routine_hits and not strong_event_hits and not listing_financing_strong:
        return CandidateResult(
            row=row,
            normalized_publish_time=publish_time,
            dedup_key=dedup_key(row),
            duplicate_group_size=duplicate_group_size,
            is_event=False,
            filter_reason="routine_announcement_without_signal",
            evidence="常规公告且缺少强事件关键词: " + "|".join(routine_hits) + f"; score=1; threshold={EVENT_SCORE_THRESHOLD}",
            score_hint=1,
            event_score=1,
            event_threshold=EVENT_SCORE_THRESHOLD,
        )

    if template_hits and not strong_event_hits and not listing_financing_strong:
        return CandidateResult(
            row=row,
            normalized_publish_time=publish_time,
            dedup_key=dedup_key(row),
            duplicate_group_size=duplicate_group_size,
            is_event=False,
            filter_reason="announcement_template_without_signal",
            evidence="公告模板词且缺少强事件关键词: " + "|".join(template_hits) + f"; score=1; threshold={EVENT_SCORE_THRESHOLD}",
            score_hint=1,
            event_score=1,
            event_threshold=EVENT_SCORE_THRESHOLD,
        )

    if row.get("source", "").startswith(("上交所", "深交所", "巨潮资讯网")) and not strong_event_hits and not listing_financing_strong:
        return CandidateResult(
            row=row,
            normalized_publish_time=publish_time,
            dedup_key=dedup_key(row),
            duplicate_group_size=duplicate_group_size,
            is_event=False,
            filter_reason="generic_announcement_without_signal",
            evidence="公告源文本仅含通用披露词; score=1; threshold=" + str(EVENT_SCORE_THRESHOLD),
            score_hint=1,
            event_score=1,
            event_threshold=EVENT_SCORE_THRESHOLD,
        )

    if row.get("source", "").startswith("中国政府网") and title_narrative_hits and not title_policy_action_hits and not title_macro_data_hits:
        return CandidateResult(
            row=row,
            normalized_publish_time=publish_time,
            dedup_key=dedup_key(row),
            duplicate_group_size=duplicate_group_size,
            is_event=False,
            filter_reason="government_narrative_without_action",
            evidence="官媒叙事型标题且缺少正式政策动作/数据词: " + "|".join(title_narrative_hits) + f"; score=1; threshold={EVENT_SCORE_THRESHOLD}",
            score_hint=1,
            event_score=1,
            event_threshold=EVENT_SCORE_THRESHOLD,
        )

    if row.get("source", "").startswith("中国证监会"):
        only_csrc_token_signal = bool(event_hits) and set(event_hits) <= {"证监会"}
        if (csrc_routine_hits or only_csrc_token_signal) and not csrc_hard_event_hits and not title_policy_action_hits:
            return CandidateResult(
                row=row,
                normalized_publish_time=publish_time,
                dedup_key=dedup_key(row),
                duplicate_group_size=duplicate_group_size,
                is_event=False,
                filter_reason="csrc_routine_without_policy_action",
                evidence="证监会常规新闻且缺少制度动作词: "
                + ("|".join(csrc_routine_hits) if csrc_routine_hits else "证监会弱信号")
                + f"; score=1; threshold={EVENT_SCORE_THRESHOLD}",
                score_hint=1,
                event_score=1,
                event_threshold=EVENT_SCORE_THRESHOLD,
            )

    score_hint = len(event_hits) + min(duplicate_group_size, EVENT_DUPLICATE_BONUS_CAP)
    is_event = score_hint >= EVENT_SCORE_THRESHOLD
    reason = "event_signal_detected" if is_event else "insufficient_signal"
    evidence = (
        "命中事件关键词: "
        + ("|".join(event_hits) if event_hits else "无")
        + f"; score={score_hint}; threshold={EVENT_SCORE_THRESHOLD}"
    )
    return CandidateResult(
        row=row,
        normalized_publish_time=publish_time,
        dedup_key=dedup_key(row),
        duplicate_group_size=duplicate_group_size,
        is_event=is_event,
        filter_reason=reason,
        evidence=evidence,
        score_hint=score_hint,
        event_score=score_hint,
        event_threshold=EVENT_SCORE_THRESHOLD,
    )


def choose_label(text: str, rules: Dict[str, List[str]], default: str) -> Tuple[str, List[str]]:
    scores = []
    for label, keywords in rules.items():
        hits = keyword_hits(text, keywords)
        scores.append((label, hits))
    scores.sort(key=lambda item: len(item[1]), reverse=True)
    best_label, hits = scores[0]
    if not hits:
        return default, []
    return best_label, hits


def compute_sentiment(text: str) -> str:
    pos = len(keyword_hits(text, POSITIVE_WORDS))
    neg = len(keyword_hits(text, NEGATIVE_WORDS))
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


def choose_first_label(text: str, rules: Any, default: str) -> str:
    items = rules.items() if hasattr(rules, "items") else rules
    for label, keywords in items:
        if any(keyword in text for keyword in keywords):
            return label
    return default


def compute_source_type(source: str) -> str:
    return choose_first_label(source, SOURCE_TYPE_RULES, "其他来源")


def compute_authority_level(source: str, source_type: str) -> str:
    level = choose_first_label(source, AUTHORITY_LEVEL_RULES, "")
    if level:
        return level
    if source_type == "行业协会/机构":
        return "general_media"
    return "general_media"


def compute_source_credibility_score(source_type: str) -> int:
    if source_type in {"官方文件", "监管/交易所", "公司公告"}:
        return 3
    if source_type in {"主流财经媒体", "行业协会/机构"}:
        return 2
    return 1


def compute_event_subject_subtype(text: str) -> str:
    return choose_first_label(text, SUBTYPE_RULES, "未细分")


def compute_event_stage(text: str) -> str:
    return choose_first_label(text, STAGE_RULES, "确认")


def compute_shock_source_type(text: str) -> str:
    return choose_first_label(text, SHOCK_SOURCE_RULES, "其他")


def compute_time_orientation(text: str) -> str:
    return choose_first_label(text, TIME_ORIENTATION_RULES, "current_confirmed")


def compute_region_scope(text: str) -> str:
    return choose_first_label(text, REGION_SCOPE_RULES, "domestic")


def count_keyword_score(text: str, keywords: Iterable[str]) -> int:
    return sum(1 for keyword in keywords if keyword in text)


def compute_explicitness_score(text: str) -> int:
    score = 0
    if re.search(r"\d+(?:\.\d+)?\s*(?:亿|万亿|万元|亿元|万美元|亿美元)", text):
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
    amounts = [float(m.group(1)) for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(亿|万亿|亿元|亿美元)", text)]
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


def compute_event_code(
    subject_type: str,
    subtype: str,
    duration_type: str,
    impact_scope: str,
    shock_source_type: str,
) -> str:
    parts = [subject_type, subtype, duration_type, impact_scope, shock_source_type]
    return "-".join(part.replace("/", "") for part in parts if part)


def extract_subject_entities(text: str) -> List[str]:
    seen = []
    for match in ENTITY_PATTERN.findall(text):
        if match in GENERIC_ENTITY_TOKENS:
            continue
        if match not in seen:
            seen.append(match)
    return seen


def build_summary(title: str, content: str) -> str:
    fragment = content[:70].rstrip("，。；; ")
    return f"{title}。{fragment}"


def build_event_name(title: str, subject_entities: List[str]) -> str:
    if subject_entities:
        return f"{subject_entities[0]}相关事件"
    return title[:24]


def event_id(result: CandidateResult) -> str:
    raw = f'{result.normalized_publish_time}|{result.row["source"]}|{result.row["title"]}'
    return "EVT-" + hashlib.md5(raw.encode("utf-8")).hexdigest()[:10]


def ensure_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)


def write_csv(path: Path, rows: List[Dict[str, object]], fieldnames: List[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Task 1 event structuring pipeline.")
    parser.add_argument(
        "--input",
        action="append",
        dest="inputs",
        help="Input CSV file. Can be repeated. Defaults to output/seeds/manual_news.csv",
    )
    parser.add_argument(
        "--output-dir",
        default=str(OUTPUT_DIR),
        help="Directory for output CSV files.",
    )
    parser.add_argument(
        "--db",
        default=DEFAULT_DB_NAME,
        help="PostgreSQL database name for direct loading.",
    )
    parser.add_argument(
        "--skip-db-load",
        action="store_true",
        help="Only write CSV outputs and skip PostgreSQL loading.",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Enable a small LLM enrichment pass for rule-positive candidates.",
    )
    parser.add_argument(
        "--llm-max-rows",
        type=int,
        default=20,
        help="Max number of rule-positive rows to enrich with LLM per run.",
    )
    return parser.parse_args()


def load_outputs_to_postgres(db_name: str) -> None:
    loader_path = ROOT / "src" / "capabilities" / "storage" / "load_task1.py"
    subprocess.run(
        ["python3", str(loader_path), "--db", db_name, "--quiet"],
        check=True,
        cwd=str(ROOT),
    )


def build_candidate_row(row: Dict[str, str], result: CandidateResult) -> Dict[str, object]:
    full_text = f'{row["title"]} {row["content"]}'
    _, subject_hits = choose_label(full_text, ACTIVE_SUBJECT_RULES, SUBJECT_DEFAULT)
    _, industry_hits = choose_label(full_text, ACTIVE_INDUSTRY_RULES, INDUSTRY_DEFAULT)
    _, predictability_hits = choose_label(full_text, ACTIVE_PREDICTABILITY_RULES, PREDICTABILITY_DEFAULT)
    _, duration_hits = choose_label(full_text, ACTIVE_DURATION_RULES, DURATION_DEFAULT)
    evidence = (
        result.evidence
        + f"; rule_version={RULE_VERSION}"
        + "; dimensions="
        + "|".join(
            [
                "subject:" + (",".join(subject_hits) if subject_hits else "none"),
                "industry:" + (",".join(industry_hits) if industry_hits else "none"),
                "predictability:" + (",".join(predictability_hits) if predictability_hits else "none"),
                "duration:" + (",".join(duration_hits) if duration_hits else "none"),
            ]
        )
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


def build_structured_row(row: Dict[str, str], result: CandidateResult) -> Dict[str, object]:
    full_text = f'{row["title"]} {row["content"]}'
    subject_type, subject_hits = choose_label(full_text, ACTIVE_SUBJECT_RULES, SUBJECT_DEFAULT)
    industry_type, industry_hits = choose_label(full_text, ACTIVE_INDUSTRY_RULES, INDUSTRY_DEFAULT)
    predictability_type, predictability_hits = choose_label(full_text, ACTIVE_PREDICTABILITY_RULES, PREDICTABILITY_DEFAULT)
    duration_type, duration_hits = choose_label(full_text, ACTIVE_DURATION_RULES, DURATION_DEFAULT)
    subject_type = freeze_enum(subject_type, EVENT_SUBJECT_ENUM, SUBJECT_DEFAULT)
    industry_type = freeze_enum(industry_type, INDUSTRY_ENUM, INDUSTRY_DEFAULT)
    predictability_type = freeze_enum(predictability_type, PREDICTABILITY_ENUM, PREDICTABILITY_DEFAULT)
    duration_type = freeze_enum(duration_type, DURATION_ENUM, DURATION_DEFAULT)
    subject_entities = extract_subject_entities(full_text)
    sentiment = compute_sentiment(full_text)
    heat_score = compute_heat_score(row["title"], row["source"], result.duplicate_group_size)
    intensity_score = compute_intensity_score(full_text, subject_type, predictability_type)
    impact_scope = compute_impact_scope(subject_type, industry_type, full_text)
    source_type = compute_source_type(row["source"])
    authority_level = compute_authority_level(row["source"], source_type)
    event_subject_subtype = compute_event_subject_subtype(full_text)
    time_orientation = compute_time_orientation(full_text)
    event_stage = compute_event_stage(full_text)
    shock_source_type = compute_shock_source_type(full_text)
    region_scope = compute_region_scope(full_text)
    trigger_word_score = count_keyword_score(full_text, STRONG_TRIGGER_WORDS)
    explicitness_score = compute_explicitness_score(full_text)
    uncertainty_score = count_keyword_score(full_text, UNCERTAINTY_WORDS)
    novelty_score = compute_novelty_score(result.duplicate_group_size)
    amount_scale = compute_amount_scale(full_text)
    event_code_value = compute_event_code(
        subject_type,
        event_subject_subtype,
        duration_type,
        impact_scope,
        shock_source_type,
    )
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
        "event_code": event_code_value,
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


def should_trigger_llm(row: Dict[str, str], result: CandidateResult, structured_preview: Optional[Dict[str, object]]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    score_gap = abs(result.event_score - result.event_threshold)
    if score_gap <= 1:
        reasons.append("borderline_score")
    source_text = row.get("source", "")
    if any(token in source_text for token in LLM_HIGH_VALUE_SOURCE_TOKENS):
        reasons.append("high_value_source")
    if structured_preview:
        if structured_preview.get("industry_type") == "其他":
            reasons.append("industry_other")
        if structured_preview.get("event_subject_type") == SUBJECT_DEFAULT:
            reasons.append("subject_default")
    if result.duplicate_group_size >= 3:
        reasons.append("duplicate_cluster")
    return bool(reasons), reasons


def promote_candidate_result(result: CandidateResult, reason_suffix: str) -> CandidateResult:
    return CandidateResult(
        row=result.row,
        normalized_publish_time=result.normalized_publish_time,
        dedup_key=result.dedup_key,
        duplicate_group_size=result.duplicate_group_size,
        is_event=True,
        filter_reason="llm_promoted_event",
        evidence=result.evidence + f"; llm_override={reason_suffix}",
        score_hint=result.score_hint,
        event_score=result.event_score,
        event_threshold=result.event_threshold,
    )


def can_llm_promote(result: CandidateResult) -> bool:
    return result.filter_reason not in LLM_NO_OVERRIDE_REASONS


import asyncio
import aiohttp
import os

SECRETS_DIR = ROOT / ".secrets"
LLM_KEY_FILE = SECRETS_DIR / "llm_api_key.txt"
LLM_BASE_URL_FILE = SECRETS_DIR / "llm_base_url.txt"
LLM_MODEL_FILE = SECRETS_DIR / "llm_model.txt"

class AsyncLLMClient:
    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        self.api_key = api_key or self._load_key()
        self.base_url = base_url or self._load_base_url()
        self.model = model or self._load_model()

    def _load_key(self) -> str:
        env_key = os.getenv("LLM_API_KEY", "").strip()
        if env_key:
            return env_key
        return self._read_secret_file(LLM_KEY_FILE)

    def _load_base_url(self) -> str:
        env_url = os.getenv("LLM_BASE_URL", "").strip()
        if env_url:
            return env_url.rstrip("/")
        file_url = self._read_secret_file(LLM_BASE_URL_FILE)
        if file_url:
            return file_url.rstrip("/")
        return "https://opencode.ai/zen/v1"

    def _load_model(self) -> str:
        env_model = os.getenv("LLM_MODEL", "").strip()
        if env_model:
            return env_model
        file_model = self._read_secret_file(LLM_MODEL_FILE)
        if file_model:
            return file_model
        return "gpt-5.4-mini"

    def _read_secret_file(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8").strip()
        except Exception:
            return ""

    async def extract_event_data(self, title: str, content: str) -> dict:
        """Call LLM to extract structured event information."""
        if not self.api_key:
            return {}

        prompt = f"""
你是一个专业的金融事件分析专家。请分析以下新闻，并判断它是否属于重要的股市基本面事件。
重要事件包括：产业政策变动、技术突破、重大公司行为（分红/并购/增发/高管变动）、宏观经济数据发布、行业重大突发事件。
不重要的事件包括：普通市场行情波动、非财经类社会新闻、重复新闻、纯技术指标讨论。

请严格返回以下JSON格式（不要包含markdown格式标记）：
{{
  "is_event": true/false,
  "event_name": "简洁的事件名称",
  "subject_type": "Macro/Policy/Industry/Entity/Shock",
  "industry": "涉及行业",
  "sentiment": "Positive/Negative/Neutral",
  "summary": "50字以内的核心内容综述"
}}

新闻标题：{title}
新闻正文：{content[:1000]}
"""
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/chat/completions", json=payload, headers=headers, timeout=30) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        data = json.loads(text)
                        return json.loads(data["choices"][0]["message"]["content"])
                    else:
                        body = await resp.text()
                        print(f"[WARN] LLM API Error: Status {resp.status}; body={body[:300]}")
                        return {}
        except Exception as e:
            print(f"[WARN] LLM API Exception: {e}")
            return {}


class AsyncOllamaClient:
    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen3:8b")

    async def extract_event_data(self, title: str, content: str) -> dict:
        prompt = f"""
你是一个专业的金融事件分析专家。请分析以下新闻，并判断它是否属于重要的股市基本面事件。
重要事件包括：产业政策变动、技术突破、重大公司行为、宏观经济数据发布、行业重大突发事件。
不重要的事件包括：普通市场行情波动、非财经类社会新闻、重复新闻、纯技术指标讨论。

请严格返回 JSON，不要返回 markdown，不要补充解释：
{{
  "is_event": true,
  "event_name": "简洁的事件名称",
  "subject_type": "Policy/Entity/Industry/Macro/Shock",
  "industry": "军工/新能源/消费/科技/其他 之一",
  "sentiment": "Positive/Negative/Neutral",
  "summary": "50字以内摘要"
}}

新闻标题：{title}
新闻正文：{content[:1000]}
"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1},
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/api/generate", json=payload, timeout=60) as resp:
                    text = await resp.text()
                    if resp.status != 200:
                        print(f"[WARN] Ollama API Error: Status {resp.status}; body={text[:300]}")
                        return {}
                    data = json.loads(text)
                    response_text = (data.get("response") or "").strip()
                    if not response_text:
                        return {}
                    return json.loads(response_text)
        except Exception as e:
            print(f"[WARN] Ollama API Exception: {e}")
            return {}

@dataclass
class LLMResultEnrichment:
    is_event_llm: bool = False
    event_name_llm: str = ""
    subject_type_llm: str = ""
    industry_llm: str = ""
    sentiment_llm: str = ""
    summary_llm: str = ""

def normalize_llm_subject(value: str, fallback: str) -> str:
    key = (value or "").strip().lower()
    return freeze_enum(LLM_SUBJECT_MAP.get(key, fallback), EVENT_SUBJECT_ENUM, fallback)


def normalize_llm_industry(value: str, fallback: str) -> str:
    text = (value or "").strip()
    return freeze_enum(text if text in INDUSTRY_ENUM else fallback, INDUSTRY_ENUM, fallback)


def normalize_llm_sentiment(value: str, fallback: str) -> str:
    key = (value or "").strip().lower()
    return freeze_enum(LLM_SENTIMENT_MAP.get(key, fallback), SENTIMENT_ENUM, fallback)


def anchored_subject_type(row: Dict[str, str], current_subject: str) -> str:
    text = f"{row.get('title', '')} {row.get('content', '')}"
    if any(token in text for token in GEO_SUBJECT_ANCHOR_KEYWORDS):
        return "地缘类"
    return current_subject


def anchored_industry_type(row: Dict[str, str], current_industry: str, rule_industry: str) -> str:
    text = f"{row.get('title', '')} {row.get('content', '')}"
    anchored = current_industry
    for label, keywords in INDUSTRY_ANCHOR_RULES.items():
        if any(token in text for token in keywords):
            anchored = label
            break
    if anchored == "其他" and rule_industry and rule_industry != "其他":
        return rule_industry
    return anchored


async def classify_rows_async(
    rows: List[Dict[str, str]], use_llm: bool = False, llm_max_rows: int = 20
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    """Classify rows with optional LLM second pass."""
    client = AsyncLLMClient()
    ollama_client = AsyncOllamaClient()
    semaphore = asyncio.Semaphore(5) # Concurrency limit to avoid rate limits
    
    # First Pass: Deterministic Rules (Fast & Free)
    duplicate_counts = Counter(dedup_key(row) for row in rows)
    candidate_results = []
    for row in rows:
        candidate_results.append(detect_event(row, duplicate_counts[dedup_key(row)]))
    
    llm_budget = 0

    async def process_one(row, res, allow_llm: bool):
        structured_preview = build_structured_row(row, res)
        llm_trigger, llm_reasons = should_trigger_llm(row, res, structured_preview)

        # Remote compatible API first when enabled and this row is selected for LLM assist.
        if allow_llm and llm_trigger and use_llm and client.api_key:
            async with semaphore:
                llm_data = await client.extract_event_data(row["title"], row["content"])
                if llm_data:
                    effective_result = res
                    if (
                        not res.is_event
                        and llm_data.get("is_event")
                        and res.event_score >= res.event_threshold - 1
                        and can_llm_promote(res)
                    ):
                        effective_result = promote_candidate_result(res, "remote_llm_borderline")
                    candidate_row = build_candidate_row(row, effective_result)
                    structured_row = build_structured_row(row, effective_result) if effective_result.is_event else None
                    if structured_row is None:
                        return candidate_row, None
                    llm_subject = normalize_llm_subject(
                        llm_data.get("subject_type", ""), structured_row["event_subject_type"]
                    )
                    llm_industry = normalize_llm_industry(
                        llm_data.get("industry", ""), structured_row["industry_type"]
                    )
                    llm_sentiment = normalize_llm_sentiment(
                        llm_data.get("sentiment", ""), structured_row["sentiment"]
                    )
                    llm_summary = (llm_data.get("summary") or structured_row["event_summary"]).strip()[:120]
                    llm_event_name = (llm_data.get("event_name") or structured_row["event_name"]).strip()[:80]
                    llm_subject = anchored_subject_type(row, llm_subject)
                    llm_industry = anchored_industry_type(row, llm_industry, structured_row["industry_type"])
                    structured_row.update({
                        "event_name": llm_event_name,
                        "event_subject_type": llm_subject,
                        "industry_type": llm_industry,
                        "sentiment": llm_sentiment,
                        "event_summary": llm_summary,
                        "classification_evidence": structured_row["classification_evidence"]
                        + f"|llm=1|llm_backend=remote|llm_trigger={','.join(llm_reasons)}|llm_subject={llm_subject}|llm_industry={llm_industry}|llm_sentiment={llm_sentiment}",
                    })
                    return candidate_row, structured_row
        if allow_llm and llm_trigger and use_llm:
            async with semaphore:
                llm_data = await ollama_client.extract_event_data(row["title"], row["content"])
                if llm_data:
                    effective_result = res
                    if (
                        not res.is_event
                        and llm_data.get("is_event")
                        and res.event_score >= res.event_threshold - 1
                        and can_llm_promote(res)
                    ):
                        effective_result = promote_candidate_result(res, "ollama_llm_borderline")
                    candidate_row = build_candidate_row(row, effective_result)
                    structured_row = build_structured_row(row, effective_result) if effective_result.is_event else None
                    if structured_row is None:
                        return candidate_row, None
                    llm_subject = normalize_llm_subject(
                        llm_data.get("subject_type", ""), structured_row["event_subject_type"]
                    )
                    llm_industry = normalize_llm_industry(
                        llm_data.get("industry", ""), structured_row["industry_type"]
                    )
                    llm_sentiment = normalize_llm_sentiment(
                        llm_data.get("sentiment", ""), structured_row["sentiment"]
                    )
                    llm_summary = (llm_data.get("summary") or structured_row["event_summary"]).strip()[:120]
                    llm_event_name = (llm_data.get("event_name") or structured_row["event_name"]).strip()[:80]
                    llm_subject = anchored_subject_type(row, llm_subject)
                    llm_industry = anchored_industry_type(row, llm_industry, structured_row["industry_type"])
                    structured_row.update({
                        "event_name": llm_event_name,
                        "event_subject_type": llm_subject,
                        "industry_type": llm_industry,
                        "sentiment": llm_sentiment,
                        "event_summary": llm_summary,
                        "classification_evidence": structured_row["classification_evidence"]
                        + f"|llm=1|llm_backend=ollama|llm_trigger={','.join(llm_reasons)}|llm_subject={llm_subject}|llm_industry={llm_industry}|llm_sentiment={llm_sentiment}",
                    })
                    return candidate_row, structured_row

        # Fallback to rules-only
        return build_candidate_row(row, res), (structured_preview if res.is_event else None)

    tasks = []
    for row, res in zip(rows, candidate_results):
        preview = build_structured_row(row, res)
        trigger, _ = should_trigger_llm(row, res, preview)
        allow_llm = False
        if trigger and llm_budget < llm_max_rows:
            allow_llm = True
            llm_budget += 1
        tasks.append(process_one(row, res, allow_llm))
    results = await asyncio.gather(*tasks)
    
    candidate_rows = []
    structured_rows = []
    seen_structured_dedup_keys = set()
    
    for row, (cand, struct) in zip(rows, results):
        candidate_rows.append(cand)
        if struct:
            # Simple dedup for structured events
            d_key = dedup_key(row)
            if d_key not in seen_structured_dedup_keys:
                seen_structured_dedup_keys.add(d_key)
                structured_rows.append(struct)
                
    return candidate_rows, structured_rows


def load_rows_from_db(db: str) -> List[Dict[str, str]]:
    """Load latest raw_documents from database for classification."""
    import psycopg
    from capabilities.storage.db_guard import dsn_for
    
    sql = """
        SELECT source, title, content, publish_time::text, url, symbol_or_subject 
        FROM raw_documents
        ORDER BY publish_time DESC
    """
    with psycopg.connect(dsn_for(db)) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]


async def run_classification_pipeline(
    db: str,
    input_rows: Optional[List[Dict[str, str]]] = None,
    use_llm: bool = False,
    llm_max_rows: int = 20,
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    """Orchestrate classification and persist results into stage and final tables."""
    from capabilities.storage.load_task1 import insert_final_tables, load_stage_tables
    
    rows = input_rows if input_rows is not None else load_rows_from_db(db)
    if not rows:
        print("No documents found for classification.")
        return [], []
        
    candidate_rows, structured_rows = await classify_rows_async(
        rows, use_llm=use_llm, llm_max_rows=llm_max_rows
    )
    
    load_stage_tables(db, [], candidate_rows, structured_rows)
    insert_final_tables(db)
    return candidate_rows, structured_rows


def main() -> None:
    args = parse_args()
    
    async def _run():
        if args.inputs:
            input_paths = [Path(p).resolve() for p in args.inputs]
            rows = load_rows_from_inputs(input_paths)
            print(f"Loaded {len(rows)} rows from {len(input_paths)} input file(s)")
            candidate_rows, structured_rows = await classify_rows_async(
                rows, use_llm=args.use_llm, llm_max_rows=args.llm_max_rows
            )
        else:
            print(f"No input files provided. Reading from database: {args.db}")
            if args.skip_db_load:
                rows = load_rows_from_db(args.db)
                candidate_rows, structured_rows = await classify_rows_async(
                    rows, use_llm=args.use_llm, llm_max_rows=args.llm_max_rows
                )
            else:
                candidate_rows, structured_rows = await run_classification_pipeline(
                    args.db, use_llm=args.use_llm, llm_max_rows=args.llm_max_rows
                )

        output_dir = Path(args.output_dir).resolve()
        raw_output_path = output_dir / "raw_event_candidates.csv"
        structured_output_path = output_dir / "structured_events.csv"
        ensure_output_dir(output_dir)
        
        write_csv(raw_output_path, candidate_rows, RAW_CANDIDATE_FIELDS)
        write_csv(structured_output_path, structured_rows, STRUCTURED_EVENT_FIELDS)

        print(f"Wrote {len(candidate_rows)} raw candidates to {raw_output_path}")
        print(f"Wrote {len(structured_rows)} structured events to {structured_output_path}")

    asyncio.run(_run())


if __name__ == "__main__":
    main()
