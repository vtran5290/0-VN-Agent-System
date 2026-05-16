"""Paper broker unit tests."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.trading.brokers.paper import PaperBroker
from src.trading.config import TradingConfig
from src.trading.models import OrderSide, OrderState


class TestPaperBroker(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.cfg = TradingConfig(
            data_root=Path(self.tmp.name) / "trading",
            initial_cash_vnd=100_000_000,
        )
        self.cfg.ensure_dirs()
        self.broker = PaperBroker(self.cfg)

    def tearDown(self):
        self.tmp.cleanup()

    def test_place_order_creates_position(self):
        self.broker.login()
        order = {
            "symbol": "FPT",
            "side": OrderSide.BUY.value,
            "quantity": 100,
            "price": 50_000,
            "idempotency_key": "test-key-1",
        }
        bo = self.broker.place_order(order)
        self.assertEqual(bo.state, OrderState.FILLED)
        positions = self.broker.get_positions()
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0]["symbol"], "FPT")
        self.assertEqual(positions[0]["quantity"], 100)
        cash = self.broker.get_cash_balance()["cash_vnd"]
        self.assertAlmostEqual(cash, 100_000_000 - 100 * 50_000)


if __name__ == "__main__":
    unittest.main()
