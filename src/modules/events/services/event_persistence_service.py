#!/usr/bin/env python3
"""Event staging/final-load persistence owned by the module layer."""

from __future__ import annotations

import csv
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile

from modules.collectors.services.raw_document_loading_service import upsert_raw_documents
from modules.events.adapters.stage_builders import build_candidate_stage_rows, build_structured_stage_rows


ROOT = Path(__file__).resolve().parents[3]
TASK1_DB_SQL_PATH = ROOT / "sql" / "create_task1_db.sql"
TASK1_STAGE_SQL_PATH = ROOT / "sql" / "create_task1_stage_tables.sql"
CANDIDATE_STAGE_FIELDS = ["raw_document_url", "dedup_key", "duplicate_group_size", "is_event", "filter_reason", "evidence", "score_hint"]
STRUCTURED_STAGE_FIELDS = [
    "event_id",
    "raw_text_ref",
    "event_name",
    "event_date",
    "source",
    "source_type",
    "authority_level",
    "source_credibility_score",
    "event_subject_type",
    "event_subject_subtype",
    "duration_type",
    "predictability_type",
    "industry_type",
    "sentiment",
    "time_orientation",
    "event_stage",
    "shock_source_type",
    "region_scope",
    "trigger_word_score",
    "explicitness_score",
    "uncertainty_score",
    "novelty_score",
    "amount_scale",
    "amount_max_rmb",
    "amount_log_rmb",
    "event_code",
    "sw_l1_industry",
    "sw_l1_industry_code",
    "sentiment_score_0_100",
    "source_credibility_type",
    "company_count",
    "industry_count",
    "province_count",
    "city_count",
    "country_count",
    "chain_stage_count",
    "chain_stages",
    "report_count",
    "media_coverage_count",
    "heat_growth_rate",
    "heat_duration_days",
    "disagreement_score",
    "classification_confidence",
    "heat_score",
    "intensity_score",
    "impact_scope",
    "event_summary",
    "subject_entities",
    "classification_evidence",
]


def run_psql(db_name: str, sql: str) -> None:
    subprocess.run(
        ["psql", "-d", db_name, "-v", "ON_ERROR_STOP=1", "-c", sql],
        check=True,
        cwd=str(ROOT),
    )


def ensure_event_schema(db_name: str) -> None:
    sql = TASK1_DB_SQL_PATH.read_text(encoding="utf-8") + "\n" + TASK1_STAGE_SQL_PATH.read_text(encoding="utf-8")
    run_psql(db_name, sql)


def copy_csv_to_table(
    db_name: str,
    rows: list[dict[str, str]],
    fieldnames: list[str],
    table_name: str,
    truncate: bool = True,
) -> None:
    with NamedTemporaryFile("w", encoding="utf-8", newline="", suffix=".csv", delete=False) as tmp:
        writer = csv.DictWriter(tmp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        temp_path = tmp.name
    try:
        if truncate:
            run_psql(db_name, f"TRUNCATE TABLE {table_name} RESTART IDENTITY CASCADE;")
        sql = (
            f"\\copy {table_name} ({', '.join(fieldnames)}) "
            f"FROM '{temp_path}' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')"
        )
        subprocess.run(
            ["psql", "-d", db_name, "-v", "ON_ERROR_STOP=1", "-c", sql],
            check=True,
            cwd=str(ROOT),
        )
    finally:
        Path(temp_path).unlink(missing_ok=True)


def load_stage_rows(
    db_name: str,
    raw_documents: list[dict[str, str]],
    raw_candidates: list[dict[str, str]],
    structured_events: list[dict[str, str]],
) -> None:
    ensure_event_schema(db_name)
    upsert_raw_documents(db_name, raw_documents)
    copy_csv_to_table(
        db_name,
        build_candidate_stage_rows(raw_candidates),
        CANDIDATE_STAGE_FIELDS,
        "stg_event_candidates",
        truncate=True,
    )
    copy_csv_to_table(
        db_name,
        build_structured_stage_rows(structured_events),
        STRUCTURED_STAGE_FIELDS,
        "stg_structured_events",
        truncate=True,
    )


def insert_final_rows(db_name: str) -> None:
    run_psql(
        db_name,
        """
        INSERT INTO event_candidates (raw_document_id, dedup_key, duplicate_group_size, is_event, filter_reason, evidence, score_hint)
        SELECT d.id,
               s.dedup_key,
               s.duplicate_group_size::integer,
               s.is_event::boolean,
               s.filter_reason,
               s.evidence,
               NULLIF(s.score_hint, '')::integer
        FROM stg_event_candidates s
        JOIN raw_documents d ON d.url = s.raw_document_url
        ORDER BY d.id
        ON CONFLICT (raw_document_id) DO UPDATE
        SET dedup_key = EXCLUDED.dedup_key,
            duplicate_group_size = EXCLUDED.duplicate_group_size,
            is_event = EXCLUDED.is_event,
            filter_reason = EXCLUDED.filter_reason,
            evidence = EXCLUDED.evidence,
            score_hint = EXCLUDED.score_hint;
        """,
    )
    run_psql(
        db_name,
        """
        INSERT INTO structured_events (
            event_id, candidate_id, event_name, event_date, source,
            source_type, authority_level, source_credibility_score, event_subject_type, event_subject_subtype,
            duration_type, predictability_type, industry_type, sentiment,
            time_orientation, event_stage, shock_source_type, region_scope, trigger_word_score, explicitness_score,
            uncertainty_score, novelty_score, amount_scale, amount_max_rmb, amount_log_rmb, event_code,
            sw_l1_industry, sw_l1_industry_code, sentiment_score_0_100, source_credibility_type,
            company_count, industry_count, province_count, city_count, country_count, chain_stage_count,
            chain_stages, report_count, media_coverage_count, heat_growth_rate, heat_duration_days,
            disagreement_score, classification_confidence, heat_score, intensity_score,
            impact_scope, event_summary, subject_entities, raw_text_ref,
            classification_evidence
        )
        SELECT s.event_id,
               c.id,
               s.event_name,
               s.event_date::date,
               s.source,
               COALESCE(NULLIF(s.source_type, ''), '其他来源'),
               COALESCE(NULLIF(s.authority_level, ''), 'general_media'),
               COALESCE(NULLIF(s.source_credibility_score, '')::numeric, 1),
               s.event_subject_type,
               COALESCE(NULLIF(s.event_subject_subtype, ''), '未细分'),
               s.duration_type,
               s.predictability_type,
               s.industry_type,
               s.sentiment,
               COALESCE(NULLIF(s.time_orientation, ''), 'current_confirmed'),
               COALESCE(NULLIF(s.event_stage, ''), '确认'),
               COALESCE(NULLIF(s.shock_source_type, ''), '其他'),
               COALESCE(NULLIF(s.region_scope, ''), 'domestic'),
               COALESCE(NULLIF(s.trigger_word_score, '')::integer, 0),
               COALESCE(NULLIF(s.explicitness_score, '')::integer, 0),
               COALESCE(NULLIF(s.uncertainty_score, '')::integer, 0),
               COALESCE(NULLIF(s.novelty_score, '')::integer, 50),
               COALESCE(NULLIF(s.amount_scale, ''), 'none'),
               NULLIF(s.amount_max_rmb, '')::numeric,
               NULLIF(s.amount_log_rmb, '')::numeric,
               COALESCE(s.event_code, ''),
               COALESCE(NULLIF(s.sw_l1_industry, ''), '其他'),
               COALESCE(NULLIF(s.sw_l1_industry_code, ''), ''),
               COALESCE(NULLIF(s.sentiment_score_0_100, '')::integer, 50),
               COALESCE(NULLIF(s.source_credibility_type, ''), '单一媒体'),
               COALESCE(NULLIF(s.company_count, '')::integer, 0),
               COALESCE(NULLIF(s.industry_count, '')::integer, 0),
               COALESCE(NULLIF(s.province_count, '')::integer, 0),
               COALESCE(NULLIF(s.city_count, '')::integer, 0),
               COALESCE(NULLIF(s.country_count, '')::integer, 0),
               COALESCE(NULLIF(s.chain_stage_count, '')::integer, 0),
               COALESCE(NULLIF(s.chain_stages, '')::jsonb, '[]'::jsonb),
               COALESCE(NULLIF(s.report_count, '')::integer, 0),
               COALESCE(NULLIF(s.media_coverage_count, '')::integer, 0),
               COALESCE(NULLIF(s.heat_growth_rate, '')::numeric, 0),
               COALESCE(NULLIF(s.heat_duration_days, '')::integer, 0),
               COALESCE(NULLIF(s.disagreement_score, '')::numeric, 0),
               COALESCE(NULLIF(s.classification_confidence, '')::numeric, 0.5),
               s.heat_score::integer,
               s.intensity_score::integer,
               s.impact_scope,
               s.event_summary,
               s.subject_entities::jsonb,
               s.raw_text_ref,
               s.classification_evidence
        FROM stg_structured_events s
        JOIN raw_documents d ON d.url = s.raw_text_ref
        JOIN event_candidates c ON c.raw_document_id = d.id
        ORDER BY c.id
        ON CONFLICT (candidate_id) DO UPDATE
        SET event_id = EXCLUDED.event_id,
            event_name = EXCLUDED.event_name,
            event_date = EXCLUDED.event_date,
            source = EXCLUDED.source,
            source_type = EXCLUDED.source_type,
            authority_level = EXCLUDED.authority_level,
            source_credibility_score = EXCLUDED.source_credibility_score,
            event_subject_type = EXCLUDED.event_subject_type,
            event_subject_subtype = EXCLUDED.event_subject_subtype,
            duration_type = EXCLUDED.duration_type,
            predictability_type = EXCLUDED.predictability_type,
            industry_type = EXCLUDED.industry_type,
            sentiment = EXCLUDED.sentiment,
            time_orientation = EXCLUDED.time_orientation,
            event_stage = EXCLUDED.event_stage,
            shock_source_type = EXCLUDED.shock_source_type,
            region_scope = EXCLUDED.region_scope,
            trigger_word_score = EXCLUDED.trigger_word_score,
            explicitness_score = EXCLUDED.explicitness_score,
            uncertainty_score = EXCLUDED.uncertainty_score,
            novelty_score = EXCLUDED.novelty_score,
            amount_scale = EXCLUDED.amount_scale,
            amount_max_rmb = EXCLUDED.amount_max_rmb,
            amount_log_rmb = EXCLUDED.amount_log_rmb,
            event_code = EXCLUDED.event_code,
            sw_l1_industry = EXCLUDED.sw_l1_industry,
            sw_l1_industry_code = EXCLUDED.sw_l1_industry_code,
            sentiment_score_0_100 = EXCLUDED.sentiment_score_0_100,
            source_credibility_type = EXCLUDED.source_credibility_type,
            company_count = EXCLUDED.company_count,
            industry_count = EXCLUDED.industry_count,
            province_count = EXCLUDED.province_count,
            city_count = EXCLUDED.city_count,
            country_count = EXCLUDED.country_count,
            chain_stage_count = EXCLUDED.chain_stage_count,
            chain_stages = EXCLUDED.chain_stages,
            report_count = EXCLUDED.report_count,
            media_coverage_count = EXCLUDED.media_coverage_count,
            heat_growth_rate = EXCLUDED.heat_growth_rate,
            heat_duration_days = EXCLUDED.heat_duration_days,
            disagreement_score = EXCLUDED.disagreement_score,
            classification_confidence = EXCLUDED.classification_confidence,
            heat_score = EXCLUDED.heat_score,
            intensity_score = EXCLUDED.intensity_score,
            impact_scope = EXCLUDED.impact_scope,
            event_summary = EXCLUDED.event_summary,
            subject_entities = EXCLUDED.subject_entities,
            raw_text_ref = EXCLUDED.raw_text_ref,
            classification_evidence = EXCLUDED.classification_evidence;
        """,
    )
    run_psql(
        db_name,
        """
        DELETE FROM structured_events se
        USING event_candidates ec
        WHERE se.candidate_id = ec.id
          AND ec.id IN (
              SELECT c.id
              FROM stg_event_candidates s
              JOIN raw_documents d ON d.url = s.raw_document_url
              JOIN event_candidates c ON c.raw_document_id = d.id
          )
          AND ec.is_event = false;
        """,
    )
