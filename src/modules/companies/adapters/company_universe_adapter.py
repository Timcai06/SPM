#!/usr/bin/env python3
"""Legacy adapter for company universe seed and load workflows."""

from __future__ import annotations

from capabilities.storage import (
    import_companies_public as legacy_import_companies_public,
    import_companies_tushare as legacy_import_companies_tushare,
    load_companies as legacy_load_companies,
)


def load_companies(argv: list[str] | None = None) -> None:
    legacy_load_companies.main(argv)


def import_companies_public(argv: list[str] | None = None) -> None:
    legacy_import_companies_public.main(argv)


def import_companies_tushare(argv: list[str] | None = None) -> None:
    legacy_import_companies_tushare.main(argv)
