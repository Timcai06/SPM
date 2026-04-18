#!/usr/bin/env python3
"""Load company profiles snapshot into PostgreSQL."""

from __future__ import annotations

from pathlib import Path
import sys

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.storage import load_company_profiles as legacy_load_profiles


def main() -> None:
    legacy_load_profiles.main()


if __name__ == "__main__":
    main()

