"""Regime anchor selection and forward returns."""
from __future__ import annotations

import numpy as np
import pandas as pd

HORIZONS_V2 = (25, 50, 100, 150, 200, 250)


def regime_candidates(dist: np.ndarray, n: int, L: int, max_dist: int) -> list[int]:
    out: list[int] = []
    for i in range(L - 1, n):
        w = dist[i - L + 1 : i + 1]
        if np.isnan(w).any():
            continue
        if int(np.nansum(w)) <= max_dist:
            out.append(i)
    return out


def sparse_anchors(candidates: list[int], spacing: int) -> list[int]:
    sparse: list[int] = []
    last_pick = -10**9
    for i in candidates:
        if i - last_pick >= spacing:
            sparse.append(i)
            last_pick = i
    return sparse


def exclude_last_index(sparse: list[int], last_index: int) -> list[int]:
    return [i for i in sparse if i != last_index]


def forward_returns_at_h(closes: np.ndarray, indices: list[int], h: int) -> np.ndarray:
    n = len(closes)
    arr: list[float] = []
    for i in indices:
        j = i + h
        if j >= n:
            continue
        c0, cj = closes[i], closes[j]
        if not (np.isfinite(c0) and np.isfinite(cj) and c0 > 0):
            continue
        arr.append(float(cj / c0 - 1.0))
    return np.array(arr, dtype=float)


def anchors_with_valid_horizon(
    sparse_excl_last: list[int],
    closes: np.ndarray,
    h: int,
) -> list[int]:
    n = len(closes)
    return [i for i in sparse_excl_last if i + h < n and np.isfinite(closes[i]) and closes[i] > 0]


def dist_sum_window(dist: np.ndarray, i: int, L: int) -> float:
    return float(np.nansum(dist[i - L + 1 : i + 1]))


def prior_dist_count_percentile(dist: np.ndarray, n: int, L: int, anchor_i: int) -> float | None:
    """Empirical percentile (0-100) of this anchor's dist_count vs all prior trailing-L counts (k < anchor_i)."""
    if anchor_i < L:
        return None
    cur = dist_sum_window(dist, anchor_i, L)
    hist: list[float] = []
    for k in range(L - 1, anchor_i):
        w = dist[k - L + 1 : k + 1]
        if np.isnan(w).any():
            continue
        hist.append(float(np.nansum(w)))
    if not hist:
        return None
    hist_arr = np.array(hist, dtype=float)
    return float(100.0 * (np.sum(hist_arr <= cur) / len(hist_arr)))
