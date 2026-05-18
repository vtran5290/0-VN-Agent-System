"""Paper account infrastructure tests."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

from src.trading.config import REPO_ROOT
from src.trading.live.paper_accounts import (
    build_live_config_for_account,
    get_paper_account,
    initialize_paper_account,
    list_paper_accounts,
    load_paper_accounts_config,
    resolve_account_paths,
)
from src.trading.live.paper_ledger import PaperLedger
from src.trading.live.run_lock import DailyRunLock, RunLockError
from src.trading.live.s3_shadow_paper_ledger import S3ShadowPaperLedger
from src.trading.live.data_health import DataHealthResult

FIXTURES = Path(__file__).parent / "fixtures" / "trading"
E2E_SCAN = FIXTURES / "sample_scan_e2e.csv"


def _mock_health(*_a, **_k):
    return DataHealthResult(
        status="PASS",
        block_order_generation=False,
        latest_panel_date="2099-03-01",
    )


class TestPaperAccountsConfig(unittest.TestCase):
    def test_default_accounts_load(self):
        raw = load_paper_accounts_config()
        ids = list((raw.get("paper_accounts") or {}).keys())
        self.assertIn("A3_PROD_PAPER_5B", ids)
        self.assertIn("A3_DSE_PILOT_PAPER_SMALL", ids)
        self.assertIn("A3_SCALE_PAPER_10B", ids)
        self.assertIn("A3_SCALE_PAPER_20B", ids)
        self.assertIn("S3_MAX60_SHADOW_PAPER", ids)

    def test_paths_under_live_not_paper_trade(self):
        for pa in list_paper_accounts():
            root = str(pa.resolve_ledger_root())
            self.assertIn("data/trading/live", root.replace("\\", "/"))
            self.assertNotIn("data/paper_trade", root.replace("\\", "/"))

    def test_s3_shadow_path(self):
        acct = get_paper_account("S3_MAX60_SHADOW_PAPER")
        root = str(acct.resolve_ledger_root()).replace("\\", "/")
        self.assertTrue(root.endswith("data/trading/live/s3_shadow") or root.endswith("s3_shadow"))


class TestPaperAccountInit(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name) / "A3_TEST"

    def tearDown(self):
        self.tmp.cleanup()

    def test_init_creates_files(self):
        paths = initialize_paper_account(
            "A3_PROD_PAPER_5B",
            ledger_root_override=self.root,
        )
        self.assertTrue(paths["paper_trades"].exists())
        self.assertTrue(paths["paper_broker_state"].exists())
        paths2 = initialize_paper_account(
            "A3_PROD_PAPER_5B",
            ledger_root_override=self.root,
        )
        self.assertTrue(paths2["paper_trades"].exists())

    def test_reset_requires_confirm(self):
        with self.assertRaises(ValueError):
            initialize_paper_account("A3_PROD_PAPER_5B", reset=True, confirm_reset=False)


class TestAccountScopedWorkflow(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.date = "2099-03-02"
        self.root5b = Path(self.tmp.name) / "A3_PROD"
        self.root_small = Path(self.tmp.name) / "A3_SMALL"

    def tearDown(self):
        self.tmp.cleanup()

    @patch("src.trading.live.workflow.run_data_health", _mock_health)
    def test_separate_ledgers_no_cross_contamination(self):
        from src.trading.live.workflow import run

        r1 = run(
            "paper",
            self.date,
            account_id="A3_PROD_PAPER_5B",
            ledger_root_override=self.root5b,
            scan_path=E2E_SCAN,
            test_mode=True,
        )
        r2 = run(
            "paper",
            self.date,
            account_id="A3_DSE_PILOT_PAPER_SMALL",
            ledger_root_override=self.root_small,
            scan_path=E2E_SCAN,
            test_mode=True,
        )
        self.assertFalse(r1.get("aborted"))
        self.assertFalse(r2.get("aborted"))
        ymd = self.date.replace("-", "")
        self.assertTrue((self.root5b / f"order_intents_{ymd}.csv").exists())
        self.assertTrue((self.root_small / f"order_intents_{ymd}.csv").exists())
        self.assertNotEqual(
            (self.root5b / "run_manifests").resolve(),
            (self.root_small / "run_manifests").resolve(),
        )

    @patch("src.trading.live.workflow.run_data_health", _mock_health)
    def test_same_account_duplicate_blocked(self):
        from src.trading.live.workflow import run

        run(
            "paper",
            self.date,
            account_id="A3_PROD_PAPER_5B",
            ledger_root_override=self.root5b,
            scan_path=E2E_SCAN,
            test_mode=True,
        )
        r2 = run(
            "paper",
            self.date,
            account_id="A3_PROD_PAPER_5B",
            ledger_root_override=self.root5b,
            scan_path=E2E_SCAN,
            test_mode=True,
        )
        self.assertTrue(r2.get("aborted"))

    @patch("src.trading.live.workflow.run_data_health", _mock_health)
    def test_different_accounts_same_date_not_blocked(self):
        from src.trading.live.workflow import run

        run(
            "paper",
            self.date,
            account_id="A3_PROD_PAPER_5B",
            ledger_root_override=self.root5b,
            scan_path=E2E_SCAN,
            test_mode=True,
        )
        r2 = run(
            "paper",
            self.date,
            account_id="A3_DSE_PILOT_PAPER_SMALL",
            ledger_root_override=self.root_small,
            scan_path=E2E_SCAN,
            test_mode=True,
        )
        self.assertFalse(r2.get("aborted"))


class TestAccountRiskLimits(unittest.TestCase):
    def test_small_account_stricter_limits(self):
        cfg5b, a5 = build_live_config_for_account("A3_PROD_PAPER_5B")
        cfg_s, a_s = build_live_config_for_account("A3_DSE_PILOT_PAPER_SMALL")
        self.assertGreater(cfg5b.max_order_value_vnd, cfg_s.max_order_value_vnd)
        self.assertGreater(cfg5b.max_slots, cfg_s.max_slots)
        self.assertEqual(cfg_s.max_daily_new_positions, 1)


class TestCloseTradePnl(unittest.TestCase):
    def test_close_trade_no_undefined_pnl(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg, _ = build_live_config_for_account(
                "A3_PROD_PAPER_5B", ledger_root_override=root
            )
            ledger = PaperLedger(cfg)
            ledger.open_T1("AAA", "2099-01-01", 10000.0, 50_000_000, 5000)
            tid = ledger.find_open_trade_id("AAA")
            self.assertIsNotNone(tid)
            ledger.close_trade(tid, "2099-01-02", 11000.0, reason="test")
            trades = ledger._load_trades()
            row = trades[trades["trade_id"] == tid].iloc[0]
            self.assertEqual(row["state"], "CLOSED")
            self.assertGreater(float(row["realized_pnl"]), 0)


class TestRunLockAccountScoped(unittest.TestCase):
    def test_lock_paths_include_account(self):
        cfg, _ = build_live_config_for_account("A3_PROD_PAPER_5B")
        with TemporaryDirectory() as tmp:
            cfg.account_root = Path(tmp)
            cfg.account_id = "A3_PROD_PAPER_5B"
            lock = DailyRunLock(cfg)
            p1 = lock._lock_path("2099-01-01", "paper", "A3_PROD_PAPER_5B")
            p2 = lock._lock_path("2099-01-01", "paper", "A3_DSE_PILOT_PAPER_SMALL")
            self.assertNotEqual(p1.name, p2.name)


class TestS3ShadowSeparate(unittest.TestCase):
    def test_s3_flag_required(self):
        ledger = S3ShadowPaperLedger()
        with self.assertRaises(ValueError):
            ledger.record_shadow_intent({"symbol": "XYZ", "date": "2099-01-01", "s3_no_real_order_flag": False})

    def test_s3_root_under_live(self):
        ledger = S3ShadowPaperLedger()
        self.assertIn("s3_shadow", str(ledger.root).replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()
