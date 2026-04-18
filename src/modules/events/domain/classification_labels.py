#!/usr/bin/env python3
"""Static enums, defaults, and scoring constants for event classification."""

from __future__ import annotations

RULE_VERSION = "task1_rules_v1"

EVENT_SCORE_THRESHOLD = 2
EVENT_DUPLICATE_BONUS_CAP = 3

EVENT_SUBJECT_ENUM = ("政策类", "公司类", "行业类", "宏观类", "地缘类")
DURATION_ENUM = ("脉冲型", "中期型", "长尾型")
PREDICTABILITY_ENUM = ("突发型", "预披露型")
INDUSTRY_ENUM = ("军工", "新能源", "消费", "科技", "其他")
IMPACT_SCOPE_ENUM = ("全市场", "行业", "个股链条")
SENTIMENT_ENUM = ("利好", "利空", "中性")

SUBJECT_DEFAULT = "行业类"
DURATION_DEFAULT = "中期型"
PREDICTABILITY_DEFAULT = "预披露型"
INDUSTRY_DEFAULT = "其他"
IMPACT_SCOPE_DEFAULT = "行业"

SOURCE_WEIGHT_DEFAULT = 0.6
HEAT_SOURCE_MULTIPLIER = 40
HEAT_TITLE_PER_HIT = 12
HEAT_TITLE_CAP = 24
HEAT_DUPLICATE_PER_COUNT = 12
HEAT_DUPLICATE_CAP = 36
HEAT_TOTAL_CAP = 100

INTENSITY_BASE_BY_SUBJECT = {
    "地缘类": 82,
    "政策类": 72,
    "公司类": 68,
    "行业类": 64,
    "宏观类": 75,
}
INTENSITY_DEFAULT_BASE = 55
INTENSITY_SURPRISE_BONUS = 8
INTENSITY_SHOCK_BONUS = 6
INTENSITY_POLICY_BONUS = 4
INTENSITY_TOTAL_CAP = 100

