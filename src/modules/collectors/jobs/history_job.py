#!/usr/bin/env python3
"""Task 1 historical collector job."""

from __future__ import annotations

from pathlib import Path
import sys

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from modules.collectors.services import history_collect_service


def main() -> None:
    history_collect_service.main()


if __name__ == "__main__":
    main()

