"""Graph relation workflows that still bridge to legacy storage scripts."""

from __future__ import annotations

from capabilities.storage import load_task3_relations as legacy_load_task3_relations


def run_load_relations(argv: list[str] | None = None) -> None:
    legacy_load_task3_relations.main(argv)
