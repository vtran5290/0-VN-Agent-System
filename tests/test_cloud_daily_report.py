"""Tests for cloud daily report — operator decision support."""
import json
import math
import sys
import tempfile
from pathlib import Path
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.trading.reports.cloud_daily_report import (
    classify_operator_action,
    build_report,
    load_inputs,
    normalize_bool,
    write_report,
)

# --- helpers ---

def _make_eod_row(**kwargs):
    """Minimal scan row for tests."""
    base = {
        "symbol": "TST", "as_of_date": "2026-05-19", "close_kVND": 20.0,
        "final_action": "NEW_T1", "final_action_reason": "test",
        "a3_active": True, "a3_signal_today": False, "a3_planned_entry_timing": "FILLED",
        "a3_bars_since": 1, "a3_bars_since_signal": 1,
        "a3_rank_score": 1.5, "a3_rank_reason": "high_ed", "ed_score": 0.8,
        "pb_trigger_price": 18.0, "tp1_price": 23.6, "trail_price": 21.0,
        "pct_cloud_bull_a3": 0.55, "pct_cloud_bull_s3": 0.30,
        "breadth_zone": "normal", "breadth_t1_permission": True, "breadth_t2_permission": False,
        "regime_bull": True, "liq_warn_T1": "OK", "s3_lead_bucket": "none",
        "s3_fresh_lead_flag": False, "s3_shadow_action": "", "s3_no_real_order_flag": True,
        "sector_l4": "Banks", "sector_l4_stress_flag": "OK",
        "in_a3_universe": True, "in_s3_universe": False, "strategy_classification": "A3_PRODUCTION",
    }
    base.update(kwargs)
    return base

def _make_intraday_row(**kwargs):
    row = _make_eod_row(**kwargs)
    row.update({
        "final_action": "INTRADAY_PREVIEW",
        "would_be_final_action": kwargs.get("would_be_final_action", "NEW_T1"),
        "auto_order_allowed": False,
        "manual_review_required": True,
        "intraday_candidate": True,
        "intraday_data_quality": "OK",
        "intraday_action_status": "MANUAL_REVIEW_REQUIRED",
        "session_phase": "PRE_ATC",
    })
    return row

def _make_inputs(scan_rows=None, intraday_rows=None, mode="eod", holdings=None):
    scan_df = pd.DataFrame(scan_rows or [_make_eod_row()])
    intraday_df = pd.DataFrame(intraday_rows or [])
    meta = {
        "status": "OK", "last_breadth": 0.55, "breadth_zone": "normal",
        "regime_bull": True, "last_s3_breadth": 0.30,
        "panel_asof": "2026-05-19", "eod_panel_asof_date": "2026-05-19",
        "session_phase": "PRE_ATC", "intraday_quote_coverage_pct": 0.95,
        "quoted_symbols_count": 10, "scan_symbols_count": 10, "missing_quote_count": 0,
        "vnindex": {"vnindex_eod_close": 1300, "vnindex_eod_regime_bull": True,
                    "vnindex_intraday_close": 1305, "vnindex_intraday_regime_bull": True,
                    "vnindex_overlay_applied": True, "vnindex_quote_quality": "OK",
                    "vnindex_regime_changed": False},
        "capability": {"available": True, "recommended_method": "FireAnt"},
    }
    return {
        "mode": mode, "scan_df": scan_df, "intraday_df": intraday_df,
        "intraday_meta": meta if intraday_rows is not None else {},
        "holdings": holdings or [], "prev_json": None,
        "warnings": [], "scan_path": None, "files_used": [],
    }


class TestEodReportGenerates:
    def test_eod_report_generates_html_and_md(self, tmp_path, monkeypatch):
        import src.trading.reports.cloud_daily_report as m
        monkeypatch.setattr(m, "REPORTS_DIR", tmp_path)
        inputs = _make_inputs()
        from datetime import datetime, timezone
        ts = datetime(2026, 5, 19, 11, 0, tzinfo=timezone.utc)
        html, md, jdata = build_report("eod", inputs, ts)
        assert "<html" in html
        assert "## " in md or "# " in md
        assert jdata["report_mode"] == "eod"
        assert "new_t1" in jdata["counts"]


class TestIntradayPreviewBanner:
    def test_intraday_report_generates_preview_only_banner(self, tmp_path, monkeypatch):
        import src.trading.reports.cloud_daily_report as m
        monkeypatch.setattr(m, "REPORTS_DIR", tmp_path)
        rows = [_make_intraday_row()]
        inputs = _make_inputs(scan_rows=rows, intraday_rows=rows, mode="pre-atc")
        from datetime import datetime, timezone
        ts = datetime(2026, 5, 19, 14, 0, tzinfo=timezone.utc)
        html, md, jdata = build_report("pre-atc", inputs, ts)
        assert "PREVIEW ONLY" in html
        assert "auto_order_allowed" in html.lower() or "AUTO ORDER" in html


class TestAutoOrderSafetyWarning:
    def test_intraday_auto_order_allowed_true_triggers_warning(self):
        row = _make_intraday_row()
        row["auto_order_allowed"] = True  # safety violation
        inputs = _make_inputs(scan_rows=[row], intraday_rows=[row], mode="pre-lunch")
        from datetime import datetime, timezone
        ts = datetime(2026, 5, 19, 11, 0, tzinfo=timezone.utc)
        _, _, jdata = build_report("pre-lunch", inputs, ts)
        assert jdata["report_status"] == "NEEDS_REVIEW"
        assert any("auto_order_allowed" in w.lower() for w in jdata["warnings"])


class TestS3PaperOnly:
    def test_s3_rows_are_paper_only(self):
        row = _make_eod_row(
            final_action="WATCH_ONLY", s3_shadow_action="PAPER_S3_SHADOW",
            s3_no_real_order_flag=True, in_s3_universe=True,
        )
        ca = classify_operator_action(row, "eod")
        assert ca["operator_action"] == "PAPER_ONLY"
        assert ca["action_group"] == "S3_PAPER"


class TestPendingEntryDisplay:
    def test_a3_signal_today_pending_levels_displayed_as_pending(self):
        row = _make_eod_row(
            final_action="NEW_T1", a3_signal_today=True,
            a3_planned_entry_timing="NEXT_OPEN",
            pb_trigger_price=float("nan"), tp1_price=float("nan"), trail_price=float("nan"),
        )
        inputs = _make_inputs(scan_rows=[row])
        from datetime import datetime, timezone
        ts = datetime(2026, 5, 19, 16, 0, tzinfo=timezone.utc)
        html, md, _ = build_report("eod", inputs, ts)
        assert "pending" in html.lower()
        assert "next session open" in html.lower() or "next open" in html.lower()


class TestNewT1Sorting:
    def test_new_t1_rows_sorted_by_a3_rank_score(self):
        rows = [
            _make_eod_row(symbol="BBB", a3_rank_score=0.5, final_action="NEW_T1"),
            _make_eod_row(symbol="AAA", a3_rank_score=2.0, final_action="NEW_T1"),
            _make_eod_row(symbol="CCC", a3_rank_score=1.0, final_action="NEW_T1"),
        ]
        inputs = _make_inputs(scan_rows=rows)
        from datetime import datetime, timezone
        ts = datetime(2026, 5, 19, 16, 0, tzinfo=timezone.utc)
        html, _, _ = build_report("eod", inputs, ts)
        idx_aaa = html.find("AAA")
        idx_ccc = html.find("CCC")
        idx_bbb = html.find("BBB")
        # AAA (rank 2.0) should appear before CCC (1.0) before BBB (0.5)
        assert idx_aaa < idx_ccc < idx_bbb


class TestBreadthT2Block:
    def test_breadth_less_40_blocks_t2_message(self):
        rows = [
            _make_eod_row(
                final_action="NO_T2_BREADTH", breadth_zone="defense",
                pct_cloud_bull_a3=0.35, breadth_t2_permission=False,
            )
        ]
        inputs = _make_inputs(scan_rows=rows)
        from datetime import datetime, timezone
        ts = datetime(2026, 5, 19, 16, 0, tzinfo=timezone.utc)
        html, md, jdata = build_report("eod", inputs, ts)
        assert "T2" in html
        assert "breadth" in html.lower() or "defense" in html.lower()
        assert jdata["counts"]["no_t2_breadth"] >= 1


class TestHoldingsMissing:
    def test_holdings_missing_does_not_crash(self, tmp_path, monkeypatch):
        import src.trading.portfolio_state as ps
        import src.trading.reports.cloud_daily_report as m

        # Portfolio state exists but points to a nonexistent positions file;
        # all fallback paths are also missing — positions chain is fully empty.
        state_path = tmp_path / "portfolio_state.json"
        state_path.write_text(
            '{"as_of_date":"2026-05-19","nav_vnd":6000000000,"positions_path":null}',
            encoding="utf-8",
        )
        monkeypatch.setattr(ps, "PORTFOLIO_STATE_PATH", state_path)
        monkeypatch.setattr(ps, "_POSITIONS_FALLBACK_CSV", tmp_path / "no.csv")
        monkeypatch.setattr(ps, "_POSITIONS_DERIVED_JSON", tmp_path / "no.json")
        monkeypatch.setattr(ps, "_HOLDINGS_TXT", tmp_path / "no.txt")
        monkeypatch.setattr(m, "REPORTS_DIR", tmp_path)

        result = write_report("eod")
        assert result["report_status"] in ("OK", "PREVIEW_OK", "NEEDS_REVIEW")
        warns = " ".join(result.get("warnings", [])).lower()
        assert "position" in warns or "holdings" in warns


class TestDeltaDetection:
    def test_previous_report_delta_detects_new_candidate(self):
        prev = {
            "new_entry_symbols": ["HPG"],
            "regime_bull": True, "breadth_zone": "normal",
            "counts": {"new_t1": 1, "manual_review_t1": 0},
        }
        rows = [
            _make_eod_row(symbol="HPG", final_action="NEW_T1"),
            _make_eod_row(symbol="VPB", final_action="NEW_T1"),  # new candidate
        ]
        inputs = _make_inputs(scan_rows=rows)
        inputs["prev_json"] = prev
        from datetime import datetime, timezone
        ts = datetime(2026, 5, 19, 16, 0, tzinfo=timezone.utc)
        _, _, jdata = build_report("eod", inputs, ts)
        delta = jdata.get("previous_report_delta", {})
        assert "VPB" in delta.get("new_candidates_added", [])


class TestJsonRequiredCounts:
    def test_report_json_contains_required_counts(self):
        rows = [
            _make_eod_row(symbol="A", final_action="NEW_T1"),
            _make_eod_row(symbol="B", final_action="NEW_T1_MANUAL_REVIEW_BREADTH"),
            _make_eod_row(symbol="C", final_action="NO_T2_BREADTH"),
            _make_eod_row(symbol="D", final_action="TRAIL_EXIT"),
        ]
        inputs = _make_inputs(scan_rows=rows)
        from datetime import datetime, timezone
        ts = datetime(2026, 5, 19, 16, 0, tzinfo=timezone.utc)
        _, _, jdata = build_report("eod", inputs, ts)
        required_keys = {"new_t1", "manual_review_t1", "add_t2", "no_t2_breadth",
                         "hold", "exit_review", "s3_paper", "intraday_candidates"}
        assert required_keys.issubset(jdata["counts"].keys())
        assert jdata["counts"]["new_t1"] == 1
        assert jdata["counts"]["manual_review_t1"] == 1
        assert jdata["counts"]["no_t2_breadth"] == 1
        assert jdata["counts"]["exit_review"] == 1


class TestUnexpectedFinalAction:
    def test_unexpected_final_action_triggers_warning(self):
        row = _make_eod_row(final_action="TOTALLY_UNKNOWN_ACTION_XYZ")
        inputs = _make_inputs(scan_rows=[row])
        from datetime import datetime, timezone
        ts = datetime(2026, 5, 19, 16, 0, tzinfo=timezone.utc)
        _, _, jdata = build_report("eod", inputs, ts)
        assert any("unknown" in w.lower() or "unexpected" in w.lower() for w in jdata["warnings"])


class TestNoFakeLiveFromIntraday:
    def test_no_fake_live_action_from_intraday_would_be_final_action(self):
        row = _make_intraday_row(would_be_final_action="NEW_T1")
        ca = classify_operator_action(row, "pre-atc")
        # Intraday must never produce PREPARE_NEXT_OPEN
        assert ca["operator_action"] != "PREPARE_NEXT_OPEN"
        assert ca["operator_action"] in ("REVIEW_MANUAL", "NO_ACTION", "PAPER_ONLY", "WATCH_ONLY")


# ---------------------------------------------------------------------------
# P0: Intraday must never contain live-order wording
# ---------------------------------------------------------------------------

class TestIntradayNoLiveOrderWording:
    def test_intraday_html_md_must_not_contain_live_order_phrases(self):
        row = _make_intraday_row(a3_signal_today=True, would_be_final_action="NEW_T1")
        inputs = _make_inputs(scan_rows=[row], intraday_rows=[row], mode="pre-lunch")
        from datetime import datetime, timezone
        ts = datetime(2026, 5, 19, 11, 0, tzinfo=timezone.utc)
        html, md, _ = build_report("pre-lunch", inputs, ts)
        forbidden = ["prepare next-open order", "place order", "execute order", "buy now"]
        for phrase in forbidden:
            assert phrase not in html.lower(), f"Forbidden phrase in HTML: '{phrase}'"
            assert phrase not in md.lower(), f"Forbidden phrase in MD: '{phrase}'"

    def test_intraday_signal_today_shows_review_wording(self):
        row = _make_intraday_row(a3_signal_today=True, would_be_final_action="NEW_T1")
        inputs = _make_inputs(scan_rows=[row], intraday_rows=[row], mode="pre-lunch")
        from datetime import datetime, timezone
        ts = datetime(2026, 5, 19, 11, 0, tzinfo=timezone.utc)
        html, md, _ = build_report("pre-lunch", inputs, ts)
        assert "wait for eod confirmation" in html.lower() or "wait for eod" in html.lower()


# ---------------------------------------------------------------------------
# P1: normalize_bool
# ---------------------------------------------------------------------------

class TestNormalizeBool:
    def test_python_bool(self):
        assert normalize_bool(True) is True
        assert normalize_bool(False) is False

    def test_none_returns_none(self):
        assert normalize_bool(None) is None

    def test_strings(self):
        for s in ("true", "True", "TRUE", "1", "yes", "Yes"):
            assert normalize_bool(s) is True, f"Expected True for {s!r}"
        for s in ("false", "False", "FALSE", "0", "no", "No"):
            assert normalize_bool(s) is False, f"Expected False for {s!r}"

    def test_numpy_bool(self):
        import numpy as np
        assert normalize_bool(np.bool_(True)) is True
        assert normalize_bool(np.bool_(False)) is False

    def test_int_zero_one(self):
        assert normalize_bool(1) is True
        assert normalize_bool(0) is False

    def test_nan_returns_none(self):
        assert normalize_bool(float("nan")) is None


# ---------------------------------------------------------------------------
# P1: VNINDEX regime display
# ---------------------------------------------------------------------------

class TestRegimeBullDisplay:
    def _run(self, regime_val):
        rows = [_make_eod_row(regime_bull=regime_val)]
        inputs = _make_inputs(scan_rows=rows)
        from datetime import datetime, timezone
        ts = datetime(2026, 5, 19, 16, 0, tzinfo=timezone.utc)
        html, md, jdata = build_report("eod", inputs, ts)
        return html, md, jdata

    def test_bool_true_shows_bull(self):
        html, md, jdata = self._run(True)
        assert "VNINDEX: BULL" in html
        assert "VNINDEX: BEAR" not in html
        assert jdata["regime_bull"] is True

    def test_bool_false_shows_bear(self):
        html, md, jdata = self._run(False)
        assert "BEAR" in html
        assert jdata["regime_bull"] is False

    def test_string_true_shows_bull(self):
        html, md, jdata = self._run("True")
        assert "BULL" in html
        assert jdata["regime_bull"] is True

    def test_numpy_bool_true(self):
        import numpy as np
        html, md, jdata = self._run(np.bool_(True))
        assert "BULL" in html
        assert jdata["regime_bull"] is True

    def test_none_shows_unknown(self):
        html, md, jdata = self._run(None)
        assert "UNKNOWN" in html
        assert jdata["regime_bull"] is None


# ---------------------------------------------------------------------------
# P1: Exact pending-entry wording
# ---------------------------------------------------------------------------

class TestPendingEntryExactWording:
    _REQUIRED = (
        "Signal confirmed at today's close; planned fill is next session open. "
        "Entry levels are pending until the next-open fill price is known."
    )

    def test_exact_wording_in_html(self):
        row = _make_eod_row(
            final_action="NEW_T1", a3_signal_today=True,
            a3_planned_entry_timing="NEXT_OPEN",
            pb_trigger_price=float("nan"), tp1_price=float("nan"), trail_price=float("nan"),
        )
        inputs = _make_inputs(scan_rows=[row])
        from datetime import datetime, timezone
        ts = datetime(2026, 5, 19, 16, 0, tzinfo=timezone.utc)
        html, md, _ = build_report("eod", inputs, ts)
        # Allow HTML-escaped apostrophe
        normalized = html.replace("&#39;", "'")
        assert self._REQUIRED in normalized, "Exact pending-entry wording missing from HTML"

    def test_exact_wording_in_md(self):
        row = _make_eod_row(
            final_action="NEW_T1", a3_signal_today=True,
            a3_planned_entry_timing="NEXT_OPEN",
            pb_trigger_price=float("nan"), tp1_price=float("nan"), trail_price=float("nan"),
        )
        inputs = _make_inputs(scan_rows=[row])
        from datetime import datetime, timezone
        ts = datetime(2026, 5, 19, 16, 0, tzinfo=timezone.utc)
        _, md, _ = build_report("eod", inputs, ts)
        assert self._REQUIRED in md, "Exact pending-entry wording missing from MD"


# ---------------------------------------------------------------------------
# P1: a3_signal_today=True with numeric prices → NEEDS_REVIEW
# ---------------------------------------------------------------------------

class TestSignalTodayNumericPrices:
    def test_signal_today_with_numeric_pb_triggers_needs_review(self):
        row = _make_eod_row(
            final_action="NEW_T1", a3_signal_today=True,
            pb_trigger_price=18.5,  # numeric — should be NaN
            tp1_price=float("nan"), trail_price=float("nan"),
        )
        inputs = _make_inputs(scan_rows=[row])
        from datetime import datetime, timezone
        ts = datetime(2026, 5, 19, 16, 0, tzinfo=timezone.utc)
        _, _, jdata = build_report("eod", inputs, ts)
        assert jdata["report_status"] == "NEEDS_REVIEW"
        assert any("a3_signal_today" in w and "non-null" in w for w in jdata["warnings"])


# ---------------------------------------------------------------------------
# P1: Boolean safety warnings catch string booleans
# ---------------------------------------------------------------------------

class TestStringBoolSafety:
    def test_auto_order_allowed_string_true_triggers_needs_review(self):
        row = _make_intraday_row()
        row["auto_order_allowed"] = "True"  # string, not Python bool
        inputs = _make_inputs(scan_rows=[row], intraday_rows=[row], mode="pre-lunch")
        from datetime import datetime, timezone
        ts = datetime(2026, 5, 19, 11, 0, tzinfo=timezone.utc)
        _, _, jdata = build_report("pre-lunch", inputs, ts)
        assert jdata["report_status"] == "NEEDS_REVIEW"
        assert any("auto_order_allowed" in w.lower() for w in jdata["warnings"])

    def test_s3_no_real_order_flag_string_false_triggers_needs_review(self):
        row = _make_eod_row()
        row["s3_no_real_order_flag"] = "False"  # string, not Python bool
        inputs = _make_inputs(scan_rows=[row])
        from datetime import datetime, timezone
        ts = datetime(2026, 5, 19, 16, 0, tzinfo=timezone.utc)
        _, _, jdata = build_report("eod", inputs, ts)
        assert jdata["report_status"] == "NEEDS_REVIEW"
        assert any("s3_no_real_order_flag" in w.lower() for w in jdata["warnings"])


# ---------------------------------------------------------------------------
# P1: Intraday quote-quality warnings
# ---------------------------------------------------------------------------

class TestIntradayQuoteQuality:
    def test_coverage_lt_100_warns(self):
        rows = [_make_intraday_row()]
        inputs = _make_inputs(scan_rows=rows, intraday_rows=rows, mode="pre-lunch")
        inputs["intraday_meta"]["intraday_quote_coverage_pct"] = 0.90  # 90%
        from datetime import datetime, timezone
        ts = datetime(2026, 5, 19, 11, 0, tzinfo=timezone.utc)
        _, _, jdata = build_report("pre-lunch", inputs, ts)
        warns = " ".join(jdata["warnings"]).lower()
        assert "coverage" in warns or "quote_coverage" in warns

    def test_missing_quote_count_gt0_warns(self):
        rows = [_make_intraday_row()]
        inputs = _make_inputs(scan_rows=rows, intraday_rows=rows, mode="pre-lunch")
        inputs["intraday_meta"]["missing_quote_count"] = 3
        from datetime import datetime, timezone
        ts = datetime(2026, 5, 19, 11, 0, tzinfo=timezone.utc)
        _, _, jdata = build_report("pre-lunch", inputs, ts)
        warns = " ".join(jdata["warnings"]).lower()
        assert "missing_quote" in warns or "missing" in warns

    def test_stale_data_key_warns(self):
        rows = [_make_intraday_row()]
        inputs = _make_inputs(scan_rows=rows, intraday_rows=rows, mode="pre-lunch")
        inputs["intraday_meta"]["stale_quotes_count"] = 5
        from datetime import datetime, timezone
        ts = datetime(2026, 5, 19, 11, 0, tzinfo=timezone.utc)
        _, _, jdata = build_report("pre-lunch", inputs, ts)
        warns = " ".join(jdata["warnings"]).lower()
        assert "stale" in warns


# ---------------------------------------------------------------------------
# P1: New T1 full sort (rank DESC, liq OK first, s3_fresh True first, sym ASC)
# ---------------------------------------------------------------------------

class TestT1SortFull:
    def _sorted_symbols(self, rows):
        inputs = _make_inputs(scan_rows=rows)
        from datetime import datetime, timezone
        ts = datetime(2026, 5, 19, 16, 0, tzinfo=timezone.utc)
        _, _, jdata = build_report("eod", inputs, ts)
        return jdata["new_entry_symbols"]

    def test_contract_rank_beats_action_group(self):
        """MANUAL_REVIEW row with rank=9 must sort before NEW_T1 rows with lower rank."""
        rows = [
            _make_eod_row(symbol="ZZZ", final_action="NEW_T1_MANUAL_REVIEW_BREADTH",
                          a3_rank_score=9, liq_warn_T1="OK", s3_fresh_lead_flag=True),
            _make_eod_row(symbol="BBB", final_action="NEW_T1",
                          a3_rank_score=5, liq_warn_T1="WARN", s3_fresh_lead_flag=False),
            _make_eod_row(symbol="AAA", final_action="NEW_T1",
                          a3_rank_score=1, liq_warn_T1="OK", s3_fresh_lead_flag=True),
        ]
        order = self._sorted_symbols(rows)
        assert order == ["ZZZ", "BBB", "AAA"], f"Expected [ZZZ, BBB, AAA], got {order}"

    def test_liq_ok_before_liq_warn_same_rank(self):
        rows = [
            _make_eod_row(symbol="BBB", a3_rank_score=1.0, final_action="NEW_T1", liq_warn_T1="WARN"),
            _make_eod_row(symbol="AAA", a3_rank_score=1.0, final_action="NEW_T1", liq_warn_T1="OK"),
        ]
        order = self._sorted_symbols(rows)
        assert order.index("AAA") < order.index("BBB"), "liq_warn_T1=OK should sort before WARN"

    def test_s3_fresh_true_before_false_same_rank_liq(self):
        rows = [
            _make_eod_row(symbol="ZZZ", a3_rank_score=1.0, final_action="NEW_T1",
                          liq_warn_T1="OK", s3_fresh_lead_flag=False),
            _make_eod_row(symbol="AAA", a3_rank_score=1.0, final_action="NEW_T1",
                          liq_warn_T1="OK", s3_fresh_lead_flag=True),
        ]
        order = self._sorted_symbols(rows)
        assert order.index("AAA") < order.index("ZZZ"), "s3_fresh_lead_flag=True should sort first"

    def test_symbol_asc_tiebreaker(self):
        rows = [
            _make_eod_row(symbol="ZZZ", a3_rank_score=1.0, final_action="NEW_T1",
                          liq_warn_T1="OK", s3_fresh_lead_flag=False),
            _make_eod_row(symbol="AAA", a3_rank_score=1.0, final_action="NEW_T1",
                          liq_warn_T1="OK", s3_fresh_lead_flag=False),
        ]
        order = self._sorted_symbols(rows)
        assert order.index("AAA") < order.index("ZZZ"), "Symbol ASC tiebreaker failed"


# ---------------------------------------------------------------------------
# P1: portfolio_as_of_date from portfolio_state, not scan_date
# ---------------------------------------------------------------------------

class TestPortfolioAsOfDate:
    def test_portfolio_as_of_date_from_state_not_scan(self):
        inputs = _make_inputs(scan_rows=[_make_eod_row(as_of_date="2026-05-19")])
        inputs["portfolio_as_of_date"] = "2026-05-15"  # different from scan date
        from datetime import datetime, timezone
        ts = datetime(2026, 5, 19, 16, 0, tzinfo=timezone.utc)
        _, _, jdata = build_report("eod", inputs, ts)
        assert jdata["portfolio_as_of_date"] == "2026-05-15"

    def test_portfolio_as_of_date_none_when_not_set(self):
        inputs = _make_inputs()
        from datetime import datetime, timezone
        ts = datetime(2026, 5, 19, 16, 0, tzinfo=timezone.utc)
        _, _, jdata = build_report("eod", inputs, ts)
        assert jdata["portfolio_as_of_date"] is None


# ---------------------------------------------------------------------------
# P2: MD header shows NAV and positions source
# ---------------------------------------------------------------------------

class TestMdNavHeader:
    def test_md_header_contains_nav(self):
        inputs = _make_inputs()
        inputs["nav_vnd"] = 7_500_000_000.0
        inputs["positions_source"] = "data/raw/current_positions_derived.json"
        from datetime import datetime, timezone
        ts = datetime(2026, 5, 19, 16, 0, tzinfo=timezone.utc)
        _, md, _ = build_report("eod", inputs, ts)
        assert "7.50" in md and "NAV" in md

    def test_md_header_contains_positions_source(self):
        inputs = _make_inputs()
        inputs["nav_vnd"] = 6_000_000_000.0
        inputs["positions_source"] = "data/trading/live/current_positions.csv"
        from datetime import datetime, timezone
        ts = datetime(2026, 5, 19, 16, 0, tzinfo=timezone.utc)
        _, md, _ = build_report("eod", inputs, ts)
        assert "current_positions" in md or "Positions" in md


class TestManualReviewT1MatchesScanSsot:
    """P0-2: NEW_T1_MANUAL_REVIEW_BREADTH must not be demoted by S3 shadow tag."""

    def _manual_row(self, symbol: str, rank: float, *, s3_shadow: bool = True):
        return _make_eod_row(
            symbol=symbol,
            final_action="NEW_T1_MANUAL_REVIEW_BREADTH",
            a3_rank_score=rank,
            a3_signal_today=True,
            s3_shadow_action="PAPER_S3_SHADOW" if s3_shadow else "",
            in_s3_universe=s3_shadow,
        )

    def test_manual_review_count_and_symbols_match_scan(self):
        rows = [
            self._manual_row("TRC", 0.957),
            self._manual_row("OIL", 0.829),
            self._manual_row("DXS", 0.798),
            self._manual_row("VGI", 0.685),
            self._manual_row("BID", 0.305),
        ]
        inputs = _make_inputs(scan_rows=rows)
        from datetime import datetime, timezone
        ts = datetime(2026, 5, 20, 8, 0, tzinfo=timezone.utc)
        _, md, jdata = build_report("eod", inputs, ts)
        assert jdata["counts"]["manual_review_t1"] == 5
        assert jdata["counts"]["new_t1"] == 0
        assert jdata["new_entry_symbols"] == ["TRC", "OIL", "DXS", "VGI", "BID"]
        assert "2 manual-review" not in md
        assert "5 manual-review" in md or "Prepare manual review checklist" in md
        for sym in ("TRC", "OIL", "DXS", "VGI", "BID"):
            assert sym in md

    def test_eod_must_not_say_prepare_next_open_order(self):
        rows = [self._manual_row("TRC", 0.9)]
        inputs = _make_inputs(scan_rows=rows)
        from datetime import datetime, timezone
        ts = datetime(2026, 5, 20, 8, 0, tzinfo=timezone.utc)
        html, md, _ = build_report("eod", inputs, ts)
        assert "prepare next-open order" not in html.lower()
        assert "prepare next-open order" not in md.lower()
        assert "manual review checklist" in md.lower() or "Review next-open candidate" in md
