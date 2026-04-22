from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pipelines import events as events_pipeline


class EventsPipelineTests(unittest.TestCase):
    @patch("pipelines.events.logged_step")
    @patch("pipelines.events.analysis_main")
    @patch("pipelines.events.run_validation_pipeline", return_value=True)
    @patch("pipelines.events.load_canonical_rows")
    @patch("pipelines.events.run_canonicalization_pipeline")
    @patch("pipelines.events.run_classification_pipeline", new_callable=AsyncMock)
    @patch("pipelines.events.upsert_raw_document_rows")
    @patch("pipelines.events.collect_all_async", new_callable=AsyncMock)
    def test_pipeline_main_uses_explicit_analysis_argv(
        self,
        mock_collect_all_async: AsyncMock,
        mock_upsert_raw_document_rows: MagicMock,
        mock_run_classification_pipeline: AsyncMock,
        mock_run_canonicalization_pipeline: MagicMock,
        mock_load_canonical_rows: MagicMock,
        mock_run_validation_pipeline: MagicMock,
        mock_analysis_main: MagicMock,
        mock_logged_step: MagicMock,
    ) -> None:
        mock_logged_step.return_value.__enter__.return_value = None
        mock_collect_all_async.return_value = []
        mock_run_classification_pipeline.return_value = ([], [])
        mock_run_canonicalization_pipeline.return_value = ([], [])

        events_pipeline.main(
            [
                "--db",
                "stock_event_mining",
                "--skip-collect",
                "--with-analysis",
                "--run-id",
                "events_pipeline_run_1",
                "--analysis-mode",
                "event-study",
                "--benchmark",
                "hs300",
            ]
        )

        mock_upsert_raw_document_rows.assert_not_called()
        mock_load_canonical_rows.assert_called_once()
        mock_run_validation_pipeline.assert_called_once()
        mock_analysis_main.assert_called_once()
        argv = mock_analysis_main.call_args.args[0]
        self.assertIn("--db", argv)
        self.assertIn("stock_event_mining", argv)
        self.assertIn("--benchmark", argv)
        self.assertIn("--run-id", argv)
        self.assertIn("events_pipeline_run_1", argv)


if __name__ == "__main__":
    unittest.main()
