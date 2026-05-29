from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.scans.institutional_accumulation.config import REPO

from .data_loader import load_benchmark_df, load_symbol_df, resolve_sources
from .p2_variants import P3_VARIANT_MAP, enrich_outcomes, get_p3_variant_mask

RESEARCH_ONLY_FLAG = "RESEARCH_ONLY_NOT_PRODUCTION"

ALLOWED_PORTFOLIO_LABELS = {
    "PORTFOLIO_PROMISING",
    "RISK_REDUCTION_ONLY",
    "REJECTED_PORTFOLIO",
    "INCONCLUSIVE",
    "BLOCKED_BY_DATA",
}

P3_SPLITS = [
    "full_sample",
    "sample_2022_2026",
    "ex_vin",
    "normal_regime",
    "fragile_correction_regime",
    "high_liquidity_subset",
]

TOP_N_OPTIONS = (10, 20, 30)
RANK_MODES = ("score_desc", "controlled_rank")
COST_SCENARIOS = {"low": 0.0015, "base": 0.0030, "high": 0.0050}
TURNOVER_EXCESSIVE_THRESHOLD = 0.80
VIN_TICKERS = {"VIC", "VHM", "VRE"}


@dataclass
class P3Outputs:
    equity_curves: pd.DataFrame
    portfolio_metrics: pd.DataFrame
    turnover_capacity: pd.DataFrame
    yearly_returns: pd.DataFrame
    regime_returns: pd.DataFrame
    diagnostic_summary: pd.DataFrame


def _p3_split_masks(df: pd.DataFrame) -> dict[str, pd.Series]:
    fragile_corr = (df.get("fragile_uptrend_narrow_leadership_proxy", False) == True) | (  # noqa: E712
        df.get("correction_or_bear", False) == True  # noqa: E712
    )
    return {
        "full_sample": pd.Series(True, index=df.index),
        "sample_2022_2026": (df["scan_date"] >= pd.Timestamp("2022-01-01"))
        & (df["scan_date"] <= pd.Timestamp("2026-12-31")),
        "ex_vin": df.get("is_vin", False) == False,  # noqa: E712
        "normal_regime": df.get("normal_regime", False) == True,  # noqa: E712
        "fragile_correction_regime": fragile_corr,
        "high_liquidity_subset": pd.to_numeric(df.get("adv50_vnd"), errors="coerce") >= 20_000_000_000,
    }


def _rank_candidates(sub: pd.DataFrame, rank_mode: str) -> pd.DataFrame:
    if sub.empty:
        return sub
    x = sub.copy()
    if rank_mode == "controlled_rank":
        d = pd.to_numeric(x["score_decile"], errors="coerce")
        x = x[d.isin([5, 6, 7, 8])]
        if x.empty:
            return x
        return x.sort_values(
            ["score_risk_penalty", "extension_pct_above_ma20", "institutional_accumulation_score"],
            ascending=[True, True, False],
        )
    return x.sort_values("institutional_accumulation_score", ascending=False)


def _build_price_cache(tickers: set[str], stocks_dir: Path) -> dict[str, pd.DataFrame]:
    cache: dict[str, pd.DataFrame] = {}
    parquet = REPO / "data" / "fireant_ssot" / "ta_ohlcv_panel.parquet"
    if parquet.is_file() and tickers:
        panel = pd.read_parquet(parquet)
        panel.columns = panel.columns.str.lower().str.strip()
        if "symbol" in panel.columns and "ticker" not in panel.columns:
            panel = panel.rename(columns={"symbol": "ticker"})
        panel["ticker"] = panel["ticker"].astype(str).str.upper()
        panel["date"] = pd.to_datetime(panel["date"], errors="coerce").dt.normalize()
        panel = panel[panel["ticker"].isin({t.upper() for t in tickers})]
        for ticker, g in panel.groupby("ticker", sort=False):
            px = g[["date", "open", "high", "low", "close", "volume"]].copy()
            cache[str(ticker)] = px.sort_values("date").reset_index(drop=True)
    for ticker in tickers:
        sym = str(ticker).upper()
        if sym in cache:
            continue
        px = load_symbol_df(stocks_dir, sym)
        if px is None or px.empty:
            continue
        px = px.copy()
        px["date"] = pd.to_datetime(px["date"], errors="coerce").dt.normalize()
        cache[sym] = px.sort_values("date").reset_index(drop=True)
    return cache


def _holding_return(
    ticker: str,
    entry_price: float | None,
    exit_date: pd.Timestamp,
    price_cache: dict[str, pd.DataFrame],
    stocks_dir: Path,
) -> float | None:
    if entry_price is None or not math.isfinite(entry_price) or entry_price <= 0:
        return None
    sym = str(ticker).upper()
    px = price_cache.get(sym)
    if px is None:
        px = load_symbol_df(stocks_dir, sym)
        if px is None or px.empty:
            return None
        px = px.copy()
        px["date"] = pd.to_datetime(px["date"], errors="coerce").dt.normalize()
        price_cache[sym] = px
    row = px[px["date"] == exit_date]
    if row.empty:
        return None
    exit_px = float(row["close"].iloc[0])
    if exit_px <= 0:
        return None
    return float(exit_px / entry_price - 1.0)


def _bench_weekly_returns(bench: pd.DataFrame, scan_dates: list[pd.Timestamp]) -> dict[tuple[pd.Timestamp, pd.Timestamp], float]:
    b = bench.copy()
    b["date"] = pd.to_datetime(b["date"], errors="coerce").dt.normalize()
    b = b.dropna(subset=["date"]).sort_values("date")
    idx = {d: i for i, d in enumerate(b["date"])}
    open_arr = b["open"].astype(float).to_numpy()
    out: dict[tuple[pd.Timestamp, pd.Timestamp], float] = {}
    for i in range(len(scan_dates) - 1):
        t0, t1 = scan_dates[i], scan_dates[i + 1]
        bi = idx.get(t0)
        bj = idx.get(t1)
        if bi is None or bj is None:
            continue
        entry_i = bi + 1
        if entry_i >= len(open_arr) or bj >= len(open_arr):
            continue
        entry_px = open_arr[entry_i]
        exit_px = float(b.loc[b["date"] == t1, "close"].iloc[0]) if (b["date"] == t1).any() else None
        if exit_px is None or entry_px <= 0:
            continue
        out[(t0, t1)] = float(exit_px / entry_px - 1.0)
    return out


def _portfolio_weekly_return(
    holdings: pd.DataFrame,
    exit_date: pd.Timestamp,
    price_cache: dict[str, pd.DataFrame],
    stocks_dir: Path,
) -> tuple[float | None, float | None]:
    rets: list[float] = []
    adv_vals: list[float] = []
    for _, r in holdings.iterrows():
        ticker = str(r["ticker"])
        entry = pd.to_numeric(r.get("entry_price_open_t1"), errors="coerce")
        entry_f = float(entry) if pd.notna(entry) else None
        hr = _holding_return(ticker, entry_f, exit_date, price_cache, stocks_dir)
        if hr is not None:
            rets.append(hr)
        adv = pd.to_numeric(r.get("adv50_vnd"), errors="coerce")
        if pd.notna(adv):
            adv_vals.append(float(adv))
    if not rets:
        return None, None
    adv_med = float(np.median(adv_vals)) if adv_vals else None
    return float(np.mean(rets)), adv_med


def _turnover(prev: set[str], curr: set[str]) -> float:
    if not prev and not curr:
        return 0.0
    if not prev or not curr:
        return 1.0
    union = prev | curr
    if not union:
        return 0.0
    return float(len(prev ^ curr) / len(union))


def _max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    peak = equity.cummax()
    dd = equity / peak - 1.0
    return float(dd.min())


def _annualize_from_weekly(weekly: pd.Series) -> dict[str, float | None]:
    w = weekly.dropna()
    if w.empty:
        return {"cagr": None, "vol": None, "sharpe": None, "sortino": None}
    mean_w = float(w.mean())
    std_w = float(w.std(ddof=0))
    weeks = len(w)
    years = weeks / 52.0
    cum = float((1.0 + w).prod())
    cagr = float(cum ** (1.0 / years) - 1.0) if years > 0 and cum > 0 else None
    vol = std_w * (52.0**0.5) if std_w > 0 else 0.0
    sharpe = (mean_w * 52.0) / vol if vol > 0 else 0.0
    downside = w[w < 0]
    down_std = float(downside.std(ddof=0)) if len(downside) else 0.0
    sortino = (mean_w * 52.0) / (down_std * (52.0**0.5)) if down_std > 0 else sharpe
    return {"cagr": cagr, "vol": vol, "sharpe": sharpe, "sortino": sortino}


def simulate_portfolio(
    df: pd.DataFrame,
    *,
    portfolio_id: str,
    split_name: str,
    split_mask: pd.Series,
    variant_mask: pd.Series,
    top_n: int,
    rank_mode: str,
    stocks_dir: Path,
    bench_returns: dict[tuple[pd.Timestamp, pd.Timestamp], float],
    liquid_mask: pd.Series,
    price_cache: dict[str, pd.DataFrame] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    x = df[split_mask.fillna(False)].copy()
    scan_dates = sorted(x["scan_date"].dropna().unique())
    if len(scan_dates) < 2:
        return pd.DataFrame(), pd.DataFrame()

    if price_cache is None:
        price_cache = {}
    equity_rows: list[dict[str, Any]] = []
    turnover_rows: list[dict[str, Any]] = []
    prev_holdings: set[str] = set()
    equity = 1.0

    for i in range(len(scan_dates) - 1):
        t0, t1 = scan_dates[i], scan_dates[i + 1]
        day = x[x["scan_date"] == t0]
        candidates = day[variant_mask.reindex(day.index, fill_value=False) & liquid_mask.reindex(day.index, fill_value=False)]
        ranked = _rank_candidates(candidates, rank_mode)
        holdings = ranked.head(top_n)
        tickers = set(holdings["ticker"].astype(str).tolist()) if not holdings.empty else set()

        gross, adv_med = _portfolio_weekly_return(holdings, t1, price_cache, stocks_dir)

        ew_day = day[liquid_mask.reindex(day.index, fill_value=False)]
        ew_gross, _ = _portfolio_weekly_return(ew_day, t1, price_cache, stocks_dir)

        bench_ret = bench_returns.get((t0, t1))
        turn = _turnover(prev_holdings, tickers)
        prev_holdings = tickers

        if gross is None:
            gross = 0.0
        nets: dict[str, float] = {}
        for label, rt_cost in COST_SCENARIOS.items():
            nets[label] = float(gross - turn * rt_cost)

        equity *= 1.0 + nets["base"]
        equity_rows.append(
            {
                "scan_date": t0,
                "exit_scan_date": t1,
                "portfolio_id": portfolio_id,
                "split": split_name,
                "top_n": top_n,
                "rank_mode": rank_mode,
                "research_only_flag": RESEARCH_ONLY_FLAG,
                "gross_return": gross,
                "net_return_low": nets["low"],
                "net_return_base": nets["base"],
                "net_return_high": nets["high"],
                "equity_base": equity,
                "vnindex_return": bench_ret,
                "ew_universe_return": ew_gross,
                "holdings": len(tickers),
                "turnover": turn,
            }
        )
        turnover_rows.append(
            {
                "scan_date": t0,
                "portfolio_id": portfolio_id,
                "split": split_name,
                "top_n": top_n,
                "rank_mode": rank_mode,
                "turnover": turn,
                "holdings": len(tickers),
                "adv50_vnd_median": adv_med,
                "capacity_flag": "OK" if adv_med is None or adv_med >= 5_000_000_000 else "LOW_ADV",
            }
        )

    return pd.DataFrame(equity_rows), pd.DataFrame(turnover_rows)


def _expand_equity_cost_rows(eq: pd.DataFrame) -> pd.DataFrame:
    if eq.empty:
        return eq
    rows: list[dict[str, Any]] = []
    equity_by_key: dict[tuple[Any, ...], float] = {}
    for _, r in eq.iterrows():
        key = (r["portfolio_id"], r["split"], r["top_n"], r["rank_mode"])
        for scenario, col in (
            ("low", "net_return_low"),
            ("base", "net_return_base"),
            ("high", "net_return_high"),
        ):
            net = float(r[col])
            eq_key = (*key, scenario)
            prev = equity_by_key.get(eq_key, 1.0)
            equity_by_key[eq_key] = prev * (1.0 + net)
            rows.append(
                {
                    "scan_date": r["scan_date"],
                    "exit_scan_date": r.get("exit_scan_date"),
                    "portfolio_id": r["portfolio_id"],
                    "split": r["split"],
                    "top_n": int(r["top_n"]),
                    "rank_mode": str(r["rank_mode"]),
                    "cost_scenario": scenario,
                    "gross_return": r["gross_return"],
                    "net_return": net,
                    "equity": equity_by_key[eq_key],
                    "vnindex_return": r.get("vnindex_return"),
                    "ew_universe_return": r.get("ew_universe_return"),
                    "research_only_flag": RESEARCH_ONLY_FLAG,
                }
            )
    return pd.DataFrame(rows)


def _metrics_from_equity(eq: pd.DataFrame, label_suffix: str = "base") -> dict[str, Any]:
    if eq.empty:
        return {}
    net_col = "net_return_base" if label_suffix == "base" else f"net_return_{label_suffix}"
    w = pd.to_numeric(eq[net_col], errors="coerce")
    ann = _annualize_from_weekly(w)
    eq_s = pd.to_numeric(eq["equity_base"], errors="coerce")
    mdd = _max_drawdown(eq_s)
    bench = pd.to_numeric(eq.get("vnindex_return"), errors="coerce")
    ew = pd.to_numeric(eq.get("ew_universe_return"), errors="coerce")
    cum_net = float((1.0 + w.fillna(0)).prod() - 1.0)
    cum_bench = float((1.0 + bench.fillna(0)).prod() - 1.0) if bench.notna().any() else None
    cum_ew = float((1.0 + ew.fillna(0)).prod() - 1.0) if ew.notna().any() else None
    worst = w.nsmallest(10).tolist()
    best = w.nlargest(10).tolist()
    return {
        "cagr": ann["cagr"],
        "annualized_vol": ann["vol"],
        "sharpe": ann["sharpe"],
        "sortino": ann["sortino"],
        "max_drawdown": mdd,
        "hit_rate": float((w > 0).mean()) if w.notna().any() else None,
        "avg_weekly_return": float(w.mean()) if w.notna().any() else None,
        "cumulative_net_return": cum_net,
        "cumulative_vnindex_return": cum_bench,
        "cumulative_ew_universe_return": cum_ew,
        "excess_vs_vnindex": None if cum_bench is None else cum_net - cum_bench,
        "excess_vs_ew_universe": None if cum_ew is None else cum_net - cum_ew,
        "avg_turnover": float(pd.to_numeric(eq["turnover"], errors="coerce").mean()),
        "avg_holdings": float(pd.to_numeric(eq["holdings"], errors="coerce").mean()),
        "worst_10_weeks": json.dumps(worst),
        "best_10_weeks": json.dumps(best),
    }


def label_portfolio(
    metrics: pd.DataFrame,
    *,
    portfolio_id: str,
    baseline_id: str = "P3_V0_LIQUID_UNIVERSE_BASELINE",
) -> tuple[str, str, str]:
    full = metrics[
        (metrics["portfolio_id"] == portfolio_id)
        & (metrics["split"] == "full_sample")
        & (metrics["top_n"] == 20)
        & (metrics["rank_mode"] == "score_desc")
    ]
    ex = metrics[
        (metrics["portfolio_id"] == portfolio_id)
        & (metrics["split"] == "ex_vin")
        & (metrics["top_n"] == 20)
        & (metrics["rank_mode"] == "score_desc")
    ]
    base = metrics[
        (metrics["portfolio_id"] == baseline_id)
        & (metrics["split"] == "full_sample")
        & (metrics["top_n"] == 20)
        & (metrics["rank_mode"] == "score_desc")
    ]
    if full.empty:
        return "BLOCKED_BY_DATA", "no full_sample metrics", "check simulation output"
    row = full.iloc[0]
    weeks = int(row.get("n_weeks", 0))
    if weeks < 20:
        return "BLOCKED_BY_DATA", f"only {weeks} weeks", "insufficient history"
    avg_hold = float(row.get("avg_holdings", 0) or 0)
    if avg_hold < 10:
        return "BLOCKED_BY_DATA", f"avg_holdings={avg_hold}", "too few holdings"
    ex_vs_vn = row.get("excess_vs_vnindex")
    ex_vs_ew = row.get("excess_vs_ew_universe")
    mdd = float(row.get("max_drawdown", 0) or 0)
    turn = float(row.get("avg_turnover", 1) or 1)
    base_mdd = float(base.iloc[0]["max_drawdown"]) if not base.empty else mdd
    dd_improve_pp = (mdd - base_mdd) * 100.0

    ex_ok = True
    if not ex.empty:
        ex_row = ex.iloc[0]
        ex_ok = (ex_row.get("excess_vs_vnindex") or -1) > 0 and (ex_row.get("excess_vs_ew_universe") or -1) > 0

    beats_vn = ex_vs_vn is not None and ex_vs_vn > 0
    beats_ew = ex_vs_ew is not None and ex_vs_ew > 0
    dd_ok = dd_improve_pp >= -2.0
    turn_ok = turn < TURNOVER_EXCESSIVE_THRESHOLD

    if beats_vn and beats_ew and dd_ok and turn_ok and ex_ok:
        return (
            "PORTFOLIO_PROMISING",
            f"ex_vnindex={ex_vs_vn:.4f}, ex_ew={ex_vs_ew:.4f}, dd_vs_v0_pp={dd_improve_pp:.2f}",
            "P3 research candidate only — not production",
        )
    if dd_improve_pp <= -3.0 and (not beats_vn or not beats_ew):
        return (
            "RISK_REDUCTION_ONLY",
            f"dd_vs_v0_pp={dd_improve_pp:.2f}, ex_vnindex={ex_vs_vn}",
            "risk filter research only",
        )
    if (ex_vs_vn is not None and ex_vs_vn < 0) and (ex_vs_ew is not None and ex_vs_ew < 0) and dd_improve_pp < 0:
        return "REJECTED_PORTFOLIO", f"ex_vn={ex_vs_vn}, ex_ew={ex_vs_ew}", "do not promote"
    return "INCONCLUSIVE", f"ex_vn={ex_vs_vn}, ex_ew={ex_vs_ew}, dd_pp={dd_improve_pp:.2f}", "needs review"


def run_p3_portfolio(outcomes: pd.DataFrame, out_dir: Path) -> P3Outputs:
    out_dir.mkdir(parents=True, exist_ok=True)
    sources = resolve_sources()
    bench = load_benchmark_df(sources.benchmark_path)
    df = enrich_outcomes(outcomes)
    split_masks = _p3_split_masks(df)
    liquid_mask = pd.to_numeric(df.get("adv50_vnd"), errors="coerce") >= 20_000_000_000

    all_scan = sorted(df["scan_date"].dropna().unique())
    bench_returns = _bench_weekly_returns(bench, all_scan)
    tickers = set(df["ticker"].astype(str).str.upper().unique().tolist())
    price_cache = _build_price_cache(tickers, sources.stocks_dir)

    equity_parts: list[pd.DataFrame] = []
    turnover_parts: list[pd.DataFrame] = []
    metric_rows: list[dict[str, Any]] = []

    for p3_id in P3_VARIANT_MAP:
        variant_mask = get_p3_variant_mask(df, p3_id)
        for split_name, split_mask in split_masks.items():
            for top_n in TOP_N_OPTIONS:
                for rank_mode in RANK_MODES:
                    eq, turn = simulate_portfolio(
                        df,
                        portfolio_id=p3_id,
                        split_name=split_name,
                        split_mask=split_mask,
                        variant_mask=variant_mask,
                        top_n=top_n,
                        rank_mode=rank_mode,
                        stocks_dir=sources.stocks_dir,
                        bench_returns=bench_returns,
                        liquid_mask=liquid_mask,
                        price_cache=price_cache,
                    )
                    if eq.empty:
                        continue
                    equity_parts.append(eq)
                    turnover_parts.append(turn)
                    m = _metrics_from_equity(eq)
                    m["avg_adv_participation"] = (
                        float(pd.to_numeric(turn["adv50_vnd_median"], errors="coerce").median())
                        if not turn.empty
                        else None
                    )
                    metric_rows.append(
                        {
                            "portfolio_id": p3_id,
                            "split": split_name,
                            "top_n": top_n,
                            "rank_mode": rank_mode,
                            "research_only_flag": RESEARCH_ONLY_FLAG,
                            "n_weeks": len(eq),
                            **m,
                        }
                    )

    equity_wide = pd.concat(equity_parts, ignore_index=True) if equity_parts else pd.DataFrame()
    equity_curves = _expand_equity_cost_rows(equity_wide)
    turnover_capacity = pd.concat(turnover_parts, ignore_index=True) if turnover_parts else pd.DataFrame()
    portfolio_metrics = pd.DataFrame(metric_rows)

    yearly_rows: list[dict[str, Any]] = []
    if not equity_wide.empty:
        eq = equity_wide.copy()
        eq["year"] = pd.to_datetime(eq["scan_date"]).dt.year
        for keys, g in eq.groupby(["portfolio_id", "split", "top_n", "rank_mode", "year"]):
            pid, split, tn, rm, year = keys
            w = pd.to_numeric(g["net_return_base"], errors="coerce").fillna(0)
            yearly_rows.append(
                {
                    "portfolio_id": pid,
                    "split": split,
                    "top_n": tn,
                    "rank_mode": rm,
                    "year": int(year),
                    "year_return": float((1.0 + w).prod() - 1.0),
                }
            )
    yearly_returns = pd.DataFrame(yearly_rows)

    regime_rows: list[dict[str, Any]] = []
    if not equity_wide.empty:
        eq = equity_wide.merge(
            df[["scan_date", "normal_regime", "correction_or_bear", "fragile_uptrend_narrow_leadership_proxy"]].drop_duplicates(
                "scan_date"
            ),
            on="scan_date",
            how="left",
        )
        eq["regime_bucket"] = np.where(
            eq["normal_regime"] == True,  # noqa: E712
            "normal_regime",
            np.where(
                eq["correction_or_bear"] == True,  # noqa: E712
                "correction_or_bear",
                np.where(
                    eq["fragile_uptrend_narrow_leadership_proxy"] == True,  # noqa: E712
                    "fragile_uptrend",
                    "other",
                ),
            ),
        )
        for keys, g in eq.groupby(["portfolio_id", "split", "top_n", "rank_mode", "regime_bucket"]):
            pid, split, tn, rm, regime = keys
            w = pd.to_numeric(g["net_return_base"], errors="coerce").dropna()
            regime_rows.append(
                {
                    "portfolio_id": pid,
                    "split": split,
                    "top_n": tn,
                    "rank_mode": rm,
                    "regime": regime,
                    "n_weeks": len(w),
                    "avg_weekly_return": float(w.mean()) if len(w) else None,
                    "cumulative_return": float((1.0 + w.fillna(0)).prod() - 1.0) if len(w) else None,
                }
            )
    regime_returns = pd.DataFrame(regime_rows)

    summary_rows = []
    for pid in P3_VARIANT_MAP:
        label, evidence, step = label_portfolio(portfolio_metrics, portfolio_id=pid)
        summary_rows.append(
            {
                "portfolio_id": pid,
                "label": label if label in ALLOWED_PORTFOLIO_LABELS else "INCONCLUSIVE",
                "evidence": evidence,
                "recommended_next_step": step,
            }
        )
    diagnostic_summary = pd.DataFrame(summary_rows)

    equity_curves.to_csv(out_dir / "p3_portfolio_equity_curves.csv", index=False)
    portfolio_metrics.to_csv(out_dir / "p3_portfolio_metrics.csv", index=False)
    turnover_capacity.to_csv(out_dir / "p3_turnover_capacity.csv", index=False)
    yearly_returns.to_csv(out_dir / "p3_yearly_returns.csv", index=False)
    regime_returns.to_csv(out_dir / "p3_regime_returns.csv", index=False)
    diagnostic_summary.to_csv(out_dir / "p3_diagnostic_summary.csv", index=False)

    return P3Outputs(equity_curves, portfolio_metrics, turnover_capacity, yearly_returns, regime_returns, diagnostic_summary)
