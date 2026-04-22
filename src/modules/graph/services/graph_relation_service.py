"""Graph relation workflows."""

from __future__ import annotations

from modules.graph.adapters.graph_relation_adapter import run_load_relations as run_load_relations_adapter


def run_load_relations(argv: list[str] | None = None) -> None:
    run_load_relations_adapter(argv)
