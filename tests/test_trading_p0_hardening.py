"""P0 hardening patch tests."""
from __future__ import annotations

import json
import os
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.trading.brokers.dnse import DNSEBroker, LiveTradingDisabledError
from src.trading.config import LiveTradingConfig, TradingConfig
from src.trading.live.order_intent import ACTION_MAP, build_order_intents, intents_to_proposals
from src.trading.live.paper_ledger import PaperLedger
from src.trading.live.recon_status import reconciliation_extra_for_mode
from src.trading.live.run_lock import DailyRunLock, RunLockError
from src.trading.live.scan_resolver import resolve_scan
from src.trading.models import ManagedOrder, OrderProposal, OrderSide, OrderState, Signal, save_proposals, proposals_path
from src.trading.oms.order_manager import OrderManager
from src.trading.risk.batch_context import BatchRiskReviewer, _proposal_order
from src.trading.risk.engine import RiskContext, RiskEngine
from src.trading.models import PortfolioState, RiskDecision


FIXTURES = Path(__file__).parent / "fixtures" / "trading"
SAMPLE = FIXTURES / "sample_scan.csv"
SAMPLE_EXITS = FIXTURES / "sample_scan_exits.csv"


class TestScanResolver(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.cfg = LiveTradingConfig(
            data_root=Path(self.tmp.name) / "trading",
            allow_sample_scan=False,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_cli_path_wins(self):
        r = resolve_scan(self.cfg, "2099-01-01", cli_scan_path=SAMPLE, test_mode=True)
        self.assertEqual(r.resolved_scan_source, "cli")
        self.assertEqual(r.path, SAMPLE)

    def test_sample_blocked_without_flag(self):
        r = resolve_scan(self.cfg, "2099-01-01", cli_scan_path=SAMPLE, test_mode=False)
        self.assertTrue(r.blocked)
        self.assertTrue(r.is_sample)

    def test_sample_still_blocked_for_non_legacy_even_with_flag(self):
        self.cfg.allow_sample_scan = True
        r = resolve_scan(self.cfg, "2099-01-01", cli_scan_path=SAMPLE, test_mode=False)
        self.assertTrue(r.blocked)

    def test_latest_phase36_over_phase34(self):
        search = Path(self.tmp.name) / "missing_work"
        search.mkdir(parents=True)
        (search / "phase34_old.csv").write_text("as_of_date,symbol,final_action\n2099-01-01,X,WATCH_ONLY\n", encoding="utf-8")
        p36 = search / "phase36_daily_scan.csv"
        shutil.copy(SAMPLE, p36)
        self.cfg.scan_csv_path = search / "nonexistent.csv"
        r = resolve_scan(self.cfg, "2099-01-01", test_mode=True, search_dir=search)
        self.assertEqual(r.resolved_scan_source, "latest")
        self.assertEqual(r.path.name, "phase36_daily_scan.csv")


class TestSellExits(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.cfg = LiveTradingConfig(
            data_root=Path(self.tmp.name) / "trading",
            allow_sample_scan=True,
            scan_csv_path=SAMPLE_EXITS,
        )
        self.cfg.ensure_dirs()
        self.ledger = PaperLedger(self.cfg)
        self.ledger.open_T1("FPT", "2099-01-02", 100_000, 250_000_000, 2500)

    def tearDown(self):
        self.tmp.cleanup()

    def test_action_map_sell(self):
        self.assertEqual(ACTION_MAP["TP1_PARTIAL"][0], "SELL_TP1")
        self.assertEqual(ACTION_MAP["TRAIL_EXIT"][0], "SELL_EXIT")

    def test_tp1_maps_sell(self):
        intents = build_order_intents(
            self.cfg, "2099-01-02", {"BLOCK_ORDER_GENERATION": False},
            ledger=self.ledger, test_mode=True,
        )
        fpt = intents[intents["symbol"] == "FPT"]
        self.assertEqual(fpt.iloc[0]["action"], "SELL_TP1")
        self.assertEqual(fpt.iloc[0]["side"], "SELL")

    def test_exit_no_position_skip(self):
        empty_cfg = LiveTradingConfig(
            data_root=Path(self.tmp.name) / "trading_empty",
            allow_sample_scan=True,
            scan_csv_path=SAMPLE_EXITS,
        )
        empty_cfg.ensure_dirs()
        intents = build_order_intents(
            empty_cfg, "2099-01-02", {"BLOCK_ORDER_GENERATION": False},
            ledger=PaperLedger(empty_cfg),
            test_mode=True,
        )
        fpt = intents[intents["symbol"] == "FPT"]
        self.assertIn(fpt.iloc[0]["action"], ("SKIP_NO_POSITION", "RECON_REQUIRED"))


class TestReconciliationGating(unittest.TestCase):
    def test_dirty_recon_blocks(self):
        cfg = LiveTradingConfig(require_reconciliation_clean=True)
        extra = reconciliation_extra_for_mode(
            cfg, "paper",
            {"BLOCK_NEW_ORDERS": True, "has_issues": True},
        )
        engine = RiskEngine(cfg)
        prop = OrderProposal(
            signal=Signal("A3_DP", "FPT", "BUY", "2099-01-01", 50_000, 100),
            nav_vnd=1e9,
        )
        v = engine.evaluate(
            prop,
            RiskContext(portfolio=PortfolioState("2099-01-01", 1e9, 1e9)),
            live_config=cfg,
            extra={"data_health": {"status": "PASS"}, "kill_switch": {"status": "CLEAR"}, "reconciliation": extra},
        )
        self.assertEqual(v.decision, RiskDecision.BLOCK)


class TestPaperExecution(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.cfg = LiveTradingConfig(
            data_root=Path(self.tmp.name) / "trading",
            mode="paper",
            live_trading=True,
            dry_run=False,
            allow_sample_scan=True,
            scan_csv_path=SAMPLE,
        )
        self.cfg.ensure_dirs()
        self.om = OrderManager(self.cfg)
        self.ledger = PaperLedger(self.cfg)

    def tearDown(self):
        self.tmp.cleanup()

    def _ready_order(self):
        sig = Signal(
            "A3_DP", "FPT", "BUY", "2099-01-01", 50_000, 100,
            metadata={"action": "BUY_T1", "tier": "T1"},
        )
        prop = OrderProposal(signal=sig, adv50_vnd=1e9, nav_vnd=1e9)
        from src.trading.models import RiskVerdict
        mo = ManagedOrder(proposal=prop, state=OrderState.ORDER_READY)
        mo.risk_verdict = RiskVerdict(passed=True, decision=RiskDecision.PASS)
        self.om.store.save(mo)
        save_proposals(proposals_path(self.cfg.data_root, "2099-01-01"), [prop])
        return prop

    def test_paper_mode_fills_and_ledger(self):
        self._ready_order()
        extra = {
            "data_health": {"status": "PASS", "BLOCK_ORDER_GENERATION": False},
            "kill_switch": {"status": "CLEAR"},
            "reconciliation": {"BLOCK_NEW_ORDERS": False},
        }
        out = self.om.execute_approved("2099-01-01", live_config=self.cfg, extra=extra, paper_ledger=self.ledger)
        self.assertTrue(any(o.state == OrderState.FILLED for o in out))
        self.assertTrue(self.ledger.trades_path.exists())

    def test_dry_run_no_ledger(self):
        self.cfg.mode = "dry_run"
        self.cfg.dry_run = True
        self._ready_order()
        out = self.om.execute_approved("2099-01-01", live_config=self.cfg, paper_ledger=self.ledger)
        self.assertFalse(
            self.ledger.trades_path.exists()
            and self.ledger.trades_path.stat().st_size > 0
        )


class TestRunLock(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.cfg = LiveTradingConfig(data_root=Path(self.tmp.name) / "trading")
        self.cfg.ensure_dirs()
        self.lock = DailyRunLock(self.cfg)

    def tearDown(self):
        self.tmp.cleanup()

    def test_duplicate_run_blocked(self):
        self.lock.acquire("2099-01-01", "paper")
        with self.assertRaises(RunLockError):
            self.lock.acquire("2099-01-01", "paper")


class TestBatchIntentLock(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.cfg = LiveTradingConfig(
            data_root=Path(self.tmp.name) / "trading",
            allow_same_day_same_symbol_side=False,
        )
        self.cfg.ensure_dirs()
        self.om = OrderManager(self.cfg)

    def tearDown(self):
        self.tmp.cleanup()

    def test_batch_duplicate_intent(self):
        p1 = OrderProposal(
            signal=Signal("A3_DP", "FPT", "BUY", "2099-01-01", 50_000, 100, metadata={"intent_sequence": 0}),
            adv50_vnd=1e9, nav_vnd=1e9,
        )
        p2 = OrderProposal(
            signal=Signal("A3_DP", "FPT", "BUY", "2099-01-01", 51_000, 100, metadata={"intent_sequence": 1}),
            adv50_vnd=1e9, nav_vnd=1e9,
        )
        reviewer = BatchRiskReviewer(self.cfg, self.om)
        results = reviewer.risk_review_batch(
            "2099-01-01", [p1, p2],
            {"data_health": {"status": "PASS"}, "kill_switch": {"status": "CLEAR"}, "reconciliation": {}},
        )
        decisions = [r.risk_verdict.decision for r in results if r.risk_verdict]
        self.assertIn(RiskDecision.BLOCK, decisions)


class TestPreSubmitSelf(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.cfg = LiveTradingConfig(data_root=Path(self.tmp.name) / "trading", mode="paper", dry_run=False, live_trading=True)
        self.cfg.ensure_dirs()
        self.om = OrderManager(self.cfg)

    def tearDown(self):
        self.tmp.cleanup()

    def test_self_does_not_block(self):
        sig = Signal("A3_DP", "FPT", "BUY", "2099-01-01", 50_000, 100)
        prop = OrderProposal(signal=sig, adv50_vnd=1e9, nav_vnd=1e9)
        mo = ManagedOrder(proposal=prop, state=OrderState.ORDER_READY)
        blocked, _, _ = self.om.check_trade_intent_blocked(prop, self.cfg, exclude_idempotency_key=mo.idempotency_key)
        self.assertFalse(blocked)


class TestStrategyContract(unittest.TestCase):
    def test_breadth_manual_review_in_map(self):
        self.assertEqual(ACTION_MAP["NEW_T1_MANUAL_REVIEW_BREADTH"][0], "BUY_T1_MANUAL_REVIEW")

    def test_a3_dual_active_not_s3_shadow(self):
        self.tmp = TemporaryDirectory()
        cfg = LiveTradingConfig(
            data_root=Path(self.tmp.name) / "trading",
            allow_sample_scan=True,
            scan_csv_path=SAMPLE,
        )
        intents = build_order_intents(cfg, "2099-01-01", {"BLOCK_ORDER_GENERATION": False}, test_mode=True)
        ssi = intents[intents["symbol"] == "SSI"]
        self.assertNotIn(ssi.iloc[0]["action"], ("PAPER_S3_SHADOW", "BUY_T1"))
        self.tmp.cleanup()

    def test_dnse_blocked(self):
        cfg = TradingConfig(broker="dnse", live_trading=True, dry_run=False, confirm_live_broker="DNSE")
        b = DNSEBroker(cfg)
        with self.assertRaises((LiveTradingDisabledError, NotImplementedError)):
            b.place_order({"symbol": "FPT", "side": "BUY", "quantity": 1, "price": 1})


class TestBatchOrderPreserve(unittest.TestCase):
    def test_intent_sequence_order(self):
        p_high = OrderProposal(
            signal=Signal("A3_DP", "AAA", "BUY", "2099-01-01", 1, 1, metadata={"intent_sequence": 0}),
        )
        p_low = OrderProposal(
            signal=Signal("A3_DP", "ZZZ", "BUY", "2099-01-01", 1, 1, metadata={"intent_sequence": 1}),
        )
        ordered = _proposal_order([p_low, p_high])
        self.assertEqual(ordered[0].signal.symbol, "AAA")


if __name__ == "__main__":
    unittest.main()
