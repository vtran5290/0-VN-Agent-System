from __future__ import annotations

"""
Kelly-style portfolio sizing simulation on backtest ledger.

Assumptions:
- Trades occur sequentially (no overlapping positions in the equity curve model).
- For each trade with simple return r (e.g. +0.15, -0.08), we bet fraction f of current
  equity and obtain equity *= (1 + f * r).
- We choose f in a grid to maximize average log growth E[log(1 + f * r)].

This is *not* a full multi-asset Kelly across simultaneous positions, but a
single-game Kelly approximation for the sequence of realized returns.
"""

import math
from pathlib import Path

import numpy as np
import pandas as pd

_PP = Path(__file__).resolve().parent


def load_ledger(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Ledger not found: {path}")
    df = pd.read_csv(path)
    if "ret" not in df.columns:
        raise ValueError("Ledger must contain 'ret' column.")
    # Ensure dates are sortable
    if "entry_date" in df.columns:
        df["entry_date"] = pd.to_datetime(df["entry_date"])
        df = df.sort_values("entry_date").reset_index(drop=True)
    return df


def kelly_grid_search(
    rets: np.ndarray,
    f_min: float = 0.0,
    f_max: float = 0.5,
    f_step: float = 0.005,
) -> tuple[float, float]:
    """
    Grid search f to maximize mean(log(1 + f * r)).
    Returns (f_opt, max_log_growth).
    """
    best_f = 0.0
    best_g = -math.inf
    fs = np.arange(f_min, f_max + 1e-9, f_step)
    for f in fs:
        x = 1.0 + f * rets
        if np.any(x <= 0):
            # log undefined; skip this f
            continue
        g = float(np.mean(np.log(x)))
        if g > best_g:
            best_g = g
            best_f = f
    return best_f, best_g


def simulate_equity(rets: np.ndarray, f: float) -> dict:
    """
    Simulate equity curve with bet fraction f per trade.
    Returns summary stats: final_multiple, mdd, n_trades, win_rate, avg_ret.
    """
    eq = np.ones(len(rets) + 1, dtype=float)
    for i, r in enumerate(rets, start=1):
        eq[i] = eq[i - 1] * (1.0 + f * r)
    # Compute MDD on equity path
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    mdd = float(dd.min())
    wins = rets[rets > 0]
    return {
        "n_trades": len(rets),
        "final_multiple": float(eq[-1]),
        "mdd": mdd,
        "win_rate": float((rets > 0).mean()) if len(rets) else float("nan"),
        "avg_ret": float(rets.mean()) if len(rets) else float("nan"),
    }


def main() -> None:
    ledger_path = _PP / "pp_weekly_ema21_ledger.csv"
    df = load_ledger(ledger_path)
    rets = df["ret"].astype(float).values
    print(f"[kelly] loaded {len(rets)} trades from {ledger_path}")

    f_opt, g_opt = kelly_grid_search(rets, f_min=0.0, f_max=0.5, f_step=0.005)
    print(f"[kelly] optimal_fraction_full = {f_opt:.3f}, avg_log_growth = {g_opt:.6f}")

    # Full Kelly
    full_stats = simulate_equity(rets, f_opt)
    print(
        "[kelly_full] f={f:.3f} trades={n_trades} final_multiple={final_multiple:.1f} "
        "mdd={mdd:.2%} avg_ret={avg_ret:.2%} win_rate={win_rate:.2%}".format(
            f=f_opt, **full_stats
        )
    )

    # Half Kelly (more realistic)
    f_half = f_opt / 2.0
    half_stats = simulate_equity(rets, f_half)
    print(
        "[kelly_half] f={f:.3f} trades={n_trades} final_multiple={final_multiple:.1f} "
        "mdd={mdd:.2%} avg_ret={avg_ret:.2%} win_rate={win_rate:.2%}".format(
            f=f_half, **half_stats
        )
    )


if __name__ == "__main__":
    main()

