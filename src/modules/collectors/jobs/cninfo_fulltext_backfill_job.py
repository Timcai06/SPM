#!/usr/bin/env python3
"""Job entrypoint for CNInfo fulltext backfill."""

from __future__ import annotations

from modules.collectors.services import cninfo_fulltext_backfill_service


def main() -> None:
    cninfo_fulltext_backfill_service.main()


if __name__ == "__main__":
    main()
