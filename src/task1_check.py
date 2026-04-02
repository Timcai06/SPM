#!/usr/bin/env python3
"""Basic validation checks for the task1 MVP outputs."""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
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


def main() -> None:
    raw_rows = read_csv(RAW_OUTPUT_PATH)
    structured_rows = read_csv(STRUCTURED_OUTPUT_PATH)
    check_non_empty(raw_rows, structured_rows)
    check_positive_case(structured_rows)
    check_noise_case(raw_rows)
    check_dedup_case(raw_rows)
    check_required_fields(structured_rows)

    print("Validation passed.")
    print(f"raw rows: {len(raw_rows)}")
    print(f"structured rows: {len(structured_rows)}")


if __name__ == "__main__":
    main()
