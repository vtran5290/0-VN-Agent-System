"""Order journal — write-before-submit, duplicate detection, startup recovery."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.trading.brokers.hard_caps import MisconfigurationError
from src.trading.brokers.paper import PaperBroker
from src.trading.config import LiveTradingConfig, TradingConfig
from src.trading.models import OrderSide, OrderState, OrderProposal, Signal, save_proposals, proposals_path
from src.trading.oms.order_journal import (
    DuplicateOrderError,
    JournalStatus,
    OrphanOrderError,
    OrderJournal,
)
from src.trading.oms.order_manager import OrderManager
from src.trading.models import OrderState as OS


def _proposal(asof="2099-06-13"):
    sig = Signal(
        strategy="test",
        symbol="FPT",
        side=OrderSide.BUY.value,
        asof_date=asof,
        intended_price=50_000,
        quantity=100,
    )
    return OrderProposal(signal=sig, adv50_vnd=2_000_000_000, nav_vnd=1_000_000_000)


class TestOrderJournal(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.data_root = Path(self.tmp.name) / "trading"
        self.cfg = TradingConfig(
            live_trading=True,
            dry_run=False,
            data_root=self.data_root,
            initial_cash_vnd=500_000_000,
        )
        self.cfg.ensure_dirs()
        self._journals: list[OrderJournal] = []
        self._oms: list[OrderManager] = []

    def tearDown(self):
        for om in self._oms:
            om.close()
        for journal in self._journals:
            journal.close()
        self.tmp.cleanup()

    def _track_journal(self, journal: OrderJournal) -> OrderJournal:
        self._journals.append(journal)
        return journal

    def _track_om(self, om: OrderManager) -> OrderManager:
        self._oms.append(om)
        return om

    def test_write_before_submit_and_fill(self):
        journal = self._track_journal(OrderJournal(self.cfg.order_journal_path))
        order_id = "test|2099-06-13|FPT|BUY|50000.00|100"
        journal.write_pending(
            order_id, symbol="FPT", action="BUY", qty=100, price=50_000
        )
        pending = journal.get(order_id)
        self.assertEqual(pending.status, JournalStatus.PENDING)

        broker = PaperBroker(self.cfg)
        broker.login()
        bo = broker.place_order(
            {
                "symbol": "FPT",
                "side": "BUY",
                "quantity": 100,
                "price": 50_000,
                "idempotency_key": order_id,
            }
        )
        journal.mark_submitted(order_id, bo.broker_order_id, raw_response=bo.to_dict())
        journal.mark_filled(order_id, raw_response=bo.to_dict())
        filled = journal.get(order_id)
        self.assertEqual(filled.status, JournalStatus.FILLED)
        self.assertEqual(bo.state, OrderState.FILLED)

    def test_duplicate_detection(self):
        journal = self._track_journal(OrderJournal(self.cfg.order_journal_path))
        order_id = "dup-key"
        journal.write_pending(order_id, symbol="FPT", action="BUY", qty=10, price=1_000)
        journal.mark_submitted(order_id, "BROKER-1")
        with self.assertRaises(DuplicateOrderError):
            journal.write_pending(order_id, symbol="FPT", action="BUY", qty=10, price=1_000)

    def test_orphan_pending_blocks_resubmit(self):
        journal = self._track_journal(OrderJournal(self.cfg.order_journal_path))
        order_id = "orphan-key"
        journal.write_pending(order_id, symbol="FPT", action="BUY", qty=10, price=1_000)
        with self.assertRaises(OrphanOrderError):
            journal.assert_can_submit(order_id)

    def test_startup_recovery_flags_orphans(self):
        journal = self._track_journal(OrderJournal(self.cfg.order_journal_path))
        journal.write_pending("o1", symbol="FPT", action="BUY", qty=10, price=1_000)
        journal.write_pending("o2", symbol="VNM", action="BUY", qty=5, price=2_000)
        journal.mark_submitted("o2", "BR-2")
        journal.close()
        self._journals.remove(journal)

        om = self._track_om(OrderManager(self.cfg))
        self.assertEqual(len(om.recovery_orphans), 2)
        self.assertTrue(self.cfg.order_recovery_report_path.exists())
        report = self.cfg.order_recovery_report_path.read_text(encoding="utf-8")
        self.assertIn("o1", report)
        self.assertIn("o2", report)

    def test_oms_journal_integration_blocks_duplicate(self):
        prop = _proposal()
        asof = "2099-06-13"
        save_proposals(proposals_path(self.cfg.data_root, asof), [prop])

        om = self._track_om(OrderManager(self.cfg))
        reviewed = om.risk_review_proposals(asof)
        self.assertEqual(len(reviewed), 1)
        mo = reviewed[0]
        self.assertEqual(mo.state, OS.ORDER_READY)

        om.journal.write_pending(
            mo.idempotency_key,
            symbol="FPT",
            action="BUY",
            qty=100,
            price=50_000,
        )
        om.journal.mark_submitted(mo.idempotency_key, "ALREADY-SUBMITTED")

        live_cfg = LiveTradingConfig(
            live_trading=True,
            dry_run=False,
            data_root=self.data_root,
            mode="paper",
            initial_cash_vnd=500_000_000,
        )
        executed = om.execute_approved(
            asof,
            live_config=live_cfg,
            extra={
                "kill_switch": {"status": "CLEAR"},
                "reconciliation": {"BLOCK_NEW_ORDERS": False},
                "data_health": {"status": "PASS"},
            },
        )
        self.assertEqual(len(executed), 1)
        self.assertEqual(executed[0].state, OS.ERROR_REQUIRES_MANUAL_REVIEW)
        self.assertIn("already SUBMITTED", executed[0].error_message)

    def test_live_mode_requires_journal_for_hard_caps(self):
        cfg = LiveTradingConfig(
            live_trading=True,
            dry_run=False,
            data_root=self.data_root,
            mode="live_manual",
            broker="dnse",
            broker_hard_caps_enabled=True,
            initial_cash_vnd=500_000_000,
        )
        cfg.ensure_dirs()
        from src.trading.oms.order_manager import get_broker

        with self.assertRaises(MisconfigurationError) as ctx:
            get_broker(cfg, journal=None)
        self.assertIn("journal=None", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
