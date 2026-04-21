from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from modules.collectors.adapters import db_repository


class CollectorDbRepositoryTests(unittest.TestCase):
    @patch("modules.collectors.adapters.db_repository.upsert_raw_documents")
    def test_upsert_raw_document_rows_delegates_to_legacy_writer(self, mock_upsert: MagicMock) -> None:
        rows = [{"url": "u1", "title": "t1", "content": "c1", "publish_time": "2025-01-01 00:00:00", "source": "s", "symbol_or_subject": ""}]
        written = db_repository.upsert_raw_document_rows("stock_event_mining", rows)
        self.assertEqual(written, 1)
        mock_upsert.assert_called_once_with("stock_event_mining", rows)

    @patch("modules.collectors.adapters.db_repository.dsn_for", return_value="dsn")
    @patch("modules.collectors.adapters.db_repository.psycopg.connect")
    def test_update_raw_document_contents_executes_batch_update(
        self,
        mock_connect: MagicMock,
        _mock_dsn_for: MagicMock,
    ) -> None:
        cursor = MagicMock()
        conn = MagicMock()
        mock_connect.return_value.__enter__.return_value = conn
        conn.cursor.return_value.__enter__.return_value = cursor

        updates = [{"id": "1", "content": "正文", "content_hash": "abc"}]
        written = db_repository.update_raw_document_contents("stock_event_mining", updates)

        self.assertEqual(written, 1)
        cursor.executemany.assert_called_once()
        conn.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
