#!/usr/bin/env python3
"""Source credibility helpers."""

from __future__ import annotations


def classify_source_credibility(source_type: str, authority_level: str) -> str:
    if source_type in ("官方文件", "监管/交易所", "公司公告"):
        return "官方原文"
    if authority_level in ("central", "ministry", "exchange", "listed_company", "top_media"):
        return "权威转述"
    return "单一媒体"

