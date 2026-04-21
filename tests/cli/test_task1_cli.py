from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cli import task1
from cli.task1_parser import build_parser


class Task1CliTests(unittest.TestCase):
    def test_parser_supports_backfill_command_defaults(self) -> None:
        parser = build_parser()

        args = parser.parse_args(["backfill-cninfo-fulltext"])

        self.assertEqual(args.command, "backfill-cninfo-fulltext")
        self.assertEqual(args.source, "巨潮资讯网/历史公告")
        self.assertEqual(args.db_flush_every, 100)
        self.assertEqual(args.workers, 8)

    def test_parser_supports_delivery_status_command(self) -> None:
        parser = build_parser()

        args = parser.parse_args(["delivery-status", "--db", "stock_event_mining"])

        self.assertEqual(args.command, "delivery-status")
        self.assertEqual(args.db, "stock_event_mining")

    @patch.dict("cli.task1.COMMAND_HANDLERS", {"db-status": MagicMock()})
    @patch("cli.task1.parse_args")
    def test_main_dispatches_via_command_handlers(self, mock_parse_args: MagicMock) -> None:
        args = MagicMock()
        args.command = "db-status"
        mock_parse_args.return_value = args

        task1.main()

        task1.COMMAND_HANDLERS["db-status"].assert_called_once_with(args)

    @patch("cli.task1.load_canonical_rows")
    def test_canonical_load_handler_passes_paths(self, mock_load_canonical_rows: MagicMock) -> None:
        args = MagicMock()
        args.db = "stock_event_mining"
        args.canonical_events = "output/canonical_events.csv"
        args.canonical_map = "output/event_canonical_map.csv"

        task1.run_canonical_load_command(args)

        mock_load_canonical_rows.assert_called_once_with(
            db="stock_event_mining",
            canonical_event_rows=None,
            canonical_link_rows=None,
            canonical_events_path="output/canonical_events.csv",
            canonical_map_path="output/event_canonical_map.csv",
            quiet=False,
        )

    @patch("cli.task1.collect_job.main")
    def test_collect_handler_calls_job_with_explicit_argv(self, mock_collect_main: MagicMock) -> None:
        args = MagicMock()
        args.limit = 12
        args.include_non_keyword = True

        task1.run_collect_command(args)

        mock_collect_main.assert_called_once_with(["--limit", "12", "--include-non-keyword"])

    @patch("cli.task1.delivery_status_job.main")
    def test_delivery_status_handler_calls_job_with_explicit_argv(self, mock_delivery_main: MagicMock) -> None:
        args = MagicMock()
        args.db = "stock_event_mining"
        args.output = "report/out.md"
        args.fail_on_blockers = True

        task1.run_delivery_status_command(args)

        mock_delivery_main.assert_called_once_with(
            ["--db", "stock_event_mining", "--output", "report/out.md", "--fail-on-blockers"]
        )

    @patch("cli.task1.feature_return_job.main")
    def test_feature_handler_calls_job_with_explicit_argv(self, mock_feature_main: MagicMock) -> None:
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
        args.dataset_path = "output/task1_event_return_dataset.csv"
        args.report_path = "output/task1_feature_return_report.md"
        args.tushare_token = ""
        args.tushare_token_file = ""
        args.disable_tushare = False
        args.disable_cache = False
        args.run_id = ""

        task1.run_feature_command(args)

        mock_feature_main.assert_called_once()
        argv = mock_feature_main.call_args.args[0]
        self.assertIn("--db", argv)
        self.assertIn("stock_event_mining", argv)
        self.assertNotIn("feature_return.py", argv)

    @patch("cli.task1.train_samples_job.main")
    def test_train_samples_handler_calls_job_with_explicit_argv(self, mock_train_main: MagicMock) -> None:
        args = MagicMock()
        args.db = "stock_event_mining"
        args.min_link_score = 0.35
        args.label_dataset = "output/task1_event_return_dataset.csv"
        args.run_id = ""

        task1.run_train_samples_command(args)

        mock_train_main.assert_called_once_with(
            [
                "--db",
                "stock_event_mining",
                "--min-link-score",
                "0.35",
                "--label-dataset",
                "output/task1_event_return_dataset.csv",
            ]
        )

    @patch("cli.task1.check_job.main")
    def test_check_handler_calls_job_without_patched_argv(self, mock_check_main: MagicMock) -> None:
        task1.run_check_command(MagicMock())
        mock_check_main.assert_called_once_with([])

    @patch("cli.task1.canonicalize_job.main")
    def test_canonicalize_handler_calls_job_without_patched_argv(self, mock_canonicalize_main: MagicMock) -> None:
        task1.run_canonicalize_command(MagicMock())
        mock_canonicalize_main.assert_called_once_with([])

    @patch("cli.task1.task1_pipeline.main")
    def test_run_handler_calls_pipeline_with_explicit_argv(self, mock_pipeline_main: MagicMock) -> None:
        args = MagicMock()
        args.limit = 8
        args.db = "stock_event_mining"
        args.skip_collect = True
        args.skip_validate = False
        args.with_analysis = True
        args.analysis_mode = "event-study"
        args.benchmark = "hs300"
        args.event_windows = "1,3,5"
        args.time_budget_sec = 300
        args.max_analysis_rows = 300
        args.api_timeout_sec = 20.0
        args.progress_every = 10
        args.use_llm = True
        args.llm_max_rows = 20

        task1.run_pipeline_command(args)

        mock_pipeline_main.assert_called_once()
        argv = mock_pipeline_main.call_args.args[0]
        self.assertEqual(argv[:4], ["--limit", "8", "--db", "stock_event_mining"])
        self.assertIn("--skip-collect", argv)
        self.assertIn("--with-analysis", argv)
        self.assertIn("--use-llm", argv)
        self.assertNotIn("task1.py", argv)


if __name__ == "__main__":
    unittest.main()
