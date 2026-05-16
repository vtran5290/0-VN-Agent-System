"""Kill switch tests."""
import unittest
from src.trading.config import LiveTradingConfig
from src.trading.monitoring.kill_switch import evaluate_kill_switch


class TestKillSwitch(unittest.TestCase):
    def test_blocks_on_critical_health(self):
        cfg = LiveTradingConfig()
        ks = evaluate_kill_switch(cfg, {"status": "CRITICAL_FAIL"}, {})
        self.assertEqual(ks.status, "BLOCK")


if __name__ == "__main__":
    unittest.main()
