#!/usr/bin/env python3
"""Bridge service for research sample generation workflows."""

from __future__ import annotations

from capabilities.analysis import build_negative_samples as legacy_build_negative_samples
from capabilities.analysis import build_model_samples as legacy_build_model_samples


def run_train_samples(argv: list[str] | None = None) -> None:
    legacy_build_model_samples.main(argv)


def run_negative_samples(argv: list[str] | None = None) -> None:
    legacy_build_negative_samples.main(argv)
