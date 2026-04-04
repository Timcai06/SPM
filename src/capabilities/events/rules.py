"""Frozen rule configuration for Task 1 event identification and labeling."""

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

SUBJECT_RULES = {
    "地缘类": ["空战", "冲突", "地缘", "印巴", "克什米尔", "战机", "局势升级", "伊朗", "中东", "霍尔木兹", "战事", "停火"],
    "政策类": ["政策", "发改委", "国务院", "证监会", "支持", "措施", "规划"],
    "公司类": ["公告", "合同", "并购", "重组", "回购", "定增", "业绩预告", "上市申请", "递表", "IPO", "港交所"],
    "行业类": ["行业", "产业链", "景气", "协会", "供需", "价格上涨", "技术突破", "样机"],
    "宏观类": ["降息", "降准", "CPI", "PPI", "GDP", "出口", "财政"],
}

INDUSTRY_RULES = {
    "军工": ["军工", "战机", "导弹", "无人机", "军品", "空战"],
    "新能源": ["新能源", "储能", "锂电", "光伏", "风电", "电池"],
    "科技": ["科技", "机器人", "芯片", "算力", "AI", "人形机器人", "样机"],
    "消费": ["消费", "白酒", "旅游", "零售", "餐饮"],
}

PREDICTABILITY_RULES = {
    "突发型": ["空战", "爆发", "冲突", "突发", "事故", "击落", "伊朗", "中东", "霍尔木兹", "战事"],
    "预披露型": ["公告", "预告", "政策", "规划", "发布", "签订"],
}

DURATION_RULES = {
    "脉冲型": ["空战", "冲突", "突发", "击落", "热点", "伊朗", "中东", "霍尔木兹", "停火", "战事"],
    "中期型": ["政策", "合同", "示范项目", "订单", "扩产", "发布", "样机"],
    "长尾型": ["规划", "技术突破", "产业趋势", "长期"],
}

POSITIVE_WORDS = ("利好", "支持", "积极", "增长", "提升", "带动", "受益", "突破", "签订")
NEGATIVE_WORDS = ("利空", "下滑", "亏损", "处罚", "暴跌", "风险", "停牌", "冲突升级")
NON_EVENT_KEYWORDS = ("明星", "综艺", "娱乐", "广告", "直播带货")
WEAK_NEUTRAL_KEYWORDS = ("年度报告摘要", "常规信息", "董事会报告", "财务报表")
ROUTINE_ANNOUNCEMENT_KEYWORDS = (
    "会议决议",
    "股东会",
    "业绩说明会",
    "法律意见书",
    "募集资金进行现金管理",
    "自有资金进行现金管理",
    "进展公告",
    "提示性公告",
    "解除质押",
    "质押",
    "持股比例",
    "减持股份",
    "过户登记",
    "辞职",
    "本息兑付",
    "工商变更登记",
    "换发安全生产许可证",
    "临时股东会",
    "持股计划",
)
ANNOUNCEMENT_TEMPLATE_KEYWORDS = (
    "公告类型：",
    "_LC_BULLETIN",
    "_M_BULLETIN",
    "_S_BULLETIN",
    "K_LC_BULLETIN",
    "M_LC_BULLETIN",
    "SZZB",
    "SZCY",
)
GENERIC_ENTITY_TOKENS = ("LC", "ST", "SZCY", "SZZB", "TOP50", "SK", "CP", "CMG", "CCTV", "IPO", "IRGC", "CRU", "CPU", "CPO", "ESG", "AI")
GOV_NARRATIVE_KEYWORDS = (
    "学习贯彻",
    "述评",
    "调研时强调",
    "激励广大干部群众",
    "春光正好",
    "新活力",
    "开创新局面",
    "真抓实干",
    "锐意进取",
    "观察",
    "综述",
)
POLICY_ACTION_KEYWORDS = (
    "印发",
    "发布",
    "出台",
    "通知",
    "意见",
    "方案",
    "措施",
    "规划",
    "办法",
    "指导意见",
    "实施方案",
)
LISTING_FINANCING_STRONG_KEYWORDS = (
    "聆讯后资料集",
    "发行聆讯",
    "H股发行",
    "上市申请",
    "递交H股发行上市申请",
    "刊发申请资料",
    "上市保荐书",
    "发行保荐书",
    "募集说明书",
)
LISTING_FINANCING_EXCLUSION_KEYWORDS = (
    "提示性公告",
    "进展公告",
    "转股情况公告",
    "法律意见书",
    "补充法律意见书",
)
CSRC_ROUTINE_TITLE_KEYWORDS = (
    "答记者问",
    "召开",
    "会议",
    "接受监察调查",
    "开除党籍",
    "违纪违法",
    "顾问委员会",
    "新闻发言人",
)
CSRC_HARD_EVENT_KEYWORDS = (
    "公开征求意见",
    "同意开展",
    "试点",
    "办法",
    "制度",
    "实施规定",
    "国务院令",
    "行政执法",
    "处罚",
    "立案",
)
MACRO_DATA_KEYWORDS = (
    "同比",
    "环比",
    "增加值",
    "CPI",
    "PPI",
    "GDP",
    "PMI",
    "出口",
    "进口",
    "社融",
    "工业企业利润",
)
TITLE_EMPHASIS_WORDS = ("重大", "爆发", "发布", "签订", "支持", "击落", "突破")
IMPACT_WIDE_KEYWORDS = ("全国", "全市场", "行业")
INTENSITY_SHOCK_KEYWORDS = ("重大", "击落", "爆发")
INTENSITY_POLICY_KEYWORDS = ("示范项目", "若干措施")

# token match, first hit wins.
SOURCE_WEIGHT_TOKENS = (
    ("中国政府网", 1.0),
    ("证监会", 1.0),
    ("国家发改委", 0.95),
    ("巨潮资讯网", 0.95),
    ("上交所", 0.9),
    ("深交所", 0.9),
    ("财新网", 0.9),
    ("第一财经", 0.85),
    ("36氪", 0.75),
    ("东方财富", 0.7),
)

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
