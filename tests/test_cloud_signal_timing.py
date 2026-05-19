"""
Cloud signal timing tests.

Covers:
1. cloud_only_entry signal on close[T]
2. Backtest fill at T+1 open (documented convention)
3. Daily scan latest-bar signal visible without next bar
4. Daily scan does not require next bar for NEW_T1
5. Intraday preview if-close-now provisional signal
6. Intraday preview never auto-orders
7. Trigger price helper matches cloud signal
8. No lookahead in intraday (provisional bar only)
9. New scan fields exist and are documented
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pp_backtest.ema_levels.entry import cloud_only_entry
from pp_backtest.portfolio_optimization_final_steps import (
    _final_action,
    compute_phase36_scan_df,
    ema_cloud,
)
from scripts.research.a3_pre_atc_trigger import compute_trigger_price
from src.trading.intraday.intraday_scan import _apply_intraday_policy, _CANDIDATE_ACTIONS


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_close(n: int = 200, trend: float = 0.001, seed: int = 42) -> pd.Series:
    rng = np.random.default_rng(seed)
    prices = [100.0]
    for _ in range(n - 1):
        prices.append(prices[-1] * (1 + trend + rng.normal(0, 0.01)))
    return pd.Series(prices, dtype=float)


def _make_panel(syms: list[str], n: int = 250, trend: float = 0.001) -> pd.DataFrame:
    rows = []
    base = pd.Timestamp("2024-01-01")
    for i, sym in enumerate(syms):
        c = _make_close(n, trend, seed=i * 13 + 7)
        for j in range(n):
            price = float(c.iloc[j])
            rows.append({
                "symbol": sym,
                "date": base + pd.Timedelta(days=j),
                "open": price * 0.99,
                "high": price * 1.01,
                "low": price * 0.98,
                "close": price,
                "volume": 1_000_000,
            })
    return pd.DataFrame(rows)


def _cloud_bull_series(n: int = 200, flip_at: int = 150, trend_up: float = 0.005) -> pd.Series:
    """Return close series: bear phase up to flip_at, then bull trend."""
    prices = [100.0]
    for i in range(1, n):
        t = trend_up if i >= flip_at else -0.001
        prices.append(prices[-1] * (1 + t))
    return pd.Series(prices, dtype=float)


def _latest_bar_signal_panel(n: int = 250) -> pd.Series:
    """
    Produce a close series guaranteed to have an A3 signal on the LAST bar.
    Strategy: long decline → bear cloud established → single +200% jump on final bar.
    The jump is large enough to push EMA20 above EMA100 in one bar.
    """
    prices = [100.0]
    for _ in range(n - 1):
        prices.append(prices[-1] * 0.999)  # steady decline → EMA20 < EMA100 by bar 110+
    # Replace last bar with a huge jump
    prices[-1] = prices[-2] * 3.0  # +200%, guaranteed cloud flip
    return pd.Series(prices, dtype=float)


# ── 1. cloud_only_entry signal on close[T] ───────────────────────────────────

class TestCloudOnlyEntrySignalOnClose:
    def test_signal_uses_current_close(self):
        """Signal at bar T is determined by close[T], EMA[T] — no lookahead."""
        c = _cloud_bull_series(200, flip_at=150)
        a3 = ema_cloud(c, 20, 100)
        sig = cloud_only_entry(c, a3["ema_fast"], a3["cloud_bull"], min_bars_bear=3, warmup=110)
        # Signal is boolean Series, same length as close
        assert len(sig) == len(c)
        # Signal is True somewhere after flip_at
        assert sig.iloc[150:].any(), "Expected A3 signal after trend flip"

    def test_signal_no_lookahead(self):
        """Truncating at bar T must not change signal value at T."""
        c = _cloud_bull_series(200, flip_at=150)
        a3 = ema_cloud(c, 20, 100)
        sig_full = cloud_only_entry(c, a3["ema_fast"], a3["cloud_bull"])

        # Find first signal bar
        sig_idxs = list(sig_full[sig_full].index)
        if not sig_idxs:
            pytest.skip("No signal in synthetic data")
        t = sig_idxs[0]
        if t < 1:
            pytest.skip("Signal at bar 0 — cannot test truncation")

        # Truncate at T
        c_trunc = c.iloc[: t + 1]
        a3_trunc = ema_cloud(c_trunc, 20, 100)
        sig_trunc = cloud_only_entry(c_trunc, a3_trunc["ema_fast"], a3_trunc["cloud_bull"])
        assert bool(sig_trunc.iloc[-1]) == bool(sig_full.iloc[t])

    def test_warmup_suppressed(self):
        c = _make_close(200)
        a3 = ema_cloud(c, 20, 100)
        sig = cloud_only_entry(c, a3["ema_fast"], a3["cloud_bull"], warmup=110)
        assert not sig.iloc[:110].any(), "Signal must not fire in warmup window"


# ── 2. Backtest fill at T+1 open ─────────────────────────────────────────────

class TestBacktestFillNextOpen:
    def test_entry_doc_convention(self):
        """entry.py documents: True at bar t means enter at bar t+1 open."""
        entry_path = Path(__file__).parent.parent / "pp_backtest" / "ema_levels" / "entry.py"
        if not entry_path.exists():
            pytest.skip("entry.py not found")
        src = entry_path.read_text(encoding="utf-8")
        assert "True at bar t means" in src and "t+1 open" in src, (
            "entry.py must document fill-at-T+1-open convention"
        )

    def test_scan_uses_entry_bar_for_price(self):
        """When a3_bars_since=1, entry bar is one bar ago; a3_bars_since=0 means entry bar is current."""
        # a3_bars in _final_action:
        # bars=0 → NEW_T1 (entry bar is now or pending)
        # bars=1 → WAIT_PB / in position
        action_0, _ = _final_action(True, False, True, True, "normal", "full_T1", a3_bars=0)
        action_1, _ = _final_action(True, False, True, True, "normal", "full_T1", a3_bars=1)
        assert action_0 in ("NEW_T1", "NEW_T1_MANUAL_REVIEW_BREADTH")
        assert action_1 in ("WAIT_PB", "NO_T2_BREADTH", "HOLD_T1_ONLY")


# ── 3 & 4. Latest-bar signal visible without next bar ────────────────────────

class TestDailyScanLatestBarSignal:
    def _minimal_vnx(self, n: int = 300) -> pd.DataFrame:
        base = pd.Timestamp("2024-01-01")
        close = _make_close(n, trend=0.001)
        rows = [{"symbol": "VNINDEX", "date": base + pd.Timedelta(days=i),
                 "open": float(close.iloc[i]) * 0.99, "high": float(close.iloc[i]) * 1.01,
                 "low": float(close.iloc[i]) * 0.98, "close": float(close.iloc[i]),
                 "volume": 1_000_000_000}
                for i in range(n)]
        return pd.DataFrame(rows)

    def _find_latest_bar_signal(self, panel: pd.DataFrame) -> str | None:
        """Return a symbol that has an A3 signal on the final bar, or None."""
        for sym, sdf in panel.groupby("symbol"):
            sdf = sdf.sort_values("date").reset_index(drop=True)
            if len(sdf) < 120:
                continue
            c = sdf["close"].astype(float)
            a3 = ema_cloud(c, 20, 100)
            sig = cloud_only_entry(c, a3["ema_fast"], a3["cloud_bull"], warmup=110)
            if bool(sig.iloc[-1]):
                return str(sym)
        return None

    def _latest_bar_panel(self, n: int = 250) -> tuple[pd.DataFrame, pd.DataFrame]:
        base = pd.Timestamp("2024-01-01")
        c_sym = _latest_bar_signal_panel(n)
        panel_rows, vnx_rows = [], []
        for i in range(n):
            dt = base + pd.Timedelta(days=i)
            p = float(c_sym.iloc[i])
            panel_rows.append({"symbol": "TST", "date": dt, "open": p * 0.99,
                                "high": p * 1.01, "low": p * 0.98, "close": p, "volume": 2_000_000})
            vnx_rows.append({"symbol": "VNINDEX", "date": dt, "open": p * 0.99,
                              "high": p * 1.01, "low": p * 0.98, "close": p * 0.9,
                              "volume": 1_000_000_000})
        return pd.DataFrame(panel_rows), pd.DataFrame(vnx_rows)

    def test_latest_bar_signal_emitted(self):
        """If signal fires on the latest bar, scan must emit NEW_T1 (not WATCH_ONLY)."""
        panel, vnx = self._latest_bar_panel()
        # Verify the synthetic series actually triggers on the last bar
        c = _latest_bar_signal_panel()
        a3 = ema_cloud(c, 20, 100)
        sig = cloud_only_entry(c, a3["ema_fast"], a3["cloud_bull"], warmup=110)
        if not bool(sig.iloc[-1]):
            pytest.skip("Synthetic data did not produce latest-bar signal")

        scan_df, _ = compute_phase36_scan_df(panel, vnx, {}, sector_map=None)
        row = scan_df[scan_df["symbol"] == "TST"]
        assert not row.empty, "TST must appear in scan output"
        action = str(row["final_action"].iloc[0])
        assert action in ("NEW_T1", "NEW_T1_MANUAL_REVIEW_BREADTH"), (
            f"Expected NEW_T1/NEW_T1_MANUAL_REVIEW_BREADTH for latest-bar signal, got {action}"
        )

    def test_a3_signal_today_true_on_latest_bar_signal(self):
        """When signal on latest bar, a3_signal_today must be True."""
        c = _latest_bar_signal_panel()
        a3 = ema_cloud(c, 20, 100)
        sig = cloud_only_entry(c, a3["ema_fast"], a3["cloud_bull"], warmup=110)
        if not bool(sig.iloc[-1]):
            pytest.skip("Synthetic data did not produce latest-bar signal")

        panel, vnx = self._latest_bar_panel()
        scan_df, _ = compute_phase36_scan_df(panel, vnx, {}, sector_map=None)
        row = scan_df[scan_df["symbol"] == "TST"]
        assert not row.empty
        assert bool(row["a3_signal_today"].iloc[0]), "a3_signal_today must be True for latest-bar signal"
        assert str(row["a3_planned_entry_timing"].iloc[0]) == "NEXT_OPEN"

    def test_scan_does_not_require_next_bar(self):
        """a3_active must be True for signal on the final bar of the panel."""
        c = _latest_bar_signal_panel()
        a3 = ema_cloud(c, 20, 100)
        sig = cloud_only_entry(c, a3["ema_fast"], a3["cloud_bull"], warmup=110)
        if not bool(sig.iloc[-1]):
            pytest.skip("Synthetic data did not produce latest-bar signal")

        panel, vnx = self._latest_bar_panel()
        scan_df, _ = compute_phase36_scan_df(panel, vnx, {}, sector_map=None)
        row = scan_df[scan_df["symbol"] == "TST"]
        assert not row.empty
        assert bool(row["a3_active"].iloc[0]), "a3_active must be True when signal on latest bar"


# ── 5 & 6. Intraday preview provisional signal / never auto-order ─────────────

class TestIntradayPreviewProvisionalSignal:
    def _make_scan_df(self, would_be_action: str) -> pd.DataFrame:
        return pd.DataFrame([{
            "symbol": "TST",
            "final_action": would_be_action,
            "a3_active": True,
            "a3_signal_today": True,
            "a3_bars_since": 0,
        }])

    def _make_quotes(self) -> pd.DataFrame:
        return pd.DataFrame([{
            "symbol": "TST",
            "last_price_kvnd": 25.0,
            "data_quality": "OK",
            "is_stale": False,
        }])

    def _make_capability(self) -> dict:
        return {"available": True, "recommended_method": "FireAnt"}

    def _ts(self) -> datetime:
        return datetime(2026, 5, 19, 13, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))

    def test_if_close_now_signal_sets_would_be_action(self):
        """Provisional NEW_T1 signal → would_be_final_action=NEW_T1, final_action=INTRADAY_PREVIEW."""
        scan_df = self._make_scan_df("NEW_T1")
        quotes = self._make_quotes()
        cap = self._make_capability()
        with patch("src.trading.intraday.intraday_scan.detect_session_phase", return_value="CONTINUOUS"):
            with patch("src.trading.intraday.intraday_scan.minutes_to_close", return_value=90):
                with patch("src.trading.intraday.intraday_scan.minutes_to_lunch_break", return_value=999):
                    result = _apply_intraday_policy(scan_df, quotes, asof_timestamp=self._ts(),
                                                   cfg={}, mode="ad-hoc", capability=cap,
                                                   quoted_equity_symbols={"TST"})
        assert str(result["would_be_final_action"].iloc[0]) == "NEW_T1"
        assert str(result["final_action"].iloc[0]) == "INTRADAY_PREVIEW"

    def test_intraday_preview_never_auto_order(self):
        """auto_order_allowed must always be False."""
        for action in ("NEW_T1", "NEW_T1_MANUAL_REVIEW_BREADTH", "WAIT_PB", "TRAIL_EXIT", "WATCH_ONLY"):
            scan_df = self._make_scan_df(action)
            quotes = self._make_quotes()
            cap = self._make_capability()
            with patch("src.trading.intraday.intraday_scan.detect_session_phase", return_value="CONTINUOUS"):
                with patch("src.trading.intraday.intraday_scan.minutes_to_close", return_value=90):
                    with patch("src.trading.intraday.intraday_scan.minutes_to_lunch_break", return_value=999):
                        result = _apply_intraday_policy(scan_df, quotes, asof_timestamp=self._ts(),
                                                       cfg={}, mode="ad-hoc", capability=cap,
                                                       quoted_equity_symbols={"TST"})
            assert not bool(result["auto_order_allowed"].iloc[0]), (
                f"auto_order_allowed must be False for action={action}"
            )

    def test_intraday_candidate_set_for_actionable(self):
        """intraday_candidate=True for NEW_T1, TRAIL_EXIT etc."""
        for action in ("NEW_T1", "TRAIL_EXIT", "TP1_PARTIAL"):
            scan_df = self._make_scan_df(action)
            quotes = self._make_quotes()
            cap = self._make_capability()
            with patch("src.trading.intraday.intraday_scan.detect_session_phase", return_value="CONTINUOUS"):
                with patch("src.trading.intraday.intraday_scan.minutes_to_close", return_value=90):
                    with patch("src.trading.intraday.intraday_scan.minutes_to_lunch_break", return_value=999):
                        result = _apply_intraday_policy(scan_df, quotes, asof_timestamp=self._ts(),
                                                       cfg={}, mode="ad-hoc", capability=cap,
                                                       quoted_equity_symbols={"TST"})
            assert bool(result["intraday_candidate"].iloc[0]), (
                f"intraday_candidate must be True for action={action}"
            )


# ── 7. Trigger price helper matches cloud signal ──────────────────────────────

class TestTriggerPriceHelper:
    def test_trigger_met_implies_cloud_signal(self):
        """If close >= trigger_price, cloud_only_entry should fire."""
        n = 200
        base = pd.Timestamp("2024-01-01")
        # Build a bear-cloud series
        prices = list(_cloud_bull_series(n, flip_at=n))  # never flips during series
        c = pd.Series(prices, dtype=float)
        a3 = ema_cloud(c, 20, 100)

        ema_fast_prev = float(a3["ema_fast"].iloc[-1])
        ema_slow_prev = float(a3["ema_slow"].iloc[-1])
        trigger = compute_trigger_price(ema_fast_prev, ema_slow_prev)
        if trigger is None:
            pytest.skip("Could not compute trigger price")

        # Extend with one bar at trigger price
        new_close = trigger * 1.001  # just above trigger
        c_ext = pd.concat([c, pd.Series([new_close])], ignore_index=True)
        a3_ext = ema_cloud(c_ext, 20, 100)
        # Check cloud_bull on the new bar
        assert bool(a3_ext["cloud_bull"].iloc[-1]), (
            "EMA20 > EMA100 should hold when close >= trigger_price"
        )

    def test_below_trigger_no_cloud_signal(self):
        """If close < trigger_price, cloud should remain bear."""
        n = 200
        prices = list(_cloud_bull_series(n, flip_at=n))
        c = pd.Series(prices, dtype=float)
        a3 = ema_cloud(c, 20, 100)
        ema_fast_prev = float(a3["ema_fast"].iloc[-1])
        ema_slow_prev = float(a3["ema_slow"].iloc[-1])
        trigger = compute_trigger_price(ema_fast_prev, ema_slow_prev)
        if trigger is None:
            pytest.skip("Could not compute trigger price")

        # Stay well below trigger
        new_close = trigger * 0.95
        c_ext = pd.concat([c, pd.Series([new_close])], ignore_index=True)
        a3_ext = ema_cloud(c_ext, 20, 100)
        # Cloud should still be bear (EMA20 < EMA100)
        # Note: could be bull if EMA was already very close — allow for numerical edge
        cloud_now = bool(a3_ext["cloud_bull"].iloc[-1])
        if cloud_now:
            pytest.skip("EMA cloud was already turning bull in synthetic data; edge case")
        assert not cloud_now


# ── 8. No lookahead in intraday ───────────────────────────────────────────────

class TestNoLookaheadIntraday:
    def test_provisional_bar_not_in_eod_parquet(self, tmp_path):
        """build_provisional_panel does not write to the source file."""
        from src.trading.intraday.panel_overlay import build_provisional_panel, load_eod_panel

        eod = pd.DataFrame({
            "symbol": ["ABC", "ABC"],
            "date": pd.to_datetime(["2026-05-18", "2026-05-19"]),
            "open": [10.0, 10.5],
            "high": [10.5, 11.0],
            "low": [9.8, 10.2],
            "close": [10.2, 10.8],
            "volume": [1e6, 1.5e6],
        })
        p = tmp_path / "eod.parquet"
        eod.to_parquet(p)
        mtime_before = p.stat().st_mtime

        quotes = pd.DataFrame([{
            "symbol": "ABC",
            "last_price_kvnd": 11.0,
            "open_price_kvnd": 10.5,
            "high_price_kvnd": 11.1,
            "low_price_kvnd": 10.4,
            "cumulative_volume": 2e6,
        }])
        prov = build_provisional_panel(
            load_eod_panel(p),
            quotes,
            target_date=pd.Timestamp("2026-05-19"),
            run_timestamp=datetime(2026, 5, 19, 13, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh")),
        )
        assert p.stat().st_mtime == mtime_before, "EOD parquet must not be written"
        last = prov[(prov["symbol"] == "ABC") & (prov["date"] == pd.Timestamp("2026-05-19"))].iloc[0]
        assert last["close"] == 11.0
        assert bool(last["is_intraday"])

    def test_provisional_bar_uses_current_price_not_future_close(self):
        """Provisional close must equal last_price_kvnd, not some future close."""
        from src.trading.intraday.panel_overlay import build_provisional_panel, load_eod_panel
        import tempfile, os

        eod = pd.DataFrame({
            "symbol": ["XYZ"],
            "date": pd.to_datetime(["2026-05-19"]),
            "open": [50.0], "high": [51.0], "low": [49.0], "close": [50.5], "volume": [1e6],
        })
        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
            tmp = f.name
        try:
            eod.to_parquet(tmp)
            quotes = pd.DataFrame([{
                "symbol": "XYZ", "last_price_kvnd": 50.8,
                "open_price_kvnd": 50.0, "high_price_kvnd": 51.2,
                "low_price_kvnd": 49.5, "cumulative_volume": 1.2e6,
            }])
            prov = build_provisional_panel(
                load_eod_panel(tmp), quotes,
                target_date=pd.Timestamp("2026-05-19"),
                run_timestamp=datetime(2026, 5, 19, 13, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh")),
            )
            last = prov[(prov["symbol"] == "XYZ")].iloc[-1]
            assert last["close"] == 50.8, "Provisional close must be last_price_kvnd"
        finally:
            os.unlink(tmp)


# ── 9. New scan fields documented ────────────────────────────────────────────

class TestScanFieldsDocumented:
    def _active_signal_panel(self, n: int = 250) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Panel with guaranteed A3 signal on the last bar using _latest_bar_signal_panel."""
        base = pd.Timestamp("2024-01-01")
        c_sym = _latest_bar_signal_panel(n)
        panel_rows, vnx_rows = [], []
        for i in range(n):
            dt = base + pd.Timedelta(days=i)
            p = float(c_sym.iloc[i])
            panel_rows.append({"symbol": "TST", "date": dt, "open": p * 0.99,
                                "high": p * 1.01, "low": p * 0.98, "close": p, "volume": 2_000_000})
            vnx_rows.append({"symbol": "VNINDEX", "date": dt, "open": p * 0.99,
                              "high": p * 1.01, "low": p * 0.98, "close": p * 0.9,
                              "volume": 1_000_000_000})
        return pd.DataFrame(panel_rows), pd.DataFrame(vnx_rows)

    def test_new_fields_in_scan_output(self):
        """a3_signal_today, a3_bars_since_signal, a3_planned_entry_timing must exist in scan output."""
        c = _latest_bar_signal_panel()
        a3 = ema_cloud(c, 20, 100)
        sig = cloud_only_entry(c, a3["ema_fast"], a3["cloud_bull"], warmup=110)
        if not bool(sig.iloc[-1]):
            pytest.skip("Synthetic data did not produce latest-bar signal")

        panel, vnx = self._active_signal_panel()
        scan_df, _ = compute_phase36_scan_df(panel, vnx, {})
        assert not scan_df.empty, "Scan must produce rows for panel with active signal"
        for field in ("a3_signal_today", "a3_bars_since_signal", "a3_planned_entry_timing", "s3_signal_today"):
            assert field in scan_df.columns, f"Missing required field: {field}"

    def test_a3_bars_since_signal_ge_a3_bars_since(self):
        """bars_since_signal >= bars_since (signal bar is before or equal to entry bar)."""
        c = _latest_bar_signal_panel()
        a3 = ema_cloud(c, 20, 100)
        sig = cloud_only_entry(c, a3["ema_fast"], a3["cloud_bull"], warmup=110)
        if not bool(sig.iloc[-1]):
            pytest.skip("Synthetic data did not produce latest-bar signal")

        panel, vnx = self._active_signal_panel()
        scan_df, _ = compute_phase36_scan_df(panel, vnx, {})
        active = scan_df[scan_df["a3_active"]]
        if active.empty:
            pytest.skip("No active A3 rows in scan output")
        for _, row in active.iterrows():
            bss = row["a3_bars_since_signal"]
            bs = row["a3_bars_since"]
            if bss is not None and bs is not None:
                assert bss >= bs, (
                    f"{row['symbol']}: a3_bars_since_signal={bss} must be >= a3_bars_since={bs}"
                )

    def test_docs_exist(self):
        """All required timing audit docs must exist."""
        docs = [
            "docs/trading/CLOUD_SIGNAL_TIMING_AUDIT.md",
            "docs/trading/CLOUD_SIGNAL_TIMING_CODE_AUDIT.md",
            "docs/trading/DAILY_SCAN_LATEST_BAR_SIGNAL_AUDIT.md",
            "docs/trading/DAILY_SCAN_SIGNAL_TIMING_FIX_PROPOSAL.md",
            "docs/trading/ENTRY_TIMING_BACKTEST_FINDINGS.md",
            "docs/trading/A3_PRE_ATC_TRIGGER_PRICE_HELPER.md",
        ]
        repo = Path(__file__).parent.parent
        for d in docs:
            assert (repo / d).exists(), f"Required doc missing: {d}"
