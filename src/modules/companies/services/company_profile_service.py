#!/usr/bin/env python3
"""Company profile import and load workflows."""

from __future__ import annotations

from modules.companies.adapters.company_profile_adapter import import_profiles, load_profiles


def run_import_profiles(argv: list[str] | None = None) -> None:
    import_profiles(argv)


def run_load_profiles(argv: list[str] | None = None) -> None:
    load_profiles(argv)
