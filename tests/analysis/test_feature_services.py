from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from modules.analysis.services.feature_cache_service import (
    get_cached_series,
    load_market_cache,
    put_cached_series,
    resolve_tushare_token,
)
from modules.analysis.services.market_data_service import (
    close_series_to_returns,
    ts_to_eastmoney_secid,
    ts_to_sina_symbol,
)
from modules.analysis.services.feature_report_service import build_feature_report


class FeatureServicesTests(unittest.TestCase):
    def test_cache_roundtrip(self) -> None:
        payload = {"series": {}}
        put_cached_series(payload, "stock:000001.SZ", {"2025-01-01": 0.1}, "unit")
        returns, source = get_cached_series(payload, "stock:000001.SZ")
        self.assertEqual(source, "unit")
        self.assertEqual(returns["2025-01-01"], 0.1)

    def test_load_market_cache_invalid_file_returns_empty_series(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "cache.json"
            path.write_text("not-json", encoding="utf-8")
            payload = load_market_cache(path)
            self.assertEqual(payload, {"series": {}})

    def test_resolve_tushare_token_prefers_cli_arg(self) -> None:
        token, source = resolve_tushare_token(
            disable_tushare=False,
            tushare_token="abc123",
            tushare_token_file="",
            root=ROOT,
        )
        self.assertEqual(token, "abc123")
        self.assertEqual(source, "cli_arg")

    def test_build_feature_report_contains_sections(self) -> None:
        report = build_feature_report(
            run_id="r1",
            analysis_mode="event-study",
            benchmark_key="hs300",
            benchmark_source="cache:test",
            token_source="disabled",
            link_source="event_company_links",
            event_windows=[1, 3],
            time_budget_sec=300,
            max_rows=100,
            rows=[{"x": "1"}],
            processed_rows=1,
            dataset_rows=[
                {
                    "car_w1": "0.01",
                    "car_w3": "0.02",
                    "impact_scope": "行业",
                    "heat_bucket": "mid",
                    "intensity_bucket": "high",
                }
            ],
            reason_counts={"no_common_trade_dates": 2},
            dataset_path=Path("/tmp/out.csv"),
            mean_and_t=lambda vals: (sum(vals) / len(vals), None),
        )
        self.assertIn("## 一、总体CAR统计", report)
        self.assertIn("## 三、不可计算样本原因", report)
        self.assertIn("car_w1", report)

    def test_symbol_helpers_map_codes(self) -> None:
        self.assertEqual(ts_to_sina_symbol("000001.SZ"), "sz000001")
        self.assertEqual(ts_to_eastmoney_secid("600000.SH"), "1.600000")
        self.assertEqual(ts_to_sina_symbol("430001.BJ"), "bj430001")

    def test_close_series_to_returns_skips_bad_rows(self) -> None:
        returns = close_series_to_returns(
            [
                {"day": "2025-01-01 15:00:00", "close": "10"},
                {"day": "2025-01-02", "close": "11"},
                {"day": "2025-01-03", "close": "bad"},
                {"day": "2025-01-04", "close": "12"},
            ]
        )
        self.assertAlmostEqual(returns["2025-01-02"], 0.1)
        self.assertNotIn("2025-01-04", returns)


if __name__ == "__main__":
    unittest.main()
