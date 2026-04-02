from __future__ import annotations

import re
from typing import Dict, List, Optional

from .common import fetch_text, strip_tags


CSRC_LIST_URL = "https://www.csrc.gov.cn/csrc/c100028/common_list.shtml"


def extract_meta_content(html: str, name: str) -> str:
    pattern = re.compile(
        rf"<meta\s+name=['\"]{re.escape(name)}['\"]\s+content=['\"](.*?)['\"]\s*/?>",
        re.I | re.S,
    )
    match = pattern.search(html)
    return strip_tags(match.group(1)) if match else ""


def parse_list(limit: int) -> List[Dict[str, str]]:
    html = fetch_text(CSRC_LIST_URL)
    pattern = re.compile(
        r'<li>\s*<a href="(?P<href>/csrc/c100028/[^"]+/content\.shtml)"[^>]*>(?P<title>.*?)</a>\s*<span class="date">(?P<date>[0-9\-]+)</span>',
        re.S,
    )
    rows: List[Dict[str, str]] = []
    for match in pattern.finditer(html):
        rows.append(
            {
                "title": strip_tags(match.group("title")),
                "publish_time": match.group("date").strip(),
                "url": "https://www.csrc.gov.cn" + match.group("href").strip(),
            }
        )
        if len(rows) >= limit:
            break
    return rows


def parse_article(url: str) -> Optional[Dict[str, str]]:
    html = fetch_text(url)
    title = extract_meta_content(html, "ArticleTitle")
    publish_time = extract_meta_content(html, "PubDate")
    source_name = extract_meta_content(html, "ContentSource") or "中国证监会"
    description = extract_meta_content(html, "Description")
    content_match = re.search(r'<div class="detail-news">([\s\S]*?)<div\s+id="files"', html, re.I)
    if not content_match:
        content_match = re.search(r'<div class="detail-news">([\s\S]*?)</div>\s*</div>\s*</div>', html, re.I)
    if not title:
        title_match = re.search(r"<title>(.*?)_中国证券监督管理委员会</title>", html, re.S)
        title = strip_tags(title_match.group(1)) if title_match else ""
    if not publish_time:
        date_match = re.search(r"页面生成时间\s*([0-9:\-\s]+)", html)
        publish_time = date_match.group(1).strip() if date_match else ""

    if not (title and publish_time):
        return None
    content = strip_tags(content_match.group(1)) if content_match else ""
    if not content:
        content = description or title
    return {
        "source": f"中国证监会/{source_name}",
        "title": title,
        "content": content,
        "publish_time": publish_time,
        "url": url,
        "symbol_or_subject": "政策/监管",
    }


def collect(limit: int = 10) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for item in parse_list(limit):
        parsed = parse_article(item["url"])
        if parsed:
            rows.append(parsed)
    return rows

