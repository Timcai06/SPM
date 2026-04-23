from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from modules.collectors.adapters import cninfo


class CninfoAdapterTests(unittest.TestCase):
    def test_parse_detail_url(self) -> None:
        parsed = cninfo.parse_detail_url(
            "http://www.cninfo.com.cn/new/disclosure/detail"
            "?stockCode=000026&announcementId=1222189112&orgId=gssz0000026&announcementTime=2025-01-02%2000:00:00"
        )
        self.assertEqual(parsed["stock_code"], "000026")
        self.assertEqual(parsed["announcement_id"], "1222189112")
        self.assertEqual(parsed["org_id"], "gssz0000026")
        self.assertEqual(parsed["announcement_time"], "2025-01-02 00:00:00")

    def test_build_derived_pdf_urls(self) -> None:
        urls = cninfo.build_derived_pdf_urls("1222189112", "2025-01-02 00:00:00")
        self.assertEqual(
            urls,
            [
                "https://static.cninfo.com.cn/finalpage/2025-01-02/1222189112.PDF",
                "https://static.cninfo.com.cn/finalpage/2025-01-02/1222189112.pdf",
            ],
        )

    @patch("modules.collectors.adapters.cninfo.extract_pdf_text")
    @patch("modules.collectors.adapters.cninfo.fetch_bulletin_detail")
    def test_extract_fulltext_from_detail_url_falls_back_to_derived_pdf(
        self,
        mock_fetch_bulletin_detail,
        mock_extract_pdf_text,
    ) -> None:
        mock_fetch_bulletin_detail.side_effect = RuntimeError("403")

        def fake_extract(
            pdf_url: str,
            max_chars: int = 12000,
            request_timeout_sec: float = 20.0,
        ) -> str:
            if pdf_url.endswith(".PDF"):
                return "这是正文内容"
            return ""

        mock_extract_pdf_text.side_effect = fake_extract
        content = cninfo.extract_fulltext_from_detail_url(
            "http://www.cninfo.com.cn/new/disclosure/detail"
            "?stockCode=000026&announcementId=1222189112&orgId=gssz0000026&announcementTime=2025-01-02%2000:00:00",
            max_chars=12000,
        )
        self.assertEqual(content, "这是正文内容")
        mock_extract_pdf_text.assert_called()


if __name__ == "__main__":
    unittest.main()
