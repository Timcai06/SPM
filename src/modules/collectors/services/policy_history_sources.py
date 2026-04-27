from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

from modules.collectors.adapters import csrc
from modules.collectors.domain.common import fetch_text, get_http_session, strip_tags
from modules.collectors.domain.history_dates import direct_history_limit, in_date_range, normalize_date, normalize_datetime
from modules.collectors.domain.history_rows import dedupe_rows
from modules.collectors.domain.raw_event_categories import POLICY_EVENT


NDRC_BASE_URL = "https://www.ndrc.gov.cn/xxgk/zcfb/tz/"
MIIT_SEARCH_INFO_URL = "https://www.miit.gov.cn/search-front-server/api/search/info"


def build_ndrc_page_url(page_index: int) -> str:
    return NDRC_BASE_URL + ("index.html" if page_index == 0 else f"index_{page_index}.html")


def build_csrc_page_url(page_index: int) -> str:
    return csrc.CSRC_LIST_URL if page_index == 0 else f"https://www.csrc.gov.cn/csrc/c100028/common_list_{page_index + 1}.shtml"


def _parse_gov_publish_time(url: str) -> str:
    m = re.search(r"/(20[0-9]{2})([01][0-9])/", url)
    if m:
        return f"{m.group(1)}-{m.group(2)}-01 00:00:00"
    return ""


def parse_gov_article_sync(item: dict[str, Any]) -> dict[str, str] | None:
    url = str(item.get("URL") or "").strip()
    if not url:
        return None
    html = fetch_text(url)
    title_match = re.search(r'<h1 id="ti">\s*(.*?)\s*</h1>', html, re.S)
    date_match = re.search(r'<div class="pages-date">\s*([0-9\-:\s]+)', html, re.S)
    source_match = re.search(r"来源：\s*([^<\s]+)", html)
    content_match = re.search(r'<div class="pages_content"[^>]*>([\s\S]*?)</div>\s*<div class="editor">', html)
    if not (title_match and content_match):
        return None
    title = strip_tags(title_match.group(1))
    publish_time = re.sub(r"\s+", " ", date_match.group(1)).strip() if date_match else _parse_gov_publish_time(url)
    source_name = strip_tags(source_match.group(1)) if source_match else "中国政府网"
    content = strip_tags(content_match.group(1))
    if not content:
        return None
    return {
        "source": f"中国政府网/{source_name}",
        "title": title,
        "content": content,
        "publish_time": normalize_datetime(publish_time),
        "url": url,
        "symbol_or_subject": POLICY_EVENT,
    }


def iter_gov_news_history_batches(
    start_date: str,
    end_date: str,
    max_pages: int,
    page_size: int,
    workers: int,
) -> list[list[dict[str, str]]]:
    payload = json.loads(fetch_text("https://www.gov.cn/yaowen/liebiao/YAOWENLIEBIAO.json"))
    selected = payload[: direct_history_limit(max_pages, page_size)]
    batches: list[list[dict[str, str]]] = []
    for items in [selected[idx : idx + page_size] for idx in range(0, len(selected), page_size)]:
        rows: list[dict[str, str]] = []
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = [pool.submit(parse_gov_article_sync, item) for item in items]
            for future in as_completed(futures):
                row = future.result()
                if row and in_date_range(row["publish_time"], start_date, end_date):
                    rows.append(row)
        batches.append(dedupe_rows(rows))
    return batches


def parse_ndrc_list_page(page_index: int, page_size: int) -> list[dict[str, str]]:
    html = fetch_text(build_ndrc_page_url(page_index))
    pattern = re.compile(
        r'<li>\s*<a href="(?P<href>[^"]+)"[^>]*title="(?P<title>[^"]+)">.*?</a>[\s\S]*?<span>(?P<date>[0-9/]+)</span>\s*</li>',
        re.S,
    )
    rows: list[dict[str, str]] = []
    for match in pattern.finditer(html):
        href = match.group("href").strip()
        title = strip_tags(match.group("title"))
        publish_time = match.group("date").replace("/", "-")
        if href.startswith("./"):
            url = NDRC_BASE_URL + href[2:]
        elif href.startswith("/"):
            url = "https://www.ndrc.gov.cn" + href
        else:
            url = href
        rows.append({"title": title, "publish_time": publish_time, "url": url})
        if len(rows) >= page_size:
            break
    return rows


def parse_ndrc_article_sync(item: dict[str, str]) -> dict[str, str] | None:
    url = item["url"]
    html = fetch_text(url)
    title_match = re.search(r'<meta name="ArticleTitle" content="([^"]+)">', html) or re.search(r"<h2[^>]*>\s*(.*?)\s*</h2>", html, re.S)
    date_match = re.search(r'<meta name="PubDate" content="([0-9:\-\s]+)">', html) or re.search(r"发布时间[:：]?\s*([0-9]{4}[/-][0-9]{2}[/-][0-9]{2})", html)
    content_match = re.search(r'<div class=TRS_Editor>([\s\S]*?)</div>\s*</div>\s*</div>', html) or re.search(r'<div class="article_con">\s*<div class=TRS_Editor>([\s\S]*?)</div>', html)
    source_match = re.search(r'<meta name="ContentSource" content="([^"]*)">', html) or re.search(r"来源[:：]?\s*([^<\s]+)", html)
    if not (title_match and date_match and content_match):
        return None
    title = strip_tags(title_match.group(1))
    publish_time = date_match.group(1).strip().replace("/", "-")
    source_name = strip_tags(source_match.group(1)) if source_match else "国家发展改革委"
    content = strip_tags(content_match.group(1))
    if not content:
        return None
    return {
        "source": f"国家发改委/{source_name}",
        "title": title,
        "content": content,
        "publish_time": normalize_datetime(publish_time),
        "url": url,
        "symbol_or_subject": POLICY_EVENT,
    }


def parse_csrc_list_page(page_index: int, page_size: int) -> list[dict[str, str]]:
    html = fetch_text(build_csrc_page_url(page_index))
    pattern = re.compile(
        r'<li>\s*<a href="(?P<href>/csrc/c100028/[^"]+/content\.shtml)"[^>]*>(?P<title>.*?)</a>\s*<span class="date">(?P<date>[0-9\-]+)</span>',
        re.S,
    )
    rows: list[dict[str, str]] = []
    for match in pattern.finditer(html):
        title = strip_tags(match.group("title"))
        publish_time = match.group("date").strip()
        url = "https://www.csrc.gov.cn" + match.group("href").strip()
        if not title:
            continue
        rows.append({"title": title, "publish_time": publish_time, "url": url})
        if len(rows) >= page_size:
            break
    return rows


def parse_csrc_article_sync(item: dict[str, str]) -> dict[str, str] | None:
    html = fetch_text(item["url"])
    title = csrc.extract_meta_content(html, "ArticleTitle")
    publish_time = csrc.extract_meta_content(html, "PubDate")
    source_name = csrc.extract_meta_content(html, "ContentSource") or "中国证监会"
    description = csrc.extract_meta_content(html, "Description")
    content_match = re.search(r'<div class="detail-news">([\s\S]*?)<div\s+id="files"', html, re.I)
    if not content_match:
        content_match = re.search(r'<div class="detail-news">([\s\S]*?)</div>\s*</div>\s*</div>', html, re.I)
    if not title:
        title_match = re.search(r"<title>(.*?)_中国证券监督管理委员会</title>", html, re.S)
        title = strip_tags(title_match.group(1)) if title_match else item["title"]
    if not publish_time:
        date_match = re.search(r"页面生成时间\s*([0-9:\-\s]+)", html)
        publish_time = date_match.group(1).strip() if date_match else item["publish_time"]
    content = strip_tags(content_match.group(1)) if content_match else ""
    if not content:
        content = description or item["title"]
    if not title or not publish_time:
        return None
    return {
        "source": f"中国证监会/{source_name}",
        "title": title,
        "content": content,
        "publish_time": normalize_datetime(publish_time),
        "url": item["url"],
        "symbol_or_subject": POLICY_EVENT,
    }


def iter_ndrc_policy_history_batches(
    start_date: str,
    end_date: str,
    max_pages: int,
    page_size: int,
    workers: int,
) -> list[list[dict[str, str]]]:
    batches: list[list[dict[str, str]]] = []
    for page_index in range(max(1, max_pages)):
        items = parse_ndrc_list_page(page_index, page_size)
        if not items:
            break
        selected = [item for item in items if in_date_range(item["publish_time"], start_date, end_date)]
        rows: list[dict[str, str]] = []
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = [pool.submit(parse_ndrc_article_sync, item) for item in selected]
            for future in as_completed(futures):
                row = future.result()
                if row and in_date_range(row["publish_time"], start_date, end_date):
                    rows.append(row)
        batches.append(dedupe_rows(rows))
        oldest = min(normalize_date(item["publish_time"]) for item in items if item.get("publish_time"))
        if oldest and oldest < start_date:
            break
    return batches


def iter_csrc_policy_history_batches(
    start_date: str,
    end_date: str,
    max_pages: int,
    page_size: int,
    workers: int = 8,
) -> list[list[dict[str, str]]]:
    batches: list[list[dict[str, str]]] = []
    total_rows = 0
    for page_index in range(max(1, max_pages)):
        items = parse_csrc_list_page(page_index, page_size)
        if not items:
            break
        page_rows: list[dict[str, str]] = []
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = [pool.submit(parse_csrc_article_sync, item) for item in items]
            for future in as_completed(futures):
                try:
                    row = future.result()
                except Exception as exc:
                    print(f"[history] warn csrc detail fetch_failed error={exc}", flush=True)
                    continue
                if row and in_date_range(row["publish_time"], start_date, end_date):
                    page_rows.append(row)
        deduped_page_rows = dedupe_rows(page_rows)
        if deduped_page_rows:
            batches.append(deduped_page_rows)
            total_rows += len(deduped_page_rows)
            oldest = min(normalize_date(row["publish_time"]) for row in deduped_page_rows)
            if oldest and oldest < start_date:
                break
        if total_rows >= direct_history_limit(max_pages, page_size):
            break
    return batches


def _extract_miit_content(item: dict[str, Any]) -> str:
    infoextends = item.get("infoextends")
    if isinstance(infoextends, str):
        try:
            infoextends = json.loads(infoextends)
        except Exception:
            infoextends = None
    if isinstance(infoextends, dict):
        for element in infoextends.get("elementList", []) or []:
            field_name = str(element.get("fieldName") or "").strip().lower()
            if field_name == "content":
                text = strip_tags(str(element.get("fieldValue") or ""))
                if text:
                    return text
    return strip_tags(str(item.get("infocontent") or ""))


def _fetch_miit_search_page(page_num: int, page_size: int, start_date: str, end_date: str) -> dict[str, Any]:
    params = {
        "websiteid": "110000000000000",
        "scope": "basic",
        "q": "",
        "pg": str(page_size),
        "cateid": "57",
        "pos": "title,content",
        "begin": start_date,
        "end": end_date,
        "dateField": "deploytime",
        "selectFields": "title,content,deploytime,_index,url,cdate,infoextends,infocontentattribute,columnname,filenumbername,publishgroupname,publishtime,metaid,bexxgk,columnid,xxgkextend1,xxgkextend2,themename,typename,indexcode,createdate",
        "highlightConfigs": '[{"field":"infocontent","numberOfFragments":2,"fragmentOffset":0,"fragmentSize":30,"noMatchSize":145}]',
        "highlightFields": "title_text,infocontent,webid",
        "level": "6",
        "group": "distinct",
        "sortFields": "deploytime:desc",
        "p": str(page_num),
    }
    response = get_http_session().get(
        MIIT_SEARCH_INFO_URL,
        params=params,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def iter_miit_policy_history_batches(
    start_date: str,
    end_date: str,
    max_pages: int,
    page_size: int,
) -> list[list[dict[str, str]]]:
    batches: list[list[dict[str, str]]] = []
    total_rows = 0
    for page_num in range(1, max(1, max_pages) + 1):
        try:
            payload = _fetch_miit_search_page(page_num, page_size, start_date, end_date)
        except Exception as exc:
            print(f"[history] warn miit page={page_num} fetch_failed error={exc}", flush=True)
            continue
        items = (((payload.get("data") or {}).get("searchResult") or {}).get("dataResults") or [])
        if not items:
            break
        page_rows: list[dict[str, str]] = []
        for item in items:
            data = (((item.get("groupData") or [{}])[0]) or {}).get("data") or item
            title = strip_tags(str(data.get("title") or "")).strip()
            if not title:
                continue
            publish_time = str(data.get("jsearch_date") or data.get("deploytime") or "").strip()
            if not publish_time and data.get("createdate"):
                try:
                    publish_time = datetime.fromtimestamp(int(data["createdate"]) / 1000).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    publish_time = ""
            if not in_date_range(publish_time, start_date, end_date):
                continue
            content = _extract_miit_content(data)
            if not content:
                continue
            url = str(data.get("url") or "").strip()
            if url.startswith("/"):
                url = urljoin("https://www.miit.gov.cn", url)
            page_rows.append(
                {
                    "source": "工信部/政策文件",
                    "title": title,
                    "content": content,
                    "publish_time": normalize_datetime(publish_time),
                    "url": url,
                    "symbol_or_subject": POLICY_EVENT,
                }
            )
        deduped_page_rows = dedupe_rows(page_rows)
        if deduped_page_rows:
            batches.append(deduped_page_rows)
            total_rows += len(deduped_page_rows)
            oldest = min(normalize_date(row["publish_time"]) for row in deduped_page_rows)
            if oldest and oldest < start_date:
                break
        if total_rows >= direct_history_limit(max_pages, page_size):
            break
    return batches
