#!/usr/bin/env python3
"""Runtime rule assembly with optional feedback keyword extension."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List

from modules.events.domain.classification_rules import (
    DURATION_RULES,
    INDUSTRY_RULES,
    PREDICTABILITY_RULES,
    SUBJECT_RULES,
)

ROOT = Path(__file__).resolve().parents[4]
RULE_FEEDBACK_PATH = ROOT / "output" / "meta" / "rule_feedback_keywords.csv"


def copy_rules(source: Dict[str, List[str]]) -> Dict[str, List[str]]:
    return {label: list(words) for label, words in source.items()}


def load_feedback_keywords(path: Path) -> Dict[str, Dict[str, List[str]]]:
    result: Dict[str, Dict[str, List[str]]] = {
        "subject": {},
        "industry": {},
        "predictability": {},
        "duration": {},
    }
    if not path.exists():
        return result
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            dimension = row.get("dimension", "").strip().lower()
            label = row.get("label", "").strip()
            keyword = row.get("keyword", "").strip()
            enabled = row.get("enabled", "true").strip().lower()
            if enabled in {"0", "false", "no"} or dimension not in result or not label or not keyword:
                continue
            result[dimension].setdefault(label, [])
            if keyword not in result[dimension][label]:
                result[dimension][label].append(keyword)
    return result


def merge_rules(base_rules: Dict[str, List[str]], feedback_rules: Dict[str, List[str]]) -> Dict[str, List[str]]:
    merged = copy_rules(base_rules)
    for label, words in feedback_rules.items():
        merged.setdefault(label, [])
        for word in words:
            if word not in merged[label]:
                merged[label].append(word)
    return merged


_feedback = load_feedback_keywords(RULE_FEEDBACK_PATH)
ACTIVE_SUBJECT_RULES = merge_rules(SUBJECT_RULES, _feedback["subject"])
ACTIVE_INDUSTRY_RULES = merge_rules(INDUSTRY_RULES, _feedback["industry"])
ACTIVE_PREDICTABILITY_RULES = merge_rules(PREDICTABILITY_RULES, _feedback["predictability"])
ACTIVE_DURATION_RULES = merge_rules(DURATION_RULES, _feedback["duration"])
ACTIVE_EVENT_KEYWORDS = sorted({word for words in ACTIVE_SUBJECT_RULES.values() for word in words})

