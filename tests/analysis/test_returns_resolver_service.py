from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from modules.analysis.services.returns_resolver_service import (
    resolve_benchmark_returns,
    resolve_stock_returns,
)


class ReturnsResolverServiceTests(unittest.TestCase):
    def test_resolve_benchmark_returns_uses_cache_first(self) -> None:
        cache_payload = {
            "series": {
                "index:hs300": {
                    "source": "unit",
                    "returns": {"2025-01-01": 0.1},
                }
            }
        }
        returns, source, use_tushare = resolve_benchmark_returns(
            benchmark_key="hs300",
            index_code_map={"hs300": "000300.SH"},
            index_sina_symbol_map={"hs300": "sh000300"},
            index_eastmoney_secid_map={"hs300": "1.000300"},
            cache_payload=cache_payload,
            disable_cache=False,
            use_tushare=False,
            ts_module=None,
            token="",
            api_timeout_sec=1.0,
            market_max_rows=10,
            enable_eastmoney_fallback=False,
            reason_counts={},
        )
        self.assertEqual(returns["2025-01-01"], 0.1)
        self.assertEqual(source, "cache:unit")
        self.assertFalse(use_tushare)

    def test_resolve_stock_returns_uses_company_stats_first(self) -> None:
        returns, source = resolve_stock_returns(
            ts_code="000001.SZ",
            db="stock_event_mining",
            cache_payload={"series": {}},
            disable_cache=False,
            use_tushare=False,
            ts_module=None,
            token="",
            api_timeout_sec=1.0,
            market_max_rows=10,
            enable_eastmoney_fallback=False,
            reason_counts={},
            fetch_company_stats_returns_fn=lambda db, ts: {"2025-01-01": 0.2},
        )
        self.assertEqual(returns["2025-01-01"], 0.2)
        self.assertEqual(source, "int_company_stats")

    def test_resolve_stock_returns_falls_back_to_sina(self) -> None:
        with (
            patch("modules.analysis.services.returns_resolver_service.fetch_eastmoney_kline") as mock_eastmoney,
            patch("modules.analysis.services.returns_resolver_service.fetch_sina_kline") as mock_fetch,
        ):
            mock_eastmoney.side_effect = RuntimeError("eastmoney disabled in test")
            mock_fetch.return_value = [
                {"day": "2025-01-01", "close": "10"},
                {"day": "2025-01-02", "close": "11"},
            ]
            returns, source = resolve_stock_returns(
                ts_code="000001.SZ",
                db="stock_event_mining",
                cache_payload={"series": {}},
                disable_cache=False,
                use_tushare=False,
                ts_module=None,
                token="",
                api_timeout_sec=1.0,
                market_max_rows=10,
                enable_eastmoney_fallback=True,
                reason_counts={},
                fetch_company_stats_returns_fn=lambda db, ts: {},
            )
        self.assertEqual(source, "sina_stock_fallback")
        self.assertIn("2025-01-02", returns)


if __name__ == "__main__":
    unittest.main()
