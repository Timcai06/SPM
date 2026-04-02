#!/usr/bin/env python3
"""Generate Task 1 quality sampling file and quality report."""

from __future__ import annotations

import argparse
import csv
import random
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
RAW_PATH = ROOT / "output" / "raw_event_candidates.csv"
STRUCTURED_PATH = ROOT / "output" / "structured_events.csv"
SAMPLE_PATH = ROOT / "output" / "quality_sample.csv"
REPORT_PATH = ROOT / "output" / "task1_quality_report.md"

STRUCTURED_REQUIRED_FIELDS = [
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
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_sample(raw_rows: list[dict[str, str]], sample_size: int, seed: int) -> list[dict[str, str]]:
    n = min(sample_size, len(raw_rows))
    rnd = random.Random(seed)
    picked = rnd.sample(raw_rows, n) if n else []
    sample_rows = []
    for row in picked:
        sample_rows.append(
            {
                "title": row.get("title", ""),
                "source": row.get("source", ""),
                "url": row.get("url", ""),
                "is_event_pred": row.get("is_event", ""),
                "event_score": row.get("event_score", ""),
                "event_threshold": row.get("event_threshold", ""),
                "evidence": row.get("evidence", ""),
                "manual_is_event": "",
                "manual_subject_type": "",
                "manual_comment": "",
            }
        )
    return sample_rows


def calc_completeness(structured_rows: list[dict[str, str]]) -> dict[str, float]:
    if not structured_rows:
        return {k: 0.0 for k in STRUCTURED_REQUIRED_FIELDS}
    total = len(structured_rows)
    result = {}
    for field in STRUCTURED_REQUIRED_FIELDS:
        non_empty = sum(1 for row in structured_rows if row.get(field, "").strip())
        result[field] = non_empty / total
    return result


def calc_label_stability(structured_rows: list[dict[str, str]]) -> float:
    by_ref = defaultdict(set)
    for row in structured_rows:
        key = row.get("raw_text_ref", "")
        label_key = "|".join(
            [
                row.get("event_subject_type", ""),
                row.get("duration_type", ""),
                row.get("predictability_type", ""),
                row.get("industry_type", ""),
            ]
        )
        by_ref[key].add(label_key)
    if not by_ref:
        return 0.0
    stable = sum(1 for labels in by_ref.values() if len(labels) == 1)
    return stable / len(by_ref)


def calc_manual_accuracy(sample_rows: list[dict[str, str]]) -> tuple[int, int, float]:
    reviewed = [r for r in sample_rows if r.get("manual_is_event", "").strip().lower() in {"true", "false"}]
    if not reviewed:
        return 0, 0, 0.0
    correct = 0
    for row in reviewed:
        if row["manual_is_event"].strip().lower() == row["is_event_pred"].strip().lower():
            correct += 1
    total = len(reviewed)
    return correct, total, (correct / total if total else 0.0)


def write_report(
    path: Path,
    raw_rows: list[dict[str, str]],
    structured_rows: list[dict[str, str]],
    sample_rows: list[dict[str, str]],
) -> None:
    completeness = calc_completeness(structured_rows)
    label_stability = calc_label_stability(structured_rows)
    correct, reviewed_total, accuracy = calc_manual_accuracy(sample_rows)
    avg_heat = sum(int(r.get("heat_score", "0") or 0) for r in structured_rows) / len(structured_rows) if structured_rows else 0.0
    avg_intensity = sum(int(r.get("intensity_score", "0") or 0) for r in structured_rows) / len(structured_rows) if structured_rows else 0.0

    lines = [
        "# 任务1质量评估报告",
        "",
        "## 一、样本规模",
        f"- raw_event_candidates 条数：{len(raw_rows)}",
        f"- structured_events 条数：{len(structured_rows)}",
        f"- 人工抽样条数：{len(sample_rows)}",
        "",
        "## 二、识别准确率（人工复核）",
    ]
    if reviewed_total == 0:
        lines.extend(
            [
                "- 当前尚未填写人工复核列 `manual_is_event`，暂无法计算准确率。",
                "- 请在 `output/quality_sample.csv` 完成 20-50 条人工标注后重跑本脚本。",
            ]
        )
    else:
        lines.extend(
            [
                f"- 人工已复核：{reviewed_total}",
                f"- 判定正确：{correct}",
                f"- 识别准确率：{accuracy:.2%}",
            ]
        )
    lines.extend(
        [
            "",
            "## 三、标签稳定性",
            f"- 同一 `raw_text_ref` 的四维标签一致率：{label_stability:.2%}",
            "",
            "## 四、字段完整率（structured_events）",
        ]
    )
    for field in STRUCTURED_REQUIRED_FIELDS:
        lines.append(f"- `{field}` 完整率：{completeness[field]:.2%}")
    lines.extend(
        [
            "",
            "## 五、特征分布概览",
            f"- 平均 `heat_score`：{avg_heat:.2f}",
            f"- 平均 `intensity_score`：{avg_intensity:.2f}",
            "",
            "## 六、结论",
            "- 本报告用于任务1质量闭环，重点关注识别准确率、标签稳定性、字段完整率。",
            "- 建议每次规则版本升级后重跑本报告并对比历史结果。",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate quality sample and Task 1 quality report.")
    parser.add_argument("--sample-size", type=int, default=30, help="Manual review sample size (recommended 20-50).")
    parser.add_argument("--seed", type=int, default=42, help="Sampling random seed.")
    parser.add_argument("--sample-path", default=str(SAMPLE_PATH), help="Output CSV path for manual review sample.")
    parser.add_argument("--report-path", default=str(REPORT_PATH), help="Output markdown report path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw_rows = read_csv(RAW_PATH)
    structured_rows = read_csv(STRUCTURED_PATH)
    sample_path = Path(args.sample_path).resolve()
    report_path = Path(args.report_path).resolve()

    sample_rows = build_sample(raw_rows, args.sample_size, args.seed)
    if sample_path.exists():
        # Keep reviewer edits if file already exists.
        existing_rows = read_csv(sample_path)
        if existing_rows and {"manual_is_event", "manual_subject_type", "manual_comment"}.issubset(existing_rows[0].keys()):
            sample_rows = existing_rows
    write_csv(
        sample_path,
        sample_rows,
        [
            "title",
            "source",
            "url",
            "is_event_pred",
            "event_score",
            "event_threshold",
            "evidence",
            "manual_is_event",
            "manual_subject_type",
            "manual_comment",
        ],
    )
    write_report(report_path, raw_rows, structured_rows, sample_rows)
    print(f"Wrote quality sample to {sample_path}")
    print(f"Wrote quality report to {report_path}")


if __name__ == "__main__":
    main()
