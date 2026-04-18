#!/usr/bin/env python3
"""LLM enrichment helpers for event classification."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import aiohttp

from modules.events.domain.classification_rules import SUBTYPE_RULES
from modules.events.domain.event_taxonomy import IMPACT_SCOPES, SHOCK_SOURCE_TYPES
from modules.events.domain.industry_mapping import SW_L1_NAMES

ROOT = Path(__file__).resolve().parents[4]
SECRETS_DIR = ROOT / ".secrets"
LLM_KEY_FILE = SECRETS_DIR / "llm_api_key.txt"
LLM_BASE_URL_FILE = SECRETS_DIR / "llm_base_url.txt"
LLM_MODEL_FILE = SECRETS_DIR / "llm_model.txt"
LLM_SUBJECT_MAP = {
    "macro": "宏观类",
    "policy": "政策类",
    "industry": "行业类",
    "entity": "公司类",
    "company": "公司类",
    "shock": "地缘类",
    "geopolitical": "地缘类",
}
LLM_SENTIMENT_MAP = {"positive": "利好", "negative": "利空", "neutral": "中性"}
LLM_HIGH_VALUE_SOURCE_TOKENS = (
    "中国政府网", "国家发展改革委", "中国证监会", "上交所", "深交所", "巨潮资讯网", "财新", "第一财经",
)
LLM_NO_OVERRIDE_REASONS = {
    "non_financial_noise",
    "routine_disclosure_without_signal",
    "routine_announcement_without_signal",
    "announcement_template_without_signal",
    "generic_announcement_without_signal",
    "government_narrative_without_action",
    "csrc_routine_without_policy_action",
}


def freeze_enum(value: str, allowed: Iterable[str], default: str) -> str:
    return value if value in set(allowed) else default


def should_trigger_llm(row: Dict[str, str], result: Any, structured_preview: Optional[Dict[str, object]], subject_default: str) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if abs(result.event_score - result.event_threshold) <= 1:
        reasons.append("borderline_score")
    source_text = row.get("source", "")
    if any(token in source_text for token in LLM_HIGH_VALUE_SOURCE_TOKENS):
        reasons.append("high_value_source")
    if structured_preview:
        if structured_preview.get("industry_type") == "其他":
            reasons.append("industry_other")
        if structured_preview.get("event_subject_type") == subject_default:
            reasons.append("subject_default")
    if result.duplicate_group_size >= 3:
        reasons.append("duplicate_cluster")
    return bool(reasons), reasons


def promote_candidate_result(result: Any, reason_suffix: str) -> Any:
    return result.__class__(
        row=result.row,
        normalized_publish_time=result.normalized_publish_time,
        dedup_key=result.dedup_key,
        duplicate_group_size=result.duplicate_group_size,
        is_event=True,
        filter_reason="llm_promoted_event",
        evidence=result.evidence + f"; llm_override={reason_suffix}",
        score_hint=result.score_hint,
        event_score=result.event_score,
        event_threshold=result.event_threshold,
    )


def can_llm_promote(result: Any) -> bool:
    return result.filter_reason not in LLM_NO_OVERRIDE_REASONS


class AsyncLLMClient:
    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        self.api_key = api_key or self._load_key()
        self.base_url = base_url or self._load_base_url()
        self.model = model or self._load_model()

    def _read_secret_file(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8").strip()
        except Exception:
            return ""

    def _load_key(self) -> str:
        return os.getenv("LLM_API_KEY", "").strip() or self._read_secret_file(LLM_KEY_FILE)

    def _load_base_url(self) -> str:
        return (os.getenv("LLM_BASE_URL", "").strip() or self._read_secret_file(LLM_BASE_URL_FILE) or "https://opencode.ai/zen/v1").rstrip("/")

    def _load_model(self) -> str:
        return os.getenv("LLM_MODEL", "").strip() or self._read_secret_file(LLM_MODEL_FILE) or "gpt-5.4-mini"

    async def extract_event_data(self, title: str, content: str) -> dict:
        if not self.api_key:
            return {}
        prompt = f"""
你是一个专业的金融事件分析专家。请分析以下新闻，并判断它是否属于重要的股市基本面事件。
请严格返回 JSON：
{{"is_event": true/false, "event_name": "简洁事件名", "subject_type": "Macro/Policy/Industry/Entity/Shock", "industry": "涉及行业", "sentiment": "Positive/Negative/Neutral", "summary": "50字摘要"}}
新闻标题：{title}
新闻正文：{content[:1000]}
"""
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/chat/completions", json=payload, headers=headers, timeout=30) as resp:
                    if resp.status != 200:
                        return {}
                    data = json.loads(await resp.text())
                    return json.loads(data["choices"][0]["message"]["content"])
        except Exception:
            return {}

    async def extract_feature_data(self, title: str, content: str, current: Dict[str, Any]) -> dict:
        if not self.api_key:
            return {}
        compact_content = content[:700]
        prompt = f"""
你是金融事件结构化专家。请只做保守纠偏，严格返回 JSON：
{{
  "sw_l1_industry": "必须是以下之一：{','.join(SW_L1_NAMES)}，若无法判断返回其他",
  "event_subject_subtype": "必须是以下之一：{','.join(SUBTYPE_RULES.keys())}，若无法判断返回{current.get('event_subject_subtype', '未细分')}",
  "shock_source_type": "必须是以下之一：{','.join(SHOCK_SOURCE_TYPES)}",
  "impact_scope": "必须是以下之一：{','.join(IMPACT_SCOPES)}",
  "confidence": 0.0
}}
当前结果：{json.dumps(current, ensure_ascii=False)}
标题：{title}
正文：{compact_content}
"""
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/chat/completions", json=payload, headers=headers, timeout=45) as resp:
                    if resp.status != 200:
                        return {}
                    data = json.loads(await resp.text())
                    return json.loads(data["choices"][0]["message"]["content"])
        except Exception:
            return {}


class AsyncOllamaClient:
    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen3:8b")

    async def extract_event_data(self, title: str, content: str) -> dict:
        prompt = f"""
你是一个专业的金融事件分析专家。请严格返回 JSON：
{{"is_event": true, "event_name": "简洁事件名", "subject_type": "Policy/Entity/Industry/Macro/Shock", "industry": "军工/新能源/消费/科技/其他", "sentiment": "Positive/Negative/Neutral", "summary": "50字摘要"}}
新闻标题：{title}
新闻正文：{content[:1000]}
"""
        payload = {"model": self.model, "prompt": prompt, "stream": False, "format": "json", "options": {"temperature": 0.1}}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/api/generate", json=payload, timeout=60) as resp:
                    if resp.status != 200:
                        return {}
                    data = json.loads(await resp.text())
                    text = (data.get("response") or "").strip()
                    return json.loads(text) if text else {}
        except Exception:
            return {}

    async def extract_feature_data(self, title: str, content: str, current: Dict[str, Any]) -> dict:
        compact_content = content[:700]
        prompt = f"""
你是金融事件结构化专家。请只做保守纠偏，并严格返回 JSON：
{{
  "sw_l1_industry": "从这些值中选择：{','.join(SW_L1_NAMES)}，若无法判断返回其他",
  "event_subject_subtype": "从这些值中选择：{','.join(SUBTYPE_RULES.keys())}",
  "shock_source_type": "从这些值中选择：{','.join(SHOCK_SOURCE_TYPES)}",
  "impact_scope": "从这些值中选择：{','.join(IMPACT_SCOPES)}",
  "confidence": 0.0
}}
当前结果：{json.dumps(current, ensure_ascii=False)}
标题：{title}
正文：{compact_content}
"""
        payload = {"model": self.model, "prompt": prompt, "stream": False, "format": "json", "options": {"temperature": 0.0}}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/api/generate", json=payload, timeout=60) as resp:
                    if resp.status != 200:
                        return {}
                    data = json.loads(await resp.text())
                    text = (data.get("response") or "").strip()
                    return json.loads(text) if text else {}
        except Exception:
            return {}


@dataclass
class LLMResultEnrichment:
    is_event_llm: bool = False
    event_name_llm: str = ""
    subject_type_llm: str = ""
    industry_llm: str = ""
    sentiment_llm: str = ""
    summary_llm: str = ""


def normalize_llm_subject(value: str, fallback: str, allowed_subjects: Iterable[str]) -> str:
    key = (value or "").strip().lower()
    return freeze_enum(LLM_SUBJECT_MAP.get(key, fallback), allowed_subjects, fallback)


def normalize_llm_industry(value: str, fallback: str, allowed_industries: Iterable[str]) -> str:
    text = (value or "").strip()
    return freeze_enum(text if text in set(allowed_industries) else fallback, allowed_industries, fallback)


def normalize_llm_sentiment(value: str, fallback: str, allowed_sentiments: Iterable[str]) -> str:
    key = (value or "").strip().lower()
    return freeze_enum(LLM_SENTIMENT_MAP.get(key, fallback), allowed_sentiments, fallback)


def normalize_llm_choice(value: str, fallback: str, allowed: Iterable[str]) -> str:
    text = (value or "").strip()
    return freeze_enum(text if text in set(allowed) else fallback, allowed, fallback)
