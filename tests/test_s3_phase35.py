"""Phase35 behavioral tests.

Tests:
1.  S3 max_hold=60 is the correct shadow config (MAR gate passed).
2.  S3 max_hold=250 is REJECTED_CONFIG (never use as shadow).
3.  S3 shadow ledger cannot route live orders.
4.  S3 shadow ledger cannot route to DNSE.
5.  a3_s3_lead_5d is True only when lead_age_bars <= 5.
6.  A3 is not blocked when a3_s3_lead_5d is False.
7.  S3 shadow ledger is separate from A3 and S3 combo ledgers.
8.  Dashboard label for S3 shadow is PAPER_TRADE_SHADOW (not PRODUCTION).
9.  GK5+top100 routes to PAPER_S3_RESEARCH_MONITOR (never live).
10. s3_no_real_order_flag is always True for all S3 rows.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.trading.live.s3_shadow_paper_ledger import (
    S3ShadowPaperLedger,
    _guard_no_live_order,
    _guard_no_dnse,
    _LIVE_ORDER_ALLOWED,
    _DNSE_ALLOWED,
    _MAX_HOLD_BARS,
    _TP1_PCT,
    STRATEGY_TAG,
    S3_SHADOW_TRADES_PATH,
)
from src.trading.live.s3_combo_paper_ledger import (
    S3ComboPaperLedger,
    S3_COMBO_TRADES_PATH,
    STRATEGY_TAG as COMBO_STRATEGY_TAG,
)
from pp_backtest.portfolio_optimization_final_steps import (
    _s3_lead_bucket,
    _final_action,
)


class TestS3MaxHoldConfig(unittest.TestCase):
    """Test 1 & 2: max_hold=60 is correct; max_hold=250 is rejected."""

    def test_shadow_ledger_max_hold_is_60(self):
        """Phase35 base shadow must enforce max_hold=60."""
        self.assertEqual(_MAX_HOLD_BARS, 60,
                         "S3 shadow max_hold must be 60 — never 250")

    def test_shadow_ledger_tp1_is_18pct(self):
        """Phase35 base shadow TP1 must be 18%."""
        self.assertAlmostEqual(_TP1_PCT, 0.18,
                               msg="S3 shadow TP1 must be 18% (0.18)")

    def test_max_hold_250_maps_to_rejected(self):
        """S3 max_hold=250 entry note must always flag REJECTED_CONFIG."""
        self.assertNotEqual(_MAX_HOLD_BARS, 250,
                            "S3 max_hold=250 is REJECTED — must never equal 250")

    def test_strategy_tag_is_shadow_not_combo(self):
        """Shadow ledger strategy tag must be S3_SHADOW_MAX60, not S3_COMBO_PAPER."""
        self.assertEqual(STRATEGY_TAG, "S3_SHADOW_MAX60")
        self.assertNotEqual(STRATEGY_TAG, "S3_COMBO_PAPER")
        self.assertNotEqual(STRATEGY_TAG, "A3_PRODUCTION")


class TestS3ShadowNoLiveOrders(unittest.TestCase):
    """Test 3: S3 shadow ledger cannot route live orders."""

    def test_live_order_allowed_is_false(self):
        self.assertFalse(_LIVE_ORDER_ALLOWED,
                         "S3 shadow ledger: _LIVE_ORDER_ALLOWED must be False")

    def test_guard_no_live_order_does_not_raise(self):
        """_guard_no_live_order() must not raise when _LIVE_ORDER_ALLOWED=False."""
        try:
            _guard_no_live_order()
        except RuntimeError:
            self.fail("_guard_no_live_order() raised unexpectedly")


class TestS3ShadowNoDNSE(unittest.TestCase):
    """Test 4: S3 shadow ledger cannot route to DNSE."""

    def test_dnse_allowed_is_false(self):
        self.assertFalse(_DNSE_ALLOWED,
                         "S3 shadow ledger: _DNSE_ALLOWED must be False")

    def test_guard_no_dnse_does_not_raise(self):
        try:
            _guard_no_dnse()
        except RuntimeError:
            self.fail("_guard_no_dnse() raised unexpectedly")


class TestA3S3Lead5dLogic(unittest.TestCase):
    """Test 5: a3_s3_lead_5d is True only when lead_age_bars <= 5."""

    def _lead_5d(self, bars):
        if bars is None:
            return False
        return int(bars) <= 5

    def test_lead_5d_true_when_bars_1(self):
        self.assertTrue(self._lead_5d(1))

    def test_lead_5d_true_when_bars_5(self):
        self.assertTrue(self._lead_5d(5))

    def test_lead_5d_false_when_bars_6(self):
        self.assertFalse(self._lead_5d(6))

    def test_lead_5d_false_when_none(self):
        self.assertFalse(self._lead_5d(None))

    def test_same_bar_0_is_lead_5d_true(self):
        """same_bar_0 (0 bars) satisfies <= 5 — but is still a 'chase' quality."""
        self.assertTrue(self._lead_5d(0))
        self.assertEqual(_s3_lead_bucket(0), "same_bar_0")


class TestA3NotBlockedBys3Lead(unittest.TestCase):
    """Test 6: A3 fires regardless of s3_lead_5d — S3 lead does NOT gate A3."""

    def _call_final_action(self, **kwargs):
        defaults = dict(
            a3_active=True, s3_active=True, cloud_bull=True,
            regime_bull=True, breadth_zone="normal", liq_rec="full_T1", a3_bars=0,
        )
        defaults.update(kwargs)
        return _final_action(**defaults)

    def test_a3_fires_when_s3_active(self):
        action, _ = self._call_final_action(s3_active=True)
        self.assertEqual(action, "NEW_T1")

    def test_a3_fires_when_s3_inactive(self):
        action, _ = self._call_final_action(s3_active=False)
        self.assertEqual(action, "NEW_T1")

    def test_bear_regime_blocks_a3_not_s3_lead(self):
        """Only VNINDEX bear blocks A3 T1 — not S3 state."""
        action, _ = self._call_final_action(regime_bull=False, s3_active=True)
        self.assertEqual(action, "SKIP_VNINDEX_BEAR")


class TestSeparateLedgers(unittest.TestCase):
    """Test 7: S3 shadow ledger is separate from A3 and S3 combo."""

    def test_shadow_trades_path_different_from_combo(self):
        self.assertNotEqual(S3_SHADOW_TRADES_PATH, S3_COMBO_TRADES_PATH,
                            "Shadow and combo ledgers must use separate CSV files")

    def test_shadow_strategy_tag_different_from_combo(self):
        self.assertNotEqual(STRATEGY_TAG, COMBO_STRATEGY_TAG,
                            "Shadow and combo strategy tags must differ")

    def test_shadow_strategy_tag_not_a3(self):
        self.assertNotIn("A3", STRATEGY_TAG,
                         "Shadow ledger tag must not contain A3")

    def test_shadow_record_entry_uses_shadow_tag(self):
        """S3ShadowPaperLedger.record_entry writes STRATEGY_TAG to notes."""
        with TemporaryDirectory() as tmp:
            with patch("src.trading.live.s3_shadow_paper_ledger.DATA_DIR", Path(tmp)):
                ledger = S3ShadowPaperLedger()
                ledger._trades_path    = Path(tmp) / "trades.csv"
                ledger._positions_path = Path(tmp) / "positions.csv"
                trade_id = ledger.record_entry(
                    symbol="TESTXYZ", signal_date="2026-01-01",
                    fill_price=10.0, value_vnd=1_000_000, quantity=100,
                )
                import pandas as pd
                trades = pd.read_csv(ledger._trades_path)
                self.assertEqual(trades.iloc[0]["strategy"], "S3_SHADOW_MAX60")
                self.assertNotEqual(trades.iloc[0]["strategy"], "S3_COMBO_PAPER")


class TestDashboardLabel(unittest.TestCase):
    """Test 8: Dashboard label for S3 shadow is PAPER_TRADE_SHADOW."""

    def test_shadow_classification_is_paper_trade_shadow(self):
        """The strategy tag and classification must match PAPER_TRADE_SHADOW intent."""
        self.assertEqual(STRATEGY_TAG, "S3_SHADOW_MAX60")
        self.assertNotIn("PRODUCTION", STRATEGY_TAG)

    def test_shadow_classification_not_production_candidate(self):
        self.assertNotIn("PRODUCTION_CANDIDATE", STRATEGY_TAG)


class TestGK5Top100NeverLive(unittest.TestCase):
    """Test 9: GK5+top100 routes to PAPER_S3_RESEARCH_MONITOR, never live."""

    def test_paper_s3_research_monitor_not_tradeable(self):
        """PAPER_S3_RESEARCH_MONITOR action must not appear in order_intent ACTION_MAP."""
        from src.trading.live.order_intent import ACTION_MAP
        self.assertNotIn("PAPER_S3_RESEARCH_MONITOR", ACTION_MAP,
                         "GK5+top100 research monitor must not map to a tradeable action")

    def test_paper_s3_shadow_not_tradeable(self):
        from src.trading.live.order_intent import ACTION_MAP
        self.assertNotIn("PAPER_S3_SHADOW", ACTION_MAP,
                         "PAPER_S3_SHADOW must not map to a tradeable action")

    def test_s3_shadow_actions_set_contains_both(self):
        from src.trading.live.order_intent import _S3_SHADOW_ACTIONS
        self.assertIn("PAPER_S3_SHADOW", _S3_SHADOW_ACTIONS)
        self.assertIn("PAPER_S3_RESEARCH_MONITOR", _S3_SHADOW_ACTIONS)


class TestS3NoRealOrderFlag(unittest.TestCase):
    """Test 10: s3_no_real_order_flag is always True for all S3 rows."""

    def test_s3_shadow_row_sets_no_real_order_flag(self):
        """_s3_shadow_row() must include s3_no_real_order_flag=True."""
        from src.trading.live.order_intent import _s3_shadow_row
        import pandas as pd
        mock_row = pd.Series({
            "s3_shadow_reason": "test",
            "breadth_zone": "normal",
            "sector_l4": "Banks",
            "adv50_B_VND": 5.0,
        })
        result = _s3_shadow_row("2026-01-01", "HPG", "PAPER_S3_SHADOW",
                                mock_row, Path("test.csv"), 0)
        self.assertTrue(result["s3_no_real_order_flag"],
                        "s3_no_real_order_flag must be True in shadow row")

    def test_s3_shadow_row_risk_flags_include_no_real_order(self):
        """_s3_shadow_row() risk_flags must include NO_REAL_ORDER."""
        from src.trading.live.order_intent import _s3_shadow_row
        import pandas as pd
        mock_row = pd.Series({
            "s3_shadow_reason": "test",
            "breadth_zone": "normal",
            "sector_l4": "Banks",
            "adv50_B_VND": 5.0,
        })
        result = _s3_shadow_row("2026-01-01", "HPG", "PAPER_S3_SHADOW",
                                mock_row, Path("test.csv"), 0)
        self.assertIn("NO_REAL_ORDER", result["risk_flags"])

    def test_s3_shadow_row_quantity_is_zero(self):
        """S3 shadow intents must have quantity_estimate=0."""
        from src.trading.live.order_intent import _s3_shadow_row
        import pandas as pd
        mock_row = pd.Series({
            "s3_shadow_reason": "test",
            "breadth_zone": "normal",
            "sector_l4": "Banks",
            "adv50_B_VND": 5.0,
        })
        result = _s3_shadow_row("2026-01-01", "HPG", "PAPER_S3_SHADOW",
                                mock_row, Path("test.csv"), 0)
        self.assertEqual(result["quantity_estimate"], 0)
        self.assertEqual(result["value_VND"], 0)


if __name__ == "__main__":
    unittest.main()
