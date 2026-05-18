"""Scale paper accounts (10B / 20B) — config, sizing, run-all, compare, path safety."""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

from src.trading.config import REPO_ROOT, load_live_trading_config
from src.trading.live.account_dashboard import write_compare_report
from src.trading.live.paper_accounts import (
    A3_PAPER_RUN_ORDER,
    build_live_config_for_account,
    get_paper_account,
    initialize_paper_account,
    list_paper_accounts,
)
from src.trading.live.paper_run_all import A3_RUN_ORDER, run_all_paper_accounts
from src.trading.live.scan_resolver import ScanResolveResult
from src.trading.live.path_safety import is_under_paper_trade
from src.trading.live.sizing_policy import (
    POLICY_CAP_TO_LIQUIDITY,
    apply_execution_sizing,
)


class TestScaleAccountConfig(unittest.TestCase):
    def test_10b_exists_and_nav(self):
        acct = get_paper_account("A3_SCALE_PAPER_10B")
        self.assertEqual(acct.starting_cash_VND, 10_000_000_000.0)
        self.assertEqual(acct.sizing_policy, "scan_size_strict")
        self.assertTrue(acct.is_a3_production)

    def test_20b_exists_and_nav(self):
        acct = get_paper_account("A3_SCALE_PAPER_20B")
        self.assertEqual(acct.starting_cash_VND, 20_000_000_000.0)
        self.assertEqual(acct.sizing_policy, POLICY_CAP_TO_LIQUIDITY)
        self.assertTrue(acct.is_a3_production)

    def test_ledger_paths_under_live_accounts(self):
        for aid in ("A3_SCALE_PAPER_10B", "A3_SCALE_PAPER_20B"):
            root = str(get_paper_account(aid).resolve_ledger_root()).replace("\\", "/")
            self.assertIn("data/trading/live/accounts/", root)
            self.assertNotIn("paper_trade", root)
            self.assertFalse(is_under_paper_trade(Path(root)))

    def test_list_shows_five_logical_accounts(self):
        ids = [a.account_id for a in list_paper_accounts()]
        for aid in (
            "A3_DSE_PILOT_PAPER_SMALL",
            "A3_PROD_PAPER_5B",
            "A3_SCALE_PAPER_10B",
            "A3_SCALE_PAPER_20B",
            "S3_MAX60_SHADOW_PAPER",
        ):
            self.assertIn(aid, ids)

    def test_run_order_four_a3_accounts(self):
        self.assertEqual(
            A3_RUN_ORDER,
            [
                "A3_DSE_PILOT_PAPER_SMALL",
                "A3_PROD_PAPER_5B",
                "A3_SCALE_PAPER_10B",
                "A3_SCALE_PAPER_20B",
            ],
        )
        self.assertEqual(A3_PAPER_RUN_ORDER, A3_RUN_ORDER)


class TestCapToLiquidity(unittest.TestCase):
    def test_caps_by_adv_and_max_order(self):
        cfg, _ = build_live_config_for_account("A3_SCALE_PAPER_20B")
        row = pd.Series({"adv50_B_VND": 1.0})  # 1B VND ADV
        scan_v = 2_000_000_000.0
        ev, qty, pol, reason, _attr = apply_execution_sizing(cfg, scan_v, 50_000.0, "BUY", row)
        self.assertEqual(pol, POLICY_CAP_TO_LIQUIDITY)
        adv_cap = 1.0 * 1_000_000_000 * cfg.adv_participation
        self.assertLessEqual(ev, cfg.max_order_value_vnd)
        self.assertLessEqual(ev, adv_cap)
        self.assertIn(reason, ("liquidity_cap_hit", "capped_to_liquidity", ""))

    def test_final_action_not_changed_by_sizing_module(self):
        """Sizing module only returns value/qty; it does not mutate scan actions."""
        cfg, _ = build_live_config_for_account("A3_SCALE_PAPER_20B")
        row = pd.Series({"adv50_B_VND": 10.0, "final_action": "BUY_T1"})
        apply_execution_sizing(cfg, 500_000_000.0, 100_000.0, "BUY", row)
        self.assertEqual(row["final_action"], "BUY_T1")


class TestScaleInitPathSafety(unittest.TestCase):
    def test_init_10b_20b_no_paper_trade(self):
        with TemporaryDirectory() as tmp:
            for aid in ("A3_SCALE_PAPER_10B", "A3_SCALE_PAPER_20B"):
                root = Path(tmp) / aid
                initialize_paper_account(aid, ledger_root_override=root)
                self.assertTrue((root / "paper_broker_state.json").exists())
                self.assertFalse(is_under_paper_trade(root))


class TestRunAllScale(unittest.TestCase):
    def test_run_all_includes_four_a3_no_s3_without_flag(self):
        with TemporaryDirectory() as tmp:
            scan = Path(tmp) / "scan.csv"
            pd.DataFrame(
                [{"symbol": "HPG", "final_action": "SKIP", "strategy_classification": "A3_PRODUCTION"}]
            ).to_csv(scan, index=False)
            called: list[str] = []

            def fake_workflow(*_a, **kwargs):
                called.append(kwargs.get("account_id", ""))
                return {"account_id": kwargs.get("account_id"), "status": "ok"}

            resolved = ScanResolveResult(
                path=scan,
                resolved_scan_source="cli",
                scan_hash="x",
                is_sample=False,
                is_stale=False,
                metadata={"path": str(scan)},
            )
            with patch("src.trading.live.paper_run_all.resolve_scan", return_value=resolved):
                with patch("src.trading.live.paper_run_all.run_workflow", side_effect=fake_workflow):
                    with patch("src.trading.live.paper_run_all.update_s3_shadow") as s3:
                        run_all_paper_accounts(
                            "2099-04-01",
                            scan_path=scan,
                            include_s3_shadow=False,
                            test_mode=True,
                        )
                        s3.assert_not_called()
            self.assertEqual(called, A3_RUN_ORDER)

    def test_s3_only_with_include_flag(self):
        with TemporaryDirectory() as tmp:
            scan = Path(tmp) / "scan.csv"
            pd.DataFrame([{"symbol": "HPG", "final_action": "SKIP"}]).to_csv(scan, index=False)
            resolved = ScanResolveResult(
                path=scan,
                resolved_scan_source="cli",
                scan_hash="x",
                is_sample=False,
                is_stale=False,
                metadata={"path": str(scan)},
            )
            with patch("src.trading.live.paper_run_all.resolve_scan", return_value=resolved):
                with patch("src.trading.live.paper_run_all.run_workflow", return_value={"status": "ok"}):
                    with patch(
                        "src.trading.live.paper_run_all.update_s3_shadow",
                        return_value={"recorded": 0, "skipped": 0, "blocked_count": 0},
                    ) as s3:
                        run_all_paper_accounts(
                            "2099-04-01",
                            scan_path=scan,
                            include_s3_shadow=True,
                            test_mode=True,
                        )
                        s3.assert_called_once()


class TestCompareScale(unittest.TestCase):
    def test_compare_all_a3_and_scale_sections(self):
        with TemporaryDirectory() as tmp:
            for aid in A3_RUN_ORDER:
                root = Path(tmp) / aid
                initialize_paper_account(aid, ledger_root_override=root)
                cfg, _ = build_live_config_for_account(aid, ledger_root_override=root)
                cfg.dashboard_dir.mkdir(parents=True, exist_ok=True)
            path = write_compare_report("2099-04-02", A3_RUN_ORDER)
            text = path.read_text(encoding="utf-8")
            self.assertIn("account sizing and liquidity capacity", text)
            for aid in A3_RUN_ORDER:
                self.assertIn(aid, text)
            self.assertIn("Scale interpretation", text)
            self.assertIn("A3_SCALE_PAPER_10B", text)
            self.assertIn("A3_SCALE_PAPER_20B", text)


class TestLiveSafety(unittest.TestCase):
    def test_live_auto_disabled(self):
        cfg = load_live_trading_config()
        self.assertFalse(cfg.live_trading)

    def test_no_dse_dnse_on_scale_accounts(self):
        for aid in ("A3_SCALE_PAPER_10B", "A3_SCALE_PAPER_20B"):
            acct = get_paper_account(aid)
            self.assertFalse(acct.allow_dse)
            self.assertFalse(acct.allow_dnse)
            self.assertFalse(acct.allow_s3)


if __name__ == "__main__":
    unittest.main()
