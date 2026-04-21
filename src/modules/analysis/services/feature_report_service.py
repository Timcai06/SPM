#!/usr/bin/env python3
"""Report rendering helpers for feature-return analysis."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional


def summarize_metric(metric: str, dataset_rows: List[dict[str, str]], mean_and_t: Callable[[List[float]], tuple[float, Optional[float]]]) -> str:
    vals = [float(r[metric]) for r in dataset_rows if r.get(metric)]
    mean_v, t_v = mean_and_t(vals)
    return f"- {metric}: 均值={mean_v:.4%}, t={'N/A' if t_v is None else f'{t_v:.3f}'}, 样本={len(vals)}"


def build_feature_report(
    *,
    run_id: str,
    analysis_mode: str,
    benchmark_key: str,
    benchmark_source: str,
    token_source: str,
    link_source: str,
    event_windows: List[int],
    time_budget_sec: int,
    max_rows: int,
    rows: List[dict[str, str]],
    processed_rows: int,
    dataset_rows: List[dict[str, str]],
    reason_counts: dict[str, int],
    dataset_path: Path,
    mean_and_t: Callable[[List[float]], tuple[float, Optional[float]]],
) -> str:
    report_lines = [
        "# 任务1事件研究法（异常收益）报告",
        "",
        f"- run_id：{run_id}",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 分析模式：{analysis_mode}",
        f"- 事件-公司有效样本：{len(dataset_rows)}",
        f"- 分析输入总行数：{len(rows)}",
        f"- 实际扫描行数：{processed_rows}",
        f"- 链接来源：{link_source}",
        f"- 基准：{benchmark_key}（{benchmark_source}）",
        f"- token来源：{token_source}",
        f"- 事件窗：{','.join(str(x) for x in event_windows)}",
        f"- 时间预算(秒)：{time_budget_sec}",
        f"- 最大输入行数：{max_rows}",
        "",
        "## 一、总体CAR统计",
    ]
    if dataset_rows:
        for w in event_windows:
            report_lines.append(summarize_metric(f"car_w{w}", dataset_rows, mean_and_t))
    else:
        report_lines.append("- 暂无可计算样本。")

    report_lines.extend(["", "## 二、分组CAR对比"])
    group_keys = ["impact_scope", "heat_bucket", "intensity_bucket"]
    for key in group_keys:
        report_lines.append(f"- 分组字段：{key}")
        groups: defaultdict[str, List[float]] = defaultdict(list)
        metric = f"car_w{event_windows[-1]}"
        for row in dataset_rows:
            if row.get(metric):
                groups[row.get(key, "unknown")].append(float(row[metric]))
        if not groups:
            report_lines.append("  - 无可用样本")
            continue
        for group_name, vals in sorted(groups.items(), key=lambda item: len(item[1]), reverse=True):
            mean_v, t_v = mean_and_t(vals)
            report_lines.append(
                f"  - {group_name}: 均值={mean_v:.4%}, t={'N/A' if t_v is None else f'{t_v:.3f}'}, 样本={len(vals)}"
            )

    report_lines.extend(["", "## 三、不可计算样本原因"])
    if not reason_counts:
        report_lines.append("- 无")
    else:
        for reason, count in sorted(reason_counts.items(), key=lambda item: item[1], reverse=True):
            report_lines.append(f"- {reason}: {count}")

    report_lines.extend(
        [
            "",
            "## 四、说明",
            "- 估计窗固定为[-120,-20]，事件窗为[t0,t0+w]。",
            "- 若Tushare不可用，默认回退Sina行情接口（可用环境变量 USE_EASTMONEY=1 启用东方财富回退），并在报告中标记。",
            f"- 数据明细见：`{dataset_path}`",
        ]
    )
    return "\n".join(report_lines)
