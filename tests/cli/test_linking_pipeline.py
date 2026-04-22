from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pipelines import linking as linking_pipeline


class LinkingPipelineTests(unittest.TestCase):
    @patch("pipelines.linking.logged_step")
    @patch("pipelines.linking.relink_job.main")
    @patch("pipelines.linking.load_companies_job.main")
    def test_main_loads_seed_then_links(
        self,
        mock_load_companies: MagicMock,
        mock_relink: MagicMock,
        mock_logged_step: MagicMock,
    ) -> None:
        mock_logged_step.return_value.__enter__.return_value = None
        with tempfile.TemporaryDirectory() as tmpdir:
            seed_path = Path(tmpdir) / "companies_seed.csv"
            seed_path.write_text("ts_code,company_name\n000001.SZ,平安银行\n", encoding="utf-8")

            linking_pipeline.main(
                [
                    "--db",
                    "stock_event_mining",
                    "--input",
                    str(seed_path),
                    "--top-k",
                    "5",
                    "--min-score",
                    "0.4",
                    "--canonical-map",
                    "output/event_canonical_map.csv",
                    "--run-id",
                    "link_pipeline_run_1",
                ]
            )

        mock_load_companies.assert_called_once_with(
            ["--db", "stock_event_mining", "--input", str(seed_path.resolve())]
        )
        mock_relink.assert_called_once_with(
            [
                "--db",
                "stock_event_mining",
                "--top-k",
                "5",
                "--min-score",
                "0.4",
                "--canonical-map",
                "output/event_canonical_map.csv",
            ]
        )


if __name__ == "__main__":
    unittest.main()
