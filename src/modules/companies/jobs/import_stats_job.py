#!/usr/bin/env python3
"""Import company stats from the configured source."""

from __future__ import annotations

from pathlib import Path
import sys

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.storage import (
    import_company_stats_akshare as legacy_akshare,
    import_company_stats_sina as legacy_sina,
    import_company_stats_tushare as legacy_tushare,
)


def run_sina(argv: list[str] | None = None) -> None:
    legacy_sina.main(argv)


def run_tushare(argv: list[str] | None = None) -> None:
    legacy_tushare.main(argv)


def run_akshare(argv: list[str] | None = None) -> None:
    legacy_akshare.main(argv)
