#!/usr/bin/env python3
"""Feature return analysis job."""

from __future__ import annotations

from pathlib import Path
import sys

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from capabilities.analysis import feature_return as legacy_feature_return


def main() -> None:
    legacy_feature_return.main()


if __name__ == "__main__":
    main()

