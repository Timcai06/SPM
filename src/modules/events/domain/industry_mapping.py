#!/usr/bin/env python3
"""Industry mapping helpers for structured event features."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Tuple

SW_L1_KEYWORDS: List[Tuple[str, str, Tuple[str, ...]]] = [
    ("801010", "农林牧渔", ("农业", "养殖", "种业", "饲料", "渔业", "生猪", "农产品")),
    ("801020", "采掘", ("采掘", "矿业", "油气", "天然气开采")),
    ("801030", "化工", ("化工", "化纤", "化学", "农药", "化肥", "钛白粉", "氟化工", "基础化工")),
    ("801040", "钢铁", ("钢铁", "特钢", "钢材", "螺纹钢", "不锈钢")),
    ("801050", "有色金属", ("有色", "铜", "铝", "锂", "钴", "镍", "稀土", "黄金", "工业金属")),
    ("801080", "电子", ("半导体", "芯片", "电子", "面板", "元器件", "封测", "消费电子", "显示器件")),
    ("801110", "家用电器", ("家电", "白电", "黑电", "冰箱", "空调", "洗衣机")),
    ("801120", "食品饮料", ("食品", "饮料", "白酒", "乳品", "啤酒", "调味品", "预制菜")),
    ("801130", "纺织服饰", ("纺织", "服饰", "服装", "鞋帽", "家纺")),
    ("801140", "轻工制造", ("轻工", "造纸", "包装", "家居", "文娱用品")),
    ("801150", "医药生物", ("医药", "药", "制药", "生物", "医疗", "创新药", "中药", "器械", "CXO")),
    ("801160", "公用事业", ("电力", "燃气", "水务", "公用事业", "火电", "水电")),
    ("801170", "交通运输", ("航运", "港口", "物流", "铁路", "机场", "快递", "航空运输")),
    ("801180", "房地产", ("地产", "房地产", "物业", "住宅开发", "商业地产", "保障房")),
    ("801200", "商贸零售", ("零售", "商贸", "百货", "电商", "超市", "消费连锁")),
    ("801210", "社会服务", ("旅游", "酒店", "教育", "社会服务", "景区", "免税", "人力服务")),
    ("801230", "综合", ("综合",)),
    ("801710", "建筑材料", ("建材", "水泥", "玻璃", "玻纤", "装修建材")),
    ("801720", "建筑装饰", ("建筑", "装饰", "基建", "工程", "园林", "建筑施工")),
    ("801730", "电力设备", ("电力设备", "光伏", "风电", "储能", "锂电", "逆变器", "输变电", "电池回收")),
    ("801740", "国防军工", ("军工", "国防", "战机", "导弹", "舰船", "雷达", "卫星导航", "低空防务")),
    ("801750", "计算机", ("计算机", "软件", "信创", "云计算", "大数据", "操作系统", "AI软件", "工业软件")),
    ("801760", "传媒", ("传媒", "游戏", "影视", "广告", "出版", "互联网内容")),
    ("801770", "通信", ("通信", "5G", "运营商", "光模块", "光通信", "通信设备")),
    ("801780", "银行", ("银行", "信贷", "存款", "贷款", "商业银行")),
    ("801790", "非银金融", ("证券", "保险", "基金", "非银", "期货", "券商", "资管")),
    ("801880", "汽车", ("汽车", "整车", "零部件", "新能源车", "车企", "汽车电子", "智能驾驶")),
    ("801890", "机械设备", ("机械", "机床", "机器人", "自动化", "工程机械", "仪器设备", "工业母机")),
    ("801950", "煤炭", ("煤炭", "焦煤", "动力煤")),
    ("801960", "石油石化", ("石油石化", "炼化", "石油", "炼油", "化工炼化")),
    ("801970", "环保", ("环保", "污水", "固废", "减排", "节能环保", "环境治理")),
]

COARSE_INDUSTRY_HINTS: Dict[str, Tuple[str, ...]] = {
    "军工": ("国防军工",),
    "新能源": ("电力设备", "汽车", "有色金属", "公用事业"),
    "科技": ("电子", "计算机", "通信", "传媒"),
    "消费": ("食品饮料", "医药生物", "商贸零售", "社会服务", "家用电器", "房地产", "银行", "非银金融"),
}

SW_L1_NAMES = tuple(name for _, name, _ in SW_L1_KEYWORDS)


def map_sw_l1_industries(text: str) -> List[Tuple[str, str]]:
    return [
        (code, name)
        for code, name, keywords in SW_L1_KEYWORDS
        if any(keyword in text for keyword in keywords)
    ]


def score_sw_l1_industries(
    title: str,
    summary: str,
    content: str,
    evidence: str,
    source: str,
    coarse_industry: str,
) -> List[Tuple[str, str, float]]:
    title_text = title or ""
    summary_text = summary or ""
    body_text = content or ""
    intro_text = body_text[:240]
    evidence_text = evidence or ""
    score_map: Dict[Tuple[str, str], float] = defaultdict(float)

    for code, name, keywords in SW_L1_KEYWORDS:
        for keyword in keywords:
            if keyword in title_text:
                score_map[(code, name)] += 3.0
            if keyword in summary_text:
                score_map[(code, name)] += 2.5
            if keyword in intro_text:
                score_map[(code, name)] += 2.0
            elif keyword in body_text:
                score_map[(code, name)] += 1.0
            if keyword in evidence_text:
                score_map[(code, name)] += 1.5
        if source and any(token in source for token in keywords):
            score_map[(code, name)] += 1.5

    for code, name in list(score_map.keys()):
        if name in COARSE_INDUSTRY_HINTS.get(coarse_industry, ()):
            score_map[(code, name)] += 0.8

    scored = [(code, name, score) for (code, name), score in score_map.items() if score > 0]
    scored.sort(key=lambda item: item[2], reverse=True)
    return scored


def choose_primary_sw_l1(
    title: str,
    summary: str,
    content: str,
    evidence: str,
    source: str,
    coarse_industry: str,
) -> Tuple[str, str, int]:
    scored = score_sw_l1_industries(title, summary, content, evidence, source, coarse_industry)
    if not scored:
        return "", "其他", 0
    top_code, top_name, top_score = scored[0]
    related = [item for item in scored if item[2] >= max(2.0, top_score - 1.5)]
    return top_code, top_name, len(related)
