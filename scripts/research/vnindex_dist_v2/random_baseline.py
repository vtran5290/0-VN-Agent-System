"""Random baselines: IID, spacing-matched sparse, year-histogram-matched."""
from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd


def eligible_pool(n: int, L: int, H: int, closes: np.ndarray) -> np.ndarray:
    lo = L - 1
    hi = n - 1 - H
    if hi < lo:
        return np.array([], dtype=int)
    idx = np.arange(lo, hi + 1, dtype=int)
    c = closes[idx]
    ok = np.isfinite(c) & (c > 0)
    return idx[ok]


def win_rate_at_indices(indices: np.ndarray, closes: np.ndarray, H: int) -> float:
    n = len(closes)
    if indices.size == 0:
        return float("nan")
    wins = 0
    tot = 0
    for j in indices.astype(int):
        jj = j + H
        if jj >= n:
            continue
        c0, c1 = closes[j], closes[jj]
        if not (np.isfinite(c0) and np.isfinite(c1) and c0 > 0):
            continue
        tot += 1
        if c1 > c0:
            wins += 1
    return wins / float(tot) if tot else float("nan")


def mc_random_win_rates(
    observed_win_rate: float,
    n_regime: int,
    pool: np.ndarray,
    closes: np.ndarray,
    H: int,
    reps: int,
    rng: np.random.Generator,
) -> dict:
    if n_regime <= 0 or pool.size == 0 or reps <= 0:
        return _empty_mc("IID_draws_no_spacing_match", n_regime, pool.size, reps)
    wrs = np.empty(reps, dtype=float)
    n = len(closes)
    for t in range(reps):
        samp = rng.choice(pool, size=n_regime, replace=True)
        wrs[t] = win_rate_at_indices(samp, closes, H)
    return _summarize_mc(wrs, observed_win_rate, n_regime, pool.size, reps, "IID_draws_no_spacing_match")


def _empty_mc(note: str, n_regime: int, pool_size: int, reps: int) -> dict:
    return {
        "n_regime": int(n_regime),
        "pool_size": int(pool_size),
        "reps": int(reps),
        "random_win_rate_median": float("nan"),
        "random_win_rate_p05": float("nan"),
        "random_win_rate_p95": float("nan"),
        "uplift_vs_random_median": float("nan"),
        "empirical_p_value_one_sided_smoothed": float("nan"),
        "note": note,
    }


def _summarize_mc(
    wrs: np.ndarray,
    observed_win_rate: float,
    n_regime: int,
    pool_size: int,
    reps: int,
    note: str,
) -> dict:
    wrs = wrs[np.isfinite(wrs)]
    if wrs.size == 0:
        return _empty_mc(note + "_all_nan", n_regime, pool_size, reps)
    med = float(np.median(wrs))
    p_side = (float(np.sum(wrs >= observed_win_rate)) + 1.0) / (float(wrs.size) + 1.0)
    return {
        "n_regime": int(n_regime),
        "pool_size": int(pool_size),
        "reps": int(wrs.size),
        "random_win_rate_median": med,
        "random_win_rate_p05": float(np.percentile(wrs, 5)),
        "random_win_rate_p95": float(np.percentile(wrs, 95)),
        "uplift_vs_random_median": float(observed_win_rate - med),
        "empirical_p_value_one_sided_smoothed": p_side,
        "note": note,
    }


def sample_spacing_matched_indices(
    pool_sorted: np.ndarray,
    n_need: int,
    spacing: int,
    rng: np.random.Generator,
    max_outer: int = 800,
) -> np.ndarray | None:
    """Random sparse subset of pool with index gaps >= spacing, sorted ascending, size n_need."""
    pool_sorted = np.sort(pool_sorted.astype(int))
    if pool_sorted.size < n_need or n_need <= 0:
        return None
    pool_max = int(pool_sorted[-1])
    # First anchor must leave room for (n_need-1) gaps of at least `spacing` before pool_max.
    hi0 = pool_max - (n_need - 1) * spacing
    first_candidates = pool_sorted[pool_sorted <= hi0]
    if first_candidates.size == 0:
        return None
    for _ in range(max_outer):
        i0 = int(rng.choice(first_candidates))
        chosen = [i0]
        cur = i0
        ok = True
        for _k in range(n_need - 1):
            already = len(chosen)
            rem = n_need - already  # anchors left to place including this pick
            lo_b = cur + spacing
            hi_b = pool_max - (rem - 1) * spacing
            opts = pool_sorted[(pool_sorted >= lo_b) & (pool_sorted <= hi_b)]
            if opts.size == 0:
                ok = False
                break
            cur = int(rng.choice(opts))
            chosen.append(cur)
        if ok and len(chosen) == n_need:
            return np.array(chosen, dtype=int)
    return None


def mc_spacing_matched_win_rates(
    observed_win_rate: float,
    n_regime: int,
    pool: np.ndarray,
    closes: np.ndarray,
    H: int,
    spacing: int,
    reps: int,
    rng: np.random.Generator,
) -> dict:
    if n_regime <= 0 or pool.size == 0 or reps <= 0:
        return _empty_mc("spacing_matched_empty", n_regime, pool.size, reps)
    pool_s = np.sort(pool.astype(int))
    wrs: list[float] = []
    for _ in range(reps):
        samp = sample_spacing_matched_indices(pool_s, n_regime, spacing, rng)
        if samp is None:
            continue
        w = win_rate_at_indices(samp, closes, H)
        if np.isfinite(w):
            wrs.append(w)
    arr = np.array(wrs, dtype=float)
    if arr.size == 0:
        return _empty_mc("spacing_matched_no_valid_samples", n_regime, pool.size, reps)
    return _summarize_mc(arr, observed_win_rate, n_regime, pool.size, arr.size, "spacing_matched_same_n_and_survival")


def mc_year_histogram_matched_win_rates(
    observed_win_rate: float,
    regime_indices: list[int],
    dates: np.ndarray,
    pool: np.ndarray,
    closes: np.ndarray,
    H: int,
    reps: int,
    rng: np.random.Generator,
) -> dict:
    """Match count per calendar year of regime anchors; sample same count from pool per year."""
    n_regime = len(regime_indices)
    if n_regime <= 0 or pool.size == 0 or reps <= 0:
        return _empty_mc("year_block_matched_empty", n_regime, pool.size, reps)
    pool = np.sort(pool.astype(int))
    regime_years = np.array([int(pd.Timestamp(dates[i]).year) for i in regime_indices], dtype=int)
    hist = Counter(regime_years.tolist())
    pool_years = np.array([int(pd.Timestamp(dates[j]).year) for j in pool], dtype=int)
    wrs: list[float] = []
    for _ in range(reps):
        samp: list[int] = []
        fail = False
        for y, k in hist.items():
            opts = pool[pool_years == y]
            if opts.size < k:
                fail = True
                break
            samp.extend(rng.choice(opts, size=k, replace=False).tolist())
        if fail or len(samp) != n_regime:
            continue
        w = win_rate_at_indices(np.array(samp, dtype=int), closes, H)
        if np.isfinite(w):
            wrs.append(w)
    arr = np.array(wrs, dtype=float)
    if arr.size == 0:
        return _empty_mc("year_hist_matched_no_valid_samples", n_regime, pool.size, reps)
    return _summarize_mc(arr, observed_win_rate, n_regime, pool.size, arr.size, "year_histogram_matched_counts_by_year")
