"""Seed and profile workflows that still bridge to legacy company scripts."""

from __future__ import annotations

from capabilities.storage import (
    import_companies_public as legacy_import_companies_public,
    import_companies_tushare as legacy_import_companies_tushare,
    import_company_profiles_akshare as legacy_import_company_profiles,
    load_companies as legacy_load_companies,
    load_company_profiles as legacy_load_company_profiles,
)


def run_load_companies(argv: list[str] | None = None) -> None:
    legacy_load_companies.main(argv)


def run_import_companies_public(argv: list[str] | None = None) -> None:
    legacy_import_companies_public.main(argv)


def run_import_companies_tushare(argv: list[str] | None = None) -> None:
    legacy_import_companies_tushare.main(argv)


def run_import_profiles(argv: list[str] | None = None) -> None:
    legacy_import_company_profiles.main(argv)


def run_load_profiles(argv: list[str] | None = None) -> None:
    legacy_load_company_profiles.main(argv)
