"""P0.1 hardening tests."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.trading.config import LiveTradingConfig
from src.trading.live.order_intent import build_order_intents
from src.trading.live.paper_ledger import PaperLedger
from src.trading.live.manual_review import intent_execution_allowed, sync_queue_from_intents
from src.trading.live.scan_resolver import resolve_scan
from src.trading.models import OrderProposal, OrderSide, PortfolioState, Position, Signal
from src.trading.risk.engine import RiskContext, RiskEngine
from src.trading.models import RiskDecision

FIXTURES = Path(__file__).parent / "fixtures" / "trading"
SAMPLE = FIXTURES / "sample_scan.csv"
E2E_SCAN = FIXTURES / "sample_scan_e2e.csv"


class TestA3ProductionGate(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.cfg = LiveTradingConfig(
            data_root=Path(self.tmp.name) / "trading",
            allow_sample_scan=True,
            scan_csv_path=E2E_SCAN,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_a3_production_new_t1(self):
        intents = build_order_intents(self.cfg, "2099-03-01", {"BLOCK_ORDER_GENERATION": False}, test_mode=True)
        fpt = intents[intents["symbol"] == "FPT"]
        self.assertEqual(fpt.iloc[0]["action"], "BUY_T1")

    def test_empty_classification_blocked(self):
        scan_path = Path(self.tmp.name) / "bad.csv"
        scan_path.write_text(
            "as_of_date,symbol,close_kVND,a3_active,strategy_classification,final_action,"
            "in_a3_universe,liq_warn_T1,regime_bull,adv50_B_VND,target_T1_M\n"
            "2099-03-01,ZZZ,100,True,,NEW_T1,True,OK,True,500,250\n",
            encoding="utf-8",
        )
        self.cfg.scan_csv_path = scan_path
        intents = build_order_intents(self.cfg, "2099-03-01", {"BLOCK_ORDER_GENERATION": False}, test_mode=True)
        zzz = intents[intents["symbol"] == "ZZZ"]
        self.assertEqual(zzz.iloc[0]["action"], "SKIP_NON_PRODUCTION_CLASSIFICATION")

    def test_a3_research_no_buy(self):
        intents = build_order_intents(self.cfg, "2099-03-01", {"BLOCK_ORDER_GENERATION": False}, test_mode=True)
        vnm = intents[intents["symbol"] == "VNM"]
        self.assertNotIn(vnm.iloc[0]["action"], ("BUY_T1", "BUY_T2"))


class TestSellRiskPath(unittest.TestCase):
    def test_sell_passes_large_order_value(self):
        cfg = LiveTradingConfig(max_order_value_vnd=100_000, sell_exit_liquidity_policy="off")
        engine = RiskEngine(cfg)
        port = PortfolioState("2099-01-01", 1e9, 1e9, positions=[
            Position("FPT", 10000, 50_000, 500_000_000),
        ])
        prop = OrderProposal(
            signal=Signal("A3_DP", "FPT", "SELL", "2099-01-01", 50_000, 100, metadata={"action": "SELL_EXIT"}),
            adv50_vnd=1e9,
            nav_vnd=1e9,
        )
        v = engine.evaluate(
            prop, RiskContext(portfolio=port), live_config=cfg,
            extra={"data_health": {"status": "PASS"}, "kill_switch": {"status": "CLEAR"}, "reconciliation": {}},
        )
        self.assertIn(v.decision, (RiskDecision.PASS, RiskDecision.MANUAL_REVIEW))
        self.assertNotEqual(v.decision, RiskDecision.BLOCK)

    def test_buy_still_blocked_by_max_order(self):
        cfg = LiveTradingConfig(max_order_value_vnd=100_000)
        engine = RiskEngine(cfg)
        port = PortfolioState("2099-01-01", 1e9, 1e9)
        prop = OrderProposal(
            signal=Signal("A3_DP", "FPT", "BUY", "2099-01-01", 50_000, 5000),
            adv50_vnd=1e9,
            nav_vnd=1e9,
        )
        v = engine.evaluate(
            prop, RiskContext(portfolio=port), live_config=cfg,
            extra={"data_health": {"status": "PASS"}, "kill_switch": {"status": "CLEAR"}, "reconciliation": {}},
        )
        self.assertEqual(v.decision, RiskDecision.BLOCK)


class TestBuildIntentsSafety(unittest.TestCase):
    def test_sample_blocked_without_flag(self):
        cfg = LiveTradingConfig(allow_sample_scan=False)
        r = resolve_scan(cfg, "2099-01-01", cli_scan_path=SAMPLE, test_mode=False)
        self.assertTrue(r.blocked)


class TestManualReview(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.cfg = LiveTradingConfig(
            data_root=Path(self.tmp.name) / "trading",
            require_manual_review_approval=True,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_unapproved_manual_review_blocked(self):
        row = {"requires_manual_review": True, "approved": False, "rejected": False}
        ok, reason = intent_execution_allowed(row, self.cfg)
        self.assertFalse(ok)
        self.assertEqual(reason, "manual_review_pending")


class TestTp1Pnl(unittest.TestCase):
    def test_partial_realized_pnl(self):
        tmp = TemporaryDirectory()
        cfg = LiveTradingConfig(data_root=Path(tmp.name) / "trading")
        ledger = PaperLedger(cfg)
        ledger.open_T1("FPT", "2099-01-01", 100_000, 250_000_000, 2500)
        ledger.apply_sell_tp1("FPT", "2099-01-02", 118_000, 1250)
        trades = ledger._load_trades()
        pnl = float(trades.iloc[0]["realized_pnl"])
        self.assertGreater(pnl, 0)
        self.assertEqual(ledger.get_a3_position_qty("FPT"), 1250)
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
