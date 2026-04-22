#!/usr/bin/env python3
"""Bridge service for company stats import and load workflows."""

from __future__ import annotations

from capabilities.storage import (
    import_company_stats_akshare as legacy_import_stats_akshare,
    import_company_stats_local as legacy_import_stats_local,
    import_company_stats_sina as legacy_import_stats_sina,
    import_company_stats_tushare as legacy_import_stats_tushare,
    load_company_stats as legacy_load_company_stats,
)


def run_import_stats_sina(argv: list[str] | None = None) -> None:
    legacy_import_stats_sina.main(argv)


def run_import_stats_tushare(argv: list[str] | None = None) -> None:
    legacy_import_stats_tushare.main(argv)


def run_import_stats_akshare(argv: list[str] | None = None) -> None:
    legacy_import_stats_akshare.main(argv)


def run_import_stats_local(argv: list[str] | None = None) -> None:
    legacy_import_stats_local.main(argv)


def run_load_stats(argv: list[str] | None = None) -> None:
    legacy_load_company_stats.main(argv)
