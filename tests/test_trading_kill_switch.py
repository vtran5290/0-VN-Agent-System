"""Kill switch tests."""
import unittest

from src.trading.config import LiveTradingConfig, load_live_trading_config
from src.trading.models import RiskDecision
from src.trading.monitoring.kill_switch import evaluate_kill_switch
from src.trading.risk.live_rules import check_kill_switch


class TestKillSwitch(unittest.TestCase):
    def test_blocks_on_critical_health(self):
        cfg = LiveTradingConfig()
        ks = evaluate_kill_switch(cfg, {"status": "CRITICAL_FAIL"}, {})
        self.assertEqual(ks.status, "BLOCK")

    def test_kill_switch_blocks_when_enabled_by_default(self):
        cfg = LiveTradingConfig()
        self.assertTrue(cfg.block_on_kill_switch)
        ok, rule_id, msg, decision = check_kill_switch(
            {"kill_switch": {"status": "BLOCK", "reason": "operator halt"}},
            cfg,
        )
        self.assertFalse(ok)
        self.assertEqual(rule_id, "kill_switch")
        self.assertEqual(decision, RiskDecision.BLOCK)
        self.assertIn("halt", msg.lower())

    def test_kill_switch_passes_when_clear(self):
        cfg = LiveTradingConfig()
        ok, _, _, decision = check_kill_switch({"kill_switch": {"status": "CLEAR"}}, cfg)
        self.assertTrue(ok)
        self.assertEqual(decision, RiskDecision.PASS)

    def test_block_on_kill_switch_default_from_live_yaml(self):
        cfg = load_live_trading_config()
        self.assertTrue(cfg.block_on_kill_switch)

    def test_missing_kill_switch_extra_still_passes_when_clear(self):
        """No kill_switch key in extra — not treated as BLOCK."""
        cfg = LiveTradingConfig()
        ok, _, _, decision = check_kill_switch({}, cfg)
        self.assertTrue(ok)
        self.assertEqual(decision, RiskDecision.PASS)

    def test_advisory_only_when_block_disabled(self):
        cfg = LiveTradingConfig(block_on_kill_switch=False)
        ok, _, _, decision = check_kill_switch(
            {"kill_switch": {"status": "BLOCK", "reason": "test"}},
            cfg,
        )
        self.assertTrue(ok)
        self.assertEqual(decision, RiskDecision.PASS)


if __name__ == "__main__":
    unittest.main()
