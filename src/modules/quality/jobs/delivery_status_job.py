#!/usr/bin/env python3
"""Report readiness for the formal data-delivery tables."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg

from modules.runtime.adapters.db import dsn_for


DEFAULT_DB = "stock_event_mining"


@dataclass(frozen=True)
class Check:
    area: str
    metric: str
    value: str
    target: str
    status: str
    detail: str = ""


def pct(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return float(numerator) / float(denominator)


def pct_text(value: float) -> str:
    return f"{value:.1%}"


def status_for(value: float, ok_threshold: float, warn_threshold: float | None = None) -> str:
    warn = ok_threshold if warn_threshold is None else warn_threshold
    if value >= ok_threshold:
        return "OK"
    if value >= warn:
        return "WARN"
    return "BLOCK"


def fetch_one(cur: psycopg.Cursor, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any]:
    cur.execute(sql, params)
    row = cur.fetchone()
    return dict(row) if row else {}


def table_exists(cur: psycopg.Cursor, table: str) -> bool:
    cur.execute("SELECT to_regclass(%s)", (f"public.{table}",))
    return cur.fetchone()["to_regclass"] is not None


def table_count(cur: psycopg.Cursor, table: str) -> int:
    cur.execute(f"SELECT count(*) AS rows FROM {table}")
    return int(cur.fetchone()["rows"])


def count_filled(cur: psycopg.Cursor, table: str, columns: list[str], where_sql: str = "") -> dict[str, int]:
    select_parts = ["count(*) AS rows"]
    for column in columns:
        select_parts.append(
            f"count(*) FILTER (WHERE {column} IS NOT NULL AND btrim({column}::text) <> '') AS {column}"
        )
    sql = f"SELECT {', '.join(select_parts)} FROM {table} {where_sql}"
    cur.execute(sql)
    row = cur.fetchone()
    return {key: int(value or 0) for key, value in dict(row).items()}


def add_presence_check(checks: list[Check], cur: psycopg.Cursor, table: str, min_rows: int) -> bool:
    if not table_exists(cur, table):
        checks.append(Check(table, "table_presence", "missing", f">= {min_rows} rows", "BLOCK", "table does not exist"))
        return False
    rows = table_count(cur, table)
    status = "OK" if rows >= min_rows else "BLOCK"
    checks.append(Check(table, "row_count", str(rows), f">= {min_rows}", status))
    return True


def add_fill_check(
    checks: list[Check],
    area: str,
    metric: str,
    filled: int,
    total: int,
    ok_threshold: float,
    warn_threshold: float,
    detail: str = "",
) -> None:
    ratio = pct(filled, total)
    checks.append(
        Check(
            area=area,
            metric=metric,
            value=f"{filled}/{total} ({pct_text(ratio)})",
            target=f">= {pct_text(ok_threshold)}",
            status=status_for(ratio, ok_threshold=ok_threshold, warn_threshold=warn_threshold),
            detail=detail,
        )
    )


def add_label_dictionary_checks(checks: list[Check], cur: psycopg.Cursor) -> None:
    if not add_presence_check(checks, cur, "label_dictionary", 1):
        return
    row = fetch_one(
        cur,
        """
        SELECT count(*) AS rows, count(DISTINCT label_group) AS groups
        FROM label_dictionary
        """,
    )
    groups = int(row["groups"] or 0)
    labels = int(row["rows"] or 0)
    checks.append(
        Check(
            "label_dictionary",
            "label_groups",
            f"{groups} groups / {labels} labels",
            ">= 10 groups",
            "OK" if groups >= 10 else "BLOCK",
            "DOCX event-classification framework should be represented here",
        )
    )


def add_raw_document_checks(checks: list[Check], cur: psycopg.Cursor) -> None:
    if not add_presence_check(checks, cur, "raw_documents", 1000):
        return
    row = fetch_one(
        cur,
        """
        SELECT count(*) AS rows,
               count(DISTINCT source) AS sources,
               count(*) - count(DISTINCT url) AS duplicate_urls
        FROM raw_documents
        """,
    )
    sources = int(row["sources"] or 0)
    duplicates = int(row["duplicate_urls"] or 0)
    checks.append(Check("raw_documents", "source_count", str(sources), ">= 8", "OK" if sources >= 8 else "WARN"))
    checks.append(
        Check(
            "raw_documents",
            "duplicate_urls",
            str(duplicates),
            "0",
            "OK" if duplicates == 0 else "WARN",
            "url uniqueness is enforced, so nonzero usually means nullable/legacy rows",
        )
    )


def add_structured_event_checks(checks: list[Check], cur: psycopg.Cursor) -> None:
    if not add_presence_check(checks, cur, "structured_events", 300):
        return
    total = table_count(cur, "structured_events")
    filled = count_filled(
        cur,
        "structured_events",
        [
            "event_subject_type",
            "event_subject_subtype",
            "source_type",
            "authority_level",
            "duration_type",
            "predictability_type",
            "sentiment",
            "event_stage",
            "shock_source_type",
            "region_scope",
            "impact_scope",
        ],
    )
    for column in [key for key in filled if key != "rows"]:
        add_fill_check(checks, "structured_events", f"{column}_fill", filled[column], total, 0.98, 0.90)

    enum_fields = [
        ("event_subject_type", "event_subject_type"),
        ("event_subject_subtype", "event_subject_subtype"),
        ("source_type", "source_type"),
        ("authority_level", "authority_level"),
        ("duration_type", "duration_type"),
        ("predictability_type", "predictability_type"),
        ("sentiment", "sentiment"),
        ("event_stage", "event_stage"),
        ("shock_source_type", "shock_source_type"),
        ("region_scope", "region_scope"),
        ("impact_scope", "impact_scope"),
    ]
    for column, label_group in enum_fields:
        row = fetch_one(
            cur,
            f"""
            SELECT count(*) AS invalid
            FROM structured_events e
            WHERE NOT EXISTS (
                SELECT 1
                FROM label_dictionary d
                WHERE d.label_group = %s
                  AND d.label_value = e.{column}
            )
            """,
            (label_group,),
        )
        invalid = int(row["invalid"] or 0)
        checks.append(
            Check(
                "structured_events",
                f"{column}_dictionary_miss",
                str(invalid),
                "0",
                "OK" if invalid == 0 else "WARN",
                f"values should exist in label_dictionary.{label_group}",
            )
        )


def add_company_profile_checks(checks: list[Check], cur: psycopg.Cursor) -> None:
    if not add_presence_check(checks, cur, "company_profiles", 50):
        return
    latest_snapshot = fetch_one(cur, "SELECT max(snapshot_date)::text AS snapshot_date FROM company_profiles").get("snapshot_date")
    where_sql = "WHERE snapshot_date = (SELECT max(snapshot_date) FROM company_profiles)"
    filled = count_filled(
        cur,
        "company_profiles",
        ["region", "list_date", "state_owned_flag", "employees", "total_shares", "float_shares", "core_products"],
        where_sql=where_sql,
    )
    total = filled["rows"]
    checks.append(
        Check(
            "company_profiles",
            "latest_snapshot",
            str(latest_snapshot or "none"),
            "current delivery snapshot",
            "OK" if latest_snapshot else "BLOCK",
            "fill metrics below are calculated on the latest snapshot only",
        )
    )
    thresholds = {
        "region": (0.80, 0.50),
        "list_date": (0.90, 0.60),
        "state_owned_flag": (0.70, 0.40),
        "employees": (0.60, 0.30),
        "total_shares": (0.80, 0.50),
        "float_shares": (0.80, 0.50),
        "core_products": (0.90, 0.70),
    }
    for column, (ok, warn) in thresholds.items():
        add_fill_check(checks, "company_profiles", f"{column}_fill", filled[column], total, ok, warn)


def add_stock_quote_checks(checks: list[Check], cur: psycopg.Cursor) -> None:
    if not add_presence_check(checks, cur, "stock_daily_quotes", 10000):
        return
    row = fetch_one(
        cur,
        """
        SELECT count(*) AS rows,
               count(DISTINCT ts_code) AS symbols,
               min(trade_date)::text AS min_date,
               max(trade_date)::text AS max_date,
               count(open) AS open_rows,
               count(high) AS high_rows,
               count(low) AS low_rows,
               count(amount) AS amount_rows,
               count(turnover_rate) AS turnover_rows,
               count(adj_factor) AS adj_rows,
               count(*) FILTER (WHERE is_limit_up OR is_limit_down) AS limit_flag_rows,
               count(*) FILTER (WHERE data_source <> 'sina') AS non_sina_rows
        FROM stock_daily_quotes
        """,
    )
    total = int(row["rows"] or 0)
    symbols = int(row["symbols"] or 0)
    checks.append(
        Check(
            "stock_daily_quotes",
            "symbol_count",
            str(symbols),
            ">= 50",
            "OK" if symbols >= 50 else "WARN",
            f"date range {row.get('min_date')}..{row.get('max_date')}",
        )
    )
    for metric, key, ok, warn in [
        ("open_fill", "open_rows", 0.98, 0.90),
        ("high_fill", "high_rows", 0.98, 0.90),
        ("low_fill", "low_rows", 0.98, 0.90),
        ("amount_fill", "amount_rows", 0.90, 0.50),
        ("turnover_rate_fill", "turnover_rows", 0.90, 0.50),
        ("adj_factor_fill", "adj_rows", 0.90, 0.50),
    ]:
        add_fill_check(checks, "stock_daily_quotes", metric, int(row[key] or 0), total, ok, warn)
    add_fill_check(
        checks,
        "stock_daily_quotes",
        "limit_flag_rows",
        int(row["limit_flag_rows"] or 0),
        total,
        0.001,
        0.0001,
        "zero means limit-up/down logic is probably only defaulting",
    )
    add_fill_check(
        checks,
        "stock_daily_quotes",
        "non_sina_source_rows",
        int(row["non_sina_rows"] or 0),
        total,
        0.50,
        0.01,
        "Sina fallback is acceptable for continuity, not for final high-quality delivery",
    )


def add_market_environment_checks(checks: list[Check], cur: psycopg.Cursor) -> None:
    if not add_presence_check(checks, cur, "market_environment_daily", 500):
        return
    total = table_count(cur, "market_environment_daily")
    filled = count_filled(
        cur,
        "market_environment_daily",
        ["index_return_1d", "market_turnover", "northbound_net_flow", "sector_hotness"],
    )
    for column, ok, warn in [
        ("index_return_1d", 0.70, 0.50),
        ("market_turnover", 0.90, 0.70),
        ("northbound_net_flow", 0.80, 0.20),
        ("sector_hotness", 0.90, 0.70),
    ]:
        add_fill_check(checks, "market_environment_daily", f"{column}_fill", filled[column], total, ok, warn)


def add_sentiment_checks(checks: list[Check], cur: psycopg.Cursor) -> None:
    if not add_presence_check(checks, cur, "sentiment_propagation_daily", 300):
        return
    total = table_count(cur, "sentiment_propagation_daily")
    filled = count_filled(
        cur,
        "sentiment_propagation_daily",
        ["heat_score", "heat_growth_rate", "heat_duration_days", "disagreement_score", "sentiment_std"],
    )
    for column, ok, warn in [
        ("heat_score", 0.80, 0.50),
        ("heat_growth_rate", 0.50, 0.25),
        ("heat_duration_days", 0.80, 0.50),
        ("disagreement_score", 0.50, 0.25),
        ("sentiment_std", 0.50, 0.25),
    ]:
        add_fill_check(checks, "sentiment_propagation_daily", f"{column}_fill", filled[column], total, ok, warn)


def add_company_relation_checks(checks: list[Check], cur: psycopg.Cursor) -> None:
    if not add_presence_check(checks, cur, "company_relations", 200):
        return
    row = fetch_one(
        cur,
        """
        SELECT count(*) AS rows,
               count(*) FILTER (WHERE direction = 'directed') AS directed_rows,
               count(*) FILTER (WHERE is_manual_override) AS manual_rows,
               count(DISTINCT relation_type) AS relation_types
        FROM company_relations
        """,
    )
    total = int(row["rows"] or 0)
    add_fill_check(checks, "company_relations", "directed_edge_ratio", int(row["directed_rows"] or 0), total, 0.35, 0.15)
    checks.append(
        Check(
            "company_relations",
            "relation_type_count",
            str(int(row["relation_types"] or 0)),
            ">= 5",
            "OK" if int(row["relation_types"] or 0) >= 5 else "WARN",
        )
    )
    manual_ratio = pct(int(row["manual_rows"] or 0), total)
    checks.append(
        Check(
            "company_relations",
            "manual_override_ratio",
            pct_text(manual_ratio),
            "<= 80% after automated/public-source expansion",
            "WARN" if manual_ratio > 0.80 else "OK",
            "manual seed is fine early, but final graph should not be all hand-made",
        )
    )


def add_event_company_link_checks(checks: list[Check], cur: psycopg.Cursor) -> None:
    if not add_presence_check(checks, cur, "event_company_links", 300):
        return
    row = fetch_one(
        cur,
        """
        SELECT count(*) AS rows,
               count(DISTINCT structured_event_id) AS events,
               count(DISTINCT company_id) AS companies,
               avg(final_link_score)::numeric(10,4) AS avg_score
        FROM event_company_links
        """,
    )
    checks.append(Check("event_company_links", "covered_events", str(row["events"]), ">= 150", "OK" if int(row["events"] or 0) >= 150 else "WARN"))
    checks.append(Check("event_company_links", "covered_companies", str(row["companies"]), ">= 50", "OK" if int(row["companies"] or 0) >= 50 else "WARN"))
    checks.append(Check("event_company_links", "avg_final_link_score", str(row["avg_score"]), ">= 0.35", "OK" if float(row["avg_score"] or 0) >= 0.35 else "WARN"))


def build_checks(db_name: str) -> list[Check]:
    checks: list[Check] = []
    with psycopg.connect(dsn_for(db_name), row_factory=psycopg.rows.dict_row) as conn:
        with conn.cursor() as cur:
            add_raw_document_checks(checks, cur)
            add_label_dictionary_checks(checks, cur)
            add_structured_event_checks(checks, cur)
            add_company_profile_checks(checks, cur)
            add_stock_quote_checks(checks, cur)
            add_market_environment_checks(checks, cur)
            add_sentiment_checks(checks, cur)
            add_company_relation_checks(checks, cur)
            add_event_company_link_checks(checks, cur)
    return checks


def render_markdown(checks: list[Check]) -> str:
    lines = [
        "# Data Delivery Status",
        "",
        "| Area | Metric | Value | Target | Status | Detail |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for check in checks:
        lines.append(
            "| "
            + " | ".join(
                [
                    check.area,
                    f"`{check.metric}`",
                    check.value,
                    check.target,
                    check.status,
                    check.detail.replace("|", "/"),
                ]
            )
            + " |"
        )
    blockers = sum(1 for check in checks if check.status == "BLOCK")
    warnings = sum(1 for check in checks if check.status == "WARN")
    lines.extend(
        [
            "",
            f"Summary: {blockers} BLOCK, {warnings} WARN, {len(checks) - blockers - warnings} OK.",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check formal data-delivery table readiness.")
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--output", default="", help="Optional markdown output path.")
    parser.add_argument("--fail-on-blockers", action="store_true", help="Exit nonzero when any BLOCK check exists.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    checks = build_checks(args.db)
    rendered = render_markdown(checks)
    print(rendered)
    if args.output:
        path = Path(args.output).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered + "\n", encoding="utf-8")
    if args.fail_on_blockers and any(check.status == "BLOCK" for check in checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
