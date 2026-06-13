"""Kill switch / HALT_LIVE blocks at broker submission layer."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.trading.brokers.hard_caps import HaltSignalError
from src.trading.brokers.paper import PaperBroker
from src.trading.config import REPO_ROOT, TradingConfig


class TestKillSwitchSubmission(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.data_root = Path(self.tmp.name) / "trading"
        self.cfg = TradingConfig(
            data_root=self.data_root,
            initial_cash_vnd=100_000_000,
        )
        self.cfg.ensure_dirs()
        self.halt_path = REPO_ROOT / "HALT_LIVE"
        self._had_halt = self.halt_path.exists()
        self._prior_content = None
        if self._had_halt:
            self._prior_content = self.halt_path.read_text(encoding="utf-8")

    def tearDown(self):
        if self._had_halt:
            self.halt_path.write_text(self._prior_content or "", encoding="utf-8")
        elif self.halt_path.exists():
            self.halt_path.unlink()
        self.tmp.cleanup()

    def test_halt_live_blocks_before_broker_fill(self):
        self.halt_path.write_text("fire drill", encoding="utf-8")
        broker = PaperBroker(self.cfg, check_halt_file=True)
        broker.login()
        order = {
            "symbol": "FPT",
            "side": "BUY",
            "quantity": 100,
            "price": 50_000,
            "idempotency_key": "halt-test",
        }
        with self.assertRaises(HaltSignalError) as ctx:
            broker.place_order(order)
        self.assertIn("HALT_LIVE", str(ctx.exception))
        positions = broker.get_positions()
        self.assertEqual(len(positions), 0)

    def test_kill_switch_status_blocks_at_submission(self):
        broker = PaperBroker(
            self.cfg,
            kill_switch={"status": "BLOCK", "reasons": ["test_block"]},
        )
        broker.login()
        with self.assertRaises(HaltSignalError) as ctx:
            broker.place_order(
                {
                    "symbol": "FPT",
                    "side": "BUY",
                    "quantity": 10,
                    "price": 50_000,
                    "idempotency_key": "ks-test",
                }
            )
        self.assertIn("kill_switch", str(ctx.exception))

    def test_paper_broker_default_unchanged_without_halt(self):
        if self.halt_path.exists():
            self.halt_path.unlink()
        broker = PaperBroker(self.cfg)
        broker.login()
        bo = broker.place_order(
            {
                "symbol": "FPT",
                "side": "BUY",
                "quantity": 10,
                "price": 50_000,
                "idempotency_key": "normal-test",
            }
        )
        self.assertEqual(bo.filled_quantity, 10)


if __name__ == "__main__":
    unittest.main()
