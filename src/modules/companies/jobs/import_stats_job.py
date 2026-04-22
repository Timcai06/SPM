#!/usr/bin/env python3
"""Import company stats from the configured source."""

from __future__ import annotations

from pathlib import Path
import sys

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from modules.companies.services.company_stats_service import (
    run_import_stats_akshare,
    run_import_stats_sina,
    run_import_stats_tushare,
)


def run_sina(argv: list[str] | None = None) -> None:
    run_import_stats_sina(argv)


def run_tushare(argv: list[str] | None = None) -> None:
    run_import_stats_tushare(argv)


def run_akshare(argv: list[str] | None = None) -> None:
    run_import_stats_akshare(argv)
