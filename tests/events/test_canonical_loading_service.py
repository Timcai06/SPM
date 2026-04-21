from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from modules.events.services import canonical_loading_service


class CanonicalLoadingServiceTests(unittest.TestCase):
    @patch("modules.events.services.canonical_loading_service.run_loading_pipeline")
    @patch("modules.events.services.canonical_loading_service.read_csv_rows")
    def test_load_canonical_rows_reads_explicit_paths(
        self,
        mock_read_csv_rows: MagicMock,
        mock_run_loading_pipeline: MagicMock,
    ) -> None:
        mock_read_csv_rows.side_effect = [
            [{"canonical_event_id": "c1"}],
            [{"event_id": "e1", "canonical_event_id": "c1"}],
        ]

        canonical_loading_service.load_canonical_rows(
            db="stock_event_mining",
            canonical_events_path="output/canonical_events.csv",
            canonical_map_path="output/event_canonical_map.csv",
            quiet=True,
        )

        self.assertEqual(mock_read_csv_rows.call_count, 2)
        mock_run_loading_pipeline.assert_called_once_with(
            db="stock_event_mining",
            canonical_event_rows=[{"canonical_event_id": "c1"}],
            canonical_link_rows=[{"event_id": "e1", "canonical_event_id": "c1"}],
            lock_timeout_sec=120,
            quiet=True,
        )


if __name__ == "__main__":
    unittest.main()
