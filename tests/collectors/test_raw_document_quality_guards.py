from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from modules.collectors.adapters.caixin import parse_time as parse_caixin_time
from modules.collectors.adapters.yicai import parse_time as parse_yicai_time
from modules.collectors.services.raw_document_loading_service import is_future_publish_date


class RawDocumentQualityGuardsTests(unittest.TestCase):
    def test_is_future_publish_date_rejects_future_calendar_days(self) -> None:
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d 09:00:00")
        self.assertTrue(is_future_publish_date(tomorrow))

    def test_is_future_publish_date_allows_today(self) -> None:
        today = datetime.now().strftime("%Y-%m-%d 23:59:59")
        self.assertFalse(is_future_publish_date(today))

    def test_caixin_parse_time_rolls_back_future_yearless_dates(self) -> None:
        parsed = datetime.strptime(parse_caixin_time("12月03日 17:11"), "%Y-%m-%d %H:%M:%S")
        self.assertLessEqual(parsed.date(), datetime.now().date())

    def test_yicai_parse_time_rolls_back_future_yearless_dates(self) -> None:
        parsed = datetime.strptime(parse_yicai_time("12-03 17:11"), "%Y-%m-%d %H:%M:%S")
        self.assertLessEqual(parsed.date(), datetime.now().date())


if __name__ == "__main__":
    unittest.main()
