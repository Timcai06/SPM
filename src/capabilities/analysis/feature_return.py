#!/usr/bin/env python3
"""Task 1 event-study analysis with benchmark abnormal returns."""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.analysis.tushare_adapter import load_tushare
from modules.analysis.adapters.db_repository import (
    fetch_company_stats_returns,
    run_query_rows,
)
from modules.analysis.services.feature_cache_service import load_market_cache, resolve_tushare_token, save_market_cache
from modules.analysis.services.event_study_service import (
    bucket3,
    build_estimation_points,
    compute_car_metrics,
    fit_market_model,
    mean_and_t,
    parse_windows,
    resolve_event_trade_index,
)
from modules.analysis.services.feature_report_service import build_feature_report
from modules.analysis.services.returns_resolver_service import (
    resolve_benchmark_returns,
    resolve_stock_returns,
)


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REPORT = ROOT / "output" / "task1_feature_return_report.md"
DEFAULT_DATASET = ROOT / "output" / "task1_event_return_dataset.csv"
DEFAULT_CACHE = ROOT / "output" / "meta" / "feature_market_cache.json"
INDEX_CODE_MAP = {"hs300": "000300.SH"}
INDEX_SINA_SYMBOL_MAP = {"hs300": "sh000300"}
INDEX_EASTMONEY_SECID_MAP = {"hs300": "1.000300"}
ENABLE_EASTMONEY_FALLBACK = os.getenv("USE_EASTMONEY", "0") == "1"

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
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
    parser.add_argument("--market-max-rows", type=int, default=1200, help="Max rows to fetch from fallback market APIs.")
    parser.add_argument("--progress-every", type=int, default=10, help="Print progress every N processed rows.")
    parser.add_argument("--cache-path", default=str(DEFAULT_CACHE), help="Local JSON cache path for market returns.")
    parser.add_argument("--disable-cache", action="store_true", help="Disable persistent market returns cache.")
    parser.add_argument("--event-align-max-gap-days", type=int, default=7, help="Max calendar-day gap when snapping event date to nearest trade date.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
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
    rows = run_query_rows(args.db, sql_links)
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
                WHEN d.symbol_or_subject ~ '^[0-9]{6}$' AND d.source LIKE '北交所%' THEN d.symbol_or_subject || '.BJ'
                WHEN d.symbol_or_subject ~ '^[0-9]{6}$' THEN d.symbol_or_subject || '.SZ'
                ELSE NULL
            END AS ts_code,
            1.0::text AS final_link_score
        FROM structured_events e
        JOIN int_event_candidates c ON c.id = e.candidate_id
        JOIN raw_documents d ON d.id = c.raw_document_id
        WHERE d.symbol_or_subject ~ '^[0-9]{6}$'
        ORDER BY e.event_date DESC
        """
        rows = run_query_rows(args.db, sql_fallback)
        link_source = "raw_documents_symbol_or_subject"
    token, token_source = resolve_tushare_token(
        disable_tushare=args.disable_tushare,
        tushare_token=args.tushare_token,
        tushare_token_file=args.tushare_token_file,
        root=ROOT,
    )
    ts_module = load_tushare() if token else None
    use_tushare = ts_module is not None
    print(
        f"[feature] init db={args.db}, analysis_mode={args.analysis_mode}, "
        f"benchmark={benchmark_key}, token_source={token_source}, use_tushare={use_tushare}"
    )

    reason_counts: defaultdict[str, int] = defaultdict(int)
    cache_path = Path(args.cache_path).resolve()
    cache_payload = {"series": {}} if args.disable_cache else load_market_cache(cache_path)
    benchmark_returns, benchmark_source, use_tushare = resolve_benchmark_returns(
        benchmark_key=benchmark_key,
        index_code_map=INDEX_CODE_MAP,
        index_sina_symbol_map=INDEX_SINA_SYMBOL_MAP,
        index_eastmoney_secid_map=INDEX_EASTMONEY_SECID_MAP,
        cache_payload=cache_payload,
        disable_cache=args.disable_cache,
        use_tushare=use_tushare,
        ts_module=ts_module,
        token=token,
        api_timeout_sec=args.api_timeout_sec,
        market_max_rows=args.market_max_rows,
        enable_eastmoney_fallback=ENABLE_EASTMONEY_FALLBACK,
        reason_counts=reason_counts,
    )
    if benchmark_source.startswith("tushare_failed:") and not use_tushare:
        print("[feature] tushare token invalid, fallback to sina and disable tushare stock fetch.")
    elif benchmark_source.startswith("eastmoney_failed:"):
        print(f"[feature] eastmoney index fallback failed: {benchmark_source.split(':', 1)[1]}")
    elif benchmark_source.startswith("sina_failed:"):
        print(f"[feature] sina index fallback failed: {benchmark_source.split(':', 1)[1]}")

    stock_cache: Dict[str, Dict[str, float]] = {}
    stock_source_map: Dict[str, str] = {}
    dataset_rows: List[Dict[str, str]] = []
    started_at = time.time()

    total_rows = len(rows)
    processed_rows = 0
    print(
        f"[feature] start rows={total_rows}, use_tushare={use_tushare}, "
        f"benchmark_source={benchmark_source}, token_source={token_source}"
    )
    for idx_row, row in enumerate(rows, start=1):
        processed_rows = idx_row
        if args.max_rows > 0 and len(dataset_rows) >= args.max_rows:
            break
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
            returns, source_name = resolve_stock_returns(
                ts_code=ts_code,
                db=args.db,
                cache_payload=cache_payload,
                disable_cache=args.disable_cache,
                use_tushare=use_tushare,
                ts_module=ts_module,
                token=token,
                api_timeout_sec=args.api_timeout_sec,
                market_max_rows=args.market_max_rows,
                enable_eastmoney_fallback=ENABLE_EASTMONEY_FALLBACK,
                reason_counts=reason_counts,
                fetch_company_stats_returns_fn=fetch_company_stats_returns,
            )
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
        event_idx, align_reason = resolve_event_trade_index(common_dates, event_date, max_gap_days=args.event_align_max_gap_days)
        if event_idx is None:
            reason_counts[align_reason] += 1
            continue
        if align_reason != "aligned_exact_trade_date":
            reason_counts[align_reason] += 1
        if event_idx - 120 < 0:
            reason_counts["insufficient_estimation_window"] += 1
            continue

        est_points = build_estimation_points(common_dates, stock_returns, benchmark_returns, event_idx)
        if est_points is None:
            reason_counts["insufficient_estimation_window"] += 1
            continue
        fit = fit_market_model(est_points)
        if fit is None:
            reason_counts["invalid_market_model_fit"] += 1
            continue
        alpha, beta = fit

        metrics, valid_any, has_max_window = compute_car_metrics(
            common_dates=common_dates,
            stock_returns=stock_returns,
            benchmark_returns=benchmark_returns,
            event_idx=event_idx,
            alpha=alpha,
            beta=beta,
            event_windows=event_windows,
        )
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
                "event_trade_date": common_dates[event_idx],
                "event_date_alignment": align_reason,
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

    report_path = Path(args.report_path).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        build_feature_report(
            run_id=run_id,
            analysis_mode=args.analysis_mode,
            benchmark_key=benchmark_key,
            benchmark_source=benchmark_source,
            token_source=token_source,
            link_source=link_source,
            event_windows=event_windows,
            time_budget_sec=args.time_budget_sec,
            max_rows=args.max_rows,
            rows=rows,
            processed_rows=processed_rows,
            dataset_rows=dataset_rows,
            reason_counts=dict(reason_counts),
            dataset_path=dataset_path,
            mean_and_t=mean_and_t,
        ),
        encoding="utf-8",
    )
    if not args.disable_cache:
        save_market_cache(cache_path, cache_payload)
    print(f"Wrote event-study dataset to {dataset_path}")
    print(f"Wrote event-study report to {report_path}")


if __name__ == "__main__":
    main()
