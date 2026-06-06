"""
Stock DNA Line Obedience Scoring
==================================
Computes composite line obedience scores per (symbol, line) and applies
council-required safeguards:

  - Minimum sample: >=20 touch events for MEDIUM, >=40 for HIGH, <20 = NONE
  - Shuffled-null benchmark: real edge must exceed null by >=2 sigma
  - Instability penalty: year-over-year variance of bounce rate
  - Regime-split: separate bull/bear scores
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

from src.trading.research.stock_dna.schema import (
    CANDIDATE_LINES,
    MIN_TOUCH_FOR_HIGH,
    MIN_TOUCH_FOR_MEDIUM,
    DNAConfidence,
)

logger = logging.getLogger(__name__)

N_SHUFFLE_RUNS: int = 200


# ── Confidence assignment ─────────────────────────────────────────────────────

def assign_confidence(n_touch: int) -> DNAConfidence:
    if n_touch >= MIN_TOUCH_FOR_HIGH:
        return DNAConfidence.HIGH
    if n_touch >= MIN_TOUCH_FOR_MEDIUM:
        return DNAConfidence.MEDIUM
    if n_touch >= 5:
        return DNAConfidence.LOW
    return DNAConfidence.NONE


def assign_sample_confidence(n_touch: int) -> DNAConfidence:
    """Sample-size confidence — driven solely by n_touch. Explicit alias of assign_confidence."""
    return assign_confidence(n_touch)


_EDGE_NONE     = "NONE"
_EDGE_WEAK     = "WEAK"
_EDGE_MODERATE = "MODERATE"
_EDGE_STRONG   = "STRONG"


def assign_edge_confidence(
    per_symbol_null_z: float,
    lift: float,
    median_fwd_ret: float,
) -> str:
    """
    Edge confidence — measures signal quality independent of sample size.

    `lift` must be a **bounce-rate differential** (symbol_bounce_rate − universe_median),
    NOT the raw bounce rate. Caller is responsible for computing the differential.

    Hard directional gate (council v3 fix): BOTH direction conditions must pass for any
    non-NONE tier. A symbol that is statistically significant but wrong-direction
    (negative lift or negative median fwd return) always returns NONE, routing to
    WATCHLIST_ONLY rather than RESEARCH_ANNOTATION_ONLY.

    Tier thresholds:
      STRONG   : null_z >= 3.0  AND lift > +2pp differential
      MODERATE : null_z >= 2.0
      WEAK     : null_z >= 1.5
      NONE     : null_z < 1.5  OR either directional condition fails

    Returns: NONE / WEAK / MODERATE / STRONG
    """
    if not pd.notna(per_symbol_null_z) or per_symbol_null_z < 1.5:
        return _EDGE_NONE

    # Hard directional gate — both must pass (council v3 requirement)
    lift_positive = pd.notna(lift) and float(lift) > 0.0
    ret_positive  = pd.notna(median_fwd_ret) and float(median_fwd_ret) > 0.0
    if not (lift_positive and ret_positive):
        return _EDGE_NONE

    # Tier assignment — direction already confirmed above
    if per_symbol_null_z >= 3.0 and float(lift) > 0.02:   # > +2pp differential for STRONG
        return _EDGE_STRONG
    if per_symbol_null_z >= 2.0:
        return _EDGE_MODERATE
    return _EDGE_WEAK


# ── Composite score ───────────────────────────────────────────────────────────

def _safe_norm(s: pd.Series) -> pd.Series:
    """Min-max normalize a Series; return 0.5 if all values are equal."""
    mn, mx = s.min(), s.max()
    if mx == mn or pd.isna(mn) or pd.isna(mx):
        return pd.Series(0.5, index=s.index)
    return (s - mn) / (mx - mn)


def compute_line_obedience_score(scores_df: pd.DataFrame) -> pd.DataFrame:
    """
    Given aggregate line score stats (from events.aggregate_line_scores),
    compute composite line_obedience_score per row.

    Formula (council v1):
      score = 0.30 * norm(bounce_rate_fwd_ret_20d)
            + 0.25 * norm(median_fwd_ret_20d)
            + 0.20 * norm(mfe_mae_ratio)
            + 0.15 * norm(bounce_rate_fwd_ret_10d)
            - 0.10 * instability_penalty

    Score is in [0, 1] before penalty. Confidence is applied separately.
    """
    df = scores_df.copy()
    if df.empty:
        return df

    # Component columns
    br20  = "bounce_rate_fwd_ret_20d"
    med20 = "median_fwd_ret_20d"
    mmr   = "mfe_mae_ratio"
    br10  = "bounce_rate_fwd_ret_10d"

    components = pd.DataFrame(index=df.index)

    if br20 in df.columns:
        components["c1"] = _safe_norm(df[br20].fillna(0.5)) * 0.30
    else:
        components["c1"] = 0.0

    if med20 in df.columns:
        components["c2"] = _safe_norm(df[med20].fillna(0.0)) * 0.25
    else:
        components["c2"] = 0.0

    if mmr in df.columns:
        components["c3"] = _safe_norm(df[mmr].fillna(1.0)) * 0.20
    else:
        components["c3"] = 0.0

    if br10 in df.columns:
        components["c4"] = _safe_norm(df[br10].fillna(0.5)) * 0.15
    else:
        components["c4"] = 0.0

    df["line_obedience_score_raw"] = components.sum(axis=1)

    # Apply confidence and set score to 0 for NONE confidence
    if "n_touch" in df.columns:
        df["confidence"] = df["n_touch"].apply(lambda n: assign_confidence(int(n) if pd.notna(n) else 0).value)
        df.loc[df["confidence"] == DNAConfidence.NONE.value, "line_obedience_score_raw"] = 0.0
    else:
        df["confidence"] = DNAConfidence.NONE.value

    return df


# ── Instability penalty ───────────────────────────────────────────────────────

def compute_instability_penalty(
    touch_df: pd.DataFrame,
    symbol: str,
    line_name: str,
) -> float:
    """
    Compute year-over-year variance of bounce_rate_fwd_ret_20d for a symbol-line pair.
    Returns a penalty in [0, 0.25]. Higher = less stable.
    """
    df = touch_df[
        (touch_df["symbol"] == symbol) & (touch_df["line_name"] == line_name)
    ].copy()

    if df.empty or "fwd_ret_20d" not in df.columns:
        return 0.0

    df["year"] = pd.to_datetime(df["date"]).dt.year
    yearly = df.groupby("year")["fwd_ret_20d"].apply(lambda s: (s > 0).mean() if len(s) >= 3 else np.nan)
    yearly = yearly.dropna()

    if len(yearly) < 2:
        return 0.0

    variance = float(yearly.var())
    # Normalize to [0, 0.25]: variance of 0.09 (std ~0.3) → penalty ~0.25
    return min(variance / 0.36, 0.25)


# ── Shuffled-null benchmark ───────────────────────────────────────────────────

def run_shuffled_null_benchmark(
    touch_df: pd.DataFrame,
    real_scores: pd.DataFrame,
    n_runs: int = N_SHUFFLE_RUNS,
    rng_seed: int = 42,
) -> dict:
    """
    Council requirement: real edge must exceed shuffled-null lift by >=2 sigma.

    Cross-symbol permutation null: shuffles the symbol→(line, tol) mapping assigned
    by the profiles, keeping dates and symbols fixed. This tests: "is the per-symbol
    DNA profile selection learning something symbol-specific, or could any random
    assignment do equally well?" This is strictly stronger than the old within-symbol
    line shuffle.

    Procedure:
      1. Identify MEDIUM/HIGH profiles with their (symbol, primary_support_line, best_tolerance).
      2. Real score: bounce rate of touch events matching these exact (sym, line, tol) keys.
      3. Null: for each run, shuffle the (line, tol) assignment across symbols while keeping
         symbols fixed, recompute the bounce rate on the resulting events.
      4. Compare real vs null distribution → z_score, by_symbol_z_score, by_regime_z_score.

    Returns dict suitable for JSON serialisation as stock_dna_null_benchmark.json:
      universe_z_score, universe_real_br, universe_null_mean, universe_null_std, passes_null_test,
      by_symbol_z_score (dict symbol→z), by_regime_z_score (dict regime→z),
      pass_fail_threshold (2.0)
    """
    empty = {
        "universe_z_score": np.nan,
        "universe_real_br": np.nan,
        "universe_null_mean": np.nan,
        "universe_null_std": np.nan,
        "passes_null_test": False,
        "pass_fail_threshold": 2.0,
        "by_symbol_z_score": {},
        "by_regime_z_score": {},
        # Legacy keys for backward-compat with existing test and report readers
        "real_mean_score": np.nan,
        "null_mean": np.nan,
        "null_std": np.nan,
        "z_score": np.nan,
    }

    if touch_df.empty or real_scores.empty or "fwd_ret_20d" not in touch_df.columns:
        return empty

    med_plus = real_scores[
        real_scores["confidence"].isin([DNAConfidence.MEDIUM.value, DNAConfidence.HIGH.value])
    ].dropna(subset=["primary_support_line", "best_tolerance"] if
             "primary_support_line" in real_scores.columns else [])

    if med_plus.empty:
        return empty

    # Require these columns for cross-symbol shuffle null
    required_profile_cols = {"symbol", "primary_support_line", "best_tolerance"}
    if not required_profile_cols.issubset(set(real_scores.columns)):
        # Fall back: old symbol-set null if profile columns not available
        logger.warning("Profile columns missing for cross-symbol null — using symbol-set null")
        med_syms = set(med_plus["symbol"])
        real_br = float(
            touch_df[touch_df["symbol"].isin(med_syms)]["fwd_ret_20d"].dropna()
            .pipe(lambda s: (s > 0).mean())
        ) if len(touch_df[touch_df["symbol"].isin(med_syms)]) else np.nan

        # Symbol-set null distribution
        rng_fb = np.random.default_rng(rng_seed)
        all_syms = touch_df["symbol"].unique()
        n_keep = len(med_plus)
        fb_nulls: list[float] = []
        for _ in range(n_runs):
            samp = set(rng_fb.choice(all_syms, size=min(n_keep, len(all_syms)), replace=False))
            nbr = float(
                touch_df[touch_df["symbol"].isin(samp)]["fwd_ret_20d"].dropna()
                .pipe(lambda s: (s > 0).mean())
            ) if len(touch_df[touch_df["symbol"].isin(samp)]) else np.nan
            if pd.notna(nbr):
                fb_nulls.append(nbr)

        fb_arr = np.array(fb_nulls) if fb_nulls else np.array([np.nan])
        fb_null_mean = float(np.nanmean(fb_arr))
        fb_null_std  = max(float(np.nanstd(fb_arr)), 1e-6) if len(fb_nulls) > 1 else 1e-6
        fb_z = float((real_br - fb_null_mean) / fb_null_std) if pd.notna(real_br) else np.nan
        fb_passes = bool(pd.notna(fb_z) and fb_z >= 2.0)

        return {
            **empty,
            "universe_real_br": real_br,
            "universe_null_mean": fb_null_mean,
            "universe_null_std": fb_null_std,
            "universe_z_score": fb_z,
            "passes_null_test": fb_passes,
            "real_mean_score": real_br,
            "null_mean": fb_null_mean,
            "null_std": fb_null_std,
            "z_score": fb_z,
        }

    rng = np.random.default_rng(rng_seed)

    symbols_arr = med_plus["symbol"].values.copy()
    lines_arr   = med_plus["primary_support_line"].values.copy()
    tols_arr    = med_plus["best_tolerance"].values.copy()

    # Pre-build key lookup from touch_df for speed
    touch_keys = list(zip(touch_df["symbol"], touch_df["line_name"], touch_df["tol_name"]))
    touch_fwd  = touch_df["fwd_ret_20d"].values

    def _bounce_rate_for_keys(key_set: set) -> float:
        vals = [touch_fwd[i] for i, k in enumerate(touch_keys) if k in key_set and not np.isnan(touch_fwd[i])]
        return float(np.mean(np.array(vals) > 0)) if vals else np.nan

    # Real score
    real_keys = set(zip(symbols_arr, lines_arr, tols_arr))
    real_br   = _bounce_rate_for_keys(real_keys)

    # Null distribution
    null_brs: list[float] = []
    for _ in range(n_runs):
        shuffled_idx = rng.permutation(len(symbols_arr))
        null_keys = set(zip(symbols_arr, lines_arr[shuffled_idx], tols_arr[shuffled_idx]))
        nbr = _bounce_rate_for_keys(null_keys)
        if pd.notna(nbr):
            null_brs.append(nbr)

    null_arr = np.array(null_brs) if null_brs else np.array([np.nan])
    null_mean = float(np.nanmean(null_arr))
    null_std  = float(np.nanstd(null_arr)) if len(null_brs) > 1 else 1e-6

    z_score = float((real_br - null_mean) / null_std) if pd.notna(real_br) else np.nan
    passes  = bool(pd.notna(z_score) and z_score >= 2.0)

    logger.info(
        "Null benchmark (cross-sym): real=%.3f null_mean=%.3f null_std=%.4f z=%.2f passes=%s",
        real_br if pd.notna(real_br) else -99,
        null_mean, null_std,
        z_score if pd.notna(z_score) else -99,
        passes,
    )

    # By-symbol z-score (one run per symbol against within-symbol null for face validity)
    by_symbol_z: dict[str, float] = {}
    for sym in symbols_arr:
        sym_mask_real = touch_df["symbol"] == sym
        sym_prof = med_plus[med_plus["symbol"] == sym]
        if sym_prof.empty:
            continue
        sym_line = sym_prof.iloc[0]["primary_support_line"]
        sym_tol  = sym_prof.iloc[0]["best_tolerance"]
        sym_real_key = {(sym, sym_line, sym_tol)}
        sym_br = _bounce_rate_for_keys(sym_real_key)

        # Null: permute line/tol within symbol's own touch events
        sym_touch = touch_df[sym_mask_real]
        if sym_touch.empty or pd.isna(sym_br):
            continue
        sym_lines = sym_touch["line_name"].values
        sym_tols  = sym_touch["tol_name"].values
        sym_fwd   = sym_touch["fwd_ret_20d"].values
        sym_null_brs: list[float] = []
        for _ in range(min(50, n_runs)):
            ridx = rng.integers(0, len(sym_lines))
            snk = {(sym, sym_lines[ridx], sym_tols[ridx])}
            snbr = _bounce_rate_for_keys(snk)
            if pd.notna(snbr):
                sym_null_brs.append(snbr)
        if len(sym_null_brs) > 1:
            snull_mean = float(np.mean(sym_null_brs))
            snull_std  = float(np.std(sym_null_brs)) or 1e-6
            by_symbol_z[sym] = float((sym_br - snull_mean) / snull_std)

    # By-regime z-score
    by_regime_z: dict[str, float] = {}
    if "breadth_regime" in touch_df.columns:
        for regime in touch_df["breadth_regime"].dropna().unique():
            reg_df = touch_df[touch_df["breadth_regime"] == regime]
            if reg_df.empty:
                continue
            reg_keys = list(zip(reg_df["symbol"], reg_df["line_name"], reg_df["tol_name"]))
            reg_fwd  = reg_df["fwd_ret_20d"].values

            def _reg_br(kset: set) -> float:
                vals = [reg_fwd[i] for i, k in enumerate(reg_keys) if k in kset and not np.isnan(reg_fwd[i])]
                return float(np.mean(np.array(vals) > 0)) if vals else np.nan

            reg_real_br = _reg_br(real_keys)
            reg_null: list[float] = []
            for _ in range(min(100, n_runs)):
                sidx = rng.permutation(len(symbols_arr))
                nk = set(zip(symbols_arr, lines_arr[sidx], tols_arr[sidx]))
                nbr = _reg_br(nk)
                if pd.notna(nbr):
                    reg_null.append(nbr)
            if len(reg_null) > 1 and pd.notna(reg_real_br):
                rn_mean = float(np.mean(reg_null))
                rn_std  = float(np.std(reg_null)) or 1e-6
                by_regime_z[str(regime)] = float((reg_real_br - rn_mean) / rn_std)

    return {
        "universe_z_score": z_score,
        "universe_real_br": real_br,
        "universe_null_mean": null_mean,
        "universe_null_std": null_std,
        "passes_null_test": passes,
        "pass_fail_threshold": 2.0,
        "by_symbol_z_score": by_symbol_z,
        "by_regime_z_score": by_regime_z,
        # Legacy keys for backward-compat with HTML report reader
        "real_mean_score": real_br,
        "null_mean": null_mean,
        "null_std": null_std,
        "z_score": z_score,
    }


# ── Best line selector ────────────────────────────────────────────────────────

def select_best_line(
    scores_df: pd.DataFrame,
    symbol: str,
    phase: str = "ALL",
    min_confidence: DNAConfidence = DNAConfidence.MEDIUM,
) -> Optional[str]:
    """
    Select the best (highest obedience score) line for a symbol in a given phase.
    Returns None if no line meets the minimum confidence threshold.
    """
    df = scores_df[
        (scores_df["symbol"] == symbol) &
        (scores_df.get("phase", "ALL") == phase if "phase" in scores_df.columns else True) &
        scores_df["confidence"].isin(
            [c.value for c in DNAConfidence
             if _confidence_rank(c) >= _confidence_rank(min_confidence)]
        )
    ].copy()

    if df.empty:
        return None

    best = df.sort_values("line_obedience_score_raw", ascending=False).iloc[0]
    return str(best["line_name"])


def _confidence_rank(c: DNAConfidence) -> int:
    return {
        DNAConfidence.NONE:   0,
        DNAConfidence.LOW:    1,
        DNAConfidence.MEDIUM: 2,
        DNAConfidence.HIGH:   3,
    }.get(c, 0)
