from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd
import pytest

from scripts.research.institutional_accumulation_backtest.build_p2_review_pack import (
    P2PackBuildError,
    build_p2_review_pack,
)
from src.research.institutional_accumulation_backtest.p1_diagnostics import extension_unit_audit
from src.research.institutional_accumulation_backtest.p2_reporting import write_p2_html_report
from src.research.institutional_accumulation_backtest.p2_variants import (
    ALLOWED_VARIANT_LABELS,
    build_variant_masks,
    enrich_outcomes,
    label_variant,
    run_p2_variants,
)


def _fixture(rows: int = 120) -> pd.DataFrame:
    out = []
    for i in range(rows):
        score = float((i % 10) * 10 + 5)
        out.append(
            {
                "scan_date": f"2024-01-{(i % 28) + 1:02d}",
                "ticker": "AAA" if i % 2 == 0 else "BBB",
                "institutional_accumulation_score": score,
                "score_money_flow": score * 0.7,
                "score_price_structure": score * 0.6,
                "score_risk_penalty": 100 - score * 0.4,
                "ret_5d": (i % 7 - 3) / 100,
                "ret_10d": (i % 9 - 4) / 100,
                "ret_20d": (i % 11 - 5) / 100,
                "ret_60d": (i % 13 - 6) / 100,
                "ret_120d": (i % 15 - 7) / 100,
                "excess_ret_20d_vs_vnindex": (i % 11 - 5) / 100 - 0.01,
                "excess_ret_60d_vs_vnindex": (i % 13 - 6) / 100 - 0.02,
                "max_dd_60d": -abs((i % 10) / 100),
                "distribution_risk_flag": i % 3 == 0,
                "distribution_days_25": i % 7,
                "is_vin": i % 20 == 0,
                "adv50_vnd": 25_000_000_000 if i % 2 == 0 else 10_000_000_000,
                "turnover_accel_ratio_5d50d": 0.5 + (i % 4) / 10,
                "extension_pct_above_ma20": (i % 8) / 20,
                "normal_regime": i % 3 == 0,
                "correction_or_bear": i % 6 == 0,
                "fragile_uptrend_narrow_leadership_proxy": i % 5 == 0,
            }
        )
    return pd.DataFrame(out)


def test_p2_runs_on_fixture(tmp_path: Path) -> None:
    out = run_p2_variants(_fixture(), tmp_path)
    assert (tmp_path / "p2_variant_results.csv").is_file()
    assert (tmp_path / "p2_top_decile_exhaustion.csv").is_file()
    assert (tmp_path / "p2_extension_cap_sweep.csv").is_file()
    assert (tmp_path / "p2_distribution_gate_sweep.csv").is_file()
    assert (tmp_path / "p2_diagnostic_summary.csv").is_file()
    assert not out.variant_results.empty


def test_extension_cap_percent_points_vs_decimal() -> None:
    df = _fixture()
    df["extension_pct_above_ma20"] = 10 + (pd.Series(range(len(df))) % 8).astype(float)
    audit = extension_unit_audit(df)
    assert (audit["interpreted_unit"] == "percent_points").all()
    assert audit.loc[audit["metric"] == "healthy_accumulation_candidate", "threshold_used"].iloc[0] == pytest.approx(12.0)


def test_extension_cap_decimal_units() -> None:
    df = _fixture()
    df["extension_pct_above_ma20"] = ((pd.Series(range(len(df))) % 8).astype(float)) / 100.0
    audit = extension_unit_audit(df)
    assert (audit["interpreted_unit"] == "decimal").all()
    assert audit.loc[audit["metric"] == "healthy_accumulation_candidate", "threshold_used"].iloc[0] == pytest.approx(0.12)


def test_variant_labels_allowed_enum(tmp_path: Path) -> None:
    out = run_p2_variants(_fixture(200), tmp_path)
    assert set(out.diagnostic_summary["label"].unique()).issubset(ALLOWED_VARIANT_LABELS)


def test_v2_excludes_decile_9() -> None:
    df = enrich_outcomes(_fixture(200))
    masks = build_variant_masks(df)
    v2 = masks["V2_SCORE_DECILE_6_8"][1]
    sub = df[v2.fillna(False)]
    assert (pd.to_numeric(sub["score_decile"], errors="coerce") == 9).sum() == 0


def test_v4_excludes_distribution_flag_true() -> None:
    df = enrich_outcomes(_fixture(200))
    masks = build_variant_masks(df)
    v4 = masks["V4_NO_DISTRIBUTION_RISK"][1]
    sub = df[v4.fillna(False)]
    assert (sub["distribution_risk_flag"] == True).sum() == 0  # noqa: E712


def test_html_has_research_only_note(tmp_path: Path) -> None:
    out = run_p2_variants(_fixture(200), tmp_path)
    html = tmp_path / "p2.html"
    write_p2_html_report(
        html,
        variant_results=out.variant_results,
        top_decile_exhaustion=out.top_decile_exhaustion,
        extension_cap_sweep=out.extension_cap_sweep,
        distribution_gate_sweep=out.distribution_gate_sweep,
        diagnostic_summary=out.diagnostic_summary,
    )
    txt = html.read_text(encoding="utf-8")
    assert "P2 Research Variants" in txt
    assert "Research-only" in txt
    assert "RESEARCH_ONLY_NOT_PRODUCTION" in txt


def test_p2_tests_do_not_write_real_output_paths(tmp_path: Path) -> None:
    real = Path.cwd() / "data" / "research" / "institutional_accumulation" / "p2_variant_results.csv"
    before = real.stat().st_mtime if real.is_file() else None
    run_p2_variants(_fixture(), tmp_path / "iso")
    after = real.stat().st_mtime if real.is_file() else None
    assert before == after


def test_p2_pack_builder_blocks_fixture_sized_outputs(tmp_path: Path) -> None:
    root = tmp_path / "root"
    p2 = root / "data" / "research" / "institutional_accumulation"
    p2.mkdir(parents=True, exist_ok=True)
    _fixture(120).to_parquet(p2 / "forward_outcomes_panel.parquet", index=False)
    run_p2_variants(_fixture(120), p2)
    (root / "implementation_report.md").write_text("# P2 Research Variants Implementation Report\n", encoding="utf-8")
    (root / "test_log.txt").write_text("ok\n", encoding="utf-8")
    (root / "open_questions_for_chatgpt.md").write_text("ok\n", encoding="utf-8")
    html = root / "reports" / "research" / "institutional_accumulation" / "p2_research_variants.html"
    html.parent.mkdir(parents=True, exist_ok=True)
    html.write_text("<html><h1>P2 Research Variants</h1>" + ("x" * 1200) + " RESEARCH_ONLY_NOT_PRODUCTION Research-only.</html>", encoding="utf-8")
    with pytest.raises(P2PackBuildError):
        build_p2_review_pack(root=root, output_zip=root / "packs" / "bad.zip")


def _seed_large_root(tmp_root: Path) -> Path:
    p2 = tmp_root / "data" / "research" / "institutional_accumulation"
    p2.mkdir(parents=True, exist_ok=True)
    df = _fixture()
    times = (20000 // len(df)) + 1
    big = pd.concat([df] * times, ignore_index=True).iloc[:20000].copy()
    big["ticker"] = [f"T{i % 400}" for i in range(len(big))]
    big.to_parquet(p2 / "forward_outcomes_panel.parquet", index=False)
    run_p2_variants(big, p2)
    (tmp_root / "implementation_report.md").write_text("# P2 Research Variants Implementation Report\n", encoding="utf-8")
    (tmp_root / "test_log.txt").write_text("ok\n", encoding="utf-8")
    (tmp_root / "open_questions_for_chatgpt.md").write_text("ok\n", encoding="utf-8")
    html = tmp_root / "reports" / "research" / "institutional_accumulation" / "p2_research_variants.html"
    html.parent.mkdir(parents=True, exist_ok=True)
    out = run_p2_variants(big, p2)
    write_p2_html_report(
        html,
        variant_results=out.variant_results,
        top_decile_exhaustion=out.top_decile_exhaustion,
        extension_cap_sweep=out.extension_cap_sweep,
        distribution_gate_sweep=out.distribution_gate_sweep,
        diagnostic_summary=out.diagnostic_summary,
    )
    return tmp_root


def test_p2_review_pack_builds_on_large_fixture(tmp_path: Path) -> None:
    root = _seed_large_root(tmp_path)
    built = build_p2_review_pack(root=root, output_zip=root / "packs" / "ok.zip")
    assert str(built).startswith(str(tmp_path))
    with zipfile.ZipFile(built) as zf:
        names = zf.namelist()
        assert "data/research/institutional_accumulation/p2_variant_results.csv" in names
        assert "reports/research/institutional_accumulation/p2_research_variants.html" in names
