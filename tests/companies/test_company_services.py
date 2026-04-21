from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from modules.companies.services import company_metrics_service, company_seed_service


class CompanySeedServiceTests(unittest.TestCase):
    @patch("modules.companies.services.company_seed_service.legacy_load_companies.main")
    def test_run_load_companies_delegates_to_legacy(self, mock_main: MagicMock) -> None:
        company_seed_service.run_load_companies(["--db", "stock_event_mining"])
        mock_main.assert_called_once_with(["--db", "stock_event_mining"])

    @patch("modules.companies.services.company_seed_service.legacy_import_companies_public.main")
    def test_run_import_companies_public_delegates_to_legacy(self, mock_main: MagicMock) -> None:
        company_seed_service.run_import_companies_public(["--output", "seed.csv"])
        mock_main.assert_called_once_with(["--output", "seed.csv"])

    @patch("modules.companies.services.company_seed_service.legacy_import_company_profiles.main")
    def test_run_import_profiles_delegates_to_legacy(self, mock_main: MagicMock) -> None:
        company_seed_service.run_import_profiles(["--db", "stock_event_mining"])
        mock_main.assert_called_once_with(["--db", "stock_event_mining"])


class CompanyMetricsServiceTests(unittest.TestCase):
    @patch("modules.companies.services.company_metrics_service.legacy_import_stats_sina.main")
    def test_run_import_stats_sina_delegates_to_legacy(self, mock_main: MagicMock) -> None:
        company_metrics_service.run_import_stats_sina(["--db", "stock_event_mining"])
        mock_main.assert_called_once_with(["--db", "stock_event_mining"])

    @patch("modules.companies.services.company_metrics_service.legacy_load_market_environment.main")
    def test_run_load_market_environment_delegates_to_legacy(self, mock_main: MagicMock) -> None:
        company_metrics_service.run_load_market_environment(["--db", "stock_event_mining"])
        mock_main.assert_called_once_with(["--db", "stock_event_mining"])

    @patch("modules.companies.services.company_metrics_service.legacy_load_sentiment_propagation.main")
    def test_run_load_sentiment_propagation_delegates_to_legacy(self, mock_main: MagicMock) -> None:
        company_metrics_service.run_load_sentiment_propagation(["--db", "stock_event_mining"])
        mock_main.assert_called_once_with(["--db", "stock_event_mining"])


if __name__ == "__main__":
    unittest.main()
