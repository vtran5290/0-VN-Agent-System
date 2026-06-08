"""
DNA × A3 Slot-Constrained Priority Simulation
Council review 2026-06-07 | Implements Option B: narrow slot-constrained final test

MANDATORY DISCLOSURES:
  SIMULATION ONLY -- NOT A LIVE SIGNAL
  STOCK_DNA_RESEARCH_ANNOTATION_ONLY
  No A3/OMS/live-routing/sizing/final_action changes
  a3_true_ledger_used = False
  STOCK_DNA_ANNOTATION_ENABLED stays False

  IN-SAMPLE LOOKAHEAD: DNA profiles fit 2017-2026. Applying to signals from 2013
  is pure in-sample. All CAGR/MAR numbers carry lookahead bias.
  Post-2017 robustness slice reported separately.

DESIGN (addresses council review issues):
  1. Priority taxonomy: derived from production_status + edge_confidence only.
     "SUPPORT_ALIGNED" proxied by status=RESEARCH_ANNOTATION_ONLY + edge tier.
     "DANGER" proxied by status=REJECT. No price-vs-support-line geometry
     (primary_support_line / danger_line are line NAMES, not price values).
  2. Same-day disambiguation: stable sort (priority_bucket ASC, symbol ASC).
  3. Baseline ordering: symbol alpha only (no DNA). Identical tiebreak logic.
  4. Exit date: resolved via sym_df["date"].iloc[entry_bar + exit_offset] --
     actual calendar date per symbol, not bar-count assumption.
  5. Placebo config: randomly permuted DNA priority buckets -- real DNA must
     beat permutation null materially to be considered non-trivial signal.
  6. Acceptance rule: AND-gate (CAGR >= baseline AND MaxDD <= baseline).
     OR-gate (slightly lower CAGR + better MAR) reported separately as softer bar.

Six configs:
  a3_baseline_slot       -- no DNA; tiebreak = symbol alpha
  dna_priority_slot      -- full tier ladder; no exclusion
  dna_danger_last        -- non-REJECT fills normally; REJECT forced to last bucket
  dna_danger_exclude     -- REJECT symbols hard-excluded
  dna_priority_plus_danger_last -- full tier + REJECT explicitly last (= dna_priority_slot)
  dna_random_permute     -- placebo: random shuffle of priority buckets (seed=42)
"""
from __future__ import annotations

import io
import json
import logging
import random
import sys
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date as Date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# ── stdout encoding fix ───────────────────────────────────────────────────────
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Scope gate ────────────────────────────────────────────────────────────────
FORBIDDEN_MODULES = {"oms", "dnse", "order_intent", "live", "final_action"}
for _mod in list(sys.modules.keys()):
    if any(f in _mod.lower() for f in FORBIDDEN_MODULES):
        raise ImportError(f"SCOPE VIOLATION: live module '{_mod}' detected.")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.research.dual_cloud_accumulation_wyckoff.panel_utils import (
    cloud_signal,
    load_panel,
)
from scripts.research.dual_cloud_accumulation_wyckoff.stage12_s3_shadow_contract_validation import (
    _atr14,
    _simulate_s3_trade,
)
from scripts.research.trend_speed_2cloud.engine import (
    load_breadth,
    simulate_a3_trade_exact,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s -- %(message)s",
)
log = logging.getLogger("dna_a3_slot_sim")

# ── Labels ────────────────────────────────────────────────────────────────────
SIM_LABEL      = "SIMULATION ONLY -- NOT A LIVE SIGNAL"
STATUS_LABEL   = "STOCK_DNA_RESEARCH_ANNOTATION_ONLY"
LOOKAHEAD_NOTE = (
    "IN-SAMPLE LOOKAHEAD: DNA profiles fit 2017-2026. "
    "Signals from 2013 carry full in-sample bias. "
    "CAGR/MAR are not predictive estimates."
)
A3_TRUE_LEDGER = False

# ── A3 frozen contract ────────────────────────────────────────────────────────
A3_FAST        = 20
A3_SLOW        = 100
A3_TP1_PCT     = 0.18
A3_TP1_SIZE    = 0.50
A3_T2_PULLBACK = 0.04
A3_T2_WINDOW   = 30
A3_TRAIL_MULT  = 2.5
A3_MAX_HOLD    = 250
COST_BPS       = 40
MIN_ADV_VND    = 2_000_000_000
COST_RT        = COST_BPS / 10_000.0

# ── Portfolio params ──────────────────────────────────────────────────────────
N_SLOTS        = 15
SLOT_FRAC      = 1.0 / N_SLOTS
SIM_START      = pd.Timestamp("2013-01-02")
POST17_START   = pd.Timestamp("2017-01-01")   # robustness slice (post DNA fit start)
MIN_WARMUP     = 200
PLACEBO_SEED   = 42

# ── DNA priority taxonomy ─────────────────────────────────────────────────────
# Derived from production_status + edge_confidence ONLY.
# "SUPPORT_ALIGNED" = proxied by status=RESEARCH_ANNOTATION_ONLY + edge tier.
# "DANGER"          = proxied by status=REJECT.
# primary_support_line / danger_line are LINE NAMES (e.g. 'ema20'), not prices.
# Price-vs-line geometry NOT computed -- requires separate pipeline.
BUCKET_LABELS = {
    0: "RAA_STRONG",          # RESEARCH_ANNOTATION_ONLY + STRONG edge
    1: "RAA_MODERATE",        # RESEARCH_ANNOTATION_ONLY + MODERATE edge
    2: "RAA_WEAK",            # RESEARCH_ANNOTATION_ONLY + WEAK edge
    3: "RAA_NONE",            # RESEARCH_ANNOTATION_ONLY + NONE edge (off support proxy)
    4: "WATCHLIST_HIGH",      # WATCHLIST_ONLY + STRONG or MODERATE edge
    5: "NO_PROFILE",          # not in DNA CSV
    6: "WATCHLIST_LOW",       # WATCHLIST_ONLY + WEAK or NONE edge
    7: "REJECT_DANGER",       # REJECT (danger proxy -- worst)
}

EDGE_ORD = {"STRONG": 0, "MODERATE": 1, "WEAK": 2, "NONE": 3}

# ── Paths ─────────────────────────────────────────────────────────────────────
DNA_CSV      = ROOT / "data" / "research" / "stock_dna" / "stock_dna_symbol_profiles.csv"
VNIDX_PATH   = ROOT / "data" / "fireant_ssot" / "ta_vnindex.parquet"
OUT_DIR      = ROOT / "outputs" / "research" / "dna_strategy_sim"
REVIEW_DIR   = ROOT / "review_outputs"

CONFIGS = [
    "a3_baseline_slot",
    "dna_priority_slot",
    "dna_danger_last",
    "dna_danger_exclude",
    "dna_priority_plus_danger_last",
    "dna_random_permute",
]


# ─────────────────────────────────────────────────────────────────────────────
# Priority bucket derivation
# ─────────────────────────────────────────────────────────────────────────────

def derive_priority_bucket(sym: str, dna: pd.DataFrame) -> int:
    """
    Map symbol -> priority bucket (0=best, 7=worst).
    Based on production_status + edge_confidence only.
    See BUCKET_LABELS for full mapping.
    """
    if sym not in dna.index:
        return 5  # no profile

    status = str(dna.loc[sym, "production_status"])
    edge   = str(dna.loc[sym, "edge_confidence"])

    if status == "REJECT":
        return 7

    if status == "RESEARCH_ANNOTATION_ONLY":
        return EDGE_ORD.get(edge, 3)  # 0, 1, 2, 3

    if status == "WATCHLIST_ONLY":
        if edge in ("STRONG", "MODERATE"):
            return 4
        return 6

    return 5  # fallback


def build_priority_map(dna: pd.DataFrame) -> Dict[str, int]:
    """Symbol -> bucket dict for all DNA symbols."""
    return {sym: derive_priority_bucket(sym, dna) for sym in dna.index}


def build_config_sort_key(config: str, sym: str, bucket_map: Dict[str, int],
                          placebo_map: Optional[Dict[str, int]] = None) -> Tuple[int, str]:
    """
    Returns (sort_key, symbol) for deterministic stable sort.
    Lower sort_key = higher priority = fills first.
    """
    raw_bucket = bucket_map.get(sym, 5)

    if config == "a3_baseline_slot":
        # No DNA priority -- all same bucket; symbol alpha tiebreak only
        return (0, sym)

    if config == "dna_priority_slot":
        return (raw_bucket, sym)

    if config == "dna_danger_last":
        # Non-REJECT fills normally (bucket 0-6 treated equally for priority);
        # REJECT forced to last bucket 7.
        # Only differentiator from baseline: REJECT trades always after non-REJECT.
        danger_key = 1 if raw_bucket == 7 else 0
        return (danger_key, sym)

    if config == "dna_danger_exclude":
        # REJECT excluded at filter stage; rest treated equally.
        return (0, sym)

    if config == "dna_priority_plus_danger_last":
        # Full tier ladder (same as dna_priority_slot).
        return (raw_bucket, sym)

    if config == "dna_random_permute":
        # Placebo: use permuted bucket
        permuted = (placebo_map or {}).get(sym, 5)
        return (permuted, sym)

    return (0, sym)


def is_excluded(config: str, sym: str, bucket_map: Dict[str, int]) -> bool:
    """Hard filter: True = signal rejected before slot check."""
    if config == "dna_danger_exclude":
        return bucket_map.get(sym, 5) == 7  # exclude REJECT
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────────

def load_dna(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path).set_index("symbol")
    log.info("DNA profiles: %d symbols, status=%s, edge=%s",
             len(df),
             df["production_status"].value_counts().to_dict(),
             df["edge_confidence"].value_counts().to_dict())
    return df


def load_vnindex_bull(sma_period: int = 200) -> pd.Series:
    raw = pd.read_parquet(VNIDX_PATH)
    raw.columns = raw.columns.str.lower()
    raw["date"] = pd.to_datetime(raw["date"])
    raw = raw.drop_duplicates("date").sort_values("date").reset_index(drop=True)
    raw["sma200"] = raw["close"].rolling(sma_period, min_periods=sma_period // 2).mean()
    return pd.Series((raw["close"] > raw["sma200"]).values, index=raw["date"], name="is_bull")


# ─────────────────────────────────────────────────────────────────────────────
# Signal generation + trade outcome pre-computation
# ─────────────────────────────────────────────────────────────────────────────

def generate_signals(panels: Dict[str, pd.DataFrame],
                     is_bull: pd.Series) -> pd.DataFrame:
    rows: List[dict] = []
    for sym, df in panels.items():
        if len(df) < MIN_WARMUP:
            continue
        sig_series, _, _ = cloud_signal(df, A3_FAST, A3_SLOW)
        adv = df["adv50"] if "adv50" in df.columns else pd.Series(np.nan, index=df.index)

        for bar in sig_series[sig_series].index:
            if bar + 1 >= len(df):
                continue
            entry_bar  = bar + 1
            signal_date = pd.Timestamp(df["date"].iloc[bar])
            entry_date  = pd.Timestamp(df["date"].iloc[entry_bar])

            adv_val = float(adv.iloc[bar]) if pd.notna(adv.iloc[bar]) else 0.0
            if adv_val < MIN_ADV_VND:
                continue

            bull_val = bool(is_bull.reindex([signal_date], method="ffill").iloc[0])
            rows.append({
                "symbol":      sym,
                "signal_bar":  bar,
                "signal_date": signal_date,
                "entry_date":  entry_date,
                "is_bull":     bull_val,
                "adv50":       adv_val,
            })

    df_out = pd.DataFrame(rows)
    df_out = df_out[df_out["entry_date"] >= SIM_START].copy()
    log.info("Signals: %d total (%d BULL / %d BEAR)",
             len(df_out), df_out["is_bull"].sum(), (~df_out["is_bull"]).sum())
    return df_out


def precompute_outcomes(signals: pd.DataFrame,
                        panels: Dict[str, pd.DataFrame],
                        breadth: pd.Series) -> pd.DataFrame:
    """
    Pre-compute (blended_net_return, exit_date) for every signal.
    exit_date resolved via actual calendar date in sym_df (not bar-count assumption).
    Both T1 and T2 legs use simulate_a3_trade_exact for return (breadth filter active).
    exit_bar_offset from _simulate_s3_trade for slot occupancy only.
    """
    rows: List[dict] = []
    skipped = 0

    for _, sig in signals.iterrows():
        sym    = sig["symbol"]
        sym_df = panels.get(sym)
        if sym_df is None:
            skipped += 1; continue

        sig_bar   = int(sig["signal_bar"])
        entry_bar = sig_bar + 1
        if entry_bar >= len(sym_df):
            skipped += 1; continue

        atr = _atr14(sym_df).values

        # ── Return via simulate_a3_trade_exact (breadth filter) ──────────────
        result = simulate_a3_trade_exact(sig_bar, sym_df, atr, breadth)
        if result is None or np.isnan(result.get("blended_net_return", np.nan)):
            skipped += 1; continue

        blended   = float(result["blended_net_return"])
        t2_filled = bool(result.get("t2_filled", False))

        # ── Exit bar via _simulate_s3_trade (slot occupancy only) ────────────
        t1 = _simulate_s3_trade(
            sig_bar, sym_df, atr,
            tp1_pct=A3_TP1_PCT, tp1_size=A3_TP1_SIZE,
            trail_mult=A3_TRAIL_MULT, max_hold=A3_MAX_HOLD, cost_rt=COST_RT,
        )
        t1_off = int((t1.get("exit_bar_offset") or A3_MAX_HOLD)) if t1 else A3_MAX_HOLD

        # Resolve exit date from actual calendar (not bar-count assumption)
        exit_bar_abs = min(entry_bar + t1_off, len(sym_df) - 1)
        exit_date    = pd.Timestamp(sym_df["date"].iloc[exit_bar_abs])

        rows.append({
            **sig.to_dict(),
            "blended_net": blended,
            "exit_date":   exit_date,
            "exit_bar_off": t1_off,
            "t2_filled":   t2_filled,
            "t1_tp1_hit":  bool(result.get("t1_tp1_hit", False)),
        })

    log.info("Trade outcomes: %d valid, %d skipped", len(rows), skipped)
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    out["signal_date"] = pd.to_datetime(out["signal_date"])
    out["entry_date"]  = pd.to_datetime(out["entry_date"])
    out["exit_date"]   = pd.to_datetime(out["exit_date"])
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Day-by-day slot simulation
# ─────────────────────────────────────────────────────────────────────────────

def run_slot_sim(
    config: str,
    trades_pre: pd.DataFrame,
    bucket_map: Dict[str, int],
    placebo_map: Optional[Dict[str, int]] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Day-by-day slot simulation.

    Returns:
      accepted_df  -- accepted trades with entry/exit/return
      rejected_df  -- rejected trades with reason (filter|capacity)
      slot_log_df  -- daily slot occupancy log
    """
    # Pre-build: entry_date -> list of trade rows (sorted will happen per day)
    by_entry: Dict[pd.Timestamp, List[dict]] = defaultdict(list)
    for _, row in trades_pre.iterrows():
        by_entry[row["entry_date"]].append(row.to_dict())

    all_entry_dates = sorted(by_entry.keys())

    accepted_list:  List[dict] = []
    rejected_list:  List[dict] = []
    slot_log:       List[dict] = []

    # Slot occupancy: list of exit_dates for currently occupied slots
    occupied: List[pd.Timestamp] = []

    for entry_dt in all_entry_dates:
        # Release slots that exited BEFORE this entry date
        occupied = [ed for ed in occupied if ed >= entry_dt]
        free     = N_SLOTS - len(occupied)

        day_sigs = by_entry[entry_dt]

        # Sort by config-specific priority (lower = higher priority)
        day_sigs.sort(key=lambda r: build_config_sort_key(
            config, r["symbol"], bucket_map, placebo_map))

        for sig in day_sigs:
            sym    = sig["symbol"]
            bucket = bucket_map.get(sym, 5)

            # Hard filter check
            if is_excluded(config, sym, bucket_map):
                rejected_list.append({**sig,
                    "config": config, "reject_reason": "filter_excluded",
                    "bucket": bucket})
                continue

            # Capacity check
            if free <= 0:
                rejected_list.append({**sig,
                    "config": config, "reject_reason": "capacity",
                    "bucket": bucket})
                continue

            # Accept
            accepted_list.append({**sig, "config": config, "bucket": bucket,
                                   "bucket_label": BUCKET_LABELS.get(bucket, "UNKNOWN")})
            occupied.append(sig["exit_date"])
            free -= 1

        slot_log.append({
            "date":     entry_dt,
            "config":   config,
            "occupied": N_SLOTS - free,
            "free":     free,
            "util_pct": (N_SLOTS - free) / N_SLOTS * 100,
        })

    acc_df = pd.DataFrame(accepted_list) if accepted_list else pd.DataFrame()
    rej_df = pd.DataFrame(rejected_list) if rejected_list else pd.DataFrame()
    slt_df = pd.DataFrame(slot_log)      if slot_log      else pd.DataFrame()

    log.info("[%s] accepted=%d  cap_rej=%d  filter_rej=%d  avg_util=%.1f%%",
             config,
             len(acc_df),
             len(rej_df[rej_df["reject_reason"] == "capacity"]) if not rej_df.empty else 0,
             len(rej_df[rej_df["reject_reason"] == "filter_excluded"]) if not rej_df.empty else 0,
             slt_df["util_pct"].mean() if not slt_df.empty else 0)

    return acc_df, rej_df, slt_df


# ─────────────────────────────────────────────────────────────────────────────
# Equity curve + metrics
# ─────────────────────────────────────────────────────────────────────────────

def build_equity_curve(accepted: pd.DataFrame) -> pd.DataFrame:
    """
    Equity curve from accepted slot trades.
    On each exit_date: equity *= (1 + blended_net / N_SLOTS).
    Multiple exits same day: compound sequentially.
    Returns DataFrame with columns [date, equity].
    """
    if accepted.empty or "blended_net" not in accepted.columns:
        return pd.DataFrame(columns=["date", "equity"])

    # Group by exit_date, compute combined daily factor
    daily = accepted.groupby("exit_date")["blended_net"].apply(
        lambda rets: np.prod([1.0 + r * SLOT_FRAC for r in rets])
    ).reset_index()
    daily.columns = ["date", "daily_factor"]
    daily = daily.sort_values("date").reset_index(drop=True)

    # Prepend start
    start_row = pd.DataFrame([{"date": SIM_START, "daily_factor": 1.0}])
    daily = pd.concat([start_row, daily], ignore_index=True)

    daily["equity"] = daily["daily_factor"].cumprod()
    return daily[["date", "equity"]].copy()


def compute_metrics(equity: pd.DataFrame, config: str,
                    accepted: pd.DataFrame, slot_log: pd.DataFrame,
                    rejected: pd.DataFrame) -> dict:
    """Compute CAGR, MaxDD, MAR plus trade diagnostics."""
    m: dict = {"config": config, "label": SIM_LABEL}

    if equity.empty or len(equity) < 2:
        m["error"] = "insufficient_data"
        return m

    eq = equity.sort_values("date").copy()
    start_val = float(eq["equity"].iloc[0])
    end_val   = float(eq["equity"].iloc[-1])
    n_years   = (eq["date"].iloc[-1] - eq["date"].iloc[0]).days / 365.25

    cagr   = (end_val / start_val) ** (1.0 / n_years) - 1.0 if n_years > 0 else 0.0
    roll_max = eq["equity"].cummax()
    dd       = (eq["equity"] - roll_max) / roll_max
    max_dd   = float(abs(dd.min()))
    mar      = cagr / max_dd if max_dd > 1e-6 else np.nan

    m.update({
        "cagr":    round(cagr,   4),
        "max_dd":  round(max_dd, 4),
        "mar":     round(float(mar) if not np.isnan(mar) else 0.0, 4),
        "n_years": round(n_years, 2),
    })

    # Trade diagnostics
    if not accepted.empty and "blended_net" in accepted.columns:
        rets = accepted["blended_net"].dropna()
        m["n_trades"]       = len(rets)
        m["win_rate"]       = round(float((rets > 0).mean()), 4)
        m["avg_ret"]        = round(float(rets.mean()), 4)
        m["median_ret"]     = round(float(rets.median()), 4)
        m["cash_drag_pct"]  = round(
            100.0 - slot_log["util_pct"].mean() if not slot_log.empty else 0.0, 2)
        m["pct_days_full"]  = round(
            float((slot_log["util_pct"] >= 100.0).mean() * 100) if not slot_log.empty else 0.0, 2)
        m["avg_util_pct"]   = round(
            float(slot_log["util_pct"].mean()) if not slot_log.empty else 0.0, 2)

    # Rejection counts
    if not rejected.empty:
        rc = rejected["reject_reason"].value_counts().to_dict()
        m["cap_rejections"]    = int(rc.get("capacity", 0))
        m["filter_rejections"] = int(rc.get("filter_excluded", 0))
    else:
        m["cap_rejections"]    = 0
        m["filter_rejections"] = 0

    return m


def annual_returns(accepted: pd.DataFrame) -> pd.DataFrame:
    """Per-year CAGR-equivalent from slot trades."""
    if accepted.empty or "blended_net" not in accepted.columns:
        return pd.DataFrame()
    acc = accepted.copy()
    acc["exit_year"] = pd.to_datetime(acc["exit_date"]).dt.year
    yr_rows = []
    for yr, grp in acc.groupby("exit_year"):
        rets   = grp["blended_net"].dropna()
        yr_ret = float(np.prod([1.0 + r * SLOT_FRAC for r in rets])) - 1.0
        yr_rows.append({"year": yr, "annual_ret": round(yr_ret, 4),
                        "n_trades": len(rets), "avg_ret": round(rets.mean(), 4)})
    return pd.DataFrame(yr_rows)


def bucket_breakdown(accepted: pd.DataFrame, rejected: pd.DataFrame) -> pd.DataFrame:
    """Accepted/rejected counts by DNA tier bucket."""
    rows = []
    for bucket, label in BUCKET_LABELS.items():
        n_acc = int((accepted["bucket"] == bucket).sum()) if not accepted.empty and "bucket" in accepted.columns else 0
        n_rej = int((rejected["bucket"] == bucket).sum()) if not rejected.empty and "bucket" in rejected.columns else 0
        rows.append({"bucket": bucket, "label": label,
                     "accepted": n_acc, "rejected": n_rej,
                     "total": n_acc + n_rej})
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Acceptance gate check
# ─────────────────────────────────────────────────────────────────────────────

def check_acceptance(m: dict, baseline_m: dict) -> dict:
    """
    AND-gate: CAGR >= baseline AND MaxDD <= baseline.
    Soft OR-gate: (CAGR slightly lower) AND (MAR materially better) reported separately.
    """
    b_cagr  = baseline_m.get("cagr",   0)
    b_maxdd = baseline_m.get("max_dd", 1)
    b_mar   = baseline_m.get("mar",    0)
    c_cagr  = m.get("cagr",   0)
    c_maxdd = m.get("max_dd", 1)
    c_mar   = m.get("mar",    0)

    and_pass = (c_cagr >= b_cagr) and (c_maxdd <= b_maxdd)
    soft_pass = (c_cagr >= b_cagr * 0.97) and (c_mar >= b_mar * 1.15) and (c_maxdd <= b_maxdd)
    return {
        "and_gate":  "PASS" if and_pass  else "FAIL",
        "soft_gate": "PASS" if soft_pass else "FAIL",
    }


def check_red_flags(m: dict) -> List[str]:
    flags = []
    if m.get("cagr", 0) > 0.30:
        flags.append(f"CAGR={m['cagr']:.1%} > 30% => likely lookahead bug")
    if m.get("max_dd", 1) < 0.05:
        flags.append(f"MaxDD={m['max_dd']:.1%} < 5% => missing drawdown events")
    if m.get("mar", 0) > 2.0:
        flags.append(f"MAR={m['mar']:.2f} > 2.0 => almost certainly a bug")
    if m.get("n_trades", 0) < 50:
        flags.append(f"n_trades={m.get('n_trades',0)} < 50 => insufficient sample")
    return flags


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("=" * 72)
    log.info("DNA x A3 SLOT-CONSTRAINED PRIORITY SIM | %s", SIM_LABEL)
    log.info(LOOKAHEAD_NOTE)
    log.info("=" * 72)

    today_str = Date.today().isoformat()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)

    # ── 1. Load data ──────────────────────────────────────────────────────────
    log.info("Loading panel (ex_vin=True)...")
    panels  = load_panel(ex_vin=True)
    log.info("Panel: %d symbols", len(panels))

    log.info("Loading VNIndex SMA200 regime...")
    is_bull = load_vnindex_bull()
    log.info("Regime: %.1f%% BULL / %.1f%% BEAR", is_bull.mean() * 100, (1 - is_bull.mean()) * 100)

    log.info("Loading DNA profiles...")
    dna = load_dna(DNA_CSV)
    bucket_map = build_priority_map(dna)

    # Placebo map: permute bucket values across symbols (seed=42)
    rng         = random.Random(PLACEBO_SEED)
    syms_list   = list(bucket_map.keys())
    buckets_shuf = list(bucket_map.values())
    rng.shuffle(buckets_shuf)
    placebo_map: Dict[str, int] = dict(zip(syms_list, buckets_shuf))
    log.info("Placebo map built (seed=%d): %d symbols shuffled", PLACEBO_SEED, len(placebo_map))

    # Bucket distribution
    bucket_counts = defaultdict(int)
    for b in bucket_map.values():
        bucket_counts[b] += 1
    log.info("Bucket distribution: %s",
             {BUCKET_LABELS[k]: v for k, v in sorted(bucket_counts.items())})

    # ── 2. Generate signals + pre-compute outcomes ────────────────────────────
    log.info("Generating A3 signals...")
    signals = generate_signals(panels, is_bull)
    if signals.empty:
        log.error("No signals -- aborting.")
        sys.exit(1)

    log.info("Loading breadth series...")
    try:
        breadth = load_breadth()
        log.info("Breadth: %d dates", len(breadth))
    except Exception as e:
        log.warning("Breadth load failed (%s) -- T2 quality gate bypassed", e)
        breadth = pd.Series(dtype=float)

    log.info("Pre-computing trade outcomes (one-time, ~5s)...")
    trades_pre = precompute_outcomes(signals, panels, breadth)
    if trades_pre.empty:
        log.error("No trade outcomes -- aborting.")
        sys.exit(1)

    log.info("Outcomes: %d trades | avg_hold=%.0f bars | median_net=%.1f%%",
             len(trades_pre),
             trades_pre["exit_bar_off"].mean(),
             trades_pre["blended_net"].median() * 100)

    # ── 3. Run all configs ────────────────────────────────────────────────────
    all_metrics:    List[dict]        = []
    all_equity:     List[pd.DataFrame] = []
    all_annual:     List[pd.DataFrame] = []
    all_trades:     List[pd.DataFrame] = []
    all_rejected:   List[pd.DataFrame] = []
    all_slots:      List[pd.DataFrame] = []
    all_bucket_bkd: List[pd.DataFrame] = []

    baseline_m: dict = {}

    for cfg in CONFIGS:
        log.info("--- Config: %s ---", cfg)
        acc_df, rej_df, slt_df = run_slot_sim(
            cfg, trades_pre, bucket_map,
            placebo_map=placebo_map if cfg == "dna_random_permute" else None,
        )

        eq_df  = build_equity_curve(acc_df)
        m      = compute_metrics(eq_df, cfg, acc_df, slt_df, rej_df)
        ann_df = annual_returns(acc_df)
        bkd_df = bucket_breakdown(acc_df, rej_df)

        flags = check_red_flags(m)
        if flags:
            log.warning("[RED FLAGS -- %s]: %s", cfg, " | ".join(flags))

        log.info("[%s] CAGR=%.1f%%  MaxDD=%.1f%%  MAR=%.2f  n=%d  util=%.1f%%",
                 cfg,
                 m.get("cagr", 0) * 100,
                 m.get("max_dd", 0) * 100,
                 m.get("mar", 0),
                 m.get("n_trades", 0),
                 m.get("avg_util_pct", 0))

        if cfg == "a3_baseline_slot":
            baseline_m = m

        # Acceptance gate (skip for baseline and placebo)
        if cfg not in ("a3_baseline_slot", "dna_random_permute") and baseline_m:
            gates = check_acceptance(m, baseline_m)
            m.update(gates)
            log.info("[%s] AND-gate=%s  soft-gate=%s", cfg, gates["and_gate"], gates["soft_gate"])
        else:
            m["and_gate"]  = "N/A"
            m["soft_gate"] = "N/A"

        m["red_flags"] = "; ".join(flags) if flags else "none"

        # Tag annual/bucket DFs with config
        ann_df["config"] = cfg
        bkd_df["config"] = cfg
        if not acc_df.empty: acc_df["config"] = cfg
        if not rej_df.empty: rej_df["config"] = cfg

        all_metrics.append(m)
        all_equity.append(eq_df.assign(config=cfg))
        all_annual.append(ann_df)
        all_trades.append(acc_df)
        all_rejected.append(rej_df)
        all_slots.append(slt_df)
        all_bucket_bkd.append(bkd_df)

    # ── 4. Post-2017 robustness slice (in-sample note) ────────────────────────
    log.info("--- Computing post-2017 robustness slice (DNA fit starts 2017) ---")
    post17_pre = trades_pre[trades_pre["entry_date"] >= POST17_START].copy()
    post17_metrics: List[dict] = []
    for cfg in CONFIGS:
        acc_df, rej_df, slt_df = run_slot_sim(
            cfg, post17_pre, bucket_map,
            placebo_map=placebo_map if cfg == "dna_random_permute" else None,
        )
        eq_df = build_equity_curve(acc_df)
        if not eq_df.empty and len(eq_df) > 1:
            # Re-anchor equity to start at 1.0 from POST17_START
            first_val = float(eq_df["equity"].iloc[0])
            eq_df["equity"] = eq_df["equity"] / first_val
        m = compute_metrics(eq_df, cfg + "_post17", acc_df, slt_df, rej_df)
        m["slice"] = "post2017"
        post17_metrics.append(m)
        log.info("[%s_post17] CAGR=%.1f%%  MaxDD=%.1f%%  MAR=%.2f  n=%d",
                 cfg,
                 m.get("cagr", 0) * 100,
                 m.get("max_dd", 0) * 100,
                 m.get("mar", 0),
                 m.get("n_trades", 0))

    # ── 5. Build output tables ────────────────────────────────────────────────
    pareto_cols = ["config", "cagr", "max_dd", "mar", "n_trades",
                   "win_rate", "avg_ret", "median_ret",
                   "avg_util_pct", "pct_days_full", "cash_drag_pct",
                   "cap_rejections", "filter_rejections",
                   "and_gate", "soft_gate", "red_flags"]

    def _fmt_metrics(mlist):
        rows = []
        for m in mlist:
            row = {k: m.get(k, "--") for k in pareto_cols if k in m or k in
                   ["config","and_gate","soft_gate","red_flags"]}
            row["cagr"]    = f"{m.get('cagr', 0):.1%}"
            row["max_dd"]  = f"{m.get('max_dd', 0):.1%}"
            row["mar"]     = f"{m.get('mar', 0):.2f}"
            row["avg_ret"] = f"{m.get('avg_ret', 0):.1%}"
            row["median_ret"] = f"{m.get('median_ret', 0):.1%}"
            rows.append(row)
        return pd.DataFrame(rows)

    pareto_df     = _fmt_metrics(all_metrics)
    pareto_post17 = _fmt_metrics(post17_metrics)

    eq_all    = pd.concat(all_equity,   ignore_index=True) if all_equity   else pd.DataFrame()
    ann_all   = pd.concat(all_annual,   ignore_index=True) if all_annual   else pd.DataFrame()
    tl_all    = pd.concat(all_trades,   ignore_index=True) if all_trades   else pd.DataFrame()
    rej_all   = pd.concat(all_rejected, ignore_index=True) if all_rejected else pd.DataFrame()
    bkd_all   = pd.concat(all_bucket_bkd, ignore_index=True) if all_bucket_bkd else pd.DataFrame()

    # ── 6. Save CSVs ──────────────────────────────────────────────────────────
    pareto_path   = OUT_DIR / f"slot_sim_pareto_{today_str}.csv"
    post17_path   = OUT_DIR / f"slot_sim_pareto_post17_{today_str}.csv"
    eq_path       = OUT_DIR / f"slot_sim_equity_{today_str}.csv"
    ann_path      = OUT_DIR / f"slot_sim_annual_{today_str}.csv"
    tl_path       = OUT_DIR / f"slot_sim_trades_{today_str}.csv"
    rej_path      = OUT_DIR / f"slot_sim_rejected_{today_str}.csv"
    bkd_path      = OUT_DIR / f"slot_sim_bucket_breakdown_{today_str}.csv"

    pareto_df.to_csv(pareto_path, index=False)
    pareto_post17.to_csv(post17_path, index=False)
    eq_all.to_csv(eq_path, index=False)
    ann_all.to_csv(ann_path, index=False)
    if not tl_all.empty:  tl_all.to_csv(tl_path, index=False)
    if not rej_all.empty: rej_all.to_csv(rej_path, index=False)
    if not bkd_all.empty: bkd_all.to_csv(bkd_path, index=False)

    # ── 7. Run log ────────────────────────────────────────────────────────────
    pareto_md = pareto_df.to_markdown(index=False) if hasattr(pareto_df, "to_markdown") \
                else pareto_df.to_string()
    post17_md = pareto_post17.to_markdown(index=False) if hasattr(pareto_post17, "to_markdown") \
                else pareto_post17.to_string()

    # By-year pivot (baseline vs dna_priority_slot)
    year_pivot_md = ""
    if not ann_all.empty:
        cfgs_to_show = ["a3_baseline_slot", "dna_priority_slot", "dna_danger_exclude", "dna_random_permute"]
        ann_sub = ann_all[ann_all["config"].isin(cfgs_to_show)].copy()
        if not ann_sub.empty:
            ann_sub["annual_pct"] = (ann_sub["annual_ret"] * 100).round(1).astype(str) + "%"
            pivot = ann_sub.pivot_table(index="year", columns="config", values="annual_pct", aggfunc="first")
            year_pivot_md = pivot.to_markdown() if hasattr(pivot, "to_markdown") else pivot.to_string()

    run_log = f"""# DNA x A3 Slot-Constrained Priority Sim — Run Log
Date: {today_str}
{SIM_LABEL}
{STATUS_LABEL}

## Disclosures
{LOOKAHEAD_NOTE}
Priority taxonomy: SUPPORT_ALIGNED proxied by production_status=RESEARCH_ANNOTATION_ONLY + edge_confidence tier.
Danger proxied by production_status=REJECT. No price-vs-support-line geometry computed.
Baseline ordering: symbol alpha (no DNA). All configs use identical stable tiebreak.
Exit dates: resolved via actual calendar date per symbol (not bar-count assumption).
Placebo config: DNA buckets randomly permuted (seed={PLACEBO_SEED}) -- null distribution.

## A3 Frozen Contract
- EMA cloud: fast={A3_FAST}, slow={A3_SLOW}
- TP1: +{A3_TP1_PCT:.0%} on {A3_TP1_SIZE:.0%} | T2: >={A3_T2_PULLBACK:.0%} within {A3_T2_WINDOW} bars
- Trail: {A3_TRAIL_MULT}x ATR14 | max_hold {A3_MAX_HOLD} bars | cost {COST_BPS}bps rt
- Min ADV: {MIN_ADV_VND/1e9:.1f}B VND | N_SLOTS={N_SLOTS} | pos=1/{N_SLOTS}

## Universe
- Panel: {len(panels)} symbols | DNA profiles: {len(dna)} | Bucket map: {len(bucket_map)}
- Trade outcomes pre-computed: {len(trades_pre)}

## Full-Period Pareto Table (2013-2026, IN-SAMPLE)
{pareto_md}

## Post-2017 Robustness Slice (DNA fit window starts 2017)
{post17_md}

## By-Year Returns (selected configs)
{year_pivot_md}

## Acceptance Rule
AND-gate: CAGR >= baseline AND MaxDD <= baseline (primary)
Soft-gate: CAGR >= baseline*0.97 AND MAR >= baseline*1.15 AND MaxDD <= baseline (secondary)
Baseline: a3_baseline_slot
Placebo benchmark: dna_random_permute -- DNA must materially beat permutation null.

## Files
- {pareto_path.name}
- {post17_path.name}
- {eq_path.name}
- {ann_path.name}
- {tl_path.name if tl_all is not None and not tl_all.empty else 'slot_sim_trades (empty)'}
- {rej_path.name if rej_all is not None and not rej_all.empty else 'slot_sim_rejected (empty)'}
- {bkd_path.name if bkd_all is not None and not bkd_all.empty else 'slot_sim_bucket_breakdown (empty)'}

## Suggested Next Prompt for ChatGPT
"DNA slot-priority sim complete. 6 configs + post-2017 robustness slice + placebo.
Pareto: [paste table]. AND-gate results: [list]. Placebo (dna_random_permute) vs real DNA: [compare CAGR/MAR].
Decision: if real DNA configs fail to beat placebo materially, stop DNA promotion path.
If any config passes AND-gate AND beats placebo: proceed to walk-forward refit discussion."
"""

    log_path = OUT_DIR / f"slot_sim_run_log_{today_str}.md"
    log_path.write_text(run_log, encoding="utf-8")

    # ── 8. Zip review outputs ─────────────────────────────────────────────────
    zip_path = REVIEW_DIR / f"dna_a3_slot_priority_{today_str}.zip"
    output_files = [pareto_path, post17_path, eq_path, ann_path, log_path]
    if tl_all is not None and not tl_all.empty:   output_files.append(tl_path)
    if rej_all is not None and not rej_all.empty: output_files.append(rej_path)
    if bkd_all is not None and not bkd_all.empty: output_files.append(bkd_path)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in output_files:
            if p.exists():
                zf.write(p, arcname=p.name)
        # Include source script snapshot
        zf.write(Path(__file__), arcname="run_dna_a3_slot_priority_sim.py")

    # ── 9. Final summary ──────────────────────────────────────────────────────
    log.info("=" * 72)
    log.info("SLOT SIM FINAL PARETO (full period)")
    log.info("=" * 72)
    for m in all_metrics:
        log.info("  %-35s CAGR=%5.1f%%  MaxDD=%5.1f%%  MAR=%4.2f  n=%4d  util=%4.1f%%  [AND=%s]",
                 m.get("config", ""),
                 m.get("cagr", 0) * 100,
                 m.get("max_dd", 0) * 100,
                 m.get("mar", 0),
                 m.get("n_trades", 0),
                 m.get("avg_util_pct", 0),
                 m.get("and_gate", "N/A"))
    log.info("=" * 72)
    log.info("POST-2017 ROBUSTNESS SLICE")
    log.info("=" * 72)
    for m in post17_metrics:
        log.info("  %-40s CAGR=%5.1f%%  MaxDD=%5.1f%%  MAR=%4.2f  n=%4d",
                 m.get("config", ""),
                 m.get("cagr", 0) * 100,
                 m.get("max_dd", 0) * 100,
                 m.get("mar", 0),
                 m.get("n_trades", 0))
    log.info("=" * 72)
    log.info("Review zip -> %s", zip_path)
    log.info("%s", SIM_LABEL)
    log.info("%s", LOOKAHEAD_NOTE)


if __name__ == "__main__":
    main()
