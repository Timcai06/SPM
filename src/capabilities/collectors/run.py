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
SOURCE_HEALTH_JSON = ROOT / "output" / "meta" / "collector_source_health.json"
DEFAULT_DB = "stock_event_mining"
NETWORK_ERROR_TOKENS = ("timeout", "timed out", "connection", "ssl", "urlopen", "network", "refused", "eof")
DEFAULT_COLLECTOR_TIMEOUT_SEC = 25
SOURCE_TIMEOUT_SEC = {
    "miit": 20,
}
BREAKER_FAILURE_THRESHOLD = 3
BREAKER_COOLDOWN_SEC = 30 * 60


def write_collector_report_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["collector", "success", "failure_category", "row_count", "duration_ms", "error", "run_at"],
        )
        writer.writeheader()
        writer.writerows(rows)


def load_source_health(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    raw_sources = payload.get("sources", {})
    if not isinstance(raw_sources, dict):
        return {}
    health: dict[str, dict] = {}
    for name, state in raw_sources.items():
        if not isinstance(state, dict):
            continue
        health[str(name)] = {
            "consecutive_failures": int(state.get("consecutive_failures", 0) or 0),
            "skip_until_ts": int(state.get("skip_until_ts", 0) or 0),
            "last_failure_category": str(state.get("last_failure_category", "")),
            "last_error": str(state.get("last_error", "")),
            "updated_at": str(state.get("updated_at", "")),
        }
    return health


def save_source_health(path: Path, health: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sources": health,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def classify_failure(error: str, row_count: int, success: str) -> str:
    if success == "true" and row_count == 0:
        return "empty_data"
    if not error:
        return ""
    lowered = error.lower()
    if any(token in lowered for token in NETWORK_ERROR_TOKENS):
        return "network"
    if any(token in lowered for token in ("json", "decode", "parse", "keyerror", "valueerror")):
        return "parse"
    return "unknown"


async def run_collector(name: str, collect_func: Callable) -> tuple[str, list[dict], dict]:
    started = time.perf_counter()
    error = ""
    rows = []
    success = "false"
    max_attempts = 3
    timeout_sec = SOURCE_TIMEOUT_SEC.get(name, DEFAULT_COLLECTOR_TIMEOUT_SEC)

    async def execute_collect() -> list[dict]:
        res = collect_func()
        if asyncio.iscoroutine(res) or asyncio.isfuture(res):
            return await res
        return res

    for attempt in range(1, max_attempts + 1):
        try:
            rows = await asyncio.wait_for(execute_collect(), timeout=timeout_sec)
            success = "true"
            break
        except asyncio.TimeoutError:
            error = f"timeout after {timeout_sec}s"
            is_network = True
            if attempt < max_attempts and is_network:
                wait_sec = attempt
                logger.warning(
                    f"Collector {name} attempt {attempt}/{max_attempts} failed ({error}), retry in {wait_sec}s"
                )
                await asyncio.sleep(wait_sec)
                continue
            logger.error(f"Collector {name} failed: {error}")
            break
        except Exception as exc:
            msg = str(exc).strip()
            error = msg or f"{exc.__class__.__name__}: <empty>"
            lowered = error.lower()
            is_network = any(token in lowered for token in NETWORK_ERROR_TOKENS)
            if attempt < max_attempts and is_network:
                wait_sec = attempt
                logger.warning(
                    f"Collector {name} attempt {attempt}/{max_attempts} failed ({error}), retry in {wait_sec}s"
                )
                await asyncio.sleep(wait_sec)
                continue
            logger.error(f"Collector {name} failed: {error}")
            break
    
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
    
    source_health = load_source_health(SOURCE_HEALTH_JSON)
    now_ts = int(time.time())

    all_combined_rows = []
    report_rows = []
    active_jobs = []
    for name, func in jobs:
        state = source_health.get(name, {})
        skip_until = int(state.get("skip_until_ts", 0) or 0)
        if skip_until > now_ts:
            wait_sec = skip_until - now_ts
            logger.warning(f"[breaker] skip collector {name}: cooldown {wait_sec}s remaining")
            report_rows.append(
                {
                    "collector": name,
                    "success": "false",
                    "failure_category": "cooldown_skip",
                    "row_count": "0",
                    "duration_ms": "0",
                    "error": f"source in cooldown, retry after {wait_sec}s",
                    "run_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
            continue
        active_jobs.append((name, func))

    total = len(jobs)
    completed = len(report_rows)
    started = time.perf_counter()
    heartbeat_sec = 5

    pending_tasks = {asyncio.create_task(run_collector(name, func)) for name, func in active_jobs}
    while pending_tasks:
        done, pending_tasks = await asyncio.wait(
            pending_tasks,
            timeout=heartbeat_sec,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if not done:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            logger.info(
                f"[progress] running collectors... completed={completed}/{total}, elapsed={elapsed_ms}ms"
            )
            continue

        for task in done:
            name, rows, report = task.result()
            completed += 1
            if rows:
                all_combined_rows.extend(rows)
            report_rows.append(report)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            logger.info(
                f"[progress] {completed}/{total} done: {name}, rows={len(rows)}, "
                f"duration={report['duration_ms']}ms, elapsed={elapsed_ms}ms"
            )
            state = source_health.get(
                name,
                {
                    "consecutive_failures": 0,
                    "skip_until_ts": 0,
                    "last_failure_category": "",
                    "last_error": "",
                    "updated_at": "",
                },
            )
            category = str(report.get("failure_category", "")).strip()
            if report.get("success") == "true":
                state["consecutive_failures"] = 0
                state["skip_until_ts"] = 0
                state["last_failure_category"] = ""
                state["last_error"] = ""
            else:
                if category in {"network", "unknown"}:
                    state["consecutive_failures"] = int(state.get("consecutive_failures", 0) or 0) + 1
                    if state["consecutive_failures"] >= BREAKER_FAILURE_THRESHOLD:
                        state["skip_until_ts"] = int(time.time()) + BREAKER_COOLDOWN_SEC
                        logger.warning(
                            f"[breaker] collector {name} enters cooldown {BREAKER_COOLDOWN_SEC}s "
                            f"after {state['consecutive_failures']} failures"
                        )
                else:
                    state["consecutive_failures"] = 0
                    state["skip_until_ts"] = 0
                state["last_failure_category"] = category
                state["last_error"] = str(report.get("error", ""))
            state["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            source_health[name] = state
    
    # Write reports
    write_collector_report_csv(DEFAULT_REPORT_CSV, report_rows)
    DEFAULT_REPORT_JSON.write_text(json.dumps(report_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    save_source_health(SOURCE_HEALTH_JSON, source_health)
    
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
