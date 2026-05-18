"""Phase36 daily scan — operator ranking only (CONDITIONAL_NO_CHANGE)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from pp_backtest.portfolio_optimization_final_steps import (
    SCAN_SCHEMA_VERSION,
    _sort_scan_for_review,
    _final_action,
    _compute_phase36_lead_context,
)
from src.trading.live.order_intent import ACTION_MAP, build_order_intents


class TestPhase36FieldsExist(unittest.TestCase):
    def test_schema_has_phase36_fields(self):
        schema_path = (
            Path(__file__).parent.parent
            / "data/research/portfolio_optimization/missing_work/phase36_daily_scan_schema.csv"
        )
        if not schema_path.exists():
            self.skipTest("run scan first")
        fields = set(pd.read_csv(schema_path)["field"])
        required = {
            "scan_schema_version", "a3_rank_score", "a3_rank_reason", "a3_rank_bucket",
            "ed_score", "ed_score_bucket", "phase36_operator_priority",
            "s3_fresh_lead_flag", "s3_stale_lead_flag", "s3_lead_1_5d",
            "s3_same_day_as_a3", "s3_after_a3_5d", "a3_without_s3",
            "s3_deterioration_flag", "s3_t2_warning_flag",
        }
        self.assertTrue(required.issubset(fields), f"missing: {required - fields}")

    def test_sample_has_schema_version(self):
        p = Path(__file__).parent.parent / "data/research/portfolio_optimization/missing_work/phase36_daily_scan_sample.csv"
        if not p.exists():
            self.skipTest("run scan first")
        df = pd.read_csv(p)
        self.assertEqual(df["scan_schema_version"].iloc[0], SCAN_SCHEMA_VERSION)


class TestSortDoesNotChangeFinalAction(unittest.TestCase):
    def test_sort_preserves_final_action_values(self):
        df = pd.DataFrame([
            {"symbol": "AAA", "final_action": "NEW_T1_MANUAL_REVIEW_BREADTH", "a3_rank_score": 0.5,
             "liq_warn_T1": "OK", "sector_l4": "Banks", "s3_fresh_lead_flag": False},
            {"symbol": "BBB", "final_action": "NEW_T1", "a3_rank_score": 2.0,
             "liq_warn_T1": "OK", "sector_l4": "Banks", "s3_fresh_lead_flag": True},
            {"symbol": "CCC", "final_action": "TRAIL_EXIT", "a3_rank_score": 1.0,
             "liq_warn_T1": "OK", "sector_l4": "RE", "s3_fresh_lead_flag": False},
        ])
        before = dict(zip(df["symbol"], df["final_action"]))
        sorted_df = _sort_scan_for_review(df)
        after = dict(zip(sorted_df["symbol"], sorted_df["final_action"]))
        self.assertEqual(before, after)
        self.assertEqual(sorted_df.iloc[0]["symbol"], "BBB")
        self.assertEqual(sorted_df.iloc[0]["final_action"], "NEW_T1")

    def test_new_t1_before_manual_review_when_scores_equal(self):
        df = pd.DataFrame([
            {"symbol": "M", "final_action": "NEW_T1_MANUAL_REVIEW_BREADTH", "a3_rank_score": 1.0,
             "liq_warn_T1": "OK", "sector_l4": "X", "s3_fresh_lead_flag": False},
            {"symbol": "N", "final_action": "NEW_T1", "a3_rank_score": 1.0,
             "liq_warn_T1": "OK", "sector_l4": "X", "s3_fresh_lead_flag": False},
        ])
        s = _sort_scan_for_review(df)
        self.assertEqual(s.iloc[0]["symbol"], "N")


class TestA3RankScoreNotTradeable(unittest.TestCase):
    def test_a3_rank_score_not_in_action_map(self):
        self.assertNotIn("a3_rank_score", ACTION_MAP)

    def test_sorting_does_not_add_buy_intent(self):
        row = {
            "as_of_date": "2026-01-01", "symbol": "HPG", "a3_active": True, "s3_active": False,
            "s3_shadow_action": "", "s3_research_monitor_action": "",
            "strategy_classification": "A3_PRODUCTION",
            "final_action": "NEW_T1", "in_a3_universe": True, "regime_bull": True,
            "breadth_zone": "normal", "liq_warn_T1": "OK", "recommendation": "full_T1",
            "close_kVND": 20.0, "adv50_B_VND": 15.0, "target_T1_M": 250.0,
            "max_10pct_M": 150.0, "sector_l4_stress_flag": "OK", "a3_rank_score": 99.0,
        }
        import json
        import tempfile
        from unittest.mock import MagicMock, patch

        with tempfile.TemporaryDirectory() as tmpdir:
            scan_path = Path(tmpdir) / "scan.csv"
            pd.DataFrame([row]).to_csv(scan_path, index=False)
            broker_state_path = Path(tmpdir) / "paper_broker_state.json"
            broker_state_path.write_text(
                json.dumps({"cash_vnd": 10_000_000_000_000, "nav_vnd": 10_000_000_000_000}),
                encoding="utf-8",
            )
            cfg = MagicMock()
            cfg.scan_csv_path = scan_path
            cfg.paper_broker_state_path = broker_state_path
            cfg.allow_s3_capital = False
            cfg.allow_pts_shadow = False
            cfg.require_regime_bull = True
            cfg.adv_participation = 0.10
            cfg.production_strategy = "A3_DP"
            with patch(
                "src.trading.live.order_intent.apply_execution_sizing",
                return_value=(250_000_000, 10_000, "scan_size_strict", "test", {}),
            ):
                intents = build_order_intents(cfg, "2026-01-01", {}, scan_path=scan_path)
            actions = set(intents["action"])
            self.assertIn("BUY_T1", actions)
            self.assertNotIn("BUY_T2", actions)
            self.assertNotIn("a3_rank_score", intents.columns)


class TestA3WithoutS3StillEligible(unittest.TestCase):
    def test_no_s3_lead_still_new_t1(self):
        action, _ = _final_action(
            a3_active=True, s3_active=False, cloud_bull=True,
            regime_bull=True, breadth_zone="normal", liq_rec="full_T1", a3_bars=0,
        )
        self.assertEqual(action, "NEW_T1")

    def test_lead_context_none(self):
        ctx = _compute_phase36_lead_context(True, 100, [], None)
        self.assertTrue(ctx["a3_without_s3"])
        self.assertEqual(ctx["s3_lead_bucket"], "none")


class TestLeadBuckets(unittest.TestCase):
    def test_fresh_lead_1_5(self):
        ctx = _compute_phase36_lead_context(True, 50, [40], 3)
        self.assertTrue(ctx["s3_fresh_lead_flag"])
        self.assertTrue(ctx["s3_lead_1_5d"])
        self.assertEqual(ctx["s3_lead_bucket"], "lead_1_5")

    def test_same_day_not_fresh_lead(self):
        ctx = _compute_phase36_lead_context(True, 50, [50], 0)
        self.assertTrue(ctx["s3_same_day_as_a3"])
        self.assertFalse(ctx["s3_fresh_lead_flag"])


class TestT2AndExitUnchanged(unittest.TestCase):
    def test_defense_blocks_t2_not_t1(self):
        t2, _ = _final_action(
            a3_active=True, s3_active=True, cloud_bull=True,
            regime_bull=True, breadth_zone="defense", liq_rec="full_T1", a3_bars=5,
        )
        self.assertEqual(t2, "NO_T2_BREADTH")
        t1, _ = _final_action(
            a3_active=True, s3_active=False, cloud_bull=True,
            regime_bull=True, breadth_zone="defense", liq_rec="full_T1", a3_bars=0,
        )
        self.assertEqual(t1, "NEW_T1_MANUAL_REVIEW_BREADTH")

    def test_trail_exit_unchanged(self):
        action, _ = _final_action(
            a3_active=True, s3_active=False, cloud_bull=True,
            regime_bull=True, breadth_zone="normal", liq_rec="full_T1", a3_bars=10,
            close_kvnd=10.0, trail_price=12.0,
        )
        self.assertEqual(action, "TRAIL_EXIT")


class TestOperatorReport(unittest.TestCase):
    def test_report_mentions_conditional_no_change(self):
        p = Path(__file__).parent.parent / "data/research/portfolio_optimization/missing_work/phase36_daily_operator_report.md"
        if not p.exists():
            self.skipTest("run scan first")
        text = p.read_text(encoding="utf-8")
        self.assertIn("CONDITIONAL_NO_CHANGE", text)


if __name__ == "__main__":
    unittest.main()
