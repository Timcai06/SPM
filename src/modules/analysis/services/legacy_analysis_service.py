#!/usr/bin/env python3
"""Bridges from module jobs to legacy analysis implementations."""

from __future__ import annotations

from capabilities.analysis import build_model_samples as legacy_build_model_samples
from capabilities.analysis import feature_return as legacy_feature_return


def run_feature_return() -> None:
    legacy_feature_return.main()


def run_train_samples() -> None:
    legacy_build_model_samples.main()
