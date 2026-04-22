#!/usr/bin/env python3
"""Legacy adapter for feature-return analysis entrypoint."""

from __future__ import annotations

from capabilities.analysis import feature_return as legacy_feature_return


def run_feature_return(argv: list[str] | None = None) -> None:
    legacy_feature_return.main(argv)
