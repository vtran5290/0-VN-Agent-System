"""Paper accounts usability + safety patch tests."""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from src.trading.config import REPO_ROOT
from src.trading.live.manual_review import (
    apply_queue_to_intents,
    intent_execution_allowed,
    sync_queue_from_intents,
)
from src.trading.live.order_intent import build_order_intents
from src.trading.live.paper_accounts import build_live_config_for_account, get_paper_account
from src.trading.live.path_safety import ForbiddenLedgerPathError, is_under_paper_trade, validate_live_output_path
from src.trading.live.row_hash import compute_row_hash, make_manual_review_key
from src.trading.live.s3_flag import s3_shadow_block_reason
from src.trading.live.s3_shadow_workflow import _filter_scan_to_date, update_s3_shadow
from src.trading.live.sizing_policy import apply_execution_sizing
from src.trading.live.account_dashboard import compute_traffic_light, write_compare_report
from src.trading.live.data_health import DataHealthResult
from src.trading.live.scan_resolver import ScanResolveResult

FIXTURES = Path(__file__).parent / "fixtures" / "trading"
E2E_SCAN = FIXTURES / "sample_scan_e2e.csv"


def _health():
    return DataHealthResult(status="PASS", block_order_generation=False, latest_panel_date="2099-03-01").to_status_dict()


def _scan_resolve(path: Path):
    return ScanResolveResult(
        path=path,
        resolved_scan_source="cli",
        scan_hash="abc123",
        is_sample=True,
        is_stale=False,
        metadata={"path": str(path), "scan_hash": "abc123"},
    )


class TestSizingPolicy(unittest.TestCase):
    def test_5b_uses_scan_size_strict(self):
        cfg, acct = build_live_config_for_account("A3_PROD_PAPER_5B")
        row = pd.Series({"adv50_B_VND": 500.0, "target_T1_M": 250.0})
        scan_v = 250_000_000.0
        ev, qty, pol, reason, _ = apply_execution_sizing(cfg, scan_v, 100_000.0, "BUY", row)
        self.assertEqual(pol, "scan_size_strict")
        self.assertEqual(ev, scan_v)
        self.assertEqual(reason, "")

    def test_small_account_caps_value(self):
        cfg, _ = build_live_config_for_account("A3_DSE_PILOT_PAPER_SMALL")
        row = pd.Series({"adv50_B_VND": 500.0, "target_T1_M": 250.0})
        scan_v = 250_000_000.0
        ev, qty, pol, reason, _ = apply_execution_sizing(cfg, scan_v, 100_000.0, "BUY", row)
        self.assertEqual(pol, "cap_to_account_limits")
        self.assertLessEqual(ev, cfg.max_order_value_vnd)
        self.assertGreater(qty, 0)
        self.assertIn(reason, ("", "capped_to_account_limits"))

    def test_below_min_trade_value(self):
        cfg, _ = build_live_config_for_account("A3_DSE_PILOT_PAPER_SMALL")
        row = pd.Series({"adv50_B_VND": 0.001})
        ev, qty, _, reason, _ = apply_execution_sizing(cfg, 500_000.0, 100_000.0, "BUY", row)
        self.assertEqual(reason, "below_min_trade_value")
        self.assertEqual(qty, 0)

    def test_same_scan_different_sizing_between_accounts(self):
        hs = _health()
        sr = _scan_resolve(E2E_SCAN)
        cfg5, _ = build_live_config_for_account("A3_PROD_PAPER_5B")
        cfg_s, _ = build_live_config_for_account("A3_DSE_PILOT_PAPER_SMALL")
        i5 = build_order_intents(cfg5, "2099-03-01", hs, scan_path=E2E_SCAN, scan_resolve=sr, test_mode=True)
        is_ = build_order_intents(cfg_s, "2099-03-01", hs, scan_path=E2E_SCAN, scan_resolve=sr, test_mode=True)
        t5 = i5[i5["action"] == "BUY_T1"]
        ts = is_[is_["action"] == "BUY_T1"]
        self.assertFalse(t5.empty)
        self.assertFalse(ts.empty)
        self.assertGreater(float(t5.iloc[0]["execution_value_VND"]), float(ts.iloc[0]["execution_value_VND"]))


class TestManualReviewStale(unittest.TestCase):
    def test_approval_stale_on_row_change(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg, _ = build_live_config_for_account("A3_PROD_PAPER_5B", ledger_root_override=root)
            row = {
                "order_intent_id": "x1",
                "manual_review_key": "2099-03-01|HPG|1",
                "date": "2099-03-01",
                "symbol": "HPG",
                "action": "BUY_T1_MANUAL_REVIEW",
                "strategy": "A3_DP",
                "tier": "T1",
                "reason_code": "NEW_T1_MANUAL_REVIEW_BREADTH",
                "risk_flags": "",
                "requires_manual_review": True,
                "approved": True,
                "rejected": False,
                "approval_stale": False,
                "source_scan_file": "f.csv",
                "source_scan_row_id": 1,
                "scan_hash": "h1",
                "row_hash": compute_row_hash({
                    "date": "2099-03-01", "symbol": "HPG", "strategy_classification": "A3_PRODUCTION",
                    "reason_code": "NEW_T1_MANUAL_REVIEW_BREADTH", "action": "BUY_T1_MANUAL_REVIEW",
                    "side": "BUY", "limit_price": 80000, "quantity_estimate": 100, "execution_value_VND": 8_000_000,
                    "risk_flags": "", "source_scan_row_id": 1,
                }),
            }
            intents = pd.DataFrame([row])
            sync_queue_from_intents(cfg, "2099-03-01", intents, scan_hash="h1")
            qpath = cfg.live_dir / "manual_review_queue_20990301.csv"
            qdf = pd.read_csv(qpath, dtype=object)
            qdf.loc[0, "approved"] = True
            qdf.to_csv(qpath, index=False)
            row2 = row.copy()
            row2["limit_price"] = 90000
            row2["row_hash"] = compute_row_hash({
                "date": "2099-03-01", "symbol": "HPG", "strategy_classification": "A3_PRODUCTION",
                "reason_code": "NEW_T1_MANUAL_REVIEW_BREADTH", "action": "BUY_T1_MANUAL_REVIEW",
                "side": "BUY", "limit_price": 90000, "quantity_estimate": 100, "execution_value_VND": 9_000_000,
                "risk_flags": "", "source_scan_row_id": 1,
            })
            sync_queue_from_intents(cfg, "2099-03-01", pd.DataFrame([row2]), scan_hash="h1")
            merged = apply_queue_to_intents(cfg, "2099-03-01", pd.DataFrame([row2]))
            self.assertTrue(bool(merged.iloc[0]["approval_stale"]))
            ok, reason = intent_execution_allowed(merged.iloc[0], cfg)
            self.assertFalse(ok)
            self.assertEqual(reason, "manual_review_stale")


class TestS3StrictFlag(unittest.TestCase):
    def test_missing_flag_blocked(self):
        self.assertEqual(s3_shadow_block_reason(None), "missing_no_real_order_flag")
        self.assertEqual(s3_shadow_block_reason(False), "false_no_real_order_flag")
        self.assertIsNone(s3_shadow_block_reason(True))

    def test_s3_date_filter(self):
        df = pd.DataFrame({
            "as_of_date": ["2099-03-01", "2099-03-02"],
            "symbol": ["A", "B"],
        })
        day, _ = _filter_scan_to_date(df, "2099-03-01")
        self.assertEqual(len(day), 1)
        self.assertEqual(day.iloc[0]["symbol"], "A")

    def test_undated_fails_closed(self):
        df = pd.DataFrame({"symbol": ["A"]})
        day, w = _filter_scan_to_date(df, "2099-03-01", allow_undated_scan=False)
        self.assertTrue(day.empty)
        self.assertIn("missing_date_column_fail_closed", w)


class TestPathSafety(unittest.TestCase):
    def test_paper_trade_forbidden(self):
        p = REPO_ROOT / "data" / "paper_trade" / "x.csv"
        self.assertTrue(is_under_paper_trade(p))
        with self.assertRaises(ForbiddenLedgerPathError):
            validate_live_output_path(p)

    def test_account_config_rejects_paper_trade_root(self):
        with TemporaryDirectory() as tmp:
            bad = Path(tmp) / "data" / "paper_trade" / "bad"
            bad.mkdir(parents=True)
            acct = get_paper_account("A3_PROD_PAPER_5B")
            acct.ledger_root = bad
            with self.assertRaises(ForbiddenLedgerPathError):
                acct.resolve_ledger_root()


class TestTrafficLight(unittest.TestCase):
    def test_dirty_recon_red(self):
        s, r = compute_traffic_light(recon={"BLOCK_NEW_ORDERS": True, "status": "BLOCK"})
        self.assertEqual(s, "RED")

    def test_manual_review_yellow(self):
        intents = pd.DataFrame([{"action": "BUY_T1", "requires_manual_review": True}])
        s, _ = compute_traffic_light(health_status={"status": "PASS"}, intents=intents)
        self.assertEqual(s, "YELLOW")

    def test_clean_green(self):
        s, r = compute_traffic_light(health_status={"status": "PASS"}, kill_switch={"status": "CLEAR"})
        self.assertEqual(s, "GREEN")


class TestCompareReport(unittest.TestCase):
    def test_compare_has_interpretation_note(self):
        with TemporaryDirectory() as tmp:
            root5 = Path(tmp) / "a5"
            root_s = Path(tmp) / "as"
            ids = ["A3_PROD_PAPER_5B", "A3_DSE_PILOT_PAPER_SMALL"]
            for aid, root in zip(ids, [root5, root_s]):
                from src.trading.live.paper_accounts import initialize_paper_account
                initialize_paper_account(aid, ledger_root_override=root)
                cfg, _ = build_live_config_for_account(aid, ledger_root_override=root)
                cfg.dashboard_dir.mkdir(parents=True, exist_ok=True)
                p = cfg.order_intents_path("2099-03-01")
                p.parent.mkdir(parents=True, exist_ok=True)
                pd.DataFrame([{"action": "BUY_T1", "requires_manual_review": False}]).to_csv(p, index=False)
            path = write_compare_report("2099-03-01", ids)
            text = path.read_text(encoding="utf-8")
            self.assertIn("account sizing and liquidity capacity", text)
            self.assertIn("A3_PROD_PAPER_5B", text)
            self.assertIn("S3 shadow (separate)", text)


if __name__ == "__main__":
    unittest.main()
