from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pipelines import graph as graph_pipeline


class GraphPipelineTests(unittest.TestCase):
    @patch("pipelines.graph.logged_step")
    @patch("pipelines.graph.propagate_links_job.main")
    @patch("pipelines.graph.load_relations_job.main")
    def test_main_loads_relations_then_propagates(
        self,
        mock_load_relations: MagicMock,
        mock_propagate: MagicMock,
        mock_logged_step: MagicMock,
    ) -> None:
        mock_logged_step.return_value.__enter__.return_value = None
        graph_pipeline.main(
            [
                "--db",
                "stock_event_mining",
                "--input",
                "output/seeds/company_relations_seed.csv",
                "--min-source-score",
                "0.5",
                "--min-propagation-score",
                "0.3",
                "--canonical-map",
                "output/event_canonical_map.csv",
                "--run-id",
                "graph_pipeline_run_1",
            ]
        )

        mock_load_relations.assert_called_once_with(
            ["--db", "stock_event_mining", "--input", "output/seeds/company_relations_seed.csv"]
        )
        mock_propagate.assert_called_once_with(
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


if __name__ == "__main__":
    unittest.main()
