#!/usr/bin/env python3
"""Job entrypoint for CNInfo fulltext backfill."""

from __future__ import annotations

from modules.collectors.services import cninfo_fulltext_backfill_service


def main(argv: list[str] | None = None) -> None:
    cninfo_fulltext_backfill_service.main(argv)


if __name__ == "__main__":
    main()
