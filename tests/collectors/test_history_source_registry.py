from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from modules.collectors.domain.source_profiles import direct_history_source_choices, symbol_history_source_choices
from modules.collectors.services.direct_history_collect_service import DIRECT_HISTORY_BATCH_COLLECTORS
from modules.collectors.services.symbol_history_collect_service import SYMBOL_HISTORY_COLLECTORS


class HistorySourceRegistryTests(unittest.TestCase):
    def test_direct_collectors_match_source_profiles(self) -> None:
        self.assertEqual(set(direct_history_source_choices()), set(DIRECT_HISTORY_BATCH_COLLECTORS))

    def test_symbol_collectors_match_source_profiles(self) -> None:
        self.assertEqual(set(symbol_history_source_choices()), set(SYMBOL_HISTORY_COLLECTORS))


if __name__ == "__main__":
    unittest.main()
