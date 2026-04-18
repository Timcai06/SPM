#!/usr/bin/env python3
"""Build model-ready samples job."""

from __future__ import annotations

from pathlib import Path
import sys

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.analysis import build_model_samples as legacy_build_model_samples


def main() -> None:
    legacy_build_model_samples.main()


if __name__ == "__main__":
    main()

