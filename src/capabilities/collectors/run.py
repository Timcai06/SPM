#!/usr/bin/env python3
"""Task 1 collector entrypoint: source plugins -> normalized CSVs."""

from __future__ import annotations

import argparse
import csv
import json
import time
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import asyncio
import logging
from capabilities.collectors import (
    caixin,
    cninfo,
    csrc,
    eastmoney,
    gov,
    kr36,
    miit,
    ndrc,
    sse,
    szse,
    szse_suspension,
    yicai,
    akshare_api,
)
from capabilities.collectors.catalog import write_source_catalog
from capabilities.storage.load_task1 import upsert_raw_documents

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]
MANUAL_TEMPLATE = ROOT / "output" / "seeds" / "manual_news.csv"
SOURCE_CATALOG = ROOT / "output" / "meta" / "appendix2_sources.csv"
DEFAULT_REPORT_CSV = ROOT / "output" / "collector_report.csv"
DEFAULT_REPORT_JSON = ROOT / "output" / "collector_report.json"
DEFAULT_DB = "stock_event_mining"


def write_collector_report_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["collector", "success", "failure_category", "row_count", "duration_ms", "error", "run_at"],
        )
        writer.writeheader()
        writer.writerows(rows)


def classify_failure(error: str, row_count: int, success: str) -> str:
    if success == "true" and row_count == 0:
        return "empty_data"
    if not error:
        return ""
    lowered = error.lower()
    if any(token in lowered for token in ("timeout", "timed out", "connection", "ssl", "urlopen", "network", "refused")):
        return "network"
    if any(token in lowered for token in ("json", "decode", "parse", "keyerror", "valueerror")):
        return "parse"
    return "unknown"


async def run_collector(name: str, collect_func: Callable) -> tuple[str, list[dict], dict]:
    started = time.perf_counter()
    error = ""
    rows = []
    success = "false"
    try:
        # Properly handle both sync functions and coroutines/awaitables
        res = collect_func()
        if asyncio.iscoroutine(res) or asyncio.isfuture(res):
            rows = await res
        else:
            rows = res
        success = "true"
    except Exception as exc:
        error = str(exc)
        logger.error(f"Collector {name} failed: {exc}")
    
    duration_ms = int((time.perf_counter() - started) * 1000)
    report = {
        "collector": name,
        "success": success,
        "failure_category": classify_failure(error, len(rows), success),
        "row_count": str(len(rows)),
        "duration_ms": str(duration_ms),
        "error": error,
        "run_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    return name, rows, report


async def collect_all_async(limit: int, include_non_keyword: bool) -> list[dict]:
    """Orchestrate all collectors in parallel and return combined rows."""
    # We call the collect functions directly now, or keep them as lambdas
    jobs = [
        ("gov", lambda: gov.collect(limit=limit, include_non_keyword=include_non_keyword)),
        ("ndrc", lambda: ndrc.collect(limit=limit)),
        ("csrc", lambda: csrc.collect(limit=limit)),
        ("sse", lambda: sse.collect(limit=limit)),
        ("cninfo", lambda: cninfo.collect(limit=limit)),
        ("szse", lambda: szse.collect(limit=limit)),
        ("szse_suspension", lambda: szse_suspension.collect(limit=limit)),
        ("yicai", lambda: yicai.collect(limit=limit)),
        ("eastmoney", lambda: eastmoney.collect(limit=limit)),
        ("36kr", lambda: kr36.collect(limit=limit)),
        ("caixin", lambda: caixin.collect(limit=limit)),
        ("miit", lambda: miit.collect(limit=limit)),
        ("akshare", lambda: akshare_api.collect(limit=limit)),
    ]
    
    tasks = [run_collector(name, func) for name, func in jobs]
    results = await asyncio.gather(*tasks)
    
    all_combined_rows = []
    report_rows = []
    for name, rows, report in results:
        if rows:
            all_combined_rows.extend(rows)
        report_rows.append(report)
        logger.info(f"Collector {name} finished, fetched {len(rows)} rows in {report['duration_ms']}ms")
    
    # Write reports
    write_collector_report_csv(DEFAULT_REPORT_CSV, report_rows)
    DEFAULT_REPORT_JSON.write_text(json.dumps(report_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    
    return all_combined_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect live Task 1 source data (Async).")
    parser.add_argument("--limit", type=int, default=10, help="Max rows to fetch per source.")
    parser.add_argument("--include-non-keyword", action="store_true", help="Disable gov title keyword prefilter.")
    parser.add_argument("--db", default=DEFAULT_DB, help="Target PostgreSQL database name.")
    args = parser.parse_args()
    
    write_source_catalog(SOURCE_CATALOG)
    
    logger.info("Starting asynchronous data collection...")
    all_rows = asyncio.run(collect_all_async(args.limit, args.include_non_keyword))
    logger.info(f"Total rows collected: {len(all_rows)}")
    
    # Direct memory-to-database processing
    if all_rows:
        logger.info(f"Upserting {len(all_rows)} rows into database '{args.db}'...")
        upsert_raw_documents(args.db, all_rows)
        logger.info("Database upsert complete.")
    else:
        logger.warning("No rows collected, skipping database upsert.")


if __name__ == "__main__":
    main()
