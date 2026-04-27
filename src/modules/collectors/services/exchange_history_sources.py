from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from modules.collectors.adapters import cninfo
from modules.collectors.domain.common import fetch_text, strip_tags
from modules.collectors.domain.history_dates import chunked_rows, direct_history_limit, in_date_range, normalize_date, normalize_datetime
from modules.collectors.domain.history_rows import dedupe_rows
from modules.collectors.domain.raw_event_categories import COMPANY_EVENT


SSE_HISTORY_URL = "https://www.sse.com.cn/disclosure/listedinfo/announcement/json/stock_bulletin_publish_order.json"
SZSE_HISTORY_URL = "https://www.szse.cn/api/disc/announcement/detailinfo"
SUSPENSION_KEYWORDS = ("停牌", "复牌", "停复牌")
PDF_TEXT_MAX_CHARS = 12000
PDF_TEXT_TIMEOUT_SEC = 18.0


def _with_pdf_body(row: dict[str, str]) -> dict[str, str]:
    url = str(row.get("url") or "").strip()
    if not url:
        return row
    try:
        text = cninfo.extract_pdf_text(url, max_chars=PDF_TEXT_MAX_CHARS, request_timeout_sec=PDF_TEXT_TIMEOUT_SEC)
    except Exception:
        return row
    if len(text) > len(row.get("content") or ""):
        updated = dict(row)
        updated["content"] = text
        return updated
    return row


def _fill_pdf_bodies(rows: list[dict[str, str]], workers: int) -> list[dict[str, str]]:
    if not rows:
        return rows
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [pool.submit(_with_pdf_body, row) for row in rows]
        return [future.result() for future in as_completed(futures)]


def iter_sse_announcements_history_batches(
    start_date: str,
    end_date: str,
    max_pages: int,
    page_size: int,
    workers: int = 8,
) -> list[list[dict[str, str]]]:
    try:
        text = fetch_text(
            f"{SSE_HISTORY_URL}?pageHelp.pageSize={max(200, direct_history_limit(max_pages, page_size))}&pageHelp.pageNo=1"
        )
        payload = json.loads(text)
    except Exception as exc:
        print(f"[history] warn sse fetch_failed error={exc}", flush=True)
        return []
    rows: list[dict[str, str]] = []
    for item in payload.get("publishData", []):
        disclose_date = str(item.get("discloseDate") or "").strip()
        if not in_date_range(disclose_date, start_date, end_date):
            continue
        title = str(item.get("bulletinTitle") or "").strip()
        if not title:
            continue
        url = str(item.get("bulletinUrl") or "").strip()
        if url.startswith("/"):
            url = "https://www.sse.com.cn" + url
        content_parts = [
            title,
            f"证券代码：{str(item.get('securityCode') or '').strip()}",
            f"证券简称：{str(item.get('securityAbbr') or '').strip()}",
            f"公告类型：{str(item.get('bulletinClassic') or '').strip()}",
        ]
        rows.append(
            {
                "source": "上交所/最新公告",
                "title": title,
                "content": "；".join([part for part in content_parts if part and not part.endswith("：")]),
                "publish_time": disclose_date,
                "url": url,
                "symbol_or_subject": COMPANY_EVENT,
            }
        )
        if len(rows) >= direct_history_limit(max_pages, page_size):
            break
    rows = _fill_pdf_bodies(rows, workers=workers)
    return [dedupe_rows(batch) for batch in chunked_rows(rows, page_size)]


def fetch_szse_page(page_num: int, page_size: int) -> dict[str, Any]:
    url = f"{SZSE_HISTORY_URL}?random=0.1&pageSize={page_size}&pageNum={page_num}&plateCode=szse"
    return json.loads(fetch_text(url))


def iter_szse_history_batches(
    start_date: str,
    end_date: str,
    max_pages: int,
    page_size: int,
    suspension_only: bool,
    workers: int = 8,
) -> list[list[dict[str, str]]]:
    batches: list[list[dict[str, str]]] = []
    total_rows = 0
    for page_num in range(1, max(1, max_pages) + 1):
        try:
            payload = fetch_szse_page(page_num=page_num, page_size=page_size)
        except Exception as exc:
            print(f"[history] warn szse page={page_num} fetch_failed error={exc}", flush=True)
            continue
        companies = payload.get("data", [])
        if not companies:
            break
        page_rows: list[dict[str, str]] = []
        for company in companies:
            sec_code = str(company.get("secCode") or "").strip()
            sec_name = str(company.get("secName") or "").strip()
            for item in company.get("announList", []):
                title = strip_tags(str(item.get("title") or "").strip())
                category = strip_tags(str(item.get("bigCategoryName") or "").strip())
                if not title:
                    continue
                if suspension_only and not any(keyword in f"{title} {category}" for keyword in SUSPENSION_KEYWORDS):
                    continue
                if (not suspension_only) and any(keyword in f"{title} {category}" for keyword in SUSPENSION_KEYWORDS):
                    pass
                publish_time = str(item.get("publishTime") or "").strip()
                if not in_date_range(publish_time, start_date, end_date):
                    continue
                attach_path = str(item.get("attachPath") or "").strip()
                attach_url = f"https://disc.static.szse.cn/download{attach_path}" if attach_path else ""
                source_name = "深交所/停复牌公告" if suspension_only else "深交所/上市公司公告"
                category_name = category or ("停复牌" if suspension_only else "")
                page_rows.append(
                    {
                        "source": source_name,
                        "title": title,
                        "content": "；".join(
                            [
                                title,
                                f"证券代码：{sec_code}",
                                f"证券简称：{sec_name}",
                                f"公告类别：{category_name}",
                            ]
                        ),
                        "publish_time": normalize_datetime(publish_time),
                        "url": attach_url,
                        "symbol_or_subject": COMPANY_EVENT,
                    }
                )
        deduped_page_rows = dedupe_rows(_fill_pdf_bodies(page_rows, workers=workers))
        if deduped_page_rows:
            batches.append(deduped_page_rows)
            total_rows += len(deduped_page_rows)
            oldest = min(normalize_date(row["publish_time"]) for row in deduped_page_rows)
            if oldest and oldest < start_date:
                break
        if total_rows >= direct_history_limit(max_pages, page_size):
            break
    return batches
