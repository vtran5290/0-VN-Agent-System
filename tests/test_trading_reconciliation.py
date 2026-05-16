"""Reconciliation unit tests."""
import json
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from src.trading.brokers.paper import PaperBroker
from src.trading.config import TradingConfig
from src.trading.models import (
    ManagedOrder,
    OrderProposal,
    OrderSide,
    OrderState,
    Signal,
)
from src.trading.oms.idempotency import IdempotencyStore
from src.trading.oms.order_manager import OrderManager
from src.trading.reconciliation.reconciler import Reconciler


class TestTradingReconciliation(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.data_root = Path(self.tmp.name) / "trading"
        self.cfg = TradingConfig(
            data_root=self.data_root,
            initial_cash_vnd=1_000_000_000,
        )
        self.cfg.ensure_dirs()
        self.broker = PaperBroker(self.cfg)
        self.broker.login()
        self.om = OrderManager(self.cfg, broker=self.broker)

    def tearDown(self):
        self.tmp.cleanup()

    def test_detects_position_mismatch(self):
        # Broker has manual position not in OMS expected
        state = self.broker._state
        state["positions"]["HPG"] = {"quantity": 500, "avg_price": 25000}
        self.broker._save_state()

        recon = Reconciler(self.cfg, self.broker, self.om)
        report = recon.run("2026-05-15")

        self.assertTrue(report.has_issues())
        unexpected = [p for p in report.unexpected_positions if p["symbol"] == "HPG"]
        self.assertTrue(len(unexpected) >= 1)
        self.assertEqual(unexpected[0]["type"], "unexpected_broker_position")


if __name__ == "__main__":
    unittest.main()
