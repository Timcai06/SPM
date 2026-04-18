from __future__ import annotations

import re
from typing import Dict, List, Optional

from modules.collectors.domain.common import fetch_text, fetch_text_async, strip_tags


NDRC_LIST_URL = "https://www.ndrc.gov.cn/xxgk/zcfb/tz/"


async def parse_list(limit: int, session: object | None = None) -> List[Dict[str, str]]:
    html = await fetch_text_async(NDRC_LIST_URL, session=session)
    pattern = re.compile(
        r'<li>\s*<a href="(?P<href>[^"]+)"[^>]*title="(?P<title>[^"]+)">.*?</a>[\s\S]*?<span>(?P<date>[0-9/]+)</span>\s*</li>',
        re.S,
    )
    rows: List[Dict[str, str]] = []
    for match in pattern.finditer(html):
        href = match.group("href").strip()
        title = strip_tags(match.group("title"))
        publish_time = match.group("date").replace("/", "-")
        if href.startswith("./"):
            url = NDRC_LIST_URL + href[2:]
        elif href.startswith("/"):
            url = "https://www.ndrc.gov.cn" + href
        else:
            url = href
        rows.append({"title": title, "publish_time": publish_time, "url": url})
        if len(rows) >= limit:
            break
    return rows


async def parse_article(url: str, session: object | None = None) -> Optional[Dict[str, str]]:
    html = await fetch_text_async(url, session=session)
    title_match = re.search(r'<meta name="ArticleTitle" content="([^"]+)">', html)
    if not title_match:
        title_match = re.search(r"<h2[^>]*>\s*(.*?)\s*</h2>", html, re.S)
    date_match = re.search(r'<meta name="PubDate" content="([0-9:\-\s]+)">', html)
    if not date_match:
        date_match = re.search(r'发布时间[:：]?\s*([0-9]{4}[/-][0-9]{2}[/-][0-9]{2})', html)
    content_match = re.search(r'<div class=TRS_Editor>([\s\S]*?)</div>\s*</div>\s*</div>', html)
    if not content_match:
        content_match = re.search(r'<div class="article_con">\s*<div class=TRS_Editor>([\s\S]*?)</div>', html)
    source_match = re.search(r'<meta name="ContentSource" content="([^"]*)">', html)
    if not source_match:
        source_match = re.search(r'来源[:：]?\s*([^<\s]+)', html)

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
        "publish_time": publish_time,
        "url": url,
        "symbol_or_subject": "政策/通知",
    }


async def collect(limit: int = 10) -> List[Dict[str, str]]:
    import aiohttp
    import asyncio
    async with aiohttp.ClientSession() as session:
        items = await parse_list(limit, session=session)
        tasks = [parse_article(item["url"], session=session) for item in items]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r]

