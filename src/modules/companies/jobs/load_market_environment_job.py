#!/usr/bin/env python3
"""Load market environment daily rows into PostgreSQL."""

from __future__ import annotations

from pathlib import Path
import sys

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from modules.companies.services.company_metrics_service import run_load_market_environment


def main(argv: list[str] | None = None) -> None:
    run_load_market_environment(argv)


if __name__ == "__main__":
    main()
