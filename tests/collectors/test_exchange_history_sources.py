from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from modules.collectors.services.exchange_history_sources import _fill_pdf_bodies, iter_sse_announcements_history_batches


class ExchangeHistorySourceTests(unittest.TestCase):
    @patch("modules.collectors.services.exchange_history_sources.cninfo.extract_pdf_text")
    def test_fill_pdf_bodies_replaces_short_metadata_with_extracted_text(self, mock_extract_pdf_text) -> None:
        mock_extract_pdf_text.return_value = "这是交易所公告 PDF 正文" * 30
        rows = [
            {
                "source": "上交所/最新公告",
                "title": "关于重大事项的公告",
                "content": "关于重大事项的公告；证券代码：600000",
                "publish_time": "2026-01-02",
                "url": "https://www.sse.com.cn/disclosure/listedinfo/announcement/c/new/notice.pdf",
                "symbol_or_subject": "公司行为事件",
            }
        ]

        updated = _fill_pdf_bodies(rows, workers=2)

        self.assertEqual(len(updated), 1)
        self.assertGreater(len(updated[0]["content"]), len(rows[0]["content"]))
        self.assertIn("交易所公告 PDF 正文", updated[0]["content"])

    @patch("modules.collectors.services.exchange_history_sources.fetch_text")
    def test_sse_history_returns_empty_batches_when_list_fetch_fails(self, mock_fetch_text) -> None:
        mock_fetch_text.side_effect = RuntimeError("ssl eof")

        batches = iter_sse_announcements_history_batches(
            start_date="2026-04-20",
            end_date="2026-04-27",
            max_pages=1,
            page_size=50,
        )

        self.assertEqual([], batches)


if __name__ == "__main__":
    unittest.main()
