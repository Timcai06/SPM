#!/usr/bin/env python3
"""Market and sentiment context loading workflows."""

from __future__ import annotations

from modules.companies.adapters.market_context_adapter import load_market_environment, load_sentiment_propagation


def run_load_market_environment(argv: list[str] | None = None) -> None:
    load_market_environment(argv)


def run_load_sentiment_propagation(argv: list[str] | None = None) -> None:
    load_sentiment_propagation(argv)
