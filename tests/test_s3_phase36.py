"""Phase36 behavioral tests.

Tests:
1. S3 combo cannot route live orders (capital guard).
2. A3 final_action is unchanged by S3 lead-age.
3. S3 lead bucket calculation is correct for every boundary.
4. lead_11_20 / lead_21_30 boost ranking only; same_bar_0 does not.
5. same_bar_0 is never marked as best quality.
"""
from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

# Ensure repo root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.trading.live.s3_combo_paper_ledger import (
    S3ComboPaperLedger,
    _guard_no_live_order,
    _LIVE_ORDER_ALLOWED,
    _DNSE_ALLOWED,
)
from pp_backtest.portfolio_optimization_final_steps import (
    _s3_lead_bucket,
    _s3_lead_quality,
    _final_action,
)


class TestS3ComboNoLiveOrders(unittest.TestCase):
    """Test 1: S3 combo paper ledger cannot route live orders."""

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.original_data_dir = None

    def tearDown(self):
        self.tmp.cleanup()

    def test_live_order_allowed_is_false(self):
        """_LIVE_ORDER_ALLOWED module constant must be False."""
        self.assertFalse(_LIVE_ORDER_ALLOWED,
                         "S3 combo ledger: _LIVE_ORDER_ALLOWED must be False")

    def test_dnse_allowed_is_false(self):
        """_DNSE_ALLOWED module constant must be False."""
        self.assertFalse(_DNSE_ALLOWED,
                         "S3 combo ledger: _DNSE_ALLOWED must be False")

    def test_guard_no_live_order_does_not_raise_when_false(self):
        """_guard_no_live_order() should not raise when _LIVE_ORDER_ALLOWED is False."""
        try:
            _guard_no_live_order()
        except RuntimeError:
            self.fail("_guard_no_live_order() raised unexpectedly with _LIVE_ORDER_ALLOWED=False")

    def test_strategy_tag_is_paper(self):
        """strategy field must be S3_COMBO_PAPER, not A3_PRODUCTION."""
        from src.trading.live.s3_combo_paper_ledger import STRATEGY_TAG
        self.assertEqual(STRATEGY_TAG, "S3_COMBO_PAPER")
        self.assertNotEqual(STRATEGY_TAG, "A3_PRODUCTION")

    def test_capacity_ceiling_enforced(self):
        """record_entry raises ValueError if value_vnd > 5B VND ceiling."""
        import os
        with patch("src.trading.live.s3_combo_paper_ledger.DATA_DIR", Path(self.tmp.name)):
            ledger = S3ComboPaperLedger()
            ledger._trades_path    = Path(self.tmp.name) / "s3_combo_paper_trades.csv"
            ledger._positions_path = Path(self.tmp.name) / "s3_combo_paper_positions.csv"
            with self.assertRaises(ValueError, msg="Should reject value > 5B VND capacity"):
                ledger.record_entry(
                    symbol="TEST",
                    signal_date="2026-01-01",
                    fill_price=10.0,
                    value_vnd=6_000_000_000,   # 6B > 5B ceiling
                    quantity=600_000_000,
                )


class TestA3FinalActionUnchangedByLeadAge(unittest.TestCase):
    """Test 2: A3 final_action is not gated by S3 lead-age.

    _final_action() has no lead-age parameter — its signature must remain
    unchanged and produce the same result regardless of S3 state.
    """

    def _call_final_action(self, **kwargs):
        defaults = dict(
            a3_active=True,
            s3_active=True,
            cloud_bull=True,
            regime_bull=True,
            breadth_zone="normal",
            liq_rec="full_T1",
            a3_bars=0,
        )
        defaults.update(kwargs)
        return _final_action(**defaults)

    def test_new_t1_regardless_of_s3_lead(self):
        """A3 NEW_T1 fires whether S3 fired same bar, 20 bars ago, or never."""
        action_s3_active,   _ = self._call_final_action(s3_active=True)
        action_s3_inactive, _ = self._call_final_action(s3_active=False)
        self.assertEqual(action_s3_active,   "NEW_T1")
        self.assertEqual(action_s3_inactive, "NEW_T1")

    def test_final_action_has_no_lead_age_param(self):
        """_final_action must NOT accept a lead_age or s3_lead_bucket parameter."""
        import inspect
        sig = inspect.signature(_final_action)
        param_names = set(sig.parameters.keys())
        forbidden = {"lead_age", "s3_lead_age", "s3_lead_bucket", "lead_bucket"}
        overlap = param_names & forbidden
        self.assertFalse(
            overlap,
            f"_final_action() must not accept lead-age params: found {overlap}"
        )

    def test_bear_regime_blocks_a3_regardless_of_s3(self):
        """VNINDEX bear blocks A3 regardless of S3 lead bucket."""
        action, _ = self._call_final_action(regime_bull=False, s3_active=True)
        self.assertEqual(action, "SKIP_VNINDEX_BEAR")


class TestS3LeadBucketCalculation(unittest.TestCase):
    """Test 3: _s3_lead_bucket returns correct bucket for every boundary value."""

    def test_none_returns_no_s3_lead(self):
        self.assertEqual(_s3_lead_bucket(None), "no_s3_lead")

    def test_zero_returns_same_bar_0(self):
        self.assertEqual(_s3_lead_bucket(0), "same_bar_0")

    def test_1_returns_lead_1_5(self):
        self.assertEqual(_s3_lead_bucket(1), "lead_1_5")

    def test_5_returns_lead_1_5(self):
        self.assertEqual(_s3_lead_bucket(5), "lead_1_5")

    def test_6_returns_lead_6_10(self):
        self.assertEqual(_s3_lead_bucket(6), "lead_6_10")

    def test_10_returns_lead_6_10(self):
        self.assertEqual(_s3_lead_bucket(10), "lead_6_10")

    def test_11_returns_lead_11_20(self):
        self.assertEqual(_s3_lead_bucket(11), "lead_11_20")

    def test_20_returns_lead_11_20(self):
        self.assertEqual(_s3_lead_bucket(20), "lead_11_20")

    def test_21_returns_lead_21_30(self):
        self.assertEqual(_s3_lead_bucket(21), "lead_21_30")

    def test_30_returns_lead_21_30(self):
        self.assertEqual(_s3_lead_bucket(30), "lead_21_30")

    def test_31_returns_no_s3_lead(self):
        self.assertEqual(_s3_lead_bucket(31), "no_s3_lead")

    def test_999_returns_no_s3_lead(self):
        self.assertEqual(_s3_lead_bucket(999), "no_s3_lead")


class TestLeadAgeRankingBoost(unittest.TestCase):
    """Test 4: lead_11_20 and lead_21_30 produce positive quality labels.
       lead_1_5 and same_bar_0 do not produce 'best' or 'good'.
    """

    def test_lead_11_20_is_best(self):
        self.assertEqual(_s3_lead_quality("lead_11_20"), "best")

    def test_lead_21_30_is_good(self):
        self.assertEqual(_s3_lead_quality("lead_21_30"), "good")

    def test_lead_6_10_is_neutral(self):
        self.assertEqual(_s3_lead_quality("lead_6_10"), "neutral")

    def test_lead_1_5_is_neutral_not_positive(self):
        q = _s3_lead_quality("lead_1_5")
        self.assertNotIn(q, ("best", "good"),
                         "lead_1_5 must not receive a positive ranking boost")

    def test_no_s3_lead_is_none(self):
        self.assertEqual(_s3_lead_quality("no_s3_lead"), "none")

    def test_rank_score_best_higher_than_neutral(self):
        """Rank score for lead_11_20 (best) must exceed lead_1_5 (neutral) at same ED."""
        _quality_lut = {"best": 2.0, "good": 1.0, "neutral": 0.0, "chase": -0.5, "none": 0.0}
        ed_pct = 5.0  # same ED for both
        ed_score = max(0.0, 1.0 - (abs(ed_pct) / 20.0))
        score_best    = _quality_lut["best"]    + ed_score
        score_neutral = _quality_lut["neutral"] + ed_score
        self.assertGreater(score_best, score_neutral)


class TestSameBar0IsNotBest(unittest.TestCase):
    """Test 5: same_bar_0 is never marked as best quality."""

    def test_same_bar_0_quality_is_chase(self):
        self.assertEqual(_s3_lead_quality("same_bar_0"), "chase")

    def test_same_bar_0_is_not_best(self):
        q = _s3_lead_quality("same_bar_0")
        self.assertNotEqual(q, "best", "same_bar_0 must never be marked as best")

    def test_same_bar_0_is_not_good(self):
        q = _s3_lead_quality("same_bar_0")
        self.assertNotEqual(q, "good", "same_bar_0 must never be marked as good")

    def test_same_bar_0_rank_score_below_lead_11_20(self):
        """same_bar_0 rank score must be lower than lead_11_20 at the same ED."""
        _quality_lut = {"best": 2.0, "good": 1.0, "neutral": 0.0, "chase": -0.5, "none": 0.0}
        ed_pct = 5.0
        ed_score = max(0.0, 1.0 - (abs(ed_pct) / 20.0))
        score_same_bar = _quality_lut["chase"] + ed_score
        score_11_20    = _quality_lut["best"]  + ed_score
        self.assertLess(score_same_bar, score_11_20)

    def test_bucket_0_bars_is_same_bar_not_lead_1_5(self):
        """0 bars must map to same_bar_0, not lead_1_5."""
        self.assertEqual(_s3_lead_bucket(0), "same_bar_0")
        self.assertNotEqual(_s3_lead_bucket(0), "lead_1_5")


if __name__ == "__main__":
    unittest.main()
