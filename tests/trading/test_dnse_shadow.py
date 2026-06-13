"""DNSE read-only shadow diff tests (mocked broker — no live credentials)."""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from src.trading.brokers.dnse import DNSEAuthError, DNSEBroker, LiveTradingDisabledError
from src.trading.brokers.dnse_shadow import (
    DNSEShadowRunner,
    compute_nav_divergence_pct,
    diff_positions,
)
from src.trading.config import LiveTradingConfig, TradingConfig


class TestDnseShadowDiff(unittest.TestCase):
    def test_clean_report_when_positions_match(self):
        unexpected, missing, mismatches = diff_positions(
            {"FPT": 100, "VNM": 200},
            {"FPT": 100, "VNM": 200},
        )
        self.assertEqual(unexpected, [])
        self.assertEqual(missing, [])
        self.assertEqual(mismatches, [])

    def test_qty_mismatch_detected(self):
        _, _, mismatches = diff_positions({"FPT": 150}, {"FPT": 100})
        self.assertEqual(len(mismatches), 1)
        self.assertEqual(mismatches[0]["symbol"], "FPT")
        self.assertEqual(mismatches[0]["dnse_qty"], 150)
        self.assertEqual(mismatches[0]["internal_qty"], 100)

    def test_unexpected_position_in_dnse(self):
        unexpected, missing, _ = diff_positions({"HPG": 500}, {})
        self.assertEqual(len(unexpected), 1)
        self.assertEqual(unexpected[0]["symbol"], "HPG")
        self.assertEqual(missing, [])

    def test_missing_position_in_dnse(self):
        unexpected, missing, _ = diff_positions({}, {"FPT": 100})
        self.assertEqual(unexpected, [])
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0]["symbol"], "FPT")

    def test_nav_divergence_calculation(self):
        pct = compute_nav_divergence_pct(1_003_000_000, 1_000_000_000)
        self.assertAlmostEqual(pct, 0.3, places=2)

    def test_shadow_runner_clean_report(self):
        tmp = TemporaryDirectory()
        try:
            data_root = Path(tmp.name) / "trading"
            cfg = LiveTradingConfig(data_root=data_root, shadow_dnse_enabled=True)
            cfg.ensure_dirs()
            positions_csv = cfg.paper_positions_path
            positions_csv.parent.mkdir(parents=True, exist_ok=True)
            positions_csv.write_text(
                "symbol,strategy,state,quantity,blended_entry,market_value_VND,unrealized_pnl,tp1_hit,signal_date\n"
                "FPT,A3_DP,NEW_T1,100,50000,5000000,0,False,2099-01-01\n",
                encoding="utf-8",
            )
            (cfg.live_dir / "portfolio_state.json").write_text(
                json.dumps({"nav_vnd": 1_000_000_000}),
                encoding="utf-8",
            )

            mock_broker = MagicMock(spec=DNSEBroker)
            mock_broker.login.return_value = {"status": "ok"}
            mock_broker.get_balances.return_value = {
                "cash_available_vnd": 995_000_000,
                "total_portfolio_value_vnd": 1_000_000_000,
                "margin_used_vnd": 0,
            }
            mock_broker.get_positions.return_value = [
                {"symbol": "FPT", "qty": 100, "quantity": 100},
            ]

            runner = DNSEShadowRunner(cfg, broker=mock_broker)
            report = runner.run("2099-01-15")
            self.assertEqual(report.status, "CLEAN")
            self.assertTrue(runner.report_path("2099-01-15").exists())
            self.assertIn("CLEAN", report.summary_line())
        finally:
            tmp.cleanup()

    def test_shadow_runner_mismatch_report(self):
        tmp = TemporaryDirectory()
        try:
            data_root = Path(tmp.name) / "trading"
            cfg = LiveTradingConfig(data_root=data_root)
            cfg.ensure_dirs()
            cfg.paper_positions_path.write_text(
                "symbol,quantity\nFPT,100\n",
                encoding="utf-8",
            )

            mock_broker = MagicMock(spec=DNSEBroker)
            mock_broker.login.return_value = {"status": "ok"}
            mock_broker.get_balances.return_value = {
                "total_portfolio_value_vnd": 900_000_000,
            }
            mock_broker.get_positions.return_value = [
                {"symbol": "FPT", "qty": 200},
            ]

            report = DNSEShadowRunner(cfg, broker=mock_broker).run("2099-01-16")
            self.assertEqual(report.status, "MISMATCH")
            self.assertEqual(len(report.qty_mismatches), 1)
        finally:
            tmp.cleanup()

    def test_auth_failed_writes_report_without_raising(self):
        tmp = TemporaryDirectory()
        try:
            cfg = TradingConfig(data_root=Path(tmp.name) / "trading")
            cfg.ensure_dirs()
            mock_broker = MagicMock(spec=DNSEBroker)
            mock_broker.login.side_effect = DNSEAuthError("bad credentials")

            report = DNSEShadowRunner(cfg, broker=mock_broker).run("2099-01-17")
            self.assertEqual(report.status, "AUTH_FAILED")
            self.assertIn("bad credentials", report.error)
            path = cfg.shadow_dir / "shadow_report_2099-01-17.json"
            self.assertTrue(path.exists())
        finally:
            tmp.cleanup()

    def test_dnse_broker_is_read_only(self):
        cfg = TradingConfig(data_root=Path("/tmp/trading"))
        broker = DNSEBroker(cfg)
        self.assertTrue(broker.is_read_only)
        with self.assertRaises(NotImplementedError):
            broker.cancel_order("x")
        with self.assertRaises(LiveTradingDisabledError):
            broker.place_order({"symbol": "FPT", "side": "BUY", "quantity": 100, "price": 1})

    def test_workflow_shadow_block_is_non_fatal(self):
        wf = (Path(__file__).resolve().parents[2] / "src" / "trading" / "live" / "workflow.py")
        source = wf.read_text(encoding="utf-8")
        self.assertIn("DNSE shadow step failed (non-fatal)", source)
        self.assertIn("shadow_dnse_enabled", source)


if __name__ == "__main__":
    unittest.main()
