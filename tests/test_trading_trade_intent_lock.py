"""Trade intent lock tests."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.trading.config import LiveTradingConfig, TradingConfig
from src.trading.models import ManagedOrder, OrderProposal, OrderSide, OrderState, Signal
from src.trading.oms.idempotency import IdempotencyStore
from src.trading.oms.order_manager import OrderManager


class TestTradeIntentLock(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.cfg = LiveTradingConfig(
            data_root=Path(self.tmp.name) / "trading",
            initial_cash_vnd=1_000_000_000,
            allow_same_day_same_symbol_side=False,
        )
        self.cfg.ensure_dirs()
        self.om = OrderManager(self.cfg)

    def tearDown(self):
        self.tmp.cleanup()

    def _save_ready(self, sym, price, qty):
        sig = Signal("A3_DP", sym, OrderSide.BUY.value, "2099-01-01", price, qty)
        prop = OrderProposal(signal=sig, adv50_vnd=1e9, nav_vnd=1e9)
        mo = ManagedOrder(proposal=prop, state=OrderState.ORDER_READY)
        self.om.store.save(mo)
        return prop

    def test_same_side_date_different_price_blocked(self):
        live = self.cfg
        p1 = self._save_ready("FPT", 50_000, 100)
        blocked = self.om._trade_intent_blocked(
            OrderProposal(signal=Signal("A3_DP", "FPT", "BUY", "2099-01-01", 51_000, 100)),
            live,
        )
        self.assertIsNotNone(blocked)


if __name__ == "__main__":
    unittest.main()
