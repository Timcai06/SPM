#!/usr/bin/env python3
"""Historical document backfill collectors."""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

import akshare as ak
import psycopg

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from modules.collectors.adapters import cninfo, csrc, kr36, miit
from modules.collectors.adapters.db_repository import upsert_raw_document_rows
from modules.collectors.domain.common import fetch_text, strip_tags
from modules.collectors.domain.raw_event_categories import (
    COMPANY_EVENT,
    INDUSTRY_EVENT,
    MACRO_EVENT,
    POLICY_EVENT,
)
from modules.runtime.adapters.db import dsn_for


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = "stock_event_mining"
DEFAULT_OUTPUT = ROOT / "output" / "history"
SYMBOL_HISTORY_SOURCES = ("akshare-news", "cninfo-disclosure")
DIRECT_HISTORY_SOURCES = (
    "gov-news",
    "ndrc-policy",
    "csrc-policy",
    "miit-policy",
    "sse-announcements",
    "szse-announcements",
    "szse-suspension",
    "eastmoney-industry",
    "kr36-flash",
    "caixin-mini",
    "yicai-news",
)
NDRC_BASE_URL = "https://www.ndrc.gov.cn/xxgk/zcfb/tz/"
SSE_HISTORY_URL = "https://www.sse.com.cn/disclosure/listedinfo/announcement/json/stock_bulletin_publish_order.json"
SZSE_HISTORY_URL = "https://www.szse.cn/api/disc/announcement/detailinfo"
EASTMONEY_PAGE_1 = "https://finance.eastmoney.com/a/cywjh.html"
CAIXIN_PAGE_1 = "https://mini.caixin.com/"
YICAI_PAGE_1 = "https://www.yicai.com/news/"
SUSPENSION_KEYWORDS = ("停牌", "复牌", "停复牌")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect historical raw documents.")
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--source", choices=list(SYMBOL_HISTORY_SOURCES + DIRECT_HISTORY_SOURCES), default="akshare-news")
    parser.add_argument("--symbol-source", choices=["db", "all-a"], default="db")
    parser.add_argument("--symbol-file", default="", help="Optional CSV/text file with ts_code/code and optional company_name/name columns.")
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--end-date", default=datetime.now().date().isoformat())
    parser.add_argument("--max-symbols", type=int, default=200)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit-per-symbol", type=int, default=20)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--sleep-sec", type=float, default=0.05)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--skip-db-load", action="store_true")
    parser.add_argument("--cninfo-fulltext", action="store_true", help="Download CNInfo PDF attachments and extract text into content.")
    parser.add_argument("--cninfo-fulltext-max-chars", type=int, default=12000)
    parser.add_argument("--db-flush-every", type=int, default=100, help="Incrementally upsert every N collected rows.")
    parser.add_argument("--max-pages", type=int, default=20, help="For direct source history collectors, cap page iterations.")
    parser.add_argument("--page-size", type=int, default=50, help="For direct source history collectors, cap rows per page or total page fetch size.")
    return parser.parse_args(argv)


def normalize_date(value: str) -> str:
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text[:19], fmt).date().isoformat()
        except Exception:
            continue
    return text[:10]


def normalize_datetime(value: Any) -> str:
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text[:19], fmt).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            continue
    return "1970-01-01 00:00:00"


def get_symbols_from_db(db_name: str, max_symbols: int, offset: int) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    with psycopg.connect(dsn_for(db_name)) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ts_code, company_name
                FROM companies
                WHERE is_active = TRUE
                  AND ts_code IS NOT NULL
                  AND ts_code <> ''
                ORDER BY ts_code
                OFFSET %s
                LIMIT %s
                """,
                (max(offset, 0), max_symbols),
            )
            rows = [(str(ts_code), str(name or "")) for ts_code, name in cur.fetchall()]
    return rows


def get_symbols_from_akshare(max_symbols: int, offset: int) -> list[tuple[str, str]]:
    try:
        df = ak.stock_zh_a_spot_em()
        code_col = "代码"
        name_col = "名称"
    except Exception:
        df = ak.stock_info_a_code_name()
        code_col = "code" if "code" in df.columns else "代码"
        name_col = "name" if "name" in df.columns else "名称"
    output: list[tuple[str, str]] = []
    for _, row in df.iterrows():
        code = str(row.get(code_col) or "").strip()
        name = str(row.get(name_col) or "").strip()
        if len(code) != 6 or not code.isdigit():
            continue
        if code.startswith(("6", "9", "5")):
            ts_code = f"{code}.SH"
        elif code.startswith(("0", "2", "3")):
            ts_code = f"{code}.SZ"
        elif code.startswith(("4", "8")):
            ts_code = f"{code}.BJ"
        else:
            continue
        output.append((ts_code, name))
    return output[max(offset, 0) : max(offset, 0) + max_symbols]


def normalize_symbol_code(value: str) -> str:
    text = str(value or "").strip().upper()
    if not text:
        return ""
    if "." in text:
        code, suffix = text.split(".", 1)
        if suffix in {"SZ", "SH", "BJ"}:
            return f"{code}.{suffix}"
    code = text
    if len(code) != 6 or not code.isdigit():
        return ""
    if code.startswith(("6", "9", "5")):
        return f"{code}.SH"
    if code.startswith(("0", "2", "3")):
        return f"{code}.SZ"
    if code.startswith(("4", "8")):
        return f"{code}.BJ"
    return ""


def get_symbols_from_file(path: Path, max_symbols: int, offset: int) -> list[tuple[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"symbol file not found: {path}")
    rows: list[tuple[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(2048)
        f.seek(0)
        if "," in sample:
            reader = csv.DictReader(f)
            for row in reader:
                raw_code = row.get("ts_code") or row.get("code") or row.get("symbol") or row.get("股票代码") or row.get("代码")
                ts_code = normalize_symbol_code(str(raw_code or ""))
                name = str(row.get("company_name") or row.get("name") or row.get("股票简称") or row.get("名称") or "").strip()
                if ts_code:
                    rows.append((ts_code, name))
        else:
            for line in f:
                parts = [part.strip() for part in line.strip().split() if part.strip()]
                if not parts:
                    continue
                ts_code = normalize_symbol_code(parts[0])
                name = parts[1] if len(parts) > 1 else ""
                if ts_code:
                    rows.append((ts_code, name))
    seen: set[str] = set()
    deduped: list[tuple[str, str]] = []
    for ts_code, name in rows:
        if ts_code in seen:
            continue
        seen.add(ts_code)
        deduped.append((ts_code, name))
    return deduped[max(offset, 0) : max(offset, 0) + max_symbols]


def resolve_symbols(db_name: str, max_symbols: int, offset: int, symbol_source: str, symbol_file: str) -> list[tuple[str, str]]:
    if symbol_file.strip():
        return get_symbols_from_file(Path(symbol_file).expanduser().resolve(), max_symbols=max_symbols, offset=offset)
    if symbol_source == "all-a":
        return get_symbols_from_akshare(max_symbols=max_symbols, offset=offset)
    return get_symbols_from_db(db_name, max_symbols=max_symbols, offset=offset)


def in_date_range(value: str, start_date: str, end_date: str) -> bool:
    date_text = normalize_date(value)
    if not date_text:
        return False
    return start_date <= date_text <= end_date


def in_date_window_exclusive(value: str, start_date: str, end_date_exclusive: str) -> bool:
    date_text = normalize_date(value)
    if not date_text:
        return False
    return start_date <= date_text < end_date_exclusive


def direct_history_limit(max_pages: int, page_size: int) -> int:
    return max(1, max_pages) * max(1, page_size)


def chunked_rows(rows: list[dict[str, str]], chunk_size: int) -> list[list[dict[str, str]]]:
    size = max(1, chunk_size)
    return [rows[idx : idx + size] for idx in range(0, len(rows), size)]


def is_symbol_history_source(source: str) -> bool:
    return source in SYMBOL_HISTORY_SOURCES


def build_ndrc_page_url(page_index: int) -> str:
    return NDRC_BASE_URL + ("index.html" if page_index == 0 else f"index_{page_index}.html")


def build_eastmoney_page_url(page_index: int) -> str:
    return EASTMONEY_PAGE_1 if page_index == 0 else f"https://finance.eastmoney.com/a/cywjh_{page_index + 1}.html"


def build_caixin_page_url(page_index: int) -> str:
    return CAIXIN_PAGE_1 if page_index == 0 else f"https://mini.caixin.com/index-{page_index + 1}.html"


def build_yicai_page_url(page_index: int) -> str:
    return YICAI_PAGE_1 if page_index == 0 else f"https://www.yicai.com/news?page={page_index + 1}"


def build_csrc_page_url(page_index: int) -> str:
    return csrc.CSRC_LIST_URL if page_index == 0 else f"https://www.csrc.gov.cn/csrc/c100028/common_list_{page_index + 1}.shtml"


def _chunk_direct_adapter_rows(
    rows: list[dict[str, str]],
    *,
    start_date: str,
    end_date: str,
    page_size: int,
) -> list[list[dict[str, str]]]:
    filtered = [row for row in rows if row and in_date_range(row.get("publish_time", ""), start_date, end_date)]
    deduped = dedupe_rows(filtered)
    return [dedupe_rows(batch) for batch in chunked_rows(deduped, page_size)]


def iter_single_fetch_history_batches(
    collect_func,
    *,
    limit: int,
    start_date: str,
    end_date: str,
    page_size: int,
) -> list[list[dict[str, str]]]:
    rows = asyncio.run(collect_func(limit=limit))
    return _chunk_direct_adapter_rows(
        rows,
        start_date=start_date,
        end_date=end_date,
        page_size=page_size,
    )


def _publish_time_from_eastmoney_url(url: str) -> str:
    match = re.search(r"/a/(20[0-9]{2})([01][0-9])([0-3][0-9])[0-9]+\.html", url)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)} 00:00:00"
    return ""


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


def collect_gov_news_history(start_date: str, end_date: str, max_pages: int, page_size: int, workers: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for batch in iter_gov_news_history_batches(start_date, end_date, max_pages, page_size, workers):
        rows.extend(batch)
    return dedupe_rows(rows)


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
    for items in chunked_rows(selected, page_size):
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


def collect_ndrc_policy_history(start_date: str, end_date: str, max_pages: int, page_size: int, workers: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for batch in iter_ndrc_policy_history_batches(start_date, end_date, max_pages, page_size, workers):
        rows.extend(batch)
    return dedupe_rows(rows)


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


def collect_csrc_policy_history(start_date: str, end_date: str, max_pages: int, page_size: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for batch in iter_csrc_policy_history_batches(start_date, end_date, max_pages, page_size):
        rows.extend(batch)
    return dedupe_rows(rows)


def iter_csrc_policy_history_batches(
    start_date: str,
    end_date: str,
    max_pages: int,
    page_size: int,
) -> list[list[dict[str, str]]]:
    batches: list[list[dict[str, str]]] = []
    total_rows = 0
    for page_index in range(max(1, max_pages)):
        items = parse_csrc_list_page(page_index, page_size)
        if not items:
            break
        page_rows: list[dict[str, str]] = []
        for item in items:
            row = parse_csrc_article_sync(item)
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


def collect_miit_policy_history(start_date: str, end_date: str, max_pages: int, page_size: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for batch in iter_miit_policy_history_batches(start_date, end_date, max_pages, page_size):
        rows.extend(batch)
    return dedupe_rows(rows)


def iter_miit_policy_history_batches(
    start_date: str,
    end_date: str,
    max_pages: int,
    page_size: int,
) -> list[list[dict[str, str]]]:
    return iter_single_fetch_history_batches(
        miit.collect,
        limit=direct_history_limit(max_pages, page_size),
        start_date=start_date,
        end_date=end_date,
        page_size=page_size,
    )


def collect_sse_announcements_history(start_date: str, end_date: str, max_pages: int, page_size: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for batch in iter_sse_announcements_history_batches(start_date, end_date, max_pages, page_size):
        rows.extend(batch)
    return dedupe_rows(rows)


def iter_sse_announcements_history_batches(
    start_date: str,
    end_date: str,
    max_pages: int,
    page_size: int,
) -> list[list[dict[str, str]]]:
    text = fetch_text(f"{SSE_HISTORY_URL}?pageHelp.pageSize={max(200, direct_history_limit(max_pages, page_size))}&pageHelp.pageNo=1")
    payload = json.loads(text)
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
    return [dedupe_rows(batch) for batch in chunked_rows(rows, page_size)]


def fetch_szse_page(page_num: int, page_size: int) -> dict[str, Any]:
    url = f"{SZSE_HISTORY_URL}?random=0.1&pageSize={page_size}&pageNum={page_num}&plateCode=szse"
    return json.loads(fetch_text(url))


def collect_szse_history(start_date: str, end_date: str, max_pages: int, page_size: int, suspension_only: bool) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for batch in iter_szse_history_batches(start_date, end_date, max_pages, page_size, suspension_only):
        rows.extend(batch)
    return dedupe_rows(rows)[: direct_history_limit(max_pages, page_size)]


def iter_szse_history_batches(
    start_date: str,
    end_date: str,
    max_pages: int,
    page_size: int,
    suspension_only: bool,
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


def collect_eastmoney_industry_history(start_date: str, end_date: str, max_pages: int, page_size: int, workers: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for batch in iter_eastmoney_industry_history_batches(start_date, end_date, max_pages, page_size, workers):
        rows.extend(batch)
    return dedupe_rows(rows)


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


def collect_kr36_flash_history(start_date: str, end_date: str, max_pages: int, page_size: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for batch in iter_kr36_flash_history_batches(start_date, end_date, max_pages, page_size):
        rows.extend(batch)
    return dedupe_rows(rows)


def iter_kr36_flash_history_batches(
    start_date: str,
    end_date: str,
    max_pages: int,
    page_size: int,
) -> list[list[dict[str, str]]]:
    return iter_single_fetch_history_batches(
        kr36.collect,
        limit=direct_history_limit(max_pages, page_size),
        start_date=start_date,
        end_date=end_date,
        page_size=page_size,
    )


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


def collect_caixin_history(start_date: str, end_date: str, max_pages: int, page_size: int, workers: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for batch in iter_caixin_history_batches(start_date, end_date, max_pages, page_size, workers):
        rows.extend(batch)
    return dedupe_rows(rows)


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


def collect_yicai_history(start_date: str, end_date: str, max_pages: int, page_size: int, workers: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for batch in iter_yicai_history_batches(start_date, end_date, max_pages, page_size, workers):
        rows.extend(batch)
    return dedupe_rows(rows)


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


def collect_direct_source_history(
    source: str,
    start_date: str,
    end_date: str,
    max_pages: int,
    page_size: int,
    workers: int,
) -> list[dict[str, str]]:
    if source == "gov-news":
        return collect_gov_news_history(start_date, end_date, max_pages, page_size, workers)
    if source == "ndrc-policy":
        return collect_ndrc_policy_history(start_date, end_date, max_pages, page_size, workers)
    if source == "csrc-policy":
        return collect_csrc_policy_history(start_date, end_date, max_pages, page_size)
    if source == "miit-policy":
        return collect_miit_policy_history(start_date, end_date, max_pages, page_size)
    if source == "sse-announcements":
        return collect_sse_announcements_history(start_date, end_date, max_pages, page_size)
    if source == "szse-announcements":
        return collect_szse_history(start_date, end_date, max_pages, page_size, suspension_only=False)
    if source == "szse-suspension":
        return collect_szse_history(start_date, end_date, max_pages, page_size, suspension_only=True)
    if source == "eastmoney-industry":
        return collect_eastmoney_industry_history(start_date, end_date, max_pages, page_size, workers)
    if source == "kr36-flash":
        return collect_kr36_flash_history(start_date, end_date, max_pages, page_size)
    if source == "caixin-mini":
        return collect_caixin_history(start_date, end_date, max_pages, page_size, workers)
    if source == "yicai-news":
        return collect_yicai_history(start_date, end_date, max_pages, page_size, workers)
    raise ValueError(f"Unsupported direct history source: {source}")


def iter_direct_source_history_batches(
    source: str,
    start_date: str,
    end_date: str,
    max_pages: int,
    page_size: int,
    workers: int,
) -> list[list[dict[str, str]]]:
    if source == "gov-news":
        return iter_gov_news_history_batches(start_date, end_date, max_pages, page_size, workers)
    if source == "ndrc-policy":
        return iter_ndrc_policy_history_batches(start_date, end_date, max_pages, page_size, workers)
    if source == "csrc-policy":
        return iter_csrc_policy_history_batches(start_date, end_date, max_pages, page_size)
    if source == "miit-policy":
        return iter_miit_policy_history_batches(start_date, end_date, max_pages, page_size)
    if source == "sse-announcements":
        return iter_sse_announcements_history_batches(start_date, end_date, max_pages, page_size)
    if source == "szse-announcements":
        return iter_szse_history_batches(start_date, end_date, max_pages, page_size, suspension_only=False)
    if source == "szse-suspension":
        return iter_szse_history_batches(start_date, end_date, max_pages, page_size, suspension_only=True)
    if source == "eastmoney-industry":
        return iter_eastmoney_industry_history_batches(start_date, end_date, max_pages, page_size, workers)
    if source == "kr36-flash":
        return iter_kr36_flash_history_batches(start_date, end_date, max_pages, page_size)
    if source == "caixin-mini":
        return iter_caixin_history_batches(start_date, end_date, max_pages, page_size, workers)
    if source == "yicai-news":
        return iter_yicai_history_batches(start_date, end_date, max_pages, page_size, workers)
    raise ValueError(f"Unsupported direct history source: {source}")


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
            if source == "akshare-news":
                rows = collect_akshare_news_for_symbol(ts_code, company_name, start_date, end_date, limit_per_symbol)
            else:
                rows = collect_cninfo_for_symbol(
                    ts_code,
                    company_name,
                    start_date,
                    end_date,
                    limit_per_symbol,
                    include_fulltext=cninfo_fulltext,
                    fulltext_max_chars=cninfo_fulltext_max_chars,
                )
            return ts_code, rows, ""
        except Exception as exc:
            last_error = f"{exc.__class__.__name__}: {exc}"
            if attempt < retries:
                time.sleep(sleep_sec * (attempt + 1))
    return ts_code, [], last_error


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["source", "title", "content", "publish_time", "url", "symbol_or_subject"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def dedupe_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    unique: dict[str, dict[str, str]] = {}
    for row in rows:
        url = row.get("url") or ""
        if not url:
            digest = hashlib.md5(f"{row.get('title')}::{row.get('publish_time')}".encode("utf-8")).hexdigest()
            url = f"local://history/{row.get('source', 'unknown')}/{digest}"
            row["url"] = url
        unique[url] = row
    return sorted(unique.values(), key=lambda item: (item["publish_time"], item["url"]))


def flush_rows_to_db(db: str, pending_rows: list[dict[str, str]]) -> int:
    rows = dedupe_rows(pending_rows)
    return upsert_raw_document_rows(db, rows)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    start_date = normalize_date(args.start_date)
    end_date = normalize_date(args.end_date)
    today = datetime.now().date().isoformat()
    effective_end_date = min(end_date, today)
    if effective_end_date != end_date:
        print(
            f"[history] clamp end-date {end_date} -> {effective_end_date} to avoid future-dated raw rows",
            flush=True,
        )
        end_date = effective_end_date
    if not is_symbol_history_source(args.source):
        started = time.time()
        print(
            f"[history] source={args.source} mode=direct range={start_date}..{end_date} "
            f"max_pages={args.max_pages} page_size={args.page_size} workers={args.workers}",
            flush=True,
        )
        batch_rows = iter_direct_source_history_batches(
            source=args.source,
            start_date=start_date,
            end_date=end_date,
            max_pages=args.max_pages,
            page_size=args.page_size,
            workers=args.workers,
        )
        rows: list[dict[str, str]] = []
        db_flushes = 0
        db_rows_upserted = 0
        for batch_idx, batch in enumerate(batch_rows, start=1):
            rows.extend(batch)
            if args.skip_db_load:
                print(
                    f"[history] progress batch {batch_idx}/{len(batch_rows)} rows={len(rows)} elapsed={int(time.time() - started)}s",
                    flush=True,
                )
                continue
            if batch:
                flushed = flush_rows_to_db(args.db, batch)
                db_flushes += 1
                db_rows_upserted += flushed
                print(
                    f"[history] db_flush {db_flushes} rows={flushed} cumulative={db_rows_upserted} "
                    f"batch={batch_idx}/{len(batch_rows)} elapsed={int(time.time() - started)}s",
                    flush=True,
                )
        out = (
            Path(args.output_dir).resolve()
            / f"history_{args.source}_{start_date}_{end_date}_pages{args.max_pages}_size{args.page_size}.csv"
        )
        rows = dedupe_rows(rows)
        write_csv(out, rows)
        if args.skip_db_load:
            print(f"[history] db_load=skipped rows={len(rows)} elapsed={int(time.time() - started)}s", flush=True)
        else:
            print(
                f"[history] db_load=done flushes={db_flushes} upserted={db_rows_upserted} rows={len(rows)} elapsed={int(time.time() - started)}s",
                flush=True,
            )
        print(f"[history] wrote {len(rows)} unique rows to {out}", flush=True)
        return

    symbols = resolve_symbols(
        args.db,
        max_symbols=args.max_symbols,
        offset=args.offset,
        symbol_source=args.symbol_source,
        symbol_file=args.symbol_file,
    )
    started = time.time()
    all_rows: list[dict[str, str]] = []
    pending_flush_rows: list[dict[str, str]] = []
    failures: list[tuple[str, str]] = []
    db_flushes = 0
    db_rows_upserted = 0
    print(
        f"[history] source={args.source} symbol_source={args.symbol_source} symbols={len(symbols)} offset={args.offset} "
        f"range={start_date}..{end_date} limit_per_symbol={args.limit_per_symbol} workers={args.workers}",
        flush=True,
    )
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [
            pool.submit(
                collect_with_retry,
                args.source,
                symbol,
                start_date,
                end_date,
                args.limit_per_symbol,
                args.retries,
                args.sleep_sec,
                args.cninfo_fulltext,
                args.cninfo_fulltext_max_chars,
            )
            for symbol in symbols
        ]
        for idx, future in enumerate(as_completed(futures), start=1):
            ts_code, rows, error = future.result()
            if error:
                failures.append((ts_code, error))
            all_rows.extend(rows)
            if not args.skip_db_load:
                pending_flush_rows.extend(rows)
                if len(pending_flush_rows) >= max(1, args.db_flush_every):
                    flushed = flush_rows_to_db(args.db, pending_flush_rows)
                    db_flushes += 1
                    db_rows_upserted += flushed
                    print(
                        f"[history] db_flush {db_flushes} rows={flushed} cumulative={db_rows_upserted}",
                        flush=True,
                    )
                    pending_flush_rows.clear()
            if idx == 1 or idx % 20 == 0 or idx == len(futures):
                elapsed = int(time.time() - started)
                print(
                    f"[history] progress {idx}/{len(futures)} rows={len(all_rows)} failures={len(failures)} elapsed={elapsed}s",
                    flush=True,
                )

    rows = dedupe_rows(all_rows)
    out = Path(args.output_dir).resolve() / f"history_{args.source}_{start_date}_{end_date}_o{args.offset}_n{args.max_symbols}.csv"
    write_csv(out, rows)
    if not args.skip_db_load:
        if pending_flush_rows:
            flushed = flush_rows_to_db(args.db, pending_flush_rows)
            db_flushes += 1
            db_rows_upserted += flushed
            print(
                f"[history] db_flush {db_flushes} rows={flushed} cumulative={db_rows_upserted}",
                flush=True,
            )
            pending_flush_rows.clear()
    print(f"[history] wrote {len(rows)} unique rows to {out}")
    if args.skip_db_load:
        print(f"[history] db_load=skipped failures={len(failures)}")
    else:
        print(f"[history] db_load=done flushes={db_flushes} upserted={db_rows_upserted} failures={len(failures)}")
    if failures:
        print("[history] first failures: " + "; ".join(f"{code}:{err[:80]}" for code, err in failures[:5]))


if __name__ == "__main__":
    main()
