#!/usr/bin/env python3
"""Runtime metadata persistence helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import psycopg

from modules.runtime.adapters.db import dsn_for


ROOT = Path(__file__).resolve().parents[4]
RUN_METADATA_SQL_PATH = ROOT / "sql" / "create_run_metadata_tables.sql"


def ensure_run_metadata_tables(db_name: str) -> None:
    sql = RUN_METADATA_SQL_PATH.read_text(encoding="utf-8")
    with psycopg.connect(dsn_for(db_name)) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()


def start_etl_run(
    db_name: str,
    run_id: str,
    command_group: str,
    command_name: str,
    argv: list[str],
    metadata: dict[str, Any] | None = None,
) -> None:
    ensure_run_metadata_tables(db_name)
    sql = """
        INSERT INTO etl_runs (
            run_id, command_group, command_name, db_name, status, argv, metadata
        )
        VALUES (%s, %s, %s, %s, 'running', %s::jsonb, %s::jsonb)
        ON CONFLICT (run_id) DO UPDATE
        SET command_group = EXCLUDED.command_group,
            command_name = EXCLUDED.command_name,
            db_name = EXCLUDED.db_name,
            status = 'running',
            argv = EXCLUDED.argv,
            metadata = EXCLUDED.metadata,
            error_message = '',
            started_at = NOW(),
            finished_at = NULL
    """
    with psycopg.connect(dsn_for(db_name)) as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    run_id,
                    command_group,
                    command_name,
                    db_name,
                    json.dumps(argv, ensure_ascii=False),
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
        conn.commit()


def finish_etl_run(
    db_name: str,
    run_id: str,
    status: str,
    error_message: str = "",
    metadata: dict[str, Any] | None = None,
) -> None:
    sql = """
        UPDATE etl_runs
        SET status = %s,
            error_message = %s,
            metadata = metadata || %s::jsonb,
            finished_at = NOW()
        WHERE run_id = %s
    """
    with psycopg.connect(dsn_for(db_name)) as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    status,
                    error_message[:2000],
                    json.dumps(metadata or {}, ensure_ascii=False),
                    run_id,
                ),
            )
        conn.commit()


def start_etl_run_step(
    db_name: str,
    run_id: str,
    step_name: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    ensure_run_metadata_tables(db_name)
    sql = """
        INSERT INTO etl_run_steps (
            run_id, step_name, status, metadata
        )
        VALUES (%s, %s, 'running', %s::jsonb)
        ON CONFLICT (run_id, step_name) DO UPDATE
        SET status = 'running',
            metadata = EXCLUDED.metadata,
            error_message = '',
            row_count = NULL,
            started_at = NOW(),
            finished_at = NULL
    """
    with psycopg.connect(dsn_for(db_name)) as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    run_id,
                    step_name,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
        conn.commit()


def finish_etl_run_step(
    db_name: str,
    run_id: str,
    step_name: str,
    status: str,
    row_count: int | None = None,
    error_message: str = "",
    metadata: dict[str, Any] | None = None,
) -> None:
    sql = """
        UPDATE etl_run_steps
        SET status = %s,
            row_count = %s,
            error_message = %s,
            metadata = metadata || %s::jsonb,
            finished_at = NOW()
        WHERE run_id = %s AND step_name = %s
    """
    with psycopg.connect(dsn_for(db_name)) as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    status,
                    row_count,
                    error_message[:2000],
                    json.dumps(metadata or {}, ensure_ascii=False),
                    run_id,
                    step_name,
                ),
            )
        conn.commit()


def upsert_dataset_version(
    db_name: str,
    dataset_key: str,
    dataset_path: str,
    producer_run_id: str,
    row_count: int | None,
    file_size_bytes: int,
    content_hash: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    ensure_run_metadata_tables(db_name)
    sql = """
        INSERT INTO dataset_versions (
            dataset_key, dataset_path, producer_run_id, db_name,
            row_count, file_size_bytes, content_hash, metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (dataset_key, dataset_path, producer_run_id) DO UPDATE
        SET row_count = EXCLUDED.row_count,
            file_size_bytes = EXCLUDED.file_size_bytes,
            content_hash = EXCLUDED.content_hash,
            metadata = EXCLUDED.metadata
    """
    with psycopg.connect(dsn_for(db_name)) as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    dataset_key,
                    dataset_path,
                    producer_run_id,
                    db_name,
                    row_count,
                    file_size_bytes,
                    content_hash,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
        conn.commit()
