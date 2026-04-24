#!/usr/bin/env python3
"""Database storage audit, raw-source coverage, and stage cleanup jobs."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from modules.collectors.domain.source_profiles import iter_source_pattern_rows
from modules.runtime.adapters.db import dsn_for
from modules.runtime.adapters.db import write_guard


ROOT = Path(__file__).resolve().parents[4]
INSPECT_SQL_PATH = ROOT / "sql" / "inspect_storage_footprint.sql"


SOURCE_PATTERN_ROWS = iter_source_pattern_rows()
REPLENISH_SOURCE_PATTERN_ROWS = iter_source_pattern_rows(include_cninfo=False)


def _source_pattern_values_sql(rows: list[tuple[str, str, str, str, bool, str]] | None = None) -> str:
    selected = SOURCE_PATTERN_ROWS if rows is None else rows
    return ",\n                ".join(["(%s, %s, %s, %s, %s, %s)"] * len(selected))


def _source_pattern_params(rows: list[tuple[str, str, str, str, bool, str]] | None = None) -> list[object]:
    selected = SOURCE_PATTERN_ROWS if rows is None else rows
    params: list[object] = []
    for row in selected:
        params.extend(row)
    return params


def _source_profile_case_sql(result_column: str, *, source_expr: str = "source") -> tuple[str, list[object]]:
    clauses: list[str] = []
    params: list[object] = []
    for _history_source, source_family, source_pattern, raw_event_category, _body_capable, _note in SOURCE_PATTERN_ROWS:
        result = source_family if result_column == "source_family" else raw_event_category
        clauses.append(f"WHEN {source_expr} LIKE %s THEN %s")
        params.extend([source_pattern, result])
    fallback = "'其他'" if result_column == "source_family" else f"{source_expr}"
    return f"CASE {' '.join(clauses)} ELSE {fallback} END", params


def parse_audit_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect database storage footprint.")
    parser.add_argument("--db", default="stock_event_mining")
    return parser.parse_args(argv)


def parse_clean_stage_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean rebuildable stage tables.")
    parser.add_argument("--db", default="stock_event_mining")
    parser.add_argument("--lock-timeout-sec", type=int, default=120)
    parser.add_argument("--yes", action="store_true", help="Execute cleanup. Required for destructive action.")
    return parser.parse_args(argv)


def parse_raw_coverage_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect raw_documents source coverage for a date window.")
    parser.add_argument("--db", default="stock_event_mining")
    parser.add_argument("--start-date", default="2025-01-01")
    parser.add_argument("--end-date", default="2027-01-01", help="Exclusive upper bound.")
    parser.add_argument("--top-n", type=int, default=200)
    return parser.parse_args(argv)


def parse_normalize_raw_categories_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize raw_documents symbol_or_subject to Appendix-2 event categories.")
    parser.add_argument("--db", default="stock_event_mining")
    parser.add_argument("--start-date", default="", help="Optional inclusive lower publish_time bound.")
    parser.add_argument("--end-date", default="", help="Optional exclusive upper publish_time bound.")
    parser.add_argument("--lock-timeout-sec", type=int, default=120)
    return parser.parse_args(argv)


def run_storage_audit(argv: list[str] | None = None) -> None:
    args = parse_audit_args(argv)
    subprocess.run(["psql", "-d", args.db, "-f", str(INSPECT_SQL_PATH)], check=True)


def run_raw_source_coverage(argv: list[str] | None = None) -> None:
    args = parse_raw_coverage_args(argv)
    with psycopg.connect(dsn_for(args.db), row_factory=dict_row) as conn:
        overview = _fetch_raw_overview(conn, args.start_date, args.end_date)
        family_rows = _fetch_family_summary(conn, args.start_date, args.end_date, args.top_n)
        category_rows = _fetch_raw_category_summary(conn, args.start_date, args.end_date)
        action_rows = _fetch_source_actions(conn, args.start_date, args.end_date, args.top_n)
        replenish_rows = _fetch_replenish_progress(conn, args.start_date, args.end_date)
    _print_raw_dashboard(
        db_name=args.db,
        start_date=args.start_date,
        end_date=args.end_date,
        overview=overview,
        family_rows=family_rows,
        category_rows=category_rows,
        action_rows=action_rows,
        replenish_rows=replenish_rows,
    )


def run_normalize_raw_categories(argv: list[str] | None = None) -> None:
    args = parse_normalize_raw_categories_args(argv)
    with write_guard(
        db_name=args.db,
        required_tables=["raw_documents"],
        lock_timeout_sec=args.lock_timeout_sec,
    ) as conn:
        updated = _normalize_raw_categories(conn, start_date=args.start_date, end_date=args.end_date)
        conn.commit()
    window = ""
    if args.start_date or args.end_date:
        window = f" window={args.start_date or '-inf'}..{args.end_date or '+inf'}"
    print(f"Normalized raw event categories for db={args.db}{window}: updated={updated}")


def run_clean_stage(argv: list[str] | None = None) -> None:
    args = parse_clean_stage_args(argv)
    if not args.yes:
        raise SystemExit("Refusing to truncate stage tables without --yes.")
    with write_guard(
        db_name=args.db,
        required_tables=["stg_event_candidates", "stg_structured_events"],
        lock_timeout_sec=args.lock_timeout_sec,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE stg_event_candidates RESTART IDENTITY CASCADE")
            cur.execute("TRUNCATE TABLE stg_structured_events RESTART IDENTITY CASCADE")
        conn.commit()
    print(f"Cleaned stage tables for db={args.db}: stg_event_candidates, stg_structured_events")


def _fetch_one(conn: psycopg.Connection, sql: str, params: tuple[object, ...]) -> dict[str, object]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
    return dict(row) if row is not None else {}


def _fetch_all(conn: psycopg.Connection, sql: str, params: tuple[object, ...]) -> list[dict[str, object]]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return [dict(row) for row in rows]


def _fetch_raw_overview(conn: psycopg.Connection, start_date: str, end_date: str) -> dict[str, object]:
    return _fetch_one(
        conn,
        """
        WITH windowed AS (
            SELECT source, content, title, publish_time
            FROM raw_documents
            WHERE publish_time >= %s::timestamp
              AND publish_time < %s::timestamp
        ),
        non_cninfo AS (
            SELECT source, count(*) AS rows_2025_2026
            FROM windowed
            WHERE source <> '巨潮资讯网/历史公告'
            GROUP BY source
        )
        SELECT
            COUNT(*) AS raw_rows,
            COUNT(DISTINCT source) AS distinct_sources,
            COUNT(*) FILTER (
                WHERE LENGTH(COALESCE(content, '')) >= 80
                  AND BTRIM(COALESCE(content, '')) <> BTRIM(COALESCE(title, ''))
            ) AS qualified_rows,
            COUNT(*) FILTER (
                WHERE LENGTH(COALESCE(content, '')) >= 300
                  AND BTRIM(COALESCE(content, '')) <> BTRIM(COALESCE(title, ''))
            ) AS strong_rows,
            (SELECT COALESCE(MIN(rows_2025_2026), 0) FROM non_cninfo) AS non_cninfo_min_rows,
            (SELECT COALESCE(MAX(rows_2025_2026), 0) FROM non_cninfo) AS non_cninfo_max_rows,
            (
                SELECT COALESCE(percentile_cont(0.5) WITHIN GROUP (ORDER BY rows_2025_2026), 0)
                FROM non_cninfo
            ) AS non_cninfo_median_rows,
            (
                SELECT COALESCE(percentile_cont(0.75) WITHIN GROUP (ORDER BY rows_2025_2026), 0)
                FROM non_cninfo
            ) AS non_cninfo_p75_rows
        FROM windowed
        """,
        (start_date, end_date),
    )


def _fetch_family_summary(
    conn: psycopg.Connection,
    start_date: str,
    end_date: str,
    top_n: int,
) -> list[dict[str, object]]:
    family_case_sql, family_case_params = _source_profile_case_sql("source_family")
    return _fetch_all(
        conn,
        f"""
        WITH windowed AS (
          SELECT
            source,
            count(*) FILTER (
              WHERE publish_time >= %s::timestamp
                AND publish_time < %s::timestamp
            ) AS rows_2025_2026,
            count(*) FILTER (
              WHERE publish_time >= %s::timestamp
                AND publish_time < %s::timestamp
                AND length(coalesce(content, '')) >= 300
                AND btrim(coalesce(content, '')) <> btrim(title)
                AND btrim(coalesce(content, '')) <> btrim(regexp_replace(title, '^[^：:]+[：:]', ''))
            ) AS qualified_fulltext_rows
          FROM raw_documents
          GROUP BY source
        ),
        family AS (
          SELECT
            {family_case_sql} AS source_family,
            rows_2025_2026,
            qualified_fulltext_rows
          FROM windowed
        )
        SELECT
          source_family,
          SUM(rows_2025_2026) AS rows_2025_2026,
          SUM(qualified_fulltext_rows) AS qualified_fulltext_rows,
          ROUND(100.0 * SUM(qualified_fulltext_rows) / NULLIF(SUM(rows_2025_2026), 0), 2) AS qualified_pct
        FROM family
        WHERE rows_2025_2026 > 0
        GROUP BY source_family
        ORDER BY rows_2025_2026 DESC, source_family
        LIMIT %s
        """,
        (start_date, end_date, start_date, end_date, *family_case_params, top_n),
    )


def _fetch_raw_category_summary(
    conn: psycopg.Connection,
    start_date: str,
    end_date: str,
) -> list[dict[str, object]]:
    return _fetch_all(
        conn,
        """
        WITH windowed AS (
            SELECT symbol_or_subject
            FROM raw_documents
            WHERE publish_time >= %s::timestamp
              AND publish_time < %s::timestamp
        ),
        normalized AS (
            SELECT
                CASE
                    WHEN symbol_or_subject IN ('政策类事件', '公司行为事件', '行业/技术事件', '宏观/地缘事件')
                        THEN symbol_or_subject
                    WHEN NULLIF(BTRIM(COALESCE(symbol_or_subject, '')), '') IS NULL
                        THEN '未填充'
                    ELSE '待规范'
                END AS raw_event_category
            FROM windowed
        )
        SELECT raw_event_category, COUNT(*) AS rows
        FROM normalized
        GROUP BY raw_event_category
        ORDER BY
            CASE raw_event_category
                WHEN '政策类事件' THEN 1
                WHEN '公司行为事件' THEN 2
                WHEN '行业/技术事件' THEN 3
                WHEN '宏观/地缘事件' THEN 4
                WHEN '待规范' THEN 5
                ELSE 6
            END,
            raw_event_category
        """,
        (start_date, end_date),
    )


def _fetch_source_actions(
    conn: psycopg.Connection,
    start_date: str,
    end_date: str,
    top_n: int,
) -> list[dict[str, object]]:
    return _fetch_all(
        conn,
        """
        WITH base AS (
          SELECT
            source,
            count(*) AS rows_2025_2026,
            count(*) FILTER (
              WHERE nullif(btrim(coalesce(content, '')), '') IS NOT NULL
            ) AS nonempty_content_rows,
            count(*) FILTER (
              WHERE length(coalesce(content, '')) >= 300
                AND btrim(coalesce(content, '')) <> btrim(title)
                AND btrim(coalesce(content, '')) <> btrim(regexp_replace(title, '^[^：:]+[：:]', ''))
            ) AS qualified_fulltext_rows
          FROM raw_documents
          WHERE publish_time >= %s::timestamp
            AND publish_time < %s::timestamp
          GROUP BY source
        )
        SELECT
          source,
          rows_2025_2026,
          nonempty_content_rows,
          qualified_fulltext_rows,
          round(100.0 * qualified_fulltext_rows / nullif(rows_2025_2026, 0), 2) AS qualified_pct,
          CASE
            WHEN source = '巨潮资讯网/历史公告' THEN 'keep_fulltext_backfill_for_2025_2026'
            WHEN rows_2025_2026 < 50 THEN 'expand_2025_2026_collection'
            WHEN qualified_fulltext_rows = 0 THEN 'source_is_thin_or_has_no_detail_backfill'
            WHEN round(100.0 * qualified_fulltext_rows / nullif(rows_2025_2026, 0), 2) < 50 THEN 'improve_fulltext_fill_rate'
            ELSE 'keep_collecting'
          END AS action_hint
        FROM base
        WHERE rows_2025_2026 > 0
        ORDER BY rows_2025_2026 DESC, source
        LIMIT %s
        """,
        (start_date, end_date, top_n),
    )


def _normalize_raw_categories(conn: psycopg.Connection, *, start_date: str = "", end_date: str = "") -> int:
    date_filters = []
    params: list[object] = []
    if start_date:
        date_filters.append("publish_time >= %s::timestamp")
        params.append(start_date)
    if end_date:
        date_filters.append("publish_time < %s::timestamp")
        params.append(end_date)
    date_sql = ""
    if date_filters:
        date_sql = " AND " + " AND ".join(date_filters)

    category_case_sql, category_case_params = _source_profile_case_sql("raw_event_category", source_expr="rd.source")
    sql = f"""
        WITH matched AS (
            SELECT rd.id, {category_case_sql} AS raw_event_category
            FROM raw_documents rd
            WHERE rd.source IS NOT NULL
              {date_sql}
        )
        UPDATE raw_documents rd
        SET symbol_or_subject = matched.raw_event_category
        FROM matched
        WHERE rd.id = matched.id
          AND rd.symbol_or_subject IS DISTINCT FROM matched.raw_event_category
    """
    with conn.cursor() as cur:
        cur.execute(sql, [*category_case_params, *params])
        return int(cur.rowcount or 0)


def _fetch_replenish_progress(
    conn: psycopg.Connection,
    start_date: str,
    end_date: str,
) -> list[dict[str, object]]:
    values_sql = _source_pattern_values_sql(REPLENISH_SOURCE_PATTERN_ROWS)
    return _fetch_all(
        conn,
        f"""
        WITH targets(history_source, source_family, source_pattern, raw_event_category, body_capable, note) AS (
            VALUES
                {values_sql}
        ),
        source_counts AS (
            SELECT
                source,
                COUNT(*) AS current_rows,
                COUNT(*) FILTER (
                    WHERE LENGTH(COALESCE(content, '')) >= 80
                      AND BTRIM(COALESCE(content, '')) <> BTRIM(COALESCE(title, ''))
                ) AS qualified_rows,
                COUNT(*) FILTER (
                    WHERE LENGTH(COALESCE(content, '')) >= 300
                      AND BTRIM(COALESCE(content, '')) <> BTRIM(COALESCE(title, ''))
                ) AS strong_body_rows
            FROM raw_documents
            WHERE publish_time >= %s::timestamp
              AND publish_time < %s::timestamp
            GROUP BY source
        ),
        counts AS (
            SELECT
                t.history_source,
                t.body_capable,
                t.note,
                COALESCE(SUM(sc.current_rows), 0) AS current_rows,
                COALESCE(SUM(sc.qualified_rows), 0) AS qualified_rows,
                COALESCE(SUM(sc.strong_body_rows), 0) AS strong_body_rows
            FROM targets t
            LEFT JOIN source_counts sc
              ON sc.source LIKE t.source_pattern
            GROUP BY t.history_source, t.body_capable, t.note
        )
        SELECT
            history_source,
            body_capable,
            current_rows,
            qualified_rows,
            strong_body_rows,
            CASE
                WHEN body_capable THEN GREATEST(5000 - strong_body_rows, 0)
                ELSE NULL
            END AS gap_to_target,
            note
        FROM counts
        ORDER BY body_capable DESC, strong_body_rows DESC, current_rows DESC
        """,
        (*_source_pattern_params(REPLENISH_SOURCE_PATTERN_ROWS), start_date, end_date),
    )


def _format_int(value: object) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "0"


def _print_kv(label: str, value: object) -> None:
    print(f"{label:<18} {_format_int(value)}")


def _print_table(title: str, rows: list[dict[str, object]], columns: list[tuple[str, str]]) -> None:
    print()
    print(title)
    if not rows:
        print("  (no rows)")
        return
    widths: list[int] = []
    for key, header in columns:
        width = len(header)
        for row in rows:
            width = max(width, len(str(row.get(key, ""))))
        widths.append(width)
    header_line = "  " + "  ".join(header.ljust(width) for (_, header), width in zip(columns, widths, strict=False))
    print(header_line)
    print("  " + "  ".join("-" * width for width in widths))
    for row in rows:
        print("  " + "  ".join(str(row.get(key, "")).ljust(width) for (key, _), width in zip(columns, widths, strict=False)))


def _print_raw_dashboard(
    *,
    db_name: str,
    start_date: str,
    end_date: str,
    overview: dict[str, object],
    family_rows: list[dict[str, object]],
    category_rows: list[dict[str, object]],
    action_rows: list[dict[str, object]],
    replenish_rows: list[dict[str, object]],
) -> None:
    print(f"Raw Dashboard  db={db_name}  window={start_date}..{end_date}")
    print()
    _print_kv("raw_rows", overview.get("raw_rows"))
    _print_kv("qualified_rows", overview.get("qualified_rows"))
    _print_kv("strong_rows", overview.get("strong_rows"))
    _print_kv("distinct_sources", overview.get("distinct_sources"))
    _print_kv("non_cninfo_min", overview.get("non_cninfo_min_rows"))
    _print_kv("non_cninfo_median", overview.get("non_cninfo_median_rows"))
    _print_kv("non_cninfo_p75", overview.get("non_cninfo_p75_rows"))
    _print_kv("non_cninfo_max", overview.get("non_cninfo_max_rows"))

    family_display = [
        {
            "source_family": row["source_family"],
            "rows": _format_int(row["rows_2025_2026"]),
            "strong": _format_int(row["qualified_fulltext_rows"]),
            "pct": f"{row['qualified_pct']}%",
        }
        for row in family_rows[:10]
    ]
    _print_table(
        "Top source families",
        family_display,
        [("source_family", "family"), ("rows", "rows"), ("strong", "strong"), ("pct", "strong_pct")],
    )

    category_display = [
        {
            "raw_event_category": row["raw_event_category"],
            "rows": _format_int(row["rows"]),
        }
        for row in category_rows
    ]
    _print_table(
        "Appendix-2 raw categories",
        category_display,
        [("raw_event_category", "category"), ("rows", "rows")],
    )

    body_priority = [
        {
            "history_source": row["history_source"],
            "current": _format_int(row["current_rows"]),
            "strong": _format_int(row["strong_body_rows"]),
            "gap": _format_int(row["gap_to_target"]),
            "note": row["note"],
        }
        for row in replenish_rows
        if bool(row["body_capable"])
    ]
    _print_table(
        "Priority:补正文+扩量",
        body_priority,
        [("history_source", "source"), ("current", "rows"), ("strong", "strong"), ("gap", "gap"), ("note", "note")],
    )

    coverage_priority = []
    for row in replenish_rows:
        if bool(row["body_capable"]):
            continue
        coverage_priority.append(
            {
                "history_source": row["history_source"],
                "current": _format_int(row["current_rows"]),
                "qualified": _format_int(row["qualified_rows"]),
                "note": row["note"],
            }
        )
    _print_table(
        "Priority:补覆盖",
        coverage_priority,
        [("history_source", "source"), ("current", "rows"), ("qualified", "qualified"), ("note", "note")],
    )

    action_priority: list[dict[str, object]] = []
    for row in action_rows:
        if row["action_hint"] not in {"expand_2025_2026_collection", "improve_fulltext_fill_rate"}:
            continue
        action_priority.append(
            {
                "source": row["source"],
                "rows": _format_int(row["rows_2025_2026"]),
                "strong": _format_int(row["qualified_fulltext_rows"]),
                "hint": row["action_hint"],
            }
        )
        if len(action_priority) >= 12:
            break
    _print_table(
        "Top action queue",
        action_priority,
        [("source", "source"), ("rows", "rows"), ("strong", "strong"), ("hint", "action")],
    )
