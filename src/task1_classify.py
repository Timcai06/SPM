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
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


ROOT = Path(__file__).resolve().parent.parent
INPUT_PATH = ROOT / "data" / "demo_news.csv"
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


SUBJECT_RULES = {
    "地缘类": ["空战", "冲突", "地缘", "印巴", "克什米尔", "战机", "局势升级"],
    "政策类": ["政策", "发改委", "国务院", "证监会", "支持", "措施", "规划"],
    "公司类": ["公告", "合同", "并购", "重组", "回购", "定增", "业绩预告"],
    "行业类": ["行业", "产业链", "景气", "协会", "供需", "价格上涨", "技术突破", "样机"],
    "宏观类": ["降息", "降准", "CPI", "PPI", "GDP", "出口", "财政"],
}

INDUSTRY_RULES = {
    "军工": ["军工", "战机", "导弹", "无人机", "军品", "空战"],
    "新能源": ["新能源", "储能", "锂电", "光伏", "风电", "电池"],
    "科技": ["科技", "机器人", "芯片", "算力", "AI", "人形机器人", "样机"],
    "消费": ["消费", "白酒", "旅游", "零售", "餐饮"],
}

PREDICTABILITY_RULES = {
    "突发型": ["空战", "爆发", "冲突", "突发", "事故", "击落"],
    "预披露型": ["公告", "预告", "政策", "规划", "发布", "签订"],
}

DURATION_RULES = {
    "脉冲型": ["空战", "冲突", "突发", "击落", "热点"],
    "中期型": ["政策", "合同", "示范项目", "订单", "扩产", "发布", "样机"],
    "长尾型": ["规划", "技术突破", "产业趋势", "长期"],
}

POSITIVE_WORDS = [
    "利好",
    "支持",
    "积极",
    "增长",
    "提升",
    "带动",
    "受益",
    "突破",
    "签订",
]
NEGATIVE_WORDS = ["利空", "下滑", "亏损", "处罚", "暴跌", "风险", "停牌", "冲突升级"]
EVENT_KEYWORDS = sorted({word for words in SUBJECT_RULES.values() for word in words})
NON_EVENT_KEYWORDS = ["明星", "综艺", "娱乐", "广告", "直播带货"]
WEAK_NEUTRAL_KEYWORDS = ["年度报告摘要", "常规信息", "董事会报告", "财务报表"]
TITLE_EMPHASIS_WORDS = ["重大", "爆发", "发布", "签订", "支持", "击落", "突破"]
SOURCE_WEIGHTS = {
    "中国政府网": 1.0,
    "证监会官网": 1.0,
    "国家发改委": 0.95,
    "巨潮资讯网": 0.95,
    "财新网": 0.9,
    "第一财经": 0.85,
    "上交所": 0.9,
    "深交所": 0.9,
    "36氪": 0.75,
    "东方财富网": 0.7,
}
ENTITY_PATTERN = re.compile(r"[A-Z]{2,}\-?\d*|[0-9]{6}\.(?:SZ|SH)|印巴|克什米尔|歼\-?10CE|中航成飞|储能|机器人")


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


def load_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_rows_from_inputs(paths: List[Path]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for path in paths:
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


def detect_event(row: Dict[str, str], duplicate_group_size: int) -> CandidateResult:
    full_text = f'{row["title"]} {row["content"]}'
    publish_time = normalize_datetime(row["publish_time"])
    non_event_hits = keyword_hits(full_text, NON_EVENT_KEYWORDS)
    weak_hits = keyword_hits(full_text, WEAK_NEUTRAL_KEYWORDS)
    event_hits = keyword_hits(full_text, EVENT_KEYWORDS)

    if non_event_hits:
        return CandidateResult(
            row=row,
            normalized_publish_time=publish_time,
            dedup_key=dedup_key(row),
            duplicate_group_size=duplicate_group_size,
            is_event=False,
            filter_reason="non_financial_noise",
            evidence="命中非金融关键词: " + "|".join(non_event_hits),
            score_hint=0,
        )

    if weak_hits and not event_hits:
        return CandidateResult(
            row=row,
            normalized_publish_time=publish_time,
            dedup_key=dedup_key(row),
            duplicate_group_size=duplicate_group_size,
            is_event=False,
            filter_reason="routine_disclosure_without_signal",
            evidence="常规披露且无显著事件关键词: " + "|".join(weak_hits),
            score_hint=1,
        )

    score_hint = len(event_hits) + min(duplicate_group_size, 3)
    is_event = score_hint >= 2
    reason = "event_signal_detected" if is_event else "insufficient_signal"
    evidence = "命中事件关键词: " + ("|".join(event_hits) if event_hits else "无")
    return CandidateResult(
        row=row,
        normalized_publish_time=publish_time,
        dedup_key=dedup_key(row),
        duplicate_group_size=duplicate_group_size,
        is_event=is_event,
        filter_reason=reason,
        evidence=evidence,
        score_hint=score_hint,
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
        return "利好"
    if neg > pos:
        return "利空"
    return "中性"


def compute_heat_score(title: str, source: str, duplicate_group_size: int) -> int:
    source_score = int(SOURCE_WEIGHTS.get(source, 0.6) * 40)
    title_score = min(len(keyword_hits(title, TITLE_EMPHASIS_WORDS)) * 12, 24)
    duplicate_score = min(duplicate_group_size * 12, 36)
    return min(source_score + title_score + duplicate_score, 100)


def compute_intensity_score(text: str, subject_type: str, predictability_type: str) -> int:
    base = {
        "地缘类": 82,
        "政策类": 72,
        "公司类": 68,
        "行业类": 64,
        "宏观类": 75,
    }.get(subject_type, 55)
    if predictability_type == "突发型":
        base += 8
    if "重大" in text or "击落" in text or "爆发" in text:
        base += 6
    if "示范项目" in text or "若干措施" in text:
        base += 4
    return min(base, 100)


def compute_impact_scope(subject_type: str, industry_type: str, text: str) -> str:
    if subject_type in {"宏观类", "政策类"} and any(word in text for word in ["全国", "全市场", "行业"]):
        return "全市场"
    if subject_type in {"地缘类", "行业类", "政策类"}:
        return "行业"
    if subject_type == "公司类":
        return "个股链条"
    return "行业" if industry_type != "其他" else "个股链条"


def extract_subject_entities(text: str) -> List[str]:
    seen = []
    for match in ENTITY_PATTERN.findall(text):
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
        help="Input CSV file. Can be repeated. Defaults to data/demo_news.csv",
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
    return parser.parse_args()


def load_outputs_to_postgres(db_name: str) -> None:
    loader_path = ROOT / "src" / "task1_load_db.py"
    subprocess.run(
        ["python3", str(loader_path), "--db", db_name, "--quiet"],
        check=True,
        cwd=str(ROOT),
    )


def build_candidate_row(row: Dict[str, str], result: CandidateResult) -> Dict[str, object]:
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
        "evidence": result.evidence,
        "score_hint": result.score_hint,
    }


def build_structured_row(row: Dict[str, str], result: CandidateResult) -> Dict[str, object]:
    full_text = f'{row["title"]} {row["content"]}'
    subject_type, subject_hits = choose_label(full_text, SUBJECT_RULES, "行业类")
    industry_type, industry_hits = choose_label(full_text, INDUSTRY_RULES, "其他")
    predictability_type, predictability_hits = choose_label(full_text, PREDICTABILITY_RULES, "预披露型")
    duration_type, duration_hits = choose_label(full_text, DURATION_RULES, "中期型")
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
                "subject=" + (",".join(subject_hits) if subject_hits else "none"),
                "industry=" + (",".join(industry_hits) if industry_hits else "none"),
                "predictability=" + (",".join(predictability_hits) if predictability_hits else "none"),
                "duration=" + (",".join(duration_hits) if duration_hits else "none"),
            ]
        ),
    }


def classify_rows(rows: List[Dict[str, str]]) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    duplicate_counts = Counter(dedup_key(row) for row in rows)
    candidate_rows: List[Dict[str, object]] = []
    structured_rows: List[Dict[str, object]] = []
    seen_structured_dedup_keys = set()

    for row in rows:
        result = detect_event(row, duplicate_counts[dedup_key(row)])
        candidate_rows.append(build_candidate_row(row, result))
        if not result.is_event:
            continue
        if result.dedup_key in seen_structured_dedup_keys:
            continue
        seen_structured_dedup_keys.add(result.dedup_key)
        structured_rows.append(build_structured_row(row, result))
    return candidate_rows, structured_rows


def main() -> None:
    args = parse_args()
    input_paths = [Path(p).resolve() for p in args.inputs] if args.inputs else [INPUT_PATH]
    output_dir = Path(args.output_dir).resolve()
    raw_output_path = output_dir / "raw_event_candidates.csv"
    structured_output_path = output_dir / "structured_events.csv"

    rows = load_rows_from_inputs(input_paths)
    candidate_rows, structured_rows = classify_rows(rows)

    ensure_output_dir(output_dir)
    write_csv(
        raw_output_path,
        candidate_rows,
        RAW_CANDIDATE_FIELDS,
    )
    write_csv(
        structured_output_path,
        structured_rows,
        STRUCTURED_EVENT_FIELDS,
    )

    print(f"Loaded {len(rows)} rows from {len(input_paths)} input file(s)")
    print(f"Wrote {len(candidate_rows)} raw candidates to {raw_output_path}")
    print(f"Wrote {len(structured_rows)} structured events to {structured_output_path}")
    if not args.skip_db_load:
        load_outputs_to_postgres(args.db)
        print(f"Loaded outputs into PostgreSQL database: {args.db}")


if __name__ == "__main__":
    main()
