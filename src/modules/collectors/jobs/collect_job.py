#!/usr/bin/env python3
"""Task 1 live collector job."""

from __future__ import annotations

from pathlib import Path
import sys

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from modules.collectors.services import collect_service


def main(argv: list[str] | None = None) -> None:
    collect_service.main(argv)


if __name__ == "__main__":
    main()
