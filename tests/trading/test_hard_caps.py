"""Broker-layer hard caps enforcement."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.trading.brokers.hard_caps import HardCapPolicy, HardCapViolationError
from src.trading.brokers.paper import PaperBroker
from src.trading.config import TradingConfig


class TestHardCaps(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.cfg = TradingConfig(
            data_root=Path(self.tmp.name) / "trading",
            initial_cash_vnd=500_000_000,
            broker_hard_caps_enabled=True,
            broker_max_order_value_vnd=10_000_000,
            broker_max_submissions_per_day=2,
        )
        self.cfg.ensure_dirs()

    def tearDown(self):
        self.tmp.cleanup()

    def test_hard_cap_blocks_oversized_order(self):
        policy = HardCapPolicy(
            enabled=True,
            max_order_value_vnd=10_000_000,
            max_submissions_per_day=10,
        )
        broker = PaperBroker(self.cfg, hard_cap_policy=policy)
        broker.login()
        with self.assertRaises(HardCapViolationError):
            broker.place_order(
                {
                    "symbol": "FPT",
                    "side": "BUY",
                    "quantity": 1000,
                    "price": 50_000,
                    "idempotency_key": "cap-test",
                }
            )

    def test_config_loads_broker_hard_caps(self):
        from src.trading.config import load_trading_config, REPO_ROOT

        cfg = load_trading_config(REPO_ROOT / "config" / "trading.yaml")
        policy = cfg.broker_hard_cap_policy()
        self.assertTrue(policy.enabled)
        self.assertEqual(policy.max_order_value_vnd, 50_000_000)
        self.assertEqual(policy.max_submissions_per_day, 3)

    def test_price_zero_raises_hard_cap_violation(self):
        policy = HardCapPolicy(enabled=True, max_order_value_vnd=50_000_000)
        with self.assertRaises(HardCapViolationError) as ctx:
            policy.enforce(
                {"symbol": "FPT", "quantity": 100, "price": 0, "order_type": "LO"},
                submissions_today=0,
            )
        self.assertIn("price=0", str(ctx.exception))

    def test_negative_price_raises_hard_cap_violation(self):
        policy = HardCapPolicy(enabled=True, max_order_value_vnd=50_000_000)
        with self.assertRaises(HardCapViolationError):
            policy.enforce(
                {"symbol": "FPT", "quantity": 100, "price": -1, "order_type": "LO"},
                submissions_today=0,
            )

    def test_market_order_types_rejected_at_adapter_layer(self):
        policy = HardCapPolicy(enabled=True, max_order_value_vnd=50_000_000)
        for order_type in ("ATO", "ATC", "MP", "MARKET"):
            with self.subTest(order_type=order_type):
                with self.assertRaises(HardCapViolationError) as ctx:
                    policy.enforce(
                        {
                            "symbol": "FPT",
                            "quantity": 100,
                            "price": 50_000,
                            "order_type": order_type,
                        },
                        submissions_today=0,
                    )
                self.assertIn("ATO/ATC", str(ctx.exception))

    def test_broker_blocks_price_zero_before_submit(self):
        policy = HardCapPolicy(enabled=True, max_order_value_vnd=50_000_000)
        broker = PaperBroker(self.cfg, hard_cap_policy=policy)
        broker.login()
        with self.assertRaises(HardCapViolationError):
            broker.place_order(
                {
                    "symbol": "FPT",
                    "side": "BUY",
                    "quantity": 100,
                    "price": 0,
                    "order_type": "LO",
                    "idempotency_key": "zero-price",
                }
            )

    def test_empty_whitelist_logs_warning(self):
        policy = HardCapPolicy(enabled=True, allowed_symbols=frozenset())
        with self.assertLogs("src.trading.brokers.hard_caps", level="WARNING") as logs:
            policy.log_startup_warnings()
        self.assertTrue(
            any("allowed_symbols is empty" in msg for msg in logs.output)
        )


if __name__ == "__main__":
    unittest.main()
