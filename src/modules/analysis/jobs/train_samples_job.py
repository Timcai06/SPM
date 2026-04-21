#!/usr/bin/env python3
"""Build model-ready samples job."""

from __future__ import annotations

from pathlib import Path
import sys

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from modules.analysis.services.legacy_analysis_service import run_train_samples


def main(argv: list[str] | None = None) -> None:
    run_train_samples(argv)


if __name__ == "__main__":
    main()
