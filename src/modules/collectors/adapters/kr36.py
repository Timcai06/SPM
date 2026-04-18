from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Dict, List, Optional

from modules.collectors.domain.common import fetch_text, fetch_text_async, strip_tags


KR36_FLASH_STOCK_URL = "https://www.36kr.com/newsflashes/catalog/2"


def extract_initial_state(html: str) -> Optional[Dict[str, object]]:
    match = re.search(r"window\.initialState\s*=\s*(\{[\s\S]*?\})</script>", html)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


async def collect(limit: int = 20) -> List[Dict[str, str]]:
    import aiohttp
    
    async with aiohttp.ClientSession() as session:
        html = await fetch_text_async(KR36_FLASH_STOCK_URL, session=session)
        state = extract_initial_state(html)
        if not state:
            return []
        item_list = (
            state.get("newsflashCatalogData", {})
            .get("data", {})
            .get("newsflashList", {})
            .get("data", {})
            .get("itemList", [])
        )
        # If newsflashList direct data fails, try one level deeper
        if not item_list:
            item_list = state.get("newsflashCatalogData", {}).get("data", {}).get("newsflashList", {}).get("data", {}).get("itemList", [])
        
        rows: List[Dict[str, str]] = []
        for item in item_list:
            material = item.get("templateMaterial", {})
            title = strip_tags(str(material.get("widgetTitle", "")).strip())
            if not title:
                continue
            content = strip_tags(str(material.get("widgetContent", "")).strip()) or title
            publish_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if material.get("publishTime"):
                publish_time = datetime.fromtimestamp(int(material["publishTime"]) / 1000).strftime("%Y-%m-%d %H:%M:%S")
            item_id = material.get("itemId") or item.get("itemId")
            rows.append(
                {
                    "source": "36氪/股市快讯",
                    "title": title,
                    "content": content,
                    "publish_time": publish_time,
                    "url": f"https://www.36kr.com/newsflashes/{item_id}" if item_id else KR36_FLASH_STOCK_URL,
                    "symbol_or_subject": "行业/股市快讯",
                }
            )
            if len(rows) >= limit:
                break
        return rows

