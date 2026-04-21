#!/usr/bin/env python3
"""Build negative samples job."""

from __future__ import annotations

from pathlib import Path
import sys

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.analysis import build_negative_samples as legacy_build_negative_samples


def main(argv: list[str] | None = None) -> None:
    legacy_build_negative_samples.main(argv)


if __name__ == "__main__":
    main()
