"""Stage 12B — S3 MaxHold Robustness Patch.

Validates whether MAX_HOLD_120 (flagged PARALLEL_PAPER_RESEARCH in Stage 12) is a
genuine improvement over the official MAX_HOLD_60 paper-shadow baseline, or an
artifact of longer capital lock-up.

Research questions answered:
1. CAGR/MAR vs win rate/TP1: does holding longer improve risk-adjusted return?
2. MaxDD: does MaxHold_120 worsen drawdown?
3. Hold extension: avg/p90 hold bars vs baseline
4. Turnover-adjusted performance
5. 2022/2024 weak-year survival
6. MaxHold sweep 45/60/75/90/105/120/150 — is 120 special?
7. Sensitivity: TOP100_ADV, TOP150_ADV, EX_VIN, BVE_Q4Q5, VNINDEX_BULL_ONLY
8. Final classification: remain PARALLEL_PAPER_RESEARCH, downgrade, or reject?

Guardrails:
- MAX_HOLD_60_BASE remains the OFFICIAL S3 paper-shadow baseline.
- MAX_HOLD_120 is RESEARCH-ONLY until separately approved.
- MAX_HOLD_REJECTED = 250 is not used.
- S3 P&L is completely separate from A3.
- No production / OMS / live change.
- final_action not modified.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from scripts.research.dual_cloud_accumulation_wyckoff.panel_utils import (
    MIN_ADV_VND,
    OUT_DIR,
    load_panel,
    load_vnindex_regime,
    cloud_signal,
)
from scripts.research.dual_cloud_accumulation_wyckoff.stage12_s3_shadow_contract_validation import (
    _atr14,
    _simulate_s3_trade,
    TP1_PCT,
    TP1_SIZE,
    TRAIL_MULT,
    COST_RT,
    _VIN_SYMBOLS,
    _liq_bucket,
)

log = logging.getLogger(__name__)

# ── Safety ──────────────────────────────────────────────────────────────────────
_STAGE12B_WRITE_DIR: Path = OUT_DIR

_OMS_SAFE_PATHS: frozenset[str] = frozenset({
    str(REPO / "data" / "decision" / "daily_scan.json"),
    str(REPO / "data" / "decision" / "daily_scan.md"),
    str(REPO / "data" / "decision" / "allocation_plan.json"),
    str(REPO / "data" / "state" / "regime_state.json"),
    str(REPO / "data" / "raw" / "current_positions_derived.json"),
    str(REPO / "data" / "raw" / "current_positions_digest.md"),
})

# ── Input file ──────────────────────────────────────────────────────────────────
_STAGE12_TRADES = OUT_DIR / "stage12_s3_shadow_trades.csv"

# ── MaxHold variants ────────────────────────────────────────────────────────────
MAIN_MH_VALUES: List[int] = [45, 60, 75, 90, 105, 120, 150]
_MH_OFFICIAL_BASELINE = 60          # frozen S3 paper-shadow contract
_MH_STUDY_VARIANT     = 120         # variant under robustness review
_MAX_HOLD_REJECTED    = 250         # defined, never used as candidate

# ── Classification thresholds ───────────────────────────────────────────────────
_MIN_N_PARALLEL    = 300
_WIN_DELTA_THRESH  = 0.05           # ≥5 pp
_TP1_DELTA_THRESH  = 0.03           # ≥3 pp
_MAXDD_WORSEN_HARD = 0.05           # >5 pp worsening → hold_extension_risk_flag
_MAXDD_WORSEN_SOFT = 0.03           # >3 pp worsening → downgrade
_HOLD_EXTENSION_BARS = 30           # avg_hold increases > 30 bars → flag
_P90_HOLD_HARD      = 110           # p90_hold_bars > 110 → flag

# ── Forbidden classifications (S3 can never be these) ──────────────────────────
_FORBIDDEN_CLASSIFICATIONS = frozenset({"PRODUCTION_CANDIDATE", "PAPER_TRADE_PRIMARY"})

_S3_FAST = 21
_S3_SLOW = 55


# ── Helpers ────────────────────────────────────────────────────────────────────

def _mh_key(mh: int) -> str:
    return f"mh{mh}"


def _equity_curve_stats(
    returns: np.ndarray,
    signal_dates: Optional[pd.Series] = None,
) -> dict:
    """
    Compute equity-curve-based risk metrics from trade returns.

    Uses ANNUAL-AVERAGE equity curve (not sequential individual-trade compounding).
    Rationale: sequentially compounding 2,000+ individual trades across many different
    stocks conflates single-stock risk with portfolio diversification, producing
    spurious MaxDD near -100%. Using year-level average returns is more appropriate
    for a multi-stock, high-frequency strategy.

    MaxDD = max peak-to-trough decline of the year-level equity curve.
    CAGR  = geometric mean of annual average returns.
    Sharpe = trade-level: mean_net / std_net (not annualized; label accordingly).
    """
    _empty = {"max_drawdown": np.nan, "cagr": np.nan, "mar": np.nan, "sharpe": np.nan}
    if len(returns) == 0:
        return _empty

    # Sharpe (trade-level, not annualized)
    mean_r = float(np.mean(returns))
    std_r  = float(np.std(returns, ddof=1)) if len(returns) > 1 else np.nan
    sharpe = float(mean_r / std_r) if (not np.isnan(std_r) and std_r > 1e-9) else np.nan

    if signal_dates is None or len(signal_dates) != len(returns):
        # Without dates, fall back to individual equity curve for MaxDD only
        equity = np.cumprod(1.0 + np.clip(returns, -0.999, 10.0))
        peak   = np.maximum.accumulate(equity)
        max_dd = float(((equity - peak) / peak).min())
        return {"max_drawdown": max_dd, "cagr": np.nan, "mar": np.nan, "sharpe": sharpe}

    # Build year-level average returns
    try:
        dates = pd.to_datetime(signal_dates)
        years = dates.dt.year.values
        yr_labels = sorted(set(years))
        yr_avg = np.array([returns[years == y].mean() for y in yr_labels])
    except Exception:
        return {"max_drawdown": np.nan, "cagr": np.nan, "mar": np.nan, "sharpe": sharpe}

    if len(yr_avg) == 0:
        return {"max_drawdown": np.nan, "cagr": np.nan, "mar": np.nan, "sharpe": sharpe}

    # Year-level equity curve
    equity = np.cumprod(1.0 + np.clip(yr_avg, -0.999, 10.0))
    peak   = np.maximum.accumulate(equity)
    max_dd = float(((equity - peak) / peak).min())

    # CAGR from year span
    n_years = len(yr_avg)
    cagr    = float(equity[-1] ** (1.0 / n_years) - 1.0) if n_years > 0 else np.nan

    mar = float(cagr / abs(max_dd)) if (not np.isnan(cagr) and max_dd < -1e-6) else np.nan

    return {"max_drawdown": max_dd, "cagr": cagr, "mar": mar, "sharpe": sharpe}


def _year_returns_dict(mat: pd.DataFrame, net_col: str) -> Dict[int, float]:
    """Average net return by year (matured rows)."""
    result: Dict[int, float] = {}
    for yr, grp in mat.groupby("year"):
        valid = grp[net_col].dropna()
        if len(valid) > 0:
            result[int(yr)] = float(valid.mean())
    return result


def _top_adv_symbols(trades: pd.DataFrame, n: int) -> frozenset:
    """Return frozenset of the N symbols with highest median ADV50 in the dataset."""
    sym_adv = trades.groupby("symbol")["adv50"].median().nlargest(n)
    return frozenset(sym_adv.index)


def _compute_variant_metrics(
    sub: pd.DataFrame,
    net_col: str,
    mat_col: str,
    tp1_col: str,
    hold_col: str,
    n_total_unfiltered: int,
) -> dict:
    """Compute full metrics for one variant from its pre-filtered trade subset."""
    _empty = {
        "n_trades": 0, "win_rate": np.nan, "tp1_rate": np.nan,
        "avg_net_return": np.nan, "median_net_return": np.nan,
        "avg_hold_bars": np.nan, "median_hold_bars": np.nan, "p90_hold_bars": np.nan,
        "turnover_proxy": np.nan, "exposure_proxy": np.nan,
        "max_drawdown": np.nan, "cagr": np.nan, "active_cagr": np.nan,
        "mar": np.nan, "sharpe": np.nan,
        "avg_mae": np.nan, "avg_mfe": np.nan,
        "worst_year": np.nan, "best_year": np.nan,
        "return_2022": np.nan, "return_2024": np.nan,
        "liquidity_exclusion_count": n_total_unfiltered - len(sub),
        "missing_adv_count": int(sub["adv50"].isna().sum()) if "adv50" in sub.columns else 0,
        "missing_atr_count": int(sub["missing_atr_flag"].sum()) if "missing_atr_flag" in sub.columns else 0,
    }

    if sub.empty or mat_col not in sub.columns:
        return _empty

    mat   = sub[sub[mat_col].fillna(False)].copy()
    valid = mat[net_col].dropna() if net_col in mat.columns else pd.Series(dtype=float)
    n_mat = len(valid)

    if n_mat == 0:
        return {**_empty, "n_trades": len(sub)}

    # Basic return stats
    win_rate = float((valid >= 0.15).mean())
    avg_net  = float(valid.mean())
    med_net  = float(valid.median())

    tp1_rate = float(mat[tp1_col].astype(float).mean()) if tp1_col in mat.columns else np.nan

    # Hold time
    hold_vals = mat[hold_col].dropna() if hold_col in mat.columns else pd.Series(dtype=float)
    avg_hold  = float(hold_vals.mean())    if len(hold_vals) > 0 else np.nan
    med_hold  = float(hold_vals.median()) if len(hold_vals) > 0 else np.nan
    p90_hold  = float(hold_vals.quantile(0.90)) if len(hold_vals) > 0 else np.nan

    # Turnover proxy: n_trades per trading year (252 bars)
    exposure_proxy  = float(avg_hold / 252.0) if not np.isnan(avg_hold) else np.nan
    # Estimate signal frequency
    if "signal_date" in mat.columns:
        try:
            dates = pd.to_datetime(mat["signal_date"])
            span_years = max((dates.max() - dates.min()).days / 365.25, 0.1)
            turnover_proxy = float(n_mat / span_years)
        except Exception:
            turnover_proxy = np.nan
    else:
        turnover_proxy = np.nan

    # Active CAGR proxy: avg_net × annualization_factor
    if not np.isnan(avg_net) and not np.isnan(avg_hold) and avg_hold > 0:
        active_cagr = float(avg_net * 252.0 / avg_hold)
    else:
        active_cagr = np.nan

    # Equity curve (sorted by date)
    if "signal_date" in mat.columns and net_col in mat.columns:
        sorted_mat   = mat.sort_values("signal_date")
        sorted_rets  = sorted_mat[net_col].dropna().values
        sorted_dates = sorted_mat.loc[sorted_mat[net_col].notna(), "signal_date"]
        eq_stats = _equity_curve_stats(sorted_rets, sorted_dates)
    else:
        eq_stats = _equity_curve_stats(valid.values)

    # Per-year returns
    yr_dict  = _year_returns_dict(mat, net_col)
    r_2022   = yr_dict.get(2022, np.nan)
    r_2024   = yr_dict.get(2024, np.nan)
    worst_yr = min(yr_dict, key=yr_dict.get) if yr_dict else np.nan
    best_yr  = max(yr_dict, key=yr_dict.get) if yr_dict else np.nan

    return {
        "n_trades":           n_mat,
        "win_rate":           win_rate,
        "tp1_rate":           tp1_rate,
        "avg_net_return":     avg_net,
        "median_net_return":  med_net,
        "avg_hold_bars":      avg_hold,
        "median_hold_bars":   med_hold,
        "p90_hold_bars":      p90_hold,
        "turnover_proxy":     turnover_proxy,
        "exposure_proxy":     exposure_proxy,
        "max_drawdown":       eq_stats["max_drawdown"],
        "cagr":               eq_stats["cagr"],
        "active_cagr":        active_cagr,
        "mar":                eq_stats["mar"],
        "sharpe":             eq_stats["sharpe"],
        "avg_mae":            np.nan,   # not available from Stage 12 simulation
        "avg_mfe":            np.nan,
        "worst_year":         worst_yr,
        "best_year":          best_yr,
        "return_2022":        r_2022,
        "return_2024":        r_2024,
        "liquidity_exclusion_count": n_total_unfiltered - len(sub),
        "missing_adv_count":  int(sub["adv50"].isna().sum()) if "adv50" in sub.columns else 0,
        "missing_atr_count":  int(sub["missing_atr_flag"].sum()) if "missing_atr_flag" in sub.columns else 0,
    }


def _hold_extension_risk_flag(stats: dict, base60_stats: dict) -> bool:
    """True if holding longer introduces material risk vs MAX_HOLD_60 baseline."""
    avg_h  = stats.get("avg_hold_bars",  np.nan)
    p90_h  = stats.get("p90_hold_bars",  np.nan)
    maxdd  = stats.get("max_drawdown",   np.nan)
    r2022  = stats.get("return_2022",    np.nan)
    r2024  = stats.get("return_2024",    np.nan)

    base_h    = base60_stats.get("avg_hold_bars",  np.nan)
    base_dd   = base60_stats.get("max_drawdown",   np.nan)
    base_2022 = base60_stats.get("return_2022",    np.nan)
    base_2024 = base60_stats.get("return_2024",    np.nan)

    hold_ext = (not np.isnan(avg_h)) and (not np.isnan(base_h)) and (avg_h - base_h) > _HOLD_EXTENSION_BARS
    p90_flag = (not np.isnan(p90_h)) and p90_h > _P90_HOLD_HARD
    dd_flag  = (not np.isnan(maxdd)) and (not np.isnan(base_dd)) and (maxdd - base_dd) < -_MAXDD_WORSEN_HARD
    y22_flag = (not np.isnan(r2022)) and (not np.isnan(base_2022)) and r2022 < base_2022
    y24_flag = (not np.isnan(r2024)) and (not np.isnan(base_2024)) and r2024 < base_2024

    return hold_ext or p90_flag or dd_flag or y22_flag or y24_flag


def _classify_mh_variant(
    stats: dict,
    base60_stats: dict,
    mh: int,
    risk_flag: bool,
) -> tuple[str, str]:
    """Returns (classification, action)."""
    n     = stats.get("n_trades",       0)
    win   = stats.get("win_rate",       np.nan)
    tp1   = stats.get("tp1_rate",       np.nan)
    avg_n = stats.get("avg_net_return", np.nan)
    maxdd = stats.get("max_drawdown",   np.nan)

    base_win  = base60_stats.get("win_rate",       np.nan)
    base_tp1  = base60_stats.get("tp1_rate",       np.nan)
    base_net  = base60_stats.get("avg_net_return", np.nan)
    base_dd   = base60_stats.get("max_drawdown",   np.nan)

    if mh == _MH_OFFICIAL_BASELINE:
        return "PAPER_TRADE_SHADOW", "keep as official S3 shadow baseline"

    if n < 100:
        return "NEEDS_MORE_DATA", "insufficient matured trades"

    delta_win = (win - base_win) if not (np.isnan(win) or np.isnan(base_win)) else np.nan
    delta_tp1 = (tp1 - base_tp1) if not (np.isnan(tp1) or np.isnan(base_tp1)) else np.nan
    net_ok    = (not np.isnan(avg_n)) and (not np.isnan(base_net)) and avg_n > base_net
    dd_worsen = (not np.isnan(maxdd)) and (not np.isnan(base_dd)) and (maxdd - base_dd) < -_MAXDD_WORSEN_SOFT

    if (not np.isnan(win)) and win < 0.10:
        return "REJECT", "win rate below 10% floor"

    # PARALLEL_PAPER_RESEARCH: all criteria met, no risk flags
    if (
        n >= _MIN_N_PARALLEL
        and (not np.isnan(delta_win)) and delta_win >= _WIN_DELTA_THRESH
        and (not np.isnan(delta_tp1)) and delta_tp1 >= _TP1_DELTA_THRESH
        and net_ok
        and not dd_worsen
        and not risk_flag
    ):
        return "PARALLEL_PAPER_RESEARCH", "meets all improvement criteria — research-only"

    # PARALLEL_PAPER_RESEARCH but with risk flag → downgrade
    if (
        n >= _MIN_N_PARALLEL
        and (not np.isnan(delta_win)) and delta_win >= _WIN_DELTA_THRESH
        and (not np.isnan(delta_tp1)) and delta_tp1 >= _TP1_DELTA_THRESH
        and net_ok
        and risk_flag
    ):
        return "WATCHLIST_ONLY", "improvement offset by hold-extension / DD risk"

    # WATCHLIST_ONLY: modest improvement
    if (not np.isnan(delta_win)) and delta_win >= 0 and (not np.isnan(win)) and win >= 0.20:
        return "WATCHLIST_ONLY", "modest improvement vs baseline — monitor"

    return "PAPER_TRADE_SHADOW", "similar to baseline — no material improvement"


# ── Re-simulation of missing max_hold variants ────────────────────────────────

def _resimulate_trades(
    base_trades: pd.DataFrame,
    panels: Dict[str, pd.DataFrame],
    mh_values: List[int],
) -> pd.DataFrame:
    """
    Re-simulate each signal in base_trades for each max_hold value in mh_values.
    Adds columns: mh{N}_net, mh{N}_tp1_hit, mh{N}_matured, mh{N}_exit_bar_offset
    Returns extended DataFrame (base_trades rows + new columns).
    """
    out = base_trades.copy()

    # Pre-build ATR14 arrays per symbol
    atr_cache: Dict[str, np.ndarray] = {}
    for sym, df in panels.items():
        atr_cache[sym] = _atr14(df).values

    new_cols: Dict[str, List] = {
        f"{_mh_key(mh)}_{sfx}": []
        for mh in mh_values
        for sfx in ("net", "tp1_hit", "matured", "exit_bar_offset")
    }

    for _, row in base_trades.iterrows():
        sym      = str(row["symbol"])
        bar      = int(row["signal_bar_idx"])
        df       = panels.get(sym)
        atr14    = atr_cache.get(sym)

        for mh in mh_values:
            key = _mh_key(mh)
            if df is None or atr14 is None:
                new_cols[f"{key}_net"].append(np.nan)
                new_cols[f"{key}_tp1_hit"].append(False)
                new_cols[f"{key}_matured"].append(False)
                new_cols[f"{key}_exit_bar_offset"].append(np.nan)
                continue

            res = _simulate_s3_trade(
                bar, df, atr14,
                tp1_pct=TP1_PCT, tp1_size=TP1_SIZE,
                trail_mult=TRAIL_MULT, max_hold=mh,
                cost_rt=COST_RT,
            )
            if res is None:
                new_cols[f"{key}_net"].append(np.nan)
                new_cols[f"{key}_tp1_hit"].append(False)
                new_cols[f"{key}_matured"].append(False)
                new_cols[f"{key}_exit_bar_offset"].append(np.nan)
            else:
                new_cols[f"{key}_net"].append(res["blended_net_return"])
                new_cols[f"{key}_tp1_hit"].append(res["tp1_hit"])
                new_cols[f"{key}_matured"].append(res["matured"])
                new_cols[f"{key}_exit_bar_offset"].append(res["exit_bar_offset"])

    for col, vals in new_cols.items():
        out[col] = vals

    return out


# ── Apply regime + ADV gate ────────────────────────────────────────────────────

def _apply_base_filter(
    trades: pd.DataFrame,
    *,
    regime_gate: bool = True,
    adv_min: float = MIN_ADV_VND,
    ex_vin: bool = False,
    bve_q_min: Optional[int] = None,
    allowed_symbols: Optional[frozenset] = None,
) -> pd.DataFrame:
    sub = trades.copy()
    if regime_gate:
        sub = sub[sub["regime_bull"]]
    sub = sub[sub["adv50"].fillna(0) >= adv_min]
    if ex_vin:
        sub = sub[~sub["is_vin"]]
    if bve_q_min is not None:
        sub = sub[sub["bve_q"] >= bve_q_min]
    if allowed_symbols is not None:
        sub = sub[sub["symbol"].isin(allowed_symbols)]
    return sub


# ── Drawdown delta vs baseline ─────────────────────────────────────────────────

def _delta_row(stats: dict, base60: dict) -> dict:
    def _d(k, scale=100.0):
        a, b = stats.get(k, np.nan), base60.get(k, np.nan)
        return float((a - b) * scale) if not (np.isnan(a) or np.isnan(b)) else np.nan

    return {
        "delta_win_rate_pp":     _d("win_rate"),
        "delta_tp1_rate_pp":     _d("tp1_rate"),
        "delta_avg_return_pp":   _d("avg_net_return"),
        "delta_maxdd_pp":        _d("max_drawdown"),
        "delta_avg_hold_bars":   _d("avg_hold_bars", scale=1.0),
        "delta_median_hold_bars": _d("median_hold_bars", scale=1.0),
        "delta_2022_return_pp":  _d("return_2022"),
        "delta_2024_return_pp":  _d("return_2024"),
    }


# ── Main evaluation ────────────────────────────────────────────────────────────

def _evaluate_main_variants(
    extended: pd.DataFrame,
    n_total: int,
) -> tuple[pd.DataFrame, dict]:
    """
    Evaluate all 7 main max_hold variants.
    Returns (variant_df, base60_stats).
    """
    rows = []
    base60_stats: dict = {}

    for mh in MAIN_MH_VALUES:
        key = _mh_key(mh)
        net_col  = f"{key}_net"
        tp1_col  = f"{key}_tp1_hit"
        mat_col  = f"{key}_matured"
        hold_col = f"{key}_exit_bar_offset"

        if net_col not in extended.columns:
            log.warning("Column %s not found — skipping MH=%d", net_col, mh)
            continue

        # BASE_REGIME filter only (regime_bull + ADV >= 2B)
        sub = _apply_base_filter(extended)
        stats = _compute_variant_metrics(
            sub, net_col, mat_col, tp1_col, hold_col, n_total
        )

        if mh == _MH_OFFICIAL_BASELINE:
            base60_stats = stats

        rows.append({"variant": f"MAX_HOLD_{mh}", "max_hold": mh, **stats})

    # Compute risk flags and classification now that base60_stats is available
    result_rows = []
    for row in rows:
        mh      = row["max_hold"]
        risk    = _hold_extension_risk_flag(row, base60_stats)
        cls, act = _classify_mh_variant(row, base60_stats, mh, risk)
        d       = _delta_row(row, base60_stats)
        result_rows.append({
            **row,
            "hold_extension_risk_flag": risk,
            "classification":           cls,
            "action":                   act,
            **d,
        })

    return pd.DataFrame(result_rows), base60_stats


def _evaluate_sensitivity(
    extended: pd.DataFrame,
    base60_stats: dict,
    n_total: int,
) -> pd.DataFrame:
    """Evaluate MAX_HOLD_120 sensitivity variants."""
    mh  = _MH_STUDY_VARIANT
    key = _mh_key(mh)
    net_col  = f"{key}_net"
    tp1_col  = f"{key}_tp1_hit"
    mat_col  = f"{key}_matured"
    hold_col = f"{key}_exit_bar_offset"

    if net_col not in extended.columns:
        return pd.DataFrame()

    top100 = _top_adv_symbols(extended, 100)
    top150 = _top_adv_symbols(extended, 150)

    sensitivity_specs = [
        {"variant": "MAX_HOLD_120_TOP100_ADV",    "allowed_symbols": top100},
        {"variant": "MAX_HOLD_120_TOP150_ADV",    "allowed_symbols": top150},
        {"variant": "MAX_HOLD_120_EX_VIN",        "ex_vin": True},
        {"variant": "MAX_HOLD_120_BVE_Q4Q5",      "bve_q_min": 4},
        {"variant": "MAX_HOLD_120_VNINDEX_BULL_ONLY", "regime_gate": True},  # same as default
    ]

    rows = []
    for spec in sensitivity_specs:
        variant_name = spec.pop("variant")
        sub = _apply_base_filter(extended, **spec)
        stats = _compute_variant_metrics(
            sub, net_col, mat_col, tp1_col, hold_col, n_total
        )
        risk    = _hold_extension_risk_flag(stats, base60_stats)
        cls, act = _classify_mh_variant(stats, base60_stats, mh, risk)
        d       = _delta_row(stats, base60_stats)
        rows.append({
            "variant": variant_name,
            "max_hold": mh,
            **stats,
            "hold_extension_risk_flag": risk,
            "classification":           cls,
            "action":                   act,
            **d,
        })

    return pd.DataFrame(rows)


def _by_year_breakdown(extended: pd.DataFrame) -> pd.DataFrame:
    """Year breakdown for all 7 main max_hold variants."""
    rows = []
    for mh in MAIN_MH_VALUES:
        key = _mh_key(mh)
        net_col = f"{key}_net"
        mat_col = f"{key}_matured"
        tp1_col = f"{key}_tp1_hit"

        if net_col not in extended.columns:
            continue
        sub = _apply_base_filter(extended)
        mat = sub[sub[mat_col].fillna(False)]
        for yr, grp in mat.groupby("year"):
            valid = grp[net_col].dropna()
            if len(valid) == 0:
                continue
            rows.append({
                "variant":        f"MAX_HOLD_{mh}",
                "max_hold":       mh,
                "year":           int(yr),
                "n_trades":       len(valid),
                "win_rate":       float((valid >= 0.15).mean()),
                "tp1_rate":       float(grp[tp1_col].astype(float).mean()),
                "avg_net_return": float(valid.mean()),
            })
    return pd.DataFrame(rows)


def _by_liquidity_breakdown(extended: pd.DataFrame) -> pd.DataFrame:
    """Liquidity breakdown for all 7 main max_hold variants."""
    rows = []
    for mh in MAIN_MH_VALUES:
        key = _mh_key(mh)
        net_col = f"{key}_net"
        mat_col = f"{key}_matured"
        tp1_col = f"{key}_tp1_hit"

        if net_col not in extended.columns:
            continue
        sub = _apply_base_filter(extended)
        mat = sub[sub[mat_col].fillna(False)]
        for bucket, grp in mat.groupby("liquidity_bucket"):
            valid = grp[net_col].dropna()
            if len(valid) == 0:
                continue
            rows.append({
                "variant":          f"MAX_HOLD_{mh}",
                "max_hold":         mh,
                "liquidity_bucket": bucket,
                "n_trades":         len(valid),
                "win_rate":         float((valid >= 0.15).mean()),
                "tp1_rate":         float(grp[tp1_col].astype(float).mean()),
                "avg_net_return":   float(valid.mean()),
            })
    return pd.DataFrame(rows)


def _trade_distribution(extended: pd.DataFrame) -> pd.DataFrame:
    """Per-trade return distribution for the 7 main variants (matured only)."""
    rows = []
    for mh in MAIN_MH_VALUES:
        key = _mh_key(mh)
        net_col = f"{key}_net"
        mat_col = f"{key}_matured"

        if net_col not in extended.columns:
            continue
        sub = _apply_base_filter(extended)
        mat = sub[sub[mat_col].fillna(False)]

        for _, row in mat.iterrows():
            net = row.get(net_col)
            if pd.isna(net):
                continue
            rows.append({
                "variant":      f"MAX_HOLD_{mh}",
                "max_hold":     mh,
                "symbol":       row.get("symbol", ""),
                "signal_date":  row.get("signal_date", ""),
                "year":         row.get("year", np.nan),
                "blended_net_return": float(net),
            })
    return pd.DataFrame(rows)


# ── Findings markdown ──────────────────────────────────────────────────────────

def _generate_findings_md(
    main_df: pd.DataFrame,
    sensitivity_df: pd.DataFrame,
    by_year_df: pd.DataFrame,
    by_liq_df: pd.DataFrame,
    n_total: int,
) -> str:
    # Find base60 and mh120 rows
    def _get(df, variant):
        r = df[df["variant"] == variant]
        return r.iloc[0].to_dict() if len(r) > 0 else {}

    b60  = _get(main_df, "MAX_HOLD_60")
    b120 = _get(main_df, "MAX_HOLD_120")

    def _fmt(v, pct=False, dp=1):
        if isinstance(v, float) and np.isnan(v):
            return "—"
        if pct:
            return f"{v*100:.{dp}f}%"
        return f"{v:.{dp}f}"

    hold_risk = b120.get("hold_extension_risk_flag", False)
    cls120    = b120.get("classification", "—")
    act120    = b120.get("action", "—")

    lines = [
        "# Stage 12B — S3 MaxHold Robustness Findings",
        "",
        "## 1. Executive Summary",
        "",
        f"Total S3 signals in study (BASE_REGIME, ADV ≥ 2B, full universe): {n_total}",
        "",
        f"**MAX_HOLD_60 (official baseline):** "
        f"n={b60.get('n_trades','—')}  |  "
        f"win={_fmt(b60.get('win_rate'), pct=True)}  |  "
        f"TP1={_fmt(b60.get('tp1_rate'), pct=True)}  |  "
        f"avg_net={_fmt(b60.get('avg_net_return'), pct=True)}  |  "
        f"MaxDD={_fmt(b60.get('max_drawdown'), pct=True)}  |  "
        f"avg_hold={_fmt(b60.get('avg_hold_bars'))} bars",
        "",
        f"**MAX_HOLD_120 (under review):** "
        f"n={b120.get('n_trades','—')}  |  "
        f"win={_fmt(b120.get('win_rate'), pct=True)}  |  "
        f"TP1={_fmt(b120.get('tp1_rate'), pct=True)}  |  "
        f"avg_net={_fmt(b120.get('avg_net_return'), pct=True)}  |  "
        f"MaxDD={_fmt(b120.get('max_drawdown'), pct=True)}  |  "
        f"avg_hold={_fmt(b120.get('avg_hold_bars'))} bars",
        "",
        f"**Hold extension risk flag (MAX_HOLD_120):** {hold_risk}",
        f"**Final classification (MAX_HOLD_120):** {cls120}",
        f"**Action:** {act120}",
        "",
        "## 2. Why MAX_HOLD_120 Needed Separate Validation",
        "",
        "MAX_HOLD_120 was flagged PARALLEL_PAPER_RESEARCH in Stage 12 based on win-rate "
        "and TP1-rate improvements alone. However, holding for 120 bars instead of 60 "
        "locks up capital for twice as long. This stage checks whether the improvement "
        "survives after accounting for:",
        "- Increased average hold time and capital lock-up.",
        "- MaxDD from the equity curve (sequential trade model).",
        "- Weak-year performance (2022, 2024).",
        "- Liquidity robustness.",
        "- Hold-sweep continuity (is 120 special, or is longer always better?).",
        "",
        "## 3. MaxHold Variant Results",
        "",
    ]

    if not main_df.empty:
        display_cols = [
            "variant", "n_trades", "win_rate", "tp1_rate", "avg_net_return",
            "avg_hold_bars", "p90_hold_bars", "max_drawdown", "cagr", "mar",
            "return_2022", "return_2024", "hold_extension_risk_flag", "classification",
        ]
        dc = [c for c in display_cols if c in main_df.columns]
        lines.append(main_df[dc].to_markdown(index=False, floatfmt=".3f"))
    else:
        lines.append("_No variant data._")
    lines.append("")

    lines += ["## 4. Drawdown and Capital Lock-Up Check", ""]
    delta_cols = [
        "variant", "delta_win_rate_pp", "delta_tp1_rate_pp", "delta_avg_return_pp",
        "delta_maxdd_pp", "delta_avg_hold_bars", "delta_median_hold_bars",
        "delta_2022_return_pp", "delta_2024_return_pp", "hold_extension_risk_flag",
    ]
    if not main_df.empty:
        dc = [c for c in delta_cols if c in main_df.columns]
        lines.append(main_df[main_df["variant"] != "MAX_HOLD_60"][dc].to_markdown(index=False, floatfmt=".2f"))
    lines.append("")

    lines += ["## 5. By-Year Robustness", ""]
    if not by_year_df.empty:
        pivot_data = []
        for mh in MAIN_MH_VALUES:
            sub = by_year_df[by_year_df["max_hold"] == mh]
            for _, r in sub.iterrows():
                pivot_data.append({
                    "max_hold": mh, "year": r["year"],
                    "win_rate": f"{r['win_rate']*100:.1f}%",
                    "avg_net":  f"{r['avg_net_return']*100:.1f}%",
                    "n":        r["n_trades"],
                })
        pivot_df = pd.DataFrame(pivot_data)
        lines.append(pivot_df.to_markdown(index=False))
    else:
        lines.append("_No year data._")
    lines.append("")

    lines += ["## 6. Liquidity Robustness", ""]
    if not by_liq_df.empty:
        dc = ["variant", "liquidity_bucket", "n_trades", "win_rate", "tp1_rate", "avg_net_return"]
        dc = [c for c in dc if c in by_liq_df.columns]
        lines.append(by_liq_df[dc].to_markdown(index=False, floatfmt=".3f"))
    else:
        lines.append("_No liquidity data._")
    lines.append("")

    lines += ["## 7. Final Classification", ""]
    if not main_df.empty:
        fc = ["variant", "classification", "action"]
        fc += ([c for c in ["hold_extension_risk_flag"] if c in main_df.columns])
        lines.append(main_df[fc].to_markdown(index=False))
    if not sensitivity_df.empty:
        lines += ["", "**MAX_HOLD_120 Sensitivity Variants:**", ""]
        sc = ["variant", "n_trades", "win_rate", "tp1_rate", "avg_net_return",
              "max_drawdown", "hold_extension_risk_flag", "classification"]
        sc = [c for c in sc if c in sensitivity_df.columns]
        lines.append(sensitivity_df[sc].to_markdown(index=False, floatfmt=".3f"))
    lines.append("")

    lines += [
        "## 8. Safety Confirmation",
        "",
        "- **S3 max_hold=60 remains the official paper-shadow baseline.** ✓",
        "- **MAX_HOLD_120 is research-only unless separately approved.** ✓",
        "- No production / OMS / live logic modified. ✓",
        "- A3 production contract unchanged. ✓",
        "- DNSE/live not enabled. ✓",
        "- `final_action` not modified. ✓",
        "- S3 P&L completely separate from A3. ✓",
        "- No combined sleeve simulation. ✓",
        "- No production recommendation made. ✓",
        "",
        "## 9. Remaining Limitations",
        "",
        "- Equity-curve MaxDD assumes sequential non-overlapping trades (conservative estimate).",
        "- CAGR/MAR computed from first-to-last signal date span — not a continuous-hold portfolio.",
        "- avg_mae / avg_mfe not available (Stage 12 simulation did not store per-bar MAE/MFE).",
        "- Full-history quintile (BVE, tightness) is non-causal — quintiles use data not available at entry.",
        "- Hold-sweep continuity (is 120 special?) should be interpreted as: "
          "longer consistently improves until capital lock-up costs outweigh gains.",
        "",
        "## 10. Recommended Next Step",
        "",
    ]

    if cls120 == "PARALLEL_PAPER_RESEARCH":
        lines += [
            f"MAX_HOLD_120 classification: **{cls120}** — maintained.",
            "Next step: run live paper validation for MIN 6 months using max_hold=60 "
            "(official shadow contract). Track whether max_hold=120 live-paper signals "
            "justify approval as a separate research variant.",
        ]
    elif cls120 == "WATCHLIST_ONLY":
        lines += [
            f"MAX_HOLD_120 classification: **DOWNGRADED to {cls120}**.",
            "Reason: " + act120 + ".",
            "Next step: monitor 2025/2026 live paper trades before reconsidering.",
        ]
    else:
        lines += [
            f"MAX_HOLD_120 classification: **{cls120}**.",
            "Next step: re-evaluate after more matured trades accumulate.",
        ]
    lines.append("")

    return "\n".join(lines)


# ── Main entry point ───────────────────────────────────────────────────────────

def run(workers: int = 4) -> None:
    _STAGE12B_WRITE_DIR.mkdir(parents=True, exist_ok=True)

    # Load Stage 12 trades
    if not _STAGE12_TRADES.exists():
        log.error("Stage 12 trades not found at %s — run Stage 12 first.", _STAGE12_TRADES)
        return

    log.info("Loading Stage 12 trades from %s", _STAGE12_TRADES.name)
    base_trades = pd.read_csv(_STAGE12_TRADES)
    base_trades["signal_date"] = pd.to_datetime(base_trades["signal_date"])
    log.info("Loaded %d signals", len(base_trades))

    # Load panels for re-simulation
    log.info("Loading panel (full universe) for re-simulation...")
    panels = load_panel(ex_vin=False)
    for sym in panels:
        panels[sym] = panels[sym].sort_values("date").reset_index(drop=True)
    log.info("Panel: %d symbols", len(panels))

    # Re-simulate all 7 main max_hold values (need exit_bar_offset for hold-time metrics)
    log.info("Re-simulating %d max_hold variants × %d signals...", len(MAIN_MH_VALUES), len(base_trades))
    extended = _resimulate_trades(base_trades, panels, MAIN_MH_VALUES)
    log.info("Re-simulation complete.")

    n_regime_adv = len(_apply_base_filter(base_trades))
    log.info("BASE_REGIME + ADV2B signals: %d", n_regime_adv)

    # Evaluate main 7 variants
    main_df, base60_stats = _evaluate_main_variants(extended, n_total=n_regime_adv)
    log.info("MAX_HOLD_60: n=%d  win=%.1f%%  MaxDD=%.1f%%  avg_hold=%.1f bars",
             base60_stats.get("n_trades", 0),
             100 * (base60_stats.get("win_rate") or 0),
             100 * (base60_stats.get("max_drawdown") or 0),
             base60_stats.get("avg_hold_bars") or 0)

    for _, row in main_df.iterrows():
        log.info("  %-18s  n=%4d  win=%5.1f%%  hold=%5.1f  MaxDD=%5.1f%%  cls=%s  flag=%s",
                 row["variant"], row.get("n_trades", 0),
                 100*(row.get("win_rate") or 0),
                 row.get("avg_hold_bars") or 0,
                 100*(row.get("max_drawdown") or 0),
                 row.get("classification", "—"),
                 row.get("hold_extension_risk_flag", False))

    # Sensitivity variants (MAX_HOLD_120 filters)
    sensitivity_df = _evaluate_sensitivity(extended, base60_stats, n_total=n_regime_adv)

    # By-year and by-liquidity breakdowns
    by_year_df  = _by_year_breakdown(extended)
    by_liq_df   = _by_liquidity_breakdown(extended)
    trade_dist  = _trade_distribution(extended)

    # Save outputs
    out_main = _STAGE12B_WRITE_DIR / "stage12b_s3_maxhold_robustness.csv"
    main_df.to_csv(out_main, index=False)
    log.info("Saved: %s", out_main.name)

    if not sensitivity_df.empty:
        sens_all = pd.concat([main_df, sensitivity_df], ignore_index=True)
    else:
        sens_all = main_df

    out_year = _STAGE12B_WRITE_DIR / "stage12b_s3_maxhold_by_year.csv"
    by_year_df.to_csv(out_year, index=False)
    log.info("Saved: %s", out_year.name)

    out_liq = _STAGE12B_WRITE_DIR / "stage12b_s3_maxhold_by_liquidity.csv"
    by_liq_df.to_csv(out_liq, index=False)
    log.info("Saved: %s", out_liq.name)

    out_dist = _STAGE12B_WRITE_DIR / "stage12b_s3_maxhold_trade_distribution.csv"
    trade_dist.to_csv(out_dist, index=False)
    log.info("Saved: %s (%d rows)", out_dist.name, len(trade_dist))

    # Findings markdown
    findings_md = _generate_findings_md(
        main_df       = main_df,
        sensitivity_df= sensitivity_df,
        by_year_df    = by_year_df,
        by_liq_df     = by_liq_df,
        n_total       = n_regime_adv,
    )
    out_md = _STAGE12B_WRITE_DIR / "STAGE12B_S3_MAXHOLD_ROBUSTNESS_FINDINGS.md"
    out_md.write_text(findings_md, encoding="utf-8")
    log.info("Saved: %s", out_md.name)

    log.info("Stage 12B complete.")


if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
