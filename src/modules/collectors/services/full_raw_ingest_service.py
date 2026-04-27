#!/usr/bin/env python3
"""Orchestrate the raw data replenishment workflow from source profiles."""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from modules.collectors.domain.source_profiles import (
    RAW_HISTORY_SOURCE_PROFILES,
    RawHistorySourceProfile,
    profile_by_history_source,
)
from modules.runtime.adapters.db import dsn_for


ROOT = Path(__file__).resolve().parents[4]
COLLECT_CLI = ROOT / "src" / "cli" / "collect.py"
QUALITY_CLI = ROOT / "src" / "cli" / "quality.py"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run full raw_documents replenishment workflow.")
    parser.add_argument("--db", default="stock_event_mining")
    parser.add_argument("--start-date", default="2025-01-01")
    parser.add_argument("--end-date", default="2026-04-23")
    parser.add_argument("--max-jobs", type=int, default=6)
    parser.add_argument("--min-content-length", type=int, default=300)
    parser.add_argument("--target-body-rows", type=int, default=0, help="Override the per-source strong body target; 0 uses each source profile default.")
    parser.add_argument("--cninfo-max-symbols", type=int, default=3000)
    parser.add_argument("--cninfo-limit-per-symbol", type=int, default=120)
    parser.add_argument("--cninfo-workers", type=int, default=32)
    parser.add_argument("--cninfo-backfill-max-rows", type=int, default=30000)
    parser.add_argument("--cninfo-backfill-workers", type=int, default=32)
    parser.add_argument("--top-n", type=int, default=200)
    parser.add_argument("--force", action="store_true", help="Run every source even when current rows already meet the profile target.")
    parser.add_argument("--fail-fast", action="store_true", help="Stop the whole workflow when any source collection subprocess fails.")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


@dataclass(frozen=True)
class SourceProgress:
    current_rows: int = 0
    strong_body_rows: int = 0


@dataclass(frozen=True)
class CollectionTask:
    name: str
    family: str
    mode: str
    target: str
    strategy: str
    progress: str
    cmd: list[str]


def _python_cmd(*parts: object) -> list[str]:
    return [sys.executable, *[str(part) for part in parts]]


def _cninfo_history_cmd(args: argparse.Namespace) -> list[str]:
    profile = _profile_by_source("cninfo-disclosure")
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
    if profile.requires_body:
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


def _profile_by_source(history_source: str) -> RawHistorySourceProfile:
    return profile_by_history_source(history_source)


def _mode_label(profile: RawHistorySourceProfile) -> str:
    return "symbol" if profile.symbol_mode else "direct"


def _target_rows(args: argparse.Namespace, profile: RawHistorySourceProfile) -> int:
    if profile.target_rows <= 0:
        return profile.target_rows
    return args.target_body_rows if args.target_body_rows > 0 else profile.target_rows


def _target_label(args: argparse.Namespace, profile: RawHistorySourceProfile) -> str:
    target_rows = _target_rows(args, profile)
    return "unbounded" if target_rows <= 0 else str(target_rows)


def _target_metric(profile: RawHistorySourceProfile) -> str:
    return "strong_body_rows"


def _progress_value(profile: RawHistorySourceProfile, progress: SourceProgress) -> int:
    return progress.strong_body_rows


def _gap_to_target(args: argparse.Namespace, profile: RawHistorySourceProfile, progress: SourceProgress) -> int:
    target_rows = _target_rows(args, profile)
    if target_rows <= 0:
        return 0
    return max(target_rows - _progress_value(profile, progress), 0)


def _should_run_profile(args: argparse.Namespace, profile: RawHistorySourceProfile, progress: SourceProgress | None) -> bool:
    if args.force or _target_rows(args, profile) <= 0 or progress is None:
        return True
    return _gap_to_target(args, profile, progress) > 0


def _strategy_label(profile: RawHistorySourceProfile) -> str:
    if profile.allow_backfill and profile.requires_body:
        return "backfill+body+coverage"
    if profile.allow_backfill:
        return "backfill+coverage"
    if profile.requires_body:
        return "body+coverage"
    return "coverage"


def _fetch_progress(args: argparse.Namespace) -> dict[str, SourceProgress] | None:
    rows: dict[str, SourceProgress] = {}
    try:
        with psycopg.connect(dsn_for(args.db), row_factory=dict_row) as conn:
            for profile in RAW_HISTORY_SOURCE_PROFILES:
                pattern_clauses = " OR ".join(["source LIKE %s"] * len(profile.source_patterns))
                params: list[object] = [args.start_date, args.end_date, *profile.source_patterns]
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT
                            COUNT(*) AS current_rows,
                            COUNT(*) FILTER (
                                WHERE LENGTH(COALESCE(content, '')) >= %s
                                  AND BTRIM(COALESCE(content, '')) <> BTRIM(COALESCE(title, ''))
                            ) AS strong_body_rows
                        FROM raw_documents
                        WHERE publish_time >= %s::timestamp
                          AND publish_time < %s::timestamp
                          AND ({pattern_clauses})
                        """,
                        [args.min_content_length, *params],
                    )
                    row = cur.fetchone() or {}
                rows[profile.history_source] = SourceProgress(
                    current_rows=int(row.get("current_rows") or 0),
                    strong_body_rows=int(row.get("strong_body_rows") or 0),
                )
    except Exception as exc:
        print(f"[full-raw] warn progress_probe_failed error={exc}; running all profile sources", flush=True)
        return None
    return rows


def _progress_label(args: argparse.Namespace, profile: RawHistorySourceProfile, progress: SourceProgress | None) -> str:
    if progress is None:
        return "current=? metric=? gap=?"
    current_value = _progress_value(profile, progress)
    if _target_rows(args, profile) <= 0:
        gap = "unbounded"
    else:
        gap = str(_gap_to_target(args, profile, progress))
    return f"current={current_value} metric={_target_metric(profile)} gap={gap}"


def _print_plan(args: argparse.Namespace, progress_by_source: dict[str, SourceProgress] | None) -> None:
    print(
        f"[full-raw] plan db={args.db} window={args.start_date}..{args.end_date} "
        f"max_jobs={args.max_jobs} min_content_length={args.min_content_length} force={int(args.force)}",
        flush=True,
    )
    cninfo = _profile_by_source("cninfo-disclosure")
    print(
        "[full-raw] source "
        f"{cninfo.history_source} family={cninfo.collector_family} mode={_mode_label(cninfo)} "
        f"category={cninfo.raw_event_category} target={_target_label(args, cninfo)} "
        f"strategy={_strategy_label(cninfo)} note={cninfo.note}",
        flush=True,
    )
    for profile in RAW_HISTORY_SOURCE_PROFILES:
        progress = progress_by_source.get(profile.history_source) if progress_by_source is not None else None
        action = "run" if _should_run_profile(args, profile, progress) else "skip"
        print(
            "[full-raw] source "
            f"{profile.history_source} family={profile.collector_family} mode={_mode_label(profile)} "
            f"category={profile.raw_event_category} target={_target_label(args, profile)} "
            f"strategy={_strategy_label(profile)} action={action} {_progress_label(args, profile, progress)} note={profile.note}",
            flush=True,
        )
    print("[full-raw] post_steps normalize_raw_categories -> raw_status", flush=True)


def _run(cmd: list[str], *, dry_run: bool) -> None:
    print(f"[full-raw] run {_quote_cmd(cmd)}")
    if dry_run:
        return
    subprocess.run(cmd, cwd=ROOT, check=True)


def _cninfo_collection_task(args: argparse.Namespace) -> CollectionTask:
    profile = _profile_by_source("cninfo-disclosure")
    return CollectionTask(
        name=profile.history_source,
        family=profile.collector_family,
        mode=_mode_label(profile),
        target=_target_label(args, profile),
        strategy=_strategy_label(profile),
        progress="current=? metric=unbounded gap=unbounded",
        cmd=_cninfo_history_cmd(args),
    )


def _profile_collection_task(
    args: argparse.Namespace,
    profile: RawHistorySourceProfile,
    progress: SourceProgress | None,
) -> CollectionTask:
    return CollectionTask(
        name=profile.history_source,
        family=profile.collector_family,
        mode=_mode_label(profile),
        target=_target_label(args, profile),
        strategy=_strategy_label(profile),
        progress=_progress_label(args, profile, progress),
        cmd=_history_cmd(args, profile),
    )


def _build_collection_tasks(
    args: argparse.Namespace,
    progress_by_source: dict[str, SourceProgress] | None,
) -> list[CollectionTask]:
    tasks = [_cninfo_collection_task(args)]
    for profile in RAW_HISTORY_SOURCE_PROFILES:
        progress = progress_by_source.get(profile.history_source) if progress_by_source is not None else None
        if not _should_run_profile(args, profile, progress):
            print(
                f"[full-raw] skip {profile.history_source} "
                f"target={_target_label(args, profile)} {_progress_label(args, profile, progress)}",
                flush=True,
            )
            continue
        tasks.append(_profile_collection_task(args, profile, progress))
    return tasks


def _run_collection_tasks(args: argparse.Namespace, tasks: list[CollectionTask]) -> None:
    running: list[tuple[CollectionTask, subprocess.Popen]] = []
    failures: list[tuple[CollectionTask, int]] = []

    def wait_one() -> None:
        task, proc = running.pop(0)
        code = proc.wait()
        if code != 0:
            failures.append((task, code))
            print(f"[full-raw] warn source_failed source={task.name} exit_code={code}", flush=True)
            if args.fail_fast:
                raise subprocess.CalledProcessError(code, task.cmd)

    def stop_running() -> None:
        for task, proc in running:
            if proc.poll() is None:
                print(f"[full-raw] terminate {task.name} pid={proc.pid}", flush=True)
                proc.terminate()
        for task, proc in running:
            if proc.poll() is not None:
                continue
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                print(f"[full-raw] kill {task.name} pid={proc.pid}", flush=True)
                proc.kill()
        running.clear()

    print(f"[full-raw] collection_queue tasks={len(tasks)} max_jobs={args.max_jobs}", flush=True)
    try:
        for task in tasks:
            print(
                f"[full-raw] start {task.name} "
                f"family={task.family} mode={task.mode} target={task.target} "
                f"strategy={task.strategy} {task.progress}",
                flush=True,
            )
            print(f"[full-raw] run {_quote_cmd(task.cmd)}")
            if args.dry_run:
                continue
            running.append((task, subprocess.Popen(task.cmd, cwd=ROOT)))
            while len(running) >= args.max_jobs:
                wait_one()

        while running:
            wait_one()
    except BaseException:
        stop_running()
        raise
    if failures:
        failed_sources = ",".join(task.name for task, _code in failures)
        print(f"[full-raw] source_failures count={len(failures)} sources={failed_sources}", flush=True)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    progress_by_source = _fetch_progress(args)
    _print_plan(args, progress_by_source)
    _run_collection_tasks(args, _build_collection_tasks(args, progress_by_source))
    _run(_cninfo_backfill_cmd(args), dry_run=args.dry_run)
    _run(_normalize_cmd(args), dry_run=args.dry_run)
    _run(_raw_status_cmd(args), dry_run=args.dry_run)


if __name__ == "__main__":
    main()
