#!/usr/bin/env python3
"""Pure event-study calculations for feature-return analysis."""

from __future__ import annotations

import math
import statistics
from datetime import datetime
from typing import Dict, List, Optional


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


def fit_market_model(est_points: List[tuple[float, float]]) -> Optional[tuple[float, float]]:
    if len(est_points) < 30:
        return None
    market = [m for _, m in est_points]
    stock = [s for s, _ in est_points]
    mean_m = statistics.mean(market)
    mean_s = statistics.mean(stock)
    var_m = sum((m - mean_m) ** 2 for m in market)
    if var_m == 0:
        return None
    cov_sm = sum((s - mean_s) * (m - mean_m) for s, m in est_points)
    beta = cov_sm / var_m
    alpha = mean_s - beta * mean_m
    return alpha, beta


def parse_windows(raw: str) -> List[int]:
    values = []
    for part in raw.split(","):
        p = part.strip()
        if not p:
            continue
        values.append(int(p))
    return sorted(set(values))


def bucket3(value: float) -> str:
    if value <= 33:
        return "low"
    if value <= 66:
        return "mid"
    return "high"


def date_distance_days(a: str, b: str) -> Optional[int]:
    try:
        da = datetime.strptime(a, "%Y-%m-%d").date()
        db = datetime.strptime(b, "%Y-%m-%d").date()
    except Exception:
        return None
    return abs((da - db).days)


def resolve_event_trade_index(common_dates: List[str], event_date: str, max_gap_days: int = 7) -> tuple[Optional[int], str]:
    if not common_dates:
        return None, "no_common_trade_dates"
    for idx, trade_date in enumerate(common_dates):
        if trade_date >= event_date:
            gap = date_distance_days(trade_date, event_date)
            if gap is None or gap <= max_gap_days:
                return idx, "aligned_next_trade_date" if trade_date != event_date else "aligned_exact_trade_date"
            break

    prev_idx = None
    for idx in range(len(common_dates) - 1, -1, -1):
        if common_dates[idx] <= event_date:
            prev_idx = idx
            break
    if prev_idx is None:
        return None, "event_outside_trade_dates"
    gap = date_distance_days(common_dates[prev_idx], event_date)
    if gap is None or gap > max_gap_days:
        return None, "event_outside_trade_dates"
    return prev_idx, "aligned_prev_trade_date"


def build_estimation_points(
    common_dates: List[str],
    stock_returns: Dict[str, float],
    benchmark_returns: Dict[str, float],
    event_idx: int,
    estimation_start_offset: int = 120,
    estimation_end_offset: int = 20,
) -> Optional[List[tuple[float, float]]]:
    if event_idx - estimation_start_offset < 0:
        return None
    est_start = event_idx - estimation_start_offset
    est_end = event_idx - estimation_end_offset
    est_points: List[tuple[float, float]] = []
    for idx in range(est_start, est_end + 1):
        day = common_dates[idx]
        est_points.append((stock_returns[day], benchmark_returns[day]))
    return est_points


def compute_car_metrics(
    *,
    common_dates: List[str],
    stock_returns: Dict[str, float],
    benchmark_returns: Dict[str, float],
    event_idx: int,
    alpha: float,
    beta: float,
    event_windows: List[int],
) -> tuple[Dict[str, str], bool, bool]:
    metrics: Dict[str, str] = {}
    valid_any = False
    has_max_window = True
    max_window = event_windows[-1] if event_windows else 0
    for w in event_windows:
        if event_idx + w >= len(common_dates):
            metrics[f"car_w{w}"] = ""
            if w == max_window:
                has_max_window = False
            continue
        ar_values = []
        for idx in range(event_idx, event_idx + w + 1):
            day = common_dates[idx]
            ri = stock_returns[day]
            rm = benchmark_returns[day]
            ar_values.append(ri - (alpha + beta * rm))
        car = sum(ar_values)
        metrics[f"car_w{w}"] = f"{car:.6f}"
        valid_any = True
    return metrics, valid_any, has_max_window
