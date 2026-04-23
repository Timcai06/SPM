#!/usr/bin/env python3
"""Build a lightweight event-link quality report."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import psycopg

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from modules.runtime.adapters.db import dsn_for


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = "stock_event_mining"
DEFAULT_REPORT = ROOT / "output" / "linking_quality_report.md"
DEFAULT_SAMPLE = ROOT / "output" / "linking_quality_sample.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate event-link quality report.")
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT))
    parser.add_argument("--sample-path", default=str(DEFAULT_SAMPLE))
    parser.add_argument("--sample-size", type=int, default=30)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report_path = Path(args.report_path).resolve()
    sample_path = Path(args.sample_path).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    sample_path.parent.mkdir(parents=True, exist_ok=True)

    with psycopg.connect(dsn_for(args.db), row_factory=psycopg.rows.dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("select count(*) as cnt from companies")
            companies = cur.fetchone()["cnt"]
            cur.execute("select count(*) as cnt from structured_events")
            structured_events = cur.fetchone()["cnt"]
            cur.execute("select count(*) as cnt from event_company_links")
            links = cur.fetchone()["cnt"]
            cur.execute("select count(distinct structured_event_id) as cnt from event_company_links")
            covered_events = cur.fetchone()["cnt"]
            cur.execute(
                """
                select link_type, count(*) as cnt
                from event_company_links
                group by link_type
                order by cnt desc
                """
            )
            type_rows = cur.fetchall()
            cur.execute(
                """
                select e.event_name,
                       e.industry_type,
                       rd.title,
                       rd.symbol_or_subject,
                       c.ts_code,
                       c.company_name,
                       c.industry_l1,
                       l.link_type,
                       l.final_link_score
                from event_company_links l
                join structured_events e on e.id=l.structured_event_id
                join event_candidates ec on ec.id=e.candidate_id
                join raw_documents rd on rd.id=ec.raw_document_id
                join companies c on c.id=l.company_id
                where rd.symbol_or_subject in ('政策类事件','行业/技术事件','宏观/地缘事件')
                order by l.final_link_score desc, l.id asc
                limit %s
                """,
                (args.sample_size,),
            )
            samples = cur.fetchall()

    with sample_path.open("w", encoding="utf-8", newline="") as f:
        fieldnames = ["event_name", "industry_type", "title", "symbol_or_subject", "ts_code", "company_name", "industry_l1", "link_type", "final_link_score"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(samples)

    coverage_pct = round(100.0 * covered_events / structured_events, 2) if structured_events else 0.0
    lines = [
        "# 事件关联质量报告",
        "",
        f"- companies: {companies}",
        f"- structured_events: {structured_events}",
        f"- event_company_links: {links}",
        f"- covered_events: {covered_events}",
        f"- coverage_pct: {coverage_pct}%",
        "",
        "## 按 link_type 分布",
    ]
    for row in type_rows:
        lines.append(f"- {row['link_type']}: {row['cnt']}")
    lines.extend(
        [
            "",
            "## 抽样说明",
            "- 样本聚焦于政策/宏观/行业新闻等更容易误关联的事件。",
            f"- 抽样明细见: `{sample_path}`",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote link quality report to {report_path}")
    print(f"Wrote link quality sample to {sample_path}")


if __name__ == "__main__":
    main()
