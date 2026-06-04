from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd
import pytest

from scripts.research.institutional_accumulation_backtest.build_p1_review_pack import (
    P1PackBuildError,
    _build_p1_output_audit,
    build_p1_review_pack,
)
from src.research.institutional_accumulation_backtest.p1_diagnostics import (
    ALLOWED_SUMMARY_LABELS,
    component_diagnostics,
    diagnostic_summary,
    distribution_flag_diagnostic,
    extension_unit_audit,
    feature_lead_lag,
    measurement_integrity,
    run_p1_diagnostics,
)


def _fixture() -> pd.DataFrame:
    rows = []
    for i in range(120):
        score = float((i % 10) * 10 + 5)
        rows.append(
            {
                "scan_date": f"2024-01-{(i % 28) + 1:02d}",
                "ticker": "AAA" if i % 2 == 0 else "BBB",
                "institutional_accumulation_score": score,
                "score_money_flow": score * 0.7,
                "score_price_structure": score * 0.6,
                "score_risk_penalty": 100 - score * 0.4,
                "score_context": 50.0,
                "score_mf_cmf": score * 0.2,
                "score_mf_obv_pvt": score * 0.2,
                "score_mf_adl": score * 0.2,
                "score_mf_participation": score * 0.2,
                "ret_5d": (i % 7 - 3) / 100,
                "ret_10d": (i % 9 - 4) / 100,
                "ret_20d": (i % 11 - 5) / 100,
                "ret_60d": (i % 13 - 6) / 100,
                "ret_120d": (i % 15 - 7) / 100,
                "vnindex_ret_20d": 0.01,
                "vnindex_ret_60d": 0.02,
                "excess_ret_20d_vs_vnindex": (i % 11 - 5) / 100 - 0.01,
                "excess_ret_60d_vs_vnindex": (i % 13 - 6) / 100 - 0.02,
                "max_dd_60d": -abs((i % 10) / 100),
                "distribution_risk_flag": i % 3 == 0,
                "caution_proxy": i % 4 == 0,
                "is_vin": i % 20 == 0,
                "adv50_vnd": 25_000_000_000 if i % 2 == 0 else 10_000_000_000,
                "cmf20_daily": (i % 5) / 10,
                "cmf20_weekly": (i % 6) / 10,
                "obv_slope_20": (i % 7) / 10,
                "obv_slope_50": (i % 8) / 10,
                "adl_slope_20": (i % 9) / 10,
                "pvt_slope_20": (i % 10) / 10,
                "turnover_accel_ratio_5d50d": 0.5 + (i % 4) / 10,
                "up_down_volume_ratio_20": 1.0 + (i % 3) / 10,
                "distribution_days_25": i % 7,
                "extension_pct_above_ma20": (i % 8) / 20,
                "fragile_uptrend_narrow_leadership_proxy": i % 5 == 0,
                "correction_or_bear": i % 6 == 0,
                "normal_regime": i % 3 == 0,
            }
        )
    return pd.DataFrame(rows)


def test_p1_runs_and_expected_columns(tmp_path: Path) -> None:
    out = run_p1_diagnostics(_fixture(), tmp_path)
    assert (tmp_path / "p1_score_decile_autopsy.csv").is_file()
    expected = {"score_decile", "ret_5d_mean", "ret_120d_mean", "vin_share", "past_ret_20d_mean"}
    assert expected.issubset(set(out.score_decile_autopsy.columns))


def test_component_diagnostics_missing_fields_graceful() -> None:
    df = _fixture().drop(columns=["score_mf_obv_pvt", "score_mf_adl"])
    out = component_diagnostics(df)
    assert "diagnostic_label" in out.columns


def test_feature_lead_lag_uses_existing_feature_inputs_only() -> None:
    df = _fixture()
    out = feature_lead_lag(df)
    assert "feature" in out.columns
    assert "spearman_ret_60d" in out.columns


def test_summary_labels_from_allowed_enum(tmp_path: Path) -> None:
    out = run_p1_diagnostics(_fixture(), tmp_path)
    assert set(out.diagnostic_summary["diagnostic_label"].unique()).issubset(ALLOWED_SUMMARY_LABELS)


def test_extension_unit_detection_percent_points() -> None:
    df = _fixture()
    df["extension_pct_above_ma20"] = 10 + (pd.Series(range(len(df))) % 8).astype(float)
    audit = extension_unit_audit(df)
    assert (audit["interpreted_unit"] == "percent_points").all()
    used = dict(zip(audit["metric"], audit["threshold_used"]))
    assert used["healthy_accumulation_candidate"] == pytest.approx(12.0)
    assert used["late_stage_exhaustion_candidate"] == pytest.approx(15.0)
    assert used["base_building_candidate"] == pytest.approx(8.0)


def test_extension_unit_detection_decimal() -> None:
    df = _fixture()
    df["extension_pct_above_ma20"] = ((pd.Series(range(len(df))) % 8).astype(float)) / 100.0
    audit = extension_unit_audit(df)
    assert (audit["interpreted_unit"] == "decimal").all()
    used = dict(zip(audit["metric"], audit["threshold_used"]))
    assert used["healthy_accumulation_candidate"] == pytest.approx(0.12)
    assert used["late_stage_exhaustion_candidate"] == pytest.approx(0.15)
    assert used["base_building_candidate"] == pytest.approx(0.08)


def test_measurement_artifact_tiny_sign_flip_is_inconclusive_small_spread() -> None:
    rows = []
    for i in range(200):
        score = float(i % 20)
        is_vin = i < 20
        if is_vin:
            ret = 0.0002 if score >= 10 else -0.0002
        else:
            ret = -0.0002 if score >= 10 else 0.0002
        rows.append(
            {
                "scan_date": "2024-06-01",
                "ticker": f"T{i%10}",
                "institutional_accumulation_score": score,
                "ret_20d": ret,
                "ret_60d": ret,
                "vnindex_ret_20d": 0.0,
                "vnindex_ret_60d": 0.0,
                "adv50_vnd": 30_000_000_000,
                "is_vin": is_vin,
            }
        )
    m = measurement_integrity(pd.DataFrame(rows))
    labels = set(m["diagnostic_label"].astype(str))
    assert "INCONCLUSIVE_SMALL_SPREAD" in labels
    assert "MEASUREMENT_ARTIFACT" not in labels


def test_measurement_artifact_meaningful_sign_flip_is_artifact() -> None:
    rows = []
    for i in range(200):
        score = float(i % 20)
        is_vin = i < 20
        if is_vin:
            ret = 0.02 if score >= 10 else -0.02
        else:
            ret = -0.02 if score >= 10 else 0.02
        rows.append(
            {
                "scan_date": "2024-06-01",
                "ticker": f"T{i%10}",
                "institutional_accumulation_score": score,
                "ret_20d": ret,
                "ret_60d": ret,
                "vnindex_ret_20d": 0.0,
                "vnindex_ret_60d": 0.0,
                "adv50_vnd": 30_000_000_000,
                "is_vin": is_vin,
            }
        )
    m = measurement_integrity(pd.DataFrame(rows))
    assert "MEASUREMENT_ARTIFACT" in set(m["diagnostic_label"].astype(str))


def test_composite_label_top_decile_exhaustion_or_hump_shape() -> None:
    autopsy = pd.DataFrame(
        {
            "score_decile": list(range(10)),
            "ret_20d_mean": [0.01, 0.012, 0.013, 0.015, 0.018, 0.02, 0.03, 0.032, 0.031, 0.022],
            "ret_60d_mean": [0.018, 0.021, 0.023, 0.026, 0.03, 0.034, 0.037, 0.039, 0.038, 0.024],
            "ret_120d_mean": [0.02, 0.023, 0.026, 0.029, 0.033, 0.036, 0.04, 0.042, 0.041, 0.028],
        }
    )
    out = diagnostic_summary(
        measurement=pd.DataFrame([{"diagnostic_label": "INCONCLUSIVE"}]),
        autopsy=autopsy,
        components=pd.DataFrame(),
        lead_lag=pd.DataFrame(),
        buckets=pd.DataFrame([{"bucket": "base_building_candidate", "n": 2000, "ret_60d_mean": 0.03, "p_dd10_60d": 0.3}]),
        unit_audit=pd.DataFrame(),
        dist_diag=pd.DataFrame(
            [
                {"flag_value": False, "ret_60d_mean": 0.03, "max_dd_60d_mean": -0.08, "p_dd10_60d": 0.2},
                {"flag_value": True, "ret_60d_mean": 0.02, "max_dd_60d_mean": -0.12, "p_dd10_60d": 0.4},
            ]
        ),
        regimes=pd.DataFrame(),
        horizons=pd.DataFrame(),
        thresholds=pd.DataFrame(),
    )
    label = out.loc[out["area"] == "composite_score", "diagnostic_label"].iloc[0]
    assert label in {"TOP_DECILE_EXHAUSTION", "NON_MONOTONIC_HUMP_SHAPE"}


def test_composite_label_full_inversion() -> None:
    autopsy = pd.DataFrame(
        {
            "score_decile": list(range(10)),
            "ret_20d_mean": [0.04, 0.038, 0.03, 0.02, 0.015, 0.01, 0.005, 0.0, -0.005, -0.01],
            "ret_60d_mean": [0.05, 0.045, 0.035, 0.025, 0.015, 0.01, 0.0, -0.005, -0.01, -0.02],
            "ret_120d_mean": [0.06, 0.05, 0.04, 0.03, 0.02, 0.01, 0.005, -0.005, -0.01, -0.02],
        }
    )
    out = diagnostic_summary(
        measurement=pd.DataFrame([{"diagnostic_label": "INCONCLUSIVE"}]),
        autopsy=autopsy,
        components=pd.DataFrame(),
        lead_lag=pd.DataFrame(),
        buckets=pd.DataFrame(),
        unit_audit=pd.DataFrame(),
        dist_diag=pd.DataFrame(),
        regimes=pd.DataFrame(),
        horizons=pd.DataFrame(),
        thresholds=pd.DataFrame(),
    )
    assert out.loc[out["area"] == "composite_score", "diagnostic_label"].iloc[0] == "CONFIRMED_FULL_INVERSION"


def test_distribution_flag_label_is_data_driven() -> None:
    df = _fixture().copy()
    df["distribution_risk_flag"] = [i % 2 == 0 for i in range(len(df))]
    df.loc[df["distribution_risk_flag"] == True, "ret_60d"] = -0.03  # noqa: E712
    df.loc[df["distribution_risk_flag"] == False, "ret_60d"] = 0.03  # noqa: E712
    df.loc[df["distribution_risk_flag"] == True, "max_dd_60d"] = -0.2  # noqa: E712
    df.loc[df["distribution_risk_flag"] == False, "max_dd_60d"] = -0.08  # noqa: E712
    dist = distribution_flag_diagnostic(df)
    out = diagnostic_summary(
        measurement=pd.DataFrame([{"diagnostic_label": "INCONCLUSIVE"}]),
        autopsy=pd.DataFrame({"score_decile": [0, 1], "ret_20d_mean": [0.0, 0.0], "ret_60d_mean": [0.0, 0.0], "ret_120d_mean": [0.0, 0.0]}),
        components=pd.DataFrame(),
        lead_lag=pd.DataFrame(),
        buckets=pd.DataFrame(),
        unit_audit=pd.DataFrame(),
        dist_diag=dist,
        regimes=pd.DataFrame(),
        horizons=pd.DataFrame(),
        thresholds=pd.DataFrame(),
    )
    assert out.loc[out["area"] == "distribution_flag", "diagnostic_label"].iloc[0] == "RISK_FILTER_USEFUL"


def _seed_tmp_root(tmp_root: Path, rows: int = 120, tickers: tuple[str, ...] = ("AAA", "BBB"), html: str | None = None) -> Path:
    p1 = tmp_root / "data" / "research" / "institutional_accumulation"
    p1.mkdir(parents=True, exist_ok=True)
    df = _fixture().copy()
    if rows != len(df):
        if rows < len(df):
            df = df.iloc[:rows].copy()
        else:
            times = (rows // len(df)) + 1
            df = pd.concat([df] * times, ignore_index=True).iloc[:rows].copy()
    df["ticker"] = [tickers[i % len(tickers)] for i in range(len(df))]
    df.to_parquet(p1 / "forward_outcomes_panel.parquet", index=False)
    run_p1_diagnostics(df, p1)
    html_path = tmp_root / "reports" / "research" / "institutional_accumulation" / "p1_score_inversion_diagnostic.html"
    html_path.parent.mkdir(parents=True, exist_ok=True)
    if html is None:
        html = "<html><body><h1>P1 Institutional Accumulation Score Inversion Diagnostic</h1>" + ("x" * 1200) + "</body></html>"
    html_path.write_text(html, encoding="utf-8")
    (tmp_root / "implementation_report.md").write_text("# P1 Score Inversion Diagnostic Implementation Report\n", encoding="utf-8")
    (tmp_root / "test_log.txt").write_text("ok\n", encoding="utf-8")
    (tmp_root / "open_questions_for_chatgpt.md").write_text("ok\n", encoding="utf-8")
    return tmp_root


def test_p1_tests_do_not_write_to_real_output_paths(tmp_path: Path) -> None:
    real_data = Path.cwd() / "data" / "research" / "institutional_accumulation" / "p1_measurement_integrity.csv"
    before = real_data.stat().st_mtime if real_data.is_file() else None
    run_p1_diagnostics(_fixture(), tmp_path / "isolated_data")
    after = real_data.stat().st_mtime if real_data.is_file() else None
    assert before == after


def test_p1_pack_builder_blocks_fixture_sized_outputs(tmp_path: Path) -> None:
    root = _seed_tmp_root(tmp_path)
    with pytest.raises(P1PackBuildError, match="BLOCKED_FIXTURE_CONTAMINATION"):
        build_p1_review_pack(root=root, output_zip=root / "packs" / "fixture.zip")


def test_p1_pack_builder_blocks_dummy_html(tmp_path: Path) -> None:
    root = _seed_tmp_root(tmp_path, rows=20000, tickers=tuple(f"T{i}" for i in range(300)), html="<html></html>")
    with pytest.raises(P1PackBuildError, match="BLOCKED_FIXTURE_CONTAMINATION"):
        build_p1_review_pack(root=root, output_zip=root / "packs" / "dummy_html.zip")


def test_p1_output_audit_detects_fixture_contamination(tmp_path: Path) -> None:
    root = _seed_tmp_root(tmp_path)
    audit, status = _build_p1_output_audit(
        root=root,
        data_dir=root / "data" / "research" / "institutional_accumulation",
        html_path=root / "reports" / "research" / "institutional_accumulation" / "p1_score_inversion_diagnostic.html",
        report_path=root / "implementation_report.md",
    )
    assert status == "BLOCKED_FIXTURE_CONTAMINATION"
    assert (audit["metric"] == "fixture_contamination_check").any()


def test_p1_review_pack_contains_real_p1_report(tmp_path: Path) -> None:
    root = _seed_tmp_root(tmp_path, rows=20000, tickers=tuple(f"T{i}" for i in range(300)))
    for fp in ["implementation_report.md", "test_log.txt", "open_questions_for_chatgpt.md"]:
        assert (root / fp).is_file()
    out_zip = root / "packs" / "real.zip"
    built = build_p1_review_pack(root=root, output_zip=out_zip)
    assert str(built).startswith(str(tmp_path))
    with zipfile.ZipFile(built) as zf:
        names = zf.namelist()
        assert "data/research/institutional_accumulation/p1_score_decile_autopsy.csv" in names
        assert "reports/research/institutional_accumulation/p1_score_inversion_diagnostic.html" in names
        assert "implementation_report.md" in names
        assert "data/research/institutional_accumulation/p1_unit_audit.csv" in names
        assert "data/research/institutional_accumulation/p1_distribution_flag_diagnostic.csv" in names

