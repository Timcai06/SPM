from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List

from modules.collectors.domain.common import fetch_text_async, strip_tags
from modules.collectors.domain.raw_event_categories import POLICY_EVENT


MIIT_HOME_URL = "https://www.miit.gov.cn/"
MIIT_KEYWORDS = ("通知", "方案", "指导意见", "行动", "产业", "工业", "信息化", "新能源", "光伏", "氢能", "算力")


async def parse_detail_publish_date(url: str, session: object | None = None) -> str:
    html = await fetch_text_async(url, session=session)
    # Most MIIT pages carry MakeTime meta.
    m = re.search(r'<meta name="MakeTime" content="([0-9]{4}-[0-9]{2}-[0-9]{2})', html)
    if m:
        return m.group(1)
    m = re.search(r"([0-9]{4}-[0-9]{2}-[0-9]{2})", html)
    if m:
        return m.group(1)
    return datetime.now().strftime("%Y-%m-%d")


async def parse_detail_content(url: str, session: object | None = None) -> str:
    html = await fetch_text_async(url, session=session)
    match = re.search(r'id="con_con"[^>]*>([\s\S]*?)</div>\s*</div>', html, re.S)
    if match:
        return strip_tags(match.group(1))
    return ""


async def collect(limit: int = 20) -> List[Dict[str, str]]:
    import aiohttp
    import asyncio
    
    async with aiohttp.ClientSession(trust_env=False) as session:
        html = await fetch_text_async(MIIT_HOME_URL, session=session)
        pattern = re.compile(r'<a[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<title>[^<]{6,120})</a>', re.S)
        rows: List[Dict[str, str]] = []
        seen: set[str] = set()
        
        candidates = []
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
            candidates.append((url, title))
            if len(candidates) >= limit:
                break
        
        dates = await asyncio.gather(*[parse_detail_publish_date(url, session=session) for url, _ in candidates])
        contents = await asyncio.gather(*[parse_detail_content(url, session=session) for url, _ in candidates])
        
        for (url, title), publish_date, content in zip(candidates, dates, contents):
            rows.append(
                {
                    "source": "工信部/政策文件",
                    "title": title,
                    "content": content or title,
                    "publish_time": publish_date,
                    "url": url,
                    "symbol_or_subject": POLICY_EVENT,
                }
            )
        return rows
