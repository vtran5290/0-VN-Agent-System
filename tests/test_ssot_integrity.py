"""SSOT integrity harness — units, limit/splice, seam continuity, ADV50 sanity.

Runnable with pytest if installed, or: python tests/test_ssot_integrity.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
SSOT = REPO / "data" / "fireant_ssot"
PANEL_PATH = SSOT / "ta_ohlcv_panel.parquet"
MANIFEST_PATH = SSOT / "manifest.json"

LIQUID = ("FPT", "VCB", "SSI", "ACB")

try:
    import pytest
except ImportError:  # pragma: no cover
    pytest = None  # type: ignore


def _load_panel() -> pd.DataFrame:
    if not PANEL_PATH.exists():
        raise FileNotFoundError(PANEL_PATH)
    df = pd.read_parquet(PANEL_PATH)
    assert {"symbol", "date", "close", "volume", "value"}.issubset(df.columns)
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    return df


def _load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(MANIFEST_PATH)
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


if pytest is not None:

    @pytest.fixture(scope="module")
    def panel() -> pd.DataFrame:
        try:
            return _load_panel()
        except FileNotFoundError:
            pytest.skip("ta_ohlcv_panel.parquet missing")

    @pytest.fixture(scope="module")
    def manifest() -> dict:
        try:
            return _load_manifest()
        except FileNotFoundError:
            pytest.skip("manifest.json missing")

    def test_provenance_columns(panel: pd.DataFrame) -> None:
        _check_provenance(panel)

    def test_units_single_cluster(panel: pd.DataFrame) -> None:
        _check_units(panel)

    def test_no_mass_splice_days(panel: pd.DataFrame) -> None:
        _check_splice(panel)

    def test_seam_continuity_acb(panel: pd.DataFrame) -> None:
        _check_seam_acb(panel)

    def test_manifest_max_date_matches_panel(panel: pd.DataFrame, manifest: dict) -> None:
        _check_manifest_dates(panel, manifest)

    def test_adv50_sanity_liquid_names(panel: pd.DataFrame) -> None:
        _check_adv50(panel)


def _check_provenance(panel: pd.DataFrame) -> None:
    for col in ("source", "adjust_basis", "unit_vnd"):
        assert col in panel.columns
        assert panel[col].notna().all()


def _check_units(panel: pd.DataFrame) -> None:
    """value / (close_raw * unit_vnd * volume) should cluster near 1, not ~1000."""
    assert "close_raw" in panel.columns
    unit = pd.to_numeric(panel["unit_vnd"], errors="coerce").fillna(1000.0)
    denom = (
        pd.to_numeric(panel["close_raw"], errors="coerce")
        * unit
        * pd.to_numeric(panel["volume"], errors="coerce")
    )
    ratio = pd.to_numeric(panel["value"], errors="coerce") / denom.replace(0, pd.NA)
    ratio = ratio.replace([float("inf"), float("-inf")], pd.NA).dropna()
    near_1 = ((ratio > 0.5) & (ratio < 2.0)).sum()
    near_1000 = ((ratio > 500) & (ratio < 2000)).sum()
    assert near_1 > 0.8 * len(ratio), f"expected most mass near 1, got {near_1}/{len(ratio)}"
    assert near_1000 < 0.01 * len(ratio), f"mixed-unit cluster at ~1000 still present: {near_1000}"


def _check_splice(panel: pd.DataFrame) -> None:
    d = panel.sort_values(["symbol", "date"]).copy()
    d["pc"] = d.groupby("symbol")["close"].pct_change()
    big = d[d["pc"].abs() > 0.20]
    by_date = big.groupby(big["date"].dt.strftime("%Y-%m-%d")).size().sort_values(ascending=False)
    seam = int(by_date.get("2024-01-30", 0))
    assert seam < 10, f"2024-01-30 still looks spliced: {seam} symbols >20%"
    if len(by_date):
        assert int(by_date.iloc[0]) < 40, f"mass >20% day detected: {by_date.head(3).to_dict()}"


def _check_seam_acb(panel: pd.DataFrame) -> None:
    acb = panel[panel["symbol"] == "ACB"].sort_values("date")
    assert not acb.empty, "ACB missing"
    window = acb[(acb["date"] >= "2024-01-25") & (acb["date"] <= "2024-02-05")].copy()
    assert len(window) >= 5
    window["pc"] = window["close"].pct_change()
    assert float(window["pc"].abs().max()) < 0.12


def _check_manifest_dates(panel: pd.DataFrame, manifest: dict) -> None:
    panel_max = str(panel["date"].max().date())
    man_max = manifest.get("ta_ohlcv_panel", {}).get("max_date")
    assert man_max == panel_max


def _check_sha_match(manifest: dict) -> None:
    from src.research._ssot_guard import assert_panel_certified, PanelNotCertified, sha256_file

    sha = assert_panel_certified(PANEL_PATH, MANIFEST_PATH)
    assert sha == manifest.get("ta_ohlcv_panel", {}).get("sha256")
    # drift must raise
    bad = dict(manifest)
    bad_panel = dict(bad.get("ta_ohlcv_panel") or {})
    bad_panel["sha256"] = "0" * 64
    bad["ta_ohlcv_panel"] = bad_panel
    tmp = MANIFEST_PATH.with_suffix(".json.tamper_test")
    tmp.write_text(json.dumps(bad), encoding="utf-8")
    try:
        raised = False
        try:
            assert_panel_certified(PANEL_PATH, tmp)
        except PanelNotCertified:
            raised = True
        assert raised, "expected PanelNotCertified on tampered manifest sha"
    finally:
        tmp.unlink(missing_ok=True)


def _check_adv50(panel: pd.DataFrame) -> None:
    recent = panel[panel["date"] >= (panel["date"].max() - pd.Timedelta(days=60))]
    for sym in LIQUID:
        s = recent[recent["symbol"] == sym]
        assert not s.empty, f"{sym} missing in recent window"
        med_bn = float((s["value"] / 1e9).median())
        assert 1.0 <= med_bn <= 5000.0, f"{sym} median turnover {med_bn} VND-bn out of band"


def main() -> int:
    panel = _load_panel()
    manifest = _load_manifest()
    _check_provenance(panel)
    _check_units(panel)
    _check_splice(panel)
    _check_seam_acb(panel)
    _check_manifest_dates(panel, manifest)
    _check_sha_match(manifest)
    _check_adv50(panel)
    print("ALL_INTEGRITY_CHECKS_PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
