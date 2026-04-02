#!/usr/bin/env python3
"""Task 1 preliminary feature-return association analysis.

This script links structured events to companies and computes forward stock
returns (1/3/5 trading days) as a first-pass impact analysis.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REPORT = ROOT / "output" / "task1_feature_return_report.md"
DEFAULT_DATASET = ROOT / "output" / "task1_event_return_dataset.csv"


def ts_to_sina_symbol(ts_code: str) -> Optional[str]:
    ts_code = ts_code.strip().upper()
    if not ts_code or "." not in ts_code:
        return None
    code, exch = ts_code.split(".", 1)
    if exch == "SZ":
        return f"sz{code}"
    if exch == "SH":
        return f"sh{code}"
    return None


def fetch_daily_prices(ts_code: str, max_rows: int = 300) -> List[Dict[str, str]]:
    symbol = ts_to_sina_symbol(ts_code)
    if not symbol:
        return []
    url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
    params = {"symbol": symbol, "scale": "240", "ma": "no", "datalen": str(max_rows)}
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    text = resp.text.strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    return [row for row in data if row.get("day") and row.get("close")]


def find_event_close_and_forward(prices: List[Dict[str, str]], event_date: str) -> tuple[Optional[float], Dict[int, Optional[float]]]:
    if not prices:
        return None, {1: None, 3: None, 5: None}
    rows = sorted(prices, key=lambda x: x["day"])
    event_idx = None
    for i, row in enumerate(rows):
        if row["day"] >= event_date:
            event_idx = i
            break
    if event_idx is None:
        return None, {1: None, 3: None, 5: None}
    try:
        base = float(rows[event_idx]["close"])
    except Exception:
        return None, {1: None, 3: None, 5: None}
    ret = {}
    for k in (1, 3, 5):
        if event_idx + k >= len(rows):
            ret[k] = None
            continue
        try:
            future = float(rows[event_idx + k]["close"])
            ret[k] = (future - base) / base
        except Exception:
            ret[k] = None
    return base, ret


def run_psql_csv(db: str, sql: str) -> List[Dict[str, str]]:
    cmd = [
        "psql",
        "-d",
        db,
        "-v",
        "ON_ERROR_STOP=1",
        "-A",
        "-F",
        ",",
        "-c",
        f"\\copy ({sql}) TO STDOUT WITH CSV HEADER",
    ]
    proc = subprocess.run(cmd, check=True, cwd=str(ROOT), capture_output=True, text=True)
    return list(csv.DictReader(proc.stdout.splitlines()))


def mean_and_t(values: List[float]) -> tuple[float, Optional[float]]:
    if not values:
        return 0.0, None
    mean_val = statistics.mean(values)
    if len(values) < 2:
        return mean_val, None
    std_val = statistics.stdev(values)
    if std_val == 0:
        return mean_val, None
    t_stat = mean_val / (std_val / math.sqrt(len(values)))
    return mean_val, t_stat


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Task1 feature-return association analysis.")
    parser.add_argument("--db", default="stock_event_mining", help="PostgreSQL database name.")
    parser.add_argument("--min-link-score", type=float, default=0.35, help="Minimum event-company link score.")
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT), help="Markdown report output path.")
    parser.add_argument("--dataset-path", default=str(DEFAULT_DATASET), help="CSV dataset output path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sql_links = f"""
    SELECT
        e.id AS structured_event_id,
        e.event_id,
        e.event_date::text AS event_date,
        e.event_subject_type,
        e.duration_type,
        e.predictability_type,
        e.industry_type,
        e.heat_score,
        e.intensity_score,
        e.impact_scope,
        c.ts_code,
        l.final_link_score
    FROM structured_events e
    JOIN event_company_links l ON l.structured_event_id = e.id
    JOIN companies c ON c.id = l.company_id
    WHERE l.final_link_score >= {args.min_link_score}
    ORDER BY e.event_date DESC, l.final_link_score DESC
    """
    rows = run_psql_csv(args.db, sql_links)
    data_source = "event_company_links"
    if not rows:
        # Fallback: use symbol_or_subject from raw documents for Task1-only stage.
        sql_fallback = """
        SELECT
            e.id AS structured_event_id,
            e.event_id,
            e.event_date::text AS event_date,
            e.event_subject_type,
            e.duration_type,
            e.predictability_type,
            e.industry_type,
            e.heat_score,
            e.intensity_score,
            e.impact_scope,
            CASE
                WHEN d.symbol_or_subject ~ '^[0-9]{6}$' AND d.source LIKE '上交所%' THEN d.symbol_or_subject || '.SH'
                WHEN d.symbol_or_subject ~ '^[0-9]{6}$' THEN d.symbol_or_subject || '.SZ'
                ELSE NULL
            END AS ts_code,
            1.0::text AS final_link_score
        FROM structured_events e
        JOIN event_candidates c ON c.id = e.candidate_id
        JOIN raw_documents d ON d.id = c.raw_document_id
        WHERE d.symbol_or_subject ~ '^[0-9]{6}$'
        ORDER BY e.event_date DESC
        """
        rows = run_psql_csv(args.db, sql_fallback)
        data_source = "raw_documents_symbol_or_subject"

    dataset_rows: List[Dict[str, str]] = []

    for row in rows:
        if not row.get("ts_code"):
            continue
        prices = fetch_daily_prices(row["ts_code"])
        _, fwd = find_event_close_and_forward(prices, row["event_date"])
        dataset_rows.append(
            {
                **row,
                "fwd_ret_1d": "" if fwd[1] is None else f"{fwd[1]:.6f}",
                "fwd_ret_3d": "" if fwd[3] is None else f"{fwd[3]:.6f}",
                "fwd_ret_5d": "" if fwd[5] is None else f"{fwd[5]:.6f}",
            }
        )

    dataset_path = Path(args.dataset_path).resolve()
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    with dataset_path.open("w", encoding="utf-8", newline="") as f:
        if dataset_rows:
            writer = csv.DictWriter(f, fieldnames=list(dataset_rows[0].keys()))
            writer.writeheader()
            writer.writerows(dataset_rows)
        else:
            writer = csv.writer(f)
            writer.writerow(["message"])
            writer.writerow(["no data"])

    valid_1d = [float(r["fwd_ret_1d"]) for r in dataset_rows if r.get("fwd_ret_1d")]
    valid_3d = [float(r["fwd_ret_3d"]) for r in dataset_rows if r.get("fwd_ret_3d")]
    valid_5d = [float(r["fwd_ret_5d"]) for r in dataset_rows if r.get("fwd_ret_5d")]
    mean1, t1 = mean_and_t(valid_1d)
    mean3, t3 = mean_and_t(valid_3d)
    mean5, t5 = mean_and_t(valid_5d)

    by_scope: Dict[str, List[float]] = {}
    for r in dataset_rows:
        if not r.get("fwd_ret_3d"):
            continue
        by_scope.setdefault(r["impact_scope"], []).append(float(r["fwd_ret_3d"]))

    report_lines = [
        "# 任务1特征-股价影响初步分析",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 事件-公司样本量：{len(dataset_rows)}",
        f"- 数据来源：{data_source}",
        f"- 最小关联分：{args.min_link_score}",
        "",
        "## 一、整体前瞻收益统计",
        f"- 1日收益均值：{mean1:.4%}，t统计量：{'N/A' if t1 is None else f'{t1:.3f}'}（样本={len(valid_1d)}）",
        f"- 3日收益均值：{mean3:.4%}，t统计量：{'N/A' if t3 is None else f'{t3:.3f}'}（样本={len(valid_3d)}）",
        f"- 5日收益均值：{mean5:.4%}，t统计量：{'N/A' if t5 is None else f'{t5:.3f}'}（样本={len(valid_5d)}）",
        "",
        "## 二、按影响范围分组（3日收益均值）",
    ]
    if not by_scope:
        report_lines.append("- 暂无可用样本。")
    else:
        for scope, vals in sorted(by_scope.items(), key=lambda kv: len(kv[1]), reverse=True):
            mean_scope, t_scope = mean_and_t(vals)
            report_lines.append(
                f"- {scope}: 均值={mean_scope:.4%}, t={'N/A' if t_scope is None else f'{t_scope:.3f}'}, 样本={len(vals)}"
            )
    report_lines.extend(
        [
            "",
            "## 三、说明",
            "- 本分析用于任务1阶段的“特征与股价影响关联性”初步验证，非最终预测模型结果。",
            "- 若需要更严格显著性分析，可在统计同学阶段引入行业/市场基准收益与异常收益模型。",
            "",
            f"数据明细见：`{dataset_path}`",
        ]
    )

    report_path = Path(args.report_path).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"Wrote feature-return dataset to {dataset_path}")
    print(f"Wrote feature-return report to {report_path}")


if __name__ == "__main__":
    main()
