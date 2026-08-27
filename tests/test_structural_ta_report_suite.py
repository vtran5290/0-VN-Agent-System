"""Structural TA Report Suite loaders/renderers + generator purity."""
from __future__ import annotations

import ast
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.trading.reports import report_suite_common as rsc


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sample_result(ticker: str, score: int = 75, classification: str = "Strong weekly support") -> dict:
    return {
        "ticker": ticker,
        "errors": [],
        "weekly_structure": {
            "structural_support_score": score,
            "score_classification": classification,
            "final_verdict": "Role-reversal support",
            "actual_zone": {"price_low": 60.0, "price_high": 62.0},
            "representative_level": 61.0,
            "score_breakdown": {"ma_confluence": 18},
            "weekly_close_test": {"state": "support_test_held"},
            "ma_cluster": {"selected_mas": {"ma20": 61.0, "ma50": 61.2}},
        },
        "dual_axis": {
            "support_quality_score": score,
            "trend_quality_score": 20,
            "matrix_2x2": "Strong Support + Weak Trend",
        },
        "final_verdict": {"label": "Role-reversal support", "confidence": "Medium"},
        "warnings": [],
        "money_flow": {"available": True, "summary": "CMF+/OBV rising"},
    }


def test_load_missing_returns_empty(tmp_path: Path) -> None:
    assert rsc.load_structural_ta_compact(tmp_path / "nope.json") == {}


def test_file_meta_missing_stale_ok(tmp_path: Path) -> None:
    missing = rsc.structural_ta_file_meta({})
    assert missing["status"] == "missing"

    old = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale = rsc.structural_ta_file_meta(
        {"generated_at": old, "source": "vn_ta_fireant_cli", "results": []}
    )
    assert stale["status"] == "stale"

    ok = rsc.structural_ta_file_meta(
        {"generated_at": _utc_now_iso(), "source": "vn_ta_fireant_cli", "results": []}
    )
    assert ok["status"] == "ok"


def test_index_and_card_renderers_zero_one_multi(tmp_path: Path) -> None:
    empty_idx = rsc.build_structural_ta_index({})
    assert empty_idx == {}
    assert "ADVISORY" in rsc.render_structural_ta_card("VCB", empty_idx, file_meta={"status": "ok"})
    assert "missing" in rsc.render_structural_ta_card("VCB", empty_idx, file_meta={"status": "missing"})

    compact = {
        "schema_version": "1.0",
        "generated_at": _utc_now_iso(),
        "source": "vn_ta_fireant_cli",
        "results": [
            _sample_result("VCB", 80),
            _sample_result("FPT", 55, "Moderate weekly support"),
        ],
    }
    idx = rsc.build_structural_ta_index(compact)
    meta = rsc.structural_ta_file_meta(compact)
    assert set(idx) == {"VCB", "FPT"}

    card = rsc.render_structural_ta_card("VCB", idx, file_meta=meta)
    assert "VCB" in card and "ADVISORY" in card and "sta-suite-card" in card
    assert "<canvas" not in card.lower()

    compact_row = rsc.render_structural_ta_compact_row("FPT", idx, file_meta=meta)
    assert "FPT" in compact_row and "sta-suite-compact" in compact_row

    section = rsc.render_structural_ta_cards_section(
        ["VCB", "FPT", "VCB"], idx, file_meta=meta, title="Structural TA test"
    )
    assert section.count("sta-suite-card") == 2

    summary = rsc.render_structural_ta_summary(idx, file_meta=meta)
    assert "structural-ta-summary" in summary
    assert "ticker(s) scored" in summary
    assert 'data-sta-ticker="' not in summary  # no per-ticker cards


def test_summary_handles_missing_without_raise() -> None:
    html = rsc.render_structural_ta_summary({}, file_meta={"status": "missing"})
    assert "missing" in html and "ADVISORY" in html


def test_four_generators_file_backed_only() -> None:
    """No fetch_ohlcv / CLI imports in the four wired suite generators."""
    repo = Path(__file__).resolve().parents[1]
    targets = [
        repo / "src/trading/reports/cloud_daily_report.py",
        repo / "scripts/reporting/generate_portfolio_monitor.py",
        repo / "src/scans/institutional_accumulation/operator_summary_html.py",
        repo / "scripts/reporting/generate_pm_regime_dashboard.py",
    ]
    banned_names = {"fetch_ohlcv", "vn_ta_fireant_cli"}
    for path in targets:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mods = []
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                else:
                    mods = [node.module or ""] + [a.name for a in node.names]
                joined = " ".join(mods)
                for banned in banned_names:
                    assert banned not in joined, f"{path.name} imports {banned}"
            if isinstance(node, ast.Call):
                func = node.func
                name = getattr(func, "id", None) or getattr(func, "attr", None)
                assert name != "fetch_ohlcv", f"{path.name} calls fetch_ohlcv"


def test_pm_regime_summary_has_no_per_ticker_cards() -> None:
    idx = rsc.build_structural_ta_index(
        {
            "generated_at": _utc_now_iso(),
            "source": "t",
            "results": [_sample_result("AAA"), _sample_result("BBB")],
        }
    )
    html = rsc.render_structural_ta_summary(idx, file_meta={"status": "ok", "source": "t", "generated_at": "x"})
    assert "sta-suite-card" not in html
    assert "sta-suite-compact" not in html
    assert "2 ticker(s) scored" in html
