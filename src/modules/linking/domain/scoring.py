#!/usr/bin/env python3
"""Scoring rules for event-company linking."""

from __future__ import annotations

import json

EVENT_INDUSTRY_TO_COMPANY = {
    "军工": "军工",
    "新能源": "新能源",
    "科技": "科技",
    "消费": "消费",
}

CNINFO_L1_TO_CATEGORY = {
    "C26": "新能源",
    "C27": "消费",
    "C28": "消费",
    "C36": "新能源",
    "C38": "新能源",
    "C39": "科技",
    "C40": "科技",
    "I63": "科技",
    "I64": "科技",
    "I65": "科技",
    "J66": "其他",
    "J67": "其他",
    "J68": "其他",
    "J69": "其他",
    "Z03": "军工",
    "Z08": "科技",
    "A": "消费",
    "C": "消费",
    "D": "新能源",
    "E": "消费",
    "F": "消费",
    "G": "消费",
    "H": "消费",
    "K": "消费",
    "L": "消费",
    "M": "消费",
    "N": "消费",
    "O": "消费",
    "P": "科技",
    "Q": "消费",
    "R": "消费",
    "S": "消费",
}

EVENT_KEYWORDS = {
    "军工": ["军工", "战机", "导弹", "无人机", "航空", "空战", "低空", "国防", "航天", "舰船", "雷达", "坦克", "军品", "装备", "高超音速"],
    "新能源": ["新能源", "储能", "电池", "电网", "光伏", "输变电", "充电桩", "锂电", "风电", "逆变器", "硅料", "碳酸锂", "氢能", "核电", "电车", "电动", "碳中和", "绿电"],
    "科技": ["AI", "人工智能", "机器人", "算力", "芯片", "数字化", "招标投标", "半导体", "集成电路", "5G", "通信", "物联网", "云计算", "大数据", "软件", "智能化", "大模型", "数字人民币", "低空经济", "信创", "自动驾驶"],
    "消费": ["消费", "旅游", "酒店", "饮料", "保险", "食品", "白酒", "零售", "餐饮", "家电", "医药", "药", "创新药", "房产", "地产", "银行", "金融", "证券", "医美", "啤酒", "乳品", "中药"],
    "其他": ["政策", "方案", "通知", "信用"],
}
GENERIC_SYMBOLS = {
    "政策/宏观",
    "政策/通知",
    "行业/市场新闻",
    "行业/股市快讯",
    "政策类事件",
    "公司行为事件",
    "行业/技术事件",
    "宏观/地缘事件",
    "印巴空战",
    "印巴冲突",
    "储能政策",
    "机器人技术突破",
}


def l1_to_category(l1: str) -> str:
    if not l1:
        return "其他"
    text = str(l1).strip()
    if text in ("军工", "新能源", "科技", "消费", "金融", "其他"):
        return text
    code = text.split()[0] if " " in text else text[:3] if len(text) >= 3 and text[:1].isalpha() and text[1:3].isdigit() else text
    code = code[:3] if len(code) >= 3 and code[:1].isalpha() and code[1:3].isdigit() else code
    for prefix in (code, code[:2], code[:1]):
        if prefix in CNINFO_L1_TO_CATEGORY:
            return CNINFO_L1_TO_CATEGORY[prefix]
    if code[:1].isalpha() and code[1:3].isdigit():
        return CNINFO_L1_TO_CATEGORY.get(code[:1], "其他")
    return "其他"


def is_specific_symbol(raw_symbol: str) -> bool:
    return raw_symbol.strip().isdigit() and len(raw_symbol.strip()) == 6


def is_generic_event(event: dict) -> bool:
    raw_symbol = (event.get("raw_symbol") or "").strip()
    return raw_symbol in GENERIC_SYMBOLS or not is_specific_symbol(raw_symbol)


def normalize_tags(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
        except Exception:
            parsed = None
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
        return [item.strip() for item in stripped.replace("，", ",").split(",") if item.strip()]
    return [str(value).strip()]


def score_link(event: dict, company: dict) -> tuple[float, dict]:
    raw_title = event.get("raw_title") or ""
    raw_content = event.get("raw_content") or ""
    raw_symbol = (event.get("raw_symbol") or "").strip()
    event_text = " ".join(
        [
            event["event_name"] or "",
            event["event_summary"] or "",
            event["industry_type"] or "",
            event["event_subject_type"] or "",
            raw_title,
            raw_content,
            raw_symbol,
        ]
    )
    company_text = " ".join(
        [
            company["company_name"] or "",
            company["industry_l1"] or "",
            company["industry_l2"] or "",
            company["business_scope"] or "",
            company["core_products"] or "",
            " ".join(normalize_tags(company["concept_tags"])),
        ]
    )
    industry_match = (
        1.0
        if l1_to_category(company["industry_l1"])
        == EVENT_INDUSTRY_TO_COMPANY.get(event["industry_type"], event["industry_type"])
        else 0.0
    )
    text_hits = [kw for kw in EVENT_KEYWORDS.get(event["industry_type"], EVENT_KEYWORDS["其他"]) if kw and kw in company_text]
    event_hits = [kw for kw in EVENT_KEYWORDS.get(event["industry_type"], EVENT_KEYWORDS["其他"]) if kw and kw in event_text]
    company_code = (company["ts_code"] or "").split(".", 1)[0]
    direct_symbol_match = 1.0 if company_code and company_code == raw_symbol else 0.0
    direct_name_match = 1.0 if company["company_name"] and company["company_name"] in f"{raw_title} {raw_content}" else 0.0
    title_name_match = 1.0 if company["company_name"] and company["company_name"] in raw_title else 0.0
    text_similarity = min(len(text_hits) / 3.0, 1.0)
    concept_tags = normalize_tags(company["concept_tags"])
    concept_hits = [tag for tag in concept_tags if tag and tag in event_text]
    concept_match = min(len(concept_hits) / 2.0, 1.0)
    title_keyword_hits = [kw for kw in EVENT_KEYWORDS.get(event["industry_type"], EVENT_KEYWORDS["其他"]) if kw and kw in raw_title]
    title_keyword_match = min(len(title_keyword_hits) / 2.0, 1.0)
    chain_position = 1.0 if title_name_match or direct_name_match else (0.9 if direct_symbol_match else (0.7 if text_hits or concept_hits else 0.2))
    event_match = min((len(event_hits) + len(text_hits)) / 6.0, 1.0)
    generic_event = is_generic_event(event)
    specific_symbol_event = is_specific_symbol(raw_symbol)
    generic_other_event = generic_event and event.get("industry_type") == "其他"
    if specific_symbol_event and direct_symbol_match == 0 and direct_name_match == 0:
        final_score = 0.0
    elif generic_event and direct_symbol_match == 0 and direct_name_match == 0:
        if industry_match == 0:
            final_score = 0.0
        elif len(event_hits) < 1 and len(text_hits) < 1 and concept_match == 0 and title_keyword_match == 0:
            final_score = 0.0
        elif generic_other_event and concept_match == 0 and len(text_hits) < 2 and title_name_match == 0:
            final_score = 0.0
        else:
            final_score = round(
                0.24 * industry_match + 0.18 * text_similarity + 0.18 * concept_match + 0.10 * title_keyword_match + 0.14 * chain_position + 0.10 * event_match,
                4,
            )
    else:
        final_score = round(
            0.28 * industry_match + 0.18 * text_similarity + 0.10 * concept_match + 0.08 * title_keyword_match + 0.20 * chain_position + 0.14 * event_match + 0.06 * direct_symbol_match + 0.04 * direct_name_match,
            4,
        )
    evidence = {
        "matched_keywords": text_hits,
        "matched_concepts": concept_hits,
        "title_keyword_hits": title_keyword_hits,
        "industry_match": bool(industry_match),
        "event_keywords": event_hits,
        "direct_symbol_match": bool(direct_symbol_match),
        "direct_name_match": bool(direct_name_match),
        "title_name_match": bool(title_name_match),
        "generic_event": generic_event,
        "generic_other_event": generic_other_event,
        "specific_symbol_event": specific_symbol_event,
    }
    return final_score, {
        "text_similarity_score": round(text_similarity, 4),
        "concept_match_score": round(concept_match, 4),
        "title_keyword_score": round(title_keyword_match, 4),
        "industry_match_score": round(industry_match, 4),
        "chain_position_score": round(chain_position, 4),
        "event_match_score": round(event_match, 4),
        "direct_symbol_score": round(direct_symbol_match, 4),
        "direct_name_score": round(direct_name_match, 4),
        "evidence": evidence,
    }
