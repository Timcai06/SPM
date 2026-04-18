from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List, Optional

from modules.collectors.domain.common import fetch_text, fetch_text_async, strip_tags


EASTMONEY_INDUSTRY_URL = "https://finance.eastmoney.com/a/cywjh.html"


def parse_datetime(text: str) -> str:
    match = re.search(r"([0-9]{4}-[0-9]{2}-[0-9]{2})(?:\s+([0-9]{2}:[0-9]{2}))?", text)
    if not match:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"{match.group(1)} {(match.group(2) or '00:00')}:00"


async def parse_article(url: str, session: object | None = None) -> Optional[Dict[str, str]]:
    html = await fetch_text_async(url, session=session)
    title_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    if not title_match:
        title_match = re.search(r"<title>(.*?)_.*?</title>", html, re.S)
    content_match = re.search(r'<div[^>]+id="ContentBody"[^>]*>([\s\S]*?)</div>', html, re.I)
    if not content_match:
        content_match = re.search(r'<div[^>]+class="newsContent"[^>]*>([\s\S]*?)</div>', html, re.I)
    time_match = re.search(r'时间[:：]?\s*([0-9:\-\s]+)', html)
    if not time_match:
        time_match = re.search(r'publishDate["\']?\s*[:=]\s*["\']([^"\']+)["\']', html)

    title = strip_tags(title_match.group(1)) if title_match else ""
    if not title:
        return None
    content = strip_tags(content_match.group(1)) if content_match else title
    return {
        "source": "东方财富/行业资讯",
        "title": title,
        "content": content or title,
        "publish_time": parse_datetime(time_match.group(1)) if time_match else datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "url": url,
        "symbol_or_subject": "行业/市场新闻",
    }


async def collect(limit: int = 20) -> List[Dict[str, str]]:
    import aiohttp
    import asyncio
    
    async with aiohttp.ClientSession() as session:
        html = await fetch_text_async(EASTMONEY_INDUSTRY_URL, session=session)
        links = re.findall(r'https://finance\.eastmoney\.com/a/[0-9]+\.html', html)
        rows: List[Dict[str, str]] = []
        seen: set[str] = set()
        
        candidates = []
        for link in links:
            if link in seen:
                continue
            seen.add(link)
            candidates.append(link)
            if len(candidates) >= limit:
                break
        
        tasks = [parse_article(link, session=session) for link in candidates]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r]

