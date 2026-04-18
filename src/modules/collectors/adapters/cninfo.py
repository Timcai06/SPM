from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List

from modules.collectors.domain.common import fetch_json_post, strip_tags


CNINFO_LIST_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"


async def collect(limit: int = 20, lookback_days: int = 5) -> List[Dict[str, str]]:
    import aiohttp
    
    async with aiohttp.ClientSession() as session:
        from modules.collectors.domain.common import fetch_json_post_async
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=lookback_days)
        payload = await fetch_json_post_async(
            CNINFO_LIST_URL,
            {
                "pageNum": "1",
                "pageSize": str(limit),
                "tabName": "fulltext",
                "column": "szse",
                "plate": "sz",
                "stock": "",
                "searchkey": "",
                "secid": "",
                "category": "",
                "trade": "",
                "seDate": f"{start_date.isoformat()}~{end_date.isoformat()}",
                "sortName": "",
                "sortType": "",
                "isHLtitle": "true",
            },
            session=session
        )
        rows: List[Dict[str, str]] = []
        for item in payload.get("announcements", [])[:limit]:
            title = strip_tags(item.get("announcementTitle", "").strip())
            if not title:
                continue
            publish_time = ""
            if item.get("announcementTime"):
                publish_time = datetime.fromtimestamp(int(item["announcementTime"]) / 1000).strftime("%Y-%m-%d")
            adjunct_url = item.get("adjunctUrl", "").strip()
            url = f"https://www.cninfo.com.cn/{adjunct_url}" if adjunct_url else ""
            rows.append(
                {
                    "source": "巨潮资讯网/最新公告",
                    "title": title,
                    "content": "；".join(
                        [
                            title,
                            f'证券代码：{item.get("secCode", "").strip()}',
                            f'证券简称：{item.get("secName", "").strip()}',
                            f'板块：{item.get("pageColumn", "").strip()}',
                        ]
                    ),
                    "publish_time": publish_time,
                    "url": url,
                    "symbol_or_subject": item.get("secCode", "").strip(),
                }
            )
        return rows

