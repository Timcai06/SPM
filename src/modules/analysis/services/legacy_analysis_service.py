#!/usr/bin/env python3
"""Bridges from module jobs to legacy analysis implementations."""

from __future__ import annotations

from capabilities.analysis import build_model_samples as legacy_build_model_samples
from capabilities.analysis import feature_return as legacy_feature_return


def run_feature_return(argv: list[str] | None = None) -> None:
    legacy_feature_return.main(argv)


def run_train_samples(argv: list[str] | None = None) -> None:
    legacy_build_model_samples.main(argv)
