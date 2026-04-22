#!/usr/bin/env python3
"""Build a lightweight canonical event layer from structured events."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import date as date_type, datetime
from pathlib import Path
from typing import Dict, List, Set


ROOT = Path(__file__).resolve().parents[3]
INPUT_PATH = ROOT / "output" / "structured_events.csv"
OUTPUT_DIR = ROOT / "output"
CANONICAL_EVENTS_PATH = OUTPUT_DIR / "canonical_events.csv"
CANONICAL_MAP_PATH = OUTPUT_DIR / "event_canonical_map.csv"
REPORT_PATH = ROOT / "report" / "event_canonicalization_report.md"

TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fffA-Za-z0-9\-]+")
GENERIC_TOKENS = {
    "相关事件",
    "事件",
    "公告",
    "发布",
    "举行",
    "召开",
    "财新闻",
    "新华社",
    "央视网",
    "中国政府网",
    "中国证监会",
    "证监会",
    "工信部",
    "政策文件",
    "股市快讯",
    "最新公告",
    "mini",
}
GENERIC_CHINESE_SUFFIXES = ("相关事件", "事件", "公告", "新闻发布会", "发布会")


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: List[Dict[str, object]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_date(value) -> date_type:
    if isinstance(value, date_type):
        return value
    return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()


def normalize_phrase(text: str) -> str:
    text = re.sub(r"\s+", "", text or "")
    for suffix in GENERIC_CHINESE_SUFFIXES:
        if text.endswith(suffix):
            text = text[: -len(suffix)]
    return text.strip("｜|:：，,。. ")


def extract_entities(raw: str) -> List[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    result = []
    for item in data:
        value = normalize_phrase(str(item))
        if value and value not in result:
            result.append(value)
    return result


def tokenize(*parts: str) -> Set[str]:
    tokens: Set[str] = set()
    for part in parts:
        for token in TOKEN_PATTERN.findall(part or ""):
            token = normalize_phrase(token)
            if len(token) < 2:
                continue
            if token in GENERIC_TOKENS:
                continue
            tokens.add(token)
    return tokens


def jaccard(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class DSU:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra = self.find(a)
        rb = self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def should_merge(left: Dict[str, object], right: Dict[str, object]) -> bool:
    if left["event_subject_type"] != right["event_subject_type"]:
        return False
    if abs((left["event_date"] - right["event_date"]).days) > 3:
        return False

    shared_entities = set(left["entities"]) & set(right["entities"])
    if shared_entities:
        return True

    title_similarity = jaccard(left["name_tokens"], right["name_tokens"])
    full_similarity = jaccard(left["all_tokens"], right["all_tokens"])

    if title_similarity >= 0.5:
        return True
    if full_similarity >= 0.38 and left["industry_type"] == right["industry_type"]:
        return True

    left_name = left["normalized_name"]
    right_name = right["normalized_name"]
    if left_name and right_name:
        if left_name in right_name or right_name in left_name:
            return True

    return False


def choose_representative(rows: List[Dict[str, object]]) -> Dict[str, object]:
    def key(row: Dict[str, object]) -> tuple:
        return (
            int(row["heat_score"]),
            int(row["intensity_score"]),
            len(str(row["event_name"])),
        )

    return sorted(rows, key=key, reverse=True)[0]


def build_canonical_events(rows: List[Dict[str, str]]) -> tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    enriched: List[Dict[str, object]] = []
    for row in rows:
        entities = extract_entities(row.get("subject_entities", ""))
        normalized_name = normalize_phrase(row.get("event_name", ""))
        name_tokens = tokenize(normalized_name)
        summary_tokens = tokenize(row.get("event_summary", ""))
        enriched.append(
            {
                **row,
                "event_date": parse_date(row["event_date"]),
                "entities": entities,
                "normalized_name": normalized_name,
                "name_tokens": name_tokens,
                "all_tokens": name_tokens | summary_tokens | set(entities),
            }
        )

    dsu = DSU(len(enriched))
    for i in range(len(enriched)):
        for j in range(i + 1, len(enriched)):
            if should_merge(enriched[i], enriched[j]):
                dsu.union(i, j)

    grouped: Dict[int, List[Dict[str, object]]] = defaultdict(list)
    for idx, row in enumerate(enriched):
        grouped[dsu.find(idx)].append(row)

    canonical_rows: List[Dict[str, object]] = []
    mapping_rows: List[Dict[str, object]] = []
    for members in sorted(grouped.values(), key=lambda items: min(x["event_date"] for x in items), reverse=True):
        rep = choose_representative(members)
        member_ids = sorted(str(item["event_id"]) for item in members)
        cluster_text = "|".join(member_ids)
        canonical_id = "CEVT-" + hashlib.md5(cluster_text.encode("utf-8")).hexdigest()[:10]
        date_start = min(item["event_date"] for item in members).isoformat()
        date_end = max(item["event_date"] for item in members).isoformat()
        all_entities: List[str] = []
        for item in members:
            for entity in item["entities"]:
                if entity not in all_entities:
                    all_entities.append(entity)

        subject_counter = Counter(item["event_subject_type"] for item in members)
        industry_counter = Counter(item["industry_type"] for item in members)
        impact_counter = Counter(item["impact_scope"] for item in members)
        source_counter = Counter(item["source"] for item in members)
        canonical_rows.append(
            {
                "canonical_event_id": canonical_id,
                "canonical_event_name": rep["event_name"],
                "cluster_size": len(members),
                "date_start": date_start,
                "date_end": date_end,
                "event_subject_type": subject_counter.most_common(1)[0][0],
                "industry_type": industry_counter.most_common(1)[0][0],
                "impact_scope": impact_counter.most_common(1)[0][0],
                "representative_event_id": rep["event_id"],
                "representative_source": rep["source"],
                "max_heat_score": max(int(item["heat_score"]) for item in members),
                "max_intensity_score": max(int(item["intensity_score"]) for item in members),
                "member_event_ids": json.dumps(member_ids, ensure_ascii=False),
                "subject_entities": json.dumps(all_entities, ensure_ascii=False),
                "source_distribution": json.dumps(source_counter, ensure_ascii=False),
            }
        )
        for item in members:
            mapping_rows.append(
                {
                    "event_id": item["event_id"],
                    "canonical_event_id": canonical_id,
                    "event_name": item["event_name"],
                    "event_date": item["event_date"].isoformat(),
                    "source": item["source"],
                    "event_subject_type": item["event_subject_type"],
                    "industry_type": item["industry_type"],
                    "cluster_size": len(members),
                    "is_representative": str(item["event_id"] == rep["event_id"]).lower(),
                    "raw_text_ref": item["raw_text_ref"],
                }
            )
    return canonical_rows, mapping_rows


def write_report(path: Path, canonical_rows: List[Dict[str, object]], mapping_rows: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cluster_sizes = Counter(int(row["cluster_size"]) for row in canonical_rows)
    multi_source = sum(1 for row in canonical_rows if int(row["cluster_size"]) > 1)
    lines = [
        "# 事件归并报告",
        "",
        f"- 归并后标准事件簇数：{len(canonical_rows)}",
        f"- 原始结构化事件数：{len(mapping_rows)}",
        f"- 多成员事件簇数：{multi_source}",
        "",
        "## 事件簇规模分布",
    ]
    for size, count in sorted(cluster_sizes.items()):
        lines.append(f"- {size} 条成员：{count} 个事件簇")

    sample_clusters = sorted(
        [row for row in canonical_rows if int(row["cluster_size"]) > 1],
        key=lambda row: (int(row["cluster_size"]), int(row["max_heat_score"])),
        reverse=True,
    )[:10]
    lines.extend(["", "## 代表性归并样本"])
    if not sample_clusters:
        lines.append("- 当前没有发现可归并的多成员事件簇。")
    else:
        for row in sample_clusters:
            lines.append(
                f"- {row['canonical_event_id']} | {row['canonical_event_name']} | "
                f"cluster_size={row['cluster_size']} | "
                f"date_range={row['date_start']}~{row['date_end']}"
            )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_canonicalization_pipeline(db: str = None, input_rows: List[Dict[str, str]] = None) -> tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    """Orchestrate canonicalization from memory or database."""
    if input_rows is not None:
        rows = input_rows
    elif db:
        import psycopg
        from modules.runtime.adapters.db import dsn_for
        with psycopg.connect(dsn_for(db)) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM stg_structured_events")
                columns = [desc[0] for desc in cur.description]
                rows = [dict(zip(columns, row)) for row in cur.fetchall()]
    else:
        rows = read_csv(INPUT_PATH)
        
    if not rows:
        print("No structured events found for canonicalization.")
        return [], []
        
    canonical_rows, mapping_rows = build_canonical_events(rows)
    return canonical_rows, mapping_rows


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build canonical event clusters from structured events.")
    parser.add_argument("--db", help="Database name to read stg_structured_events from.")
    parser.add_argument("--input", default=str(INPUT_PATH), help="Structured events CSV path (if not using --db).")
    parser.add_argument("--canonical_output", default=str(CANONICAL_EVENTS_PATH), help="Canonical events CSV output path.")
    parser.add_argument("--mapping_output", default=str(CANONICAL_MAP_PATH), help="Event to canonical mapping CSV output path.")
    parser.add_argument("--report-path", default=str(REPORT_PATH), help="Markdown report output path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    if args.db:
        print(f"Reading structured events from database: {args.db}")
        canonical_rows, mapping_rows = run_canonicalization_pipeline(db=args.db)
    else:
        print(f"Reading structured events from file: {args.input}")
        rows = read_csv(Path(args.input))
        canonical_rows, mapping_rows = build_canonical_events(rows)

    write_csv(
        Path(args.canonical_output),
        canonical_rows,
        [
            "canonical_event_id",
            "canonical_event_name",
            "cluster_size",
            "date_start",
            "date_end",
            "event_subject_type",
            "industry_type",
            "impact_scope",
            "representative_event_id",
            "representative_source",
            "max_heat_score",
            "max_intensity_score",
            "member_event_ids",
            "subject_entities",
            "source_distribution",
        ],
    )
    write_csv(
        Path(args.mapping_output),
        mapping_rows,
        [
            "event_id",
            "canonical_event_id",
            "event_name",
            "event_date",
            "source",
            "event_subject_type",
            "industry_type",
            "cluster_size",
            "is_representative",
            "raw_text_ref",
        ],
    )
    write_report(Path(args.report_path), canonical_rows, mapping_rows)
    print(f"Wrote canonical events to {args.canonical_output}")
    print(f"Wrote event-canonical map to {args.mapping_output}")
    print(f"Wrote canonicalization report to {args.report_path}")


if __name__ == "__main__":
    main()
