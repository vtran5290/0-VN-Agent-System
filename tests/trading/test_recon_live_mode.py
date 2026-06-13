"""Recon fail-closed in live_manual/live_auto regardless of allow_missing_reconciliation."""
import unittest

from src.trading.config import LiveTradingConfig
from src.trading.live.recon_status import reconciliation_extra_for_mode


class TestReconLiveMode(unittest.TestCase):
    def _config(self, **kwargs) -> LiveTradingConfig:
        return LiveTradingConfig(
            allow_missing_reconciliation=True,
            **kwargs,
        )

    def test_live_manual_blocks_when_recon_missing(self):
        cfg = self._config()
        extra = reconciliation_extra_for_mode(cfg, "live_manual", persisted=None)
        self.assertTrue(extra["BLOCK_NEW_ORDERS"])
        self.assertEqual(extra["status"], "MISSING")

    def test_live_auto_blocks_when_recon_missing(self):
        cfg = self._config()
        extra = reconciliation_extra_for_mode(cfg, "live_auto", persisted=None)
        self.assertTrue(extra["BLOCK_NEW_ORDERS"])

    def test_paper_allows_missing_when_flag_true(self):
        cfg = self._config()
        extra = reconciliation_extra_for_mode(cfg, "paper", persisted=None)
        self.assertFalse(extra["BLOCK_NEW_ORDERS"])
        self.assertEqual(extra["status"], "MISSING")

    def test_dry_run_allows_missing_when_flag_true(self):
        cfg = self._config()
        extra = reconciliation_extra_for_mode(cfg, "dry_run", persisted=None)
        self.assertFalse(extra["BLOCK_NEW_ORDERS"])

    def test_oms_execute_blocked_in_live_manual_on_dirty_recon(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from src.trading.oms.order_manager import OrderManager

        tmp = TemporaryDirectory()
        try:
            data_root = Path(tmp.name) / "trading"
            cfg = LiveTradingConfig(
                live_trading=True,
                dry_run=False,
                data_root=data_root,
                mode="live_manual",
                allow_missing_reconciliation=True,
                initial_cash_vnd=500_000_000,
            )
            cfg.ensure_dirs()
            om = OrderManager(cfg)
            try:
                executed = om.execute_approved(
                "2099-01-15",
                live_config=cfg,
                extra={
                    "reconciliation": {"BLOCK_NEW_ORDERS": True, "status": "MISSING"},
                    "kill_switch": {"status": "CLEAR"},
                },
                )
                self.assertEqual(executed, [])
            finally:
                om.close()
        finally:
            tmp.cleanup()

    def test_workflow_source_contains_live_recon_guard(self):
        from pathlib import Path

        wf = (Path(__file__).resolve().parents[2] / "src" / "trading" / "live" / "workflow.py")
        source = wf.read_text(encoding="utf-8")
        self.assertIn("Reconciliation failure in live mode", source)
        self.assertIn('mode in ("live_manual", "live_auto")', source)

    def test_stale_recon_blocks_live_manual(self):
        cfg = self._config()
        yesterday = {"asof_date": "2099-01-14", "BLOCK_NEW_ORDERS": False, "has_issues": False}
        extra = reconciliation_extra_for_mode(
            cfg,
            "live_manual",
            yesterday,
            cycle_asof_date="2099-01-15",
        )
        self.assertTrue(extra["BLOCK_NEW_ORDERS"])
        self.assertEqual(extra["status"], "STALE")
        self.assertIn("stale", extra["reason"])

    def test_stale_recon_missing_asof_date_blocks(self):
        cfg = self._config()
        persisted = {"BLOCK_NEW_ORDERS": False, "has_issues": False}
        extra = reconciliation_extra_for_mode(
            cfg,
            "live_auto",
            persisted,
            cycle_asof_date="2099-01-15",
        )
        self.assertTrue(extra["BLOCK_NEW_ORDERS"])
        self.assertEqual(extra["status"], "STALE")

    def test_fresh_recon_passes_through(self):
        cfg = self._config()
        today = {"asof_date": "2099-01-15", "BLOCK_NEW_ORDERS": False, "has_issues": False}
        extra = reconciliation_extra_for_mode(
            cfg,
            "live_manual",
            today,
            cycle_asof_date="2099-01-15",
        )
        self.assertFalse(extra["BLOCK_NEW_ORDERS"])
        self.assertEqual(extra["asof_date"], "2099-01-15")


if __name__ == "__main__":
    unittest.main()
