"""Wilson CI and year-block bootstrap for forward returns."""
from __future__ import annotations

import numpy as np


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1.0 + z**2 / n
    center = (p + z**2 / (2.0 * n)) / denom
    rad = z * np.sqrt((p * (1.0 - p) / n + z**2 / (4.0 * n * n))) / denom
    return (float(max(0.0, center - rad)), float(min(1.0, center + rad)))


def block_bootstrap_year_mean_median(
    years: np.ndarray,
    returns: np.ndarray,
    B: int,
    rng: np.random.Generator,
) -> dict:
    mask = np.isfinite(returns) & np.isfinite(years)
    y = years[mask].astype(int)
    r = returns[mask]
    if r.size < 5:
        return {
            "n": int(r.size),
            "mean_ci95_low": float("nan"),
            "mean_ci95_high": float("nan"),
            "median_ci95_low": float("nan"),
            "median_ci95_high": float("nan"),
            "note": "insufficient_sample",
        }
    unique_years = np.unique(y)
    if unique_years.size < 2:
        return {
            "n": int(r.size),
            "mean_ci95_low": float("nan"),
            "mean_ci95_high": float("nan"),
            "median_ci95_low": float("nan"),
            "median_ci95_high": float("nan"),
            "note": "single_year_block",
        }
    means: list[float] = []
    medians: list[float] = []
    n_draw = int(unique_years.size)
    for _ in range(B):
        drawn_years = rng.choice(unique_years, size=n_draw, replace=True)
        parts: list[np.ndarray] = []
        for yr in np.sort(drawn_years):
            parts.append(r[y == yr])
        if not parts:
            continue
        stacked = np.concatenate(parts)
        means.append(float(np.mean(stacked)))
        medians.append(float(np.median(stacked)))
    ma = np.array(means, dtype=float)
    md = np.array(medians, dtype=float)
    return {
        "n": int(r.size),
        "n_unique_years": int(unique_years.size),
        "bootstrap_reps": B,
        "mean_ci95_low": float(np.percentile(ma, 2.5)),
        "mean_ci95_high": float(np.percentile(ma, 97.5)),
        "median_ci95_low": float(np.percentile(md, 2.5)),
        "median_ci95_high": float(np.percentile(md, 97.5)),
    }
