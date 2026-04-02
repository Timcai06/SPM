#!/usr/bin/env python3
"""Basic validation checks for the task1 MVP outputs."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.events.rules import DURATION_ENUM, EVENT_SUBJECT_ENUM, IMPACT_SCOPE_ENUM, INDUSTRY_ENUM, PREDICTABILITY_ENUM, RULE_VERSION


ROOT = Path(__file__).resolve().parents[3]
RAW_OUTPUT_PATH = ROOT / "output" / "raw_event_candidates.csv"
STRUCTURED_OUTPUT_PATH = ROOT / "output" / "structured_events.csv"


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def check_non_empty(raw_rows, structured_rows) -> None:
    assert raw_rows, "raw_event_candidates.csv must not be empty"
    assert structured_rows, "structured_events.csv must not be empty"


def check_positive_case(structured_rows) -> None:
    positive_case = next((r for r in structured_rows if "印巴" in r["event_summary"] or "克什米尔" in r["event_summary"]), None)
    assert positive_case is not None, "Expected 印巴空战 case in structured events"
    assert positive_case["event_subject_type"] == "地缘类", "印巴空战 should be classified as 地缘类"
    assert positive_case["industry_type"] == "军工", "印巴空战 should map to 军工"
    assert positive_case["duration_type"] == "脉冲型", "印巴空战 should be 脉冲型"


def check_noise_case(raw_rows) -> None:
    noise_case = next((r for r in raw_rows if "综艺节目" in r["title"]), None)
    assert noise_case is not None, "Expected noise sample in raw candidates"
    assert noise_case["is_event"] == "false", "娱乐新闻 should not be classified as event"


def check_dedup_case(raw_rows) -> None:
    dedup_rows = [r for r in raw_rows if "印巴在克什米尔爆发大规模空战" in r["title"]]
    assert len(dedup_rows) == 2, "Expected duplicate positive samples"
    assert len({r["dedup_key"] for r in dedup_rows}) == 1, "Duplicate news should share the same dedup key"


def check_required_fields(structured_rows) -> None:
    required_fields = {
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
        "raw_text_ref",
    }
    assert required_fields.issubset(structured_rows[0].keys()), "structured_events.csv missing required fields"


def check_decision_threshold_fields(raw_rows) -> None:
    required = {"event_score", "event_threshold", "rule_version", "is_event"}
    assert required.issubset(raw_rows[0].keys()), "raw_event_candidates.csv missing decision threshold fields"
    for row in raw_rows:
        assert row["rule_version"] == RULE_VERSION, f"Unexpected rule version: {row['rule_version']}"
        score = int(row["event_score"])
        threshold = int(row["event_threshold"])
        decision = row["is_event"] == "true"
        assert decision == (score >= threshold), f"is_event decision mismatch for title={row['title']}"


def check_enum_values(structured_rows) -> None:
    for row in structured_rows:
        assert row["event_subject_type"] in EVENT_SUBJECT_ENUM, f"Invalid event_subject_type: {row['event_subject_type']}"
        assert row["duration_type"] in DURATION_ENUM, f"Invalid duration_type: {row['duration_type']}"
        assert row["predictability_type"] in PREDICTABILITY_ENUM, f"Invalid predictability_type: {row['predictability_type']}"
        assert row["industry_type"] in INDUSTRY_ENUM, f"Invalid industry_type: {row['industry_type']}"
        assert row["impact_scope"] in IMPACT_SCOPE_ENUM, f"Invalid impact_scope: {row['impact_scope']}"


def main() -> None:
    raw_rows = read_csv(RAW_OUTPUT_PATH)
    structured_rows = read_csv(STRUCTURED_OUTPUT_PATH)
    check_non_empty(raw_rows, structured_rows)
    check_positive_case(structured_rows)
    check_noise_case(raw_rows)
    check_dedup_case(raw_rows)
    check_required_fields(structured_rows)
    check_decision_threshold_fields(raw_rows)
    check_enum_values(structured_rows)

    print("Validation passed.")
    print(f"raw rows: {len(raw_rows)}")
    print(f"structured rows: {len(structured_rows)}")


if __name__ == "__main__":
    main()
