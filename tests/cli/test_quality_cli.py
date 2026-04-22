from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cli import quality
from cli.quality_parser import build_parser


class QualityCliTests(unittest.TestCase):
    def test_parser_supports_delivery_status(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["delivery-status", "--db", "stock_event_mining"])
        self.assertEqual(args.command, "delivery-status")
        self.assertEqual(args.db, "stock_event_mining")

    @patch("cli.quality.check_job.main")
    def test_check_handler_calls_job(self, mock_check_main: MagicMock) -> None:
        quality.run_check_command(MagicMock())
        mock_check_main.assert_called_once_with([])

    @patch("cli.quality.logged_run")
    @patch("cli.quality.delivery_status_job.main")
    def test_delivery_status_handler_calls_job(self, mock_delivery_main: MagicMock, mock_logged_run: MagicMock) -> None:
        mock_logged_run.return_value.__enter__.return_value = "quality_run_1"
        args = MagicMock()
        args.db = "stock_event_mining"
        args.output = "report/out.md"
        args.fail_on_blockers = True

        quality.run_delivery_status_command(args)

        mock_delivery_main.assert_called_once_with(
            ["--db", "stock_event_mining", "--output", "report/out.md", "--fail-on-blockers"]
        )


if __name__ == "__main__":
    unittest.main()
