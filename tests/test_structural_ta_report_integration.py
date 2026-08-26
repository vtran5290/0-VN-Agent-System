"""Tests for structural_ta weekly-report merge (missing/stale/error/purity)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.ingest import weekly_lean_sections as wls


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_structural_ta_missing_when_file_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wls, "TA_STRUCTURAL_SUPPORT_PATH", tmp_path / "missing.json")
    out = wls.build_structural_ta_block({})
    assert out["status"] == "missing"
    assert out["tickers"] == []
    assert "not generated" in (out.get("note") or "").lower()


def test_structural_ta_stale_when_generated_at_old(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "ta_structural_support.json"
    old = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "generated_at": old,
                "source": "vn_ta_fireant_cli",
                "results": [
                    {
                        "ticker": "VCB",
                        "errors": [],
                        "weekly_structure": {
                            "structural_support_score": 80,
                            "score_classification": "Strong weekly support",
                            "final_verdict": "Role-reversal support",
                            "actual_zone": {"price_low": 60.0, "price_high": 62.0},
                            "representative_level": 61.0,
                            "score_breakdown": {"ma_confluence": 18},
                            "weekly_close_test": {"state": "support_test_held"},
                            "ma_cluster": {"selected_mas": {"ma20": 61.0, "ma50": 61.2}},
                        },
                        "dual_axis": {
                            "support_quality_score": 80,
                            "trend_quality_score": 20,
                            "matrix_2x2": "Strong Support + Weak Trend",
                        },
                        "final_verdict": {"label": "Role-reversal support", "confidence": "Medium"},
                        "warnings": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(wls, "TA_STRUCTURAL_SUPPORT_PATH", path)
    out = wls.build_structural_ta_block({})
    assert out["status"] == "stale"
    assert out["age_days"] is not None and out["age_days"] > wls.STRUCTURAL_TA_STALE_DAYS
    assert len(out["tickers"]) == 1
    assert out["tickers"][0]["ticker"] == "VCB"
    assert out["tickers"][0]["error"] is None


def test_structural_ta_one_ticker_error_does_not_blank_others(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "ta_structural_support.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "generated_at": _utc_now_iso(),
                "source": "vn_ta_fireant_cli",
                "results": [
                    {
                        "ticker": "BAD",
                        "errors": ["fetch_ohlcv daily failed: boom"],
                        "weekly_structure": {},
                        "dual_axis": {},
                        "final_verdict": {},
                        "warnings": [],
                    },
                    {
                        "ticker": "OKT",
                        "errors": [],
                        "weekly_structure": {
                            "structural_support_score": 70,
                            "score_classification": "Strong weekly support",
                            "final_verdict": "Support under test",
                            "actual_zone": {"price_low": 10.0, "price_high": 11.0},
                            "representative_level": 10.5,
                            "score_breakdown": {"ma_confluence": 16},
                            "weekly_close_test": {"state": "support_test_held"},
                            "ma_cluster": {"selected_mas": {"ma20": 10.4, "ma50": 10.6}},
                        },
                        "dual_axis": {
                            "support_quality_score": 70,
                            "trend_quality_score": 40,
                            "matrix_2x2": "Strong Support + Weak Trend",
                        },
                        "final_verdict": {"label": "Support under test", "confidence": "Medium"},
                        "warnings": [],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(wls, "TA_STRUCTURAL_SUPPORT_PATH", path)
    out = wls.build_structural_ta_block({})
    assert out["status"] == "ok"
    by_t = {t["ticker"]: t for t in out["tickers"]}
    assert by_t["BAD"]["error"]
    assert by_t["BAD"]["status_label"] == "error"
    assert by_t["OKT"]["error"] is None
    assert by_t["OKT"]["score"] == 70
    assert by_t["OKT"]["chart"]["labels"]


def test_render_weekly_report_has_no_network_ta_imports() -> None:
    root = Path(__file__).resolve().parents[1]
    render_src = (root / "scripts" / "reporting" / "render_weekly_report.py").read_text(encoding="utf-8")
    template_src = (root / "templates" / "weekly_report_lean.html.j2").read_text(encoding="utf-8")
    for banned in (
        "fetch_ohlcv",
        "import scripts.vn_ta_fireant_cli",
        "from scripts.vn_ta_fireant_cli",
        "fireant_fetcher",
        "ta_structural_support.json",
    ):
        assert banned not in render_src
    for banned in ("fetch_ohlcv", "fireant_fetcher", "import scripts.vn_ta_fireant_cli"):
        assert banned not in template_src
    assert 'id="structural-ta"' in template_src
    assert "beforeprint" in template_src
    assert "afterprint" in template_src
    assert "ADVISORY — not a signal input" in template_src


def test_cli_main_output_wrapper_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts import vn_ta_fireant_cli as cli

    def fake_analyze(ticker: str, asof, cfg):
        return {"ticker": ticker, "asof": asof.isoformat(), "errors": [], "warnings": []}

    monkeypatch.setattr(cli, "analyze_ticker", fake_analyze)
    out = tmp_path / "ta_structural_support.json"
    rc = cli.main(["vn_ta_fireant_cli", "AAA", "--output", str(out)])
    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0"
    assert payload["source"] == "vn_ta_fireant_cli"
    assert payload["generated_at"]
    assert payload["results"][0]["ticker"] == "AAA"


def test_cli_stdout_array_without_output(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from scripts import vn_ta_fireant_cli as cli

    monkeypatch.setattr(
        cli,
        "analyze_ticker",
        lambda ticker, asof, cfg: {"ticker": ticker, "errors": []},
    )
    rc = cli.main(["vn_ta_fireant_cli", "BBB"])
    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    assert isinstance(printed, list)
    assert printed[0]["ticker"] == "BBB"


def test_render_html_includes_structural_ta_section(tmp_path: Path) -> None:
    from scripts.reporting.render_weekly_report import render_html
    from scripts.utils.io import read_json

    root = Path(__file__).resolve().parents[1]
    payload = read_json(root / "data" / "processed" / "weekly_report.json")
    payload["structural_ta"] = {
        "status": "ok",
        "generated_at": "2026-08-26T00:00:00Z",
        "source": "vn_ta_fireant_cli",
        "schema_version": "1.0",
        "tickers": [
            {
                "ticker": "DGW",
                "error": None,
                "score": 80,
                "classification": "Strong weekly support",
                "verdict": "Role-reversal support",
                "status_glyph": "✓",
                "status_label": "held",
                "status_tone": "info",
                "matrix_2x2": "Strong Support + Weak Trend",
                "zone": {"price_low": 40.3, "price_high": 42.6},
                "representative_level": 41.4,
                "score_breakdown": {"ma_confluence": 18, "horizontal_pivot": 16},
                "weekly_close_test": {
                    "state": "support_test_held",
                    "confirmation_close": 42.6,
                    "invalidation_close": 40.3,
                },
                "chart": {"labels": ["Zone low", "Rep", "Zone high"], "values": [40.3, 41.4, 42.6]},
            }
        ],
    }
    out = tmp_path / "index.html"
    render_html(payload, out)
    html = out.read_text(encoding="utf-8")
    assert 'id="structural-ta"' in html
    assert "ADVISORY — not a signal input" in html
    assert "DGW" in html
    assert "sta-chart-DGW" in html
