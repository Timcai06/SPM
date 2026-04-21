from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pipelines import task1 as task1_pipeline


class Task1PipelineTests(unittest.TestCase):
    @patch("pipelines.task1.analysis_main")
    @patch("pipelines.task1.run_validation_pipeline", return_value=True)
    @patch("pipelines.task1.load_canonical_rows")
    @patch("pipelines.task1.run_canonicalization_pipeline")
    @patch("pipelines.task1.run_classification_pipeline", new_callable=AsyncMock)
    @patch("pipelines.task1.upsert_raw_document_rows")
    @patch("pipelines.task1.collect_all_async", new_callable=AsyncMock)
    def test_pipeline_main_uses_explicit_analysis_argv(
        self,
        mock_collect_all_async: AsyncMock,
        mock_upsert_raw_document_rows: MagicMock,
        mock_run_classification_pipeline: AsyncMock,
        mock_run_canonicalization_pipeline: MagicMock,
        mock_load_canonical_rows: MagicMock,
        mock_run_validation_pipeline: MagicMock,
        mock_analysis_main: MagicMock,
    ) -> None:
        mock_collect_all_async.return_value = []
        mock_run_classification_pipeline.return_value = ([], [])
        mock_run_canonicalization_pipeline.return_value = ([], [])

        task1_pipeline.main(
            [
                "--db",
                "stock_event_mining",
                "--skip-collect",
                "--with-analysis",
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
        self.assertNotIn("feature_return.py", argv)


if __name__ == "__main__":
    unittest.main()
