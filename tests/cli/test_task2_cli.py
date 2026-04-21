from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cli import task2
from cli.task2_parser import build_parser


class Task2CliTests(unittest.TestCase):
    def test_parser_supports_link_events_defaults(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["link-events"])
        self.assertEqual(args.command, "link-events")
        self.assertEqual(args.top_k, 3)
        self.assertEqual(args.min_score, 0.35)

    @patch.dict("cli.task2.COMMAND_HANDLERS", {"run": MagicMock()})
    @patch("cli.task2.parse_args")
    def test_main_dispatches_via_command_handlers(self, mock_parse_args: MagicMock) -> None:
        args = MagicMock()
        args.command = "run"
        mock_parse_args.return_value = args

        task2.main()

        task2.COMMAND_HANDLERS["run"].assert_called_once_with(args)

    @patch("cli.task2.task2_pipeline.main")
    def test_run_handler_calls_pipeline_with_explicit_argv(self, mock_pipeline_main: MagicMock) -> None:
        args = MagicMock()
        args.db = "stock_event_mining"
        args.top_k = 3
        args.min_score = 0.35
        args.canonical_map = "output/event_canonical_map.csv"

        task2.run_pipeline_command(args)

        mock_pipeline_main.assert_called_once_with(
            [
                "--db",
                "stock_event_mining",
                "--top-k",
                "3",
                "--min-score",
                "0.35",
                "--canonical-map",
                "output/event_canonical_map.csv",
            ]
        )

    @patch("cli.task2.relink_job.main")
    def test_link_events_handler_calls_job_with_explicit_argv(self, mock_relink_main: MagicMock) -> None:
        args = MagicMock()
        args.db = "stock_event_mining"
        args.top_k = 5
        args.min_score = 0.4
        args.canonical_map = "output/event_canonical_map.csv"
        args.progress_every = 200

        task2.run_link_events_command(args)

        mock_relink_main.assert_called_once_with(
            [
                "--db",
                "stock_event_mining",
                "--top-k",
                "5",
                "--min-score",
                "0.4",
                "--canonical-map",
                "output/event_canonical_map.csv",
                "--progress-every",
                "200",
            ]
        )


if __name__ == "__main__":
    unittest.main()
