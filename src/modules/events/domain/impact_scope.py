#!/usr/bin/env python3
"""Impact scope, predictability, shock source, and confidence helpers."""

from __future__ import annotations

from typing import Any, Dict, List

from modules.events.domain.entity_counts import parse_json_list

UNCERTAINTY_WORDS = ("拟", "计划", "预计", "可能", "或将", "征求意见", "草案", "预案", "研究")
GRADUAL_WORDS = ("持续", "逐步", "加速", "推进", "深化", "优化", "完善")
SHOCK_RULES = (
    ("自然灾害", ("地震", "台风", "洪水", "极端天气", "灾害")),
    ("公共卫生", ("疫情", "传染病", "公共卫生")),
    ("安全事故", ("事故", "爆炸", "停产", "火灾", "安全事件", "召回")),
    ("地缘政治", ("冲突", "战争", "制裁", "中东", "印巴", "伊朗", "关税战", "边境")),
    ("政策制度", ("政策", "通知", "办法", "制度", "监管", "征求意见", "条例", "实施方案")),
    ("金融事件", ("违约", "挤兑", "流动性", "股灾", "金融风险", "暴跌", "融资收紧", "债务")),
    ("供应链冲击", ("断供", "供应链", "航运受阻", "物流受阻", "停航", "缺货", "产能紧张")),
    ("技术革新", ("技术突破", "新技术", "新工艺", "创新", "新产品", "大模型", "临床突破")),
)
GENERIC_SUBTYPES = ("", "未细分", "公司事项", "行业跟踪", "政策动态", "宏观跟踪", "地缘事件")


def safe_text(value: Any) -> str:
    return str(value or "").strip()


def choose_predictability(text: str, current: str) -> str:
    return "渐进演化型" if any(word in text for word in GRADUAL_WORDS) else (current or "预披露型")


def choose_shock_source(text: str, current: str) -> str:
    for label, words in SHOCK_RULES:
        if any(word in text for word in words):
            return label
    return current or "其他"


def choose_impact_scope(
    text: str,
    company_count: int,
    industry_count: int,
    province_count: int,
    country_count: int,
) -> str:
    if country_count >= 2 or "全球" in text:
        return "全球面"
    if "全国" in text:
        return "全国面"
    if province_count >= 2 or any(word in text for word in ("城市群", "区域")):
        return "区域面"
    if industry_count >= 2:
        return "跨行业面"
    if industry_count == 1:
        return "行业面"
    if any(word in text for word in ("产业链", "上下游", "供应链")):
        return "产业链面"
    if company_count >= 2:
        return "多主体"
    return "单主体"


def compute_classification_confidence(row: Dict[str, Any], text: str) -> float:
    score = 0.35
    if safe_text(row.get("event_subject_subtype")) not in GENERIC_SUBTYPES:
        score += 0.15
    if safe_text(row.get("industry_type")) != "其他":
        score += 0.15
    if safe_text(row.get("sentiment")) != "中性":
        score += 0.1
    if parse_json_list(row.get("subject_entities")):
        score += 0.1
    score += min(int(row.get("trigger_word_score") or 0) * 0.03, 0.12)
    uncertainty = sum(1 for word in UNCERTAINTY_WORDS if word in text)
    score -= min(uncertainty * 0.02, 0.12)
    return round(max(0.05, min(score, 0.99)), 4)
