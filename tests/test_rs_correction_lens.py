"""RS correction lens — anchor detection and report integration."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.market.rs_correction_lens.anchor import detect_correction_anchor
from src.market.rs_correction_lens.pipeline import run_rs_correction_lens
from src.trading.reports.rs_correction_card import (
    build_rs_correction_section_for_daily_scan,
    load_rs_correction_latest,
    render_rs_correction_md,
)

REPO = Path(__file__).resolve().parents[1]


def test_detect_anchor_on_sample_vni():
    dates = pd.date_range("2026-05-01", periods=15, freq="B")
    closes = [1900, 1905, 1910, 1915, 1920, 1921.6, 1910, 1905, 1900, 1896, 1890, 1888, 1886, 1886, 1886]
    vni = pd.DataFrame({"date": dates, "close": closes})
    anc = detect_correction_anchor(vni, as_of="2026-05-25", lookback=15, min_drawdown_pct=1.0)
    assert float(anc.anchor_close) == 1921.6
    assert anc.drawdown_pct < -1.0


def test_run_lens_writes_ssot(tmp_path, monkeypatch):
    out = tmp_path / "market_risk"
    out.mkdir(parents=True)
    monkeypatch.setattr(
        "src.market.rs_correction_lens.pipeline.OUT_DIR",
        out,
    )
    monkeypatch.setattr(
        "src.market.rs_correction_lens.pipeline.LATEST_JSON",
        out / "rs_correction_latest.json",
    )
    monkeypatch.setattr(
        "src.market.rs_correction_lens.pipeline.LATEST_CSV",
        out / "rs_correction_latest.csv",
    )

    def _fake_compute(**_kwargs):
        df = pd.DataFrame(
            [
                {
                    "symbol": "AAA",
                    "anchor_date": "2026-05-15",
                    "end_date": "2026-05-25",
                    "ret_pct": 5.0,
                    "vnindex_ret_pct": -1.85,
                    "rs_pct": 6.85,
                    "rs_line_chg_pct": 6.9,
                    "rs20_end_pct": 1.0,
                    "rs20_anchor_pct": -2.0,
                    "rs_improving_flag": True,
                    "mdd_since_anchor_pct": -1.0,
                    "bucket": "leader_strong",
                    "is_vin": False,
                }
            ]
        )
        meta = {
            "source": "FireAnt",
            "method": "test",
            "benchmark": "VNINDEX",
            "universe": "test",
            "anchor": {
                "anchor_date": "2026-05-15",
                "anchor_close": 1921.6,
                "end_date": "2026-05-25",
                "end_close": 1886.0,
                "vnindex_ret_pct": -1.85,
                "drawdown_from_peak_pct": -1.85,
                "lookback_bars": 60,
                "detection_method": "test",
            },
            "n_symbols": 1,
            "n_outperform_rs_gt_0": 1,
            "n_leader_rs_ge_3": 1,
            "safety_note": "RS correction lens is market context only and does not change final_action.",
        }
        return df, meta, []

    monkeypatch.setattr(
        "src.market.rs_correction_lens.pipeline.compute_rs_correction_table",
        _fake_compute,
    )
    result = run_rs_correction_lens()
    assert (out / "rs_correction_latest.json").is_file()
    assert result["n_leader_rs_ge_3"] == 1


def test_daily_scan_section_from_json(tmp_path, monkeypatch):
    sample = {
        "method_version": "rs_correction_lens_v1.0",
        "anchor": {
            "anchor_date": "2026-05-15",
            "anchor_close": 1921.6,
            "end_date": "2026-05-25",
            "end_close": 1886.03,
            "vnindex_ret_pct": -1.85,
            "drawdown_from_peak_pct": -1.85,
            "detection_method": "peak_in_lookback",
        },
        "n_symbols": 272,
        "n_outperform_rs_gt_0": 151,
        "n_leader_rs_ge_3": 47,
        "leaders_top25": [{
            "symbol": "CTR",
            "close_anchor": 85.0,
            "close_end": 92.1,
            "ret_pct": 8.36,
            "rs_pct": 10.21,
            "rs20_anchor_pct": -2.0,
            "rs20_end_pct": 6.5,
            "rs20_delta_pp": 8.5,
            "rs_improving_flag": True,
            "is_vin": False,
        }],
        "improving_top25": [],
        "defensive_flat_top25": [],
        "laggards_bottom15": [],
    }
    p = tmp_path / "rs_correction_latest.json"
    p.write_text(json.dumps(sample), encoding="utf-8")
    monkeypatch.setattr("src.trading.reports.rs_correction_card.LATEST_JSON", p)
    monkeypatch.setattr(
        "src.trading.reports.rs_correction_card.refresh_rs_correction_for_reports",
        lambda **_: [],
    )
    md, warns = build_rs_correction_section_for_daily_scan(refresh=False)
    assert "RS vs VNINDEX" in md
    assert "CTR" in md
    assert "does not change final_action" in md
    md = render_rs_correction_md(sample)
    assert "RS20 before" in md
    assert "Close (anchor→end)" in md
    data, _ = load_rs_correction_latest(p)
    assert data is not None
