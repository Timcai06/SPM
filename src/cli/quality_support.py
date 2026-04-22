#!/usr/bin/env python3
"""Shared helpers for quality and delivery CLIs."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import psycopg

from modules.runtime.adapters.db import dsn_for

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QA_SNAPSHOT = ROOT / "output" / "meta" / "qa_snapshot.json"
DEFAULT_COLLECTOR_REPORT = ROOT / "output" / "collector_report.json"
DEFAULT_FEATURE_REPORT = ROOT / "output" / "feature_return_report.md"


def print_db_status(db_name: str) -> None:
    table_names = [
        "etl_runs",
        "etl_run_steps",
        "dataset_versions",
        "raw_documents",
        "structured_events",
        "company_relations",
        "company_profiles",
        "stock_daily_quotes",
        "market_environment_daily",
        "sentiment_propagation_daily",
        "event_research_samples",
        "event_candidates",
        "canonical_event_clusters",
        "canonical_event_memberships",
        "security_features_daily",
        "security_forward_labels_daily",
        "control_research_samples",
    ]
    print(f"Database status for: {db_name}")
    with psycopg.connect(dsn_for(db_name)) as conn:
        with conn.cursor() as cur:
            for table in table_names:
                cur.execute("SELECT to_regclass(%s)", (f"public.{table}",))
                exists = cur.fetchone()[0]
                if exists is None:
                    print(f"- {table}: missing")
                    continue
                cur.execute(f"SELECT count(*) FROM {table}")
                print(f"- {table}: {cur.fetchone()[0]}")


def parse_feature_top_reasons(path: Path, top_n: int = 3) -> list[tuple[str, int]]:
    if not path.exists():
        return []
    reasons: list[tuple[str, int]] = []
    in_section = False
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if text.startswith("## 三、不可计算样本原因"):
            in_section = True
            continue
        if in_section and text.startswith("## "):
            break
        if in_section and text.startswith("- ") and ":" in text:
            key, value = text[2:].split(":", 1)
            try:
                reasons.append((key.strip(), int(value.strip())))
            except Exception:
                continue
    reasons.sort(key=lambda x: x[1], reverse=True)
    return reasons[:top_n]


def parse_collector_failures(path: Path, top_n: int = 3) -> list[tuple[str, int]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    counter: dict[str, int] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        if str(item.get("success", "")).lower() == "true":
            continue
        category = str(item.get("failure_category") or "unknown").strip() or "unknown"
        counter[category] = counter.get(category, 0) + 1
    return sorted(counter.items(), key=lambda x: x[1], reverse=True)[:top_n]


def print_qa_summary(db_name: str, snapshot_path: Path, collector_report: Path, feature_report: Path) -> None:
    keys = [
        "raw_documents",
        "structured_events",
        "company_relations",
        "company_profiles",
        "stock_daily_quotes",
        "market_environment_daily",
        "sentiment_propagation_daily",
        "event_company_links",
        "event_propagation_edges",
        "event_research_samples",
        "control_research_samples",
        "security_features_daily",
        "security_forward_labels_daily",
    ]
    counts: dict[str, int] = {}
    labeled = 0
    with psycopg.connect(dsn_for(db_name)) as conn:
        with conn.cursor() as cur:
            for table in keys:
                cur.execute("SELECT to_regclass(%s)", (f"public.{table}",))
                exists = cur.fetchone()[0]
                if exists is None:
                    counts[table] = -1
                    continue
                cur.execute(f"SELECT count(*) FROM {table}")
                counts[table] = int(cur.fetchone()[0])
            cur.execute(
                """
                SELECT count(*)
                FROM event_research_samples
                WHERE label_car_w1 IS NOT NULL OR label_car_w3 IS NOT NULL OR label_car_w5 IS NOT NULL
                """
            )
            labeled = int(cur.fetchone()[0])

    prev_counts: dict[str, int] = {}
    if snapshot_path.exists():
        try:
            payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
            prev_counts = {str(k): int(v) for k, v in payload.get("counts", {}).items()}
        except Exception:
            prev_counts = {}

    total_samples = counts.get("event_research_samples", 0)
    label_ratio = (labeled / total_samples) if total_samples > 0 else 0.0
    print(f"QA summary for: {db_name}")
    for key in keys:
        current = counts.get(key, -1)
        prev = prev_counts.get(key)
        if current < 0:
            print(f"- {key}: missing")
            continue
        if prev is None:
            print(f"- {key}: {current} (delta: n/a)")
        else:
            print(f"- {key}: {current} (delta: {current - prev:+d})")
    print(f"- labeled_samples: {labeled}")
    print(f"- label_ratio: {label_ratio:.2%}")

    collector_top = parse_collector_failures(collector_report, top_n=3)
    feature_top = parse_feature_top_reasons(feature_report, top_n=3)
    print(f"- collector_fail_top3: {', '.join(f'{k}:{v}' for k, v in collector_top) if collector_top else 'none'}")
    print(f"- feature_reason_top3: {', '.join(f'{k}:{v}' for k, v in feature_top) if feature_top else 'none'}")

    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(
        json.dumps(
            {
                "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "db": db_name,
                "counts": counts,
                "labeled_samples": labeled,
                "label_ratio": label_ratio,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
