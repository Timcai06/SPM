from __future__ import annotations

import json
from typing import Dict, List

from .common import fetch_text, fetch_text_async, strip_tags


SZSE_LIST_URL = "https://www.szse.cn/api/disc/announcement/detailinfo"


async def collect(limit: int = 20) -> List[Dict[str, str]]:
    import aiohttp
    import json
    
    async with aiohttp.ClientSession() as session:
        url = f"{SZSE_LIST_URL}?random=0.1&pageSize={limit}&pageNum=1&plateCode=szse"
        text = await fetch_text_async(url, session=session)
        payload = json.loads(text)
        rows: List[Dict[str, str]] = []
        for company in payload.get("data", []):
            sec_code = company.get("secCode", "").strip()
            sec_name = company.get("secName", "").strip()
            for item in company.get("announList", []):
                title = strip_tags(item.get("title", "").strip())
                if not title:
                    continue
                attach_path = item.get("attachPath", "").strip()
                attach_url = f"https://disc.static.szse.cn/download{attach_path}" if attach_path else ""
                rows.append(
                    {
                        "source": "深交所/上市公司公告",
                        "title": title,
                        "content": "；".join(
                            [
                                title,
                                f"证券代码：{sec_code}",
                                f"证券简称：{sec_name}",
                                f"公告类别：{item.get('bigCategoryName', '').strip()}",
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

