from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

from modules.collectors.domain.common import fetch_text, fetch_text_async, strip_tags
from modules.collectors.domain.raw_event_categories import POLICY_EVENT


GOV_LIST_URL = "https://www.gov.cn/yaowen/liebiao/YAOWENLIEBIAO.json"
HIGH_VALUE_KEYWORDS = [
    "政策",
    "方案",
    "措施",
    "通知",
    "产业",
    "能源",
    "电网",
    "轻工业",
    "经济",
    "税收",
    "科技",
    "创新",
    "新能源",
]


def is_high_value_title(title: str) -> bool:
    return any(keyword in title for keyword in HIGH_VALUE_KEYWORDS)


async def parse_gov_article(url: str, session: object | None = None) -> Optional[Dict[str, str]]:
    html = await fetch_text_async(url, session=session)
    title_match = re.search(r'<h1 id="ti">\s*(.*?)\s*</h1>', html, re.S)
    date_match = re.search(r'<div class="pages-date">\s*([0-9\-:\s]+)', html, re.S)
    source_match = re.search(r'来源：\s*([^<\s]+)', html)
    content_match = re.search(r'<div class="pages_content"[^>]*>([\s\S]*?)</div>\s*<div class="editor">', html)
    if not (title_match and date_match and content_match):
        return None

    title = strip_tags(title_match.group(1))
    publish_time = re.sub(r"\s+", " ", date_match.group(1)).strip()
    source_name = strip_tags(source_match.group(1)) if source_match else "中国政府网"
    content = strip_tags(content_match.group(1))
    if not content:
        return None

    return {
        "source": f"中国政府网/{source_name}",
        "title": title,
        "content": content,
        "publish_time": publish_time,
        "url": url,
        "symbol_or_subject": POLICY_EVENT,
    }


async def collect(limit: int = 10, include_non_keyword: bool = False) -> List[Dict[str, str]]:
    import aiohttp
    import json
    import asyncio
    
    async with aiohttp.ClientSession(trust_env=False) as session:
        list_text = await fetch_text_async(GOV_LIST_URL, session=session)
        payload = json.loads(list_text)
        selected = []
        for item in payload:
            title = item.get("TITLE", "").strip()
            if not title:
                continue
            if include_non_keyword or is_high_value_title(title):
                selected.append(item)
            if len(selected) >= limit:
                break

        tasks = [parse_gov_article(item["URL"], session=session) for item in selected]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r]
