"""Trade collection, TSA overlays, and metrics for 2-cloud × Trend Speed research."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

REPO = Path(__file__).resolve().parents[3]

from scripts.research.dual_cloud_accumulation_wyckoff.panel_utils import (
    A3_FAST,
    A3_SLOW,
    COST_BPS,
    MIN_ADV_VND,
    MIN_HISTORY,
    S3_FAST,
    S3_SLOW,
    cloud_signal,
    load_panel,
    load_vnindex_regime,
)
from scripts.research.dual_cloud_accumulation_wyckoff.stage12_s3_shadow_contract_validation import (
    MAX_HOLD as S3_MAX_HOLD,
    TP1_PCT,
    TP1_SIZE,
    TRAIL_MULT as S3_TRAIL_MULT,
    _atr14,
    _liq_bucket,
    _simulate_s3_trade,
)
from scripts.research.dual_cloud_accumulation_wyckoff.stage13_combined_sleeve_simulation import (
    A3_MAX_HOLD,
    A3_T2_PULLBACK,
    A3_T2_WINDOW,
    A3_TRAIL_MULT,
    _simulate_a3_trade_blended,
)
from src.research.indicators.trend_speed_analyzer import compute_tsa_features

log = logging.getLogger(__name__)

OUT_DIR = REPO / "outputs" / "research" / "trend_speed_2cloud"
BREADTH_CSV = REPO / "data" / "research" / "portfolio_optimization" / "missing_work" / "regime_decomposition_breadth.csv"
COST_RT = COST_BPS / 10_000.0
DAILY_SLOTS = 5
VIN_SYMBOLS = frozenset({"VIC", "VHM", "VRE"})

ENTRY_FILTERS: Dict[str, Callable[[pd.Series], bool]] = {
    "A0_baseline": lambda r: True,
    "A1_trendspeed_pos": lambda r: bool(r.get("tsa_trendspeed_positive")),
    "A2_speed_pos": lambda r: bool(r.get("tsa_speed_positive")),
    "A3_dyn_bull": lambda r: bool(r.get("tsa_dyn_trend_bull")),
    "A4_trendspeed_slope": lambda r: bool(r.get("tsa_trendspeed_positive")) and float(r.get("tsa_trendspeed_slope_3", 0) or 0) > 0,
    "A5_norm_50": lambda r: float(r.get("tsa_norm_speed", 0) or 0) >= 0.50,
    "A6_norm_60": lambda r: float(r.get("tsa_norm_speed", 0) or 0) >= 0.60,
    "A7_bull_turn_5": lambda r: bool(r.get("tsa_bull_turn_5")),
    "A8_trendspeed_soft": lambda r: True,  # same as baseline; manual-review flag when false
}

T2_GATES: Dict[str, Callable[[pd.Series], bool]] = {
    "C0_baseline": lambda r: True,
    "C1_trendspeed_pos": lambda r: bool(r.get("tsa_trendspeed_positive")),
    "C2_speed_pos": lambda r: bool(r.get("tsa_speed_positive")),
    "C3_trendspeed_slope": lambda r: float(r.get("tsa_trendspeed_slope_3", 0) or 0) >= 0,
    "C4_norm_40": lambda r: float(r.get("tsa_norm_speed", 0) or 0) >= 0.40,
    "C5_no_bear_turn_5": lambda r: not bool(r.get("tsa_bear_turn_5")),
    "C6_no_deterioration": lambda r: not bool(r.get("tsa_speed_deterioration")),
}

T2_GATE_FEATURE_COL: Dict[str, str] = {
    "C0_baseline": "tsa_trendspeed_slope_3",
    "C1_trendspeed_pos": "tsa_trendspeed",
    "C2_speed_pos": "tsa_speed",
    "C3_trendspeed_slope": "tsa_trendspeed_slope_3",
    "C4_norm_40": "tsa_norm_speed",
    "C5_no_bear_turn_5": "tsa_bear_turn_5",
    "C6_no_deterioration": "tsa_speed_deterioration",
}

# Phase36 / scan rank not present on OHLCV panel — ranking modes 3–4 skipped unless added later.
HAS_EXISTING_A3_RANK = False


def load_breadth() -> pd.Series:
    df = pd.read_csv(BREADTH_CSV, parse_dates=["date"])
    return pd.Series(df["a3_breadth"].values, index=df["date"], name="a3_breadth")


def _zscore_rolling(s: pd.Series, window: int = 252) -> pd.Series:
    mu = s.rolling(window, min_periods=60).mean()
    sd = s.rolling(window, min_periods=60).std(ddof=1)
    return (s - mu) / sd.replace(0, np.nan)


def _pctile_rolling(s: pd.Series, window: int = 252) -> pd.Series:
    return s.rolling(window, min_periods=60).apply(
        lambda x: scipy_stats.percentileofscore(x, x[-1], kind="rank") / 100.0
        if len(x) >= 60 and not np.isnan(x[-1])
        else np.nan,
        raw=True,
    )


def attach_tsa_ranks(tsa: pd.DataFrame) -> pd.DataFrame:
    t = tsa.copy()
    t["tsa_rank_1"] = _zscore_rolling(t["tsa_trendspeed"])
    t["tsa_rank_2"] = _pctile_rolling(t["tsa_norm_speed"])
    t["tsa_rank_3"] = _zscore_rolling(t["tsa_trendspeed_slope_3"])
    t["tsa_rank_composite"] = (
        0.4 * t["tsa_rank_1"].fillna(0)
        + 0.4 * t["tsa_rank_2"].fillna(0)
        + 0.2 * t["tsa_rank_3"].fillna(0)
    )
    return t


def _t2_features_at_bar(sym_df: pd.DataFrame, bar: int) -> pd.Series:
    cols = [c for c in sym_df.columns if c.startswith("tsa_")]
    return sym_df.iloc[bar][cols]


def _find_t2_fill_bar(
    entry_bar: int,
    t1_entry: float,
    low_arr: np.ndarray,
    n: int,
) -> Optional[int]:
    thresh = t1_entry * (1.0 - A3_T2_PULLBACK)
    for i in range(1, A3_T2_WINDOW + 1):
        bar = entry_bar + i
        if bar >= n:
            break
        if low_arr[bar] <= thresh:
            return bar
    return None


def simulate_a3_trade_exact(
    signal_bar: int,
    sym_df: pd.DataFrame,
    atr14_arr: np.ndarray,
    breadth_by_date: pd.Series,
    *,
    t2_gate_fn: Callable[[pd.Series], bool] | None = None,
    t2_gate_variant: str = "C0_baseline",
) -> Optional[dict]:
    """
    Exact A3 T1/T2 path: T2 gate + breadth evaluated at T2 fill bar only.
    If pullback occurs but gate/breadth blocks T2 -> T1-only return (no scaling).
    """
    n = len(sym_df)
    entry_bar = signal_bar + 1
    if entry_bar >= n:
        return None

    open_arr = sym_df["open"].values
    low_arr = sym_df["low"].values
    dates = sym_df["date"].values

    t1_entry = float(open_arr[entry_bar])
    if t1_entry <= 0 or np.isnan(t1_entry):
        return None

    t1 = _simulate_s3_trade(
        signal_bar,
        sym_df,
        atr14_arr,
        tp1_pct=TP1_PCT,
        tp1_size=TP1_SIZE,
        trail_mult=A3_TRAIL_MULT,
        max_hold=A3_MAX_HOLD,
        cost_rt=COST_RT,
    )
    if t1 is None:
        return None

    t1_net = float(t1.get("blended_net_return", np.nan))
    t2_fill_bar = _find_t2_fill_bar(entry_bar, t1_entry, low_arr, n)
    pullback_occurred = t2_fill_bar is not None

    t2_gate_pass = True
    t2_blocked_by_tsa = False
    t2_blocked_by_breadth = False
    gate_feat_val = np.nan
    t2_filled = False
    t2_net = np.nan
    t2_tp1_hit = False
    t2_fill_date = pd.NaT
    t2_fill_price = np.nan

    if pullback_occurred:
        fill_date = pd.Timestamp(dates[t2_fill_bar])
        br_at_fill = float(
            breadth_by_date.reindex([fill_date], method="ffill").iloc[-1]
        ) if len(breadth_by_date) else np.nan
        t2_blocked_by_breadth = (not np.isnan(br_at_fill)) and br_at_fill < 0.40

        feat = _t2_features_at_bar(sym_df, t2_fill_bar)
        gate_fn = t2_gate_fn if t2_gate_fn is not None else (lambda _: True)
        t2_gate_pass = bool(gate_fn(feat))
        feat_col = T2_GATE_FEATURE_COL.get(t2_gate_variant, "tsa_trendspeed_slope_3")
        gate_feat_val = feat.get(feat_col, np.nan)

        t2_blocked_by_tsa = t2_blocked_by_breadth or (not t2_gate_pass)

        if not t2_blocked_by_tsa:
            bars_used = (t2_fill_bar + 1) - entry_bar
            t2_max_hold = A3_MAX_HOLD - bars_used
            if t2_max_hold > 0 and t2_fill_bar + 1 < n:
                t2 = _simulate_s3_trade(
                    t2_fill_bar,
                    sym_df,
                    atr14_arr,
                    tp1_pct=TP1_PCT,
                    tp1_size=TP1_SIZE,
                    trail_mult=A3_TRAIL_MULT,
                    max_hold=t2_max_hold,
                    cost_rt=COST_RT,
                )
                if t2 is not None and not np.isnan(t2.get("blended_net_return", np.nan)):
                    t2_filled = True
                    t2_net = float(t2["blended_net_return"])
                    t2_tp1_hit = bool(t2.get("tp1_hit", False))
                    t2_fill_date = fill_date
                    t2_fill_price = float(open_arr[t2_fill_bar + 1])

    if t2_filled:
        blended_net = 0.5 * t1_net + 0.5 * t2_net
    else:
        blended_net = t1_net

    return {
        "t1_entry": t1_entry,
        "t1_net": t1_net,
        "t2_net": t2_net,
        "blended_net_return": blended_net,
        "t2_filled": t2_filled,
        "t2_pullback_occurred": pullback_occurred,
        "t2_blocked_by_tsa": bool(pullback_occurred and t2_blocked_by_tsa),
        "t2_blocked_by_breadth": bool(pullback_occurred and t2_blocked_by_breadth),
        "t2_fill_bar": int(t2_fill_bar) if t2_fill_bar is not None else np.nan,
        "t2_fill_date": t2_fill_date,
        "t2_fill_price": t2_fill_price,
        "t2_gate_variant": t2_gate_variant,
        "t2_gate_feature_value": gate_feat_val,
        "t1_tp1_hit": bool(t1.get("tp1_hit", False)),
        "t2_tp1_hit": t2_tp1_hit,
        "tp1_hit": bool(t1.get("tp1_hit", False)) or t2_tp1_hit,
        "matured": bool(t1.get("matured", False)),
        "missing_atr_flag": False,
    }


def resimulate_a3_with_t2_gates(
    signals: pd.DataFrame,
    panels: Dict[str, pd.DataFrame],
    breadth: pd.Series,
) -> Dict[str, pd.DataFrame]:
    """Re-run exact A3 sim for each T2 gate variant; returns {variant: trades_df}."""
    out: Dict[str, pd.DataFrame] = {}
    for variant, gate_fn in T2_GATES.items():
        rows: List[dict] = []
        for _, row in signals.iterrows():
            sym = row["symbol"]
            bar = int(row["signal_bar"])
            df = panels.get(sym)
            if df is None:
                continue
            atr = _atr14(df).values
            sim = simulate_a3_trade_exact(
                bar,
                df,
                atr,
                breadth,
                t2_gate_fn=gate_fn,
                t2_gate_variant=variant,
            )
            if sim is None:
                continue
            rows.append({**row.to_dict(), **sim})
        out[variant] = pd.DataFrame(rows)
    return out


def _simulate_exit_overlay(
    signal_bar: int,
    sym_df: pd.DataFrame,
    atr14_arr: np.ndarray,
    overlay: str,
    tp1_pct: float = TP1_PCT,
    tp1_size: float = TP1_SIZE,
    trail_mult: float = A3_TRAIL_MULT,
    max_hold: int = A3_MAX_HOLD,
) -> Optional[dict]:
    """S3-style single-leg sim with optional post-TP1 TSA exit overlays (research)."""
    n = len(sym_df)
    entry_bar = signal_bar + 1
    if entry_bar >= n:
        return None

    open_arr = sym_df["open"].values
    high_arr = sym_df["high"].values
    low_arr = sym_df["low"].values
    close_arr = sym_df["close"].values
    ts = sym_df["tsa_trendspeed"].values if "tsa_trendspeed" in sym_df.columns else np.zeros(n)
    bear_turn = sym_df["tsa_bear_turn"].values if "tsa_bear_turn" in sym_df.columns else np.zeros(n, dtype=bool)
    deterior = sym_df["tsa_speed_deterioration"].values if "tsa_speed_deterioration" in sym_df.columns else np.zeros(n, dtype=bool)

    entry_price = open_arr[entry_bar]
    if entry_price <= 0 or np.isnan(entry_price):
        return None

    atr_val = atr14_arr[signal_bar] if signal_bar < len(atr14_arr) else np.nan
    if np.isnan(atr_val) or atr_val <= 0:
        atr_val = entry_price * 0.02

    tp1_level = entry_price * (1.0 + tp1_pct)
    tp1_sold = False
    highest_close = entry_price
    trail_stop = np.nan
    det_streak = 0
    effective_trail = trail_mult

    exit_price = np.nan
    exit_reason = "max_hold"
    tp1_hit = False

    for i in range(1, max_hold + 1):
        bar = entry_bar + i
        if bar >= n:
            return {"blended_net_return": np.nan, "matured": False, "tp1_hit": tp1_sold, "exit_reason": "immature"}

        bh, bl, bc, bo = high_arr[bar], low_arr[bar], close_arr[bar], open_arr[bar]

        if not tp1_sold:
            if bh >= tp1_level:
                tp1_sold = True
                tp1_hit = True
                highest_close = bc
                effective_trail = trail_mult
                if overlay == "D4" and ts[bar] < 0:
                    effective_trail = 2.0
                trail_stop = highest_close - effective_trail * atr_val
            continue

        if overlay in ("D2", "D3", "D4", "D5") and tp1_sold:
            if overlay == "D2" and bear_turn[bar]:
                exit_price = bo if bo < bc else bc
                exit_reason = "tsa_bear_turn"
                break
            if overlay == "D3":
                det_streak = det_streak + 1 if deterior[bar] else 0
                if det_streak >= 3:
                    exit_price = bo if bo < bc else bc
                    exit_reason = "tsa_deterioration"
                    break
            if overlay == "D4" and ts[bar] < 0:
                effective_trail = 2.0

        if bc > highest_close:
            highest_close = bc
        trail_stop = highest_close - effective_trail * atr_val
        if bl <= trail_stop:
            exit_price = bo if bo <= trail_stop else trail_stop
            exit_reason = "trail"
            break
    else:
        bar = entry_bar + max_hold
        if bar >= n:
            return {"blended_net_return": np.nan, "matured": False, "tp1_hit": tp1_hit, "exit_reason": "immature"}
        exit_price = open_arr[bar]
        exit_reason = "max_hold"

    if tp1_sold:
        r_tp1 = tp1_level / entry_price - 1.0
        r_exit = exit_price / entry_price - 1.0
        gross = tp1_size * r_tp1 + (1.0 - tp1_size) * r_exit
    else:
        gross = exit_price / entry_price - 1.0

    return {
        "blended_net_return": float(gross - COST_RT),
        "matured": True,
        "tp1_hit": tp1_hit,
        "exit_reason": exit_reason,
    }


def collect_trades(
    sleeve: str,
    panels: Dict[str, pd.DataFrame],
    regime_map: pd.Series,
    breadth: pd.Series,
    *,
    ex_vin: bool = True,
) -> pd.DataFrame:
    """Collect baseline cloud signals with TSA features at signal bar."""
    fast, slow = (A3_FAST, A3_SLOW) if sleeve == "A3" else (S3_FAST, S3_SLOW)
    rows: List[dict] = []

    for sym, df in panels.items():
        if len(df) < MIN_HISTORY + slow + 5:
            continue
        if ex_vin and sym in VIN_SYMBOLS:
            continue

        work = df.copy()
        tsa = attach_tsa_ranks(compute_tsa_features(work))
        for c in tsa.columns:
            work[c] = tsa[c].values

        sig, _, _ = cloud_signal(work, fast, slow)
        if sleeve == "S3":
            regime_aligned = regime_map.reindex(work["date"]).ffill().fillna(False).values
            sig = sig & pd.Series(regime_aligned, index=sig.index)

        atr14_arr = _atr14(work).values
        adv_arr = work["adv50"].values if "adv50" in work.columns else np.full(len(work), np.nan)
        dates = work["date"].values

        for bar in np.where(sig.values)[0]:
            adv = float(adv_arr[bar]) if bar < len(adv_arr) else np.nan
            if np.isnan(adv) or adv < MIN_ADV_VND:
                continue

            d = pd.Timestamp(dates[bar])
            if sleeve == "A3":
                regime_ok = bool(regime_map.reindex([d], method="ffill").iloc[-1])
                if not regime_ok:
                    continue
            else:
                regime_ok = bool(regime_map.reindex([d], method="ffill").iloc[-1])

            br_s = breadth.reindex(pd.to_datetime(work["date"])).ffill()
            br = float(br_s.iloc[bar]) if bar < len(br_s) and not np.isnan(br_s.iloc[bar]) else np.nan

            feat = {c: work[c].iloc[bar] for c in tsa.columns}
            feat.update(
                {
                    "tsa_rank_1": work["tsa_rank_1"].iloc[bar],
                    "tsa_rank_2": work["tsa_rank_2"].iloc[bar],
                    "tsa_rank_3": work["tsa_rank_3"].iloc[bar],
                    "tsa_rank_composite": work["tsa_rank_composite"].iloc[bar],
                }
            )

            br_work = breadth.reindex(pd.to_datetime(work["date"])).ffill()

            if sleeve == "A3":
                sim = simulate_a3_trade_exact(
                    int(bar),
                    work,
                    atr14_arr,
                    br_work,
                    t2_gate_fn=T2_GATES["C0_baseline"],
                    t2_gate_variant="C0_baseline",
                )
            else:
                sim = _simulate_s3_trade(
                    int(bar), work, atr14_arr,
                    tp1_pct=TP1_PCT, tp1_size=TP1_SIZE,
                    trail_mult=S3_TRAIL_MULT, max_hold=S3_MAX_HOLD, cost_rt=COST_RT,
                )

            if sim is None:
                continue

            rec = {
                "sleeve": sleeve,
                "symbol": sym,
                "signal_date": d,
                "year": d.year,
                "signal_bar": int(bar),
                "adv50": adv,
                "liquidity_bucket": _liq_bucket(adv),
                "is_vin": sym in VIN_SYMBOLS,
                "regime_bull": regime_ok if sleeve == "A3" else bool(regime_map.reindex([d]).ffill().iloc[-1]),
                "a3_breadth": br,
                "breadth_t2_ok": br >= 0.40 if not np.isnan(br) else True,
                "breadth_review": br < 0.35 if not np.isnan(br) else False,
                **{k: feat[k] for k in feat},
            }
            if sleeve == "A3":
                rec.update(
                    {
                        "t1_net": sim.get("t1_net"),
                        "t2_net": sim.get("t2_net"),
                        "blended_net_return": sim.get("blended_net_return"),
                        "tp1_hit": bool(sim.get("tp1_hit", False)),
                        "t2_filled": bool(sim.get("t2_filled", False)),
                        "t2_pullback_occurred": bool(sim.get("t2_pullback_occurred", False)),
                        "t2_blocked_by_tsa": bool(sim.get("t2_blocked_by_tsa", False)),
                        "t2_blocked_by_breadth": bool(sim.get("t2_blocked_by_breadth", False)),
                        "t2_fill_bar": sim.get("t2_fill_bar"),
                        "t2_fill_date": sim.get("t2_fill_date"),
                        "t2_fill_price": sim.get("t2_fill_price"),
                        "t2_gate_variant": sim.get("t2_gate_variant"),
                        "t2_gate_feature_value": sim.get("t2_gate_feature_value"),
                        "matured": bool(sim.get("matured", False)),
                    }
                )
            else:
                rec.update(
                    {
                        "blended_net_return": sim.get("blended_net_return"),
                        "tp1_hit": bool(sim.get("tp1_hit", False)),
                        "t2_filled": False,
                        "matured": bool(sim.get("matured", False)),
                    }
                )
            rows.append(rec)

    return pd.DataFrame(rows)


def apply_entry_filter(trades: pd.DataFrame, variant: str) -> pd.DataFrame:
    fn = ENTRY_FILTERS[variant]
    if variant == "A8_trendspeed_soft":
        mask = trades.apply(fn, axis=1)
        out = trades[mask].copy()
        out["tsa_manual_review"] = ~trades["tsa_trendspeed_positive"]
        return out
    return trades[trades.apply(fn, axis=1)].copy()


def select_daily_slots(
    trades: pd.DataFrame,
    mode: str,
    slots: int = DAILY_SLOTS,
    *,
    primary_rank_col: str | None = None,
    tiebreak_col: str | None = None,
) -> pd.DataFrame:
    """
    Ranking modes:
      fifo | tsa_composite_only | existing_rank_only | existing_rank_then_tsa_tiebreak
    """
    sub = trades.copy()
    if mode == "fifo":
        sub["_rk"] = sub.groupby("signal_date")["symbol"].rank(method="first")
    elif mode == "tsa_composite_only":
        sub["_rk"] = sub.groupby("signal_date")["tsa_rank_composite"].rank(ascending=False, method="first")
    elif mode == "existing_rank_only":
        if not HAS_EXISTING_A3_RANK or primary_rank_col is None or primary_rank_col not in sub.columns:
            return sub.iloc[0:0]
        sub["_rk"] = sub.groupby("signal_date")[primary_rank_col].rank(ascending=False, method="first")
    elif mode == "existing_rank_then_tsa_tiebreak":
        if not HAS_EXISTING_A3_RANK or primary_rank_col is None or primary_rank_col not in sub.columns:
            return sub.iloc[0:0]
        sub["_rk"] = sub.groupby("signal_date").apply(
            lambda g: g.sort_values(
                [primary_rank_col, tiebreak_col or "tsa_rank_composite"],
                ascending=[False, False],
            ).reset_index(drop=True).index
            + 1,
            include_groups=False,
        )
        # fallback: stable sort per day
        sub = sub.sort_values(["signal_date", primary_rank_col, tiebreak_col or "tsa_rank_composite"], ascending=[True, False, False])
        sub["_rk"] = sub.groupby("signal_date").cumcount() + 1
    else:
        raise ValueError(f"unknown rank mode: {mode}")
    return sub[sub["_rk"] <= slots].drop(columns=["_rk"], errors="ignore")


def trade_metrics(trades: pd.DataFrame) -> dict:
    sub = trades[trades["matured"] == True].copy()  # noqa: E712
    rets = sub["blended_net_return"].dropna()
    if len(rets) == 0:
        return {"n_trades": 0}

    yearly = sub.assign(year=sub["signal_date"].dt.year).groupby("year")["blended_net_return"].mean()
    eq_stats = _equity_from_annual(yearly.to_dict())

    return {
        "n_trades": len(rets),
        "n_signals": len(trades),
        "pct_matured": len(rets) / max(len(trades), 1),
        "cagr": eq_stats["cagr"],
        "mar": eq_stats["mar"],
        "max_drawdown": eq_stats["max_drawdown"],
        "win_rate": float((rets > 0).mean()),
        "tp1_rate": float(sub["tp1_hit"].mean()),
        "avg_r": float(rets.mean()),
        "med_r": float(rets.median()),
        "avg_hold_proxy": float(sub.get("hold_bars", pd.Series([np.nan])).mean()),
        "profit_factor": float(rets[rets > 0].sum() / abs(rets[rets < 0].sum())) if (rets < 0).any() else np.nan,
        "exposure_proxy": len(rets) / max((sub["signal_date"].max() - sub["signal_date"].min()).days / 365.25, 1),
    }


def _equity_from_annual(annual_returns: Dict[int, float]) -> dict:
    if not annual_returns:
        return {"cagr": np.nan, "max_drawdown": np.nan, "mar": np.nan}
    years = sorted(annual_returns.keys())
    rets = [annual_returns[y] for y in years]
    equity = np.cumprod(1.0 + np.clip(rets, -0.999, 10.0))
    peak = np.maximum.accumulate(equity)
    max_dd = float(((equity - peak) / peak).min())
    n = len(years)
    cagr = float(equity[-1] ** (1.0 / n) - 1.0) if n > 0 else np.nan
    mar = cagr / abs(max_dd) if max_dd != 0 else np.nan
    return {"cagr": cagr, "max_drawdown": max_dd, "mar": mar}


def compare_to_baseline(baseline: dict, variant: dict, baseline_trades: pd.DataFrame, variant_trades: pd.DataFrame) -> dict:
    b_m = baseline.get("mar", np.nan)
    v_m = variant.get("mar", np.nan)
    merged = baseline_trades.merge(
        variant_trades[["symbol", "signal_date", "blended_net_return"]],
        on=["symbol", "signal_date"],
        how="outer",
        suffixes=("_b", "_v"),
        indicator=True,
    )
    missed_winners = int(
        ((merged["_merge"] == "left_only") & (merged["blended_net_return_b"] > 0.18)).sum()
    )
    avoided_losers = int(
        ((merged["_merge"] == "left_only") & (merged["blended_net_return_b"] < -0.08)).sum()
    )
    return {
        "delta_mar": v_m - b_m if not (np.isnan(v_m) or np.isnan(b_m)) else np.nan,
        "delta_cagr": variant.get("cagr", np.nan) - baseline.get("cagr", np.nan),
        "delta_max_dd": variant.get("max_drawdown", np.nan) - baseline.get("max_drawdown", np.nan),
        "delta_win_rate": variant.get("win_rate", np.nan) - baseline.get("win_rate", np.nan),
        "delta_tp1_rate": variant.get("tp1_rate", np.nan) - baseline.get("tp1_rate", np.nan),
        "trade_count_retained_pct": len(variant_trades) / max(len(baseline_trades), 1) * 100,
        "missed_winners": missed_winners,
        "avoided_losers": avoided_losers,
    }


def rank_decile_analysis(trades: pd.DataFrame, rank_col: str = "tsa_rank_composite") -> pd.DataFrame:
    sub = trades[trades["matured"] == True].copy()  # noqa: E712
    if sub.empty or rank_col not in sub.columns:
        return pd.DataFrame()
    valid = sub[rank_col].notna()
    sub = sub[valid]
    if len(sub) < 20:
        return pd.DataFrame()
    sub = sub.copy()
    sub["decile"] = pd.qcut(sub[rank_col].rank(method="first"), 10, labels=False) + 1
    rows = []
    decile_means = []
    for d, g in sub.groupby("decile"):
        rets = g["blended_net_return"].dropna()
        sp, _ = scipy_stats.spearmanr(g[rank_col], rets) if len(rets) > 2 else (np.nan, np.nan)
        avg_r = float(rets.mean()) if len(rets) else np.nan
        decile_means.append(avg_r)
        rows.append(
            {
                "rank_col": rank_col,
                "decile": int(d),
                "n": len(rets),
                "avg_return": avg_r,
                "hit_rate": float((rets > 0).mean()) if len(rets) else np.nan,
                "tp1_rate": float(g["tp1_hit"].mean()),
                "spearman_rank_vs_return": float(sp) if sp == sp else np.nan,
            }
        )
    mono = np.nan
    if len(decile_means) >= 3:
        mono, _ = scipy_stats.spearmanr(range(1, len(decile_means) + 1), decile_means)
    for r in rows:
        r["decile_monotonicity_spearman"] = float(mono) if mono == mono else np.nan
    return pd.DataFrame(rows)


def classify_variant(baseline: dict, variant: dict, cmp: dict) -> str:
    mar_delta = cmp.get("delta_mar", 0) or 0
    dd_improve = baseline.get("max_drawdown", 0) and variant.get("max_drawdown", 0)
    dd_pct = (variant.get("max_drawdown", 0) - baseline.get("max_drawdown", 0)) / abs(baseline.get("max_drawdown", 0.01))
    retained = cmp.get("trade_count_retained_pct", 0) or 0
    if retained < 70 and mar_delta > 0:
        return "REJECT"
    if mar_delta >= 0.05 or dd_pct <= -0.10:
        if retained >= 70:
            return "APPROVE_FOR_SHADOW"
    if mar_delta > 0 or dd_pct < 0:
        return "WATCHLIST_ONLY"
    return "REJECT"
