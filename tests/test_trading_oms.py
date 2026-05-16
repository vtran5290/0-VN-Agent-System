"""Order manager — duplicate prevention and LIVE_TRADING guard."""
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.trading.brokers.dnse import DNSEBroker, LiveTradingDisabledError
from src.trading.config import TradingConfig
from src.trading.models import (
    OrderProposal,
    OrderSide,
    OrderState,
    Signal,
    save_proposals,
    proposals_path,
)
from src.trading.oms.idempotency import IdempotencyStore
from src.trading.oms.order_manager import OrderManager


def _make_proposal(asof="2099-01-01"):
    sig = Signal(
        strategy="test",
        symbol="FPT",
        side=OrderSide.BUY.value,
        asof_date=asof,
        intended_price=50_000,
        quantity=100,
    )
    return OrderProposal(signal=sig, adv50_vnd=1_000_000_000, nav_vnd=1_000_000_000)


class TestTradingOMS(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.data_root = Path(self.tmp.name) / "trading"
        self.cfg = TradingConfig(
            live_trading=False,
            dry_run=True,
            data_root=self.data_root,
            initial_cash_vnd=1_000_000_000,
        )
        self.cfg.ensure_dirs()

    def tearDown(self):
        self.tmp.cleanup()

    def test_prevents_duplicate_order(self):
        prop = _make_proposal()
        asof = "2099-01-01"
        path = proposals_path(self.cfg.data_root, asof)
        save_proposals(path, [prop])

        om = OrderManager(self.cfg)
        first = om.risk_review_proposals(asof)
        second = om.risk_review_proposals(asof)

        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)
        # Same managed order returned, not duplicated on disk
        store = IdempotencyStore(self.cfg.orders_dir)
        files = list(self.cfg.orders_dir.glob("*.json"))
        self.assertEqual(len(files), 1)

    def test_live_trading_false_prevents_dnse_order(self):
        cfg = TradingConfig(
            broker="dnse",
            live_trading=False,
            dry_run=False,
            data_root=self.data_root,
        )
        broker = DNSEBroker(cfg)
        with self.assertRaises(LiveTradingDisabledError):
            broker.place_order(
                {"symbol": "FPT", "side": "BUY", "quantity": 100, "price": 50000}
            )

    def test_dnse_blocked_even_with_live_flag_without_confirm(self):
        cfg = TradingConfig(
            broker="dnse",
            live_trading=True,
            dry_run=False,
            confirm_live_broker="",
            data_root=self.data_root,
        )
        broker = DNSEBroker(cfg)
        self.assertFalse(cfg.live_dnse_orders_allowed())
        with self.assertRaises(LiveTradingDisabledError):
            broker.place_order(
                {"symbol": "FPT", "side": "BUY", "quantity": 100, "price": 50000}
            )


if __name__ == "__main__":
    unittest.main()
