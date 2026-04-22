#!/usr/bin/env python3
"""Research sample generation workflows."""

from __future__ import annotations

from modules.analysis.services.control_sample_service import main as run_control_sample_builder
from modules.analysis.services.event_sample_service import main as run_event_sample_builder


def run_train_samples(argv: list[str] | None = None) -> None:
    run_event_sample_builder(argv)


def run_negative_samples(argv: list[str] | None = None) -> None:
    run_control_sample_builder(argv)
