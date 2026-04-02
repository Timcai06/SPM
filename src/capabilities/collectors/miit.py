from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List

from .common import fetch_text, strip_tags


MIIT_HOME_URL = "https://www.miit.gov.cn/"
MIIT_KEYWORDS = ("通知", "方案", "指导意见", "行动", "产业", "工业", "信息化", "新能源", "光伏", "氢能", "算力")


def parse_detail_publish_date(url: str) -> str:
    html = fetch_text(url)
    # Most MIIT pages carry MakeTime meta.
    m = re.search(r'<meta name="MakeTime" content="([0-9]{4}-[0-9]{2}-[0-9]{2})', html)
    if m:
        return m.group(1)
    m = re.search(r"([0-9]{4}-[0-9]{2}-[0-9]{2})", html)
    if m:
        return m.group(1)
    return datetime.now().strftime("%Y-%m-%d")


def collect(limit: int = 20) -> List[Dict[str, str]]:
    html = fetch_text(MIIT_HOME_URL)
    pattern = re.compile(r'<a[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<title>[^<]{6,120})</a>', re.S)
    rows: List[Dict[str, str]] = []
    seen: set[str] = set()
    for m in pattern.finditer(html):
        href = m.group("href").strip().replace("&amp;", "&")
        title = strip_tags(m.group("title")).strip()
        if not title or not any(k in title for k in MIIT_KEYWORDS):
            continue
        # Prefer policy/news pages with clear financial relevance.
        if not any(seg in href for seg in ("/zwgk/zcwj/wjfb/", "/xwfb/xwfbh/", "/xwfb/bldhd/")):
            continue
        if href.startswith("//"):
            url = "https:" + href
        elif href.startswith("/"):
            url = "https://www.miit.gov.cn" + href
        elif href.startswith("http"):
            url = href
        else:
            url = "https://www.miit.gov.cn/" + href.lstrip("./")
        if url in seen:
            continue
        seen.add(url)
        publish_date = parse_detail_publish_date(url)
        rows.append(
            {
                "source": "工信部/政策文件",
                "title": title,
                "content": title,
                "publish_time": publish_date,
                "url": url,
                "symbol_or_subject": "政策/产业",
            }
        )
        if len(rows) >= limit:
            break
    return rows
