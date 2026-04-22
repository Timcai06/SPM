#!/usr/bin/env python3
"""Company universe seed and load workflows."""

from __future__ import annotations

from modules.companies.adapters.company_universe_adapter import (
    import_companies_public,
    import_companies_tushare,
    load_companies,
)


def run_load_companies(argv: list[str] | None = None) -> None:
    load_companies(argv)


def run_import_companies_public(argv: list[str] | None = None) -> None:
    import_companies_public(argv)


def run_import_companies_tushare(argv: list[str] | None = None) -> None:
    import_companies_tushare(argv)
