from __future__ import annotations

from dataclasses import dataclass

from modules.collectors.domain.raw_event_categories import (
    COMPANY_EVENT,
    INDUSTRY_EVENT,
    MACRO_EVENT,
    POLICY_EVENT,
)


TARGET_BODY_ROWS_PER_NON_CNINFO_SOURCE = 2000


@dataclass(frozen=True)
class RawHistorySourceProfile:
    history_source: str
    raw_event_category: str
    source_family: str
    source_patterns: tuple[str, ...]
    note: str
    collector_family: str
    target_rows: int = TARGET_BODY_ROWS_PER_NON_CNINFO_SOURCE
    requires_body: bool = False
    allow_backfill: bool = False
    max_pages: int = 200
    workers: int = 16
    symbol_mode: bool = False
    max_symbols: int = 0
    limit_per_symbol: int = 0
    db_flush_every: int = 50

    @property
    def body_quality_required(self) -> bool:
        return self.requires_body


RAW_HISTORY_SOURCE_PROFILES: tuple[RawHistorySourceProfile, ...] = (
    RawHistorySourceProfile(
        history_source="yicai-news",
        raw_event_category=MACRO_EVENT,
        source_family="第一财经",
        source_patterns=("第一财经/%", "第一财经"),
        note="宏观正文源：补正文并扩量",
        collector_family="media",
        max_pages=300,
        workers=24,
        requires_body=True,
    ),
    RawHistorySourceProfile(
        history_source="eastmoney-industry",
        raw_event_category=INDUSTRY_EVENT,
        source_family="东方财富行业资讯",
        source_patterns=("东方财富/行业资讯", "东方财富网"),
        note="行业正文源：补正文并扩量",
        collector_family="media",
        max_pages=300,
        workers=24,
        requires_body=True,
    ),
    RawHistorySourceProfile(
        history_source="gov-news",
        raw_event_category=POLICY_EVENT,
        source_family="中国政府网",
        source_patterns=("中国政府网/%", "中国政府网"),
        note="政策正文源：补正文并扩量",
        collector_family="policy",
        requires_body=True,
    ),
    RawHistorySourceProfile(
        history_source="ndrc-policy",
        raw_event_category=POLICY_EVENT,
        source_family="国家发改委",
        source_patterns=("国家发改委/%",),
        note="政策正文源：补正文并扩量",
        collector_family="policy",
        requires_body=True,
    ),
    RawHistorySourceProfile(
        history_source="csrc-policy",
        raw_event_category=POLICY_EVENT,
        source_family="中国证监会",
        source_patterns=("中国证监会/%",),
        note="政策正文源：补正文并扩量",
        collector_family="policy",
        requires_body=True,
    ),
    RawHistorySourceProfile(
        history_source="miit-policy",
        raw_event_category=POLICY_EVENT,
        source_family="工信部",
        source_patterns=("工信部/%",),
        note="政策正文源：补正文并扩量",
        collector_family="policy",
        requires_body=True,
    ),
    RawHistorySourceProfile(
        history_source="kr36-flash",
        raw_event_category=INDUSTRY_EVENT,
        source_family="36氪",
        source_patterns=("36氪/%", "36氪"),
        note="快讯源：先补覆盖，正文按自然命中率提升",
        collector_family="media",
    ),
    RawHistorySourceProfile(
        history_source="caixin-mini",
        raw_event_category=MACRO_EVENT,
        source_family="财新网",
        source_patterns=("财新网/%", "财新网"),
        note="媒体源：先补覆盖，正文按详情页命中率提升",
        collector_family="media",
    ),
    RawHistorySourceProfile(
        history_source="sse-announcements",
        raw_event_category=COMPANY_EVENT,
        source_family="上交所公告",
        source_patterns=("上交所/%", "上交所"),
        note="交易所公告：先补覆盖",
        collector_family="exchange",
    ),
    RawHistorySourceProfile(
        history_source="szse-announcements",
        raw_event_category=COMPANY_EVENT,
        source_family="深交所公告",
        source_patterns=("深交所/上市公司公告",),
        note="交易所公告：先补覆盖",
        collector_family="exchange",
    ),
    RawHistorySourceProfile(
        history_source="szse-suspension",
        raw_event_category=COMPANY_EVENT,
        source_family="深交所停复牌",
        source_patterns=("深交所/停复牌公告",),
        note="停复牌事实源：先补覆盖",
        collector_family="exchange",
        max_pages=100,
        workers=12,
    ),
    RawHistorySourceProfile(
        history_source="akshare-news",
        raw_event_category=COMPANY_EVENT,
        source_family="AKShare/EastMoney 新闻聚合",
        source_patterns=("AKShare/EastMoney/%",),
        note="聚合新闻：先补覆盖",
        collector_family="symbol",
        workers=16,
        symbol_mode=True,
        max_symbols=1500,
        limit_per_symbol=40,
        db_flush_every=100,
    ),
)

CNINFO_SOURCE_PROFILES: tuple[RawHistorySourceProfile, ...] = (
    RawHistorySourceProfile(
        history_source="cninfo-disclosure",
        raw_event_category=COMPANY_EVENT,
        source_family="CNInfo 历史公告",
        source_patterns=("巨潮资讯网/历史公告",),
        note="巨潮历史公告：补来源并做正文回填",
        collector_family="symbol",
        target_rows=0,
        allow_backfill=True,
        symbol_mode=True,
        max_symbols=3000,
        limit_per_symbol=120,
    ),
    RawHistorySourceProfile(
        history_source="cninfo-latest",
        raw_event_category=COMPANY_EVENT,
        source_family="CNInfo 最新公告",
        source_patterns=("巨潮资讯网/最新公告",),
        note="巨潮最新公告",
        collector_family="symbol",
        target_rows=0,
    ),
)

RAW_SOURCE_PROFILES: tuple[RawHistorySourceProfile, ...] = (
    *CNINFO_SOURCE_PROFILES,
    *RAW_HISTORY_SOURCE_PROFILES,
)


def history_source_choices() -> list[str]:
    symbol_sources = [
        profile.history_source
        for profile in RAW_HISTORY_SOURCE_PROFILES
        if profile.symbol_mode
    ]
    symbol_sources.extend(
        profile.history_source
        for profile in CNINFO_SOURCE_PROFILES
        if profile.symbol_mode
    )
    direct_sources = [
        profile.history_source
        for profile in RAW_HISTORY_SOURCE_PROFILES
        if not profile.symbol_mode
    ]
    return [*symbol_sources, *direct_sources]


def symbol_history_source_choices() -> tuple[str, ...]:
    return tuple(
        profile.history_source
        for profile in (*RAW_HISTORY_SOURCE_PROFILES, *CNINFO_SOURCE_PROFILES)
        if profile.symbol_mode
    )


def direct_history_source_choices() -> tuple[str, ...]:
    return tuple(
        profile.history_source
        for profile in RAW_HISTORY_SOURCE_PROFILES
        if not profile.symbol_mode
    )


def profile_by_history_source(history_source: str) -> RawHistorySourceProfile:
    for profile in RAW_SOURCE_PROFILES:
        if profile.history_source == history_source:
            return profile
    raise KeyError(f"Unknown history source profile: {history_source}")


def iter_source_pattern_rows(*, include_cninfo: bool = True) -> list[tuple[str, str, str, str, bool, str]]:
    rows: list[tuple[str, str, str, str, bool, str]] = []
    profiles = RAW_SOURCE_PROFILES if include_cninfo else RAW_HISTORY_SOURCE_PROFILES
    for profile in profiles:
        for pattern in profile.source_patterns:
            rows.append(
                (
                    profile.history_source,
                    profile.source_family,
                    pattern,
                    profile.raw_event_category,
                    profile.body_quality_required,
                    profile.note,
                )
            )
    return rows


def iter_replenish_pattern_rows() -> list[tuple[str, str, str, str, bool, str, int, str]]:
    rows: list[tuple[str, str, str, str, bool, str, int, str]] = []
    for profile in RAW_HISTORY_SOURCE_PROFILES:
        for pattern in profile.source_patterns:
            rows.append(
                (
                    profile.history_source,
                    profile.source_family,
                    pattern,
                    profile.raw_event_category,
                    profile.requires_body,
                    profile.note,
                    profile.target_rows,
                    profile.collector_family,
                )
            )
    return rows
