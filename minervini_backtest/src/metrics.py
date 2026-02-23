# minervini_backtest/src/metrics.py — PF, winrate, expectancy, MaxDD, CAGR, trade stats, sensitivity
from __future__ import annotations
import numpy as np
import pandas as pd


def trade_metrics(ledger: pd.DataFrame) -> dict:
    """
    ledger must have: ret, hold_bars (or hold_days), entry_px, exit_px.
    Returns: trades, win_rate, avg_ret, median_ret, avg_win, avg_loss, profit_factor,
             expectancy, max_drawdown, avg_hold_days, median_hold_bars, tail5, cagr (if dates).
    """
    if ledger is None or ledger.empty:
        return {
            "trades": 0, "win_rate": np.nan, "avg_ret": np.nan, "median_ret": np.nan,
            "avg_win": np.nan, "avg_loss": np.nan, "profit_factor": np.nan,
            "expectancy": np.nan, "max_drawdown": np.nan, "avg_hold_days": np.nan,
            "median_hold_bars": np.nan, "tail5": np.nan, "cagr": np.nan,
        }
    ret = ledger["ret"].astype(float).values
    n = len(ret)
    wins = ret[ret > 0]
    losses = ret[ret <= 0]
    pf = (wins.sum() / (-losses.sum())) if len(losses) and losses.sum() < 0 and len(wins) else np.nan
    cum = np.cumprod(1.0 + ret) - 1.0
    peak = np.maximum.accumulate(1.0 + cum)
    mdd = float((((1.0 + cum) / peak) - 1.0).min()) if len(cum) else np.nan
    tail5 = float(np.nanpercentile(ret, 5))
    median_hold = float(ledger["hold_bars"].median()) if "hold_bars" in ledger.columns else np.nan
    avg_hold_days = float(ledger["hold_days"].mean()) if "hold_days" in ledger.columns else np.nan

    # CAGR: (1 + total_ret)^(252*bar_years / n_bars) - 1 approx; or from first entry to last exit
    cagr = np.nan
    if "entry_date" in ledger.columns and "exit_date" in ledger.columns and len(ledger) > 0:
        first = pd.to_datetime(ledger["entry_date"].min())
        last = pd.to_datetime(ledger["exit_date"].max())
        years = (last - first).days / 365.25 if (last - first).days > 0 else np.nan
        if years and np.isfinite(years) and years > 0:
            total_ret = float(cum[-1]) if len(cum) else 0.0
            cagr = (1.0 + total_ret) ** (1.0 / years) - 1.0

    return {
        "trades": n,
        "win_rate": float((ret > 0).mean()),
        "avg_ret": float(ret.mean()),
        "median_ret": float(np.median(ret)),
        "avg_win": float(wins.mean()) if len(wins) else np.nan,
        "avg_loss": float(losses.mean()) if len(losses) else np.nan,
        "profit_factor": float(pf) if pf == pf and np.isfinite(pf) else np.nan,
        "expectancy": float(ret.mean()),
        "max_drawdown": mdd,
        "avg_hold_days": avg_hold_days,
        "median_hold_bars": median_hold,
        "tail5": tail5,
        "cagr": cagr,
    }


def trades_per_year(ledger: pd.DataFrame) -> float:
    if ledger is None or ledger.empty or "exit_date" not in ledger.columns:
        return np.nan
    dates = pd.to_datetime(ledger["exit_date"])
    span_years = (dates.max() - dates.min()).days / 365.25
    if span_years <= 0:
        return np.nan
    return len(ledger) / span_years


def minervini_r_metrics(ledger: pd.DataFrame) -> dict:
    """
    R-multiple game metrics. Ledger should have entry_px, exit_px, stop_px.
    Returns: expectancy_r, pct_hit_1r, pct_hit_2r, payoff_ratio, loss_rate, top10_pct_pnl.
    MAE/MFE need bar-level data (not in ledger); optional later.
    """
    out = {
        "expectancy_r": np.nan,
        "pct_hit_1r": np.nan,
        "pct_hit_2r": np.nan,
        "payoff_ratio": np.nan,
        "loss_rate": np.nan,
        "top10_pct_pnl": np.nan,
    }
    if ledger is None or ledger.empty or "stop_px" not in ledger.columns:
        return out
    entry = ledger["entry_px"].astype(float)
    exit_px = ledger["exit_px"].astype(float)
    stop = ledger["stop_px"].astype(float)
    r_per_share = entry - stop
    r_per_share = r_per_share.replace(0, np.nan)
    r_mult = (exit_px - entry) / r_per_share
    r_mult = r_mult.dropna()
    if len(r_mult) == 0:
        return out
    ret = ledger["ret"].astype(float)
    wins = ret[ret > 0]
    losses = ret[ret <= 0]
    out["expectancy_r"] = float(r_mult.mean())
    out["pct_hit_1r"] = float((r_mult >= 1.0).mean())
    out["pct_hit_2r"] = float((r_mult >= 2.0).mean())
    out["loss_rate"] = float((ret <= 0).mean())
    if len(wins) and len(losses) and losses.sum() != 0:
        out["payoff_ratio"] = float(wins.mean() / (-losses.mean()))
    # Profit concentration: top 10 trades % of total PnL
    pnl = ret * 100  # % per trade
    total = pnl.sum()
    if total > 0 and len(pnl) >= 10:
        top10 = pnl.nlargest(10).sum()
        out["top10_pct_pnl"] = float(top10 / total)
    elif total != 0 and len(pnl) > 0:
        out["top10_pct_pnl"] = float(pnl.nlargest(min(10, len(pnl))).sum() / total)
    return out
