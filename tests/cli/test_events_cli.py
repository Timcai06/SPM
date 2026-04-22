from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cli import events
from cli.events_parser import build_parser


class EventsCliTests(unittest.TestCase):
    def test_parser_supports_classify_pending(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["classify-pending"])
        self.assertEqual(args.command, "classify-pending")
        self.assertEqual(args.batch_size, 2000)

    @patch.dict("cli.events.COMMAND_HANDLERS", {"classify": MagicMock()})
    @patch("cli.events.parse_args")
    def test_main_dispatches_via_handlers(self, mock_parse_args: MagicMock) -> None:
        args = MagicMock()
        args.command = "classify"
        mock_parse_args.return_value = args

        events.main()

        events.COMMAND_HANDLERS["classify"].assert_called_once_with(args)

    @patch("cli.events.logged_run")
    @patch("cli.events.classify_job.main")
    @patch("cli.events.CLASSIFY_INPUT_FILES", ["output/sources/source_gov.csv"])
    @patch("pathlib.Path.exists", return_value=True)
    def test_classify_handler_discovers_inputs(
        self,
        _mock_exists: MagicMock,
        mock_classify_main: MagicMock,
        mock_logged_run: MagicMock,
    ) -> None:
        mock_logged_run.return_value.__enter__.return_value = "events_run_1"
        args = MagicMock()
        args.db = "stock_event_mining"
        args.skip_db_load = True
        args.use_llm = True
        args.llm_max_rows = 10

        events.run_classify_command(args)

        argv = mock_classify_main.call_args.args[0]
        self.assertIn("--input", argv)
        self.assertIn("output/sources/source_gov.csv", argv)
        self.assertIn("--skip-db-load", argv)
        self.assertIn("--use-llm", argv)

    @patch("cli.events.canonicalize_job.main")
    def test_canonicalize_handler_calls_job(self, mock_canonicalize_main: MagicMock) -> None:
        events.run_canonicalize_command(MagicMock())
        mock_canonicalize_main.assert_called_once_with([])

    @patch("cli.events.logged_run")
    @patch("cli.events.events_pipeline.main")
    def test_run_handler_calls_pipeline(self, mock_pipeline_main: MagicMock, mock_logged_run: MagicMock) -> None:
        mock_logged_run.return_value.__enter__.return_value = "events_run_2"
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

        events.run_pipeline_command(args)

        argv = mock_pipeline_main.call_args.args[0]
        self.assertIn("--with-analysis", argv)
        self.assertIn("--use-llm", argv)
        self.assertIn("--run-id", argv)
        self.assertIn("events_run_2", argv)


if __name__ == "__main__":
    unittest.main()
