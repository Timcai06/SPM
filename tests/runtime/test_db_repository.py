from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import psycopg


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from modules.runtime.adapters import db_repository


class RuntimeDbRepositoryTests(unittest.TestCase):
    def _mock_connection(self, cursor: MagicMock) -> MagicMock:
        conn = MagicMock()
        conn.__enter__.return_value = conn
        conn.__exit__.return_value = False
        conn.cursor.return_value.__enter__.return_value = cursor
        conn.cursor.return_value.__exit__.return_value = False
        return conn

    @patch("modules.runtime.adapters.db_repository.RUN_METADATA_SQL_PATH")
    @patch("modules.runtime.adapters.db_repository.psycopg.connect")
    def test_ensure_run_metadata_tables_skips_ddl_when_tables_exist(
        self, mock_connect: MagicMock, mock_sql_path: MagicMock
    ) -> None:
        mock_sql_path.read_text.return_value = "SELECT 1;"
        cursor = MagicMock()
        cursor.fetchone.return_value = (3,)
        mock_connect.return_value = self._mock_connection(cursor)

        db_repository.ensure_run_metadata_tables("stock_event_mining")

        self.assertEqual(cursor.execute.call_count, 1)
        self.assertIn("information_schema.tables", cursor.execute.call_args.args[0])
        mock_connect.return_value.commit.assert_not_called()

    @patch("modules.runtime.adapters.db_repository.RUN_METADATA_SQL_PATH")
    @patch("modules.runtime.adapters.db_repository.psycopg.connect")
    def test_ensure_run_metadata_tables_ignores_owner_errors_when_tables_already_exist(
        self, mock_connect: MagicMock, mock_sql_path: MagicMock
    ) -> None:
        mock_sql_path.read_text.return_value = "SELECT 1;"
        first_cursor = MagicMock()
        retry_cursor = MagicMock()
        first_cursor.fetchone.return_value = (2,)
        retry_cursor.fetchone.return_value = (3,)
        first_cursor.execute.side_effect = [
            None,
            psycopg.errors.InsufficientPrivilege("must be owner of table etl_runs"),
        ]
        conn = MagicMock()
        conn.__enter__.return_value = conn
        conn.__exit__.return_value = False
        conn.cursor.side_effect = [
            MagicMock(__enter__=MagicMock(return_value=first_cursor), __exit__=MagicMock(return_value=False)),
            MagicMock(__enter__=MagicMock(return_value=retry_cursor), __exit__=MagicMock(return_value=False)),
        ]
        mock_connect.return_value = conn

        db_repository.ensure_run_metadata_tables("stock_event_mining")

        conn.rollback.assert_called_once()
        conn.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
