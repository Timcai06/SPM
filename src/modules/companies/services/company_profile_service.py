#!/usr/bin/env python3
"""Bridge service for company profile import and load workflows."""

from __future__ import annotations

from capabilities.storage import (
    import_company_profiles_akshare as legacy_import_company_profiles,
    load_company_profiles as legacy_load_company_profiles,
)


def run_import_profiles(argv: list[str] | None = None) -> None:
    legacy_import_company_profiles.main(argv)


def run_load_profiles(argv: list[str] | None = None) -> None:
    legacy_load_company_profiles.main(argv)
