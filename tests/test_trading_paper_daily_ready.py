"""Daily paper-live readiness — account capital defaults and run-all."""
from __future__ import annotations

import unittest
from pathlib import Path

from src.trading.live.paper_accounts import get_paper_account, load_paper_accounts_config
from src.trading.live.path_safety import is_under_paper_trade


class TestPaperDailyReady(unittest.TestCase):
    def test_small_account_30m_capital(self):
        acct = get_paper_account("A3_DSE_PILOT_PAPER_SMALL")
        self.assertEqual(acct.starting_cash_VND, 30_000_000.0)
        self.assertEqual(acct.max_order_value_VND, 5_000_000.0)
        self.assertEqual(acct.sizing_policy, "cap_to_account_limits")
        self.assertEqual(acct.min_trade_value_VND, 1_000_000.0)

    def test_5b_reference_capital(self):
        acct = get_paper_account("A3_PROD_PAPER_5B")
        self.assertEqual(acct.starting_cash_VND, 5_000_000_000.0)
        self.assertEqual(acct.sizing_policy, "scan_size_strict")

    def test_s3_shadow_separate(self):
        acct = get_paper_account("S3_MAX60_SHADOW_PAPER")
        self.assertTrue(acct.is_s3_shadow)
        root = str(acct.resolve_ledger_root()).replace("\\", "/")
        self.assertIn("s3_shadow", root)
        self.assertFalse(acct.allow_dse)
        self.assertFalse(acct.allow_dnse)

    def test_no_paper_trade_paths_in_config(self):
        raw = load_paper_accounts_config()
        for aid, spec in (raw.get("paper_accounts") or {}).items():
            lr = spec.get("ledger_root", "")
            self.assertFalse(is_under_paper_trade(Path(lr)), msg=aid)


if __name__ == "__main__":
    unittest.main()
