#!/usr/bin/env python3
"""Feature-return analysis workflows."""

from __future__ import annotations

from modules.analysis.adapters.feature_return_adapter import run_feature_return as run_feature_return_adapter


def run_feature_return(argv: list[str] | None = None) -> None:
    run_feature_return_adapter(argv)
