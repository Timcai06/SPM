from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from modules.analysis.services.feature_analysis_service import run_feature_return
from modules.analysis.services.sample_generation_service import run_negative_samples, run_train_samples


class AnalysisBridgeServiceTests(unittest.TestCase):
    @patch("modules.analysis.services.feature_analysis_service.legacy_feature_return.main")
    def test_run_feature_return_passes_argv(self, mock_main) -> None:
        run_feature_return(["--db", "stock_event_mining", "--benchmark", "hs300"])

        mock_main.assert_called_once_with(["--db", "stock_event_mining", "--benchmark", "hs300"])

    @patch("modules.analysis.services.sample_generation_service.legacy_build_model_samples.main")
    def test_run_train_samples_passes_argv(self, mock_main) -> None:
        run_train_samples(["--db", "stock_event_mining", "--label-dataset", "out.csv"])

        mock_main.assert_called_once_with(["--db", "stock_event_mining", "--label-dataset", "out.csv"])

    @patch("modules.analysis.services.sample_generation_service.legacy_build_negative_samples.main")
    def test_run_negative_samples_passes_argv(self, mock_main) -> None:
        run_negative_samples(["--db", "stock_event_mining", "--max-per-day", "50"])

        mock_main.assert_called_once_with(["--db", "stock_event_mining", "--max-per-day", "50"])


if __name__ == "__main__":
    unittest.main()
