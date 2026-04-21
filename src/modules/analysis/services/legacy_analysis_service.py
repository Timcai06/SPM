#!/usr/bin/env python3
"""Bridges from module jobs to legacy analysis implementations."""

from __future__ import annotations

import sys
from contextlib import contextmanager

from capabilities.analysis import build_model_samples as legacy_build_model_samples
from capabilities.analysis import feature_return as legacy_feature_return


@contextmanager
def patched_argv(argv: list[str] | None):
    if argv is None:
        yield
        return
    old = sys.argv[:]
    sys.argv = [old[0], *argv]
    try:
        yield
    finally:
        sys.argv = old


def run_feature_return(argv: list[str] | None = None) -> None:
    with patched_argv(argv):
        legacy_feature_return.main()


def run_train_samples(argv: list[str] | None = None) -> None:
    with patched_argv(argv):
        legacy_build_model_samples.main()
