#!/usr/bin/env python3
"""Generate event-company links."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from modules.linking.services.link_events_service import run_linking

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DB = "stock_event_mining"
CANONICAL_MAP_PATH = ROOT / "output" / "event_canonical_map.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate minimal event-company links.")
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--min-score", type=float, default=0.35)
    parser.add_argument("--lock-timeout-sec", type=int, default=120)
    parser.add_argument("--canonical-map", default=str(CANONICAL_MAP_PATH))
    parser.add_argument("--progress-every", type=int, default=250)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    upserted, stale_deleted = run_linking(
        db=args.db,
        top_k=args.top_k,
        min_score=args.min_score,
        canonical_map_path=args.canonical_map,
        progress_every=args.progress_every,
        lock_timeout_sec=args.lock_timeout_sec,
    )
    print(f"Upserted {upserted} event-company links into {args.db}; deleted stale links: {stale_deleted}")


if __name__ == "__main__":
    main()

