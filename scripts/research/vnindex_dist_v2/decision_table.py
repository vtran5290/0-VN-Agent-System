"""Compact decision rows from horizon statistics (spacing-matched baseline primary)."""
from __future__ import annotations

from typing import Any


def wilson_ci_str(lo: float | None, hi: float | None) -> str:
    if lo is None or hi is None or (isinstance(lo, float) and lo != lo):
        return ""
    return f"[{lo:.4f},{hi:.4f}]"


def bootstrap_mean_ci_str(boot: dict[str, Any]) -> str:
    lo = boot.get("mean_ci95_low")
    hi = boot.get("mean_ci95_high")
    if lo is None or hi is None or (isinstance(lo, float) and lo != lo):
        return ""
    return f"[{lo:.6f},{hi:.6f}]"


def _bad(x: object) -> bool:
    return x is None or (isinstance(x, float) and x != x)


def conclude(
    H: int,
    n: int,
    conditional_win: float,
    wilson_lo: float | None,
    random_median: float | None,
    uplift: float | None,
    p_value: float | None,
) -> str:
    """Heuristic enum; not investment advice."""
    if n < 8 or _bad(random_median) or _bad(uplift) or _bad(p_value):
        return "weak_or_inconclusive"
    if conditional_win <= random_median - 0.02 or p_value >= 0.25 or uplift < -0.02:
        return "no_edge_vs_baseline"
    if H in (25, 50) and p_value <= 0.05 and uplift >= 0.02 and conditional_win > random_median:
        if wilson_lo is not None and not _bad(wilson_lo) and wilson_lo > random_median - 0.01:
            return "strong_short_term_edge"
        if uplift >= 0.05:
            return "strong_short_term_edge"
    if p_value <= 0.1 and uplift > 0 and conditional_win > random_median:
        return "weak_or_inconclusive"
    return "weak_or_inconclusive"


def row_from_block(
    regime_fork: str,
    forward_series: str,
    H: int,
    block: dict[str, Any],
) -> dict[str, Any] | None:
    if not block or "win_rate" not in block:
        return None
    n = int(block["n"])
    wr = float(block["win_rate"])
    wlo = block.get("wilson_ci95_low")
    whi = block.get("wilson_ci95_high")
    mean_ret = float(block.get("forward_return_mean", float("nan")))
    boot = block.get("block_bootstrap_by_year") or {}
    spacing = block.get("random_baseline_spacing_matched") or {}
    rm = spacing.get("random_win_rate_median")
    uplift = spacing.get("uplift_vs_random_median")
    pval = spacing.get("empirical_p_value_one_sided_smoothed")
    conc = conclude(H, n, wr, float(wlo) if wlo is not None else None, rm, uplift, float(pval) if pval is not None else None)
    return {
        "regime_fork": regime_fork,
        "forward_series": forward_series,
        "horizon": H,
        "n": n,
        "conditional_win": wr,
        "wilson_ci": wilson_ci_str(float(wlo) if wlo is not None else None, float(whi) if whi is not None else None),
        "random_win_median": rm,
        "uplift": uplift,
        "p_value": pval,
        "mean_return": mean_ret,
        "bootstrap_mean_ci": bootstrap_mean_ci_str(boot),
        "conclusion": conc,
    }
