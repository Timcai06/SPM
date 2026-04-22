from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from modules.analysis.services.sample_generation_service import run_negative_samples, run_train_samples


class SampleGenerationServiceTests(unittest.TestCase):
    @patch("modules.analysis.services.sample_generation_service.run_event_sample_builder")
    def test_run_train_samples_dispatches_to_module_service(self, mock_main) -> None:
        run_train_samples(["--db", "stock_event_mining"])
        mock_main.assert_called_once_with(["--db", "stock_event_mining"])

    @patch("modules.analysis.services.sample_generation_service.run_control_sample_builder")
    def test_run_negative_samples_dispatches_to_module_service(self, mock_main) -> None:
        run_negative_samples(["--db", "stock_event_mining"])
        mock_main.assert_called_once_with(["--db", "stock_event_mining"])


if __name__ == "__main__":
    unittest.main()
