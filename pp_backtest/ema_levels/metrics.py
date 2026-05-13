"""
Performance metrics for the EMA-cloud + price-level backtest.

compute_metrics(trades)         -- all core metrics from a trades DataFrame
subperiod_metrics(trades, ...)  -- per-subperiod breakdown
composite_score(m)              -- balanced scalar for ranking parameter combos
"""

from __future__ import annotations

import numpy as np
import pandas as pd

ANN_FACTOR = 252   # trading days per year


def compute_metrics(
    trades:  pd.DataFrame,
    ret_col: str = "net_return",
) -> dict:
    """
    Core metrics.  All metrics computed on per-trade returns.

    Notes
    -----
    • CAGR is approximate: uses average hold duration to estimate total calendar time.
    • Sharpe/Sortino are annualised assuming IID per-trade returns spaced avg_hold apart.
    • max_dd is computed on a sequential equity curve (trades in date order).
    • Returns NaN for metrics that require more data than available.
    """
    if len(trades) == 0:
        return _empty_metrics()

    rets = trades[ret_col].dropna()
    n = len(rets)

    if n < 5:
        return _empty_metrics()

    # Basic stats
    hit_rate   = (rets > 0).mean()
    avg_ret    = rets.mean()
    med_ret    = rets.median()
    std_ret    = rets.std(ddof=1)
    gross_wins = rets[rets > 0].sum()
    gross_loss = abs(rets[rets < 0].sum()) or 1e-12
    pf         = gross_wins / gross_loss

    # Hold duration (bars) — use actual or horizon column
    if "hold_bars" in trades.columns:
        avg_hold = trades["hold_bars"].dropna().mean()
    elif "horizon" in trades.columns:
        avg_hold = trades["horizon"].mean()
    else:
        avg_hold = 50.0

    # Total compounded return
    total_ret = (1.0 + rets).prod() - 1.0

    # CAGR
    n_years = max((n * avg_hold) / ANN_FACTOR, 0.05)
    cagr = (1.0 + total_ret) ** (1.0 / n_years) - 1.0 if n_years > 0 else np.nan

    # Max drawdown (sequential equity curve)
    eq = (1.0 + rets.reset_index(drop=True)).cumprod()
    run_max = eq.cummax()
    dd = (eq - run_max) / run_max
    max_dd = dd.min()

    # Sharpe (annualised)
    if std_ret > 0 and avg_hold > 0:
        sharpe = (avg_ret / std_ret) * np.sqrt(ANN_FACTOR / avg_hold)
    else:
        sharpe = np.nan

    # Sortino (annualised, no risk-free rate)
    down_rets = rets[rets < 0]
    if len(down_rets) >= 2 and down_rets.std(ddof=1) > 0 and avg_hold > 0:
        sortino = (avg_ret / down_rets.std(ddof=1)) * np.sqrt(ANN_FACTOR / avg_hold)
    else:
        sortino = np.nan

    # MAR = CAGR / |max_dd|
    mar = cagr / abs(max_dd) if (max_dd != 0 and not np.isnan(cagr)) else np.nan

    # Right-tail capture
    rt2 = float((rets > 2.0 * avg_ret).mean()) if avg_ret > 0 else np.nan
    rt3 = float((rets > 3.0 * avg_ret).mean()) if avg_ret > 0 else np.nan

    return {
        "n_trades":       n,
        "hit_rate":       hit_rate,
        "avg_return":     avg_ret,
        "median_return":  med_ret,
        "std_return":     std_ret,
        "profit_factor":  pf,
        "total_return":   total_ret,
        "cagr":           cagr,
        "max_dd":         max_dd,
        "sharpe":         sharpe,
        "sortino":        sortino,
        "mar":            mar,
        "right_tail_2x":  rt2,
        "right_tail_3x":  rt3,
    }


def _empty_metrics() -> dict:
    return {k: np.nan for k in [
        "n_trades", "hit_rate", "avg_return", "median_return", "std_return",
        "profit_factor", "total_return", "cagr", "max_dd",
        "sharpe", "sortino", "mar", "right_tail_2x", "right_tail_3x",
    ]}


def subperiod_metrics(
    trades:   pd.DataFrame,
    periods:  list[tuple],   # [(start_str, end_str, label), ...]
    date_col: str = "entry_date",
    ret_col:  str = "net_return",
) -> pd.DataFrame:
    """
    Compute metrics for each subperiod.
    Returns a DataFrame with columns: period, start, end, + all metric keys.
    """
    rows = []
    tdf = trades.copy()
    tdf[date_col] = pd.to_datetime(tdf[date_col])

    for start, end, label in periods:
        mask = (tdf[date_col] >= start) & (tdf[date_col] < end)
        sub  = tdf[mask]
        m    = compute_metrics(sub, ret_col=ret_col)
        m["period"] = label
        m["start"]  = start
        m["end"]    = end
        rows.append(m)

    return pd.DataFrame(rows)


def stability_score(sub_metrics: pd.DataFrame) -> float:
    """
    Cross-period stability: penalise high variance of hit_rate and avg_return.
    Returns a score in [0, 1], where 1 = perfectly stable across periods.
    Only periods with at least 5 trades contribute.
    """
    if len(sub_metrics) < 2:
        return 0.5

    valid = sub_metrics[sub_metrics["n_trades"] >= 5]
    if len(valid) < 2:
        return 0.3   # not enough periods with real data

    hr_std = valid["hit_rate"].dropna().std()
    ar_std = valid["avg_return"].dropna().std()
    pct_positive = (valid["avg_return"].dropna() > 0).mean()

    # score degrades with high variance; rewards consistency across periods
    raw = max(0.0, 1.0 - hr_std * 2.0 - ar_std * 8.0)
    return 0.7 * raw + 0.3 * pct_positive


def composite_score(
    m: dict,
    period_ret_std: float = np.nan,
) -> float:
    """
    Balanced composite score for ranking parameter combinations.

    Weights (approximate):
        CAGR           25 %
        Sharpe         25 %
        Max drawdown   25 %
        Median return  15 %
        Sample size     5 %
        Stability       5 %

    Hard penalties:
        n_trades < 20  →  -999 (not rankable)
        max_dd < -0.6  →  -999 (catastrophic drawdown)
    """
    n     = m.get("n_trades", 0) or 0
    cagr  = m.get("cagr",    0.0) or 0.0
    dd    = m.get("max_dd", -1.0) or -1.0
    sh    = m.get("sharpe",  0.0) or 0.0
    med   = m.get("median_return", 0.0) or 0.0

    if n < 20 or dd < -0.70:
        return -999.0

    # Clip to avoid extreme distortions
    cagr = float(np.clip(cagr, -0.5, 3.0))
    sh   = float(np.clip(sh,   -3.0, 10.0))
    dd   = float(np.clip(dd,   -1.0, 0.0))

    return_s    = cagr  * 0.25
    risk_adj_s  = (sh / 5.0) * 0.25
    dd_s        = (1.0 + dd) * 0.25   # dd in (-1,0] → (0,1]
    med_s       = float(np.clip(med * 20.0, -1.0, 1.0)) * 0.15
    size_s      = min(np.log10(max(n, 1)) / 3.0, 1.0) * 0.05

    # Stability bonus: penalise high cross-period variance
    if not np.isnan(period_ret_std):
        stab_s = max(0.0, 0.5 - period_ret_std * 5.0) * 0.05
    else:
        stab_s = 0.0

    return return_s + risk_adj_s + dd_s + med_s + size_s + stab_s
