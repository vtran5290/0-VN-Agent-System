"""Phase-B metric suite for B0_CLEAN (facts only — no verdict)."""

from __future__ import annotations

from typing import Any, Iterable

import numpy as np
import pandas as pd

from .metrics import PRIMARY_COST, _pf
from .universe import EX_VIN

SETTLEMENT_PRIMARY = "SETTLEMENT_T2_ERA"


def _filled(trades: pd.DataFrame, *, t2_only: bool = False, ex_vin: bool | None = None) -> pd.DataFrame:
    if trades is None or trades.empty:
        return pd.DataFrame()
    df = trades[trades["filled"] == True].copy()  # noqa: E712
    if t2_only and "settlement_tag" in df.columns:
        df = df[df["settlement_tag"] == SETTLEMENT_PRIMARY]
    if ex_vin is True:
        df = df[~df["symbol"].isin(EX_VIN)]
    elif ex_vin is False:
        df = df[df["symbol"].isin(EX_VIN)]
    return df


def evidence_label(n: int) -> str:
    if n < 30:
        return "INSUFFICIENT_SAMPLE"
    if n < 60:
        return "DESCRIPTIVE_ONLY"
    return "ELIGIBLE_FOR_STATISTICAL_LABEL"


def _block_bootstrap_ci(
    trades: pd.DataFrame,
    col: str = PRIMARY_COST,
    block: int = 10,
    n_boot: int = 400,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Date-block bootstrap on signal_date clusters. Returns (mean, lo95, hi95)."""
    df = trades.dropna(subset=[col, "signal_date"]).copy()
    if df.empty:
        return (float("nan"), float("nan"), float("nan"))
    df["signal_date"] = pd.to_datetime(df["signal_date"])
    # daily mean of trade returns (keep cross-section together)
    daily = df.groupby("signal_date", sort=True)[col].mean()
    dates = daily.index.to_list()
    vals = daily.to_numpy(dtype=float)
    n = len(vals)
    if n < 5:
        m = float(np.nanmean(vals))
        return (m, float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    means = []
    n_blocks = max(1, int(np.ceil(n / block)))
    for _ in range(n_boot):
        picks = []
        for _b in range(n_blocks):
            start = int(rng.integers(0, max(1, n - block + 1)))
            picks.append(vals[start : start + block])
        sample = np.concatenate(picks)[:n]
        means.append(float(np.mean(sample)))
    lo, hi = np.percentile(means, [2.5, 97.5])
    return (float(np.mean(vals)), float(lo), float(hi))


def _ttest_pvalue(x: np.ndarray) -> float:
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 3:
        return float("nan")
    m = float(np.mean(x))
    s = float(np.std(x, ddof=1))
    if s == 0:
        return 0.0 if m != 0 else 1.0
    t = m / (s / np.sqrt(n))
    # two-sided normal approx for large n; Student-t via scipy if available
    try:
        from scipy import stats

        return float(2 * stats.t.sf(abs(t), df=n - 1))
    except Exception:
        from math import erfc, sqrt

        return float(erfc(abs(t) / sqrt(2.0)))


def benjamini_hochberg(pvals: pd.Series, q: float = 0.10) -> pd.Series:
    """Return BH q-values (adjusted p) aligned to pvals index."""
    s = pvals.dropna()
    m = len(s)
    if m == 0:
        return pd.Series(np.nan, index=pvals.index)
    order = s.sort_values()
    ranks = np.arange(1, m + 1)
    adj = order.to_numpy(dtype=float) * m / ranks
    # enforce monotonicity from the back
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    adj = np.clip(adj, 0, 1)
    out = pd.Series(adj, index=order.index)
    return out.reindex(pvals.index)


def per_ticker_metrics_full(trades: pd.DataFrame) -> pd.DataFrame:
    """Primary T2-era filled trades; per-ticker stats + bootstrap + BH FDR."""
    filled = _filled(trades, t2_only=True)
    if filled.empty:
        return pd.DataFrame()

    # signals attempted per symbol (all rows)
    attempted = trades.groupby("symbol").size().rename("n_signals")
    filled_n = filled.groupby("symbol").size().rename("n_filled")

    rows = []
    pvals = {}
    for sym, g in filled.groupby("symbol"):
        ret = g[PRIMARY_COST].to_numpy(dtype=float)
        gross = g["gross_return"].to_numpy(dtype=float)
        mean_b, lo, hi = _block_bootstrap_ci(g, PRIMARY_COST)
        p = _ttest_pvalue(ret)
        pvals[sym] = p
        yearly = g.copy()
        yearly["year"] = pd.to_datetime(yearly["entry_date"]).dt.year
        yearly_net = yearly.groupby("year")[PRIMARY_COST].sum()
        rows.append(
            {
                "symbol": sym,
                "n_signals": int(attempted.get(sym, 0)),
                "n_filled": int(len(g)),
                "fill_rate": float(len(g) / attempted.get(sym, len(g))) if attempted.get(sym, 0) else float("nan"),
                "mean_gross": float(np.mean(gross)),
                "median_gross": float(np.median(gross)),
                "mean_net_45bp": float(np.mean(ret)),
                "median_net_45bp": float(np.median(ret)),
                "win_rate": float(np.mean(gross > 0)),
                "pf_gross": _pf(pd.Series(gross)),
                "pf_net_45bp": _pf(pd.Series(ret)),
                "payoff": float(gross[gross > 0].mean() / abs(gross[gross < 0].mean()))
                if (gross > 0).any() and (gross < 0).any()
                else float("nan"),
                "stdev_net_45bp": float(np.std(ret, ddof=1)) if len(ret) > 1 else float("nan"),
                "es5_net_45bp": float(np.percentile(ret, 5)),
                "max_loss_net_45bp": float(np.min(ret)),
                "boot_mean_net_45bp": mean_b,
                "boot_lo95_net_45bp": lo,
                "boot_hi95_net_45bp": hi,
                "raw_pvalue": p,
                "yearly_net_sum": float(yearly_net.sum()) if len(yearly_net) else float("nan"),
                "n_years": int(yearly_net.shape[0]),
                "pct_years_positive": float((yearly_net > 0).mean()) if len(yearly_net) else float("nan"),
                "evidence_label": evidence_label(len(g)),
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["fdr_q"] = benjamini_hochberg(out.set_index("symbol")["raw_pvalue"]).reindex(out["symbol"]).to_numpy()
    return out.sort_values(["n_filled", "mean_net_45bp"], ascending=[False, False])


def multiple_testing_table(per_ticker: pd.DataFrame) -> pd.DataFrame:
    if per_ticker is None or per_ticker.empty:
        return pd.DataFrame()
    cols = [
        "symbol",
        "n_filled",
        "mean_net_45bp",
        "boot_lo95_net_45bp",
        "boot_hi95_net_45bp",
        "raw_pvalue",
        "fdr_q",
        "evidence_label",
    ]
    return per_ticker[cols].copy()


def period_window_metrics(trades: pd.DataFrame, asof: str = "2026-07-23") -> pd.DataFrame:
    """Full/5Y/3Y/1Y/6M/3M × FULL/EX_VIN × (T2-primary vs all)."""
    asof_ts = pd.Timestamp(asof)
    windows = {
        "Full_2017": pd.Timestamp("2017-01-01"),
        "5Y": asof_ts - pd.DateOffset(years=5),
        "3Y": asof_ts - pd.DateOffset(years=3),
        "1Y": asof_ts - pd.DateOffset(years=1),
        "6M": asof_ts - pd.DateOffset(months=6),
        "3M": asof_ts - pd.DateOffset(months=3),
    }
    rows = []
    for wname, start in windows.items():
        for vin_label, ex in [("FULL", None), ("EX_VIN", True)]:
            for era_label, t2 in [("T2_primary", True), ("ALL_eras", False)]:
                df = _filled(trades, t2_only=t2, ex_vin=ex if ex else None)
                if df.empty:
                    rows.append(
                        {
                            "window": wname,
                            "universe": vin_label,
                            "era": era_label,
                            "n": 0,
                        }
                    )
                    continue
                df = df[pd.to_datetime(df["entry_date"]) >= start]
                df = df[pd.to_datetime(df["entry_date"]) <= asof_ts]
                if df.empty:
                    rows.append(
                        {
                            "window": wname,
                            "universe": vin_label,
                            "era": era_label,
                            "n": 0,
                        }
                    )
                    continue
                rows.append(
                    {
                        "window": wname,
                        "universe": vin_label,
                        "era": era_label,
                        "n": int(len(df)),
                        "n_tickers": int(df["symbol"].nunique()),
                        "mean_gross": float(df["gross_return"].mean()),
                        "mean_net_45bp": float(df[PRIMARY_COST].mean()),
                        "pf_gross": _pf(df["gross_return"]),
                        "pf_net_45bp": _pf(df[PRIMARY_COST]),
                        "win_rate": float((df["gross_return"] > 0).mean()),
                    }
                )
    return pd.DataFrame(rows)


def capacity_metrics(trades: pd.DataFrame) -> pd.DataFrame:
    """Capacity proxy: fraction of ADV50 consumed at 0.5/1.0/2.0% (descriptive)."""
    filled = _filled(trades, t2_only=True, ex_vin=True)
    if filled.empty or "adv50_at_signal" not in filled.columns:
        return pd.DataFrame()
    rows = []
    # Assume notional = 1 share * entry_px is meaningless; use turnover share of ADV
    # Report how many trades have ADV50 present and summary of ADV50 itself.
    adv = pd.to_numeric(filled["adv50_at_signal"], errors="coerce")
    for pct in (0.005, 0.01, 0.02):
        cap_vnd = adv * pct
        rows.append(
            {
                "adv_fraction": pct,
                "n_with_adv": int(adv.notna().sum()),
                "median_capacity_vnd": float(cap_vnd.median()),
                "p10_capacity_vnd": float(cap_vnd.quantile(0.10)),
                "p90_capacity_vnd": float(cap_vnd.quantile(0.90)),
                "note": "capacity = ADV50_at_signal * fraction; not a position-sizing recommendation",
            }
        )
    return pd.DataFrame(rows)


def leave_one_out(trades: pd.DataFrame) -> pd.DataFrame:
    filled = _filled(trades, t2_only=True, ex_vin=True)
    if filled.empty:
        return pd.DataFrame()
    base = float(filled[PRIMARY_COST].mean())
    rows = [{"kind": "BASE_EX_VIN_T2", "left_out": None, "n": int(len(filled)), "mean_net_45bp": base}]
    # top contributors by |pnl|
    filled = filled.copy()
    filled["pnl"] = filled[PRIMARY_COST]
    top = filled.groupby("symbol")["pnl"].sum().abs().sort_values(ascending=False).head(15).index
    for sym in top:
        g = filled[filled["symbol"] != sym]
        rows.append(
            {
                "kind": "LEAVE_ONE_TICKER",
                "left_out": sym,
                "n": int(len(g)),
                "mean_net_45bp": float(g[PRIMARY_COST].mean()) if len(g) else float("nan"),
            }
        )
    filled["year"] = pd.to_datetime(filled["entry_date"]).dt.year
    for year in sorted(filled["year"].unique()):
        g = filled[filled["year"] != year]
        rows.append(
            {
                "kind": "LEAVE_ONE_YEAR",
                "left_out": str(year),
                "n": int(len(g)),
                "mean_net_45bp": float(g[PRIMARY_COST].mean()) if len(g) else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def top_ticker_contribution(trades: pd.DataFrame) -> pd.DataFrame:
    filled = _filled(trades, t2_only=True, ex_vin=True)
    if filled.empty:
        return pd.DataFrame()
    g = filled.groupby("symbol")[PRIMARY_COST].agg(["sum", "count", "mean"])
    g = g.sort_values("sum", ascending=False)
    total = float(g["sum"].sum()) if len(g) else float("nan")
    g["pct_of_aggregate_net"] = g["sum"] / total if total else np.nan
    g = g.reset_index()
    # mark top 1/5/10 cumulative
    g["cum_pct"] = g["pct_of_aggregate_net"].cumsum()
    return g


def portfolio_weight_views(trades: pd.DataFrame) -> pd.DataFrame:
    filled = _filled(trades, t2_only=True, ex_vin=True)
    if filled.empty:
        return pd.DataFrame()
    event = float(filled[PRIMARY_COST].mean())
    by_date = filled.groupby(pd.to_datetime(filled["signal_date"]))[PRIMARY_COST].mean()
    date_eq = float(by_date.mean()) if len(by_date) else float("nan")
    # daily portfolio: mean across active exits on that calendar day (approx)
    by_exit = filled.groupby(pd.to_datetime(filled["exit_date"]))[PRIMARY_COST].mean()
    daily_eq = float(by_exit.mean()) if len(by_exit) else float("nan")
    return pd.DataFrame(
        [
            {"view": "event_weighted", "mean_net_45bp": event, "n": int(len(filled))},
            {"view": "signal_date_equal_weight", "mean_net_45bp": date_eq, "n": int(len(by_date))},
            {"view": "exit_date_equal_weight", "mean_net_45bp": daily_eq, "n": int(len(by_exit))},
        ]
    )


def aggregate_extended(trades: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for label, kwargs in [
        ("T2_FULL", {"t2_only": True, "ex_vin": None}),
        ("T2_EX_VIN", {"t2_only": True, "ex_vin": True}),
        ("T2_VIN_ONLY", {"t2_only": True, "ex_vin": False}),
        ("ALL_FULL", {"t2_only": False, "ex_vin": None}),
    ]:
        df = _filled(trades, **kwargs)
        if df.empty:
            rows.append({"cell": label, "n": 0})
            continue
        mean_b, lo, hi = _block_bootstrap_ci(df, PRIMARY_COST)
        rows.append(
            {
                "cell": label,
                "n": int(len(df)),
                "n_tickers": int(df["symbol"].nunique()),
                "n_signal_dates": int(pd.to_datetime(df["signal_date"]).nunique()),
                "mean_gross": float(df["gross_return"].mean()),
                "mean_net_30bp": float(df["net_30bp"].mean()),
                "mean_net_45bp": float(df[PRIMARY_COST].mean()),
                "mean_net_60bp": float(df["net_60bp"].mean()),
                "pf_net_45bp": _pf(df[PRIMARY_COST]),
                "win_rate": float((df["gross_return"] > 0).mean()),
                "boot_lo95_net_45bp": lo,
                "boot_hi95_net_45bp": hi,
            }
        )
    return pd.DataFrame(rows)
