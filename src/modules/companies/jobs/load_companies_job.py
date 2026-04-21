#!/usr/bin/env python3
"""Load company seed rows into PostgreSQL."""

from __future__ import annotations

from pathlib import Path
import sys

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from modules.companies.services.company_seed_service import run_load_companies


def main(argv: list[str] | None = None) -> None:
    run_load_companies(argv)


if __name__ == "__main__":
    main()
