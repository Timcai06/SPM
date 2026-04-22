from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cli import linking
from cli.linking_parser import build_parser


class LinkingCliTests(unittest.TestCase):
    def test_parser_supports_link_events_defaults(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["link-events"])
        self.assertEqual(args.command, "link-events")
        self.assertEqual(args.top_k, 3)
        self.assertEqual(args.min_score, 0.35)

    @patch.dict("cli.linking.COMMAND_HANDLERS", {"run": MagicMock()})
    @patch("cli.linking.parse_args")
    def test_main_dispatches_via_command_handlers(self, mock_parse_args: MagicMock) -> None:
        args = MagicMock()
        args.command = "run"
        mock_parse_args.return_value = args

        linking.main()

        linking.COMMAND_HANDLERS["run"].assert_called_once_with(args)

    @patch("cli.linking.logged_run")
    @patch("cli.linking.linking_pipeline.main")
    def test_run_handler_calls_pipeline_with_explicit_argv(self, mock_pipeline_main: MagicMock, mock_logged_run: MagicMock) -> None:
        mock_logged_run.return_value.__enter__.return_value = "link_run_1"
        args = MagicMock()
        args.db = "stock_event_mining"
        args.top_k = 3
        args.min_score = 0.35
        args.canonical_map = "output/event_canonical_map.csv"

        linking.run_pipeline_command(args)

        mock_pipeline_main.assert_called_once_with(
            [
                "--db",
                "stock_event_mining",
                "--top-k",
                "3",
                "--min-score",
                "0.35",
                "--canonical-map",
                "output/event_canonical_map.csv",
                "--run-id",
                "link_run_1",
            ]
        )

    @patch("cli.linking.logged_run")
    @patch("cli.linking.relink_job.main")
    def test_link_events_handler_calls_job_with_explicit_argv(self, mock_relink_main: MagicMock, mock_logged_run: MagicMock) -> None:
        mock_logged_run.return_value.__enter__.return_value = "link_run_2"
        args = MagicMock()
        args.db = "stock_event_mining"
        args.top_k = 5
        args.min_score = 0.4
        args.canonical_map = "output/event_canonical_map.csv"
        args.progress_every = 200

        linking.run_link_events_command(args)

        mock_relink_main.assert_called_once_with(
            [
                "--db",
                "stock_event_mining",
                "--top-k",
                "5",
                "--min-score",
                "0.4",
                "--canonical-map",
                "output/event_canonical_map.csv",
                "--progress-every",
                "200",
            ]
        )

    @patch("cli.linking.logged_run")
    @patch("cli.linking.import_companies_job.main")
    def test_import_companies_all_a_handler_calls_job_with_explicit_argv(self, mock_import_main: MagicMock, mock_logged_run: MagicMock) -> None:
        mock_logged_run.return_value.__enter__.return_value = "link_run_3"
        task2_args = MagicMock()
        task2_args.command = "import-companies-all-a"
        task2_args.db = "stock_event_mining"
        task2_args.max_symbols = 100
        task2_args.offset = 20
        task2_args.lock_timeout_sec = 120

        with patch("cli.linking.parse_args", return_value=task2_args):
            linking.main()

        mock_import_main.assert_called_once_with(
            [
                "--db",
                "stock_event_mining",
                "--max-symbols",
                "100",
                "--offset",
                "20",
                "--lock-timeout-sec",
                "120",
            ]
        )

    @patch("cli.linking.import_companies_tushare_job.main")
    def test_import_companies_handler_calls_legacy_main_with_explicit_argv(self, mock_tushare_main: MagicMock) -> None:
        task2_args = MagicMock()
        task2_args.command = "import-companies"
        task2_args.output = "output/seeds/companies_a_share.csv"
        task2_args.tushare_token = "token"
        task2_args.tushare_token_file = ""

        with patch("cli.linking.parse_args", return_value=task2_args):
            linking.main()

        mock_tushare_main.assert_called_once_with(
            [
                "--output",
                "output/seeds/companies_a_share.csv",
                "--tushare-token",
                "token",
            ]
        )

    @patch("cli.linking.logged_run")
    @patch("cli.linking.board_industries_job.main")
    def test_import_company_industries_handler_calls_job_with_explicit_argv(self, mock_board_main: MagicMock, mock_logged_run: MagicMock) -> None:
        mock_logged_run.return_value.__enter__.return_value = "link_run_4"
        task2_args = MagicMock()
        task2_args.command = "import-company-industries"
        task2_args.db = "stock_event_mining"
        task2_args.max_industries = 50
        task2_args.offset = 10
        task2_args.sleep_sec = 0.05
        task2_args.progress_every = 20
        task2_args.lock_timeout_sec = 120

        with patch("cli.linking.parse_args", return_value=task2_args):
            linking.main()

        mock_board_main.assert_called_once_with(
            [
                "--db",
                "stock_event_mining",
                "--max-industries",
                "50",
                "--offset",
                "10",
                "--sleep-sec",
                "0.05",
                "--progress-every",
                "20",
                "--lock-timeout-sec",
                "120",
            ]
        )

    @patch("cli.linking.logged_run")
    @patch("cli.linking.standard_industries_job.main")
    def test_import_standard_industries_handler_calls_job_with_explicit_argv(self, mock_standard_main: MagicMock, mock_logged_run: MagicMock) -> None:
        mock_logged_run.return_value.__enter__.return_value = "link_run_5"
        task2_args = MagicMock()
        task2_args.command = "import-company-standard-industries"
        task2_args.db = "stock_event_mining"
        task2_args.max_symbols = 200
        task2_args.offset = 0
        task2_args.start_date = "19900101"
        task2_args.end_date = "20251231"
        task2_args.sleep_sec = 0.05
        task2_args.progress_every = 20
        task2_args.lock_timeout_sec = 120
        task2_args.retries = 2
        task2_args.failure_backoff_sec = 0.8
        task2_args.only_dirty = True
        task2_args.skip_legacy = True

        with patch("cli.linking.parse_args", return_value=task2_args):
            linking.main()

        mock_standard_main.assert_called_once()
        argv = mock_standard_main.call_args.args[0]
        self.assertIn("--only-dirty", argv)
        self.assertIn("--skip-legacy", argv)
        self.assertNotIn("import_company_standard_industries_akshare.py", argv)

    @patch("cli.linking.logged_run")
    @patch("cli.linking.load_companies_job.main")
    def test_load_companies_handler_calls_legacy_main_with_explicit_argv(self, mock_load_main: MagicMock, mock_logged_run: MagicMock) -> None:
        mock_logged_run.return_value.__enter__.return_value = "link_run_6"
        task2_args = MagicMock()
        task2_args.command = "load-companies"
        task2_args.db = "stock_event_mining"
        task2_args.input = "output/seeds/companies_seed.csv"

        with patch("cli.linking.parse_args", return_value=task2_args):
            linking.main()

        mock_load_main.assert_called_once_with(
            ["--db", "stock_event_mining", "--input", "output/seeds/companies_seed.csv"]
        )

    @patch("cli.linking.import_companies_public_job.main")
    def test_import_companies_public_handler_calls_legacy_main_with_explicit_argv(self, mock_public_main: MagicMock) -> None:
        task2_args = MagicMock()
        task2_args.command = "import-companies-public"
        task2_args.output = "output/seeds/companies_public.csv"

        with patch("cli.linking.parse_args", return_value=task2_args):
            linking.main()

        mock_public_main.assert_called_once_with(["--output", "output/seeds/companies_public.csv"])

    @patch("cli.linking.logged_run")
    @patch("cli.linking.import_profiles_job.main")
    def test_import_company_profiles_handler_calls_job_with_explicit_argv(self, mock_profiles_main: MagicMock, mock_logged_run: MagicMock) -> None:
        mock_logged_run.return_value.__enter__.return_value = "link_run_7"
        task2_args = MagicMock()
        task2_args.command = "import-company-profiles"
        task2_args.db = "stock_event_mining"
        task2_args.input = "output/seeds/company_profiles_seed.csv"
        task2_args.output = "output/seeds/company_profiles_seed.csv"
        task2_args.max_symbols = 100
        task2_args.sleep_sec = 0.05
        task2_args.progress_every = 10
        task2_args.with_holders = True

        with patch("cli.linking.parse_args", return_value=task2_args):
            linking.main()

        mock_profiles_main.assert_called_once_with(
            [
                "--db",
                "stock_event_mining",
                "--input",
                "output/seeds/company_profiles_seed.csv",
                "--output",
                "output/seeds/company_profiles_seed.csv",
                "--max-symbols",
                "100",
                "--sleep-sec",
                "0.05",
                "--progress-every",
                "10",
                "--with-holders",
            ]
        )

    @patch("cli.linking.logged_run")
    @patch("cli.linking.import_stats_job.run_tushare")
    def test_import_company_stats_tushare_handler_calls_job_with_explicit_argv(self, mock_run_tushare: MagicMock, mock_logged_run: MagicMock) -> None:
        mock_logged_run.return_value.__enter__.return_value = "link_run_8"
        task2_args = MagicMock()
        task2_args.command = "import-company-stats"
        task2_args.source = "tushare"
        task2_args.output = "company_stats.csv"
        task2_args.quotes_output = "stock_daily_quotes.csv"
        task2_args.db = "stock_event_mining"
        task2_args.days = 30
        task2_args.max_symbols = 300
        task2_args.max_rows = 1200
        task2_args.sleep_sec = 0.05
        task2_args.progress_every = 20
        task2_args.timeout_sec = 12.0
        task2_args.offset = 0
        task2_args.retries = 2
        task2_args.failure_backoff_sec = 0.8
        task2_args.resume_existing = False
        task2_args.tushare_token = "token"
        task2_args.tushare_token_file = ""

        with patch("cli.linking.parse_args", return_value=task2_args):
            linking.main()

        mock_run_tushare.assert_called_once_with(
            [
                "--output",
                "company_stats.csv",
                "--quotes-output",
                "stock_daily_quotes.csv",
                "--db",
                "stock_event_mining",
                "--days",
                "30",
                "--max-symbols",
                "300",
                "--tushare-token",
                "token",
            ]
        )

    @patch("cli.linking.import_stats_job.run_akshare")
    def test_import_company_stats_akshare_handler_calls_job_with_explicit_argv(self, mock_run_akshare: MagicMock) -> None:
        task2_args = MagicMock()
        task2_args.command = "import-company-stats"
        task2_args.source = "akshare"
        task2_args.output = "company_stats.csv"
        task2_args.quotes_output = "stock_daily_quotes.csv"
        task2_args.db = "stock_event_mining"
        task2_args.days = 30
        task2_args.max_symbols = 300
        task2_args.max_rows = 1200
        task2_args.sleep_sec = 0.05
        task2_args.progress_every = 20
        task2_args.timeout_sec = 12.0
        task2_args.offset = 10
        task2_args.retries = 2
        task2_args.failure_backoff_sec = 0.8
        task2_args.resume_existing = True
        task2_args.tushare_token = ""
        task2_args.tushare_token_file = ""

        with patch("cli.linking.parse_args", return_value=task2_args):
            linking.main()

        mock_run_akshare.assert_called_once_with(
            [
                "--output",
                "company_stats.csv",
                "--quotes-output",
                "stock_daily_quotes.csv",
                "--db",
                "stock_event_mining",
                "--days",
                "30",
                "--max-symbols",
                "300",
                "--offset",
                "10",
                "--sleep-sec",
                "0.05",
                "--progress-every",
                "20",
                "--timeout-sec",
                "12.0",
                "--retries",
                "2",
                "--failure-backoff-sec",
                "0.8",
                "--resume-existing",
            ]
        )

    @patch("cli.linking.import_stats_local_job.main")
    def test_import_company_stats_local_handler_calls_job_with_explicit_argv(self, mock_local_main: MagicMock) -> None:
        task2_args = MagicMock()
        task2_args.command = "import-company-stats-local"
        task2_args.input = "quotes.csv"
        task2_args.output = "company_stats.csv"
        task2_args.quotes_output = "stock_daily_quotes.csv"

        with patch("cli.linking.parse_args", return_value=task2_args):
            linking.main()

        mock_local_main.assert_called_once_with(
            [
                "--input",
                "quotes.csv",
                "--output",
                "company_stats.csv",
                "--quotes-output",
                "stock_daily_quotes.csv",
            ]
        )

    @patch("cli.linking.load_stats_job.main")
    def test_load_company_stats_handler_calls_job_with_explicit_argv(self, mock_load_stats_main: MagicMock) -> None:
        task2_args = MagicMock()
        task2_args.command = "load-company-stats"
        task2_args.db = "stock_event_mining"
        task2_args.input = "company_stats.csv"
        task2_args.quotes_input = "stock_daily_quotes.csv"

        with patch("cli.linking.parse_args", return_value=task2_args):
            linking.main()

        mock_load_stats_main.assert_called_once_with(
            [
                "--db",
                "stock_event_mining",
                "--input",
                "company_stats.csv",
                "--quotes-input",
                "stock_daily_quotes.csv",
            ]
        )

    @patch("cli.linking.load_profiles_job.main")
    def test_load_company_profiles_handler_calls_job_with_explicit_argv(self, mock_load_profiles_main: MagicMock) -> None:
        task2_args = MagicMock()
        task2_args.command = "load-company-profiles"
        task2_args.db = "stock_event_mining"
        task2_args.snapshot_date = "2026-04-21"
        task2_args.input = "company_profiles_seed.csv"
        task2_args.lock_timeout_sec = 120

        with patch("cli.linking.parse_args", return_value=task2_args):
            linking.main()

        mock_load_profiles_main.assert_called_once_with(
            [
                "--db",
                "stock_event_mining",
                "--snapshot-date",
                "2026-04-21",
                "--input",
                "company_profiles_seed.csv",
                "--lock-timeout-sec",
                "120",
            ]
        )

    @patch("cli.linking.load_market_environment_job.main")
    def test_load_market_environment_handler_calls_legacy_main_with_explicit_argv(self, mock_market_main: MagicMock) -> None:
        task2_args = MagicMock()
        task2_args.command = "load-market-environment"
        task2_args.db = "stock_event_mining"
        task2_args.benchmark = "hs300"
        task2_args.input = "market_environment_seed.csv"
        task2_args.timeout_sec = 12.0
        task2_args.lock_timeout_sec = 120

        with patch("cli.linking.parse_args", return_value=task2_args):
            linking.main()

        mock_market_main.assert_called_once_with(
            [
                "--db",
                "stock_event_mining",
                "--benchmark",
                "hs300",
                "--input",
                "market_environment_seed.csv",
                "--timeout-sec",
                "12.0",
                "--lock-timeout-sec",
                "120",
            ]
        )

    @patch("cli.linking.load_sentiment_propagation_job.main")
    def test_load_sentiment_propagation_handler_calls_legacy_main_with_explicit_argv(self, mock_sentiment_main: MagicMock) -> None:
        task2_args = MagicMock()
        task2_args.command = "load-sentiment-propagation"
        task2_args.db = "stock_event_mining"
        task2_args.lock_timeout_sec = 120
        task2_args.quiet = True

        with patch("cli.linking.parse_args", return_value=task2_args):
            linking.main()

        mock_sentiment_main.assert_called_once_with(
            ["--db", "stock_event_mining", "--lock-timeout-sec", "120", "--quiet"]
        )

if __name__ == "__main__":
    unittest.main()
