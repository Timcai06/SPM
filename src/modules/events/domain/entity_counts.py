#!/usr/bin/env python3
"""Entity and supply-chain count helpers."""

from __future__ import annotations

import json
import re
from typing import Any, List, Tuple

COUNTRY_KEYWORDS = (
    "美国",
    "中国",
    "日本",
    "韩国",
    "俄罗斯",
    "乌克兰",
    "伊朗",
    "以色列",
    "印度",
    "巴基斯坦",
    "欧盟",
    "英国",
    "德国",
    "法国",
    "东南亚",
)
PROVINCE_KEYWORDS = (
    "北京",
    "上海",
    "天津",
    "重庆",
    "广东",
    "江苏",
    "浙江",
    "山东",
    "河南",
    "四川",
    "湖北",
    "湖南",
    "安徽",
    "福建",
    "河北",
    "陕西",
    "山西",
    "辽宁",
    "吉林",
    "黑龙江",
    "江西",
    "广西",
    "云南",
    "贵州",
    "海南",
    "甘肃",
    "青海",
    "宁夏",
    "新疆",
    "西藏",
    "内蒙古",
)
CITY_SUFFIX_PATTERN = re.compile(r"[\u4e00-\u9fa5]{2,8}(?:市|区|县)")
CHAIN_STAGE_KEYWORDS = {
    "上游资源材料": ("上游", "资源", "原料", "矿", "材料", "矿山", "锂矿", "稀土", "铜箔", "硅料"),
    "设备零部件": ("设备", "零部件", "器件", "模组", "组件", "控制器", "逆变器", "传感器"),
    "中游制造": ("制造", "加工", "生产", "装配", "产线", "代工", "封测", "电芯"),
    "下游应用": ("应用", "终端", "消费端", "装机", "车端", "电站", "工业端", "商业化"),
    "渠道服务": ("渠道", "服务", "经销", "零售网络", "销售网络", "代理"),
    "配套保障": ("配套", "保障", "物流", "运维", "仓储", "认证", "测试"),
}


def parse_json_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    raw = str(value or "").strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except Exception:
        return []
    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]
    return []


def region_counts(text: str) -> Tuple[int, int, int]:
    provinces = {name for name in PROVINCE_KEYWORDS if name in text}
    cities = set(CITY_SUFFIX_PATTERN.findall(text))
    countries = {name for name in COUNTRY_KEYWORDS if name in text}
    return len(provinces), len(cities), len(countries)


def chain_stages(text: str) -> List[str]:
    return [
        stage
        for stage, keywords in CHAIN_STAGE_KEYWORDS.items()
        if any(keyword in text for keyword in keywords)
    ]
