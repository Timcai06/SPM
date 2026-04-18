#!/usr/bin/env python3
"""Event taxonomy based on the 4.13 revised classification framework."""

from __future__ import annotations

EVENT_SUBJECT_TYPES = ("政策类", "公司类", "行业类", "宏观类", "地缘类")
DURATION_TYPES = ("脉冲型", "中期型", "长尾型")
PREDICTABILITY_TYPES = ("突发型", "预披露型", "渐进演化型")
EVENT_STAGES = ("预期", "确认", "执行", "反馈", "落地/执行")
SHOCK_SOURCE_TYPES = (
    "自然灾害",
    "公共卫生",
    "安全事故",
    "地缘政治",
    "政策制度",
    "金融事件",
    "供应链冲击",
    "技术革新",
    "技术系统冲击",
    "其他",
)
IMPACT_SCOPES = (
    "单主体",
    "多主体",
    "产业链面",
    "行业面",
    "跨行业面",
    "区域面",
    "全国面",
    "全球面",
    "个股链条",
    "行业",
    "全市场",
)
TIME_ORIENTATIONS = ("future_oriented", "current_confirmed", "retrospective")
SENTIMENT_LABELS = ("利好", "利空", "中性")
SOURCE_CREDIBILITY_TYPES = ("官方原文", "权威转述", "单一媒体")

STRUCTURED_FEATURE_COLUMNS = (
    "sentiment_score_0_100",
    "amount_max_rmb",
    "amount_log_rmb",
    "source_credibility_type",
    "company_count",
    "industry_count",
    "province_count",
    "city_count",
    "country_count",
    "chain_stage_count",
    "chain_stages",
    "report_count",
    "media_coverage_count",
    "heat_growth_rate",
    "heat_duration_days",
    "disagreement_score",
    "classification_confidence",
)

CHINESE_DELIVERY_COLUMNS = {
    "event_id": "事件ID",
    "event_date": "事件日期",
    "event_name": "事件名称",
    "event_subject_type": "事件驱动主体",
    "event_subject_subtype": "事件细分类别",
    "duration_type": "影响持续周期",
    "predictability_type": "可预测性",
    "sw_l1_industry": "申万一级行业",
    "impact_scope": "事件影响范围",
    "event_stage": "事件阶段属性",
    "shock_source_type": "冲击源类型",
    "sentiment_score_0_100": "事件极性分",
    "amount_log_rmb": "金额对数值",
    "source_credibility_type": "信源可信度",
    "report_count": "报道总量",
    "media_coverage_count": "媒体覆盖度",
    "disagreement_score": "分歧度",
}

