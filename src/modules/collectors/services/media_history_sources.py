from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests

from modules.collectors.domain.common import fetch_text, strip_tags
from modules.collectors.domain.history_dates import direct_history_limit, in_date_range, normalize_datetime
from modules.collectors.domain.history_rows import dedupe_rows
from modules.collectors.domain.raw_event_categories import INDUSTRY_EVENT, MACRO_EVENT


EASTMONEY_PAGE_1 = "https://finance.eastmoney.com/a/cywjh.html"
CAIXIN_PAGE_1 = "https://mini.caixin.com/"
YICAI_PAGE_1 = "https://www.yicai.com/news/"
KR36_FLASH_API_URL = "https://gateway.36kr.com/api/mis/nav/newsflash/list"


def build_eastmoney_page_url(page_index: int) -> str:
    return EASTMONEY_PAGE_1 if page_index == 0 else f"https://finance.eastmoney.com/a/cywjh_{page_index + 1}.html"


def build_caixin_page_url(page_index: int) -> str:
    return CAIXIN_PAGE_1 if page_index == 0 else f"https://mini.caixin.com/index-{page_index + 1}.html"


def build_yicai_page_url(page_index: int) -> str:
    return YICAI_PAGE_1 if page_index == 0 else f"https://www.yicai.com/news?page={page_index + 1}"


def _publish_time_from_eastmoney_url(url: str) -> str:
    match = re.search(r"/a/(20[0-9]{2})([01][0-9])([0-3][0-9])[0-9]+\.html", url)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)} 00:00:00"
    return ""


def parse_eastmoney_article_sync(url: str) -> dict[str, str] | None:
    html = fetch_text(url)
    title_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S) or re.search(r"<title>(.*?)_.*?</title>", html, re.S)
    content_match = re.search(r'<div[^>]+id="ContentBody"[^>]*>([\s\S]*?)</div>', html, re.I) or re.search(r'<div[^>]+class="newsContent"[^>]*>([\s\S]*?)</div>', html, re.I)
    time_match = re.search(r"([0-9]{4}-[0-9]{2}-[0-9]{2}\s+[0-9]{2}:[0-9]{2})", html)
    title = strip_tags(title_match.group(1)) if title_match else ""
    if not title:
        return None
    content = strip_tags(content_match.group(1)) if content_match else title
    return {
        "source": "东方财富/行业资讯",
        "title": title,
        "content": content or title,
        "publish_time": normalize_datetime(time_match.group(1) if time_match else _publish_time_from_eastmoney_url(url)),
        "url": url,
        "symbol_or_subject": INDUSTRY_EVENT,
    }


def iter_eastmoney_industry_history_batches(
    start_date: str,
    end_date: str,
    max_pages: int,
    page_size: int,
    workers: int,
) -> list[list[dict[str, str]]]:
    batches: list[list[dict[str, str]]] = []
    total_links = 0
    seen: set[str] = set()
    for page_index in range(max(1, max_pages)):
        html = fetch_text(build_eastmoney_page_url(page_index))
        page_links: list[str] = []
        for link in re.findall(r"https://finance\.eastmoney\.com/a/[0-9]+\.html", html):
            if link in seen:
                continue
            seen.add(link)
            page_links.append(link)
            total_links += 1
            if total_links >= direct_history_limit(max_pages, page_size):
                break
        rows: list[dict[str, str]] = []
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = [pool.submit(parse_eastmoney_article_sync, link) for link in page_links[:page_size]]
            for future in as_completed(futures):
                row = future.result()
                if row and in_date_range(row["publish_time"], start_date, end_date):
                    rows.append(row)
        batches.append(dedupe_rows(rows))
        if total_links >= direct_history_limit(max_pages, page_size):
            break
    return batches


def iter_kr36_flash_history_batches(
    start_date: str,
    end_date: str,
    max_pages: int,
    page_size: int,
) -> list[list[dict[str, str]]]:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": "https://www.36kr.com",
            "Referer": "https://www.36kr.com/newsflashes/catalog/2",
        }
    )
    batches: list[list[dict[str, str]]] = []
    page_callback: str | None = None
    total_rows = 0
    for page_index in range(max(1, max_pages)):
        payload = {
            "partner_id": "web",
            "timestamp": int(time.time() * 1000),
            "param": {
                "pageSize": max(1, page_size),
                "pageEvent": 0 if page_index == 0 else 1,
                "siteId": 1,
                "type": 2,
                "platformId": 2,
            },
        }
        if page_callback:
            payload["param"]["pageCallback"] = page_callback
        try:
            response = session.post(KR36_FLASH_API_URL, json=payload, timeout=20)
            response.raise_for_status()
            data = response.json().get("data") or {}
        except Exception as exc:
            print(f"[history] warn 36kr page={page_index + 1} fetch_failed error={exc}", flush=True)
            continue
        item_list = data.get("itemList") or []
        if not item_list:
            break
        page_rows: list[dict[str, str]] = []
        for item in item_list:
            material = item.get("templateMaterial", {}) or {}
            title = strip_tags(str(material.get("widgetTitle") or "")).strip()
            content = strip_tags(str(material.get("widgetContent") or "")).strip() or title
            publish_ts = material.get("publishTime")
            publish_time = datetime.fromtimestamp(int(publish_ts) / 1000).strftime("%Y-%m-%d %H:%M:%S") if publish_ts else ""
            if not title or not in_date_range(publish_time, start_date, end_date):
                continue
            item_id = material.get("itemId") or item.get("itemId")
            page_rows.append(
                {
                    "source": "36氪/股市快讯",
                    "title": title,
                    "content": content,
                    "publish_time": publish_time,
                    "url": f"https://www.36kr.com/newsflashes/{item_id}" if item_id else "https://www.36kr.com/newsflashes/catalog/2",
                    "symbol_or_subject": INDUSTRY_EVENT,
                }
            )
        deduped_page_rows = dedupe_rows(page_rows)
        if deduped_page_rows:
            batches.append(deduped_page_rows)
            total_rows += len(deduped_page_rows)
        page_callback = str(data.get("pageCallback") or "")
        if not data.get("hasNextPage") or total_rows >= direct_history_limit(max_pages, page_size):
            break
    return batches


def parse_caixin_list_page(page_index: int, page_size: int) -> list[dict[str, str]]:
    html = fetch_text(build_caixin_page_url(page_index))
    pattern = re.compile(r'<div class="boxa">([\s\S]*?)</div></div>', re.S)
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for block_match in pattern.finditer(html):
        block = block_match.group(1)
        title_match = re.search(r'<h4><a href="(?P<url>https://mini\.caixin\.com/[^\"]+)">(?P<title>.*?)</a>', block, re.S)
        if not title_match:
            continue
        url = title_match.group("url").strip()
        if url in seen:
            continue
        seen.add(url)
        title = strip_tags(title_match.group("title"))
        if not title:
            continue
        summary_match = re.search(r"<p>(.*?)</p>", block, re.S)
        rows.append({"url": url, "title": title, "summary": strip_tags(summary_match.group(1)) if summary_match else title})
        if len(rows) >= page_size:
            break
    return rows


def parse_caixin_article_sync(item: dict[str, str]) -> dict[str, str] | None:
    html = fetch_text(item["url"])
    title = item["title"]
    time_match = re.search(r"([0-9]{4}-[0-9]{2}-[0-9]{2}\s+[0-9]{2}:[0-9]{2})", html)
    content_match = re.search(r'<div class="textbox"[^>]*>([\s\S]*?)</div>\s*</div>', html, re.S)
    if not content_match:
        content_match = re.search(r'<meta name="description" content="([^"]+)"/>', html)
    publish_time = normalize_datetime(time_match.group(1) if time_match else "")
    content = strip_tags(content_match.group(1)) if content_match else item["summary"]
    return {
        "source": "财新网/mini",
        "title": title,
        "content": content or title,
        "publish_time": publish_time,
        "url": item["url"],
        "symbol_or_subject": MACRO_EVENT,
    }


def iter_caixin_history_batches(
    start_date: str,
    end_date: str,
    max_pages: int,
    page_size: int,
    workers: int,
) -> list[list[dict[str, str]]]:
    batches: list[list[dict[str, str]]] = []
    total_items = 0
    for page_index in range(max(1, max_pages)):
        items = parse_caixin_list_page(page_index, page_size)
        if not items:
            break
        rows: list[dict[str, str]] = []
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = [pool.submit(parse_caixin_article_sync, item) for item in items]
            for future in as_completed(futures):
                row = future.result()
                if row and in_date_range(row["publish_time"], start_date, end_date):
                    rows.append(row)
        batches.append(dedupe_rows(rows))
        total_items += len(items)
        if total_items >= direct_history_limit(max_pages, page_size):
            break
    return batches


def parse_yicai_list_page(page_index: int, page_size: int) -> list[dict[str, str]]:
    html = fetch_text(build_yicai_page_url(page_index))
    pattern = re.compile(r'<a href="(?P<href>/news/[0-9]+\.html)"[^>]*>\s*<div class="m-list[\s\S]*?</a>', re.S)
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in pattern.finditer(html):
        href = match.group("href").strip()
        url = "https://www.yicai.com" + href
        if url in seen:
            continue
        seen.add(url)
        block = match.group(0)
        title_match = re.search(r"<h2>(.*?)</h2>", block, re.S)
        summary_match = re.search(r"<p>(.*?)</p>", block, re.S)
        title = strip_tags(title_match.group(1)) if title_match else ""
        if not title:
            continue
        rows.append({"url": url, "title": title, "summary": strip_tags(summary_match.group(1)) if summary_match else title})
        if len(rows) >= page_size:
            break
    return rows


def parse_yicai_article_sync(item: dict[str, str]) -> dict[str, str] | None:
    html = fetch_text(item["url"])
    time_match = re.search(r"([0-9]{4}-[0-9]{2}-[0-9]{2}\s+[0-9]{2}:[0-9]{2})", html)
    content_match = re.search(r'<div class="m-text"[\s\S]*?<div class="m-txt">([\s\S]*?)</div>\s*</div>', html, re.S)
    if not content_match:
        content_match = re.search(r'<meta name="description" content="([^"]+)"', html)
    publish_time = normalize_datetime(time_match.group(1) if time_match else "")
    content = strip_tags(content_match.group(1)) if content_match else item["summary"]
    return {
        "source": "第一财经/新闻",
        "title": item["title"],
        "content": content or item["title"],
        "publish_time": publish_time,
        "url": item["url"],
        "symbol_or_subject": MACRO_EVENT,
    }


def iter_yicai_history_batches(
    start_date: str,
    end_date: str,
    max_pages: int,
    page_size: int,
    workers: int,
) -> list[list[dict[str, str]]]:
    batches: list[list[dict[str, str]]] = []
    total_items = 0
    for page_index in range(max(1, max_pages)):
        items = parse_yicai_list_page(page_index, page_size)
        if not items:
            break
        rows: list[dict[str, str]] = []
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = [pool.submit(parse_yicai_article_sync, item) for item in items]
            for future in as_completed(futures):
                row = future.result()
                if row and in_date_range(row["publish_time"], start_date, end_date):
                    rows.append(row)
        batches.append(dedupe_rows(rows))
        total_items += len(items)
        if total_items >= direct_history_limit(max_pages, page_size):
            break
    return batches
