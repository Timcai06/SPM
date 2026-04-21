#!/usr/bin/env python3
"""Basic validation checks for the task1 MVP outputs."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from modules.events.domain.classification_rules import DURATION_ENUM, EVENT_SUBJECT_ENUM, IMPACT_SCOPE_ENUM, INDUSTRY_ENUM, PREDICTABILITY_ENUM, RULE_VERSION


ROOT = Path(__file__).resolve().parents[3]
RAW_OUTPUT_PATH = ROOT / "output" / "raw_event_candidates.csv"
STRUCTURED_OUTPUT_PATH = ROOT / "output" / "structured_events.csv"


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def check_non_empty(raw_rows, structured_rows) -> None:
    assert raw_rows, "raw_event_candidates.csv must not be empty"
    assert structured_rows, "structured_events.csv must not be empty"


def check_event_balance(raw_rows, structured_rows) -> None:
    event_rows = [r for r in raw_rows if r["is_event"] == "true"]
    non_event_rows = [r for r in raw_rows if r["is_event"] == "false"]
    assert event_rows, "No positive events found in raw_event_candidates.csv"
    assert non_event_rows, "No negative samples found in raw_event_candidates.csv"
    assert len(structured_rows) <= len(event_rows), "structured_events rows should not exceed positive event candidates"


def check_dedup_consistency(raw_rows) -> None:
    grouped = {}
    for row in raw_rows:
        key = row["dedup_key"]
        grouped.setdefault(key, 0)
        grouped[key] += 1
    for row in raw_rows:
        key = row["dedup_key"]
        expected = grouped.get(key, 0)
        actual = int(row.get("duplicate_group_size", "0") or 0)
        assert actual == expected, f"duplicate_group_size mismatch for dedup_key={key}: {actual} != {expected}"


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


def run_validation_pipeline(raw_rows: List[Dict[str, str]] = None, structured_rows: List[Dict[str, str]] = None) -> bool:
    """Orchestrate validation from memory or CSV files."""
    if raw_rows is None:
        raw_rows = read_csv(RAW_OUTPUT_PATH)
    if structured_rows is None:
        structured_rows = read_csv(STRUCTURED_OUTPUT_PATH)
        
    try:
        check_non_empty(raw_rows, structured_rows)
        check_event_balance(raw_rows, structured_rows)
        check_dedup_consistency(raw_rows)
        check_required_fields(structured_rows)
        check_decision_threshold_fields(raw_rows)
        check_enum_values(structured_rows)
        print("Validation passed.")
        print(f"raw rows: {len(raw_rows)}")
        print(f"structured rows: {len(structured_rows)}")
        return True
    except Exception as exc:
        print(f"Validation failed: {exc}")
        return False


def main(_argv: list[str] | None = None) -> None:
    run_validation_pipeline()


if __name__ == "__main__":
    main()
