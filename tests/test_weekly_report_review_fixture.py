"""Review-only phase36 fixture tests (not production scan SSOT)."""
from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _minimal_payload() -> dict:
    return {
        "metadata": {"asof_date": "2026-05-17", "data_confidence": "Medium"},
        "regime_engine": {"current_regime": "STATE B", "suggested_regime": "STATE B"},
        "probability_allocation": {
            "allocation": {"gross_exposure": 0.55, "cash_weight": 0.45},
            "probabilities": {"fed_cut_3m": 0.35},
        },
        "decision_layer": {"top_actions": [], "top_risks": []},
        "execution_monitoring": {"risk_flags": {}, "sell_trim_signals": []},
        "portfolio_command_center": {},
        "market_structure": {
            "levels": {"vnindex_level": 1300, "vn30_level": 1400, "distribution_days_rolling_20": 3},
        },
    }


def _fixture_positions_block() -> dict:
    return {
        "rows": [
            {"ticker": "NVL", "sector": "BDS", "action": "HOLD", "weight_pct": 7.8, "current_price": 17300.0},
            {"ticker": "HDB", "sector": "Banks", "action": "HOLD", "weight_pct": 6.7, "current_price": 27329.0},
            {"ticker": "GVR", "sector": "Rubber", "action": "HOLD", "weight_pct": 10.8, "current_price": 37000.0},
            {"ticker": "STB", "sector": "Banks", "action": "HOLD", "weight_pct": 5.0, "current_price": 68950.0},
        ],
    }


def test_nvl_trail_exit_in_execution(review_scan_path: Path) -> None:
    from scripts.ingest.weekly_lean_sections import build_execution_scan_aligned

    ex = build_execution_scan_aligned(_minimal_payload(), _fixture_positions_block())
    nvl = next(r for r in ex["rows"] if r["ticker"] == "NVL")
    assert nvl["scan_final_action"] == "TRAIL_EXIT"
    assert "EXIT" in (nvl.get("required_operator_action") or "").upper()
    assert nvl.get("row_class") != "row-noscan"


def test_nvl_in_immediate_actions(review_scan_path: Path) -> None:
    from scripts.ingest.weekly_lean_sections import _build_immediate_actions, build_execution_scan_aligned

    ex = build_execution_scan_aligned(_minimal_payload(), _fixture_positions_block())
    actions = _build_immediate_actions(ex["rows"])
    assert any("NVL" in a and "TRAIL_EXIT" in a for a in actions)


def test_command_center_reflects_scan_forced_exit(review_scan_path: Path) -> None:
    from scripts.ingest.weekly_lean_sections import (
        _patch_command_center,
        build_compact_data_quality,
        build_execution_scan_aligned,
    )

    payload = _minimal_payload()
    ex = build_execution_scan_aligned(payload, _fixture_positions_block())
    dq = build_compact_data_quality(payload, review_scan_path, ex, [])
    _patch_command_center(payload, ex, dq)
    cc = payload["portfolio_command_center"]
    assert cc.get("has_forced_exit") is True
    assert "NVL" in (cc.get("highest_priority_action") or "")


def test_hdb_no_t2_breadth_operator_action(review_scan_path: Path) -> None:
    from scripts.ingest.weekly_lean_sections import build_execution_scan_aligned

    ex = build_execution_scan_aligned(_minimal_payload(), _fixture_positions_block())
    hdb = next(r for r in ex["rows"] if r["ticker"] == "HDB")
    assert hdb["scan_final_action"] == "NO_T2_BREADTH"
    assert "BLOCK" in (hdb.get("operator_action") or "").upper()


def test_scan_missing_holdings_row_noscan(review_scan_path: Path) -> None:
    from scripts.ingest.weekly_lean_sections import build_execution_scan_aligned

    ex = build_execution_scan_aligned(_minimal_payload(), _fixture_positions_block())
    stb = next(r for r in ex["rows"] if r["ticker"] == "STB")
    assert stb.get("scan_missing") is True
    assert stb.get("row_class") == "row-noscan"


def test_s3_research_hidden_from_default_watchlist(review_scan_path: Path) -> None:
    from scripts.ingest.weekly_lean_sections import build_watchlist_a3

    wl = build_watchlist_a3(_minimal_payload())
    tickers = {c.get("ticker") for c in wl.get("candidates") or []}
    assert "S3X" not in tickers
    assert wl.get("filter") == "A3_PRODUCTION"


def test_a3_rank_score_does_not_change_required_action(review_scan_path: Path) -> None:
    from scripts.ingest.weekly_lean_sections import build_execution_scan_aligned, build_watchlist_a3

    ex = build_execution_scan_aligned(_minimal_payload(), _fixture_positions_block())
    nvl = next(r for r in ex["rows"] if r["ticker"] == "NVL")
    assert "EXIT" in (nvl.get("required_operator_action") or "").upper()
    wl = build_watchlist_a3(_minimal_payload())
    candidates = wl.get("candidates") or []
    buy_now = [c for c in candidates if c.get("bucket") == "Buy Now Candidate"]
    assert any(c.get("ticker") == "ZX99" for c in buy_now)
    assert not any(c.get("ticker") == "NVL" for c in buy_now)
    nvl_rows = [c for c in candidates if c.get("ticker") == "NVL"]
    assert nvl_rows and nvl_rows[0].get("bucket") == "Avoid / Remove"


def test_all_scan_missing_execution_not_ready_wording() -> None:
    from scripts.ingest.weekly_lean_sections import execution_not_ready_message

    msg = execution_not_ready_message(14, 14)
    assert msg is not None
    assert "not decision-ready" in msg
    assert "14/14" in msg
