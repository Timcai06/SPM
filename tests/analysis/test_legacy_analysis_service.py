from __future__ import annotations

import sys
import unittest
from unittest.mock import patch


from modules.analysis.services.legacy_analysis_service import (
    run_feature_return,
    run_train_samples,
)


class LegacyAnalysisServiceTests(unittest.TestCase):
    @patch("modules.analysis.services.legacy_analysis_service.legacy_feature_return.main")
    def test_run_feature_return_patches_argv(self, mock_main) -> None:
        original_argv = sys.argv[:]

        run_feature_return(["--db", "stock_event_mining", "--benchmark", "hs300"])

        mock_main.assert_called_once_with()
        self.assertEqual(sys.argv, original_argv)

    @patch("modules.analysis.services.legacy_analysis_service.legacy_build_model_samples.main")
    def test_run_train_samples_patches_argv(self, mock_main) -> None:
        original_argv = sys.argv[:]

        run_train_samples(["--db", "stock_event_mining", "--label-dataset", "out.csv"])

        mock_main.assert_called_once_with()
        self.assertEqual(sys.argv, original_argv)


if __name__ == "__main__":
    unittest.main()
