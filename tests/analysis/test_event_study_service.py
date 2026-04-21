from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from modules.analysis.services.event_study_service import (
    build_estimation_points,
    compute_car_metrics,
    fit_market_model,
    resolve_event_trade_index,
)


class EventStudyServiceTests(unittest.TestCase):
    def test_resolve_event_trade_index_aligns_previous_trade_date(self) -> None:
        idx, reason = resolve_event_trade_index(["2025-01-02", "2025-01-03"], "2025-01-04", max_gap_days=2)
        self.assertEqual(idx, 1)
        self.assertEqual(reason, "aligned_prev_trade_date")

    def test_fit_market_model_returns_alpha_beta(self) -> None:
        points = [(0.01 + 1.5 * (i / 1000.0), i / 1000.0) for i in range(1, 60)]
        fit = fit_market_model(points)
        self.assertIsNotNone(fit)
        alpha, beta = fit or (0.0, 0.0)
        self.assertAlmostEqual(alpha, 0.01, places=4)
        self.assertAlmostEqual(beta, 1.5, places=4)

    def test_build_estimation_points_returns_none_when_window_insufficient(self) -> None:
        result = build_estimation_points(["2025-01-01"] * 10, {}, {}, 5)
        self.assertIsNone(result)

    def test_compute_car_metrics_builds_values(self) -> None:
        common_dates = [f"2025-01-{i:02d}" for i in range(1, 10)]
        stock_returns = {day: 0.02 for day in common_dates}
        benchmark_returns = {day: 0.01 for day in common_dates}
        metrics, valid_any, has_max = compute_car_metrics(
            common_dates=common_dates,
            stock_returns=stock_returns,
            benchmark_returns=benchmark_returns,
            event_idx=3,
            alpha=0.0,
            beta=1.0,
            event_windows=[1, 3],
        )
        self.assertTrue(valid_any)
        self.assertTrue(has_max)
        self.assertEqual(metrics["car_w1"], "0.020000")


if __name__ == "__main__":
    unittest.main()
