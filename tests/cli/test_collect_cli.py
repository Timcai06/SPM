from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cli import collect
from cli.collect_parser import build_parser


class CollectCliTests(unittest.TestCase):
    def test_parser_supports_backfill_defaults(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["backfill-cninfo-fulltext"])
        self.assertEqual(args.command, "backfill-cninfo-fulltext")
        self.assertEqual(args.source, "巨潮资讯网/历史公告")
        self.assertEqual(args.db_flush_every, 100)
        self.assertEqual(args.progress_every, 10)
        self.assertEqual(args.heartbeat_sec, 5.0)

    def test_parser_supports_history_quality_flags(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["collect-history", "--quality-body-only", "--min-content-length", "400"])
        self.assertTrue(args.quality_body_only)
        self.assertEqual(args.min_content_length, 400)

    def test_parser_supports_full_raw(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["full-raw", "--db", "stock_event_mining", "--max-jobs", "6", "--dry-run"])
        self.assertEqual(args.command, "full-raw")
        self.assertEqual(args.db, "stock_event_mining")
        self.assertEqual(args.max_jobs, 6)
        self.assertTrue(args.dry_run)

    @patch.dict("cli.collect.COMMAND_HANDLERS", {"collect": MagicMock()})
    @patch("cli.collect.parse_args")
    def test_main_dispatches_via_handlers(self, mock_parse_args: MagicMock) -> None:
        args = MagicMock()
        args.command = "collect"
        mock_parse_args.return_value = args

        collect.main()

        collect.COMMAND_HANDLERS["collect"].assert_called_once_with(args)

    @patch("cli.collect.collect_job.main")
    def test_collect_handler_calls_job(self, mock_collect_main: MagicMock) -> None:
        args = MagicMock()
        args.limit = 12
        args.include_non_keyword = True

        collect.run_collect_command(args)

        mock_collect_main.assert_called_once_with(["--limit", "12", "--include-non-keyword"])

    @patch("cli.collect.logged_run")
    @patch("cli.collect.history_job.main")
    def test_collect_history_handler_calls_job(self, mock_history_main: MagicMock, mock_logged_run: MagicMock) -> None:
        mock_logged_run.return_value.__enter__.return_value = "collect_run_1"
        args = MagicMock()
        args.db = "stock_event_mining"
        args.source = "cninfo-disclosure"
        args.symbol_source = "db"
        args.symbol_file = ""
        args.start_date = "2025-01-01"
        args.end_date = "2025-02-01"
        args.max_symbols = 100
        args.offset = 20
        args.limit_per_symbol = 10
        args.workers = 4
        args.retries = 2
        args.sleep_sec = 0.1
        args.db_flush_every = 50
        args.output_dir = "output/history"
        args.skip_db_load = False
        args.cninfo_fulltext = True
        args.cninfo_fulltext_max_chars = 9000
        args.quality_body_only = True
        args.min_content_length = 400

        collect.run_collect_history_command(args)

        argv = mock_history_main.call_args.args[0]
        self.assertIn("--cninfo-fulltext", argv)
        self.assertIn("--db-flush-every", argv)
        self.assertIn("--quality-body-only", argv)
        self.assertIn("--min-content-length", argv)

    @patch("cli.collect.logged_run")
    @patch("cli.collect.cninfo_fulltext_backfill_job.main")
    def test_cninfo_backfill_handler_calls_job(self, mock_backfill_main: MagicMock, mock_logged_run: MagicMock) -> None:
        mock_logged_run.return_value.__enter__.return_value = "collect_run_2"
        args = MagicMock()
        args.db = "stock_event_mining"
        args.source = "巨潮资讯网/历史公告"
        args.start_date = "2025-01-01"
        args.end_date = "2025-02-01"
        args.max_rows = 100
        args.offset = 0
        args.id_min = 0
        args.id_max = 0
        args.shard_count = 0
        args.shard_index = 0
        args.workers = 4
        args.retries = 2
        args.sleep_sec = 0.1
        args.progress_every = 10
        args.heartbeat_sec = 5.0
        args.detail_timeout_sec = 20.0
        args.pdf_timeout_sec = 20.0
        args.db_flush_every = 10
        args.fulltext_max_chars = 9000
        args.skip_db_load = False

        collect.run_cninfo_backfill_command(args)

        argv = mock_backfill_main.call_args.args[0]
        self.assertIn("--progress-every", argv)
        self.assertIn("--heartbeat-sec", argv)
        self.assertIn("--detail-timeout-sec", argv)
        self.assertIn("--pdf-timeout-sec", argv)

    @patch("cli.collect.logged_run")
    @patch("cli.collect.full_raw_ingest_service.main")
    def test_full_raw_handler_calls_service(self, mock_full_raw_main: MagicMock, mock_logged_run: MagicMock) -> None:
        mock_logged_run.return_value.__enter__.return_value = "collect_run_full"
        args = MagicMock()
        args.db = "stock_event_mining"
        args.start_date = "2025-01-01"
        args.end_date = "2026-04-23"
        args.max_jobs = 4
        args.min_content_length = 300
        args.cninfo_max_symbols = 3000
        args.cninfo_limit_per_symbol = 120
        args.cninfo_workers = 24
        args.cninfo_backfill_max_rows = 30000
        args.cninfo_backfill_workers = 24
        args.top_n = 200
        args.dry_run = True

        collect.run_full_raw_command(args)

        argv = mock_full_raw_main.call_args.args[0]
        self.assertIn("--max-jobs", argv)
        self.assertIn("--dry-run", argv)
        self.assertIn("--cninfo-backfill-max-rows", argv)


if __name__ == "__main__":
    unittest.main()
