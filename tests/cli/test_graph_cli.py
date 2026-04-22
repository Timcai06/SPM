from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cli import graph
from cli.graph_parser import build_parser


class GraphCliTests(unittest.TestCase):
    def test_parser_supports_propagate_defaults(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["propagate"])
        self.assertEqual(args.command, "propagate")
        self.assertEqual(args.min_source_score, 0.35)
        self.assertEqual(args.min_propagation_score, 0.20)

    @patch.dict("cli.graph.COMMAND_HANDLERS", {"run": MagicMock()})
    @patch("cli.graph.parse_args")
    def test_main_dispatches_via_command_handlers(self, mock_parse_args: MagicMock) -> None:
        args = MagicMock()
        args.command = "run"
        mock_parse_args.return_value = args

        graph.main()

        graph.COMMAND_HANDLERS["run"].assert_called_once_with(args)

    @patch("cli.graph.logged_run")
    @patch("cli.graph.graph_pipeline.main")
    def test_run_handler_calls_pipeline_with_explicit_argv(self, mock_pipeline_main: MagicMock, mock_logged_run: MagicMock) -> None:
        mock_logged_run.return_value.__enter__.return_value = "graph_run_1"
        args = MagicMock()
        args.db = "stock_event_mining"
        args.input = "output/seeds/company_relations_seed.csv"
        args.min_source_score = 0.35
        args.min_propagation_score = 0.20
        args.canonical_map = "output/event_canonical_map.csv"

        graph.run_pipeline_command(args)

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
                "--run-id",
                "graph_run_1",
            ]
        )

    @patch("cli.graph.logged_run")
    @patch("cli.graph.propagate_links_job.main")
    def test_propagate_handler_calls_job_with_explicit_argv(self, mock_propagate_main: MagicMock, mock_logged_run: MagicMock) -> None:
        mock_logged_run.return_value.__enter__.return_value = "graph_run_2"
        args = MagicMock()
        args.db = "stock_event_mining"
        args.min_source_score = 0.5
        args.min_propagation_score = 0.3
        args.canonical_map = "output/event_canonical_map.csv"

        graph.run_propagate_command(args)

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

    @patch("cli.graph.logged_run")
    @patch("cli.graph.load_relations_job.main")
    def test_load_relations_handler_calls_job_with_explicit_argv(self, mock_load_relations: MagicMock, mock_logged_run: MagicMock) -> None:
        mock_logged_run.return_value.__enter__.return_value = "graph_run_3"
        args = MagicMock()
        args.db = "stock_event_mining"
        args.input = "output/seeds/company_relations_seed.csv"

        graph.run_load_relations_command(args)

        mock_load_relations.assert_called_once_with(
            ["--db", "stock_event_mining", "--input", "output/seeds/company_relations_seed.csv"]
        )


if __name__ == "__main__":
    unittest.main()
