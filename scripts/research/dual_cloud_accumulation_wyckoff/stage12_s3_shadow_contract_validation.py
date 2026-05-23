"""Stage 12 — S3 Standalone Paper-Shadow Contract Validation.

Evaluates the S3 EMA21/55 signal universe as a standalone paper-shadow contract:
  Entry    = open[t+1]
  TP1      = +18% from entry (exits 50% of position)
  Trail    = 3.5× ATR14 on remainder (checked bar-by-bar from t+2 onward)
  MaxHold  = 60 bars hard stop on full/remainder position
  Gate     = VNINDEX regime (EMA21/55 bullish) + ADV50 ≥ 2 B VND

Research questions:
1. What is the base-rate performance of S3 paper-shadow contracts?
2. Do BVE / tightness observation filters improve TP1 rate or reduce drawdown?
3. Does higher liquidity filter change outcomes?
4. Do 2022 / 2024 bear-year returns suggest structural risk?

Safety invariants:
- MAX_HOLD_REJECTED = 250  is defined here for completeness; it is NOT a candidate variant.
- S3 P&L is completely separate from A3.
- No modification to A3 production contract.
- `final_action` not touched anywhere in this file.
- OMS / live / DNSE untouched.
- All output fields are observation-only.

OBSERVATION / RESEARCH ONLY.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from scripts.research.dual_cloud_accumulation_wyckoff.panel_utils import (
    COST_BPS,
    MIN_ADV_VND,
    OUT_DIR,
    cloud_signal,
    load_panel,
    load_vnindex_regime,
)
from scripts.research.dual_cloud_accumulation_wyckoff.features import (
    bo_vol_expansion,
    price_tightness_20,
)

log = logging.getLogger(__name__)

# ── Safety constants ────────────────────────────────────────────────────────────
_STAGE12_WRITE_DIR: Path = OUT_DIR

_OMS_SAFE_PATHS: frozenset[str] = frozenset({
    str(REPO / "data" / "decision" / "daily_scan.json"),
    str(REPO / "data" / "decision" / "daily_scan.md"),
    str(REPO / "data" / "decision" / "allocation_plan.json"),
    str(REPO / "data" / "state" / "regime_state.json"),
    str(REPO / "data" / "raw" / "current_positions_derived.json"),
    str(REPO / "data" / "raw" / "current_positions_digest.md"),
})

# ── Contract parameters ─────────────────────────────────────────────────────────
TP1_PCT           = 0.18     # +18% TP1 target
TP1_SIZE          = 0.50     # 50% of position exited at TP1
TRAIL_MULT        = 3.5      # remainder trailed at 3.5× ATR14
MAX_HOLD          = 60       # hard stop after 60 bars
MAX_HOLD_REJECTED = 250      # defined for reference; NOT used as a candidate variant
COST_RT           = COST_BPS / 10_000.0  # round-trip cost fraction (40 bps)

# ── S3 EMAs ────────────────────────────────────────────────────────────────────
_S3_FAST = 21
_S3_SLOW = 55

# ── VIN symbols ────────────────────────────────────────────────────────────────
_VIN_SYMBOLS: frozenset[str] = frozenset({"VIC", "VHM", "VRE"})

# ── Liquidity bucket thresholds ────────────────────────────────────────────────
_LIQ_LOW_MAX = 5_000_000_000    # < 5 B VND → "low"
_LIQ_MID_MAX = 20_000_000_000   # 5–20 B VND → "mid"; ≥20 B → "high"

# ── Classification thresholds ───────────────────────────────────────────────────
_MIN_N_PAPER_RESEARCH = 300    # preferred minimum for PARALLEL_PAPER_RESEARCH
_MIN_N_WATCHLIST      = 100    # below 100 → NEEDS_MORE_DATA
_WIN_DELTA_THRESH     = 0.05   # ≥5 pp win-rate delta for PARALLEL_PAPER_RESEARCH
_TP1_DELTA_THRESH     = 0.03   # ≥3 pp TP1-rate delta for PARALLEL_PAPER_RESEARCH

# ── Contract simulation variants ───────────────────────────────────────────────
# (key, tp1_pct, trail_mult, max_hold)
_CONTRACT_VARIANTS: List[Tuple[str, float, float, int]] = [
    ("base",     0.18, 3.5,  60),
    ("tp1_22",   0.22, 3.5,  60),
    ("tp1_15",   0.15, 3.5,  60),
    ("trail_25", 0.18, 2.5,  60),
    ("trail_45", 0.18, 4.5,  60),
    ("mh_30",    0.18, 3.5,  30),
    ("mh_120",   0.18, 3.5, 120),
]

# ── Variant specs (filter + contract) ──────────────────────────────────────────
_VARIANT_SPECS: List[dict] = [
    # Baselines
    {"name": "BASE_NO_REGIME",        "regime_gate": False, "adv_min": 2e9,  "contract_key": "base"},
    {"name": "BASE_REGIME",           "regime_gate": True,  "adv_min": 2e9,  "contract_key": "base"},
    # BVE observation filters
    {"name": "BVE_Q45",               "regime_gate": True,  "adv_min": 2e9,  "bve_q_min": 4, "contract_key": "base"},
    {"name": "BVE_Q5",                "regime_gate": True,  "adv_min": 2e9,  "bve_q_min": 5, "contract_key": "base"},
    # Tightness observation filters (Q5 = most compressed)
    {"name": "TPBCQ_Q45",             "regime_gate": True,  "adv_min": 2e9,  "tpbcq_q_min": 4, "contract_key": "base"},
    {"name": "TPBCQ_Q5",              "regime_gate": True,  "adv_min": 2e9,  "tpbcq_q_min": 5, "contract_key": "base"},
    # Combo filters
    {"name": "BVE_TPBCQ_COMBO_Q45",   "regime_gate": True,  "adv_min": 2e9,  "bve_q_min": 4, "tpbcq_q_min": 4, "contract_key": "base"},
    {"name": "BVE_TPBCQ_COMBO_Q5",    "regime_gate": True,  "adv_min": 2e9,  "bve_q_min": 5, "tpbcq_q_min": 5, "contract_key": "base"},
    # ADV liquidity filters
    {"name": "ADV5B",                  "regime_gate": True,  "adv_min": 5e9,  "contract_key": "base"},
    {"name": "ADV10B",                 "regime_gate": True,  "adv_min": 10e9, "contract_key": "base"},
    {"name": "BVE_Q45_ADV5B",         "regime_gate": True,  "adv_min": 5e9,  "bve_q_min": 4, "contract_key": "base"},
    {"name": "BVE_Q45_ADV10B",        "regime_gate": True,  "adv_min": 10e9, "bve_q_min": 4, "contract_key": "base"},
    # Universe variants
    {"name": "EX_VIN_BASE",           "regime_gate": True,  "adv_min": 2e9,  "ex_vin": True, "contract_key": "base"},
    {"name": "EX_VIN_BVE_Q45",        "regime_gate": True,  "adv_min": 2e9,  "bve_q_min": 4, "ex_vin": True, "contract_key": "base"},
    # Bad-year defense
    {"name": "EXCL_2022",             "regime_gate": True,  "adv_min": 2e9,  "exclude_years": [2022], "contract_key": "base"},
    {"name": "EXCL_2024",             "regime_gate": True,  "adv_min": 2e9,  "exclude_years": [2024], "contract_key": "base"},
    {"name": "BVE_Q45_EXCL_2022",     "regime_gate": True,  "adv_min": 2e9,  "bve_q_min": 4, "exclude_years": [2022], "contract_key": "base"},
    {"name": "BVE_Q45_EXCL_2024",     "regime_gate": True,  "adv_min": 2e9,  "bve_q_min": 4, "exclude_years": [2024], "contract_key": "base"},
    # Contract parameter variants (re-simulated)
    {"name": "TP1_22PCT",             "regime_gate": True,  "adv_min": 2e9,  "contract_key": "tp1_22"},
    {"name": "TP1_15PCT",             "regime_gate": True,  "adv_min": 2e9,  "contract_key": "tp1_15"},
    {"name": "TRAIL_2_5X",            "regime_gate": True,  "adv_min": 2e9,  "contract_key": "trail_25"},
    {"name": "TRAIL_4_5X",            "regime_gate": True,  "adv_min": 2e9,  "contract_key": "trail_45"},
    {"name": "MAX_HOLD_30",           "regime_gate": True,  "adv_min": 2e9,  "contract_key": "mh_30"},
    {"name": "MAX_HOLD_120",          "regime_gate": True,  "adv_min": 2e9,  "contract_key": "mh_120"},
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _atr14(df: pd.DataFrame) -> pd.Series:
    """True range rolling mean 14 bars (not EWM). Returns Series in same kVND units as price."""
    high  = df["high"]
    low   = df["low"]
    prev  = df["close"].shift(1)
    tr = pd.concat([
        (high - low),
        (high - prev).abs(),
        (low  - prev).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(14, min_periods=5).mean()


def _full_history_quintile(values: np.ndarray) -> np.ndarray:
    """
    Quintile 1–5 (Q5 = highest) using full history of the supplied array.
    Non-causal research approximation. NaN input → 0 (unknown/excluded).
    """
    result = np.zeros(len(values), dtype=float)
    valid  = ~np.isnan(values)
    if valid.sum() < 5:
        return result
    q20, q40, q60, q80 = np.nanpercentile(values, [20, 40, 60, 80])
    if any(np.isnan(x) for x in (q20, q40, q60, q80)):
        return result
    q = np.select(
        [values <= q20, values <= q40, values <= q60, values <= q80, values > q80],
        [1, 2, 3, 4, 5],
        default=0,
    )
    return np.where(valid, q, 0).astype(float)


def _liq_bucket(adv50: float) -> str:
    if np.isnan(adv50) or adv50 < _LIQ_LOW_MAX:
        return "low"
    if adv50 < _LIQ_MID_MAX:
        return "mid"
    return "high"


# ── Contract simulation ────────────────────────────────────────────────────────

def _simulate_s3_trade(
    signal_bar: int,
    sym_df: pd.DataFrame,
    atr14_arr: np.ndarray,
    *,
    tp1_pct: float = TP1_PCT,
    tp1_size: float = TP1_SIZE,
    trail_mult: float = TRAIL_MULT,
    max_hold: int = MAX_HOLD,
    cost_rt: float = COST_RT,
) -> Optional[dict]:
    """
    Simulate one S3 paper-shadow contract.

    Entry  : open[signal_bar + 1]
    TP1    : first bar where high >= entry * (1 + tp1_pct) → exit tp1_size fraction at tp1 level
    Trail  : from TP1 bar onward, trail stop = highest_close - trail_mult * ATR14
             trail fires when low <= trail_stop (gap protection: fill at open if open <= stop)
    MaxHold: if neither TP1 nor trail triggered within max_hold bars → exit full/remainder at
             open[signal_bar + 1 + max_hold]

    Returns dict with outcome fields, or None if entry bar is out of range.
    Returns dict with matured=False if future bars run out before max_hold.
    """
    n = len(sym_df)
    entry_bar = signal_bar + 1
    if entry_bar >= n:
        return None

    open_arr  = sym_df["open"].values
    high_arr  = sym_df["high"].values
    low_arr   = sym_df["low"].values
    close_arr = sym_df["close"].values

    entry_price = open_arr[entry_bar]
    if entry_price <= 0 or np.isnan(entry_price):
        return None

    tp1_level = entry_price * (1.0 + tp1_pct)

    # ATR at signal bar — fallback to 2% of entry if missing
    missing_atr_flag = False
    atr_val = atr14_arr[signal_bar] if signal_bar < len(atr14_arr) else np.nan
    if np.isnan(atr_val) or atr_val <= 0:
        missing_atr_flag = True
        atr_val = entry_price * 0.02

    tp1_sold        = False
    tp1_bar_offset  = None

    highest_close   = entry_price
    trail_stop      = np.nan

    exit_bar_offset = None
    exit_price_val  = np.nan
    max_hold_exit   = False

    for i in range(1, max_hold + 1):
        bar = entry_bar + i
        if bar >= n:
            # Series not long enough — trade not matured
            return {
                "entry_price":        float(entry_price),
                "tp1_hit":            tp1_sold,
                "tp1_bar_offset":     tp1_bar_offset,
                "exit_bar_offset":    None,
                "exit_price":         np.nan,
                "max_hold_exit_flag": False,
                "missing_atr_flag":   missing_atr_flag,
                "blended_gross_return": np.nan,
                "blended_net_return":   np.nan,
                "matured":            False,
            }

        bar_high  = high_arr[bar]
        bar_low   = low_arr[bar]
        bar_close = close_arr[bar]
        bar_open  = open_arr[bar]

        if not tp1_sold:
            if bar_high >= tp1_level:
                tp1_sold       = True
                tp1_bar_offset = i
                # Initialize trailing from TP1 bar's close
                highest_close = bar_close
                trail_stop    = highest_close - trail_mult * atr_val
        else:
            # Update trail
            if bar_close > highest_close:
                highest_close = bar_close
            trail_stop = highest_close - trail_mult * atr_val

            # Trail hit
            if bar_low <= trail_stop:
                # Gap protection: if open is already below stop, fill at open
                exit_price_val  = bar_open if bar_open <= trail_stop else trail_stop
                exit_bar_offset = i
                break

    # Max-hold exit if no trail triggered
    if exit_bar_offset is None:
        bar = entry_bar + max_hold
        if bar >= n:
            return {
                "entry_price":        float(entry_price),
                "tp1_hit":            tp1_sold,
                "tp1_bar_offset":     tp1_bar_offset,
                "exit_bar_offset":    None,
                "exit_price":         np.nan,
                "max_hold_exit_flag": False,
                "missing_atr_flag":   missing_atr_flag,
                "blended_gross_return": np.nan,
                "blended_net_return":   np.nan,
                "matured":            False,
            }
        exit_bar_offset = max_hold
        exit_price_val  = open_arr[bar]
        max_hold_exit   = True

    # Blended return
    tp1_level_actual = entry_price * (1.0 + tp1_pct)
    if tp1_sold:
        r_tp1  = tp1_level_actual / entry_price - 1.0
        r_exit = exit_price_val   / entry_price - 1.0
        blended_gross = tp1_size * r_tp1 + (1.0 - tp1_size) * r_exit
    else:
        blended_gross = exit_price_val / entry_price - 1.0

    blended_net = blended_gross - cost_rt

    return {
        "entry_price":        float(entry_price),
        "tp1_hit":            tp1_sold,
        "tp1_bar_offset":     tp1_bar_offset,
        "exit_bar_offset":    exit_bar_offset,
        "exit_price":         float(exit_price_val),
        "max_hold_exit_flag": max_hold_exit,
        "missing_atr_flag":   missing_atr_flag,
        "blended_gross_return": float(blended_gross),
        "blended_net_return":   float(blended_net),
        "matured":            True,
    }


# ── Signal collection + simulation ────────────────────────────────────────────

def _collect_trades(
    panels: Dict[str, pd.DataFrame],
    regime_map: pd.Series,
) -> pd.DataFrame:
    """
    For every symbol in panels:
    1. Find all ADV-gated S3 signal bars (no regime filter here; stored as per-bar flag).
    2. Compute per-bar features: BVE quintile, tightness quintile.
    3. Simulate all _CONTRACT_VARIANTS for each signal bar.

    Returns wide DataFrame: one row per signal.
    Base contract columns use plain names; contract variants use '{key}_' prefix.
    """
    all_rows: List[dict] = []

    _null_sim = {
        "entry_price": np.nan, "tp1_hit": False, "tp1_bar_offset": None,
        "exit_bar_offset": None, "exit_price": np.nan,
        "max_hold_exit_flag": False, "missing_atr_flag": False,
        "blended_gross_return": np.nan, "blended_net_return": np.nan,
        "matured": False,
    }

    for sym, df in panels.items():
        if len(df) < 100:
            continue

        # S3 signal (no regime gate — stored per bar for post-hoc filtering)
        sig, _ema21, _ema55 = cloud_signal(df, _S3_FAST, _S3_SLOW)

        # ADV gate (fails closed for NaN — missing ADV excluded from all variants)
        adv_arr  = df["adv50"].values if "adv50" in df.columns else np.full(len(df), np.nan)
        adv_pass = (~np.isnan(adv_arr)) & (adv_arr >= MIN_ADV_VND)

        # Regime per bar
        regime_aligned = regime_map.reindex(df["date"]).ffill().fillna(False).values

        # Features
        bve_arr   = bo_vol_expansion(df["volume"]).values
        tight_arr = price_tightness_20(df["close"]).values
        atr14_arr = _atr14(df).values

        # Full-history quintiles
        bve_q = _full_history_quintile(bve_arr)
        # Tightness: lower raw value = more compressed = better. Invert so Q5 = tightest.
        tight_inv = np.where(np.isnan(tight_arr), np.nan, -tight_arr)
        tpbcq_q   = _full_history_quintile(tight_inv)

        # Valid signal bars (must pass ADV gate)
        sig_bars = np.where(sig.values & adv_pass)[0]
        is_vin   = sym in _VIN_SYMBOLS

        for bar in sig_bars:
            sim_results: dict = {}

            for cv_key, cv_tp1, cv_trail, cv_mh in _CONTRACT_VARIANTS:
                res = _simulate_s3_trade(
                    bar, df, atr14_arr,
                    tp1_pct=cv_tp1, tp1_size=TP1_SIZE,
                    trail_mult=cv_trail, max_hold=cv_mh,
                    cost_rt=COST_RT,
                ) or _null_sim

                if cv_key == "base":
                    for k, v in res.items():
                        sim_results[k] = v
                else:
                    sim_results[f"{cv_key}_tp1_hit"]        = res["tp1_hit"]
                    sim_results[f"{cv_key}_matured"]        = res["matured"]
                    sim_results[f"{cv_key}_blended_gross"]  = res["blended_gross_return"]
                    sim_results[f"{cv_key}_blended_net"]    = res["blended_net_return"]

            bar_date  = pd.Timestamp(df["date"].iloc[bar])
            adv50_val = float(adv_arr[bar]) if not np.isnan(adv_arr[bar]) else np.nan

            all_rows.append({
                "symbol":           sym,
                "signal_date":      bar_date,
                "year":             bar_date.year,
                "signal_bar_idx":   int(bar),
                "adv50":            adv50_val,
                "liquidity_bucket": _liq_bucket(adv50_val),
                "regime_bull":      bool(regime_aligned[bar]),
                "is_vin":           is_vin,
                "bve_val":          float(bve_arr[bar]) if not np.isnan(bve_arr[bar]) else np.nan,
                "bve_q":            int(bve_q[bar]) if bve_q[bar] > 0 else 0,
                "tightness_val":    float(tight_arr[bar]) if not np.isnan(tight_arr[bar]) else np.nan,
                "tightness_q":      int(tpbcq_q[bar]) if tpbcq_q[bar] > 0 else 0,
                **sim_results,
            })

    if not all_rows:
        return pd.DataFrame()
    return pd.DataFrame(all_rows)


# ── Variant statistics ─────────────────────────────────────────────────────────

def _variant_stats(trades: pd.DataFrame, spec: dict) -> dict:
    """Filter trades by variant spec and compute matured-only statistics."""
    _empty = {
        "n_signals": 0, "n_matured": 0,
        "win_rate": np.nan, "tp1_rate": np.nan,
        "avg_net_return": np.nan, "avg_gross_return": np.nan,
        "pct_positive": np.nan, "pct_matured": 0.0,
    }
    if trades is None or trades.empty:
        return _empty

    sub = trades.copy()

    if spec.get("regime_gate", True):
        sub = sub[sub["regime_bull"]]
    if spec.get("ex_vin", False):
        sub = sub[~sub["is_vin"]]

    adv_min = spec.get("adv_min", MIN_ADV_VND)
    sub = sub[sub["adv50"].fillna(0) >= adv_min]

    bve_q_min = spec.get("bve_q_min")
    if bve_q_min is not None:
        sub = sub[sub["bve_q"] >= bve_q_min]

    tpbcq_q_min = spec.get("tpbcq_q_min")
    if tpbcq_q_min is not None:
        sub = sub[sub["tightness_q"] >= tpbcq_q_min]

    excl = spec.get("exclude_years", [])
    if excl:
        sub = sub[~sub["year"].isin(excl)]

    n_total = len(sub)
    if n_total == 0:
        return _empty

    ck = spec.get("contract_key", "base")
    if ck == "base":
        net_col   = "blended_net_return"
        gross_col = "blended_gross_return"
        tp1_col   = "tp1_hit"
        mat_col   = "matured"
    else:
        net_col   = f"{ck}_blended_net"
        gross_col = f"{ck}_blended_gross"
        tp1_col   = f"{ck}_tp1_hit"
        mat_col   = f"{ck}_matured"

    if mat_col not in sub.columns:
        return {**_empty, "n_signals": n_total}

    matured   = sub[sub[mat_col].fillna(False)].copy()
    valid_net = matured[net_col].dropna() if net_col in matured.columns else pd.Series(dtype=float)
    n_matured = len(valid_net)

    if n_matured == 0:
        return {**_empty, "n_signals": n_total}

    win_rate  = float((valid_net >= 0.15).mean())
    pct_pos   = float((valid_net > 0).mean())
    avg_net   = float(valid_net.mean())
    avg_gross = float(matured[gross_col].dropna().mean()) if gross_col in matured.columns else np.nan
    tp1_rate  = float(matured[tp1_col].astype(float).mean()) if tp1_col in matured.columns else np.nan

    return {
        "n_signals":       n_total,
        "n_matured":       n_matured,
        "win_rate":        win_rate,
        "tp1_rate":        tp1_rate,
        "avg_net_return":  avg_net,
        "avg_gross_return": avg_gross,
        "pct_positive":    pct_pos,
        "pct_matured":     float(n_matured / n_total),
    }


# ── Classification ─────────────────────────────────────────────────────────────

def _classify_variant(stats: dict, baseline_stats: dict, variant_name: str) -> str:
    """
    Classify a variant.

    S3 can NEVER be PRODUCTION_CANDIDATE or PAPER_TRADE_PRIMARY.
    Maximum classification for base variants: PAPER_TRADE_SHADOW.
    Filter variants: up to PARALLEL_PAPER_RESEARCH if material improvement.
    """
    n       = stats.get("n_matured", 0)
    win     = stats.get("win_rate", np.nan)
    tp1     = stats.get("tp1_rate", np.nan)
    avg_net = stats.get("avg_net_return", np.nan)

    if n < _MIN_N_WATCHLIST:
        return "NEEDS_MORE_DATA"

    if not np.isnan(win) and win < 0.10:
        return "REJECT"

    if variant_name in ("BASE_NO_REGIME", "BASE_REGIME"):
        return "PAPER_TRADE_SHADOW"

    base_win = baseline_stats.get("win_rate", np.nan)
    base_tp1 = baseline_stats.get("tp1_rate", np.nan)
    base_net = baseline_stats.get("avg_net_return", np.nan)

    delta_win = (win - base_win) if not (np.isnan(win) or np.isnan(base_win)) else np.nan
    delta_tp1 = (tp1 - base_tp1) if not (np.isnan(tp1) or np.isnan(base_tp1)) else np.nan

    # PARALLEL_PAPER_RESEARCH: n ≥ MIN_N_PAPER_RESEARCH, Δwin ≥ 5pp, Δtp1 ≥ 3pp, avg_net improves
    n_ok      = n >= _MIN_N_PAPER_RESEARCH
    win_ok    = (not np.isnan(delta_win)) and delta_win >= _WIN_DELTA_THRESH
    tp1_ok    = (not np.isnan(delta_tp1)) and delta_tp1 >= _TP1_DELTA_THRESH
    net_ok    = (not np.isnan(avg_net)) and (not np.isnan(base_net)) and avg_net > base_net

    if n_ok and win_ok and tp1_ok and net_ok:
        return "PARALLEL_PAPER_RESEARCH"

    # WATCHLIST_ONLY: some positive signal
    if not np.isnan(delta_win) and delta_win >= 0 and not np.isnan(win) and win >= 0.20:
        return "WATCHLIST_ONLY"

    return "PAPER_TRADE_SHADOW"


# ── Group breakdown helpers ────────────────────────────────────────────────────

def _breakdown_by(df: pd.DataFrame, group_col: str, *, regime_gate: bool = True) -> pd.DataFrame:
    """Compute matured-only stats for base contract grouped by `group_col`."""
    sub = df.copy()
    if regime_gate:
        sub = sub[sub["regime_bull"]]
    sub = sub[sub["adv50"].fillna(0) >= MIN_ADV_VND]

    rows = []
    for grp, g in sub.groupby(group_col, dropna=False):
        mat   = g[g["matured"].fillna(False)]
        valid = mat["blended_net_return"].dropna()
        if len(valid) == 0:
            continue
        rows.append({
            group_col:       grp,
            "n_matured":     len(valid),
            "win_rate":      float((valid >= 0.15).mean()),
            "tp1_rate":      float(mat["tp1_hit"].astype(float).mean()),
            "avg_net_return": float(valid.mean()),
            "pct_positive":  float((valid > 0).mean()),
            "max_hold_rate": float(mat["max_hold_exit_flag"].astype(float).mean()),
        })
    return pd.DataFrame(rows)


# ── Findings markdown ──────────────────────────────────────────────────────────

def _generate_findings_md(
    variant_df: pd.DataFrame,
    by_year_df: pd.DataFrame,
    by_regime_df: pd.DataFrame,
    by_liq_df: pd.DataFrame,
    n_total_signals: int,
    baseline_stats: dict,
) -> str:
    bwin = baseline_stats.get("win_rate", np.nan)
    btp1 = baseline_stats.get("tp1_rate", np.nan)
    bnet = baseline_stats.get("avg_net_return", np.nan)
    bmat = baseline_stats.get("n_matured", 0)

    lines = [
        "# Stage 12 — S3 Paper-Shadow Contract Validation",
        "",
        f"**Total S3 signals (ADV-gated, full universe):** {n_total_signals}",
        f"**Baseline (BASE_REGIME) matured:** {bmat} | "
        f"Win rate: {bwin:.1%} | TP1 rate: {btp1:.1%} | Avg net: {bnet:.2%}",
        "",
        "## Contract Specification",
        "",
        f"- Entry: open[t+1]",
        f"- TP1: +{TP1_PCT:.0%} → exits {TP1_SIZE:.0%} of position",
        f"- Trail: {TRAIL_MULT}× ATR14 on remainder",
        f"- MaxHold: {MAX_HOLD} bars",
        f"- Cost: {COST_BPS} bps round-trip",
        f"- Gate: VNINDEX regime (EMA21/55) + ADV50 ≥ 2 B VND",
        "",
        "## Variant Summary",
        "",
    ]
    if not variant_df.empty:
        display_cols = [
            "variant_name", "n_signals", "n_matured",
            "win_rate", "tp1_rate", "avg_net_return", "classification",
        ]
        dc = [c for c in display_cols if c in variant_df.columns]
        lines.append(variant_df[dc].to_markdown(index=False))
    else:
        lines.append("_No variants evaluated._")
    lines.append("")

    lines += ["## By Year (BASE_REGIME)", ""]
    if not by_year_df.empty:
        lines.append(by_year_df.to_markdown(index=False))
    else:
        lines.append("_No year data._")
    lines.append("")

    lines += ["## By Regime Gate", ""]
    if not by_regime_df.empty:
        lines.append(by_regime_df.to_markdown(index=False))
    else:
        lines.append("_No regime data._")
    lines.append("")

    lines += ["## By Liquidity Bucket (BASE_REGIME)", ""]
    if not by_liq_df.empty:
        lines.append(by_liq_df.to_markdown(index=False))
    else:
        lines.append("_No liquidity data._")
    lines.append("")

    # Classification summary
    if not variant_df.empty and "classification" in variant_df.columns:
        cls_counts = variant_df["classification"].value_counts().to_dict()
        lines += ["## Classification Summary", ""]
        for cls, cnt in sorted(cls_counts.items()):
            lines.append(f"- **{cls}**: {cnt} variant(s)")
        lines.append("")

    lines += [
        "## Interpretation Notes",
        "",
        "- Win rate = fraction of matured trades with blended_net_return ≥ +15%.",
        "- Blended return = 50% × TP1_level_return + 50% × trail/max_hold_return.",
        "- `missing_atr_flag=True` trades used 2% ATR fallback — treat as approximate.",
        "- S3 classification cap: PAPER_TRADE_SHADOW (base) / PARALLEL_PAPER_RESEARCH (filters).",
        "- S3 CANNOT be PRODUCTION_CANDIDATE or PAPER_TRADE_PRIMARY.",
        "- MAX_HOLD_REJECTED = 250 bars is defined for reference only; not used as a variant.",
        "- **This file is RESEARCH / OBSERVATION ONLY. Not OMS input.**",
        "",
    ]
    return "\n".join(lines)


# ── Main entry point ───────────────────────────────────────────────────────────

def run(workers: int = 4) -> None:
    _STAGE12_WRITE_DIR.mkdir(parents=True, exist_ok=True)

    log.info("Stage 12 — loading panel (full universe)...")
    panels = load_panel(ex_vin=False)
    for sym in panels:
        panels[sym] = panels[sym].sort_values("date").reset_index(drop=True)
    log.info("Panel loaded: %d symbols", len(panels))

    log.info("Loading VNINDEX regime...")
    regime_map = load_vnindex_regime()

    # Collect trades + simulate all contract variants
    log.info("Collecting S3 signals and simulating contracts...")
    trades = _collect_trades(panels, regime_map)
    log.info("S3 signals (ADV-gated, full universe): %d", len(trades))

    # Save base trades
    out_trades = _STAGE12_WRITE_DIR / "stage12_s3_shadow_trades.csv"
    trades.to_csv(out_trades, index=False)
    log.info("Saved trades: %s (%d rows)", out_trades.name, len(trades))

    # Baseline stats (BASE_REGIME)
    baseline_spec  = next(s for s in _VARIANT_SPECS if s["name"] == "BASE_REGIME")
    baseline_stats = _variant_stats(trades, baseline_spec)
    log.info(
        "BASE_REGIME: n_matured=%d, win_rate=%.1f%%, tp1_rate=%.1f%%",
        baseline_stats["n_matured"],
        100 * (baseline_stats["win_rate"] or 0),
        100 * (baseline_stats["tp1_rate"] or 0),
    )

    # Evaluate all variants
    variant_rows = []
    for spec in _VARIANT_SPECS:
        stats = _variant_stats(trades, spec)
        cls   = _classify_variant(stats, baseline_stats, spec["name"])
        variant_rows.append({
            "variant_name":  spec["name"],
            "regime_gate":   spec.get("regime_gate", True),
            "adv_min_vnd":   spec.get("adv_min", 2e9),
            "bve_q_min":     spec.get("bve_q_min", ""),
            "tpbcq_q_min":   spec.get("tpbcq_q_min", ""),
            "ex_vin":        spec.get("ex_vin", False),
            "contract_key":  spec.get("contract_key", "base"),
            "classification": cls,
            **stats,
        })
        log.info(
            "  %-28s n=%4d  win=%.1f%%  tp1=%.1f%%  cls=%s",
            spec["name"],
            stats["n_matured"],
            100 * (stats["win_rate"] or 0),
            100 * (stats["tp1_rate"] or 0),
            cls,
        )

    variant_df = pd.DataFrame(variant_rows)
    out_variant = _STAGE12_WRITE_DIR / "stage12_s3_shadow_variant_summary.csv"
    variant_df.to_csv(out_variant, index=False)
    log.info("Saved variant summary: %s", out_variant.name)

    # By-year (BASE_REGIME)
    by_year_df = _breakdown_by(trades, "year", regime_gate=True)
    out_year   = _STAGE12_WRITE_DIR / "stage12_s3_shadow_by_year.csv"
    by_year_df.to_csv(out_year, index=False)

    # By-regime (all ADV-gated signals, no regime pre-filter)
    by_regime_df = _breakdown_by(trades, "regime_bull", regime_gate=False)
    out_regime   = _STAGE12_WRITE_DIR / "stage12_s3_shadow_by_regime.csv"
    by_regime_df.to_csv(out_regime, index=False)

    # By-liquidity (BASE_REGIME)
    by_liq_df = _breakdown_by(trades, "liquidity_bucket", regime_gate=True)
    out_liq   = _STAGE12_WRITE_DIR / "stage12_s3_shadow_by_liquidity.csv"
    by_liq_df.to_csv(out_liq, index=False)

    # Findings markdown
    findings_md = _generate_findings_md(
        variant_df      = variant_df,
        by_year_df      = by_year_df,
        by_regime_df    = by_regime_df,
        by_liq_df       = by_liq_df,
        n_total_signals = len(trades),
        baseline_stats  = baseline_stats,
    )
    out_md = _STAGE12_WRITE_DIR / "STAGE12_S3_SHADOW_CONTRACT_FINDINGS.md"
    out_md.write_text(findings_md, encoding="utf-8")
    log.info("Saved findings: %s", out_md.name)

    log.info(
        "Stage 12 complete. %d signals, %d variants evaluated.",
        len(trades), len(variant_df),
    )


if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
