from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cli import quality
from cli.quality_parser import build_parser


class QualityCliTests(unittest.TestCase):
    def test_parser_supports_summary_alias(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["summary", "--db", "stock_event_mining"])
        self.assertEqual(args.command, "summary")
        self.assertEqual(args.db, "stock_event_mining")

    def test_parser_supports_db_alias(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["db", "--db", "stock_event_mining"])
        self.assertEqual(args.command, "db")
        self.assertEqual(args.db, "stock_event_mining")

    def test_parser_supports_sample_alias(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["sample", "--sample-size", "25"])
        self.assertEqual(args.command, "sample")
        self.assertEqual(args.sample_size, 25)

    def test_parser_supports_delivery_status(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["delivery-status", "--db", "stock_event_mining"])
        self.assertEqual(args.command, "delivery-status")
        self.assertEqual(args.db, "stock_event_mining")

    def test_parser_supports_storage_audit(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["storage-audit", "--db", "stock_event_mining"])
        self.assertEqual(args.command, "storage-audit")
        self.assertEqual(args.db, "stock_event_mining")

    def test_parser_supports_sources_alias(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["sources", "--db", "stock_event_mining", "--top-n", "25"])
        self.assertEqual(args.command, "sources")
        self.assertEqual(args.db, "stock_event_mining")
        self.assertEqual(args.top_n, 25)

    def test_parser_supports_normalize_raw_categories(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "normalize-raw-categories",
                "--db",
                "stock_event_mining",
                "--start-date",
                "2025-01-01",
                "--end-date",
                "2026-04-24",
            ]
        )
        self.assertEqual(args.command, "normalize-raw-categories")
        self.assertEqual(args.db, "stock_event_mining")
        self.assertEqual(args.start_date, "2025-01-01")
        self.assertEqual(args.end_date, "2026-04-24")

    @patch("cli.quality.check_job.main")
    def test_check_handler_calls_job(self, mock_check_main: MagicMock) -> None:
        quality.run_check_command(MagicMock())
        mock_check_main.assert_called_once_with([])

    @patch("cli.quality.logged_run")
    @patch("cli.quality.quality_report_job.main")
    def test_sample_alias_handler_calls_quality_job(
        self, mock_quality_main: MagicMock, mock_logged_run: MagicMock
    ) -> None:
        mock_logged_run.return_value.__enter__.return_value = "quality_run_sample"
        args = MagicMock()
        args.sample_size = 25
        args.run_id = ""

        quality.COMMAND_HANDLERS["sample"](args)

        mock_quality_main.assert_called_once_with(["--sample-size", "25", "--run-id", "quality_run_sample"])

    @patch("cli.quality.logged_run")
    @patch("cli.quality.print_db_status")
    def test_db_alias_handler_calls_db_status(self, mock_db_status: MagicMock, mock_logged_run: MagicMock) -> None:
        mock_logged_run.return_value.__enter__.return_value = "quality_run_db"
        args = MagicMock()
        args.db = "stock_event_mining"

        quality.COMMAND_HANDLERS["db"](args)

        mock_db_status.assert_called_once_with("stock_event_mining")

    @patch("cli.quality.logged_run")
    @patch("cli.quality.print_qa_summary")
    def test_summary_alias_handler_calls_qa(self, mock_qa_summary: MagicMock, mock_logged_run: MagicMock) -> None:
        mock_logged_run.return_value.__enter__.return_value = "quality_run_summary"
        args = MagicMock()
        args.db = "stock_event_mining"
        args.snapshot_path = "output/qa_snapshot.json"
        args.collector_report = "output/collector_report.md"
        args.feature_report = "output/feature_report.md"

        quality.COMMAND_HANDLERS["summary"](args)

        mock_qa_summary.assert_called_once()

    @patch("cli.quality.logged_run")
    @patch("cli.quality.delivery_status_job.main")
    def test_delivery_status_handler_calls_job(self, mock_delivery_main: MagicMock, mock_logged_run: MagicMock) -> None:
        mock_logged_run.return_value.__enter__.return_value = "quality_run_1"
        args = MagicMock()
        args.db = "stock_event_mining"
        args.output = "report/out.md"
        args.fail_on_blockers = True

        quality.run_delivery_status_command(args)

        mock_delivery_main.assert_called_once_with(
            ["--db", "stock_event_mining", "--output", "report/out.md", "--fail-on-blockers"]
        )

    @patch("cli.quality.logged_run")
    @patch("cli.quality.storage_governance_job.run_storage_audit")
    def test_storage_audit_handler_calls_job(self, mock_audit: MagicMock, mock_logged_run: MagicMock) -> None:
        mock_logged_run.return_value.__enter__.return_value = "quality_run_2"
        args = MagicMock()
        args.db = "stock_event_mining"

        quality.run_storage_audit_command(args)

        mock_audit.assert_called_once_with(["--db", "stock_event_mining"])

    @patch("cli.quality.logged_run")
    @patch("cli.quality.storage_governance_job.run_raw_source_coverage")
    def test_sources_alias_handler_calls_job(self, mock_raw_coverage: MagicMock, mock_logged_run: MagicMock) -> None:
        mock_logged_run.return_value.__enter__.return_value = "quality_run_sources"
        args = MagicMock()
        args.db = "stock_event_mining"
        args.start_date = "2025-01-01"
        args.end_date = "2027-01-01"
        args.top_n = 25

        quality.COMMAND_HANDLERS["sources"](args)

        mock_raw_coverage.assert_called_once_with(
            [
                "--db",
                "stock_event_mining",
                "--start-date",
                "2025-01-01",
                "--end-date",
                "2027-01-01",
                "--top-n",
                "25",
            ]
        )

    @patch("cli.quality.logged_run")
    @patch("cli.quality.storage_governance_job.run_normalize_raw_categories")
    def test_normalize_raw_categories_handler_calls_job(
        self, mock_normalize: MagicMock, mock_logged_run: MagicMock
    ) -> None:
        mock_logged_run.return_value.__enter__.return_value = "quality_run_raw_categories"
        args = MagicMock()
        args.db = "stock_event_mining"
        args.start_date = "2025-01-01"
        args.end_date = "2026-04-24"
        args.lock_timeout_sec = 120

        quality.run_normalize_raw_categories_command(args)

        mock_normalize.assert_called_once_with(
            [
                "--db",
                "stock_event_mining",
                "--lock-timeout-sec",
                "120",
                "--start-date",
                "2025-01-01",
                "--end-date",
                "2026-04-24",
            ]
        )

    @patch("cli.quality.logged_run")
    @patch("cli.quality.storage_governance_job.run_clean_stage")
    def test_clean_stage_handler_calls_job(self, mock_clean: MagicMock, mock_logged_run: MagicMock) -> None:
        mock_logged_run.return_value.__enter__.return_value = "quality_run_3"
        args = MagicMock()
        args.db = "stock_event_mining"
        args.lock_timeout_sec = 120
        args.yes = True

        quality.run_clean_stage_command(args)

        mock_clean.assert_called_once_with(["--db", "stock_event_mining", "--lock-timeout-sec", "120", "--yes"])


if __name__ == "__main__":
    unittest.main()
