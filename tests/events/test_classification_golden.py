from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from modules.events.domain.detection_rules import detect_event
from modules.events.jobs.classify_job import STRUCTURED_BUILDER_CONFIG
from modules.events.services.structured_event_builder import build_structured_row


class ClassificationGoldenTests(unittest.TestCase):
    def test_major_contract_company_event(self) -> None:
        row = {
            "source": "巨潮资讯网/历史公告",
            "title": "测试公司：关于签订重大合同的公告",
            "content": "公司近日与某客户签订重大合同，合同金额为5亿元。",
            "publish_time": "2025-03-01 10:00:00",
            "url": "u1",
            "symbol_or_subject": "000001.SZ",
        }
        result = detect_event(row, 1)
        self.assertTrue(result.is_event)
        structured = build_structured_row(row, result, STRUCTURED_BUILDER_CONFIG)
        self.assertEqual(structured["event_subject_type"], "公司类")
        self.assertEqual(structured["event_subject_subtype"], "重大合同")
        self.assertEqual(structured["predictability_type"], "预披露型")
        self.assertEqual(structured["duration_type"], "中期型")
        self.assertEqual(structured["impact_scope"], "个股链条")
        self.assertEqual(structured["sentiment"], "利好")

    def test_policy_event_golden_labels(self) -> None:
        row = {
            "source": "中国政府网/新华社",
            "title": "国务院印发新一轮稳增长政策措施",
            "content": "国务院发布政策措施，支持制造业升级和扩大内需。",
            "publish_time": "2025-03-02 09:00:00",
            "url": "u2",
            "symbol_or_subject": "",
        }
        result = detect_event(row, 1)
        self.assertTrue(result.is_event)
        structured = build_structured_row(row, result, STRUCTURED_BUILDER_CONFIG)
        self.assertEqual(structured["event_subject_type"], "政策类")
        self.assertEqual(structured["event_subject_subtype"], "产业政策")
        self.assertEqual(structured["predictability_type"], "预披露型")
        self.assertEqual(structured["duration_type"], "中期型")
        self.assertEqual(structured["impact_scope"], "行业")
        self.assertEqual(structured["sentiment"], "利好")

    def test_generic_shareholder_meeting_is_filtered(self) -> None:
        row = {
            "source": "巨潮资讯网/历史公告",
            "title": "测试公司：关于召开2025年第一次临时股东大会的通知",
            "content": "公司将召开股东大会审议议案。",
            "publish_time": "2025-03-01 10:00:00",
            "url": "u3",
            "symbol_or_subject": "000001.SZ",
        }
        result = detect_event(row, 1)
        self.assertFalse(result.is_event)
        self.assertEqual(result.filter_reason, "generic_announcement_without_signal")


if __name__ == "__main__":
    unittest.main()
