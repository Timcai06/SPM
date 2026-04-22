from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from modules.runtime.services.run_metadata_service import logged_run, register_output_artifact, resolve_run_id


class RunMetadataServiceTests(unittest.TestCase):
    def test_resolve_run_id_uses_explicit_value(self) -> None:
        self.assertEqual(resolve_run_id("manual_run"), "manual_run")

    @patch("modules.runtime.services.run_metadata_service.db_repository.finish_etl_run")
    @patch("modules.runtime.services.run_metadata_service.db_repository.start_etl_run")
    def test_logged_run_marks_success(self, mock_start, mock_finish) -> None:
        with logged_run(
            db_name="stock_event_mining",
            command_group="research",
            command_name="feature",
            argv=["--db", "stock_event_mining"],
            explicit_run_id="run_123",
        ) as run_id:
            self.assertEqual(run_id, "run_123")

        mock_start.assert_called_once()
        mock_finish.assert_called_once()
        self.assertEqual(mock_finish.call_args.kwargs["status"], "success")

    @patch("modules.runtime.services.run_metadata_service.db_repository.finish_etl_run")
    @patch("modules.runtime.services.run_metadata_service.db_repository.start_etl_run")
    def test_logged_run_marks_failure(self, mock_start, mock_finish) -> None:
        with self.assertRaisesRegex(RuntimeError, "boom"):
            with logged_run(
                db_name="stock_event_mining",
                command_group="research",
                command_name="feature",
                argv=["--db", "stock_event_mining"],
                explicit_run_id="run_456",
            ):
                raise RuntimeError("boom")

        mock_start.assert_called_once()
        mock_finish.assert_called_once()
        self.assertEqual(mock_finish.call_args.kwargs["status"], "failed")

    @patch("modules.runtime.services.run_metadata_service.db_repository.upsert_dataset_version")
    def test_register_output_artifact_records_csv_metadata(self, mock_upsert) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "dataset.csv"
            path.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
            created = register_output_artifact(
                db_name="stock_event_mining",
                run_id="run_789",
                dataset_key="research.feature.dataset",
                output_path=path,
            )

        self.assertTrue(created)
        mock_upsert.assert_called_once()
        self.assertEqual(mock_upsert.call_args.kwargs["row_count"], 2)
