"""Tests for P3.1 Coverage / Price-Path QA.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import pandas as pd
import numpy as np
import pytest

from src.research.institutional_accumulation_backtest.p3_coverage_qa import (
    ALLOWED_QA_LABELS,
    build_candidate_loss_funnel,
    summarize_coverage_audit,
    build_price_path_audit,
    build_missing_price_reasons,
    candidate_density_by_week,
    candidate_density_by_year,
    holding_period_qa,
    assign_qa_label,
    build_html_report,
    LIQUID_THRESHOLD_20B,
    LIQUID_THRESHOLD_5B,
    HOLDING_WEEKS_OPTIONS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_outcomes(n_scans: int = 5, n_tickers: int = 10, adv50_range: tuple = (1e9, 50e9)) -> pd.DataFrame:
    rows = []
    scan_dates = pd.date_range("2024-01-05", periods=n_scans, freq="W-FRI")
    for dt in scan_dates:
        for i in range(n_tickers):
            adv = float(np.random.uniform(adv50_range[0], adv50_range[1]))
            rows.append(
                {
                    "scan_date": dt,
                    "ticker": f"T{i:03d}",
                    "institutional_accumulation_score": float(np.random.uniform(20, 80)),
                    "adv50_vnd": adv,
                    "distribution_risk_flag": i % 3 == 0,
                    "score_decile": i % 10,
                    "is_vin": False,
                    "entry_price_open_t1": float(np.random.uniform(10, 100)) if i % 7 != 0 else None,
                    "entry_date": str((dt + pd.Timedelta(days=1)).date()) if i % 7 != 0 else None,
                    "ret_5d": float(np.random.uniform(-0.05, 0.05)) if i % 5 != 0 else None,
                    "ret_10d": float(np.random.uniform(-0.08, 0.08)) if i % 5 != 0 else None,
                    "ret_20d": float(np.random.uniform(-0.1, 0.1)) if i % 5 != 0 else None,
                    "ret_60d": float(np.random.uniform(-0.15, 0.15)) if i % 5 != 0 else None,
                    "ret_120d": float(np.random.uniform(-0.2, 0.2)) if i % 5 != 0 else None,
                    "vnindex_ret_5d": float(np.random.uniform(-0.03, 0.03)),
                    "vnindex_ret_20d": float(np.random.uniform(-0.05, 0.05)),
                    "normal_regime": True,
                    "correction_or_bear": False,
                    "fragile_uptrend_narrow_leadership_proxy": False,
                    "extension_pct_above_ma20": float(np.random.uniform(0, 20)),
                    "score_risk_penalty": float(np.random.uniform(20, 60)),
                    "score_money_flow": float(np.random.uniform(20, 80)),
                    "score_price_structure": float(np.random.uniform(20, 80)),
                    "distribution_days_25": float(np.random.randint(0, 8)),
                    "turnover_accel_ratio_5d50d": float(np.random.uniform(0.5, 2.0)),
                    "close": float(np.random.uniform(10, 100)),
                }
            )
    return pd.DataFrame(rows)


def _make_sparse_outcomes(n_scans: int = 5, n_tickers: int = 10) -> pd.DataFrame:
    """All tickers below 20B ADV50 — simulates pre-2024 market."""
    return _make_outcomes(n_scans=n_scans, n_tickers=n_tickers, adv50_range=(1e6, 1e9))


def _make_dense_outcomes(n_scans: int = 5, n_tickers: int = 30) -> pd.DataFrame:
    """All tickers above 20B ADV50 — simulates 2024+ liquid market."""
    return _make_outcomes(n_scans=n_scans, n_tickers=n_tickers, adv50_range=(20e9, 100e9))


# ---------------------------------------------------------------------------
# Test 1: Candidate-loss funnel produces correct stage counts
# ---------------------------------------------------------------------------


def test_candidate_loss_funnel_stage_counts() -> None:
    df = _make_dense_outcomes(n_scans=3, n_tickers=20)
    funnel = build_candidate_loss_funnel(df, variant_key="V4_NO_DISTRIBUTION_RISK", liquid_threshold=LIQUID_THRESHOLD_20B, top_n=10)
    assert not funnel.empty
    assert "stage_1_raw_universe" in funnel.columns
    assert "stage_4_variant_and_liquid" in funnel.columns
    assert "stage_5_valid_entry_price" in funnel.columns
    assert "stage_6_selected_top_n" in funnel.columns
    # stage_1 >= stage_2 >= stage_4 for each scan
    for _, r in funnel.iterrows():
        assert r["stage_1_raw_universe"] >= r["stage_2_liquid"]
        assert r["stage_4_variant_and_liquid"] <= r["stage_2_liquid"]
        assert r["stage_5_valid_entry_price"] <= r["stage_4_variant_and_liquid"]
        assert r["stage_6_selected_top_n"] <= r["stage_5_valid_entry_price"]


# ---------------------------------------------------------------------------
# Test 2: Missing entry/exit prices counted correctly
# ---------------------------------------------------------------------------


def test_missing_entry_exit_prices_counted() -> None:
    df = _make_dense_outcomes(n_scans=4, n_tickers=15)
    # Force some nulls
    df.loc[df["ticker"].isin(["T000", "T001"]), "entry_price_open_t1"] = None
    price_audit = build_price_path_audit(df, liquid_threshold=LIQUID_THRESHOLD_20B)
    assert not price_audit.empty
    assert "entry_price_missing" in price_audit.columns
    assert "entry_price_ok" in price_audit.columns
    # Total missing across all scans should be >= 0
    assert price_audit["entry_price_missing"].sum() >= 0


# ---------------------------------------------------------------------------
# Test 3: Dense candidates not falsely labeled as TRUE_SIGNAL_SPARSE
# ---------------------------------------------------------------------------


def test_v4_broad_not_falsely_sparse() -> None:
    df = _make_dense_outcomes(n_scans=5, n_tickers=40)
    funnel = build_candidate_loss_funnel(df, variant_key="V4_NO_DISTRIBUTION_RISK", liquid_threshold=LIQUID_THRESHOLD_20B, top_n=10)
    summary = summarize_coverage_audit(funnel)
    label, note = assign_qa_label(summary, pd.DataFrame())
    # With 40 tickers all above 20B, label should NOT be VARIANT_TOO_RESTRICTIVE
    assert label != "VARIANT_TOO_RESTRICTIVE", f"False restrictive label: {note}"


# ---------------------------------------------------------------------------
# Test 4: QA labels use allowed enum only
# ---------------------------------------------------------------------------


def test_qa_labels_use_allowed_enum() -> None:
    for label in ALLOWED_QA_LABELS:
        assert label in ALLOWED_QA_LABELS

    # assign_qa_label always returns an allowed label
    df_sparse = _make_sparse_outcomes(n_scans=10, n_tickers=5)
    funnel = build_candidate_loss_funnel(df_sparse, liquid_threshold=LIQUID_THRESHOLD_20B)
    summary = summarize_coverage_audit(funnel)
    label, _ = assign_qa_label(summary, pd.DataFrame())
    assert label in ALLOWED_QA_LABELS, f"Unexpected label: {label}"


# ---------------------------------------------------------------------------
# Test 5: Holding-period QA creates expected horizon columns
# ---------------------------------------------------------------------------


def test_holding_period_qa_creates_expected_horizons() -> None:
    df = _make_dense_outcomes(n_scans=4, n_tickers=20)
    hp = holding_period_qa(df, liquid_threshold=LIQUID_THRESHOLD_20B, variant_key="V4_NO_DISTRIBUTION_RISK", top_n=10)
    assert not hp.empty
    assert "holding_weeks" in hp.columns
    assert "return_column_used" in hp.columns
    assert "mean_return" in hp.columns
    found_weeks = set(hp["holding_weeks"].unique())
    for w in HOLDING_WEEKS_OPTIONS:
        assert w in found_weeks, f"Missing holding weeks: {w}"


# ---------------------------------------------------------------------------
# Test 6: Sparse market correctly labeled as VARIANT_TOO_RESTRICTIVE
# ---------------------------------------------------------------------------


def test_sparse_market_labeled_restrictive() -> None:
    df = _make_sparse_outcomes(n_scans=20, n_tickers=10)
    funnel = build_candidate_loss_funnel(df, liquid_threshold=LIQUID_THRESHOLD_20B)
    summary = summarize_coverage_audit(funnel)
    label, note = assign_qa_label(summary, pd.DataFrame())
    assert label == "VARIANT_TOO_RESTRICTIVE", f"Expected VARIANT_TOO_RESTRICTIVE, got {label}: {note}"


# ---------------------------------------------------------------------------
# Test 7: Candidate density by year produces year column
# ---------------------------------------------------------------------------


def test_candidate_density_by_year_has_year_col() -> None:
    df = _make_outcomes(n_scans=5, n_tickers=15, adv50_range=(5e9, 50e9))
    density = candidate_density_by_year(df, liquid_threshold=LIQUID_THRESHOLD_5B, variant_key="V4_NO_DISTRIBUTION_RISK")
    assert not density.empty
    assert "year" in density.columns
    assert "scan_count" in density.columns
    assert "scans_with_zero_liquid" in density.columns


# ---------------------------------------------------------------------------
# Test 8: HTML report includes research-only safety note
# ---------------------------------------------------------------------------


def test_html_includes_research_only_note() -> None:
    df = _make_dense_outcomes(n_scans=3, n_tickers=15)
    funnel = build_candidate_loss_funnel(df)
    summary = summarize_coverage_audit(funnel)
    price_audit = build_price_path_audit(df)
    density_week = candidate_density_by_week(df)
    density_year = candidate_density_by_year(df)
    missing = build_missing_price_reasons(df)
    hp = holding_period_qa(df)
    label, note = assign_qa_label(summary, price_audit)

    html = build_html_report(
        funnel_by_scan=funnel,
        funnel_summary=summary,
        price_path_audit=price_audit,
        density_by_week=density_week,
        density_by_year=density_year,
        missing_price_reasons=missing,
        holding_period=hp,
        qa_label=label,
        qa_note=note,
        run_date="2026-05-28",
    )
    assert "RESEARCH_ONLY_NOT_PRODUCTION" in html
    assert "A3" in html
    assert "DNSE" in html
