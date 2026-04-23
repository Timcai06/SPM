from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cli import research
from cli.research_parser import build_parser


class ResearchCliTests(unittest.TestCase):
    def test_parser_supports_train_samples(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["train-samples"])
        self.assertEqual(args.command, "train-samples")
        self.assertEqual(args.min_link_score, 0.35)

    def test_parser_supports_train_alias(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["train"])
        self.assertEqual(args.command, "train")
        self.assertEqual(args.min_link_score, 0.35)

    def test_parser_supports_controls_alias(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["controls"])
        self.assertEqual(args.command, "controls")
        self.assertEqual(args.min_link_score, 0.35)

    @patch("cli.research.register_output_artifact")
    @patch("cli.research.logged_run")
    @patch("cli.research.feature_return_job.main")
    def test_feature_handler_calls_job(
        self,
        mock_feature_main: MagicMock,
        mock_logged_run: MagicMock,
        mock_register_output_artifact: MagicMock,
    ) -> None:
        mock_logged_run.return_value.__enter__.return_value = "run_feature_1"
        args = MagicMock()
        args.db = "stock_event_mining"
        args.min_link_score = 0.35
        args.analysis_mode = "event-study"
        args.benchmark = "hs300"
        args.event_windows = "1,3,5"
        args.time_budget_sec = 300
        args.max_rows = 300
        args.api_timeout_sec = 20.0
        args.progress_every = 10
        args.market_max_rows = 1200
        args.dataset_path = "output/event_return_dataset.csv"
        args.report_path = "output/feature_return_report.md"
        args.tushare_token = ""
        args.tushare_token_file = ""
        args.disable_tushare = False
        args.disable_cache = False
        args.run_id = ""

        research.run_feature_command(args)

        argv = mock_feature_main.call_args.args[0]
        self.assertIn("--db", argv)
        self.assertIn("stock_event_mining", argv)
        self.assertIn("--run-id", argv)
        self.assertIn("run_feature_1", argv)
        self.assertEqual(mock_register_output_artifact.call_count, 2)

    @patch("cli.research.logged_run")
    @patch("cli.research.train_samples_job.main")
    def test_train_samples_handler_calls_job(self, mock_train_main: MagicMock, mock_logged_run: MagicMock) -> None:
        mock_logged_run.return_value.__enter__.return_value = "run_train_1"
        args = MagicMock()
        args.db = "stock_event_mining"
        args.min_link_score = 0.35
        args.label_dataset = "output/event_return_dataset.csv"
        args.run_id = ""

        research.run_train_samples_command(args)

        mock_train_main.assert_called_once_with(
            [
                "--db",
                "stock_event_mining",
                "--min-link-score",
                "0.35",
                "--label-dataset",
                "output/event_return_dataset.csv",
                "--run-id",
                "run_train_1",
            ]
        )

    @patch("cli.research.logged_run")
    @patch("cli.research.negative_samples_job.main")
    def test_negative_samples_handler_calls_job(self, mock_negative_main: MagicMock, mock_logged_run: MagicMock) -> None:
        mock_logged_run.return_value.__enter__.return_value = "run_neg_1"
        args = MagicMock()
        args.db = "stock_event_mining"
        args.start_date = "2025-01-01"
        args.end_date = "2025-12-31"
        args.max_per_day = 50
        args.min_link_score = 0.35
        args.run_id = "run_1"

        research.run_negative_samples_command(args)

        mock_negative_main.assert_called_once_with(
            [
                "--db",
                "stock_event_mining",
                "--start-date",
                "2025-01-01",
                "--end-date",
                "2025-12-31",
                "--max-per-day",
                "50",
                "--min-link-score",
                "0.35",
                "--run-id",
                "run_neg_1",
            ]
        )


if __name__ == "__main__":
    unittest.main()
