from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from modules.companies.services import (
    company_profile_service,
    company_stats_service,
    company_universe_service,
    market_context_service,
)


class CompanyUniverseServiceTests(unittest.TestCase):
    @patch("modules.companies.services.company_universe_service.load_companies")
    def test_run_load_companies_delegates_to_legacy(self, mock_main: MagicMock) -> None:
        company_universe_service.run_load_companies(["--db", "stock_event_mining"])
        mock_main.assert_called_once_with(["--db", "stock_event_mining"])

    @patch("modules.companies.services.company_universe_service.import_companies_public")
    def test_run_import_companies_public_delegates_to_legacy(self, mock_main: MagicMock) -> None:
        company_universe_service.run_import_companies_public(["--output", "seed.csv"])
        mock_main.assert_called_once_with(["--output", "seed.csv"])

    @patch("modules.companies.services.company_universe_service.import_companies_tushare")
    def test_run_import_companies_tushare_delegates_to_legacy(self, mock_main: MagicMock) -> None:
        company_universe_service.run_import_companies_tushare(["--db", "stock_event_mining"])
        mock_main.assert_called_once_with(["--db", "stock_event_mining"])


class CompanyProfileServiceTests(unittest.TestCase):
    @patch("modules.companies.services.company_profile_service.import_profiles")
    def test_run_import_profiles_delegates_to_legacy(self, mock_main: MagicMock) -> None:
        company_profile_service.run_import_profiles(["--db", "stock_event_mining"])
        mock_main.assert_called_once_with(["--db", "stock_event_mining"])

    @patch("modules.companies.services.company_profile_service.load_profiles")
    def test_run_load_profiles_delegates_to_legacy(self, mock_main: MagicMock) -> None:
        company_profile_service.run_load_profiles(["--db", "stock_event_mining"])
        mock_main.assert_called_once_with(["--db", "stock_event_mining"])

class CompanyStatsServiceTests(unittest.TestCase):
    @patch("modules.companies.services.company_stats_service.import_stats_sina")
    def test_run_import_stats_sina_delegates_to_legacy(self, mock_main: MagicMock) -> None:
        company_stats_service.run_import_stats_sina(["--db", "stock_event_mining"])
        mock_main.assert_called_once_with(["--db", "stock_event_mining"])

    @patch("modules.companies.services.company_stats_service.load_stats")
    def test_run_load_stats_delegates_to_legacy(self, mock_main: MagicMock) -> None:
        company_stats_service.run_load_stats(["--db", "stock_event_mining"])
        mock_main.assert_called_once_with(["--db", "stock_event_mining"])

    @patch("modules.companies.services.company_stats_service.import_stats_local")
    def test_run_import_stats_local_delegates_to_legacy(self, mock_main: MagicMock) -> None:
        company_stats_service.run_import_stats_local(["--db", "stock_event_mining"])
        mock_main.assert_called_once_with(["--db", "stock_event_mining"])


class MarketContextServiceTests(unittest.TestCase):
    @patch("modules.companies.services.market_context_service.load_market_environment")
    def test_run_load_market_environment_delegates_to_legacy(self, mock_main: MagicMock) -> None:
        market_context_service.run_load_market_environment(["--db", "stock_event_mining"])
        mock_main.assert_called_once_with(["--db", "stock_event_mining"])

    @patch("modules.companies.services.market_context_service.load_sentiment_propagation")
    def test_run_load_sentiment_propagation_delegates_to_legacy(self, mock_main: MagicMock) -> None:
        market_context_service.run_load_sentiment_propagation(["--db", "stock_event_mining"])
        mock_main.assert_called_once_with(["--db", "stock_event_mining"])


if __name__ == "__main__":
    unittest.main()
