#!/usr/bin/env python3
"""Build sentiment propagation daily rows from structured events and canonical links."""

from __future__ import annotations

import argparse
import math
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import psycopg

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.storage.db_guard import dsn_for, write_guard


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = "stock_event_mining"
AUTHORITY_LEVELS = {"central", "ministry", "exchange", "listed_company", "top_media"}
KNOWN_SOURCE_CHANNELS = {
    "官方文件",
    "监管/交易所",
    "公司公告",
    "主流财经媒体",
    "行业协会/机构",
    "其他来源",
}
SOURCE_CHANNEL_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("官方文件", ("中国政府网", "国务院", "国家发展改革委", "发改委", "工信部", "财政部", "商务部", "央行")),
    ("监管/交易所", ("中国证监会", "证监会", "上交所", "深交所", "北交所")),
    ("公司公告", ("巨潮资讯网", "公司公告", "公告", "年报", "季报", "临时公告")),
    ("主流财经媒体", ("财新", "第一财经", "上海证券报", "证券时报", "中国证券报", "36氪", "东方财富", "Reuters", "Bloomberg")),
    ("行业协会/机构", ("协会", "商会", "联盟", "研究院")),
)
SENTIMENT_MAP = {
    "利好": 1,
    "Positive": 1,
    "positive": 1,
    "利空": -1,
    "Negative": -1,
    "negative": -1,
    "中性": 0,
    "Neutral": 0,
    "neutral": 0,
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load sentiment propagation daily rows into PostgreSQL.")
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--lock-timeout-sec", type=int, default=120)
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args(argv)


def normalize_source_channel(source_type: str, source_name: str) -> str:
    text = f"{source_type or ''} {source_name or ''}"
    for label, keywords in SOURCE_CHANNEL_RULES:
        if any(keyword in text for keyword in keywords):
            return label
    if source_type and source_type.strip() in KNOWN_SOURCE_CHANNELS:
        return source_type.strip()
    return "其他来源"


def sentiment_to_score(value: str) -> int:
    text = (value or "").strip()
    if text in SENTIMENT_MAP:
        return SENTIMENT_MAP[text]
    if "利好" in text or "正" in text:
        return 1
    if "利空" in text or "负" in text:
        return -1
    return 0


def safe_float(value: object, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        text = str(value).strip()
        if not text:
            return default
        return float(text)
    except Exception:
        return default


def mean_or_zero(values: list[float]) -> float:
    return float(statistics.mean(values)) if values else 0.0


def stdev_or_zero(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    return float(statistics.pstdev(values))


def load_source_rows(conn: psycopg.Connection) -> list[dict[str, object]]:
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(
            """
            SELECT
                COALESCE(ce.canonical_event_id, se.event_id) AS canonical_event_id,
                se.event_date::date AS stat_date,
                se.source_type,
                se.authority_level,
                se.sentiment,
                se.heat_score,
                rd.source AS raw_source,
                rd.title AS raw_title
            FROM structured_events se
            JOIN int_event_candidates ec ON ec.id = se.candidate_id
            JOIN raw_documents rd ON rd.id = ec.raw_document_id
            LEFT JOIN int_event_canonical_links ecl ON ecl.structured_event_id = se.id
            LEFT JOIN int_canonical_events ce ON ce.canonical_event_id = ecl.canonical_event_id
            ORDER BY canonical_event_id, stat_date, se.source_type, rd.source, rd.title
            """
        )
        return list(cur.fetchall())


@dataclass
class DailyStat:
    mention_count: int = 0
    heat_scores: list[float] = None  # type: ignore[assignment]
    sentiments: list[int] = None  # type: ignore[assignment]
    raw_sources: set[str] = None  # type: ignore[assignment]
    authority_count: int = 0

    def __post_init__(self) -> None:
        if self.heat_scores is None:
            self.heat_scores = []
        if self.sentiments is None:
            self.sentiments = []
        if self.raw_sources is None:
            self.raw_sources = set()


def build_rows(source_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], DailyStat] = defaultdict(DailyStat)
    daily_totals: dict[tuple[str, str], int] = defaultdict(int)

    for row in source_rows:
        canonical_event_id = str(row.get("canonical_event_id") or "").strip()
        stat_date = str(row.get("stat_date") or "").strip()
        source_channel = normalize_source_channel(str(row.get("source_type") or ""), str(row.get("raw_source") or ""))
        if not canonical_event_id or not stat_date:
            continue
        key = (canonical_event_id, stat_date, source_channel)
        stat = grouped[key]
        stat.mention_count += 1
        stat.heat_scores.append(safe_float(row.get("heat_score")))
        sentiment_score = sentiment_to_score(str(row.get("sentiment") or ""))
        stat.sentiments.append(sentiment_score)
        stat.raw_sources.add(str(row.get("raw_source") or "").strip() or str(row.get("raw_title") or "").strip())
        if str(row.get("authority_level") or "").strip() in AUTHORITY_LEVELS:
            stat.authority_count += 1

        daily_key = (canonical_event_id, stat_date)
        daily_totals[daily_key] += 1

    daily_growth: dict[tuple[str, str], float] = {}
    daily_duration: dict[tuple[str, str], int] = {}
    daily_stance_divergence: dict[tuple[str, str], float] = {}
    by_canonical: dict[str, list[str]] = defaultdict(list)
    for canonical_event_id, stat_date in daily_totals.keys():
        by_canonical[canonical_event_id].append(stat_date)

    for canonical_event_id, dates in by_canonical.items():
        sorted_dates = sorted(set(dates))
        prev_date = None
        prev_total = None
        streak = 0
        for stat_date in sorted_dates:
            total = daily_totals[(canonical_event_id, stat_date)]
            if prev_total and prev_total > 0:
                daily_growth[(canonical_event_id, stat_date)] = (total - prev_total) / prev_total
            else:
                daily_growth[(canonical_event_id, stat_date)] = 0.0
            if prev_date is not None:
                current_dt = datetime.strptime(stat_date, "%Y-%m-%d").date()
                prev_dt = datetime.strptime(prev_date, "%Y-%m-%d").date()
                if (current_dt - prev_dt).days == 1:
                    streak += 1
                else:
                    streak = 1
            else:
                streak = 1
            daily_duration[(canonical_event_id, stat_date)] = streak
            prev_total = total
            prev_date = stat_date

            channel_means: list[float] = []
            for (cid, cdate, _channel), stat in grouped.items():
                if cid != canonical_event_id or cdate != stat_date:
                    continue
                channel_means.append(mean_or_zero([float(x) for x in stat.sentiments]))
            if len(channel_means) <= 1:
                daily_stance_divergence[(canonical_event_id, stat_date)] = 0.0
            else:
                daily_stance_divergence[(canonical_event_id, stat_date)] = max(channel_means) - min(channel_means)

    rows: list[dict[str, object]] = []
    for (canonical_event_id, stat_date, source_channel), stat in sorted(grouped.items()):
        daily_key = (canonical_event_id, stat_date)
        total_mentions = daily_totals[daily_key]
        sentiment_counts = {
            1: sum(1 for item in stat.sentiments if item > 0),
            -1: sum(1 for item in stat.sentiments if item < 0),
            0: sum(1 for item in stat.sentiments if item == 0),
        }
        sentiment_list = [float(item) for item in stat.sentiments]
        dominant_share = max(sentiment_counts.values()) / max(total_mentions, 1)
        heat_score = mean_or_zero(stat.heat_scores)
        search_index = heat_score * math.log1p(total_mentions) * 10.0
        source_divergence = daily_stance_divergence.get(daily_key, 0.0)
        rows.append(
            {
                "canonical_event_id": canonical_event_id,
                "stat_date": stat_date,
                "source_channel": source_channel,
                "mention_count": stat.mention_count,
                "media_count": stat.mention_count if source_channel != "其他来源" else 0,
                "authority_media_count": stat.authority_count,
                "repost_count": max(0, stat.mention_count - len(stat.raw_sources)),
                "search_index": f"{search_index:.4f}",
                "heat_score": f"{heat_score:.6f}",
                "heat_growth_rate": f"{daily_growth.get(daily_key, 0.0):.6f}",
                "heat_duration_days": daily_duration.get(daily_key, 1),
                "sentiment_pos_count": sentiment_counts[1],
                "sentiment_neg_count": sentiment_counts[-1],
                "sentiment_neu_count": sentiment_counts[0],
                "disagreement_score": f"{(1.0 - dominant_share):.6f}",
                "sentiment_std": f"{stdev_or_zero(sentiment_list):.6f}",
                "source_stance_divergence": f"{source_divergence:.6f}",
            }
        )
    return rows


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    with write_guard(
        db_name=args.db,
        required_tables=[
            "raw_documents",
            "structured_events",
            "int_canonical_events",
            "int_event_canonical_links",
            "sentiment_propagation_daily",
        ],
        lock_timeout_sec=args.lock_timeout_sec,
    ) as conn:
        source_rows = load_source_rows(conn)
        rows = build_rows(source_rows)
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE sentiment_propagation_daily RESTART IDENTITY CASCADE;")
            if rows:
                cur.executemany(
                    """
                    INSERT INTO sentiment_propagation_daily (
                        canonical_event_id, stat_date, source_channel, mention_count, media_count,
                        authority_media_count, repost_count, search_index, heat_score,
                        heat_growth_rate, heat_duration_days, sentiment_pos_count, sentiment_neg_count,
                        sentiment_neu_count, disagreement_score, sentiment_std, source_stance_divergence
                    )
                    VALUES (
                        %(canonical_event_id)s, %(stat_date)s::date, %(source_channel)s, %(mention_count)s, %(media_count)s,
                        %(authority_media_count)s, %(repost_count)s, %(search_index)s::numeric, %(heat_score)s::numeric,
                        %(heat_growth_rate)s::numeric, %(heat_duration_days)s, %(sentiment_pos_count)s, %(sentiment_neg_count)s,
                        %(sentiment_neu_count)s, %(disagreement_score)s::numeric, %(sentiment_std)s::numeric, %(source_stance_divergence)s::numeric
                    )
                    ON CONFLICT (canonical_event_id, stat_date, source_channel) DO UPDATE
                    SET mention_count = EXCLUDED.mention_count,
                        media_count = EXCLUDED.media_count,
                        authority_media_count = EXCLUDED.authority_media_count,
                        repost_count = EXCLUDED.repost_count,
                        search_index = EXCLUDED.search_index,
                        heat_score = EXCLUDED.heat_score,
                        heat_growth_rate = EXCLUDED.heat_growth_rate,
                        heat_duration_days = EXCLUDED.heat_duration_days,
                        sentiment_pos_count = EXCLUDED.sentiment_pos_count,
                        sentiment_neg_count = EXCLUDED.sentiment_neg_count,
                        sentiment_neu_count = EXCLUDED.sentiment_neu_count,
                        disagreement_score = EXCLUDED.disagreement_score,
                        sentiment_std = EXCLUDED.sentiment_std,
                        source_stance_divergence = EXCLUDED.source_stance_divergence,
                        updated_at = NOW()
                    """,
                    rows,
                )
        conn.commit()

    if not args.quiet:
        print(f"Loaded {len(rows)} sentiment_propagation_daily rows into {args.db}")


if __name__ == "__main__":
    main()
