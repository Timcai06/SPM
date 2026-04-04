from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List

from .common import fetch_text, fetch_text_async, strip_tags


CAIXIN_MINI_URL = "https://mini.caixin.com/"


def parse_time(value: str) -> str:
    now = datetime.now()
    match = re.search(r"([0-9]{2})月([0-9]{2})日\s+([0-9]{2}:[0-9]{2})", value)
    if not match:
        return now.strftime("%Y-%m-%d %H:%M:%S")
    month, day, hm = match.group(1), match.group(2), match.group(3)
    dt = datetime.strptime(f"{now.year}-{month}-{day} {hm}", "%Y-%m-%d %H:%M")
    return dt.strftime("%Y-%m-%d %H:%M:%S")


async def collect(limit: int = 20) -> List[Dict[str, str]]:
    import aiohttp
    
    async with aiohttp.ClientSession() as session:
        html = await fetch_text_async(CAIXIN_MINI_URL, session=session)
        pattern = re.compile(r'<div class="boxa">([\s\S]*?)</div></div>', re.S)
        rows: List[Dict[str, str]] = []
        seen: set[str] = set()
        for block_match in pattern.finditer(html):
            block = block_match.group(1)
            title_match = re.search(r"<h4><a href=\"(?P<url>https://mini\.caixin\.com/[^\"]+)\">(?P<title>.*?)</a>", block, re.S)
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
            time_match = re.search(r"<span>(.*?)</span>", block, re.S)
            rows.append(
                {
                    "source": "财新网/mini",
                    "title": title,
                    "content": strip_tags(summary_match.group(1)) if summary_match else title,
                    "publish_time": parse_time(strip_tags(time_match.group(1)) if time_match else ""),
                    "url": url,
                    "symbol_or_subject": "宏观/地缘新闻",
                }
            )
            if len(rows) >= limit:
                break
        return rows

