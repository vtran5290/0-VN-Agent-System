"""Risk engine unit tests."""
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from src.trading.config import TradingConfig
from src.trading.models import OrderProposal, OrderSide, PortfolioState, Signal
from src.trading.risk.engine import RiskContext, RiskEngine


def _proposal(symbol="FPT", price=100_000, qty=100, adv=1_000_000_000):
    sig = Signal(
        strategy="test",
        symbol=symbol,
        side=OrderSide.BUY.value,
        asof_date="2099-01-01",
        intended_price=price,
        quantity=qty,
    )
    return OrderProposal(signal=sig, adv50_vnd=adv, nav_vnd=1_000_000_000)


class TestTradingRisk(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.cfg = TradingConfig(
            max_order_value_vnd=10_000_000,
            min_adv50_vnd=500_000_000,
            max_order_pct_adv50=0.05,
            data_root=Path(self.tmp.name) / "trading",
        )
        self.engine = RiskEngine(self.cfg)
        self.portfolio = PortfolioState(
            asof_date="2099-01-01",
            cash_vnd=1_000_000_000,
            nav_vnd=1_000_000_000,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_rejects_oversized_order(self):
        # 100k * 200 = 20M > 10M max
        prop = _proposal(price=100_000, qty=200)
        verdict = self.engine.evaluate(prop, RiskContext(portfolio=self.portfolio))
        self.assertFalse(verdict.passed)
        self.assertIn("max_order_value_vnd", verdict.rule_ids)

    def test_rejects_illiquid_ticker(self):
        prop = _proposal(adv=100_000_000)  # below 500M min
        verdict = self.engine.evaluate(prop, RiskContext(portfolio=self.portfolio))
        self.assertFalse(verdict.passed)
        self.assertIn("min_adv50_vnd", verdict.rule_ids)


if __name__ == "__main__":
    unittest.main()
