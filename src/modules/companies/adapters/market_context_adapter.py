#!/usr/bin/env python3
"""Legacy adapter for market context loading workflows."""

from __future__ import annotations

from capabilities.storage import (
    load_market_environment as legacy_load_market_environment,
    load_sentiment_propagation as legacy_load_sentiment_propagation,
)


def load_market_environment(argv: list[str] | None = None) -> None:
    legacy_load_market_environment.main(argv)


def load_sentiment_propagation(argv: list[str] | None = None) -> None:
    legacy_load_sentiment_propagation.main(argv)
