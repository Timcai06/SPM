#!/usr/bin/env python3
"""High-level run metadata and provenance helpers."""

from __future__ import annotations

import csv
import hashlib
import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from modules.runtime.adapters import db_repository


def resolve_run_id(explicit_run_id: str = "") -> str:
    return explicit_run_id.strip() or datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _with_runtime_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(metadata or {})
    merged.setdefault("process_id", os.getpid())
    merged.setdefault("parent_process_id", os.getppid())
    merged.setdefault("working_directory", str(Path.cwd()))
    return merged


@contextmanager
def logged_run(
    db_name: str | None,
    command_group: str,
    command_name: str,
    argv: list[str],
    explicit_run_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> Iterator[str]:
    run_id = resolve_run_id(explicit_run_id)
    if db_name:
        db_repository.start_etl_run(
            db_name=db_name,
            run_id=run_id,
            command_group=command_group,
            command_name=command_name,
            argv=argv,
            metadata=_with_runtime_metadata(metadata),
        )
    try:
        yield run_id
    except Exception as exc:
        if db_name:
            db_repository.finish_etl_run(
                db_name=db_name,
                run_id=run_id,
                status="failed",
                error_message=str(exc),
            )
        raise
    else:
        if db_name:
            db_repository.finish_etl_run(
                db_name=db_name,
                run_id=run_id,
                status="success",
            )


@contextmanager
def logged_step(
    db_name: str | None,
    run_id: str,
    step_name: str,
    metadata: dict[str, Any] | None = None,
) -> Iterator[None]:
    if db_name and run_id:
        db_repository.start_etl_run_step(
            db_name=db_name,
            run_id=run_id,
            step_name=step_name,
            metadata=metadata,
        )
    try:
        yield
    except Exception as exc:
        if db_name and run_id:
            db_repository.finish_etl_run_step(
                db_name=db_name,
                run_id=run_id,
                step_name=step_name,
                status="failed",
                error_message=str(exc),
            )
        raise
    else:
        if db_name and run_id:
            db_repository.finish_etl_run_step(
                db_name=db_name,
                run_id=run_id,
                step_name=step_name,
                status="success",
                metadata=metadata,
            )


def _count_csv_rows(path: Path) -> int | None:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            next(reader, None)
            return sum(1 for _ in reader)
    except Exception:
        return None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def register_output_artifact(
    db_name: str,
    run_id: str,
    dataset_key: str,
    output_path: str | Path,
    metadata: dict[str, Any] | None = None,
) -> bool:
    path = Path(output_path).resolve()
    if not path.exists() or not path.is_file():
        return False
    row_count = _count_csv_rows(path) if path.suffix.lower() == ".csv" else None
    db_repository.upsert_dataset_version(
        db_name=db_name,
        dataset_key=dataset_key,
        dataset_path=str(path),
        producer_run_id=run_id,
        row_count=row_count,
        file_size_bytes=path.stat().st_size,
        content_hash=_sha256_file(path),
        metadata=metadata or {"suffix": path.suffix.lower()},
    )
    return True
