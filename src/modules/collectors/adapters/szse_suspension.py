from __future__ import annotations

import json
from typing import Dict, List

from modules.collectors.domain.common import fetch_text, fetch_text_async, strip_tags


SZSE_LIST_URL = "https://www.szse.cn/api/disc/announcement/detailinfo"
SUSPENSION_KEYWORDS = ("停牌", "复牌", "停复牌")


def _is_suspension_announcement(title: str, category: str) -> bool:
    merged = f"{title} {category}"
    return any(keyword in merged for keyword in SUSPENSION_KEYWORDS)


async def collect(limit: int = 20) -> List[Dict[str, str]]:
    import aiohttp
    import asyncio
    import json
    
    async with aiohttp.ClientSession() as session:
        url = f"{SZSE_LIST_URL}?random=0.1&pageSize={max(limit, 20)}&pageNum=1&plateCode=szse"
        text = await fetch_text_async(url, session=session)
        payload = json.loads(text)
        rows: List[Dict[str, str]] = []
        for company in payload.get("data", []):
            sec_code = company.get("secCode", "").strip()
            sec_name = company.get("secName", "").strip()
            for item in company.get("announList", []):
                title = strip_tags(item.get("title", "").strip())
                category = strip_tags(item.get("bigCategoryName", "").strip())
                if not title or not _is_suspension_announcement(title, category):
                    continue
                attach_path = item.get("attachPath", "").strip()
                attach_url = f"https://disc.static.szse.cn/download{attach_path}" if attach_path else ""
                rows.append(
                    {
                        "source": "深交所/停复牌公告",
                        "title": title,
                        "content": "；".join(
                            [
                                title,
                                f"证券代码：{sec_code}",
                                f"证券简称：{sec_name}",
                                f"公告类别：{category or '停复牌'}",
                            ]
                        ),
                        "publish_time": item.get("publishTime", "").strip().split(" ")[0],
                        "url": attach_url,
                        "symbol_or_subject": sec_code,
                    }
                )
                if len(rows) >= limit:
                    return rows
        return rows

