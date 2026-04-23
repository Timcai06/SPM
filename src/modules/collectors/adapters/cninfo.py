from __future__ import annotations

import shutil
import tempfile
import threading
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import parse_qs, urlparse

import requests
from requests.adapters import HTTPAdapter

from modules.collectors.domain.common import fetch_json_post, strip_tags


CNINFO_LIST_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_STOCKS_URL = "https://www.cninfo.com.cn/new/data/szse_stock.json"
CNINFO_PDF_HOST = "https://static.cninfo.com.cn/"
CNINFO_DETAIL_API_URL = "https://www.cninfo.com.cn/new/announcement/bulletin_detail"
CNINFO_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "X-Requested-With": "XMLHttpRequest",
}
_THREAD_LOCAL = threading.local()


def get_session() -> requests.Session:
    session = getattr(_THREAD_LOCAL, "session", None)
    if session is None:
        session = requests.Session()
        adapter = HTTPAdapter(pool_connections=32, pool_maxsize=32, max_retries=0)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        _THREAD_LOCAL.session = session
    return session


async def collect(limit: int = 20, lookback_days: int = 5) -> List[Dict[str, str]]:
    import aiohttp
    
    async with aiohttp.ClientSession() as session:
        from modules.collectors.domain.common import fetch_json_post_async
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=lookback_days)
        payload = await fetch_json_post_async(
            CNINFO_LIST_URL,
            {
                "pageNum": "1",
                "pageSize": str(limit),
                "tabName": "fulltext",
                "column": "szse",
                "plate": "sz",
                "stock": "",
                "searchkey": "",
                "secid": "",
                "category": "",
                "trade": "",
                "seDate": f"{start_date.isoformat()}~{end_date.isoformat()}",
                "sortName": "",
                "sortType": "",
                "isHLtitle": "true",
            },
            session=session
        )
        rows: List[Dict[str, str]] = []
        for item in payload.get("announcements", [])[:limit]:
            title = strip_tags(item.get("announcementTitle", "").strip())
            if not title:
                continue
            publish_time = ""
            if item.get("announcementTime"):
                publish_time = datetime.fromtimestamp(int(item["announcementTime"]) / 1000).strftime("%Y-%m-%d")
            adjunct_url = item.get("adjunctUrl", "").strip()
            url = f"https://www.cninfo.com.cn/{adjunct_url}" if adjunct_url else ""
            rows.append(
                {
                    "source": "巨潮资讯网/最新公告",
                    "title": title,
                    "content": "；".join(
                        [
                            title,
                            f'证券代码：{item.get("secCode", "").strip()}',
                            f'证券简称：{item.get("secName", "").strip()}',
                            f'板块：{item.get("pageColumn", "").strip()}',
                        ]
                    ),
                    "publish_time": publish_time,
                    "url": url,
                    "symbol_or_subject": item.get("secCode", "").strip(),
                }
            )
        return rows


@lru_cache()
def get_stock_org_map() -> dict[str, str]:
    response = get_session().get(CNINFO_STOCKS_URL, timeout=20)
    response.raise_for_status()
    data = response.json()
    stock_list = data.get("stockList", [])
    mapping: dict[str, str] = {}
    for item in stock_list:
        code = str(item.get("code") or "").strip()
        org_id = str(item.get("orgId") or "").strip()
        if code and org_id:
            mapping[code] = org_id
    return mapping


def build_history_detail_url(sec_code: str, announcement_id: str, org_id: str, announcement_time: str) -> str:
    return (
        "http://www.cninfo.com.cn/new/disclosure/detail"
        f"?stockCode={sec_code}&announcementId={announcement_id}&orgId={org_id}&announcementTime={announcement_time}"
    )


def build_pdf_url(adjunct_url: str) -> str:
    cleaned = str(adjunct_url or "").strip().lstrip("/")
    if not cleaned:
        return ""
    return f"{CNINFO_PDF_HOST}{cleaned}"


def build_derived_pdf_urls(announcement_id: str, announcement_time: str) -> list[str]:
    text = str(announcement_time or "").strip()
    if not announcement_id or not text:
        return []
    day = text[:10]
    if len(day) != 10:
        return []
    return [
        f"{CNINFO_PDF_HOST}finalpage/{day}/{announcement_id}.PDF",
        f"{CNINFO_PDF_HOST}finalpage/{day}/{announcement_id}.pdf",
    ]


def parse_detail_url(detail_url: str) -> dict[str, str]:
    parsed = urlparse(str(detail_url or "").strip())
    query = parse_qs(parsed.query)
    return {
        "stock_code": (query.get("stockCode") or [""])[0].strip(),
        "announcement_id": (query.get("announcementId") or [""])[0].strip(),
        "org_id": (query.get("orgId") or [""])[0].strip(),
        "announcement_time": (query.get("announcementTime") or [""])[0].strip(),
    }


def build_detail_referer(detail_url: str, stock_code: str, announcement_id: str, org_id: str, announcement_time: str) -> str:
    if detail_url:
        return detail_url
    return (
        "https://www.cninfo.com.cn/new/disclosure/detail"
        f"?stockCode={stock_code}&announcementId={announcement_id}&orgId={org_id}&announcementTime={announcement_time}"
    )


def fetch_bulletin_detail(
    detail_url: str,
    stock_code: str,
    announcement_id: str,
    announcement_time: str,
    timeout_sec: float = 20.0,
) -> dict[str, Any]:
    params = {
        "announceId": announcement_id,
        "flag": "true" if stock_code.startswith(("0", "2", "3")) else "false",
        "announceTime": announcement_time,
    }
    headers = dict(CNINFO_HEADERS)
    headers["Referer"] = build_detail_referer(
        detail_url,
        stock_code=stock_code,
        announcement_id=announcement_id,
        org_id="",
        announcement_time=announcement_time,
    )
    response = get_session().post(
        CNINFO_DETAIL_API_URL,
        params=params,
        headers=headers,
        timeout=timeout_sec,
    )
    response.raise_for_status()
    payload = response.json()
    announcement = payload.get("announcement") or {}
    if not announcement:
        raise ValueError("missing announcement detail")
    return payload


def extract_fulltext_from_detail_url(
    detail_url: str,
    max_chars: int = 12000,
    detail_timeout_sec: float = 20.0,
    pdf_timeout_sec: float = 20.0,
) -> str:
    parsed = parse_detail_url(detail_url)
    stock_code = parsed["stock_code"]
    announcement_id = parsed["announcement_id"]
    announcement_time = parsed["announcement_time"]
    if not stock_code or not announcement_id or not announcement_time:
        return ""
    pdf_urls: list[str] = []
    try:
        payload = fetch_bulletin_detail(
            detail_url=detail_url,
            stock_code=stock_code,
            announcement_id=announcement_id,
            announcement_time=announcement_time,
            timeout_sec=detail_timeout_sec,
        )
        direct_url = str(payload.get("fileUrl") or "").strip()
        if direct_url:
            pdf_urls.append(direct_url)
        adjunct_url = build_pdf_url(str((payload.get("announcement") or {}).get("adjunctUrl") or "").strip())
        if adjunct_url:
            pdf_urls.append(adjunct_url)
    except Exception:
        pass
    pdf_urls.extend(build_derived_pdf_urls(announcement_id=announcement_id, announcement_time=announcement_time))
    seen: set[str] = set()
    for pdf_url in pdf_urls:
        if not pdf_url or pdf_url in seen:
            continue
        seen.add(pdf_url)
        try:
            extracted = extract_pdf_text(pdf_url, max_chars=max_chars, request_timeout_sec=pdf_timeout_sec)
            if extracted:
                return extracted
        except Exception:
            continue
    return ""


def extract_pdf_text(pdf_url: str, max_chars: int = 12000, request_timeout_sec: float = 20.0) -> str:
    if not pdf_url:
        return ""
    with tempfile.TemporaryDirectory(prefix="cninfo_pdf_") as tmpdir:
        pdf_path = Path(tmpdir) / "notice.pdf"
        txt_path = Path(tmpdir) / "notice.txt"
        response = get_session().get(
            pdf_url,
            headers={"User-Agent": CNINFO_HEADERS["User-Agent"]},
            timeout=request_timeout_sec,
        )
        response.raise_for_status()
        pdf_path.write_bytes(response.content)

        text = _extract_pdf_text_with_pdftotext(pdf_path, txt_path)
        if not text:
            text = _extract_pdf_text_with_pdfplumber(pdf_path, max_chars=max_chars)
    text = " ".join(text.split())
    if max_chars > 0:
        return text[:max_chars]
    return text


def _extract_pdf_text_with_pdftotext(pdf_path: Path, txt_path: Path) -> str:
    import subprocess

    candidates = [
        shutil.which("pdftotext"),
        "/opt/homebrew/bin/pdftotext",
        "/usr/local/bin/pdftotext",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        binary = Path(candidate)
        if not binary.exists():
            continue
        try:
            subprocess.run(
                [str(binary), "-q", "-nopgbrk", str(pdf_path), str(txt_path)],
                check=True,
                capture_output=True,
                text=False,
            )
            return txt_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
    return ""


def _extract_pdf_text_with_pdfplumber(pdf_path: Path, max_chars: int = 12000) -> str:
    import pdfplumber

    chunks: list[str] = []
    remaining = max_chars if max_chars > 0 else None
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if not page_text.strip():
                continue
            if remaining is None:
                chunks.append(page_text)
                continue
            if remaining <= 0:
                break
            chunks.append(page_text[:remaining])
            remaining -= len(chunks[-1])
    return "\n".join(chunks)


def collect_history(
    ts_code: str,
    company_name: str,
    start_date: str,
    end_date: str,
    limit_per_symbol: int,
    include_fulltext: bool = False,
    fulltext_max_chars: int = 12000,
) -> List[Dict[str, str]]:
    symbol = ts_code.split(".", 1)[0]
    org_id = get_stock_org_map().get(symbol, "")
    if not org_id:
        return []
    payload = {
        "pageNum": "1",
        "pageSize": "30",
        "column": "szse",
        "tabName": "fulltext",
        "plate": "",
        "stock": f"{symbol},{org_id}",
        "searchkey": "",
        "secid": "",
        "category": "",
        "trade": "",
        "seDate": f"{start_date}~{end_date}",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }
    first_page = fetch_json_post(CNINFO_LIST_URL, payload)
    total = int(first_page.get("totalAnnouncement") or 0)
    if total <= 0:
        return []
    rows: List[Dict[str, str]] = []
    total_pages = max(1, (total + 29) // 30)
    page_payload = dict(payload)
    for page_num in range(1, total_pages + 1):
        page_payload["pageNum"] = str(page_num)
        page_data = first_page if page_num == 1 else fetch_json_post(CNINFO_LIST_URL, page_payload)
        for item in page_data.get("announcements", []) or []:
            title = strip_tags(str(item.get("announcementTitle") or "").strip())
            if not title:
                continue
            announcement_time = item.get("announcementTime")
            publish_time = ""
            if announcement_time:
                publish_time = datetime.fromtimestamp(int(announcement_time) / 1000).strftime("%Y-%m-%d %H:%M:%S")
            announcement_id = str(item.get("announcementId") or "").strip()
            item_org_id = str(item.get("orgId") or org_id).strip()
            detail_url = build_history_detail_url(symbol, announcement_id, item_org_id, publish_time)
            content = title
            if include_fulltext:
                adjunct_url = str(item.get("adjunctUrl") or "").strip()
                pdf_url = build_pdf_url(adjunct_url)
                try:
                    extracted = extract_pdf_text(pdf_url, max_chars=fulltext_max_chars)
                    if extracted:
                        content = extracted
                except Exception:
                    content = title
            rows.append(
                {
                    "source": "巨潮资讯网/历史公告",
                    "title": f"{company_name or symbol}：{title}",
                    "content": content,
                    "publish_time": publish_time,
                    "url": detail_url,
                    "symbol_or_subject": ts_code,
                }
            )
            if len(rows) >= limit_per_symbol:
                return rows
    return rows
