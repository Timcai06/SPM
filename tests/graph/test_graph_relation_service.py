from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from modules.graph.services import graph_relation_service


class GraphRelationServiceTests(unittest.TestCase):
    @patch("modules.graph.services.graph_relation_service.run_load_relations_adapter")
    def test_run_load_relations_delegates_to_legacy(self, mock_main: MagicMock) -> None:
        graph_relation_service.run_load_relations(["--db", "stock_event_mining"])
        mock_main.assert_called_once_with(["--db", "stock_event_mining"])


if __name__ == "__main__":
    unittest.main()
