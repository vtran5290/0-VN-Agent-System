"""Stale market data rule tests."""
import unittest

from src.trading.config import TradingConfig
from src.trading.models import OrderProposal, OrderSide, Signal
from src.trading.risk.engine import RiskContext, RiskEngine
from src.trading.models import PortfolioState


class TestStaleData(unittest.TestCase):
    def test_panel_date_match_passes(self):
        cfg = TradingConfig(market_data_max_age_hours=1)
        engine = RiskEngine(cfg)
        prop = OrderProposal(
            signal=Signal(
                "A3_DP", "FPT", OrderSide.BUY.value, "2020-01-01", 50_000, 100,
                metadata={"latest_panel_date": "2020-01-01"},
            ),
            adv50_vnd=1e9,
            nav_vnd=1e9,
        )
        v = engine.evaluate(prop, RiskContext(PortfolioState("2020-01-01", 1e9, 1e9)))
        self.assertTrue(v.passed)


if __name__ == "__main__":
    unittest.main()
