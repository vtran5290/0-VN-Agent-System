"""Tests for portfolio_state SSoT module and cloud daily report integration."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.trading.portfolio_state import (
    _HOLDINGS_TXT,
    _POSITIONS_DERIVED_JSON,
    _POSITIONS_FALLBACK_CSV,
    PORTFOLIO_STATE_PATH,
    get_current_nav_vnd,
    get_positions_path,
    load_current_positions,
    load_portfolio_state,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_state(tmp: Path, **kwargs) -> Path:
    p = tmp / "portfolio_state.json"
    data = {
        "as_of_date": "2026-05-19",
        "nav_vnd": 6_000_000_000,
        "portfolio_name": "production",
        "positions_path": None,
        "notes": "test",
    }
    data.update(kwargs)
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _make_eod_row(**kwargs):
    base = {
        "symbol": "HPG", "as_of_date": "2026-05-19", "close_kVND": 20.0,
        "final_action": "NEW_T1", "final_action_reason": "test",
        "a3_active": True, "a3_signal_today": False, "a3_planned_entry_timing": "FILLED",
        "a3_bars_since": 1, "a3_bars_since_signal": 1,
        "a3_rank_score": 1.5, "a3_rank_reason": "test", "ed_score": 0.8,
        "pb_trigger_price": 18.0, "tp1_price": 23.6, "trail_price": 21.0,
        "pct_cloud_bull_a3": 0.55, "pct_cloud_bull_s3": 0.30,
        "breadth_zone": "normal", "breadth_t1_permission": True, "breadth_t2_permission": False,
        "regime_bull": True, "liq_warn_T1": "OK", "s3_lead_bucket": "none",
        "s3_fresh_lead_flag": False, "s3_shadow_action": "", "s3_no_real_order_flag": True,
        "sector_l4": "Steel", "sector_l4_stress_flag": "OK",
        "in_a3_universe": True, "in_s3_universe": False, "strategy_classification": "A3_PRODUCTION",
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# 1. nav_vnd from portfolio_state is used in report
# ---------------------------------------------------------------------------

class TestPortfolioStateNavUsedInReport:
    def test_portfolio_state_nav_used_in_report(self, tmp_path, monkeypatch):
        import src.trading.portfolio_state as ps
        import src.trading.reports.cloud_daily_report as m

        state_path = _write_state(tmp_path, nav_vnd=8_500_000_000)
        monkeypatch.setattr(ps, "PORTFOLIO_STATE_PATH", state_path)
        monkeypatch.setattr(m, "REPORTS_DIR", tmp_path)

        scan_df = pd.DataFrame([_make_eod_row()])
        inputs = {
            "mode": "eod", "scan_df": scan_df, "intraday_df": pd.DataFrame(),
            "intraday_meta": {}, "holdings": ["HPG"],
            "nav_vnd": 8_500_000_000.0, "positions_df": pd.DataFrame({"symbol": ["HPG"]}),
            "positions_source": str(state_path), "portfolio_state_path": str(state_path),
            "prev_json": None, "warnings": [], "scan_path": None, "files_used": [],
        }
        ts = datetime(2026, 5, 19, 16, 0, tzinfo=timezone.utc)
        html, md, jdata = m.build_report("eod", inputs, ts)

        assert "8.50" in html or "8.5" in html, "NAV badge should show 8.50bn"
        assert jdata["portfolio_nav_vnd"] == 8_500_000_000.0


# ---------------------------------------------------------------------------
# 2. Port excludes cash; NAV is not inferred from positions
# ---------------------------------------------------------------------------

class TestPortExcludesCashNavNotInferred:
    def test_port_excludes_cash_and_nav_not_inferred(self, tmp_path, monkeypatch):
        import src.trading.reports.cloud_daily_report as m
        monkeypatch.setattr(m, "REPORTS_DIR", tmp_path)

        # Provide positions with market value != nav_vnd
        positions_df = pd.DataFrame([
            {"symbol": "HPG", "lots": 10000, "entry_price": 200000.0},
        ])
        inputs = {
            "mode": "eod", "scan_df": pd.DataFrame([_make_eod_row()]),
            "intraday_df": pd.DataFrame(), "intraday_meta": {}, "holdings": ["HPG"],
            "nav_vnd": 6_000_000_000.0,
            "positions_df": positions_df, "positions_source": "test_positions.csv",
            "portfolio_state_path": "data/trading/live/portfolio_state.json",
            "prev_json": None, "warnings": [], "scan_path": None, "files_used": [],
        }
        ts = datetime(2026, 5, 19, 16, 0, tzinfo=timezone.utc)
        html, md, jdata = m.build_report("eod", inputs, ts)

        # NAV must come from portfolio_state, not from positions math
        assert jdata["portfolio_nav_vnd"] == 6_000_000_000.0
        assert jdata["port_excludes_cash"] is True
        assert jdata["nav_is_user_updated"] is True
        # Report must say port excludes cash somewhere
        assert "excludes cash" in html.lower() or "excludes cash" in md.lower()


# ---------------------------------------------------------------------------
# 3. Missing portfolio state warns but does not crash
# ---------------------------------------------------------------------------

class TestMissingPortfolioStateWarns:
    def test_missing_portfolio_state_warns_but_does_not_crash(self, tmp_path, monkeypatch):
        import src.trading.portfolio_state as ps
        import src.trading.reports.cloud_daily_report as m

        monkeypatch.setattr(ps, "PORTFOLIO_STATE_PATH", tmp_path / "nonexistent.json")
        monkeypatch.setattr(ps, "_POSITIONS_FALLBACK_CSV", tmp_path / "no.csv")
        monkeypatch.setattr(ps, "_POSITIONS_DERIVED_JSON", tmp_path / "no.json")
        monkeypatch.setattr(ps, "_HOLDINGS_TXT", tmp_path / "no.txt")
        monkeypatch.setattr(m, "REPORTS_DIR", tmp_path)

        result = m.write_report("eod")
        assert result["report_status"] in ("OK", "PREVIEW_OK", "NEEDS_REVIEW")
        assert any("portfolio state" in w.lower() for w in result.get("warnings", []))


# ---------------------------------------------------------------------------
# 4. Invalid nav triggers warning
# ---------------------------------------------------------------------------

class TestInvalidNavTriggersWarning:
    def test_invalid_nav_triggers_warning(self, tmp_path, monkeypatch):
        import src.trading.portfolio_state as ps
        monkeypatch.setattr(ps, "PORTFOLIO_STATE_PATH", _write_state(tmp_path, nav_vnd="not_a_number"))
        state = ps.load_portfolio_state()
        nav = ps.get_current_nav_vnd(state)
        assert nav is None

    def test_zero_nav_triggers_warning(self, tmp_path, monkeypatch):
        import src.trading.portfolio_state as ps
        monkeypatch.setattr(ps, "PORTFOLIO_STATE_PATH", _write_state(tmp_path, nav_vnd=0))
        state = ps.load_portfolio_state()
        nav = ps.get_current_nav_vnd(state)
        assert nav is None

    def test_negative_nav_triggers_warning(self, tmp_path, monkeypatch):
        import src.trading.portfolio_state as ps
        monkeypatch.setattr(ps, "PORTFOLIO_STATE_PATH", _write_state(tmp_path, nav_vnd=-1))
        state = ps.load_portfolio_state()
        nav = ps.get_current_nav_vnd(state)
        assert nav is None


# ---------------------------------------------------------------------------
# 5. positions_path from portfolio_state is used
# ---------------------------------------------------------------------------

class TestPositionsPathFromPortfolioState:
    def test_positions_path_from_portfolio_state_used(self, tmp_path, monkeypatch):
        import src.trading.portfolio_state as ps

        # Write a custom positions CSV
        pos_csv = tmp_path / "my_positions.csv"
        pos_csv.write_text("symbol,lots\nVPB,5000\nHDB,3000\n", encoding="utf-8")

        state_path = _write_state(tmp_path, positions_path=str(pos_csv))
        monkeypatch.setattr(ps, "PORTFOLIO_STATE_PATH", state_path)

        state = ps.load_portfolio_state(state_path)
        df, source = ps.load_current_positions(state)

        assert "VPB" in df["symbol"].values
        assert "HDB" in df["symbol"].values
        assert str(pos_csv) in source or "my_positions" in source

    def test_json_positions_normalized_ticker_to_symbol(self, tmp_path, monkeypatch):
        import src.trading.portfolio_state as ps

        pos_json = tmp_path / "positions.json"
        pos_json.write_text(
            json.dumps([{"ticker": "stb", "lots": 14500, "entry_price": 70000.0}]),
            encoding="utf-8",
        )
        state_path = _write_state(tmp_path, positions_path=str(pos_json))
        state = ps.load_portfolio_state(state_path)
        df, _ = ps.load_current_positions(state)
        assert "symbol" in df.columns
        assert "STB" in df["symbol"].values


# ---------------------------------------------------------------------------
# 6. Missing current positions warns but does not crash
# ---------------------------------------------------------------------------

class TestCurrentPositionsMissingWarns:
    def test_current_positions_missing_warns_but_does_not_crash(self, tmp_path, monkeypatch):
        import src.trading.portfolio_state as ps
        import src.trading.reports.cloud_daily_report as m

        state_path = _write_state(tmp_path, positions_path=str(tmp_path / "no_positions.csv"))
        monkeypatch.setattr(ps, "PORTFOLIO_STATE_PATH", state_path)
        monkeypatch.setattr(ps, "_POSITIONS_FALLBACK_CSV", tmp_path / "no.csv")
        monkeypatch.setattr(ps, "_POSITIONS_DERIVED_JSON", tmp_path / "no.json")
        monkeypatch.setattr(ps, "_HOLDINGS_TXT", tmp_path / "no.txt")
        monkeypatch.setattr(m, "REPORTS_DIR", tmp_path)

        result = m.write_report("eod")
        # Must not crash; should warn about missing positions
        assert result["report_status"] in ("OK", "PREVIEW_OK", "NEEDS_REVIEW")
        # At least one of these warnings should appear
        warns = " ".join(result.get("warnings", [])).lower()
        assert "position" in warns or "portfolio" in warns or "holdings" in warns


# ---------------------------------------------------------------------------
# 7. No hardcoded 6bn NAV in live/report/workflow code
# ---------------------------------------------------------------------------

class TestNoHardcoded6bnNavInLiveCode:
    """Ensure no live/report/workflow Python file hardcodes 6_000_000_000 as NAV."""

    # Files where 6B is acceptable (paper account config, test fixtures,
    # backtest samples, liquidity threshold arrays — not live NAV assumptions)
    _ALLOWED_PATHS = {
        "config/paper_accounts.yaml",
        "config/trading.yaml",
        "config/live_trading.yaml",  # portfolio_size_VND — separate from report NAV
        "tests/",
        "pp_backtest/",
        "data/",
        "src/canslim/",
    }

    def test_no_hardcoded_6bn_nav_in_live_report_workflow(self):
        repo = Path(__file__).parent.parent
        violations = []
        check_dirs = [
            repo / "src" / "trading" / "reports",
            repo / "src" / "trading" / "live",
            repo / "src" / "trading" / "monitoring",
            repo / "scripts" / "reporting",
        ]
        patterns = ["6000000000", "6_000_000_000"]
        for d in check_dirs:
            if not d.exists():
                continue
            for py in d.rglob("*.py"):
                text = py.read_text(encoding="utf-8", errors="replace")
                for pat in patterns:
                    if pat in text:
                        rel = str(py.relative_to(repo))
                        violations.append(f"{rel}: contains '{pat}'")
        assert violations == [], (
            "Hardcoded 6B NAV found in live/report code:\n" + "\n".join(violations)
        )
