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


class Task1CliTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
