#!/usr/bin/env python3
"""Task 1 MVP pipeline for event identification and classification.

This implementation intentionally uses only Python's standard library so it
can run in a clean environment. It reads raw text candidates from CSV, applies
deterministic rules for filtering/classification, and writes two outputs:

1. output/raw_event_candidates.csv
2. output/structured_events.csv
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import argparse
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.events.rules import (
    ANNOUNCEMENT_TEMPLATE_KEYWORDS,
    CSRC_HARD_EVENT_KEYWORDS,
    CSRC_ROUTINE_TITLE_KEYWORDS,
    DURATION_DEFAULT,
    DURATION_ENUM,
    DURATION_RULES,
    EVENT_DUPLICATE_BONUS_CAP,
    EVENT_SCORE_THRESHOLD,
    EVENT_SUBJECT_ENUM,
    GOV_NARRATIVE_KEYWORDS,
    HEAT_DUPLICATE_CAP,
    HEAT_DUPLICATE_PER_COUNT,
    HEAT_SOURCE_MULTIPLIER,
    HEAT_TITLE_CAP,
    HEAT_TITLE_PER_HIT,
    HEAT_TOTAL_CAP,
    IMPACT_SCOPE_DEFAULT,
    IMPACT_SCOPE_ENUM,
    IMPACT_WIDE_KEYWORDS,
    GENERIC_ENTITY_TOKENS,
    INDUSTRY_DEFAULT,
    INDUSTRY_ENUM,
    INDUSTRY_RULES,
    INTENSITY_BASE_BY_SUBJECT,
    INTENSITY_DEFAULT_BASE,
    INTENSITY_POLICY_BONUS,
    INTENSITY_POLICY_KEYWORDS,
    INTENSITY_SHOCK_BONUS,
    INTENSITY_SHOCK_KEYWORDS,
    INTENSITY_SURPRISE_BONUS,
    INTENSITY_TOTAL_CAP,
    MACRO_DATA_KEYWORDS,
    NEGATIVE_WORDS,
    NON_EVENT_KEYWORDS,
    POLICY_ACTION_KEYWORDS,
    POSITIVE_WORDS,
    PREDICTABILITY_DEFAULT,
    PREDICTABILITY_ENUM,
    PREDICTABILITY_RULES,
    RULE_VERSION,
    ROUTINE_ANNOUNCEMENT_KEYWORDS,
    LISTING_FINANCING_STRONG_KEYWORDS,
    LISTING_FINANCING_EXCLUSION_KEYWORDS,
    SENTIMENT_ENUM,
    SOURCE_WEIGHT_DEFAULT,
    SOURCE_WEIGHT_TOKENS,
    SUBJECT_DEFAULT,
    SUBJECT_RULES,
    TITLE_EMPHASIS_WORDS,
    WEAK_NEUTRAL_KEYWORDS,
)


ROOT = Path(__file__).resolve().parents[3]
INPUT_PATH = ROOT / "output" / "seeds" / "manual_news.csv"
RULE_FEEDBACK_PATH = ROOT / "output" / "meta" / "rule_feedback_keywords.csv"
OUTPUT_DIR = ROOT / "output"
RAW_OUTPUT_PATH = OUTPUT_DIR / "raw_event_candidates.csv"
STRUCTURED_OUTPUT_PATH = OUTPUT_DIR / "structured_events.csv"
DEFAULT_DB_NAME = "stock_event_mining"
RAW_CANDIDATE_FIELDS = [
    "source",
    "title",
    "publish_time",
    "url",
    "symbol_or_subject",
    "dedup_key",
    "duplicate_group_size",
    "is_event",
    "filter_reason",
    "evidence",
    "score_hint",
    "event_score",
    "event_threshold",
    "rule_version",
]
STRUCTURED_EVENT_FIELDS = [
    "event_id",
    "event_name",
    "event_date",
    "source",
    "event_subject_type",
    "duration_type",
    "predictability_type",
    "industry_type",
    "sentiment",
    "heat_score",
    "intensity_score",
    "impact_scope",
    "event_summary",
    "subject_entities",
    "raw_text_ref",
    "classification_evidence",
]

ENTITY_PATTERN = re.compile(r"[0-9]{6}\.(?:SZ|SH)|印巴|克什米尔|歼\-?10CE|中航成飞|储能|机器人")
GENERIC_EVENT_HITS = {"公告"}
LLM_SUBJECT_MAP = {
    "macro": "宏观类",
    "policy": "政策类",
    "industry": "行业类",
    "entity": "公司类",
    "company": "公司类",
    "shock": "地缘类",
    "geopolitical": "地缘类",
}
LLM_SENTIMENT_MAP = {
    "positive": "利好",
    "negative": "利空",
    "neutral": "中性",
}


def _copy_rules(source: Dict[str, List[str]]) -> Dict[str, List[str]]:
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
            if enabled in {"0", "false", "no"}:
                continue
            if dimension not in result or not label or not keyword:
                continue
            result[dimension].setdefault(label, [])
            if keyword not in result[dimension][label]:
                result[dimension][label].append(keyword)
    return result


def merge_rules(base_rules: Dict[str, List[str]], feedback_rules: Dict[str, List[str]]) -> Dict[str, List[str]]:
    merged = _copy_rules(base_rules)
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


@dataclass
class CandidateResult:
    row: Dict[str, str]
    normalized_publish_time: str
    dedup_key: str
    duplicate_group_size: int
    is_event: bool
    filter_reason: str
    evidence: str
    score_hint: int
    event_score: int
    event_threshold: int


def load_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        # Some upstream sources may include unexpected NUL bytes.
        # Strip them at read time to keep the pipeline resilient.
        cleaned_lines = (line.replace("\x00", "") for line in f)
        return list(csv.DictReader(cleaned_lines))


def load_rows_from_inputs(paths: List[Path]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for path in paths:
        if not path.exists():
            continue
        for row in load_rows(path):
            if row.get("url") == "local://manual-seed":
                continue
            rows.append(row)
    return rows


def normalize_datetime(value: str) -> str:
    value = value.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    raise ValueError(f"Unsupported publish_time format: {value}")


def canonical_text(text: str) -> str:
    cleaned = re.sub(r"\s+", "", text)
    cleaned = re.sub(r"[，。、“”‘’!！?？:：;；,\.]", "", cleaned)
    return cleaned.lower()


def dedup_key(row: Dict[str, str]) -> str:
    base = canonical_text(row["title"])[:80] + "::" + canonical_text(row["content"])[:160]
    return hashlib.md5(base.encode("utf-8")).hexdigest()[:12]


def keyword_hits(text: str, keywords: Iterable[str]) -> List[str]:
    return [kw for kw in keywords if kw in text]


def freeze_enum(value: str, allowed: Iterable[str], default: str) -> str:
    return value if value in set(allowed) else default


def resolve_source_weight(source: str) -> float:
    for token, weight in SOURCE_WEIGHT_TOKENS:
        if token in source:
            return weight
    return SOURCE_WEIGHT_DEFAULT


def detect_event(row: Dict[str, str], duplicate_group_size: int) -> CandidateResult:
    full_text = f'{row["title"]} {row["content"]}'
    publish_time = normalize_datetime(row["publish_time"])
    non_event_hits = keyword_hits(full_text, NON_EVENT_KEYWORDS)
    weak_hits = keyword_hits(full_text, WEAK_NEUTRAL_KEYWORDS)
    routine_hits = keyword_hits(full_text, ROUTINE_ANNOUNCEMENT_KEYWORDS)
    template_hits = keyword_hits(full_text, ANNOUNCEMENT_TEMPLATE_KEYWORDS)
    title_narrative_hits = keyword_hits(row["title"], GOV_NARRATIVE_KEYWORDS)
    title_policy_action_hits = keyword_hits(row["title"], POLICY_ACTION_KEYWORDS)
    title_macro_data_hits = keyword_hits(row["title"], MACRO_DATA_KEYWORDS)
    listing_financing_hits = keyword_hits(row["title"], LISTING_FINANCING_STRONG_KEYWORDS)
    listing_financing_exclusion_hits = keyword_hits(row["title"], LISTING_FINANCING_EXCLUSION_KEYWORDS)
    listing_financing_strong = bool(listing_financing_hits) and not listing_financing_exclusion_hits
    csrc_routine_hits = keyword_hits(row["title"], CSRC_ROUTINE_TITLE_KEYWORDS)
    csrc_hard_event_hits = keyword_hits(full_text, CSRC_HARD_EVENT_KEYWORDS)
    event_hits = keyword_hits(full_text, ACTIVE_EVENT_KEYWORDS)
    strong_event_hits = [kw for kw in event_hits if kw not in GENERIC_EVENT_HITS]

    if non_event_hits:
        return CandidateResult(
            row=row,
            normalized_publish_time=publish_time,
            dedup_key=dedup_key(row),
            duplicate_group_size=duplicate_group_size,
            is_event=False,
            filter_reason="non_financial_noise",
            evidence="命中非金融关键词: " + "|".join(non_event_hits) + f"; score=0; threshold={EVENT_SCORE_THRESHOLD}",
            score_hint=0,
            event_score=0,
            event_threshold=EVENT_SCORE_THRESHOLD,
        )

    if weak_hits and not event_hits:
        return CandidateResult(
            row=row,
            normalized_publish_time=publish_time,
            dedup_key=dedup_key(row),
            duplicate_group_size=duplicate_group_size,
            is_event=False,
            filter_reason="routine_disclosure_without_signal",
            evidence="常规披露且无显著事件关键词: " + "|".join(weak_hits) + f"; score=1; threshold={EVENT_SCORE_THRESHOLD}",
            score_hint=1,
            event_score=1,
            event_threshold=EVENT_SCORE_THRESHOLD,
        )

    if routine_hits and not strong_event_hits and not listing_financing_strong:
        return CandidateResult(
            row=row,
            normalized_publish_time=publish_time,
            dedup_key=dedup_key(row),
            duplicate_group_size=duplicate_group_size,
            is_event=False,
            filter_reason="routine_announcement_without_signal",
            evidence="常规公告且缺少强事件关键词: " + "|".join(routine_hits) + f"; score=1; threshold={EVENT_SCORE_THRESHOLD}",
            score_hint=1,
            event_score=1,
            event_threshold=EVENT_SCORE_THRESHOLD,
        )

    if template_hits and not strong_event_hits and not listing_financing_strong:
        return CandidateResult(
            row=row,
            normalized_publish_time=publish_time,
            dedup_key=dedup_key(row),
            duplicate_group_size=duplicate_group_size,
            is_event=False,
            filter_reason="announcement_template_without_signal",
            evidence="公告模板词且缺少强事件关键词: " + "|".join(template_hits) + f"; score=1; threshold={EVENT_SCORE_THRESHOLD}",
            score_hint=1,
            event_score=1,
            event_threshold=EVENT_SCORE_THRESHOLD,
        )

    if row.get("source", "").startswith(("上交所", "深交所", "巨潮资讯网")) and not strong_event_hits and not listing_financing_strong:
        return CandidateResult(
            row=row,
            normalized_publish_time=publish_time,
            dedup_key=dedup_key(row),
            duplicate_group_size=duplicate_group_size,
            is_event=False,
            filter_reason="generic_announcement_without_signal",
            evidence="公告源文本仅含通用披露词; score=1; threshold=" + str(EVENT_SCORE_THRESHOLD),
            score_hint=1,
            event_score=1,
            event_threshold=EVENT_SCORE_THRESHOLD,
        )

    if row.get("source", "").startswith("中国政府网") and title_narrative_hits and not title_policy_action_hits and not title_macro_data_hits:
        return CandidateResult(
            row=row,
            normalized_publish_time=publish_time,
            dedup_key=dedup_key(row),
            duplicate_group_size=duplicate_group_size,
            is_event=False,
            filter_reason="government_narrative_without_action",
            evidence="官媒叙事型标题且缺少正式政策动作/数据词: " + "|".join(title_narrative_hits) + f"; score=1; threshold={EVENT_SCORE_THRESHOLD}",
            score_hint=1,
            event_score=1,
            event_threshold=EVENT_SCORE_THRESHOLD,
        )

    if row.get("source", "").startswith("中国证监会"):
        only_csrc_token_signal = bool(event_hits) and set(event_hits) <= {"证监会"}
        if (csrc_routine_hits or only_csrc_token_signal) and not csrc_hard_event_hits and not title_policy_action_hits:
            return CandidateResult(
                row=row,
                normalized_publish_time=publish_time,
                dedup_key=dedup_key(row),
                duplicate_group_size=duplicate_group_size,
                is_event=False,
                filter_reason="csrc_routine_without_policy_action",
                evidence="证监会常规新闻且缺少制度动作词: "
                + ("|".join(csrc_routine_hits) if csrc_routine_hits else "证监会弱信号")
                + f"; score=1; threshold={EVENT_SCORE_THRESHOLD}",
                score_hint=1,
                event_score=1,
                event_threshold=EVENT_SCORE_THRESHOLD,
            )

    score_hint = len(event_hits) + min(duplicate_group_size, EVENT_DUPLICATE_BONUS_CAP)
    is_event = score_hint >= EVENT_SCORE_THRESHOLD
    reason = "event_signal_detected" if is_event else "insufficient_signal"
    evidence = (
        "命中事件关键词: "
        + ("|".join(event_hits) if event_hits else "无")
        + f"; score={score_hint}; threshold={EVENT_SCORE_THRESHOLD}"
    )
    return CandidateResult(
        row=row,
        normalized_publish_time=publish_time,
        dedup_key=dedup_key(row),
        duplicate_group_size=duplicate_group_size,
        is_event=is_event,
        filter_reason=reason,
        evidence=evidence,
        score_hint=score_hint,
        event_score=score_hint,
        event_threshold=EVENT_SCORE_THRESHOLD,
    )


def choose_label(text: str, rules: Dict[str, List[str]], default: str) -> Tuple[str, List[str]]:
    scores = []
    for label, keywords in rules.items():
        hits = keyword_hits(text, keywords)
        scores.append((label, hits))
    scores.sort(key=lambda item: len(item[1]), reverse=True)
    best_label, hits = scores[0]
    if not hits:
        return default, []
    return best_label, hits


def compute_sentiment(text: str) -> str:
    pos = len(keyword_hits(text, POSITIVE_WORDS))
    neg = len(keyword_hits(text, NEGATIVE_WORDS))
    if pos > neg:
        return freeze_enum("利好", SENTIMENT_ENUM, "中性")
    if neg > pos:
        return freeze_enum("利空", SENTIMENT_ENUM, "中性")
    return freeze_enum("中性", SENTIMENT_ENUM, "中性")


def compute_heat_score(title: str, source: str, duplicate_group_size: int) -> int:
    source_score = int(resolve_source_weight(source) * HEAT_SOURCE_MULTIPLIER)
    title_score = min(len(keyword_hits(title, TITLE_EMPHASIS_WORDS)) * HEAT_TITLE_PER_HIT, HEAT_TITLE_CAP)
    duplicate_score = min(duplicate_group_size * HEAT_DUPLICATE_PER_COUNT, HEAT_DUPLICATE_CAP)
    return min(source_score + title_score + duplicate_score, HEAT_TOTAL_CAP)


def compute_intensity_score(text: str, subject_type: str, predictability_type: str) -> int:
    base = INTENSITY_BASE_BY_SUBJECT.get(subject_type, INTENSITY_DEFAULT_BASE)
    if predictability_type == "突发型":
        base += INTENSITY_SURPRISE_BONUS
    if any(word in text for word in INTENSITY_SHOCK_KEYWORDS):
        base += INTENSITY_SHOCK_BONUS
    if any(word in text for word in INTENSITY_POLICY_KEYWORDS):
        base += INTENSITY_POLICY_BONUS
    return min(base, INTENSITY_TOTAL_CAP)


def compute_impact_scope(subject_type: str, industry_type: str, text: str) -> str:
    if subject_type in {"宏观类", "政策类"} and any(word in text for word in IMPACT_WIDE_KEYWORDS):
        return freeze_enum("全市场", IMPACT_SCOPE_ENUM, IMPACT_SCOPE_DEFAULT)
    if subject_type in {"地缘类", "行业类", "政策类"}:
        return freeze_enum("行业", IMPACT_SCOPE_ENUM, IMPACT_SCOPE_DEFAULT)
    if subject_type == "公司类":
        return freeze_enum("个股链条", IMPACT_SCOPE_ENUM, IMPACT_SCOPE_DEFAULT)
    default_scope = "行业" if industry_type != "其他" else "个股链条"
    return freeze_enum(default_scope, IMPACT_SCOPE_ENUM, IMPACT_SCOPE_DEFAULT)


def extract_subject_entities(text: str) -> List[str]:
    seen = []
    for match in ENTITY_PATTERN.findall(text):
        if match in GENERIC_ENTITY_TOKENS:
            continue
        if match not in seen:
            seen.append(match)
    return seen


def build_summary(title: str, content: str) -> str:
    fragment = content[:70].rstrip("，。；; ")
    return f"{title}。{fragment}"


def build_event_name(title: str, subject_entities: List[str]) -> str:
    if subject_entities:
        return f"{subject_entities[0]}相关事件"
    return title[:24]


def event_id(result: CandidateResult) -> str:
    raw = f'{result.normalized_publish_time}|{result.row["source"]}|{result.row["title"]}'
    return "EVT-" + hashlib.md5(raw.encode("utf-8")).hexdigest()[:10]


def ensure_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)


def write_csv(path: Path, rows: List[Dict[str, object]], fieldnames: List[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Task 1 event structuring pipeline.")
    parser.add_argument(
        "--input",
        action="append",
        dest="inputs",
        help="Input CSV file. Can be repeated. Defaults to output/seeds/manual_news.csv",
    )
    parser.add_argument(
        "--output-dir",
        default=str(OUTPUT_DIR),
        help="Directory for output CSV files.",
    )
    parser.add_argument(
        "--db",
        default=DEFAULT_DB_NAME,
        help="PostgreSQL database name for direct loading.",
    )
    parser.add_argument(
        "--skip-db-load",
        action="store_true",
        help="Only write CSV outputs and skip PostgreSQL loading.",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Enable a small LLM enrichment pass for rule-positive candidates.",
    )
    parser.add_argument(
        "--llm-max-rows",
        type=int,
        default=20,
        help="Max number of rule-positive rows to enrich with LLM per run.",
    )
    return parser.parse_args()


def load_outputs_to_postgres(db_name: str) -> None:
    loader_path = ROOT / "src" / "capabilities" / "storage" / "load_task1.py"
    subprocess.run(
        ["python3", str(loader_path), "--db", db_name, "--quiet"],
        check=True,
        cwd=str(ROOT),
    )


def build_candidate_row(row: Dict[str, str], result: CandidateResult) -> Dict[str, object]:
    full_text = f'{row["title"]} {row["content"]}'
    _, subject_hits = choose_label(full_text, ACTIVE_SUBJECT_RULES, SUBJECT_DEFAULT)
    _, industry_hits = choose_label(full_text, ACTIVE_INDUSTRY_RULES, INDUSTRY_DEFAULT)
    _, predictability_hits = choose_label(full_text, ACTIVE_PREDICTABILITY_RULES, PREDICTABILITY_DEFAULT)
    _, duration_hits = choose_label(full_text, ACTIVE_DURATION_RULES, DURATION_DEFAULT)
    evidence = (
        result.evidence
        + f"; rule_version={RULE_VERSION}"
        + "; dimensions="
        + "|".join(
            [
                "subject:" + (",".join(subject_hits) if subject_hits else "none"),
                "industry:" + (",".join(industry_hits) if industry_hits else "none"),
                "predictability:" + (",".join(predictability_hits) if predictability_hits else "none"),
                "duration:" + (",".join(duration_hits) if duration_hits else "none"),
            ]
        )
    )
    return {
        "source": row["source"],
        "title": row["title"],
        "publish_time": result.normalized_publish_time,
        "url": row["url"],
        "symbol_or_subject": row["symbol_or_subject"],
        "dedup_key": result.dedup_key,
        "duplicate_group_size": result.duplicate_group_size,
        "is_event": str(result.is_event).lower(),
        "filter_reason": result.filter_reason,
        "evidence": evidence,
        "score_hint": result.score_hint,
        "event_score": result.event_score,
        "event_threshold": result.event_threshold,
        "rule_version": RULE_VERSION,
    }


def build_structured_row(row: Dict[str, str], result: CandidateResult) -> Dict[str, object]:
    full_text = f'{row["title"]} {row["content"]}'
    subject_type, subject_hits = choose_label(full_text, ACTIVE_SUBJECT_RULES, SUBJECT_DEFAULT)
    industry_type, industry_hits = choose_label(full_text, ACTIVE_INDUSTRY_RULES, INDUSTRY_DEFAULT)
    predictability_type, predictability_hits = choose_label(full_text, ACTIVE_PREDICTABILITY_RULES, PREDICTABILITY_DEFAULT)
    duration_type, duration_hits = choose_label(full_text, ACTIVE_DURATION_RULES, DURATION_DEFAULT)
    subject_type = freeze_enum(subject_type, EVENT_SUBJECT_ENUM, SUBJECT_DEFAULT)
    industry_type = freeze_enum(industry_type, INDUSTRY_ENUM, INDUSTRY_DEFAULT)
    predictability_type = freeze_enum(predictability_type, PREDICTABILITY_ENUM, PREDICTABILITY_DEFAULT)
    duration_type = freeze_enum(duration_type, DURATION_ENUM, DURATION_DEFAULT)
    subject_entities = extract_subject_entities(full_text)
    sentiment = compute_sentiment(full_text)
    heat_score = compute_heat_score(row["title"], row["source"], result.duplicate_group_size)
    intensity_score = compute_intensity_score(full_text, subject_type, predictability_type)
    impact_scope = compute_impact_scope(subject_type, industry_type, full_text)
    return {
        "event_id": event_id(result),
        "event_name": build_event_name(row["title"], subject_entities),
        "event_date": result.normalized_publish_time.split(" ")[0],
        "source": row["source"],
        "event_subject_type": subject_type,
        "duration_type": duration_type,
        "predictability_type": predictability_type,
        "industry_type": industry_type,
        "sentiment": sentiment,
        "heat_score": heat_score,
        "intensity_score": intensity_score,
        "impact_scope": impact_scope,
        "event_summary": build_summary(row["title"], row["content"]),
        "subject_entities": json.dumps(subject_entities, ensure_ascii=False),
        "raw_text_ref": row["url"],
        "classification_evidence": "|".join(
            [
                f"rule_version={RULE_VERSION}",
                "subject=" + (",".join(subject_hits) if subject_hits else "none"),
                "industry=" + (",".join(industry_hits) if industry_hits else "none"),
                "predictability=" + (",".join(predictability_hits) if predictability_hits else "none"),
                "duration=" + (",".join(duration_hits) if duration_hits else "none"),
            ]
        ),
    }


import asyncio
import aiohttp
import os

SECRETS_DIR = ROOT / ".secrets"
LLM_KEY_FILE = SECRETS_DIR / "llm_api_key.txt"
LLM_BASE_URL_FILE = SECRETS_DIR / "llm_base_url.txt"
LLM_MODEL_FILE = SECRETS_DIR / "llm_model.txt"

class AsyncLLMClient:
    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        self.api_key = api_key or self._load_key()
        self.base_url = base_url or self._load_base_url()
        self.model = model or self._load_model()

    def _load_key(self) -> str:
        env_key = os.getenv("LLM_API_KEY", "").strip()
        if env_key:
            return env_key
        return self._read_secret_file(LLM_KEY_FILE)

    def _load_base_url(self) -> str:
        env_url = os.getenv("LLM_BASE_URL", "").strip()
        if env_url:
            return env_url.rstrip("/")
        file_url = self._read_secret_file(LLM_BASE_URL_FILE)
        if file_url:
            return file_url.rstrip("/")
        return "https://opencode.ai/zen/v1"

    def _load_model(self) -> str:
        env_model = os.getenv("LLM_MODEL", "").strip()
        if env_model:
            return env_model
        file_model = self._read_secret_file(LLM_MODEL_FILE)
        if file_model:
            return file_model
        return "gpt-5.4-mini"

    def _read_secret_file(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8").strip()
        except Exception:
            return ""

    async def extract_event_data(self, title: str, content: str) -> dict:
        """Call LLM to extract structured event information."""
        if not self.api_key:
            return {}

        prompt = f"""
你是一个专业的金融事件分析专家。请分析以下新闻，并判断它是否属于重要的股市基本面事件。
重要事件包括：产业政策变动、技术突破、重大公司行为（分红/并购/增发/高管变动）、宏观经济数据发布、行业重大突发事件。
不重要的事件包括：普通市场行情波动、非财经类社会新闻、重复新闻、纯技术指标讨论。

请严格返回以下JSON格式（不要包含markdown格式标记）：
{{
  "is_event": true/false,
  "event_name": "简洁的事件名称",
  "subject_type": "Macro/Policy/Industry/Entity/Shock",
  "industry": "涉及行业",
  "sentiment": "Positive/Negative/Neutral",
  "summary": "50字以内的核心内容综述"
}}

新闻标题：{title}
新闻正文：{content[:1000]}
"""
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/chat/completions", json=payload, headers=headers, timeout=30) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        data = json.loads(text)
                        return json.loads(data["choices"][0]["message"]["content"])
                    else:
                        body = await resp.text()
                        print(f"[WARN] LLM API Error: Status {resp.status}; body={body[:300]}")
                        return {}
        except Exception as e:
            print(f"[WARN] LLM API Exception: {e}")
            return {}


class AsyncOllamaClient:
    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen3:8b")

    async def extract_event_data(self, title: str, content: str) -> dict:
        prompt = f"""
你是一个专业的金融事件分析专家。请分析以下新闻，并判断它是否属于重要的股市基本面事件。
重要事件包括：产业政策变动、技术突破、重大公司行为、宏观经济数据发布、行业重大突发事件。
不重要的事件包括：普通市场行情波动、非财经类社会新闻、重复新闻、纯技术指标讨论。

请严格返回 JSON，不要返回 markdown，不要补充解释：
{{
  "is_event": true,
  "event_name": "简洁的事件名称",
  "subject_type": "Policy/Entity/Industry/Macro/Shock",
  "industry": "军工/新能源/消费/科技/其他 之一",
  "sentiment": "Positive/Negative/Neutral",
  "summary": "50字以内摘要"
}}

新闻标题：{title}
新闻正文：{content[:1000]}
"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1},
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/api/generate", json=payload, timeout=60) as resp:
                    text = await resp.text()
                    if resp.status != 200:
                        print(f"[WARN] Ollama API Error: Status {resp.status}; body={text[:300]}")
                        return {}
                    data = json.loads(text)
                    response_text = (data.get("response") or "").strip()
                    if not response_text:
                        return {}
                    return json.loads(response_text)
        except Exception as e:
            print(f"[WARN] Ollama API Exception: {e}")
            return {}

@dataclass
class LLMResultEnrichment:
    is_event_llm: bool = False
    event_name_llm: str = ""
    subject_type_llm: str = ""
    industry_llm: str = ""
    sentiment_llm: str = ""
    summary_llm: str = ""

def normalize_llm_subject(value: str, fallback: str) -> str:
    key = (value or "").strip().lower()
    return freeze_enum(LLM_SUBJECT_MAP.get(key, fallback), EVENT_SUBJECT_ENUM, fallback)


def normalize_llm_industry(value: str, fallback: str) -> str:
    text = (value or "").strip()
    return freeze_enum(text if text in INDUSTRY_ENUM else fallback, INDUSTRY_ENUM, fallback)


def normalize_llm_sentiment(value: str, fallback: str) -> str:
    key = (value or "").strip().lower()
    return freeze_enum(LLM_SENTIMENT_MAP.get(key, fallback), SENTIMENT_ENUM, fallback)


async def classify_rows_async(
    rows: List[Dict[str, str]], use_llm: bool = False, llm_max_rows: int = 20
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    """Classify rows with optional LLM second pass."""
    client = AsyncLLMClient()
    ollama_client = AsyncOllamaClient()
    semaphore = asyncio.Semaphore(5) # Concurrency limit to avoid rate limits
    
    # First Pass: Deterministic Rules (Fast & Free)
    duplicate_counts = Counter(dedup_key(row) for row in rows)
    candidate_results = []
    for row in rows:
        candidate_results.append(detect_event(row, duplicate_counts[dedup_key(row)]))
    
    llm_budget = 0

    async def process_one(row, res, allow_llm: bool):
        # We only call LLM if rules say it MIGHT be an event OR for enrichment
        if res.is_event and allow_llm and use_llm and client.api_key:
            async with semaphore:
                llm_data = await client.extract_event_data(row["title"], row["content"])
                if llm_data:
                    # Enrich original result
                    structured_row = build_structured_row(row, res)
                    llm_subject = normalize_llm_subject(
                        llm_data.get("subject_type", ""), structured_row["event_subject_type"]
                    )
                    llm_industry = normalize_llm_industry(
                        llm_data.get("industry", ""), structured_row["industry_type"]
                    )
                    llm_sentiment = normalize_llm_sentiment(
                        llm_data.get("sentiment", ""), structured_row["sentiment"]
                    )
                    llm_summary = (llm_data.get("summary") or structured_row["event_summary"]).strip()[:120]
                    llm_event_name = (llm_data.get("event_name") or structured_row["event_name"]).strip()[:80]
                    structured_row.update({
                        "event_name": llm_event_name,
                        "event_subject_type": llm_subject,
                        "industry_type": llm_industry,
                        "sentiment": llm_sentiment,
                        "event_summary": llm_summary,
                        "classification_evidence": structured_row["classification_evidence"]
                        + f"|llm=1|llm_subject={llm_subject}|llm_industry={llm_industry}|llm_sentiment={llm_sentiment}",
                    })
                    return build_candidate_row(row, res), structured_row
        if res.is_event and allow_llm and use_llm:
            async with semaphore:
                llm_data = await ollama_client.extract_event_data(row["title"], row["content"])
                if llm_data:
                    structured_row = build_structured_row(row, res)
                    llm_subject = normalize_llm_subject(
                        llm_data.get("subject_type", ""), structured_row["event_subject_type"]
                    )
                    llm_industry = normalize_llm_industry(
                        llm_data.get("industry", ""), structured_row["industry_type"]
                    )
                    llm_sentiment = normalize_llm_sentiment(
                        llm_data.get("sentiment", ""), structured_row["sentiment"]
                    )
                    llm_summary = (llm_data.get("summary") or structured_row["event_summary"]).strip()[:120]
                    llm_event_name = (llm_data.get("event_name") or structured_row["event_name"]).strip()[:80]
                    structured_row.update({
                        "event_name": llm_event_name,
                        "event_subject_type": llm_subject,
                        "industry_type": llm_industry,
                        "sentiment": llm_sentiment,
                        "event_summary": llm_summary,
                        "classification_evidence": structured_row["classification_evidence"]
                        + f"|llm=1|llm_backend=ollama|llm_subject={llm_subject}|llm_industry={llm_industry}|llm_sentiment={llm_sentiment}",
                    })
                    return build_candidate_row(row, res), structured_row

        # Fallback to rules-only
        return build_candidate_row(row, res), (build_structured_row(row, res) if res.is_event else None)

    tasks = []
    for row, res in zip(rows, candidate_results):
        allow_llm = False
        if res.is_event and llm_budget < llm_max_rows:
            allow_llm = True
            llm_budget += 1
        tasks.append(process_one(row, res, allow_llm))
    results = await asyncio.gather(*tasks)
    
    candidate_rows = []
    structured_rows = []
    seen_structured_dedup_keys = set()
    
    for row, (cand, struct) in zip(rows, results):
        candidate_rows.append(cand)
        if struct:
            # Simple dedup for structured events
            d_key = dedup_key(row)
            if d_key not in seen_structured_dedup_keys:
                seen_structured_dedup_keys.add(d_key)
                structured_rows.append(struct)
                
    return candidate_rows, structured_rows


def load_rows_from_db(db: str) -> List[Dict[str, str]]:
    """Load latest raw_documents from database for classification."""
    import psycopg
    from capabilities.storage.db_guard import dsn_for
    
    sql = """
        SELECT source, title, content, publish_time::text, url, symbol_or_subject 
        FROM raw_documents
        ORDER BY publish_time DESC
        LIMIT 1000;
    """
    with psycopg.connect(dsn_for(db)) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]


async def run_classification_pipeline(
    db: str,
    input_rows: Optional[List[Dict[str, str]]] = None,
    use_llm: bool = False,
    llm_max_rows: int = 20,
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    """Orchestrate classification and write results to Stage tables (Async)."""
    from capabilities.storage.load_task1 import load_stage_tables
    
    rows = input_rows if input_rows is not None else load_rows_from_db(db)
    if not rows:
        print("No documents found for classification.")
        return [], []
        
    candidate_rows, structured_rows = await classify_rows_async(
        rows, use_llm=use_llm, llm_max_rows=llm_max_rows
    )
    
    load_stage_tables(db, [], candidate_rows, structured_rows)
    return candidate_rows, structured_rows


def main() -> None:
    args = parse_args()
    
    async def _run():
        if args.inputs:
            input_paths = [Path(p).resolve() for p in args.inputs]
            rows = load_rows_from_inputs(input_paths)
            print(f"Loaded {len(rows)} rows from {len(input_paths)} input file(s)")
            candidate_rows, structured_rows = await classify_rows_async(
                rows, use_llm=args.use_llm, llm_max_rows=args.llm_max_rows
            )
        else:
            print(f"No input files provided. Reading from database: {args.db}")
            if args.skip_db_load:
                rows = load_rows_from_db(args.db)
                candidate_rows, structured_rows = await classify_rows_async(
                    rows, use_llm=args.use_llm, llm_max_rows=args.llm_max_rows
                )
            else:
                candidate_rows, structured_rows = await run_classification_pipeline(
                    args.db, use_llm=args.use_llm, llm_max_rows=args.llm_max_rows
                )

        output_dir = Path(args.output_dir).resolve()
        raw_output_path = output_dir / "raw_event_candidates.csv"
        structured_output_path = output_dir / "structured_events.csv"
        ensure_output_dir(output_dir)
        
        write_csv(raw_output_path, candidate_rows, RAW_CANDIDATE_FIELDS)
        write_csv(structured_output_path, structured_rows, STRUCTURED_EVENT_FIELDS)

        print(f"Wrote {len(candidate_rows)} raw candidates to {raw_output_path}")
        print(f"Wrote {len(structured_rows)} structured events to {structured_output_path}")

    asyncio.run(_run())


if __name__ == "__main__":
    main()
