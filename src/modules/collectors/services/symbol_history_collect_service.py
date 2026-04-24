from __future__ import annotations

import time
from typing import Callable

import akshare as ak

from modules.collectors.adapters import cninfo
from modules.collectors.domain.history_dates import in_date_range, normalize_datetime
from modules.collectors.domain.raw_event_categories import COMPANY_EVENT
from modules.collectors.domain.source_profiles import symbol_history_source_choices


SymbolCollector = Callable[[str, str, str, str, int, bool, int], list[dict[str, str]]]


def collect_akshare_news_for_symbol(
    ts_code: str,
    company_name: str,
    start_date: str,
    end_date: str,
    limit_per_symbol: int,
) -> list[dict[str, str]]:
    symbol = ts_code.split(".", 1)[0]
    df = ak.stock_news_em(symbol=symbol)
    rows: list[dict[str, str]] = []
    if df is None or df.empty:
        return rows
    for _, row in df.iterrows():
        publish_time = str(row.get("发布时间") or "")
        if not in_date_range(publish_time, start_date=start_date, end_date=end_date):
            continue
        title = str(row.get("新闻标题") or "").strip()
        content = str(row.get("新闻内容") or "").strip() or title
        url = str(row.get("新闻链接") or "").strip()
        source_name = str(row.get("文章来源") or "EastMoney").strip()
        if not title or not url:
            continue
        rows.append(
            {
                "source": f"AKShare/EastMoney/{source_name}",
                "title": title,
                "content": content,
                "publish_time": normalize_datetime(publish_time),
                "url": url,
                "symbol_or_subject": COMPANY_EVENT,
            }
        )
        if len(rows) >= limit_per_symbol:
            break
    return rows


def collect_cninfo_for_symbol(
    ts_code: str,
    company_name: str,
    start_date: str,
    end_date: str,
    limit_per_symbol: int,
    include_fulltext: bool = False,
    fulltext_max_chars: int = 12000,
) -> list[dict[str, str]]:
    return cninfo.collect_history(
        ts_code=ts_code,
        company_name=company_name,
        start_date=start_date,
        end_date=end_date,
        limit_per_symbol=limit_per_symbol,
        include_fulltext=include_fulltext,
        fulltext_max_chars=fulltext_max_chars,
    )


def collect_akshare_history_for_symbol(
    ts_code: str,
    company_name: str,
    start_date: str,
    end_date: str,
    limit_per_symbol: int,
    include_fulltext: bool = False,
    fulltext_max_chars: int = 12000,
) -> list[dict[str, str]]:
    return collect_akshare_news_for_symbol(
        ts_code=ts_code,
        company_name=company_name,
        start_date=start_date,
        end_date=end_date,
        limit_per_symbol=limit_per_symbol,
    )


_SYMBOL_HISTORY_COLLECTOR_IMPLEMENTATIONS: dict[str, SymbolCollector] = {
    "akshare-news": collect_akshare_history_for_symbol,
    "cninfo-disclosure": collect_cninfo_for_symbol,
}


def _build_profiled_symbol_collectors() -> dict[str, SymbolCollector]:
    expected_sources = set(symbol_history_source_choices())
    missing_sources = expected_sources - set(_SYMBOL_HISTORY_COLLECTOR_IMPLEMENTATIONS)
    extra_sources = set(_SYMBOL_HISTORY_COLLECTOR_IMPLEMENTATIONS) - expected_sources
    if missing_sources or extra_sources:
        raise RuntimeError(
            "Symbol history collector registry is out of sync with source profiles: "
            f"missing={sorted(missing_sources)} extra={sorted(extra_sources)}"
        )
    return {
        source: _SYMBOL_HISTORY_COLLECTOR_IMPLEMENTATIONS[source]
        for source in symbol_history_source_choices()
    }


SYMBOL_HISTORY_COLLECTORS = _build_profiled_symbol_collectors()


def collect_with_retry(
    source: str,
    symbol: tuple[str, str],
    start_date: str,
    end_date: str,
    limit_per_symbol: int,
    retries: int,
    sleep_sec: float,
    cninfo_fulltext: bool = False,
    cninfo_fulltext_max_chars: int = 12000,
) -> tuple[str, list[dict[str, str]], str]:
    ts_code, company_name = symbol
    last_error = ""
    for attempt in range(retries + 1):
        try:
            collector = SYMBOL_HISTORY_COLLECTORS[source]
            rows = collector(
                ts_code,
                company_name,
                start_date,
                end_date,
                limit_per_symbol,
                cninfo_fulltext,
                cninfo_fulltext_max_chars,
            )
            return ts_code, rows, ""
        except Exception as exc:
            last_error = f"{exc.__class__.__name__}: {exc}"
            if attempt < retries:
                time.sleep(sleep_sec * (attempt + 1))
    return ts_code, [], last_error
