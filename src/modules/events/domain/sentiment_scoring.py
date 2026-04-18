#!/usr/bin/env python3
"""Sentiment scoring for structured event features."""

from __future__ import annotations

POSITIVE_WORDS = ("利好", "增长", "突破", "获批", "中标", "签约", "增持", "回购")
NEGATIVE_WORDS = ("利空", "下滑", "亏损", "处罚", "风险", "停产", "冲突升级")


def sentiment_score_0_100(text: str, label: str) -> int:
    pos = sum(1 for word in POSITIVE_WORDS if word in text)
    neg = sum(1 for word in NEGATIVE_WORDS if word in text)
    base = 62 if label == "利好" else 38 if label == "利空" else 50
    return max(0, min(base + pos * 5 - neg * 5, 100))

