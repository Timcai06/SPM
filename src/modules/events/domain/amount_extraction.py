#!/usr/bin/env python3
"""Amount extraction and RMB normalization."""

from __future__ import annotations

import math
import re
from typing import List, Tuple

AMOUNT_PATTERN = re.compile(
    r"(?:约|近|超|逾|达|至|累计|合计|总计|总投资|募资|金额|规模|不超过|不少于|超过)?"
    r"\s*(\d+(?:\.\d+)?)\s*(万亿|亿港元|亿元|亿|千万元|百万元|万元|万港元|港元|美元|亿美元)"
)


def extract_amount_rmb(text: str) -> Tuple[float | None, float | None]:
    matches = AMOUNT_PATTERN.findall(text)
    if not matches:
        return None, None
    converted: List[float] = []
    for number, unit in matches:
        value = float(number)
        if unit == "万亿":
            value *= 1_0000_0000_0000
        elif unit == "亿港元":
            value *= 0.92 * 1_0000_0000
        elif unit in ("亿", "亿元"):
            value *= 1_0000_0000
        elif unit == "千万元":
            value *= 1_0000_0000
        elif unit == "百万元":
            value *= 100_0000
        elif unit == "万元":
            value *= 1_0000
        elif unit == "万港元":
            value *= 0.92 * 1_0000
        elif unit == "港元":
            value *= 0.92
        elif unit == "亿美元":
            value *= 7.2 * 1_0000_0000
        elif unit == "美元":
            value *= 7.2
        converted.append(value)
    max_amount = max(converted)
    return max_amount, round(math.log(max_amount + 1, 10), 6)
