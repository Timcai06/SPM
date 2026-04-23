from __future__ import annotations

import logging
import akshare as ak
import pandas as pd
from typing import Dict, List
from datetime import datetime

from modules.collectors.domain.raw_event_categories import COMPANY_EVENT

logger = logging.getLogger(__name__)

# Top active stocks symbols for broad announcement/news coverage
# This is a sample list; in a real scenario, this could be dynamic or based on HS300/CSI500.
TOP_STOCKS = [
    "600519", "601318", "000858", "601888", "600036", "600276", "600900", "000333", "603288", "002415",
    "601166", "601398", "600030", "000001", "600887", "600048", "601328", "601288", "601939", "600000",
    "000651", "603259", "600309", "300750", "300059", "002475", "002594", "601601", "601857", "601012"
]

def collect(limit: int = 10) -> List[Dict[str, str]]:
    """Collect recent stock news/announcements using AKShare.
    
    Returns a list of dicts with keys: source, title, content, publish_time, url, symbol_or_subject.
    """
    all_rows: List[Dict[str, str]] = []
    
    # We fetch a few top stocks to get representative 'announcements' which are mirrored in EM news.
    # To keep it efficient within the limit, we iterate until we hit the total limit.
    for symbol in TOP_STOCKS:
        if len(all_rows) >= limit:
            break
            
        try:
            # em_news = ak.stock_news_em(symbol=symbol)
            # Use raw eastmoney news if possible as it is more diverse than just one stock.
            # However, stock_news_em is very specific to company events.
            df = ak.stock_news_em(symbol=symbol)
            if df.empty:
                continue
            
            # Map columns: 关键词, 新闻标题, 新闻内容, 发布时间, 文章来源, 新闻链接
            for _, row in df.iterrows():
                if len(all_rows) >= limit:
                    break
                    
                all_rows.append({
                    "source": f"AKShare/EastMoney/{row['文章来源']}",
                    "title": str(row['新闻标题']),
                    "content": str(row['新闻内容']),
                    "publish_time": str(row['发布时间']),
                    "url": str(row['新闻链接']),
                    "symbol_or_subject": COMPANY_EVENT
                })
        except Exception as e:
            logger.warning(f"Failed to fetch news for {symbol} via AKShare: {e}")
            continue

    # Return only up to the limit across all stocks
    return all_rows[:limit]
