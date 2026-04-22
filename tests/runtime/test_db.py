from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from modules.runtime.adapters.db import dsn_for


class RuntimeDbTests(unittest.TestCase):
    def test_dsn_for_prefers_explicit_stock_event_mining_dsn(self) -> None:
        env = {
            "STOCK_EVENT_MINING_DSN": "postgresql://collector_runner:secret@192.168.43.14:5432/stock_event_mining"
        }
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(dsn_for("ignored_db"), env["STOCK_EVENT_MINING_DSN"])

    def test_dsn_for_builds_from_pg_environment(self) -> None:
        env = {
            "PGHOST": "192.168.43.14",
            "PGPORT": "5432",
            "PGUSER": "collector_runner",
            "PGPASSWORD": "strong-password",
            "PGDATABASE": "other_db",
        }
        with patch.dict(os.environ, env, clear=True):
            dsn = dsn_for("stock_event_mining")

        self.assertIn("dbname=stock_event_mining", dsn)
        self.assertIn("host=192.168.43.14", dsn)
        self.assertIn("port=5432", dsn)
        self.assertIn("user=collector_runner", dsn)
        self.assertIn("password=strong-password", dsn)

    def test_dsn_for_falls_back_to_local_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            dsn = dsn_for("stock_event_mining")

        self.assertIn("dbname=stock_event_mining", dsn)
        self.assertIn("host=127.0.0.1", dsn)
        self.assertIn("port=5432", dsn)
        self.assertIn("user=tim", dsn)


if __name__ == "__main__":
    unittest.main()
