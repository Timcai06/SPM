from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cli import task3
from cli.task3_parser import build_parser


class Task3CliTests(unittest.TestCase):
    def test_parser_supports_propagate_defaults(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["propagate"])
        self.assertEqual(args.command, "propagate")
        self.assertEqual(args.min_source_score, 0.35)
        self.assertEqual(args.min_propagation_score, 0.20)

    @patch.dict("cli.task3.COMMAND_HANDLERS", {"run": MagicMock()})
    @patch("cli.task3.parse_args")
    def test_main_dispatches_via_command_handlers(self, mock_parse_args: MagicMock) -> None:
        args = MagicMock()
        args.command = "run"
        mock_parse_args.return_value = args

        task3.main()

        task3.COMMAND_HANDLERS["run"].assert_called_once_with(args)

    @patch("cli.task3.task3_pipeline.main")
    def test_run_handler_calls_pipeline_with_explicit_argv(self, mock_pipeline_main: MagicMock) -> None:
        args = MagicMock()
        args.db = "stock_event_mining"
        args.input = "output/seeds/company_relations_seed.csv"
        args.min_source_score = 0.35
        args.min_propagation_score = 0.20
        args.canonical_map = "output/event_canonical_map.csv"

        task3.run_pipeline_command(args)

        mock_pipeline_main.assert_called_once_with(
            [
                "--db",
                "stock_event_mining",
                "--input",
                "output/seeds/company_relations_seed.csv",
                "--min-source-score",
                "0.35",
                "--min-propagation-score",
                "0.2",
                "--canonical-map",
                "output/event_canonical_map.csv",
            ]
        )

    @patch("cli.task3.propagate_links_job.main")
    def test_propagate_handler_calls_job_with_explicit_argv(self, mock_propagate_main: MagicMock) -> None:
        args = MagicMock()
        args.db = "stock_event_mining"
        args.min_source_score = 0.5
        args.min_propagation_score = 0.3
        args.canonical_map = "output/event_canonical_map.csv"

        task3.run_propagate_command(args)

        mock_propagate_main.assert_called_once_with(
            [
                "--db",
                "stock_event_mining",
                "--min-source-score",
                "0.5",
                "--min-propagation-score",
                "0.3",
                "--canonical-map",
                "output/event_canonical_map.csv",
            ]
        )

    @patch("cli.task3.load_relations_job.main")
    def test_load_relations_handler_calls_job_with_explicit_argv(self, mock_load_relations: MagicMock) -> None:
        args = MagicMock()
        args.db = "stock_event_mining"
        args.input = "output/seeds/company_relations_seed.csv"

        task3.run_load_relations_command(args)

        mock_load_relations.assert_called_once_with(
            ["--db", "stock_event_mining", "--input", "output/seeds/company_relations_seed.csv"]
        )


if __name__ == "__main__":
    unittest.main()
