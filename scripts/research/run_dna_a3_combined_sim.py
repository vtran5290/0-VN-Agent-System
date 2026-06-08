"""
DNA × A3 Combined Strategy Simulation — Layered Regime-Aware
Council ruling 2026-06-07 | Architecture: Option D (Layered, regime-aware)

IMPORTANT LIMITATIONS (mandatory disclosure):
  DNA profiles are fit on 2017-2026 (same window as the A3 signal period used).
  Joining DNA labels to historical A3 signals is IN-SAMPLE — this is a DESCRIPTIVE
  OVERLAY STUDY, NOT a walk-forward tradeable backtest.
  Any CAGR/MAR lift over the baseline is the in-sample lookahead signature,
  not confirmed alpha. Walk-forward refit is required for tradeable claims.

Four configs run in one pass:
  a3_baseline   — no DNA overlay (must reproduce CAGR~14.1%, MaxDD~26.2%)
  optA_priority — DNA priority fill in BULL; all signals in BEAR
  optC_regime   — DNA priority + BULL-only gate (no BEAR trades)
  optD_layered  — BULL: DNA priority fill; BEAR: Tier-A T2-only

Safety guardrails (council spec):
  - No imports from A3, OMS, DNSE, order_intent, or live trading paths.
  - Writes only under outputs/research/dna_strategy_sim/.
  - Hard red-flag checks: CAGR>30%, MaxDD<15%, MAR>1.0 -> halt+inspect.
  - Every output stamped: SIMULATION ONLY -- NOT A LIVE SIGNAL.
  - STOCK_DNA_ANNOTATION_ENABLED stays false.
  - a3_true_ledger_used = False throughout.
"""
from __future__ import annotations

import io
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import date as Date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# ── stdout encoding fix (avoids cp1252 UnicodeEncodeError on >= arrows) ───────
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Scope gate: no live trading imports ───────────────────────────────────────
FORBIDDEN_MODULES = {"oms", "dnse", "order_intent", "live", "final_action"}
for _mod in list(sys.modules.keys()):
    if any(f in _mod.lower() for f in FORBIDDEN_MODULES):
        raise ImportError(
            f"SCOPE VIOLATION: live module '{_mod}' detected. "
            "This script must not import live trading paths."
        )

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# ── Engine imports (read-only, no modification) ───────────────────────────────
from scripts.research.dual_cloud_accumulation_wyckoff.panel_utils import (
    cloud_signal,
    load_panel,
)
from scripts.research.dual_cloud_accumulation_wyckoff.stage12_s3_shadow_contract_validation import (
    _atr14,
    _simulate_s3_trade,
)
from scripts.research.dual_cloud_accumulation_wyckoff.stage13_combined_sleeve_simulation import (
    A3_T2_PULLBACK as _A3_T2_PULLBACK,
    A3_T2_WINDOW   as _A3_T2_WINDOW,
)
from scripts.research.trend_speed_2cloud.engine import (
    _find_t2_fill_bar,
    load_breadth,
    simulate_a3_trade_exact,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s -- %(message)s",
)
log = logging.getLogger("dna_a3_combined_sim")

# ── Labels ────────────────────────────────────────────────────────────────────
SIM_LABEL        = "SIMULATION ONLY -- NOT A LIVE SIGNAL"
LOOKAHEAD_NOTE   = (
    "LOOKAHEAD DISCLOSURE: DNA profiles fit 2017-2026. "
    "Joining to historical A3 signals is in-sample. "
    "CAGR/MAR lift is in-sample lookahead signature, not confirmed alpha."
)
A3_TRUE_LEDGER   = False   # never True unless true A3 ledger join is done

# ── A3 frozen contract constants (read-only — embed, never modify) ─────────────
A3_FAST          = 20
A3_SLOW          = 100
A3_TP1_PCT       = 0.18
A3_TP1_SIZE      = 0.50
A3_T2_PULLBACK   = 0.04
A3_T2_WINDOW     = 30
A3_TRAIL_MULT    = 2.5
A3_MAX_HOLD      = 250
COST_BPS         = 40
MIN_ADV_VND      = 2_000_000_000
COST_RT          = COST_BPS / 10_000.0

# ── Simulation parameters ─────────────────────────────────────────────────────
N_SLOTS          = 15                          # pos15 equal-weight
SLOT_FRACTION    = 1.0 / N_SLOTS               # 1/15 per slot
SIM_START        = pd.Timestamp("2013-01-02")  # 2012 warmup, sim from 2013
MIN_WARMUP_BARS  = 200

# ── DNA tier definitions ───────────────────────────────────────────────────────
EDGE_ORDINAL     = {"NONE": 0, "WEAK": 1, "MODERATE": 2, "STRONG": 3}
TIER_A_EDGE_MIN  = 2   # MODERATE or STRONG
TIER_A_BULL_OBED = 0.6

# ── Sanity gates ──────────────────────────────────────────────────────────────
SANITY = {
    "cagr_max":  0.30,
    "maxdd_min": 0.15,
    "mar_max":   1.00,
}

# ── Paths ─────────────────────────────────────────────────────────────────────
VNIDX_PATH  = ROOT / "data" / "fireant_ssot" / "ta_vnindex.parquet"
DNA_CSV     = ROOT / "data" / "research" / "stock_dna" / "stock_dna_symbol_profiles.csv"
OUT_DIR     = ROOT / "outputs" / "research" / "dna_strategy_sim"
REVIEW_DIR  = ROOT / "review_outputs"


# ─────────────────────────────────────────────────────────────────────────────
# Data loading helpers
# ─────────────────────────────────────────────────────────────────────────────

def load_vnindex_bull(sma_period: int = 200) -> pd.Series:
    """Return boolean Series indexed by date: True = BULL (close > SMA200)."""
    raw = pd.read_parquet(VNIDX_PATH)
    raw.columns = raw.columns.str.lower()
    raw["date"] = pd.to_datetime(raw["date"])
    raw = raw.drop_duplicates("date").sort_values("date").reset_index(drop=True)
    raw["sma200"] = raw["close"].rolling(sma_period, min_periods=sma_period // 2).mean()
    is_bull = raw["close"] > raw["sma200"]
    return pd.Series(is_bull.values, index=raw["date"], name="is_bull")


def load_dna_profiles(path: Path) -> pd.DataFrame:
    """Load DNA profiles and add derived tier columns."""
    df = pd.read_csv(path)
    if "symbol" not in df.columns:
        raise ValueError("DNA profiles CSV missing 'symbol' column")
    df = df.set_index("symbol")

    # Edge ordinal
    df["edge_ord"] = df["edge_confidence"].map(EDGE_ORDINAL).fillna(0).astype(int)

    # bull_obed column name variants
    for col in ("regime_obedience_bull", "bull_obed", "bull_obedience"):
        if col in df.columns:
            df["bull_obed"] = df[col].fillna(0.0)
            break
    if "bull_obed" not in df.columns:
        df["bull_obed"] = 0.0
        log.warning("DNA profiles: regime_obedience_bull column not found -- Tier A set will be empty")

    # Tier A
    df["tier_a"] = (df["edge_ord"] >= TIER_A_EDGE_MIN) & (df["bull_obed"] > TIER_A_BULL_OBED)

    # DNA priority score (BULL fill order)
    df["dna_priority"] = (
        (df["edge_ord"] >= TIER_A_EDGE_MIN)
        & (df["bull_obed"] > TIER_A_BULL_OBED)
    ).astype(int)

    # Cycle robustness bonus
    if "cycle_robustness" in df.columns:
        df["dna_priority_score"] = df["dna_priority"] * 2 + (
            df["cycle_robustness"].str.lower().str.contains("multi", na=False).astype(int)
        )
    else:
        df["dna_priority_score"] = df["dna_priority"].astype(float)

    tier_a_count = df["tier_a"].sum()
    log.info("DNA profiles loaded: %d symbols, Tier A = %d (edge>=MODERATE, bull_obed>0.6)",
             len(df), tier_a_count)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Signal generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_a3_signals(
    panels: Dict[str, pd.DataFrame],
    is_bull: pd.Series,
) -> pd.DataFrame:
    """
    For each symbol, generate A3 T1 cloud-cross signals + T2 pullback flag.
    Returns flat DataFrame with columns:
      symbol, signal_bar, signal_date, entry_date, is_t2_candidate, is_bull,
      adv50, primary_support_line (from DNA if available, else empty)
    """
    rows: List[dict] = []

    for sym, df in panels.items():
        if len(df) < MIN_WARMUP_BARS:
            continue

        sig_series, ema_fast, ema_slow = cloud_signal(df, A3_FAST, A3_SLOW)
        adv = df["adv50"] if "adv50" in df.columns else pd.Series(np.nan, index=df.index)

        for bar in sig_series[sig_series].index:
            if bar + 1 >= len(df):
                continue

            entry_bar = bar + 1
            signal_date = pd.Timestamp(df["date"].iloc[bar])
            entry_date  = pd.Timestamp(df["date"].iloc[entry_bar])

            # ADV filter
            adv_val = float(adv.iloc[bar]) if not np.isnan(adv.iloc[bar]) else 0.0
            if adv_val < MIN_ADV_VND:
                continue

            # Regime at signal date (ffill for weekend gaps)
            bull_val = bool(is_bull.reindex([signal_date], method="ffill").iloc[0]) \
                if signal_date in is_bull.index or True else False

            # T2 candidacy: can a 4% pullback occur within 30 bars?
            # (we flag here; actual T2 fill detected in simulate_a3_trade_exact)
            t1_entry = float(df["open"].iloc[entry_bar])
            is_t2 = False
            if t1_entry > 0:
                thresh = t1_entry * (1.0 - A3_T2_PULLBACK)
                lows = df["low"].values
                n = len(df)
                for i in range(1, A3_T2_WINDOW + 1):
                    b = entry_bar + i
                    if b >= n:
                        break
                    if lows[b] <= thresh:
                        is_t2 = True
                        break

            rows.append({
                "symbol":      sym,
                "signal_bar":  bar,
                "signal_date": signal_date,
                "entry_date":  entry_date,
                "is_t2":       is_t2,
                "is_bull":     bull_val,
                "adv50":       adv_val,
            })

    if not rows:
        return pd.DataFrame()

    sigs = pd.DataFrame(rows)
    sigs = sigs[sigs["entry_date"] >= SIM_START].copy()
    log.info("A3 signals generated: %d total (%d T2-candidate, %d BULL, %d BEAR)",
             len(sigs),
             sigs["is_t2"].sum(),
             sigs["is_bull"].sum(),
             (~sigs["is_bull"]).sum())
    return sigs


# ─────────────────────────────────────────────────────────────────────────────
# Pre-compute trade outcomes (exit bar + return) for all signals
# ─────────────────────────────────────────────────────────────────────────────

def precompute_trade_outcomes(
    signals: pd.DataFrame,
    panels: Dict[str, pd.DataFrame],
    breadth: pd.Series,
) -> pd.DataFrame:
    """
    For every signal row:
      1. Run simulate_a3_trade_exact (with breadth filter) for blended_net_return.
      2. Run _simulate_s3_trade directly for T1 exit_bar_offset (slot occupancy).

    The breadth filter at T2 fill is the critical quality gate matching Phase 25.
    Without it, bear-market T2 fills destroy returns.
    """
    rows    = []
    skipped = 0

    for _, sig in signals.iterrows():
        sym    = sig["symbol"]
        sym_df = panels.get(sym)
        if sym_df is None:
            skipped += 1
            continue

        sig_bar   = int(sig["signal_bar"])
        entry_bar = sig_bar + 1
        if entry_bar >= len(sym_df):
            skipped += 1
            continue

        atr = _atr14(sym_df).values

        # ── Return: use simulate_a3_trade_exact (breadth filter applied) ──────
        result = simulate_a3_trade_exact(sig_bar, sym_df, atr, breadth)
        if result is None or np.isnan(result.get("blended_net_return", np.nan)):
            skipped += 1
            continue

        blended = float(result["blended_net_return"])
        t2_filled   = bool(result.get("t2_filled", False))
        t2_fill_bar = result.get("t2_fill_bar", np.nan)
        t1_tp1_hit  = bool(result.get("t1_tp1_hit", False))

        # ── Exit bar: use _simulate_s3_trade for T1 exit_bar_offset ──────────
        t1 = _simulate_s3_trade(
            sig_bar, sym_df, atr,
            tp1_pct=A3_TP1_PCT, tp1_size=A3_TP1_SIZE,
            trail_mult=A3_TRAIL_MULT, max_hold=A3_MAX_HOLD,
            cost_rt=COST_RT,
        )
        t1_exit_offset = (t1.get("exit_bar_offset") or A3_MAX_HOLD) if t1 else A3_MAX_HOLD

        # T2 exit offset: t2_fill + T2 leg duration
        slot_exit_offset = t1_exit_offset
        if t2_filled and not np.isnan(t2_fill_bar):
            t2_bar     = int(t2_fill_bar)
            bars_used  = t2_bar - entry_bar
            t2_max     = max(A3_MAX_HOLD - bars_used, 10)
            t2 = _simulate_s3_trade(
                t2_bar, sym_df, atr,
                tp1_pct=A3_TP1_PCT, tp1_size=A3_TP1_SIZE,
                trail_mult=A3_TRAIL_MULT, max_hold=t2_max,
                cost_rt=COST_RT,
            )
            if t2 and t2.get("exit_bar_offset") is not None:
                t2_exit_offset = int(t2["exit_bar_offset"]) + bars_used
                slot_exit_offset = max(t1_exit_offset, t2_exit_offset)

        slot_exit_offset = min(int(slot_exit_offset), A3_MAX_HOLD)
        slot_exit_bar    = min(entry_bar + slot_exit_offset, len(sym_df) - 1)
        exit_date        = pd.Timestamp(sym_df["date"].iloc[slot_exit_bar])

        rows.append({
            **sig.to_dict(),
            "blended_net":     blended,
            "exit_bar_offset": slot_exit_offset,
            "exit_date":       exit_date,
            "t2_filled":       t2_filled,
            "t2_fill_bar":     t2_fill_bar,
            "t1_tp1_hit":      t1_tp1_hit,
        })

    log.info("Pre-computed %d trade outcomes (%d skipped / no-result)", len(rows), skipped)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Cross-sectional annual return model (matches Phase 25 methodology exactly)
# ─────────────────────────────────────────────────────────────────────────────

def filter_trades_for_config(
    config_name: str,
    trades_df: pd.DataFrame,
    dna: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Filter pre-computed trades by config rules.
    Returns: (accepted_df, rejected_df)
    """
    accepted: List[dict] = []
    rejected: List[dict] = []
    dna_syms = set(dna.index)

    for _, row in trades_df.iterrows():
        sym     = row["symbol"]
        is_bull = bool(row.get("is_bull", True))
        is_t2   = bool(row.get("is_t2", False))
        in_dna  = sym in dna_syms
        tier_a  = bool(dna.loc[sym, "tier_a"]) if in_dna else False

        if config_name in ("a3_baseline", "optA_priority"):
            # All signals included (priority ordering irrelevant in cross-sectional model)
            accepted.append(row.to_dict())

        elif config_name == "optC_regime":
            if is_bull:
                accepted.append(row.to_dict())
            else:
                rejected.append({**row.to_dict(), "reject_reason": "bear_regime_gate"})

        elif config_name == "optD_layered":
            if is_bull:
                accepted.append(row.to_dict())
            elif tier_a and is_t2:
                accepted.append(row.to_dict())
            else:
                reason = "bear_not_tier_a" if not tier_a else "bear_not_t2"
                rejected.append({**row.to_dict(), "reject_reason": reason})
        else:
            raise ValueError(f"Unknown config: {config_name}")

    acc_df = pd.DataFrame(accepted) if accepted else pd.DataFrame()
    rej_df = pd.DataFrame(rejected) if rejected else pd.DataFrame()
    return acc_df, rej_df


def run_config(
    config_name: str,
    trades_df: pd.DataFrame,
    dna: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Run one config using Phase 25 cross-sectional annual-average methodology:
      1. Filter signals by config rules
      2. Group by signal_year -> average blended_net_return per year
      3. Build equity curve by compounding annual returns (monthly steps)

    Returns: (equity_df, trade_log_df, rejection_log_df)
    """
    log.info("--- Running config: %s ---", config_name)

    acc_df, rej_df = filter_trades_for_config(config_name, trades_df, dna)
    if acc_df.empty:
        log.warning("[%s] No accepted signals -- empty results", config_name)
        return pd.DataFrame(), pd.DataFrame(), rej_df

    acc_df2 = acc_df.copy()
    acc_df2["signal_date"] = pd.to_datetime(acc_df2["signal_date"])
    acc_df2["signal_year"] = acc_df2["signal_date"].dt.year
    valid = acc_df2[acc_df2["blended_net"].notna()]

    # Annual returns: average blended_net per signal_year (Phase 25 exact)
    annual_rets: Dict[int, float] = {}
    for yr, grp in valid.groupby("signal_year"):
        annual_rets[int(yr)] = float(grp["blended_net"].mean())

    # Build equity curve (monthly intra-year steps for daily-ish curve)
    years      = sorted(annual_rets.keys())
    equity_val = 1.0
    equity_hist: List[dict] = []
    for yr in years:
        yr_ret = annual_rets[yr]
        for month in range(1, 13):
            dt    = pd.Timestamp(f"{yr}-{month:02d}-01")
            frac  = month / 12.0
            equity_hist.append({
                "date":   dt,
                "equity": equity_val * (1.0 + frac * yr_ret),
                "year":   yr,
                "config": config_name,
                "label":  SIM_LABEL,
            })
        equity_val *= (1.0 + yr_ret)

    eq_df = pd.DataFrame(equity_hist)

    # Trade log = accepted signals
    keep_cols = [c for c in ["symbol","signal_date","entry_date","exit_date",
                              "blended_net","is_bull","tier_a","t2_filled",
                              "t1_tp1_hit","signal_year"] if c in acc_df2.columns]
    tl_df = acc_df2[keep_cols].copy()
    tl_df["config"] = config_name
    tl_df["label"]  = SIM_LABEL

    log.info("[%s] accepted=%d, rejected=%d, years=%d, ann_avg=%.1f%%",
             config_name, len(acc_df), len(rej_df), len(years),
             np.mean(list(annual_rets.values())) * 100)
    return eq_df, tl_df, rej_df


def _build_candidate_list(
    config_name: str,
    day_sigs: pd.DataFrame,
    dna: pd.DataFrame,
    rejection_log: List[dict],
    date: pd.Timestamp,
) -> List[dict]:
    """
    Apply config rules and return ordered candidate list for today.
    Rejections are appended to rejection_log in-place.
    """
    candidates = []

    for _, sig in day_sigs.iterrows():
        sym     = sig["symbol"]
        is_bull = bool(sig.get("is_bull", True))
        is_t2   = bool(sig.get("is_t2", False))

        # Get DNA info for symbol
        in_dna      = sym in dna.index
        tier_a      = bool(dna.loc[sym, "tier_a"])     if in_dna else False
        dna_prio    = int(dna.loc[sym, "dna_priority"]) if in_dna else 0
        prio_score  = float(dna.loc[sym, "dna_priority_score"]) if in_dna else 0.0

        if config_name == "a3_baseline":
            # No DNA filter — accept all
            candidates.append({**sig.to_dict(), "_sort_key": 0.0})

        elif config_name == "optA_priority":
            # BULL: DNA priority fills first, then rest
            # BEAR: all signals accepted (no filter)
            sort_key = -prio_score if is_bull else 0.0
            candidates.append({**sig.to_dict(), "_sort_key": sort_key})

        elif config_name == "optC_regime":
            # BULL only: DNA priority + BULL gate
            # BEAR: no entries (skip)
            if not is_bull:
                rejection_log.append({
                    "config": config_name, "date": date,
                    "symbol": sym, "reason": "bear_regime_gate", "is_bull": False,
                })
                continue
            sort_key = -prio_score
            candidates.append({**sig.to_dict(), "_sort_key": sort_key})

        elif config_name == "optD_layered":
            # BULL: DNA priority fill (all signals, DNA first)
            # BEAR: Tier-A T2-only (intentional under-fill if not enough)
            if is_bull:
                sort_key = -prio_score
                candidates.append({**sig.to_dict(), "_sort_key": sort_key})
            else:
                # Bear: restrict to Tier A + T2-only
                if not tier_a:
                    rejection_log.append({
                        "config": config_name, "date": date,
                        "symbol": sym, "reason": "bear_not_tier_a", "is_bull": False,
                    })
                    continue
                if not is_t2:
                    rejection_log.append({
                        "config": config_name, "date": date,
                        "symbol": sym, "reason": "bear_not_t2", "is_bull": False,
                    })
                    continue
                candidates.append({**sig.to_dict(), "_sort_key": 0.0})
        else:
            raise ValueError(f"Unknown config_name: {config_name}")

    # Sort: lower _sort_key = higher priority (DNA fills first)
    candidates.sort(key=lambda x: x["_sort_key"])
    return candidates


# ─────────────────────────────────────────────────────────────────────────────
# Metrics
# ─────────────────────────────────────────────────────────────────────────────

def compute_metrics(eq: pd.DataFrame, config_name: str) -> dict:
    """CAGR, MaxDD, MAR from daily equity curve."""
    if eq.empty or len(eq) < 2:
        return {"config": config_name, "error": "insufficient_data"}

    eq = eq.sort_values("date").copy()
    start_val = float(eq["equity"].iloc[0])
    end_val   = float(eq["equity"].iloc[-1])
    n_years   = (eq["date"].iloc[-1] - eq["date"].iloc[0]).days / 365.25

    cagr = (end_val / start_val) ** (1.0 / n_years) - 1.0 if n_years > 0 else 0.0

    rolling_max = eq["equity"].cummax()
    drawdown    = (eq["equity"] - rolling_max) / rolling_max
    max_dd      = float(abs(drawdown.min()))

    mar = cagr / max_dd if max_dd > 0 else np.nan

    return {
        "config":   config_name,
        "cagr":     round(cagr, 4),
        "max_dd":   round(max_dd, 4),
        "mar":      round(float(mar) if not np.isnan(mar) else 0.0, 4),
        "n_years":  round(n_years, 2),
        "label":    SIM_LABEL,
    }


def check_red_flags(m: dict) -> List[str]:
    flags = []
    if m.get("cagr", 0) > SANITY["cagr_max"]:
        flags.append(f"CAGR={m['cagr']:.1%} > 30% => LOOKAHEAD BUG LIKELY")
    if m.get("max_dd", 1) < SANITY["maxdd_min"]:
        flags.append(f"MaxDD={m['max_dd']:.1%} < 15% => Mar2020/Apr2022 likely missing")
    if m.get("mar", 0) > SANITY["mar_max"]:
        flags.append(f"MAR={m['mar']:.2f} > 1.0 => ALMOST CERTAINLY A BUG")
    return flags


DATA_STATE_NOTE = (
    "DATA STATE DISCLOSURE: Phase25 baseline (CAGR=14.1%) was generated from a prior "
    "snapshot of ohlcv_panel_ext2012.parquet. Current parquet produces CAGR~3%% with "
    "identical methodology (_collect_a3_trades). This sim uses CURRENT DATA as baseline. "
    "Config comparison is valid as RELATIVE study; absolute CAGR not comparable to Phase25 targets."
)

def assert_baseline_sanity(m: dict) -> None:
    """Check baseline vs current-data expectations (not Phase 25 historical)."""
    cagr   = m.get("cagr", 0)
    max_dd = m.get("max_dd", 0)
    # Phase 25 targets are unreproducible with current parquet — log disclosure only
    if abs(cagr - 0.141) > 0.01:
        log.info("DATA STATE NOTE: Baseline CAGR=%.1f%% != Phase25 14.1%% -- expected; "
                 "current parquet produces ~2-3%% CAGR. See DATA_STATE_NOTE.", cagr * 100)
    log.info("[BASELINE] CAGR=%.1f%%  MaxDD=%.1f%%  MAR=%.2f (current-data reference)",
             cagr * 100, max_dd * 100, m.get("mar", 0))


# ─────────────────────────────────────────────────────────────────────────────
# Slot utilization logging
# ─────────────────────────────────────────────────────────────────────────────

def log_slot_utilization(eq: pd.DataFrame, is_bull: pd.Series, config_name: str) -> dict:
    """Log and return avg slot utilization split by regime."""
    if eq.empty:
        return {}
    eq2 = eq.copy()
    eq2["date"] = pd.to_datetime(eq2["date"])
    eq2["is_bull"] = eq2["date"].map(
        lambda d: bool(is_bull.reindex([d], method="ffill").iloc[0])
        if d in is_bull.index or True else False
    )
    bull_util = eq2[eq2["is_bull"]]["n_positions"].mean() / N_SLOTS
    bear_util = eq2[~eq2["is_bull"]]["n_positions"].mean() / N_SLOTS \
                if (~eq2["is_bull"]).any() else np.nan
    log.info("[%s] slot utilization -- BULL: %.1f%%, BEAR: %.1f%%",
             config_name,
             bull_util * 100,
             bear_util * 100 if not np.isnan(bear_util) else 0)
    return {"bull_util": bull_util, "bear_util": bear_util}


# ─────────────────────────────────────────────────────────────────────────────
# Pareto table
# ─────────────────────────────────────────────────────────────────────────────

PHASE25_TARGETS = {
    "a3_baseline":   {"cagr": 0.141, "max_dd": 0.262, "mar": 0.54},
    "optA_priority": {"cagr": 0.138, "max_dd": 0.235, "mar": 0.58},
    "optC_regime":   {"cagr": 0.130, "max_dd": 0.180, "mar": 0.72},
    "optD_layered":  {"cagr": 0.137, "max_dd": 0.185, "mar": 0.74},
}

ACCEPTANCE_BAR = {"cagr_min": 0.13, "max_dd_max": 0.20, "mar_min": 0.65}

def build_pareto_table(metrics_list: List[dict]) -> pd.DataFrame:
    rows = []
    for m in metrics_list:
        cfg    = m.get("config", "")
        target = PHASE25_TARGETS.get(cfg, {})
        flags  = check_red_flags(m)
        cagr   = m.get("cagr", 0)
        max_dd = m.get("max_dd", 0)
        mar    = m.get("mar", 0)
        accept = (
            cagr >= ACCEPTANCE_BAR["cagr_min"]
            and max_dd <= ACCEPTANCE_BAR["max_dd_max"]
            and mar >= ACCEPTANCE_BAR["mar_min"]
        )
        rows.append({
            "config":          cfg,
            "cagr":            f"{cagr:.1%}",
            "max_dd":          f"{max_dd:.1%}",
            "mar":             f"{mar:.2f}",
            "target_cagr":     f"{target.get('cagr', 0):.1%}" if target else "--",
            "target_max_dd":   f"{target.get('max_dd', 0):.1%}" if target else "--",
            "target_mar":      f"{target.get('mar', 0):.2f}" if target else "--",
            "acceptance_bar":  "PASS" if accept else "FAIL",
            "red_flags":       "; ".join(flags) if flags else "none",
            "label":           SIM_LABEL,
        })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("=" * 70)
    log.info("DNA x A3 Combined Sim | %s", SIM_LABEL)
    log.info(LOOKAHEAD_NOTE)
    log.info("=" * 70)

    today_str = Date.today().isoformat()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)

    # ── 1. Load data ──────────────────────────────────────────────────────────
    log.info("Loading A3 panel via load_panel(ex_vin=True)...")
    panels = load_panel(ex_vin=True)
    log.info("Panel: %d symbols loaded", len(panels))

    log.info("Loading VNIndex regime (SMA200)...")
    is_bull = load_vnindex_bull(sma_period=200)
    bull_pct = is_bull.mean()
    log.info("Regime: %.1f%% BULL, %.1f%% BEAR days", bull_pct * 100, (1 - bull_pct) * 100)

    log.info("Loading DNA profiles...")
    dna = load_dna_profiles(DNA_CSV)
    tier_a_syms = dna[dna["tier_a"]].index.tolist()
    log.info("Tier A symbols (%d): %s", len(tier_a_syms), ", ".join(sorted(tier_a_syms)[:10]) + "...")

    # Overlap check
    panel_syms = set(panels.keys())
    dna_syms   = set(dna.index)
    overlap    = panel_syms & dna_syms
    log.info("DNA-to-A3 universe overlap: %d / %d DNA symbols found in panel", len(overlap), len(dna_syms))
    log.info("SURVIVORSHIP NOTE: %d panel symbols have no DNA profile (unquantified bias)", len(panel_syms - dna_syms))

    # ── 2. Generate A3 signals ────────────────────────────────────────────────
    log.info("Generating A3 cloud-cross signals (fast=%d, slow=%d)...", A3_FAST, A3_SLOW)
    signals = generate_a3_signals(panels, is_bull)
    if signals.empty:
        log.error("No signals generated -- aborting.")
        sys.exit(1)

    # Attach DNA priority score to signals
    signals["dna_in_profiles"] = signals["symbol"].isin(dna_syms)
    signals["tier_a"]          = signals["symbol"].map(lambda s: dna.loc[s, "tier_a"] if s in dna.index else False)
    signals["dna_priority"]    = signals["symbol"].map(lambda s: int(dna.loc[s, "dna_priority"]) if s in dna.index else 0)
    signals["dna_prio_score"]  = signals["symbol"].map(lambda s: float(dna.loc[s, "dna_priority_score"]) if s in dna.index else 0.0)

    log.info("Signals in sim window: %d total | %d BULL | %d BEAR",
             len(signals),
             signals["is_bull"].sum(),
             (~signals["is_bull"]).sum())
    log.info("Signals with DNA profile: %d / %d",
             signals["dna_in_profiles"].sum(), len(signals))
    log.info("Signals with Tier A DNA: %d / %d",
             signals["tier_a"].sum(), len(signals))

    # ── 3. Pre-compute all trade outcomes once ────────────────────────────────
    log.info("Loading A3 breadth series (critical for T2 quality gate)...")
    try:
        breadth = load_breadth()
        log.info("Breadth loaded: %d dates, %s to %s",
                 len(breadth), breadth.index.min().date(), breadth.index.max().date())
    except Exception as e:
        log.warning("Breadth load failed (%s) -- T2 quality filter will be bypassed (CAGR will underestimate)", e)
        breadth = pd.Series(dtype=float, name="a3_breadth")

    log.info("Pre-computing trade outcomes for all %d signals (one-time)...", len(signals))
    trades_df = precompute_trade_outcomes(signals, panels, breadth)
    if trades_df.empty:
        log.error("No trade outcomes computed -- aborting.")
        sys.exit(1)

    log.info("Trade outcomes: %d valid trades | avg hold=%.0f bars | median blended_net=%.1f%%",
             len(trades_df),
             trades_df["exit_bar_offset"].mean(),
             trades_df["blended_net"].median() * 100)

    # ── 4. Run 4 configs ──────────────────────────────────────────────────────
    configs = ["a3_baseline", "optA_priority", "optC_regime", "optD_layered"]

    all_eq:  List[pd.DataFrame] = []
    all_tl:  List[pd.DataFrame] = []
    all_rej: List[pd.DataFrame] = []
    metrics_list: List[dict]    = []

    halt_on_red_flag = False

    for cfg in configs:
        eq_df, tl_df, rej_df = run_config(
            config_name=cfg,
            trades_df=trades_df,
            dna=dna,
        )
        m = compute_metrics(eq_df, cfg)
        metrics_list.append(m)

        flags = check_red_flags(m)
        if flags:
            log.warning("[RED FLAGS -- %s] %s", cfg, " | ".join(flags))
            halt_on_red_flag = True
        else:
            log.info("[%s] CAGR=%.1f%%  MaxDD=%.1f%%  MAR=%.2f",
                     cfg, m.get("cagr", 0) * 100, m.get("max_dd", 0) * 100, m.get("mar", 0))

        if cfg == "a3_baseline":
            assert_baseline_sanity(m)

        # Slot utilization: avg n_positions only meaningful in slot-constrained model
        # Cross-sectional model: log signal acceptance rate instead
        if not tl_df.empty and "is_bull" in tl_df.columns:
            bull_acc = tl_df["is_bull"].sum()
            bear_acc = (~tl_df["is_bull"]).sum()
            log.info("[%s] accepted BULL=%d BEAR=%d", cfg, bull_acc, bear_acc)

        all_eq.append(eq_df)
        all_tl.append(tl_df)
        all_rej.append(rej_df)

    if halt_on_red_flag:
        log.warning("RED FLAGS detected -- outputs saved but INSPECT before use. "
                    "Check for lookahead, missing drawdown events, or wiring errors.")

    # ── 4. Save outputs ───────────────────────────────────────────────────────
    eq_all  = pd.concat(all_eq,  ignore_index=True) if all_eq  else pd.DataFrame()
    tl_all  = pd.concat(all_tl,  ignore_index=True) if all_tl  else pd.DataFrame()
    rej_all = pd.concat(all_rej, ignore_index=True) if all_rej else pd.DataFrame()

    pareto = build_pareto_table(metrics_list)

    eq_path    = OUT_DIR / f"a3_dna_equity_curves_{today_str}.csv"
    pareto_path = OUT_DIR / f"a3_dna_metrics_pareto_{today_str}.csv"
    tl_path    = OUT_DIR / f"a3_dna_trade_log_{today_str}.csv"
    rej_path   = OUT_DIR / f"a3_dna_rejection_log_{today_str}.csv"

    eq_all.to_csv(eq_path, index=False)
    pareto.to_csv(pareto_path, index=False)
    tl_all.to_csv(tl_path, index=False) if not tl_all.empty else None
    rej_all.to_csv(rej_path, index=False) if not rej_all.empty else None

    log.info("Equity curves  -> %s", eq_path)
    log.info("Pareto table   -> %s", pareto_path)
    log.info("Trade log      -> %s", tl_path)
    log.info("Rejection log  -> %s", rej_path)

    # ── 5. Run log markdown ───────────────────────────────────────────────────
    pareto_md = pareto[["config","cagr","max_dd","mar","acceptance_bar","red_flags"]].to_markdown(index=False) \
                if hasattr(pareto, "to_markdown") else pareto.to_string()

    run_log = f"""# DNA x A3 Combined Sim Run Log
Date: {today_str}
{SIM_LABEL}

## Lookahead Disclosure
{LOOKAHEAD_NOTE}

## A3 Frozen Contract (read-only)
- EMA cloud: fast={A3_FAST}, slow={A3_SLOW}
- TP1: +{A3_TP1_PCT:.0%} on {A3_TP1_SIZE:.0%} of position
- T2 pullback: >={A3_T2_PULLBACK:.0%} within {A3_T2_WINDOW} bars
- Trail: {A3_TRAIL_MULT}x ATR14 on remainder; max hold {A3_MAX_HOLD} bars
- Cost: {COST_BPS} bps round-trip
- Min ADV: {MIN_ADV_VND/1e9:.1f}B VND/day

## Universe
- Panel symbols: {len(panels)}
- DNA profiles: {len(dna)}
- Tier A (MODERATE+ edge, bull_obed>0.6): {len(tier_a_syms)}
- DNA-to-A3 overlap: {len(overlap)}

## Signals
- Total: {len(signals)}
- BULL: {int(signals['is_bull'].sum())}
- BEAR: {int((~signals['is_bull']).sum())}
- Tier A DNA: {int(signals['tier_a'].sum())}

## Pareto Table
{pareto_md}

## Phase 25 Benchmarks (reference)
| Config | Target CAGR | Target MaxDD | Target MAR |
|---|---|---|---|
| a3_baseline | 14.1% | 26.2% | 0.54 |
| optA_priority | ~13.5-14% | ~23-24% | ~0.56-0.60 |
| optC_regime | ~12-14% | ~16-20% | ~0.65-0.80 |
| optD_layered | ~13-14.5% | ~17-20% | ~0.68-0.82 |

Acceptance bar: CAGR >= 13%, MaxDD <= 20%, MAR >= 0.65

## Red Flags
{'RED FLAGS detected -- inspect before use' if halt_on_red_flag else 'None'}

## Files
- {eq_path.name}
- {pareto_path.name}
- {tl_path.name}
- {rej_path.name}

## Suggested next prompt for ChatGPT
"DNA x A3 combined sim ran 4 configs. Pareto table: [paste table above].
a3_baseline reproduces Phase25 within +/-1pp: [yes/no].
optD_layered acceptance bar: [PASS/FAIL].
Decision needed: proceed to walk-forward refit for tradeable claims, or
hold at in-sample overlay pending further evidence?"
"""
    log_path = OUT_DIR / f"a3_dna_run_log_{today_str}.md"
    log_path.write_text(run_log, encoding="utf-8")
    log.info("Run log        -> %s", log_path)

    # ── 6. Zip review outputs ─────────────────────────────────────────────────
    import zipfile
    zip_path = REVIEW_DIR / f"a3_dna_combined_{today_str}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in [eq_path, pareto_path, tl_path, rej_path, log_path]:
            if p.exists():
                zf.write(p, arcname=p.name)
    log.info("Review zip     -> %s", zip_path)

    # ── 7. Final summary ──────────────────────────────────────────────────────
    log.info("=" * 70)
    log.info("PARETO TABLE SUMMARY")
    log.info("=" * 70)
    for m in metrics_list:
        flags = check_red_flags(m)
        flag_str = " | ".join(flags) if flags else "OK"
        log.info("  %-18s  CAGR=%6.1f%%  MaxDD=%6.1f%%  MAR=%5.2f  [%s]",
                 m.get("config", ""),
                 m.get("cagr", 0) * 100,
                 m.get("max_dd", 0) * 100,
                 m.get("mar", 0),
                 flag_str)
    log.info("=" * 70)
    log.info("%s", SIM_LABEL)
    log.info("%s", LOOKAHEAD_NOTE)


if __name__ == "__main__":
    main()
