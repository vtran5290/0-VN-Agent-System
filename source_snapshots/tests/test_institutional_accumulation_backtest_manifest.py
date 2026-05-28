from __future__ import annotations

import json

from src.research.institutional_accumulation_backtest.manifest import write_manifest


def test_manifest_contains_required_fields(tmp_path) -> None:
    p = tmp_path / "manifest.json"
    write_manifest(
        p,
        run_id="r1",
        git_commit="abc",
        data_start="2012-01-01",
        data_end="2024-12-31",
        rebalance_cadence="weekly",
        signal_timing="close_T_to_open_T_plus_1",
        universe_policy="u",
        data_source="s",
        context_mode="OHLCV_ONLY",
        outputs=["x.csv"],
    )
    m = json.loads(p.read_text(encoding="utf-8"))
    assert m["run_id"] == "r1"
    assert m["data_start"] == "2012-01-01"
    assert m["fund_context_mode"] == "OHLCV_ONLY"
    assert "vin_policy" in m
