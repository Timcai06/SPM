from __future__ import annotations

from typing import Callable

from modules.collectors.domain.source_profiles import direct_history_source_choices
from modules.collectors.services.exchange_history_sources import (
    iter_sse_announcements_history_batches,
    iter_szse_history_batches,
)
from modules.collectors.services.media_history_sources import (
    iter_caixin_history_batches,
    iter_eastmoney_industry_history_batches,
    iter_kr36_flash_history_batches,
    iter_yicai_history_batches,
)
from modules.collectors.services.policy_history_sources import (
    iter_csrc_policy_history_batches,
    iter_gov_news_history_batches,
    iter_miit_policy_history_batches,
    iter_ndrc_policy_history_batches,
)


BatchCollector = Callable[[str, str, int, int, int], list[list[dict[str, str]]]]


def _without_workers(collector: Callable[[str, str, int, int], list[list[dict[str, str]]]]) -> BatchCollector:
    def wrapper(start_date: str, end_date: str, max_pages: int, page_size: int, workers: int) -> list[list[dict[str, str]]]:
        return collector(start_date, end_date, max_pages, page_size)

    return wrapper


def _szse(suspension_only: bool) -> BatchCollector:
    def wrapper(start_date: str, end_date: str, max_pages: int, page_size: int, workers: int) -> list[list[dict[str, str]]]:
        return iter_szse_history_batches(start_date, end_date, max_pages, page_size, suspension_only=suspension_only)

    return wrapper


_DIRECT_HISTORY_COLLECTOR_IMPLEMENTATIONS: dict[str, BatchCollector] = {
    "gov-news": iter_gov_news_history_batches,
    "ndrc-policy": iter_ndrc_policy_history_batches,
    "csrc-policy": _without_workers(iter_csrc_policy_history_batches),
    "miit-policy": _without_workers(iter_miit_policy_history_batches),
    "sse-announcements": _without_workers(iter_sse_announcements_history_batches),
    "szse-announcements": _szse(suspension_only=False),
    "szse-suspension": _szse(suspension_only=True),
    "eastmoney-industry": iter_eastmoney_industry_history_batches,
    "kr36-flash": _without_workers(iter_kr36_flash_history_batches),
    "caixin-mini": iter_caixin_history_batches,
    "yicai-news": iter_yicai_history_batches,
}


def _build_profiled_direct_collectors() -> dict[str, BatchCollector]:
    expected_sources = set(direct_history_source_choices())
    missing_sources = expected_sources - set(_DIRECT_HISTORY_COLLECTOR_IMPLEMENTATIONS)
    extra_sources = set(_DIRECT_HISTORY_COLLECTOR_IMPLEMENTATIONS) - expected_sources
    if missing_sources or extra_sources:
        raise RuntimeError(
            "Direct history collector registry is out of sync with source profiles: "
            f"missing={sorted(missing_sources)} extra={sorted(extra_sources)}"
        )
    return {
        source: _DIRECT_HISTORY_COLLECTOR_IMPLEMENTATIONS[source]
        for source in direct_history_source_choices()
    }


DIRECT_HISTORY_BATCH_COLLECTORS = _build_profiled_direct_collectors()


def iter_direct_source_history_batches(
    source: str,
    start_date: str,
    end_date: str,
    max_pages: int,
    page_size: int,
    workers: int,
) -> list[list[dict[str, str]]]:
    collector = DIRECT_HISTORY_BATCH_COLLECTORS.get(source)
    if collector is None:
        raise ValueError(f"Unsupported direct history source: {source}")
    return collector(start_date, end_date, max_pages, page_size, workers)
