"""Batch risk tests."""
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from src.trading.config import LiveTradingConfig
from src.trading.models import OrderProposal, OrderSide, Signal
from src.trading.risk.batch_context import apply_verdict_to_sim
from src.trading.risk.engine import RiskContext, RiskEngine
from src.trading.models import PortfolioState, Position, RiskDecision, RiskVerdict


def _prop(sym, price, qty, asof="2099-01-01"):
    return OrderProposal(
        signal=Signal("A3_DP", sym, OrderSide.BUY.value, asof, price, qty),
        adv50_vnd=1_000_000_000,
        nav_vnd=1_000_000_000,
    )


class TestBatchRisk(unittest.TestCase):
    def test_collective_cash_exceeded(self):
        cfg = LiveTradingConfig(
            max_order_value_vnd=600_000_000,
            max_position_pct_nav=0.50,
            initial_cash_vnd=500_000_000,
            data_root=Path("/tmp/x"),
        )
        engine = RiskEngine(cfg)
        port = PortfolioState("2099-01-01", cash_vnd=500_000_000, nav_vnd=1_000_000_000)
        p1 = _prop("FPT", 50_000, 5000)  # 250M — adv 1B keeps pct under 5% cap
        p1.adv50_vnd = 10_000_000_000
        v1 = engine.evaluate(p1, RiskContext(portfolio=port), live_config=cfg, extra={"data_health": {"status": "PASS"}, "kill_switch": {"status": "CLEAR"}, "reconciliation": {}})
        self.assertEqual(v1.decision, RiskDecision.PASS)
        apply_verdict_to_sim(port, p1, v1)
        p2 = _prop("HPG", 50_000, 6000)  # 300M > remaining cash
        v2 = engine.evaluate(p2, RiskContext(portfolio=port), live_config=cfg, extra={"data_health": {"status": "PASS"}, "kill_switch": {"status": "CLEAR"}, "reconciliation": {}})
        self.assertEqual(v2.decision, RiskDecision.BLOCK)


if __name__ == "__main__":
    unittest.main()
