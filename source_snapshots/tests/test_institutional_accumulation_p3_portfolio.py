from __future__ import annotations

import zipfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from scripts.research.institutional_accumulation_backtest.build_p3_review_pack import (
    P3PackBuildError,
    build_p3_review_pack,
)
from src.research.institutional_accumulation_backtest.p2_variants import (
    build_variant_masks,
    enrich_outcomes,
    get_p3_variant_mask,
)
from src.research.institutional_accumulation_backtest.p3_portfolio import (
    ALLOWED_PORTFOLIO_LABELS,
    COST_SCENARIOS,
    RESEARCH_ONLY_FLAG,
    _expand_equity_cost_rows,
    run_p3_portfolio,
    simulate_portfolio,
)
from src.research.institutional_accumulation_backtest.p3_reporting import write_p3_html_report


def _fixture(rows: int = 160) -> pd.DataFrame:
    out = []
    dates = pd.date_range("2024-01-02", periods=8, freq="7D")
    for i in range(rows):
        scan = dates[i % len(dates)]
        score = float((i % 10) * 10 + 5)
        ticker = "AAA" if i % 2 == 0 else "BBB"
        out.append(
            {
                "scan_date": scan,
                "ticker": ticker,
                "institutional_accumulation_score": score,
                "score_risk_penalty": 100 - score * 0.4,
                "extension_pct_above_ma20": (i % 8) / 20,
                "ret_5d": (i % 7 - 3) / 100,
                "ret_10d": (i % 9 - 4) / 100,
                "ret_20d": (i % 11 - 5) / 100,
                "ret_60d": (i % 13 - 6) / 100,
                "ret_120d": (i % 15 - 7) / 100,
                "distribution_risk_flag": i % 3 == 0,
                "distribution_days_25": i % 7,
                "is_vin": ticker == "VIC",
                "adv50_vnd": 25_000_000_000 if i % 2 == 0 else 10_000_000_000,
                "turnover_accel_ratio_5d50d": 0.5 + (i % 4) / 10,
                "normal_regime": i % 3 == 0,
                "correction_or_bear": i % 6 == 0,
                "fragile_uptrend_narrow_leadership_proxy": i % 5 == 0,
                "entry_price_open_t1": 100.0 + i,
            }
        )
    return pd.DataFrame(out)


def _mock_prices(stocks_dir: Path, ticker: str) -> pd.DataFrame:
    dates = pd.date_range("2024-01-02", periods=60, freq="D")
    return pd.DataFrame(
        {
            "date": dates,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0 + (dates.dayofyear % 5),
            "volume": 1_000_000,
        }
    )


def _mock_bench(path: Path) -> pd.DataFrame:
    dates = pd.date_range("2024-01-02", periods=60, freq="D")
    return pd.DataFrame(
        {
            "date": dates,
            "open": 1000.0,
            "high": 1001.0,
            "low": 999.0,
            "close": 1000.0,
            "volume": 1_000_000,
        }
    )


@patch("src.research.institutional_accumulation_backtest.p3_portfolio.load_benchmark_df", side_effect=_mock_bench)
@patch("src.research.institutional_accumulation_backtest.p3_portfolio.load_symbol_df", side_effect=_mock_prices)
@patch("src.research.institutional_accumulation_backtest.p3_portfolio.resolve_sources")
def test_p3_runs_on_fixture(mock_sources, _sym, _bench, tmp_path: Path) -> None:
    mock_sources.return_value.stocks_dir = tmp_path / "stocks"
    mock_sources.return_value.benchmark_path = tmp_path / "VNINDEX.csv"
    mock_sources.return_value.benchmark_ticker = "VNINDEX"
    mock_sources.return_value.sector_map_path = tmp_path / "sectors.csv"
    mock_sources.return_value.source_label = "fixture"

    out = run_p3_portfolio(_fixture(), tmp_path)
    assert (tmp_path / "p3_portfolio_equity_curves.csv").is_file()
    assert (tmp_path / "p3_portfolio_metrics.csv").is_file()
    assert (tmp_path / "p3_diagnostic_summary.csv").is_file()
    assert not out.equity_curves.empty
    assert set(out.diagnostic_summary["label"].unique()).issubset(ALLOWED_PORTFOLIO_LABELS)


@patch("src.research.institutional_accumulation_backtest.p3_portfolio.load_benchmark_df", side_effect=_mock_bench)
@patch("src.research.institutional_accumulation_backtest.p3_portfolio.load_symbol_df", side_effect=_mock_prices)
@patch("src.research.institutional_accumulation_backtest.p3_portfolio.resolve_sources")
def test_non_overlapping_weekly_rebalance(mock_sources, _sym, _bench, tmp_path: Path) -> None:
    mock_sources.return_value.stocks_dir = tmp_path / "stocks"
    mock_sources.return_value.benchmark_path = tmp_path / "VNINDEX.csv"
    out = run_p3_portfolio(_fixture(), tmp_path)
    eq = out.equity_curves[out.equity_curves["cost_scenario"] == "base"]
    sub = eq[
        (eq["portfolio_id"] == "P3_V0_LIQUID_UNIVERSE_BASELINE")
        & (eq["split"] == "full_sample")
        & (eq["top_n"] == 20)
        & (eq["rank_mode"] == "score_desc")
    ]
    sub = sub.sort_values("scan_date")
    exits = pd.to_datetime(sub["exit_scan_date"]).tolist()
    next_scans = pd.to_datetime(sub["scan_date"]).tolist()[1:]
    assert exits[:-1] == next_scans


@patch("src.research.institutional_accumulation_backtest.p3_portfolio.load_benchmark_df", side_effect=_mock_bench)
@patch("src.research.institutional_accumulation_backtest.p3_portfolio.load_symbol_df", side_effect=_mock_prices)
@patch("src.research.institutional_accumulation_backtest.p3_portfolio.resolve_sources")
def test_equity_not_compounding_20d_60d(mock_sources, _sym, _bench, tmp_path: Path) -> None:
    mock_sources.return_value.stocks_dir = tmp_path / "stocks"
    mock_sources.return_value.benchmark_path = tmp_path / "VNINDEX.csv"
    df = enrich_outcomes(_fixture())
    out = run_p3_portfolio(df, tmp_path)
    eq = out.equity_curves[(out.equity_curves["cost_scenario"] == "base") & (out.equity_curves["split"] == "full_sample")]
    weekly = eq.groupby("portfolio_id")["gross_return"].mean().iloc[0]
    ret60_path = float(df["ret_60d"].mean())
    assert weekly != pytest.approx(ret60_path, rel=0.01)


def test_variant_selection_matches_p2_masks() -> None:
    df = enrich_outcomes(_fixture(200))
    v4 = get_p3_variant_mask(df, "P3_V4_NO_DISTRIBUTION_RISK")
    sub = df[v4.fillna(False)]
    assert (sub["distribution_risk_flag"] == True).sum() == 0  # noqa: E712
    v6 = get_p3_variant_mask(df, "P3_V6_CONTROLLED_ACCUMULATION")
    sub6 = df[v6.fillna(False)]
    d = pd.to_numeric(sub6["score_decile"], errors="coerce")
    assert (d == 9).sum() == 0


@patch("src.research.institutional_accumulation_backtest.p3_portfolio.load_benchmark_df", side_effect=_mock_bench)
@patch("src.research.institutional_accumulation_backtest.p3_portfolio.load_symbol_df", side_effect=_mock_prices)
def test_top_n_cap(_sym, _bench, tmp_path: Path) -> None:
    df = enrich_outcomes(_fixture())
    liquid = pd.to_numeric(df.get("adv50_vnd"), errors="coerce") >= 20_000_000_000
    mask = get_p3_variant_mask(df, "P3_V0_LIQUID_UNIVERSE_BASELINE")
    eq, turn = simulate_portfolio(
        df,
        portfolio_id="P3_V0_LIQUID_UNIVERSE_BASELINE",
        split_name="full_sample",
        split_mask=pd.Series(True, index=df.index),
        variant_mask=mask,
        top_n=10,
        rank_mode="score_desc",
        stocks_dir=tmp_path / "stocks",
        bench_returns={},
        liquid_mask=liquid,
    )
    assert (turn["holdings"] <= 10).all()


def test_costs_reduce_returns() -> None:
    row = {"gross_return": 0.02, "turnover": 0.5}
    gross = row["gross_return"]
    turn = row["turnover"]
    nets = {k: gross - turn * v for k, v in COST_SCENARIOS.items()}
    assert nets["high"] < nets["base"] < nets["low"] < gross


def test_ex_vin_excludes_vin() -> None:
    df = enrich_outcomes(_fixture(200))
    df.loc[df["ticker"] == "AAA", "is_vin"] = True
    df.loc[df["ticker"] == "AAA", "ticker"] = "VIC"
    ex_mask = df.get("is_vin", False) == False  # noqa: E712
    assert not ex_mask[df["ticker"] == "VIC"].any()


def test_html_safety_note(tmp_path: Path) -> None:
    metrics = pd.DataFrame(
        [{"portfolio_id": "P3_V0_LIQUID_UNIVERSE_BASELINE", "split": "full_sample", "top_n": 20, "rank_mode": "score_desc", "cagr": 0.1}]
    )
    diag = pd.DataFrame([{"portfolio_id": "P3_V0_LIQUID_UNIVERSE_BASELINE", "label": "INCONCLUSIVE", "evidence": "x", "recommended_next_step": "y"}])
    html = tmp_path / "p3.html"
    write_p3_html_report(
        html,
        portfolio_metrics=metrics,
        diagnostic_summary=diag,
        turnover_capacity=pd.DataFrame(),
        yearly_returns=pd.DataFrame(),
        regime_returns=pd.DataFrame(),
        equity_curves=pd.DataFrame(),
    )
    txt = html.read_text(encoding="utf-8")
    assert "P3 Portfolio Simulation" in txt
    assert "Research-only" in txt
    assert RESEARCH_ONLY_FLAG in txt


def test_p3_no_real_path_writes(tmp_path: Path) -> None:
    real = Path.cwd() / "data" / "research" / "institutional_accumulation" / "p3_portfolio_metrics.csv"
    before = real.stat().st_mtime if real.is_file() else None
    with patch("src.research.institutional_accumulation_backtest.p3_portfolio.resolve_sources") as mock_sources:
        mock_sources.return_value.stocks_dir = tmp_path / "stocks"
        mock_sources.return_value.benchmark_path = tmp_path / "VNINDEX.csv"
        with patch("src.research.institutional_accumulation_backtest.p3_portfolio.load_symbol_df", side_effect=_mock_prices):
            with patch("src.research.institutional_accumulation_backtest.p3_portfolio.load_benchmark_df", side_effect=_mock_bench):
                run_p3_portfolio(_fixture(), tmp_path / "iso")
    after = real.stat().st_mtime if real.is_file() else None
    assert before == after


def test_p3_pack_blocks_fixture(tmp_path: Path) -> None:
    root = tmp_path / "root"
    p3 = root / "data" / "research" / "institutional_accumulation"
    p3.mkdir(parents=True, exist_ok=True)
    _fixture(120).to_parquet(p3 / "forward_outcomes_panel.parquet", index=False)
    pd.DataFrame([{"scan_date": "2024-01-01", "portfolio_id": "x"}]).to_csv(p3 / "p3_portfolio_equity_curves.csv", index=False)
    (root / "implementation_report.md").write_text("# P3 Portfolio Simulation Implementation Report\n", encoding="utf-8")
    (root / "test_log.txt").write_text("ok\n", encoding="utf-8")
    (root / "open_questions_for_chatgpt.md").write_text("ok\n", encoding="utf-8")
    html = root / "reports" / "research" / "institutional_accumulation" / "p3_portfolio_simulation.html"
    html.parent.mkdir(parents=True, exist_ok=True)
    html.write_text(
        "<html><h1>P3 Portfolio Simulation</h1>" + ("x" * 1200) + " RESEARCH_ONLY_NOT_PRODUCTION Research-only.</html>",
        encoding="utf-8",
    )
    with pytest.raises(P3PackBuildError):
        build_p3_review_pack(root=root, output_zip=root / "packs" / "bad.zip")


def test_expand_equity_cost_rows() -> None:
    wide = pd.DataFrame(
        [
            {
                "scan_date": "2024-01-02",
                "exit_scan_date": "2024-01-09",
                "portfolio_id": "P3_V0_LIQUID_UNIVERSE_BASELINE",
                "split": "full_sample",
                "top_n": 20,
                "rank_mode": "score_desc",
                "gross_return": 0.01,
                "net_return_low": 0.009,
                "net_return_base": 0.008,
                "net_return_high": 0.007,
                "vnindex_return": 0.0,
                "ew_universe_return": 0.0,
            }
        ]
    )
    long_df = _expand_equity_cost_rows(wide)
    assert set(long_df["cost_scenario"]) == {"low", "base", "high"}
    assert len(long_df) == 3
