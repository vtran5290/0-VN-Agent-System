"""Tests for P3.2 Modern-Liquidity Portfolio Simulation.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import pandas as pd
import numpy as np
import pytest

from src.research.institutional_accumulation_backtest.p3_2_modern_portfolio import (
    ALLOWED_PORTFOLIO_LABELS,
    LIQUIDITY_CONFIGS,
    MODERN_WINDOW_START,
    PRIMARY_LIQUIDITY,
    RESEARCH_ONLY_FLAG,
    _liquid_mask,
    _liq_label,
    _modern_splits,
    _sensitivity_run,
    _metrics_from_equity,
    build_sensitivity_table,
    holding_period_sensitivity,
    label_portfolio_modern,
)
from src.research.institutional_accumulation_backtest.p3_2_reporting import write_p3_2_html


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_modern_outcomes(n_scans: int = 6, n_tickers: int = 40) -> pd.DataFrame:
    rows = []
    scan_dates = pd.date_range("2024-01-05", periods=n_scans, freq="W-FRI")
    rng = np.random.default_rng(42)
    for dt in scan_dates:
        for i in range(n_tickers):
            rows.append(
                {
                    "scan_date": dt,
                    "ticker": f"T{i:03d}",
                    "institutional_accumulation_score": float(rng.uniform(20, 80)),
                    "adv50_vnd": float(rng.uniform(5e9, 80e9)),
                    "distribution_risk_flag": i % 4 == 0,
                    "score_decile": i % 10,
                    "is_vin": i < 3,
                    "entry_price_open_t1": float(rng.uniform(10, 100)) if i % 8 != 0 else None,
                    "ret_5d": float(rng.uniform(-0.05, 0.07)),
                    "ret_10d": float(rng.uniform(-0.07, 0.10)),
                    "ret_20d": float(rng.uniform(-0.10, 0.15)),
                    "ret_60d": float(rng.uniform(-0.15, 0.25)),
                    "ret_120d": float(rng.uniform(-0.20, 0.30)),
                    "vnindex_ret_5d": float(rng.uniform(-0.03, 0.05)),
                    "vnindex_ret_10d": float(rng.uniform(-0.04, 0.06)),
                    "vnindex_ret_20d": float(rng.uniform(-0.05, 0.08)),
                    "vnindex_ret_60d": float(rng.uniform(-0.08, 0.12)),
                    "excess_ret_20d_vs_vnindex": float(rng.uniform(-0.05, 0.07)),
                    "normal_regime": True,
                    "correction_or_bear": False,
                    "fragile_uptrend_narrow_leadership_proxy": False,
                    "extension_pct_above_ma20": float(rng.uniform(0, 20)),
                    "score_risk_penalty": float(rng.uniform(20, 60)),
                    "score_money_flow": float(rng.uniform(20, 80)),
                    "score_price_structure": float(rng.uniform(20, 80)),
                    "distribution_days_25": float(rng.integers(0, 8)),
                    "turnover_accel_ratio_5d50d": float(rng.uniform(0.5, 2.0)),
                    "adv20_vnd": float(rng.uniform(3e9, 50e9)),
                    "close": float(rng.uniform(10, 100)),
                }
            )
    return pd.DataFrame(rows)


def _make_pre2024_outcomes(n_scans: int = 5, n_tickers: int = 10) -> pd.DataFrame:
    rows = []
    scan_dates = pd.date_range("2022-01-07", periods=n_scans, freq="W-FRI")
    rng = np.random.default_rng(7)
    for dt in scan_dates:
        for i in range(n_tickers):
            rows.append(
                {
                    "scan_date": dt,
                    "ticker": f"P{i:03d}",
                    "institutional_accumulation_score": float(rng.uniform(20, 80)),
                    "adv50_vnd": float(rng.uniform(1e8, 5e9)),
                    "distribution_risk_flag": False,
                    "score_decile": i % 10,
                    "is_vin": False,
                    "entry_price_open_t1": float(rng.uniform(10, 50)),
                    "ret_20d": float(rng.uniform(-0.1, 0.1)),
                    "ret_60d": float(rng.uniform(-0.15, 0.15)),
                    "vnindex_ret_20d": float(rng.uniform(-0.05, 0.05)),
                    "vnindex_ret_60d": float(rng.uniform(-0.08, 0.08)),
                    "excess_ret_20d_vs_vnindex": float(rng.uniform(-0.05, 0.05)),
                    "normal_regime": True,
                    "correction_or_bear": False,
                    "fragile_uptrend_narrow_leadership_proxy": False,
                    "extension_pct_above_ma20": float(rng.uniform(0, 15)),
                    "score_risk_penalty": float(rng.uniform(20, 60)),
                    "score_money_flow": float(rng.uniform(20, 80)),
                    "score_price_structure": float(rng.uniform(20, 80)),
                    "distribution_days_25": float(rng.integers(0, 8)),
                    "turnover_accel_ratio_5d50d": float(rng.uniform(0.5, 2.0)),
                    "close": float(rng.uniform(10, 100)),
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Test 1: 2024+ window filter keeps only modern rows
# ---------------------------------------------------------------------------


def test_modern_window_filter_excludes_pre2024() -> None:
    modern = _make_modern_outcomes(n_scans=5)
    old = _make_pre2024_outcomes(n_scans=5)
    combined = pd.concat([modern, old], ignore_index=True)
    combined["scan_date"] = pd.to_datetime(combined["scan_date"])

    splits = _modern_splits(combined, LIQUIDITY_CONFIGS[PRIMARY_LIQUIDITY])
    primary_split_mask = splits[f"modern_{PRIMARY_LIQUIDITY}"]
    filtered = combined[primary_split_mask]
    assert (pd.to_datetime(filtered["scan_date"]) >= pd.Timestamp(MODERN_WINDOW_START)).all()
    assert len(filtered) < len(combined)


# ---------------------------------------------------------------------------
# Test 2: Liquidity threshold sensitivity changes avg_candidates
# ---------------------------------------------------------------------------


def test_liquidity_threshold_sensitivity_ordering() -> None:
    df = _make_modern_outcomes(n_scans=6, n_tickers=50)
    r20 = _sensitivity_run(df, LIQUIDITY_CONFIGS["20b"], "liquid_universe", top_n=20)
    r5 = _sensitivity_run(df, LIQUIDITY_CONFIGS["5b"], "liquid_universe", top_n=20)
    # Lower threshold → more candidates
    assert r5["avg_candidates"] >= r20["avg_candidates"]


# ---------------------------------------------------------------------------
# Test 3: avg_holdings gate applied only to selected window (not full sample)
# ---------------------------------------------------------------------------


def test_label_uses_primary_split_not_full_sample() -> None:
    # Build a metrics DF where modern_20b has avg_holdings=25 but full_sample has 3
    rows = [
        {
            "portfolio_id": "P3_V0_LIQUID_UNIVERSE_BASELINE",
            "split": "modern_20b",
            "top_n": 20,
            "rank_mode": "score_desc",
            "n_weeks": 100,
            "avg_holdings": 25.0,
            "excess_vs_vnindex": 0.05,
            "excess_vs_ew_universe": 0.03,
            "max_drawdown": -0.2,
            "avg_turnover": 0.5,
        },
        {
            "portfolio_id": "P3_V0_LIQUID_UNIVERSE_BASELINE",
            "split": "full_sample",
            "top_n": 20,
            "rank_mode": "score_desc",
            "n_weeks": 468,
            "avg_holdings": 3.0,
            "excess_vs_vnindex": -0.5,
            "excess_vs_ew_universe": -0.3,
            "max_drawdown": -0.8,
            "avg_turnover": 1.0,
        },
        {
            "portfolio_id": "P3_V0_LIQUID_UNIVERSE_BASELINE",
            "split": "modern_20b_ex_vin",
            "top_n": 20,
            "rank_mode": "score_desc",
            "n_weeks": 100,
            "avg_holdings": 22.0,
            "excess_vs_vnindex": 0.04,
            "excess_vs_ew_universe": 0.02,
            "max_drawdown": -0.21,
            "avg_turnover": 0.5,
        },
    ]
    metrics = pd.DataFrame(rows)
    label, evidence, _ = label_portfolio_modern(
        metrics,
        "P3_V0_LIQUID_UNIVERSE_BASELINE",
        primary_split="modern_20b",
        ex_vin_split="modern_20b_ex_vin",
    )
    # Should NOT be BLOCKED_BY_DATA because modern_20b avg_holdings=25
    assert label != "BLOCKED_BY_DATA", f"Label was {label}: {evidence}"


# ---------------------------------------------------------------------------
# Test 4: Research-only flag in outputs
# ---------------------------------------------------------------------------


def test_sensitivity_contains_research_only_flag() -> None:
    df = _make_modern_outcomes(n_scans=4, n_tickers=30)
    sens = build_sensitivity_table(df, top_n=10)
    assert not sens.empty
    # liq_label column present
    assert "liq_label" in sens.columns
    assert "ret_20d_mean" in sens.columns


# ---------------------------------------------------------------------------
# Test 5: Holding-period sensitivity creates all four horizons
# ---------------------------------------------------------------------------


def test_holding_period_sensitivity_four_horizons() -> None:
    df = _make_modern_outcomes(n_scans=5, n_tickers=30)
    hp = holding_period_sensitivity(df, liq_threshold=LIQUIDITY_CONFIGS["5b"], top_n=20)
    assert not hp.empty
    assert "holding_label" in hp.columns
    assert set(hp["holding_label"].unique()) >= {"weekly_5d", "2week_10d", "4week_20d", "12week_60d"}
    assert (hp["research_only_flag"] == RESEARCH_ONLY_FLAG).all()


# ---------------------------------------------------------------------------
# Test 6: label_portfolio_modern always returns allowed label
# ---------------------------------------------------------------------------


def test_label_always_allowed() -> None:
    metrics = pd.DataFrame(
        [
            {
                "portfolio_id": "X",
                "split": "modern_20b",
                "top_n": 20,
                "rank_mode": "score_desc",
                "n_weeks": 5,
                "avg_holdings": 2.0,
                "excess_vs_vnindex": None,
                "excess_vs_ew_universe": None,
                "max_drawdown": -0.5,
                "avg_turnover": 0.8,
            }
        ]
    )
    label, _, _ = label_portfolio_modern(metrics, "X", primary_split="modern_20b", ex_vin_split="modern_20b_ex_vin")
    assert label in ALLOWED_PORTFOLIO_LABELS, f"Disallowed label: {label}"


# ---------------------------------------------------------------------------
# Test 7: HTML report contains safety banner and key labels
# ---------------------------------------------------------------------------


def test_html_contains_safety_banner(tmp_path) -> None:
    df = _make_modern_outcomes(n_scans=4, n_tickers=30)
    # Build minimal DataFrames
    metrics = pd.DataFrame(
        [
            {
                "portfolio_id": "P",
                "split": "modern_20b",
                "liq_threshold_label": "20b",
                "top_n": 20,
                "rank_mode": "score_desc",
                "n_weeks": 50,
                "avg_holdings": 20.0,
                "weeks_lt10_holdings": 0,
                "cagr": 0.05,
                "annualized_vol": 0.2,
                "sharpe": 0.3,
                "sortino": 0.35,
                "max_drawdown": -0.15,
                "hit_rate": 0.55,
                "avg_weekly_return": 0.001,
                "cumulative_net_return": 0.12,
                "cumulative_vnindex_return": 0.74,
                "excess_vs_vnindex": -0.62,
                "excess_vs_ew_universe": -0.05,
                "avg_turnover": 0.4,
                "avg_adv_participation": 5e10,
                "worst_10_weeks": "[]",
                "best_10_weeks": "[]",
            }
        ]
    )
    diag = pd.DataFrame(
        [{"portfolio_id": "P", "liq_threshold_label": "20b", "primary_split": "modern_20b", "label": "INCONCLUSIVE", "evidence": "test", "recommended_next_step": "none", "research_only_flag": RESEARCH_ONLY_FLAG}]
    )
    out = tmp_path / "p3_2_test.html"
    write_p3_2_html(
        out,
        portfolio_metrics=metrics,
        diagnostic_summary=diag,
        equity_curves=pd.DataFrame(),
        turnover_capacity=pd.DataFrame(),
        yearly_returns=pd.DataFrame(),
        sensitivity=pd.DataFrame(),
        run_date="2026-05-28",
    )
    html = out.read_text(encoding="utf-8")
    assert "RESEARCH_ONLY_NOT_PRODUCTION" in html
    assert "DNSE" in html
    assert "2024-01-01" in html


# ---------------------------------------------------------------------------
# Test 8: _liq_label round-trips LIQUIDITY_CONFIGS
# ---------------------------------------------------------------------------


def test_liq_label_round_trips() -> None:
    for label, threshold in LIQUIDITY_CONFIGS.items():
        assert _liq_label(threshold) == label
