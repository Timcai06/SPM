#!/usr/bin/env python3
"""Structured-event feature enrichment domain helpers."""

from __future__ import annotations

import json
import math
import re
from typing import Any, Dict, List, Tuple

SW_L1_KEYWORDS: List[Tuple[str, str, Tuple[str, ...]]] = [
    ("801010", "农林牧渔", ("农业", "养殖", "种业", "饲料", "渔业")),
    ("801020", "采掘", ("煤炭", "石油", "天然气", "矿业")),
    ("801030", "化工", ("化工", "化纤", "化学", "农药", "化肥")),
    ("801040", "钢铁", ("钢铁", "特钢", "钢材")),
    ("801050", "有色金属", ("有色", "铜", "铝", "锂", "钴", "镍", "稀土")),
    ("801080", "电子", ("半导体", "芯片", "电子", "面板", "元器件")),
    ("801110", "家用电器", ("家电", "白电", "黑电")),
    ("801120", "食品饮料", ("食品", "饮料", "白酒", "乳品", "啤酒")),
    ("801130", "纺织服饰", ("纺织", "服饰", "服装")),
    ("801140", "轻工制造", ("轻工", "造纸", "包装")),
    ("801150", "医药生物", ("医药", "药", "制药", "生物", "医疗")),
    ("801160", "公用事业", ("电力", "燃气", "水务", "公用事业")),
    ("801170", "交通运输", ("航运", "港口", "物流", "铁路", "机场")),
    ("801180", "房地产", ("地产", "房地产", "物业", "住宅开发")),
    ("801200", "商贸零售", ("零售", "商贸", "百货", "电商")),
    ("801210", "社会服务", ("旅游", "酒店", "教育", "社会服务")),
    ("801230", "综合", ("综合",)),
    ("801710", "建筑材料", ("建材", "水泥", "玻璃", "玻纤")),
    ("801720", "建筑装饰", ("建筑", "装饰", "基建", "工程")),
    ("801730", "电力设备", ("电力设备", "光伏", "风电", "储能", "锂电")),
    ("801740", "国防军工", ("军工", "国防", "战机", "导弹", "舰船")),
    ("801750", "计算机", ("计算机", "软件", "信创", "云计算", "大数据")),
    ("801760", "传媒", ("传媒", "游戏", "影视", "广告")),
    ("801770", "通信", ("通信", "5G", "运营商", "光模块")),
    ("801780", "银行", ("银行", "信贷", "存款", "贷款")),
    ("801790", "非银金融", ("证券", "保险", "基金", "非银")),
    ("801880", "汽车", ("汽车", "整车", "零部件", "新能源车")),
    ("801890", "机械设备", ("机械", "机床", "机器人", "自动化")),
    ("801950", "煤炭", ("煤炭",)),
    ("801960", "石油石化", ("石油石化", "炼化")),
    ("801970", "环保", ("环保", "污水", "固废", "减排")),
]
COUNTRY_KEYWORDS = (
    "美国", "中国", "日本", "韩国", "俄罗斯", "乌克兰", "伊朗", "以色列", "印度",
    "巴基斯坦", "欧盟", "英国", "德国", "法国", "东南亚",
)
PROVINCE_KEYWORDS = (
    "北京", "上海", "天津", "重庆", "广东", "江苏", "浙江", "山东", "河南", "四川", "湖北", "湖南",
    "安徽", "福建", "河北", "陕西", "山西", "辽宁", "吉林", "黑龙江", "江西", "广西", "云南", "贵州",
    "海南", "甘肃", "青海", "宁夏", "新疆", "西藏", "内蒙古",
)
CITY_SUFFIX_PATTERN = re.compile(r"[\u4e00-\u9fa5]{2,8}(?:市|区|县)")
CHAIN_STAGE_KEYWORDS = {
    "上游资源材料": ("上游", "资源", "原料", "矿", "材料"),
    "设备零部件": ("设备", "零部件", "器件"),
    "中游制造": ("制造", "加工", "生产"),
    "下游应用": ("应用", "终端", "消费端", "装机"),
    "渠道服务": ("渠道", "服务", "经销"),
    "配套保障": ("配套", "保障", "物流", "运维"),
}
POSITIVE_WORDS = ("利好", "增长", "突破", "获批", "中标", "签约", "增持", "回购")
NEGATIVE_WORDS = ("利空", "下滑", "亏损", "处罚", "风险", "停产", "冲突升级")
UNCERTAINTY_WORDS = ("拟", "计划", "预计", "可能", "或将", "征求意见", "草案", "预案", "研究")
GRADUAL_WORDS = ("持续", "逐步", "加速", "推进", "深化", "优化", "完善")
SHOCK_RULES = (
    ("自然灾害", ("地震", "台风", "洪水", "极端天气", "灾害")),
    ("公共卫生", ("疫情", "传染病", "公共卫生")),
    ("安全事故", ("事故", "爆炸", "停产", "火灾")),
    ("地缘政治", ("冲突", "战争", "制裁", "中东", "印巴", "伊朗")),
    ("政策制度", ("政策", "通知", "办法", "制度", "监管")),
    ("金融事件", ("违约", "挤兑", "流动性", "股灾", "金融风险")),
    ("供应链冲击", ("断供", "供应链", "航运受阻", "物流受阻")),
    ("技术革新", ("技术突破", "新技术", "新工艺", "创新")),
)


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _parse_json_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    raw = _safe_text(value)
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except Exception:
        return []
    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]
    return []


def map_sw_l1_industries(text: str) -> List[Tuple[str, str]]:
    return [(code, name) for code, name, keywords in SW_L1_KEYWORDS if any(k in text for k in keywords)]


def sentiment_score_0_100(text: str, label: str) -> int:
    pos = sum(1 for word in POSITIVE_WORDS if word in text)
    neg = sum(1 for word in NEGATIVE_WORDS if word in text)
    base = 62 if label == "利好" else 38 if label == "利空" else 50
    return max(0, min(base + pos * 5 - neg * 5, 100))


def extract_amount_rmb(text: str) -> Tuple[float | None, float | None]:
    matches = re.findall(r"(\d+(?:\.\d+)?)\s*(万亿|亿|万元|亿元|美元|亿美元)", text)
    if not matches:
        return None, None
    converted: List[float] = []
    for number, unit in matches:
        value = float(number)
        if unit == "万亿":
            value *= 1_0000_0000_0000
        elif unit in ("亿", "亿元"):
            value *= 1_0000_0000
        elif unit == "万元":
            value *= 1_0000
        elif unit == "亿美元":
            value *= 7.2 * 1_0000_0000
        elif unit == "美元":
            value *= 7.2
        converted.append(value)
    max_amount = max(converted)
    return max_amount, round(math.log(max_amount + 1, 10), 6)


def classify_source_credibility(source_type: str, authority_level: str) -> str:
    if source_type in ("官方文件", "监管/交易所", "公司公告"):
        return "官方原文"
    if authority_level in ("central", "ministry", "exchange", "listed_company", "top_media"):
        return "权威转述"
    return "单一媒体"


def choose_predictability(text: str, current: str) -> str:
    return "渐进演化型" if any(word in text for word in GRADUAL_WORDS) else (current or "预披露型")


def choose_shock_source(text: str, current: str) -> str:
    for label, words in SHOCK_RULES:
        if any(word in text for word in words):
            return label
    return current or "其他"


def region_counts(text: str) -> Tuple[int, int, int]:
    provinces = {name for name in PROVINCE_KEYWORDS if name in text}
    cities = set(CITY_SUFFIX_PATTERN.findall(text))
    countries = {name for name in COUNTRY_KEYWORDS if name in text}
    return len(provinces), len(cities), len(countries)


def chain_stages(text: str) -> List[str]:
    return [stage for stage, keywords in CHAIN_STAGE_KEYWORDS.items() if any(keyword in text for keyword in keywords)]


def choose_impact_scope(text: str, company_count: int, industry_count: int, province_count: int, country_count: int) -> str:
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
    if _safe_text(row.get("event_subject_subtype")) not in ("", "未细分", "公司事项", "行业跟踪", "政策动态", "宏观跟踪", "地缘事件"):
        score += 0.15
    if _safe_text(row.get("industry_type")) != "其他":
        score += 0.15
    if _safe_text(row.get("sentiment")) != "中性":
        score += 0.1
    if _parse_json_list(row.get("subject_entities")):
        score += 0.1
    score += min(int(row.get("trigger_word_score") or 0) * 0.03, 0.12)
    uncertainty = sum(1 for word in UNCERTAINTY_WORDS if word in text)
    score -= min(uncertainty * 0.02, 0.12)
    return round(max(0.05, min(score, 0.99)), 4)


def enrich_structured_event_row(row: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(row)
    event_text = " ".join([
        _safe_text(row.get("event_name")),
        _safe_text(row.get("event_summary")),
        _safe_text(row.get("classification_evidence")),
    ])
    sw_hits = map_sw_l1_industries(event_text)
    sw_code, sw_name = sw_hits[0] if sw_hits else ("", "其他")
    entities = _parse_json_list(row.get("subject_entities"))
    company_count = len(entities)
    industry_count = len({name for _, name in sw_hits}) if sw_hits else 0
    province_count, city_count, country_count = region_counts(event_text)
    chain = chain_stages(event_text)
    amount_max, amount_log = extract_amount_rmb(event_text)

    out["sw_l1_industry_code"] = sw_code
    out["sw_l1_industry"] = sw_name
    out["industry_count"] = str(industry_count)
    out["sentiment_score_0_100"] = str(sentiment_score_0_100(event_text, _safe_text(row.get("sentiment"))))
    out["source_credibility_type"] = classify_source_credibility(
        _safe_text(row.get("source_type")), _safe_text(row.get("authority_level"))
    )
    out["amount_max_rmb"] = "" if amount_max is None else f"{amount_max:.6f}"
    out["amount_log_rmb"] = "" if amount_log is None else f"{amount_log:.6f}"
    out["company_count"] = str(company_count)
    out["province_count"] = str(province_count)
    out["city_count"] = str(city_count)
    out["country_count"] = str(country_count)
    out["chain_stage_count"] = str(len(chain))
    out["chain_stages"] = json.dumps(chain, ensure_ascii=False)
    out["predictability_type"] = choose_predictability(event_text, _safe_text(row.get("predictability_type")))
    out["shock_source_type"] = choose_shock_source(event_text, _safe_text(row.get("shock_source_type")))
    out["impact_scope"] = choose_impact_scope(
        event_text, company_count, industry_count, province_count, country_count
    )
    out["classification_confidence"] = str(compute_classification_confidence(out, event_text))
    return out

