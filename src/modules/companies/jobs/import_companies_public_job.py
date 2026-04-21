#!/usr/bin/env python3
"""Build public company seed CSV from collected sources."""

from __future__ import annotations

from pathlib import Path
import sys

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.storage import import_companies_public as legacy_import_companies_public


def main(argv: list[str] | None = None) -> None:
    legacy_import_companies_public.main(argv)


if __name__ == "__main__":
    main()
