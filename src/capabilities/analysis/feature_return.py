#!/usr/bin/env python3
"""Task 1 event-study analysis with benchmark abnormal returns."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.analysis.tushare_adapter import fetch_index_returns, fetch_stock_returns, load_tushare


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REPORT = ROOT / "output" / "task1_feature_return_report.md"
DEFAULT_DATASET = ROOT / "output" / "task1_event_return_dataset.csv"
DEFAULT_CACHE = ROOT / "output" / "meta" / "feature_market_cache.json"
INDEX_CODE_MAP = {"hs300": "000300.SH"}
INDEX_SINA_SYMBOL_MAP = {"hs300": "sh000300"}
INDEX_EASTMONEY_SECID_MAP = {"hs300": "1.000300"}
ENABLE_EASTMONEY_FALLBACK = os.getenv("USE_EASTMONEY", "0") == "1"


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


def ts_to_eastmoney_secid(ts_code: str) -> Optional[str]:
    ts_code = ts_code.strip().upper()
    if not ts_code or "." not in ts_code:
        return None
    code, exch = ts_code.split(".", 1)
    if exch == "SZ":
        return f"0.{code}"
    if exch == "SH":
        return f"1.{code}"
    if exch == "BJ":
        return f"0.{code}"
    return None


def fetch_sina_kline(symbol: str, max_rows: int = 800, timeout_seconds: float = 20.0) -> List[Dict[str, str]]:
    url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
    params = {"symbol": symbol, "scale": "240", "ma": "no", "datalen": str(max_rows)}
    resp = requests.get(url, params=params, timeout=timeout_seconds)
    resp.raise_for_status()
    text = resp.text.strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    return [row for row in data if row.get("day") and row.get("close")]


def fetch_eastmoney_kline(
    secid: str, max_rows: int = 800, timeout_seconds: float = 20.0
) -> List[Dict[str, str]]:
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5",
        "fields2": "f51,f52,f53,f54,f55,f56,f57",
        "klt": "101",
        "fqt": "1",
        "beg": "0",
        "end": "0",
        "lmt": str(max_rows),
    }
    resp = requests.get(url, params=params, timeout=timeout_seconds)
    resp.raise_for_status()
    payload = resp.json()
    data = payload.get("data") or {}
    klines = data.get("klines") or []
    rows: List[Dict[str, str]] = []
    for line in klines:
        parts = str(line).split(",")
        if len(parts) < 3:
            continue
        day = parts[0].strip()
        close = parts[2].strip()
        if day and close:
            rows.append({"day": day, "close": close})
    return rows


def close_series_to_returns(kline: List[Dict[str, str]]) -> Dict[str, float]:
    rows = sorted(kline, key=lambda x: x["day"])
    result: Dict[str, float] = {}
    prev_close: Optional[float] = None
    for row in rows:
        day = row["day"]
        try:
            close = float(row["close"])
        except Exception:
            prev_close = None
            continue
        if prev_close and prev_close != 0:
            result[day] = (close - prev_close) / prev_close
        prev_close = close
    return result


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Task1 event-study analysis.")
    parser.add_argument("--db", default="stock_event_mining", help="PostgreSQL database name.")
    parser.add_argument("--min-link-score", type=float, default=0.35, help="Minimum event-company link score.")
    parser.add_argument("--analysis-mode", default="event-study", help="Analysis mode, currently only event-study.")
    parser.add_argument("--benchmark", default="hs300", help="Benchmark id, default hs300.")
    parser.add_argument("--event-windows", default="1,3,5", help="Event windows in days, comma-separated.")
    parser.add_argument("--tushare-token", default="", help="Explicit Tushare token. Prefer env/file in shared environments.")
    parser.add_argument("--tushare-token-file", default="", help="Path to local file containing Tushare token.")
    parser.add_argument("--disable-tushare", action="store_true", help="Disable Tushare and use fallback sources directly.")
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT), help="Markdown report output path.")
    parser.add_argument("--dataset-path", default=str(DEFAULT_DATASET), help="CSV dataset output path.")
    parser.add_argument("--run-id", default="", help="Run identifier for traceability.")
    parser.add_argument("--time-budget-sec", type=int, default=300, help="Stop analysis when runtime budget is reached.")
    parser.add_argument("--max-rows", type=int, default=300, help="Max event-company rows to analyze per run.")
    parser.add_argument("--api-timeout-sec", type=float, default=20.0, help="Per request timeout for Tushare/Sina fetch.")
    parser.add_argument("--progress-every", type=int, default=10, help="Print progress every N processed rows.")
    parser.add_argument("--cache-path", default=str(DEFAULT_CACHE), help="Local JSON cache path for market returns.")
    parser.add_argument("--disable-cache", action="store_true", help="Disable persistent market returns cache.")
    return parser.parse_args()


def resolve_tushare_token(args: argparse.Namespace) -> tuple[str, str]:
    if args.disable_tushare:
        return "", "disabled"
    if args.tushare_token.strip():
        return args.tushare_token.strip(), "cli_arg"
    if args.tushare_token_file.strip():
        token_path = Path(args.tushare_token_file).expanduser().resolve()
        if token_path.exists():
            content = token_path.read_text(encoding="utf-8").strip()
            if content:
                return content, f"file:{token_path.name}"
    default_paths = [
        ROOT / ".secrets" / "tushare_token.txt",
        Path.home() / ".config" / "stock_event_mining" / "tushare_token.txt",
    ]
    for token_path in default_paths:
        if token_path.exists():
            content = token_path.read_text(encoding="utf-8").strip()
            if content:
                return content, f"file:{token_path.name}"
    env_token = os.getenv("TUSHARE_TOKEN", "").strip()
    if env_token:
        return env_token, "env:TUSHARE_TOKEN"
    return "", "missing"


def load_market_cache(path: Path) -> dict:
    if not path.exists():
        return {"series": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"series": {}}
    if not isinstance(payload, dict):
        return {"series": {}}
    series = payload.get("series")
    if not isinstance(series, dict):
        payload["series"] = {}
    return payload


def save_market_cache(path: Path, cache_payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cache_payload["saved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    path.write_text(json.dumps(cache_payload, ensure_ascii=False), encoding="utf-8")


def get_cached_series(cache_payload: dict, key: str) -> tuple[Dict[str, float], str]:
    series = cache_payload.get("series", {}).get(key)
    if not isinstance(series, dict):
        return {}, "none"
    returns = series.get("returns")
    if not isinstance(returns, dict):
        return {}, "none"
    normalized: Dict[str, float] = {}
    for date_key, value in returns.items():
        try:
            normalized[str(date_key)] = float(value)
        except Exception:
            continue
    source = str(series.get("source") or "cache")
    return normalized, source


def put_cached_series(cache_payload: dict, key: str, returns: Dict[str, float], source: str) -> None:
    cache_payload.setdefault("series", {})
    cache_payload["series"][key] = {
        "source": source,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "returns": returns,
    }


def main() -> None:
    args = parse_args()
    if args.analysis_mode != "event-study":
        raise ValueError(f"Unsupported analysis mode: {args.analysis_mode}")
    event_windows = parse_windows(args.event_windows)
    run_id = args.run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    benchmark_key = args.benchmark.lower()
    if benchmark_key not in INDEX_CODE_MAP:
        raise ValueError(f"Unsupported benchmark: {args.benchmark}")

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
    link_source = "event_company_links"
    if not rows:
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
        link_source = "raw_documents_symbol_or_subject"
    if args.max_rows > 0:
        rows = rows[: args.max_rows]

    token, token_source = resolve_tushare_token(args)
    ts_module = load_tushare() if token else None
    use_tushare = ts_module is not None
    print(
        f"[feature] init db={args.db}, analysis_mode={args.analysis_mode}, "
        f"benchmark={benchmark_key}, token_source={token_source}, use_tushare={use_tushare}"
    )

    reason_counts: defaultdict[str, int] = defaultdict(int)
    cache_path = Path(args.cache_path).resolve()
    cache_payload = {"series": {}} if args.disable_cache else load_market_cache(cache_path)
    benchmark_returns: Dict[str, float] = {}
    benchmark_source = "none"
    benchmark_cache_key = f"index:{benchmark_key}"
    if not args.disable_cache:
        benchmark_returns, benchmark_source = get_cached_series(cache_payload, benchmark_cache_key)
        if benchmark_returns:
            benchmark_source = f"cache:{benchmark_source}"
    try:
        if use_tushare and not benchmark_returns:
            ret_obj = fetch_index_returns(
                ts_module,
                token,
                INDEX_CODE_MAP[benchmark_key],
                "20200101",
                datetime.now().strftime("%Y%m%d"),
                timeout_seconds=args.api_timeout_sec,
            )
            benchmark_returns = ret_obj.returns
            benchmark_source = ret_obj.source
            if benchmark_returns and not args.disable_cache:
                put_cached_series(cache_payload, benchmark_cache_key, benchmark_returns, benchmark_source)
    except Exception as exc:
        benchmark_returns = {}
        reason_counts["tushare_index_error"] += 1
        if "token不对" in str(exc):
            use_tushare = False
            print("[feature] tushare token invalid, fallback to sina and disable tushare stock fetch.")
        benchmark_source = f"tushare_failed:{exc.__class__.__name__}"
    if not benchmark_returns and ENABLE_EASTMONEY_FALLBACK and benchmark_key in INDEX_EASTMONEY_SECID_MAP:
        secid = INDEX_EASTMONEY_SECID_MAP[benchmark_key]
        try:
            benchmark_returns = close_series_to_returns(
                fetch_eastmoney_kline(secid, max_rows=800, timeout_seconds=args.api_timeout_sec)
            )
            benchmark_source = "eastmoney_index_fallback"
            if benchmark_returns and not args.disable_cache:
                put_cached_series(cache_payload, benchmark_cache_key, benchmark_returns, benchmark_source)
        except Exception as exc:
            benchmark_returns = {}
            reason_counts[f"eastmoney_index_error:{exc.__class__.__name__}"] += 1
            benchmark_source = f"eastmoney_failed:{exc.__class__.__name__}"
            print(f"[feature] eastmoney index fallback failed: {exc.__class__.__name__}")
    if not benchmark_returns and benchmark_key in INDEX_SINA_SYMBOL_MAP:
        symbol = INDEX_SINA_SYMBOL_MAP[benchmark_key]
        try:
            benchmark_returns = close_series_to_returns(
                fetch_sina_kline(symbol, max_rows=800, timeout_seconds=args.api_timeout_sec)
            )
            benchmark_source = "sina_index_fallback"
            if benchmark_returns and not args.disable_cache:
                put_cached_series(cache_payload, benchmark_cache_key, benchmark_returns, benchmark_source)
        except Exception as exc:
            benchmark_returns = {}
            reason_counts[f"sina_index_error:{exc.__class__.__name__}"] += 1
            benchmark_source = f"sina_failed:{exc.__class__.__name__}"
            print(f"[feature] sina index fallback failed: {exc.__class__.__name__}")

    stock_cache: Dict[str, Dict[str, float]] = {}
    stock_source_map: Dict[str, str] = {}
    dataset_rows: List[Dict[str, str]] = []
    started_at = time.time()

    total_rows = len(rows)
    print(
        f"[feature] start rows={total_rows}, use_tushare={use_tushare}, "
        f"benchmark_source={benchmark_source}, token_source={token_source}"
    )
    for idx_row, row in enumerate(rows, start=1):
        if args.time_budget_sec > 0 and (time.time() - started_at) >= args.time_budget_sec:
            reason_counts["time_budget_exceeded"] += 1
            print(f"[feature] stop by time budget at row={idx_row}/{total_rows}")
            break
        if args.progress_every > 0 and (idx_row == 1 or idx_row % args.progress_every == 0):
            elapsed = int(time.time() - started_at)
            print(
                f"[feature] progress {idx_row}/{total_rows}, generated={len(dataset_rows)}, "
                f"stocks_cached={len(stock_cache)}, elapsed={elapsed}s"
            )
        ts_code = (row.get("ts_code") or "").strip()
        if not ts_code:
            reason_counts["missing_ts_code"] += 1
            continue
        if ts_code not in stock_cache:
            stock_cache_key = f"stock:{ts_code}"
            returns: Dict[str, float] = {}
            source_name = "none"
            if not args.disable_cache:
                returns, source_name = get_cached_series(cache_payload, stock_cache_key)
                if returns:
                    source_name = f"cache:{source_name}"
            if use_tushare:
                if not returns:
                    try:
                        ret_obj = fetch_stock_returns(
                            ts_module,
                            token,
                            ts_code,
                            "20200101",
                            datetime.now().strftime("%Y%m%d"),
                            timeout_seconds=args.api_timeout_sec,
                        )
                        returns = ret_obj.returns
                        source_name = ret_obj.source
                        if returns and not args.disable_cache:
                            put_cached_series(cache_payload, stock_cache_key, returns, source_name)
                    except Exception as exc:
                        returns = {}
                        reason_counts[f"tushare_stock_error:{exc.__class__.__name__}"] += 1
            if not returns and ENABLE_EASTMONEY_FALLBACK:
                eastmoney_secid = ts_to_eastmoney_secid(ts_code)
                if eastmoney_secid:
                    try:
                        returns = close_series_to_returns(
                            fetch_eastmoney_kline(eastmoney_secid, max_rows=800, timeout_seconds=args.api_timeout_sec)
                        )
                        source_name = "eastmoney_stock_fallback"
                        if returns and not args.disable_cache:
                            put_cached_series(cache_payload, stock_cache_key, returns, source_name)
                    except Exception as exc:
                        returns = {}
                        source_name = "none"
                        reason_counts[f"eastmoney_stock_error:{exc.__class__.__name__}"] += 1
                if not returns:
                    sina_symbol = ts_to_sina_symbol(ts_code)
                    if sina_symbol:
                        try:
                            returns = close_series_to_returns(
                                fetch_sina_kline(sina_symbol, max_rows=800, timeout_seconds=args.api_timeout_sec)
                            )
                            source_name = "sina_stock_fallback"
                            if returns and not args.disable_cache:
                                put_cached_series(cache_payload, stock_cache_key, returns, source_name)
                        except Exception as exc:
                            returns = {}
                            source_name = "none"
                            reason_counts[f"sina_stock_error:{exc.__class__.__name__}"] += 1
            stock_cache[ts_code] = returns
            stock_source_map[ts_code] = source_name

        stock_returns = stock_cache[ts_code]
        if not benchmark_returns:
            reason_counts["benchmark_unavailable"] += 1
            continue
        common_dates = sorted(set(stock_returns.keys()) & set(benchmark_returns.keys()))
        if not common_dates:
            reason_counts["no_common_trade_dates"] += 1
            continue

        event_date = row["event_date"]
        event_idx = next((i for i, d in enumerate(common_dates) if d >= event_date), None)
        if event_idx is None:
            reason_counts["event_outside_trade_dates"] += 1
            continue
        if event_idx - 120 < 0:
            reason_counts["insufficient_estimation_window"] += 1
            continue

        est_start = event_idx - 120
        est_end = event_idx - 20
        est_points: List[tuple[float, float]] = []
        for idx in range(est_start, est_end + 1):
            day = common_dates[idx]
            est_points.append((stock_returns[day], benchmark_returns[day]))
        fit = fit_market_model(est_points)
        if fit is None:
            reason_counts["invalid_market_model_fit"] += 1
            continue
        alpha, beta = fit

        metrics: Dict[str, str] = {}
        valid_any = False
        for w in event_windows:
            if event_idx + w >= len(common_dates):
                metrics[f"car_w{w}"] = ""
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
        if not valid_any:
            reason_counts["insufficient_event_window"] += 1
            continue

        dataset_rows.append(
            {
                "run_id": run_id,
                **row,
                "analysis_mode": args.analysis_mode,
                "benchmark": benchmark_key,
                "benchmark_source": benchmark_source,
                "token_source": token_source,
                "stock_source": stock_source_map.get(ts_code, "none"),
                "estimation_window": "[-120,-20]",
                "event_windows": ",".join(str(x) for x in event_windows),
                "estimation_points": str(len(est_points)),
                "alpha": f"{alpha:.8f}",
                "beta": f"{beta:.8f}",
                "heat_bucket": bucket3(float(row.get("heat_score") or 0.0)),
                "intensity_bucket": bucket3(float(row.get("intensity_score") or 0.0)),
                **metrics,
            }
        )

    dataset_path = Path(args.dataset_path).resolve()
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    with dataset_path.open("w", encoding="utf-8", newline="") as f:
        if dataset_rows:
            writer = csv.DictWriter(f, fieldnames=list(dataset_rows[0].keys()))
            writer.writeheader()
            writer.writerows(dataset_rows)
            print(f"[feature] generated dataset rows={len(dataset_rows)}")
        else:
            writer = csv.DictWriter(
                f,
                fieldnames=["run_id", "message", "analysis_mode", "benchmark", "benchmark_source", "token_source", "link_source"],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "run_id": run_id,
                    "message": "no_data",
                    "analysis_mode": args.analysis_mode,
                    "benchmark": benchmark_key,
                    "benchmark_source": benchmark_source,
                    "token_source": token_source,
                    "link_source": link_source,
                }
            )
            print(f"[feature] no dataset rows. reason_counts={dict(reason_counts)}")

    def summarize_metric(metric: str) -> str:
        vals = [float(r[metric]) for r in dataset_rows if r.get(metric)]
        mean_v, t_v = mean_and_t(vals)
        return f"- {metric}: 均值={mean_v:.4%}, t={'N/A' if t_v is None else f'{t_v:.3f}'}, 样本={len(vals)}"

    report_lines = [
        "# 任务1事件研究法（异常收益）报告",
        "",
        f"- run_id：{run_id}",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 分析模式：{args.analysis_mode}",
        f"- 事件-公司有效样本：{len(dataset_rows)}",
        f"- 分析输入行数：{len(rows)}",
        f"- 链接来源：{link_source}",
        f"- 基准：{benchmark_key}（{benchmark_source}）",
        f"- token来源：{token_source}",
        f"- 事件窗：{','.join(str(x) for x in event_windows)}",
        f"- 时间预算(秒)：{args.time_budget_sec}",
        f"- 最大输入行数：{args.max_rows}",
        "",
        "## 一、总体CAR统计",
    ]
    if dataset_rows:
        for w in event_windows:
            report_lines.append(summarize_metric(f"car_w{w}"))
    else:
        report_lines.append("- 暂无可计算样本。")

    report_lines.extend(["", "## 二、分组CAR对比"])
    group_keys = ["impact_scope", "heat_bucket", "intensity_bucket"]
    for key in group_keys:
        report_lines.append(f"- 分组字段：{key}")
        groups: defaultdict[str, List[float]] = defaultdict(list)
        metric = f"car_w{event_windows[-1]}"
        for r in dataset_rows:
            if r.get(metric):
                groups[r.get(key, "unknown")].append(float(r[metric]))
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

    report_path = Path(args.report_path).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    if not args.disable_cache:
        save_market_cache(cache_path, cache_payload)
    print(f"Wrote event-study dataset to {dataset_path}")
    print(f"Wrote event-study report to {report_path}")


if __name__ == "__main__":
    main()
