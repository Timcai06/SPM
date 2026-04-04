from __future__ import annotations

import json
from typing import Dict, List

from .common import fetch_text, fetch_text_async, strip_tags, fetch_text_async, strip_tags


SSE_LIST_URL = "https://www.sse.com.cn/disclosure/listedinfo/announcement/json/stock_bulletin_publish_order.json"


async def collect(limit: int = 20) -> List[Dict[str, str]]:
    import aiohttp
    import json
    
    async with aiohttp.ClientSession() as session:
        text = await fetch_text_async(SSE_LIST_URL, session=session)
        payload = json.loads(text)
        rows: List[Dict[str, str]] = []
        for item in payload.get("publishData", [])[:limit]:
            title = item.get("bulletinTitle", "").strip()
            if not title:
                continue
            url = item.get("bulletinUrl", "").strip()
            if url.startswith("/"):
                url = "https://www.sse.com.cn" + url
            content_parts = [
                title,
                f'证券代码：{item.get("securityCode", "").strip()}',
                f'证券简称：{item.get("securityAbbr", "").strip()}',
                f'公告类型：{item.get("bulletinClassic", "").strip()}',
            ]
            rows.append(
                {
                    "source": "上交所/最新公告",
                    "title": title,
                    "content": "；".join([part for part in content_parts if part and not part.endswith("：")]),
                    "publish_time": item.get("discloseDate", "").strip(),
                    "url": url,
                    "symbol_or_subject": item.get("securityCode", "").strip(),
                }
            )
        return rows

