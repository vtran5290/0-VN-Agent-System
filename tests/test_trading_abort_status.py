"""Abort status, run-lock details, allow_sample metadata, kill switch persistence."""
from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from src.trading.config import LiveTradingConfig
from src.trading.live.account_dashboard import write_account_abort_status
from src.trading.live.paper_accounts import build_live_config_for_account
from src.trading.live.run_lock import DailyRunLock, RunLockError
from src.trading.live.scan_resolver import (
    PHASE36_LEGACY_PRODUCTION_NAME,
    resolve_scan,
)
from src.trading.live.workflow import run as run_workflow
from src.trading.monitoring.kill_switch import load_kill_switch

FIXTURES = Path(__file__).parent / "fixtures" / "trading"
SAMPLE = FIXTURES / "sample_scan.csv"


def _write_scan(path: Path, asof: str) -> None:
    df = pd.DataFrame(
        [
            {
                "as_of_date": asof,
                "symbol": "FPT",
                "final_action": "WATCH_ONLY",
                "strategy_classification": "A3_PRODUCTION",
                "in_a3_universe": True,
            }
        ]
    )
    df.to_csv(path, index=False)


class TestAbortStatus(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        root = Path(self.tmp.name)
        self.search = root / "missing_work"
        self.search.mkdir(parents=True)
        self.latest = self.search / "phase36_daily_scan_latest.csv"
        _write_scan(self.latest, "2099-01-01")
        ledger = root / "accounts" / "A3_DSE_PILOT_PAPER_SMALL"
        self.cfg, self.acct = build_live_config_for_account(
            "A3_DSE_PILOT_PAPER_SMALL",
            data_root_override=root / "trading",
            ledger_root_override=ledger,
        )
        self.cfg.ensure_dirs()
        stale = self.cfg.dashboard_dir / "latest_status.json"
        stale.write_text(
            json.dumps(
                {
                    "traffic_light_status": "RED",
                    "traffic_light_reasons": ["sample_scan"],
                    "workflow_aborted": False,
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_run_lock_conflict_writes_abort_status(self):
        write_account_abort_status(
            self.cfg,
            self.acct,
            "2099-01-01",
            "run_lock_conflict",
            "Run already COMPLETED",
            manifest_info={
                "account_id": self.acct.account_id,
                "manifest_status": "COMPLETED",
                "operator_hint": "Use --force only after confirming",
            },
        )
        st = json.loads((self.cfg.dashboard_dir / "latest_status.json").read_text(encoding="utf-8"))
        self.assertEqual(st["traffic_light_status"], "RED")
        self.assertIn("run_lock_conflict", st["traffic_light_reasons"])
        self.assertNotIn("sample_scan", st["traffic_light_reasons"])
        self.assertTrue(st.get("workflow_aborted"))

    def test_stale_scan_blocked_writes_abort_status(self):
        r = resolve_scan(
            LiveTradingConfig(
                data_root=Path(self.tmp.name) / "x",
                allow_sample_scan=False,
                scan_csv_path=self.latest,
            ),
            "2099-01-02",
            cli_scan_path=self.latest,
            test_mode=False,
        )
        self.assertTrue(r.blocked)
        self.assertTrue(r.is_stale)
        write_account_abort_status(
            self.cfg,
            self.acct,
            "2099-01-02",
            "stale_scan",
            "stale test",
            scan_meta=r.metadata,
        )
        st = json.loads((self.cfg.dashboard_dir / "latest_status.json").read_text(encoding="utf-8"))
        self.assertIn("stale_scan", st["traffic_light_reasons"])


class TestAllowSampleMetadata(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.search = Path(self.tmp.name) / "missing_work"
        self.search.mkdir(parents=True)
        self.legacy = self.search / PHASE36_LEGACY_PRODUCTION_NAME
        _write_scan(self.legacy, "2099-01-01")
        self.cfg = LiveTradingConfig(
            data_root=Path(self.tmp.name) / "trading",
            allow_sample_scan=False,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_allow_sample_false_by_default(self):
        r = resolve_scan(
            self.cfg, "2099-01-01", cli_scan_path=self.legacy, test_mode=False, search_dir=self.search
        )
        self.assertFalse(r.metadata.get("allow_sample"))

    def test_allow_sample_true_when_flag(self):
        r = resolve_scan(
            self.cfg,
            "2099-01-01",
            cli_scan_path=self.legacy,
            test_mode=False,
            allow_sample=True,
            search_dir=self.search,
        )
        self.assertTrue(r.metadata.get("allow_sample"))
        self.assertFalse(r.is_sample)


class TestKillSwitchPersistence(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        root = Path(self.tmp.name)
        self.cfg, self.acct = build_live_config_for_account(
            "A3_PROD_PAPER_5B",
            data_root_override=root / "trading",
            ledger_root_override=root / "accounts" / "A3_PROD_PAPER_5B",
        )
        shutil.copy(SAMPLE, self.cfg.scan_csv_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_kill_switch_file_written_after_monitoring(self):
        from src.trading.monitoring.monitor import run_monitoring

        run_monitoring(
            self.cfg,
            "2099-01-01",
            {"status": "PASS", "checks": []},
            {},
        )
        self.assertTrue(self.cfg.kill_switch_status_path.exists())
        ks = load_kill_switch(self.cfg)
        self.assertIn(ks.get("status"), ("CLEAR", "WARN", "BLOCK"))


class TestRunLockErrorDetails(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.cfg = LiveTradingConfig(data_root=Path(self.tmp.name) / "trading")
        self.cfg.ensure_dirs()
        self.lock = DailyRunLock(self.cfg)

    def tearDown(self):
        self.tmp.cleanup()

    def test_completed_run_lock_includes_account_id(self):
        self.lock.acquire("2099-01-01", "paper", account_id="A3_PROD_PAPER_5B")
        self.lock.complete(self.lock.load_manifest("2099-01-01", "paper", "A3_PROD_PAPER_5B"))
        with self.assertRaises(RunLockError) as ctx:
            self.lock.acquire("2099-01-01", "paper", account_id="A3_PROD_PAPER_5B")
        self.assertEqual(ctx.exception.details.get("account_id"), "A3_PROD_PAPER_5B")
        self.assertIn("manifest_path", ctx.exception.details)
        self.assertIn("operator_hint", ctx.exception.details)


class TestUseLatestScanDateEffective(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.search = Path(self.tmp.name) / "missing_work"
        self.search.mkdir(parents=True)
        self.latest = self.search / "phase36_daily_scan_latest.csv"
        _write_scan(self.latest, "2099-01-05")

    def tearDown(self):
        self.tmp.cleanup()

    def test_override_sets_effective_date(self):
        cfg = LiveTradingConfig(
            data_root=Path(self.tmp.name) / "trading",
            scan_csv_path=self.latest,
        )
        r = resolve_scan(
            cfg,
            "2099-01-10",
            cli_scan_path=self.latest,
            use_latest_scan_date=True,
        )
        self.assertFalse(r.blocked)
        self.assertEqual(r.effective_date, "2099-01-05")
        self.assertEqual(r.metadata.get("effective_date"), "2099-01-05")


if __name__ == "__main__":
    unittest.main()
