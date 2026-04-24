#!/usr/bin/env python3
"""Orchestrate the raw data replenishment workflow from source profiles."""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

from modules.collectors.domain.source_profiles import RAW_HISTORY_SOURCE_PROFILES, RawHistorySourceProfile


ROOT = Path(__file__).resolve().parents[4]
COLLECT_CLI = ROOT / "src" / "cli" / "collect.py"
QUALITY_CLI = ROOT / "src" / "cli" / "quality.py"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run full raw_documents replenishment workflow.")
    parser.add_argument("--db", default="stock_event_mining")
    parser.add_argument("--start-date", default="2025-01-01")
    parser.add_argument("--end-date", default="2026-04-23")
    parser.add_argument("--max-jobs", type=int, default=4)
    parser.add_argument("--min-content-length", type=int, default=300)
    parser.add_argument("--cninfo-max-symbols", type=int, default=3000)
    parser.add_argument("--cninfo-limit-per-symbol", type=int, default=120)
    parser.add_argument("--cninfo-workers", type=int, default=24)
    parser.add_argument("--cninfo-backfill-max-rows", type=int, default=30000)
    parser.add_argument("--cninfo-backfill-workers", type=int, default=24)
    parser.add_argument("--top-n", type=int, default=200)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def _python_cmd(*parts: object) -> list[str]:
    return [sys.executable, *[str(part) for part in parts]]


def _cninfo_history_cmd(args: argparse.Namespace) -> list[str]:
    return _python_cmd(
        COLLECT_CLI,
        "collect-history",
        "--db",
        args.db,
        "--source",
        "cninfo-disclosure",
        "--start-date",
        args.start_date,
        "--end-date",
        args.end_date,
        "--max-symbols",
        args.cninfo_max_symbols,
        "--limit-per-symbol",
        args.cninfo_limit_per_symbol,
        "--workers",
        args.cninfo_workers,
        "--cninfo-fulltext",
        "--cninfo-fulltext-max-chars",
        12000,
    )


def _history_cmd(args: argparse.Namespace, profile: RawHistorySourceProfile) -> list[str]:
    if profile.symbol_mode:
        return _python_cmd(
            COLLECT_CLI,
            "collect-history",
            "--db",
            args.db,
            "--source",
            profile.history_source,
            "--start-date",
            args.start_date,
            "--end-date",
            args.end_date,
            "--max-symbols",
            profile.max_symbols,
            "--limit-per-symbol",
            profile.limit_per_symbol,
            "--workers",
            profile.workers,
            "--db-flush-every",
            profile.db_flush_every,
        )

    cmd = _python_cmd(
        COLLECT_CLI,
        "collect-history",
        "--db",
        args.db,
        "--source",
        profile.history_source,
        "--start-date",
        args.start_date,
        "--end-date",
        args.end_date,
        "--max-pages",
        profile.max_pages,
        "--page-size",
        50,
        "--workers",
        profile.workers,
        "--db-flush-every",
        profile.db_flush_every,
        "--min-content-length",
        args.min_content_length,
    )
    if profile.body_quality_required:
        cmd.append("--quality-body-only")
    return cmd


def _cninfo_backfill_cmd(args: argparse.Namespace) -> list[str]:
    return _python_cmd(
        COLLECT_CLI,
        "backfill-cninfo-fulltext",
        "--db",
        args.db,
        "--source",
        "巨潮资讯网/历史公告",
        "--start-date",
        args.start_date,
        "--end-date",
        args.end_date,
        "--max-rows",
        args.cninfo_backfill_max_rows,
        "--workers",
        args.cninfo_backfill_workers,
        "--retries",
        3,
        "--sleep-sec",
        0.02,
        "--progress-every",
        10,
        "--heartbeat-sec",
        5,
        "--detail-timeout-sec",
        20,
        "--pdf-timeout-sec",
        20,
        "--db-flush-every",
        100,
        "--fulltext-max-chars",
        12000,
    )


def _normalize_cmd(args: argparse.Namespace) -> list[str]:
    return _python_cmd(QUALITY_CLI, "normalize-raw-categories", "--db", args.db)


def _raw_status_cmd(args: argparse.Namespace) -> list[str]:
    return _python_cmd(
        QUALITY_CLI,
        "raw",
        "--db",
        args.db,
        "--start-date",
        args.start_date,
        "--end-date",
        args.end_date,
        "--top-n",
        args.top_n,
    )


def _quote_cmd(cmd: list[str]) -> str:
    return shlex.join(cmd)


def _run(cmd: list[str], *, dry_run: bool) -> None:
    print(f"[full-raw] run {_quote_cmd(cmd)}")
    if dry_run:
        return
    subprocess.run(cmd, cwd=ROOT, check=True)


def _run_profile_batch(args: argparse.Namespace) -> None:
    running: list[tuple[RawHistorySourceProfile, subprocess.Popen]] = []

    def wait_one() -> None:
        profile, proc = running.pop(0)
        code = proc.wait()
        if code != 0:
            raise subprocess.CalledProcessError(code, _history_cmd(args, profile))

    for profile in RAW_HISTORY_SOURCE_PROFILES:
        cmd = _history_cmd(args, profile)
        print(f"[full-raw] start {profile.history_source} - {profile.note}")
        print(f"[full-raw] run {_quote_cmd(cmd)}")
        if args.dry_run:
            continue
        running.append((profile, subprocess.Popen(cmd, cwd=ROOT)))
        while len(running) >= args.max_jobs:
            wait_one()

    while running:
        wait_one()


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    _run(_cninfo_history_cmd(args), dry_run=args.dry_run)
    _run_profile_batch(args)
    _run(_cninfo_backfill_cmd(args), dry_run=args.dry_run)
    _run(_normalize_cmd(args), dry_run=args.dry_run)
    _run(_raw_status_cmd(args), dry_run=args.dry_run)


if __name__ == "__main__":
    main()
