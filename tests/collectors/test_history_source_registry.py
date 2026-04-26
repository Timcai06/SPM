from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from modules.collectors.domain.source_profiles import (
    RAW_HISTORY_SOURCE_PROFILES,
    TARGET_BODY_ROWS_PER_NON_CNINFO_SOURCE,
    direct_history_source_choices,
    profile_by_history_source,
    symbol_history_source_choices,
)
from modules.collectors.services.direct_history_collect_service import DIRECT_HISTORY_BATCH_COLLECTORS
from modules.collectors.services.symbol_history_collect_service import SYMBOL_HISTORY_COLLECTORS


class HistorySourceRegistryTests(unittest.TestCase):
    def test_direct_collectors_match_source_profiles(self) -> None:
        self.assertEqual(set(direct_history_source_choices()), set(DIRECT_HISTORY_BATCH_COLLECTORS))

    def test_symbol_collectors_match_source_profiles(self) -> None:
        self.assertEqual(set(symbol_history_source_choices()), set(SYMBOL_HISTORY_COLLECTORS))

    def test_profile_lookup_uses_history_source(self) -> None:
        self.assertEqual(profile_by_history_source("gov-news").source_family, "中国政府网")

    def test_non_cninfo_profiles_have_operator_contract(self) -> None:
        for profile in RAW_HISTORY_SOURCE_PROFILES:
            self.assertIn(profile.collector_family, {"policy", "exchange", "media", "symbol"})
            self.assertEqual(profile.target_rows, TARGET_BODY_ROWS_PER_NON_CNINFO_SOURCE)

    def test_body_sources_use_requires_body_contract(self) -> None:
        body_sources = {
            "yicai-news",
            "eastmoney-industry",
            "gov-news",
            "ndrc-policy",
            "csrc-policy",
            "miit-policy",
        }
        actual = {profile.history_source for profile in RAW_HISTORY_SOURCE_PROFILES if profile.requires_body}
        self.assertEqual(body_sources, actual)


if __name__ == "__main__":
    unittest.main()
