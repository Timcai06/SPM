from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Dict, List

from modules.collectors.domain.common import fetch_text, fetch_text_async, strip_tags
from modules.collectors.domain.raw_event_categories import MACRO_EVENT


YICAI_NEWS_URL = "https://www.yicai.com/news/"


def parse_time(value: str) -> str:
    value = value.strip()
    now = datetime.now()
    if re.fullmatch(r"[0-9]{1,2}分钟前", value):
        return (now - timedelta(minutes=int(value.replace("分钟前", "")))).strftime("%Y-%m-%d %H:%M:%S")
    if re.fullmatch(r"[0-9]{1,2}小时前", value):
        return (now - timedelta(hours=int(value.replace("小时前", "")))).strftime("%Y-%m-%d %H:%M:%S")
    if re.fullmatch(r"[0-9]{2}-[0-9]{2}\s+[0-9]{2}:[0-9]{2}", value):
        dt = datetime.strptime(f"{now.year}-{value}", "%Y-%m-%d %H:%M")
        if dt > now + timedelta(days=1):
            dt = dt.replace(year=dt.year - 1)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\s+[0-9]{2}:[0-9]{2}", value):
        dt = datetime.strptime(value, "%Y-%m-%d %H:%M")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return now.strftime("%Y-%m-%d %H:%M:%S")


async def collect(limit: int = 20) -> List[Dict[str, str]]:
    import aiohttp
    
    async with aiohttp.ClientSession() as session:
        html = await fetch_text_async(YICAI_NEWS_URL, session=session)
        pattern = re.compile(r'<a href="(?P<href>/news/[0-9]+\.html)"[^>]*>\s*<div class="m-list[\s\S]*?</a>', re.S)
        rows: List[Dict[str, str]] = []
        seen: set[str] = set()
        for match in pattern.finditer(html):
            url = "https://www.yicai.com" + match.group("href").strip()
            if url in seen:
                continue
            seen.add(url)
            block = match.group(0)
            title_match = re.search(r"<h2>(.*?)</h2>", block, re.S)
            summary_match = re.search(r"<p>(.*?)</p>", block, re.S)
            time_match = re.search(r'<div class="rightspan">\s*<span>(.*?)</span>', block, re.S)
            title = strip_tags(title_match.group(1)) if title_match else ""
            if not title:
                continue
            detail_html = fetch_text(url)
            content_match = re.search(r'<div class="m-text"[\s\S]*?<div class="m-txt">([\s\S]*?)</div>\s*</div>', detail_html, re.S)
            content = strip_tags(content_match.group(1)) if content_match else ""
            rows.append(
                {
                    "source": "第一财经/新闻",
                    "title": title,
                    "content": content or (strip_tags(summary_match.group(1)) if summary_match else title),
                    "publish_time": parse_time(strip_tags(time_match.group(1)) if time_match else ""),
                    "url": url,
                    "symbol_or_subject": MACRO_EVENT,
                }
            )
            if len(rows) >= limit:
                break
        return rows
