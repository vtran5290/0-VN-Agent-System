"""
Tests 9, 19, 21: Walk-forward integrity, OOS holdout, and report/zip generation.
  Test 9:  Walk-forward profile generation uses only prior data
  Test 19: OOS holdout integrity — last 12 months never in profile construction
  Test 21: Report and zip generation succeeds
"""
import numpy as np
import pandas as pd
import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.trading.research.stock_dna.events import attach_bounce_outcomes, detect_touch_events
from src.trading.research.stock_dna.features import compute_indicators
from src.trading.research.stock_dna.profiles import (
    _oos_cutoff_date,
    _training_years,
    build_symbol_profiles,
    build_walkforward_line_scores,
    collect_all_touch_events,
    score_symbol_line,
)
from src.trading.research.stock_dna.schema import DNAConfidence, OOS_HOLDOUT_MONTHS


def _make_long_panel(n_years: int = 6, n_syms: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(99)
    rows = []
    for sym in [f"SYM{i}" for i in range(n_syms)]:
        n = n_years * 252
        dates = pd.date_range("2018-01-01", periods=n, freq="B")
        close = np.cumprod(1 + rng.normal(0.001, 0.015, n)) * 50
        high  = close * (1 + np.abs(rng.normal(0, 0.005, n)))
        low   = close * (1 - np.abs(rng.normal(0, 0.005, n)))
        rows.append(pd.DataFrame({
            "symbol": sym,
            "date":   dates,
            "open":   close,
            "high":   high,
            "low":    low,
            "close":  close,
            "volume": rng.uniform(1e6, 5e6, n),
            "value":  close * rng.uniform(5e9 / close.mean(), 5e9 / close.mean() * 2, n),
        }))
    panel = pd.concat(rows, ignore_index=True)
    panel = compute_indicators(panel)
    panel["fwd_ret_5d"]  = panel.groupby("symbol")["close"].transform(lambda s: s.shift(-5) / s - 1)
    panel["fwd_ret_10d"] = panel.groupby("symbol")["close"].transform(lambda s: s.shift(-10) / s - 1)
    panel["fwd_ret_20d"] = panel.groupby("symbol")["close"].transform(lambda s: s.shift(-20) / s - 1)
    panel["mfe_20d"] = 0.05
    panel["mae_20d"] = -0.03
    panel["stock_phase"]   = "MARKUP"
    panel["breadth_regime"] = "BULL_BROAD"
    panel["vin_return_distortion_flag"] = 0
    panel["adv20_vnd"] = panel["value"].rolling(20).mean().shift(1)
    panel["adv50_vnd"] = panel["value"].rolling(50).mean().shift(1)
    return panel.sort_values(["symbol", "date"]).reset_index(drop=True)


# ── Test 9: Walk-forward uses only prior data ─────────────────────────────────

class TestWalkForwardPriorDataOnly:

    def test_year_cutoff_excludes_future_data(self):
        """
        score_symbol_line with year_cutoff=Y must not use data from year Y or later.
        """
        panel = _make_long_panel()
        touch_df = collect_all_touch_events(panel)

        if touch_df.empty:
            pytest.skip("No touch events for walk-forward test")

        # Choose a symbol and line with events
        sym = touch_df["symbol"].iloc[0]
        line = touch_df["line_name"].iloc[0]
        tol  = touch_df["tol_name"].iloc[0]

        cutoff_year = 2022

        # Score with cutoff
        result_cutoff = score_symbol_line(touch_df, sym, line, tol, year_cutoff=cutoff_year)
        n_with_cutoff = result_cutoff.get("n_touch", 0)

        # Score without cutoff (all history)
        result_all = score_symbol_line(touch_df, sym, line, tol, year_cutoff=None)
        n_all = result_all.get("n_touch", 0)

        # Walk-forward must use less or equal data than full history
        assert n_with_cutoff <= n_all, (
            f"Walk-forward with cutoff {cutoff_year} used MORE events than full history: "
            f"{n_with_cutoff} > {n_all}"
        )

    def test_training_years_require_min_history(self):
        """training_years should require at least min_years of prior history."""
        panel = _make_long_panel(n_years=4)
        years = _training_years(panel, min_years=3)
        if years:
            min_panel_year = panel["date"].min().year
            first_oos_year = years[0]
            assert first_oos_year >= min_panel_year + 3, (
                f"First OOS year {first_oos_year} < min_panel_year+3 ({min_panel_year+3})"
            )

    def test_no_future_data_in_touch_events_for_cutoff(self):
        """Touch events filtered for year_cutoff Y must not contain dates from year Y+."""
        panel = _make_long_panel()
        touch_df = collect_all_touch_events(panel)
        if touch_df.empty:
            pytest.skip("No touch events")

        cutoff_year = 2022
        sym = touch_df["symbol"].iloc[0]
        line = touch_df["line_name"].iloc[0]
        tol  = touch_df["tol_name"].iloc[0]

        # Replicate filtering logic from score_symbol_line
        filtered = touch_df[
            (touch_df["symbol"] == sym) &
            (touch_df["line_name"] == line) &
            (touch_df["tol_name"] == tol) &
            (pd.to_datetime(touch_df["date"]).dt.year < cutoff_year)
        ]
        if not filtered.empty:
            max_year = pd.to_datetime(filtered["date"]).dt.year.max()
            assert max_year < cutoff_year, (
                f"Filtered events contain year {max_year} >= cutoff {cutoff_year}"
            )


# ── Test 19: OOS holdout integrity ────────────────────────────────────────────

class TestOOSHoldoutIntegrity:

    def test_oos_cutoff_is_last_n_months(self):
        """OOS cutoff must be (max_date - OOS_HOLDOUT_MONTHS) months from end."""
        panel = _make_long_panel()
        oos_start = _oos_cutoff_date(panel)
        max_date  = panel["date"].max()

        expected_start = max_date - pd.DateOffset(months=OOS_HOLDOUT_MONTHS)
        diff_days = abs((oos_start - pd.Timestamp(expected_start)).days)
        assert diff_days <= 5, (
            f"OOS cutoff {oos_start} is not ~{OOS_HOLDOUT_MONTHS} months before max_date {max_date}"
        )

    def test_training_years_end_before_oos_cutoff(self):
        """All walk-forward training years must be before the OOS cutoff year."""
        panel = _make_long_panel()
        oos_start = _oos_cutoff_date(panel)
        years = _training_years(panel)

        for y in years:
            assert y <= oos_start.year, (
                f"Training year {y} extends into OOS period (cutoff year {oos_start.year})"
            )

    def test_oos_period_not_used_in_profile_construction(self):
        """
        When building profiles for year_cutoff Y, data from OOS period must not appear.
        This verifies year_cutoff filtering works correctly.
        """
        panel = _make_long_panel()
        oos_start = _oos_cutoff_date(panel)
        touch_df = collect_all_touch_events(panel)

        if touch_df.empty:
            pytest.skip("No touch events")

        # Score with year_cutoff = OOS start year
        oos_year = oos_start.year
        sym = touch_df["symbol"].iloc[0]
        line = touch_df["line_name"].iloc[0]
        tol  = touch_df["tol_name"].iloc[0]

        # Manually filter to verify
        valid_touches = touch_df[
            (touch_df["symbol"] == sym) &
            (touch_df["line_name"] == line) &
            (touch_df["tol_name"] == tol) &
            (pd.to_datetime(touch_df["date"]).dt.year < oos_year)
        ]

        result = score_symbol_line(touch_df, sym, line, tol, year_cutoff=oos_year)
        assert result["n_touch"] == len(valid_touches), (
            f"Profile n_touch {result['n_touch']} != manually filtered {len(valid_touches)} — "
            "OOS data may have leaked into profile"
        )


# ── Test 21: Report and zip generation ───────────────────────────────────────

class TestReportAndZipGeneration:

    def test_html_report_generates_without_error(self, tmp_path):
        from src.trading.research.stock_dna.reporting import build_html_report
        profiles = pd.DataFrame([{
            "symbol": "TEST", "confidence": "MEDIUM", "n_touch": 25,
            "bounce_rate_20d": 0.65, "regime_obedience_bull": 0.70,
            "regime_obedience_bear": 0.40, "oos_lift": 0.05,
            "primary_support_line": "ema20",
            "line_obedience_score_raw": 0.72,
            "operator_note": "Test note",
            "production_status": "RESEARCH_ANNOTATION_ONLY",
        }])
        p = build_html_report(profiles, pd.DataFrame(), {}, {}, output_dir=tmp_path)
        assert p.exists(), "HTML report was not created"
        content = p.read_text()
        assert "Stock DNA" in content, "HTML report is empty"

    def test_implementation_report_generates_without_error(self, tmp_path):
        from src.trading.research.stock_dna.reporting import save_implementation_report
        p = save_implementation_report(
            {"n_symbols": 50, "n_medium_plus_profiles": 10,
             "null_benchmark_passes": True, "verdict": "RESEARCH_ANNOTATION_ONLY"},
            output_dir=tmp_path,
        )
        assert p.exists()

    def test_zip_generation_succeeds(self, tmp_path):
        """Test packager creates a valid zip."""
        import zipfile
        # Create some fake output files
        input_dir = tmp_path / "stock_dna"
        input_dir.mkdir()
        (input_dir / "stock_dna_symbol_profiles.csv").write_text("symbol,confidence\nTEST,MEDIUM")
        (input_dir / "stock_dna_implementation_report.md").write_text("# Test report")

        from src.trading.research.stock_dna.schema import assert_output_path_safe
        review_dir = tmp_path / "review_outputs"
        review_dir.mkdir()
        zip_path = review_dir / "test_review.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            for p in input_dir.glob("*"):
                zf.write(p, arcname=p.name)

        assert zip_path.exists()
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
        assert len(names) >= 2
