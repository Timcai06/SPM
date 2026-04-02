#!/usr/bin/env python3
"""Task 1 collector entrypoint: source plugins -> normalized CSVs."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Callable

from collectors import caixin, cninfo, csrc, eastmoney, gov, kr36, ndrc, sse, szse, yicai
from collectors.catalog import write_source_catalog


ROOT = Path(__file__).resolve().parent.parent
MANUAL_TEMPLATE = ROOT / "data" / "manual_news.csv"
SOURCE_CATALOG = ROOT / "data" / "appendix2_sources.csv"


def ensure_manual_template() -> None:
    if MANUAL_TEMPLATE.exists():
        return
    with MANUAL_TEMPLATE.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["source", "title", "content", "publish_time", "url", "symbol_or_subject"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "source": "手工录入",
                "title": "请删除本行后再录入正式事件",
                "content": "把正文粘贴到这里。这个占位行会被程序自动忽略。",
                "publish_time": "2026-04-02 00:00:00",
                "url": "local://manual-seed",
                "symbol_or_subject": "自定义主题",
            }
        )


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["source", "title", "content", "publish_time", "url", "symbol_or_subject"],
        )
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect live Task 1 source data.")
    parser.add_argument("--limit", type=int, default=10, help="Max rows to fetch per source.")
    parser.add_argument("--include-non-keyword", action="store_true", help="Disable gov title keyword prefilter.")
    parser.add_argument("--gov-output", default=str(ROOT / "data" / "source_gov.csv"))
    parser.add_argument("--ndrc-output", default=str(ROOT / "data" / "source_ndrc.csv"))
    parser.add_argument("--csrc-output", default=str(ROOT / "data" / "source_csrc.csv"))
    parser.add_argument("--sse-output", default=str(ROOT / "data" / "source_sse.csv"))
    parser.add_argument("--cninfo-output", default=str(ROOT / "data" / "source_cninfo.csv"))
    parser.add_argument("--szse-output", default=str(ROOT / "data" / "source_szse.csv"))
    parser.add_argument("--yicai-output", default=str(ROOT / "data" / "source_yicai.csv"))
    parser.add_argument("--eastmoney-output", default=str(ROOT / "data" / "source_eastmoney.csv"))
    parser.add_argument("--kr36-output", default=str(ROOT / "data" / "source_36kr.csv"))
    parser.add_argument("--caixin-output", default=str(ROOT / "data" / "source_caixin.csv"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_manual_template()
    write_source_catalog(SOURCE_CATALOG)

    jobs: list[tuple[str, Path, Callable[[], list[dict[str, str]]]]] = [
        ("government", Path(args.gov_output).resolve(), lambda: gov.collect(limit=args.limit, include_non_keyword=args.include_non_keyword)),
        ("ndrc", Path(args.ndrc_output).resolve(), lambda: ndrc.collect(limit=args.limit)),
        ("csrc", Path(args.csrc_output).resolve(), lambda: csrc.collect(limit=args.limit)),
        ("sse", Path(args.sse_output).resolve(), lambda: sse.collect(limit=args.limit)),
        ("cninfo", Path(args.cninfo_output).resolve(), lambda: cninfo.collect(limit=args.limit)),
        ("szse", Path(args.szse_output).resolve(), lambda: szse.collect(limit=args.limit)),
        ("yicai", Path(args.yicai_output).resolve(), lambda: yicai.collect(limit=args.limit)),
        ("eastmoney", Path(args.eastmoney_output).resolve(), lambda: eastmoney.collect(limit=args.limit)),
        ("36kr", Path(args.kr36_output).resolve(), lambda: kr36.collect(limit=args.limit)),
        ("caixin", Path(args.caixin_output).resolve(), lambda: caixin.collect(limit=args.limit)),
    ]

    for name, out_path, run in jobs:
        try:
            rows = run()
        except Exception as exc:
            rows = []
            print(f"[WARN] collector failed: {name}: {exc}")
        write_csv(out_path, rows)
        print(f"Wrote {len(rows)} live {name} rows to {out_path}")

    print(f"Wrote appendix 2 source catalog to {SOURCE_CATALOG}")
    print(f"Manual import template available at {MANUAL_TEMPLATE}")


if __name__ == "__main__":
    main()
