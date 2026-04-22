#!/usr/bin/env python3
"""Parser helpers for graph and propagation commands."""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Graph-relation and propagation entrypoint.")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="load graph edges and build propagation links")
    run_parser.add_argument("--db", default="stock_event_mining")
    run_parser.add_argument("--input", default="output/seeds/company_relations_seed.csv")
    run_parser.add_argument("--min-source-score", type=float, default=0.35)
    run_parser.add_argument("--min-propagation-score", type=float, default=0.20)
    run_parser.add_argument("--canonical-map", default="output/event_canonical_map.csv")

    load_parser = sub.add_parser("load-relations", help="load company graph edges")
    load_parser.add_argument("--db", default="stock_event_mining")
    load_parser.add_argument("--input", default="output/seeds/company_relations_seed.csv")

    propagate_parser = sub.add_parser("propagate", help="build one-hop propagated event links")
    propagate_parser.add_argument("--db", default="stock_event_mining")
    propagate_parser.add_argument("--min-source-score", type=float, default=0.35)
    propagate_parser.add_argument("--min-propagation-score", type=float, default=0.20)
    propagate_parser.add_argument("--canonical-map", default="output/event_canonical_map.csv")
    return parser
