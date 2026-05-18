"""E2E live-workflow test with fixtures (no parquet/DNSE)."""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.trading.config import LiveTradingConfig
from src.trading.live.data_health import DataHealthResult
from src.trading.live.run_lock import RunLockError

FIXTURES = Path(__file__).parent / "fixtures" / "trading"
E2E_SCAN = FIXTURES / "sample_scan_e2e.csv"


def _mock_health(*_a, **_k):
    return DataHealthResult(
        status="PASS",
        block_order_generation=False,
        latest_panel_date="2099-03-01",
    )


class TestLiveWorkflowE2E(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.cfg_root = Path(self.tmp.name) / "trading"
        self.date = "2099-03-01"

    def tearDown(self):
        self.tmp.cleanup()

    @patch("src.trading.live.workflow.run_data_health", _mock_health)
    def test_paper_workflow_e2e(self):
        from src.trading.live.workflow import run

        acct_root = Path(self.tmp.name) / "acct_e2e"
        result = run(
            "paper",
            self.date,
            account_id="A3_PROD_PAPER_5B",
            ledger_root_override=acct_root,
            scan_path=E2E_SCAN,
            test_mode=True,
        )
        self.assertFalse(result.get("aborted"))
        self.assertGreater(result.get("intents_count", 0), 0)
        self.assertEqual(result.get("account_id"), "A3_PROD_PAPER_5B")
        self.assertTrue((acct_root / f"order_intents_{self.date.replace('-', '')}.csv").exists())
        self.assertTrue((acct_root / "run_manifests").exists())
        self.assertTrue((acct_root / f"manual_review_queue_{self.date.replace('-', '')}.csv").exists())
        self.assertTrue((acct_root / "dashboard" / "latest_status.json").exists())

    @patch("src.trading.live.workflow.run_data_health", _mock_health)
    def test_duplicate_run_blocked(self):
        from src.trading.live.workflow import run

        acct_root = Path(self.tmp.name) / "acct_dup"
        run(
            "paper",
            self.date,
            account_id="A3_PROD_PAPER_5B",
            ledger_root_override=acct_root,
            scan_path=E2E_SCAN,
            test_mode=True,
        )
        r2 = run(
            "paper",
            self.date,
            account_id="A3_PROD_PAPER_5B",
            ledger_root_override=acct_root,
            scan_path=E2E_SCAN,
            test_mode=True,
        )
        self.assertTrue(r2.get("aborted"))


if __name__ == "__main__":
    unittest.main()
