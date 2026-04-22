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


class AnalysisBridgeServiceTests(unittest.TestCase):
    @patch("modules.analysis.services.feature_analysis_service.legacy_feature_return.main")
    def test_run_feature_return_passes_argv(self, mock_main) -> None:
        run_feature_return(["--db", "stock_event_mining", "--benchmark", "hs300"])

        mock_main.assert_called_once_with(["--db", "stock_event_mining", "--benchmark", "hs300"])

if __name__ == "__main__":
    unittest.main()
