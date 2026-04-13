#!/usr/bin/env python3
"""Build model-ready event-company samples into PostgreSQL."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import psycopg

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.storage.db_guard import write_guard


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = "stock_event_mining"
DEFAULT_LABEL_DATASET = ROOT / "output" / "task1_event_return_dataset.csv"
CREATE_SQL_PATH = ROOT / "sql" / "create_model_training_tables.sql"
SUPPORT_SQL_PATH = ROOT / "sql" / "create_training_support_tables.sql"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build model-ready samples for training.")
    parser.add_argument("--db", default=DEFAULT_DB, help="Target PostgreSQL database.")
    parser.add_argument("--min-link-score", type=float, default=0.35, help="Minimum event-company link score.")
    parser.add_argument(
        "--label-dataset",
        default=str(DEFAULT_LABEL_DATASET),
        help="Optional event-study dataset CSV (task1 feature output).",
    )
    parser.add_argument("--run-id", default="", help="Optional run id for traceability.")
    parser.add_argument("--lock-timeout-sec", type=int, default=120, help="Write lock timeout in seconds.")
    return parser.parse_args()


def parse_float(value: str) -> Optional[float]:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


def parse_bool_up(value: Optional[float]) -> Optional[bool]:
    if value is None:
        return None
    return value > 0


def resolve_label_dataset(path: Path) -> Path:
    if path.exists():
        return path
    candidates = [
        ROOT.parent / f"{ROOT.name}-main-run" / "output" / "task1_event_return_dataset.csv",
        ROOT.parent / f"{ROOT.name}-run" / "output" / "task1_event_return_dataset.csv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return path


def load_label_map(path: Path) -> tuple[dict[tuple[int, str], dict[str, object]], str]:
    if not path.exists():
        return {}, f"missing:{path}"
    mapping: dict[tuple[int, str], dict[str, object]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            sid_text = (row.get("structured_event_id") or "").strip()
            ts_code = (row.get("ts_code") or "").strip().upper()
            if not sid_text or not ts_code:
                continue
            try:
                sid = int(sid_text)
            except ValueError:
                continue
            mapping[(sid, ts_code)] = {
                "label_car_w1": parse_float(row.get("car_w1", "")),
                "label_car_w3": parse_float(row.get("car_w3", "")),
                "label_car_w5": parse_float(row.get("car_w5", "")),
                "label_source": (
                    f"{(row.get('benchmark_source') or '').strip()}|{(row.get('stock_source') or '').strip()}"
                ).strip("|")
                or "event_study",
            }
    return mapping, str(path)


def ensure_tables(conn: psycopg.Connection) -> None:
    sql = CREATE_SQL_PATH.read_text(encoding="utf-8") + "\n" + SUPPORT_SQL_PATH.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def fetch_base_rows(conn: psycopg.Connection, min_link_score: float) -> list[dict[str, Any]]:
    sql = """
        SELECT
            se.id AS structured_event_id,
            se.event_id,
            se.event_date,
            se.event_subject_type,
            se.event_subject_subtype,
            se.source_type,
            se.source_credibility_score,
            se.duration_type,
            se.predictability_type,
            se.industry_type AS event_industry_type,
            se.sentiment,
            se.event_stage,
            se.shock_source_type,
            se.trigger_word_score,
            se.explicitness_score,
            se.uncertainty_score,
            se.novelty_score,
            se.event_code,
            se.heat_score,
            se.intensity_score,
            se.impact_scope,
            CASE se.impact_scope
                WHEN '个股链条' THEN 1
                WHEN '行业' THEN 3
                WHEN '全市场' THEN 4
                ELSE 2
            END AS impact_level_score,
            l.company_id,
            l.link_type,
            l.final_link_score,
            COALESCE(ls.affected_company_count, 0) AS affected_company_count,
            COALESCE(ls.affected_industry_count, 0) AS affected_industry_count,
            ROW_NUMBER() OVER (PARTITION BY se.id ORDER BY l.final_link_score DESC, c.ts_code) AS relation_rank_in_event,
            c.ts_code,
            c.company_name,
            c.industry_l1 AS company_industry_l1,
            c.industry_l2 AS company_industry_l2,
            c.concept_tags,
            cl.canonical_event_id,
            cs.trade_date AS company_stat_date,
            cs.total_mv,
            cs.circ_mv,
            cs.pe_ttm,
            cs.pb,
            cs.turnover_rate,
            cs.volume_ratio,
            cs.trailing_return_5d,
            cs.trailing_return_20d,
            cs.trailing_return_60d,
            cs.volatility_5d,
            cs.volatility_20d,
            cs.volatility_60d,
            cs.up_days_20d
        FROM structured_events se
        JOIN event_company_links l ON l.structured_event_id = se.id
        JOIN companies c ON c.id = l.company_id
        LEFT JOIN (
            SELECT
                ecl.structured_event_id,
                COUNT(*) AS affected_company_count,
                COUNT(DISTINCT NULLIF(comp.industry_l1, '')) AS affected_industry_count
            FROM event_company_links ecl
            JOIN companies comp ON comp.id = ecl.company_id
            GROUP BY ecl.structured_event_id
        ) ls ON ls.structured_event_id = se.id
        LEFT JOIN int_event_canonical_links cl ON cl.structured_event_id = se.id
        LEFT JOIN LATERAL (
            SELECT *
            FROM int_company_stats cs
            WHERE cs.ts_code = c.ts_code
              AND cs.trade_date <= se.event_date
            ORDER BY cs.trade_date DESC
            LIMIT 1
        ) cs ON TRUE
        WHERE l.final_link_score >= %s
        ORDER BY se.event_date DESC, l.final_link_score DESC
    """
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(sql, (min_link_score,))
        return list(cur.fetchall())


def main() -> None:
    args = parse_args()
    run_id = args.run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    label_path = resolve_label_dataset(Path(args.label_dataset).resolve())
    label_map, label_path_used = load_label_map(label_path)

    with write_guard(
        db_name=args.db,
        required_tables=["structured_events", "event_company_links", "companies"],
        lock_timeout_sec=args.lock_timeout_sec,
    ) as conn:
        ensure_tables(conn)
        base_rows = fetch_base_rows(conn, args.min_link_score)
        upserted = 0
        with conn.cursor() as cur:
            for row in base_rows:
                sid = int(row["structured_event_id"])
                ts_code = (row["ts_code"] or "").upper()
                labels = label_map.get((sid, ts_code), {})
                car_w1 = labels.get("label_car_w1")
                car_w3 = labels.get("label_car_w3")
                car_w5 = labels.get("label_car_w5")
                label_source = str(labels.get("label_source") or "none")
                sample_key = f"{sid}:{int(row['company_id'])}:{row['event_date']}"

                cur.execute(
                    """
                    INSERT INTO model_event_samples (
                        sample_key, sample_run_id, structured_event_id, company_id, canonical_event_id,
                        event_id, event_date, ts_code, company_name,
                        event_subject_type, event_subject_subtype, source_type, source_credibility_score,
                        duration_type, predictability_type, event_industry_type,
                        sentiment, event_stage, shock_source_type, trigger_word_score, explicitness_score,
                        uncertainty_score, novelty_score, event_code, heat_score, intensity_score, impact_scope,
                        impact_level_score, affected_company_count, affected_industry_count, relation_rank_in_event,
                        link_type, final_link_score, company_industry_l1, company_industry_l2, concept_tags,
                        company_stat_date, total_mv, circ_mv, pe_ttm, pb, turnover_rate, volume_ratio,
                        trailing_return_5d, trailing_return_20d, trailing_return_60d,
                        volatility_5d, volatility_20d, volatility_60d, up_days_20d,
                        label_car_w1, label_car_w3, label_car_w5, label_up_w1, label_up_w3, label_up_w5, label_source,
                        updated_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s, %s::jsonb,
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s,
                        NOW()
                    )
                    ON CONFLICT (sample_key) DO UPDATE
                    SET
                        sample_run_id = EXCLUDED.sample_run_id,
                        canonical_event_id = EXCLUDED.canonical_event_id,
                        event_id = EXCLUDED.event_id,
                        ts_code = EXCLUDED.ts_code,
                        company_name = EXCLUDED.company_name,
                        event_subject_type = EXCLUDED.event_subject_type,
                        event_subject_subtype = EXCLUDED.event_subject_subtype,
                        source_type = EXCLUDED.source_type,
                        source_credibility_score = EXCLUDED.source_credibility_score,
                        duration_type = EXCLUDED.duration_type,
                        predictability_type = EXCLUDED.predictability_type,
                        event_industry_type = EXCLUDED.event_industry_type,
                        sentiment = EXCLUDED.sentiment,
                        event_stage = EXCLUDED.event_stage,
                        shock_source_type = EXCLUDED.shock_source_type,
                        trigger_word_score = EXCLUDED.trigger_word_score,
                        explicitness_score = EXCLUDED.explicitness_score,
                        uncertainty_score = EXCLUDED.uncertainty_score,
                        novelty_score = EXCLUDED.novelty_score,
                        event_code = EXCLUDED.event_code,
                        heat_score = EXCLUDED.heat_score,
                        intensity_score = EXCLUDED.intensity_score,
                        impact_scope = EXCLUDED.impact_scope,
                        impact_level_score = EXCLUDED.impact_level_score,
                        affected_company_count = EXCLUDED.affected_company_count,
                        affected_industry_count = EXCLUDED.affected_industry_count,
                        relation_rank_in_event = EXCLUDED.relation_rank_in_event,
                        link_type = EXCLUDED.link_type,
                        final_link_score = EXCLUDED.final_link_score,
                        company_industry_l1 = EXCLUDED.company_industry_l1,
                        company_industry_l2 = EXCLUDED.company_industry_l2,
                        concept_tags = EXCLUDED.concept_tags,
                        company_stat_date = EXCLUDED.company_stat_date,
                        total_mv = EXCLUDED.total_mv,
                        circ_mv = EXCLUDED.circ_mv,
                        pe_ttm = EXCLUDED.pe_ttm,
                        pb = EXCLUDED.pb,
                        turnover_rate = EXCLUDED.turnover_rate,
                        volume_ratio = EXCLUDED.volume_ratio,
                        trailing_return_5d = EXCLUDED.trailing_return_5d,
                        trailing_return_20d = EXCLUDED.trailing_return_20d,
                        trailing_return_60d = EXCLUDED.trailing_return_60d,
                        volatility_5d = EXCLUDED.volatility_5d,
                        volatility_20d = EXCLUDED.volatility_20d,
                        volatility_60d = EXCLUDED.volatility_60d,
                        up_days_20d = EXCLUDED.up_days_20d,
                        label_car_w1 = EXCLUDED.label_car_w1,
                        label_car_w3 = EXCLUDED.label_car_w3,
                        label_car_w5 = EXCLUDED.label_car_w5,
                        label_up_w1 = EXCLUDED.label_up_w1,
                        label_up_w3 = EXCLUDED.label_up_w3,
                        label_up_w5 = EXCLUDED.label_up_w5,
                        label_source = EXCLUDED.label_source,
                        updated_at = NOW()
                    """,
                    (
                        sample_key,
                        run_id,
                        sid,
                        int(row["company_id"]),
                        row.get("canonical_event_id"),
                        row["event_id"],
                        row["event_date"],
                        ts_code,
                        row["company_name"],
                        row["event_subject_type"],
                        row.get("event_subject_subtype"),
                        row.get("source_type"),
                        row.get("source_credibility_score"),
                        row["duration_type"],
                        row["predictability_type"],
                        row["event_industry_type"],
                        row["sentiment"],
                        row.get("event_stage"),
                        row.get("shock_source_type"),
                        row.get("trigger_word_score"),
                        row.get("explicitness_score"),
                        row.get("uncertainty_score"),
                        row.get("novelty_score"),
                        row.get("event_code"),
                        int(row["heat_score"]),
                        int(row["intensity_score"]),
                        row["impact_scope"],
                        row.get("impact_level_score"),
                        row.get("affected_company_count"),
                        row.get("affected_industry_count"),
                        row.get("relation_rank_in_event"),
                        row["link_type"],
                        row["final_link_score"],
                        row.get("company_industry_l1"),
                        row.get("company_industry_l2"),
                        json.dumps(row.get("concept_tags") or [], ensure_ascii=False),
                        row.get("company_stat_date"),
                        row.get("total_mv"),
                        row.get("circ_mv"),
                        row.get("pe_ttm"),
                        row.get("pb"),
                        row.get("turnover_rate"),
                        row.get("volume_ratio"),
                        row.get("trailing_return_5d"),
                        row.get("trailing_return_20d"),
                        row.get("trailing_return_60d"),
                        row.get("volatility_5d"),
                        row.get("volatility_20d"),
                        row.get("volatility_60d"),
                        row.get("up_days_20d"),
                        car_w1,
                        car_w3,
                        car_w5,
                        parse_bool_up(car_w1),
                        parse_bool_up(car_w3),
                        parse_bool_up(car_w5),
                        label_source,
                    ),
                )
                upserted += 1
        conn.commit()

    print(
        f"Built model_event_samples for db={args.db}: "
        f"upserted={upserted}, labels_loaded={len(label_map)}, label_path={label_path_used}"
    )
    print(f"run_id={run_id}")


if __name__ == "__main__":
    main()
