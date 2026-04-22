#!/usr/bin/env python3
"""Company stats import and load workflows."""

from __future__ import annotations

from modules.companies.adapters.company_stats_adapter import (
    import_stats_akshare,
    import_stats_local,
    import_stats_sina,
    import_stats_tushare,
    load_stats,
)


def run_import_stats_sina(argv: list[str] | None = None) -> None:
    import_stats_sina(argv)


def run_import_stats_tushare(argv: list[str] | None = None) -> None:
    import_stats_tushare(argv)


def run_import_stats_akshare(argv: list[str] | None = None) -> None:
    import_stats_akshare(argv)


def run_import_stats_local(argv: list[str] | None = None) -> None:
    import_stats_local(argv)


def run_load_stats(argv: list[str] | None = None) -> None:
    load_stats(argv)
