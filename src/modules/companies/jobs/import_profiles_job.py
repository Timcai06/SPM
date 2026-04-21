#!/usr/bin/env python3
"""Import company profile seed rows from AKShare public endpoints."""

from __future__ import annotations

from pathlib import Path
import sys

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from modules.companies.services.company_seed_service import run_import_profiles


def main(argv: list[str] | None = None) -> None:
    run_import_profiles(argv)


if __name__ == "__main__":
    main()
