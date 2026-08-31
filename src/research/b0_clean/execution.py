"""B0_CLEAN execution: entry open T+1, exit close T+3 sessions, locks / zero-vol."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

SETTLEMENT_CUTOVER = pd.Timestamp("2022-08-29")
COST_BPS = (30, 45, 60)
DEFAULT_LIMIT_PCT = 0.07  # HOSE-like default without security master


@dataclass
class ExecConfig:
    limit_pct: float = DEFAULT_LIMIT_PCT
    max_exit_defer_sessions: int = 10
    exit_sessions_after_signal: int = 3  # T+3 primary: exit at close of 3rd session after T


def _one_price(row: pd.Series) -> bool:
    return float(row["high"]) == float(row["low"])


def is_locked_limit_up(row: pd.Series, prev_close: float, limit_pct: float) -> bool:
    if not np.isfinite(prev_close) or prev_close <= 0:
        return False
    if not _one_price(row):
        return False
    return float(row["close"]) >= prev_close * (1.0 + limit_pct - 1e-9)


def is_locked_limit_down(row: pd.Series, prev_close: float, limit_pct: float) -> bool:
    if not np.isfinite(prev_close) or prev_close <= 0:
        return False
    if not _one_price(row):
        return False
    return float(row["close"]) <= prev_close * (1.0 - limit_pct + 1e-9)


def _net(gross: float, bps: int) -> float:
    return gross - bps / 10_000.0


def simulate_symbol_trades(
    df: pd.DataFrame,
    *,
    cfg: ExecConfig | None = None,
) -> list[dict[str, Any]]:
    """
    df: single-symbol frame sorted by date with signal bool and OHLCV + prev_close + ca_suspect.
    One position at a time; no overlapping re-entry.
    """
    cfg = cfg or ExecConfig()
    d = df.sort_values("date").reset_index(drop=True)
    n = len(d)
    trades: list[dict[str, Any]] = []
    i = 0
    while i < n:
        if not bool(d.at[i, "signal"]):
            i += 1
            continue

        signal_idx = i
        signal_date = pd.Timestamp(d.at[i, "date"])
        entry_idx = signal_idx + 1
        if entry_idx >= n:
            break

        entry_row = d.loc[entry_idx]
        prev_c = float(d.at[signal_idx, "close"])  # prior session close for limit vs entry bar
        # Use entry bar's prev_close if present
        if "prev_close" in d.columns and pd.notna(entry_row.get("prev_close")):
            prev_c = float(entry_row["prev_close"])

        entry_flag = None
        if float(entry_row["volume"]) <= 0:
            entry_flag = "ENTRY_NO_VOL"
        elif is_locked_limit_up(entry_row, prev_c, cfg.limit_pct):
            entry_flag = "ENTRY_LOCKED_NO_FILL"

        if entry_flag:
            trades.append(
                {
                    "symbol": str(d.at[signal_idx, "symbol"]),
                    "signal_date": signal_date,
                    "entry_date": pd.Timestamp(entry_row["date"]),
                    "exit_date": pd.NaT,
                    "filled": False,
                    "entry_flag": entry_flag,
                    "exit_flag": None,
                    "entry_px": None,
                    "exit_px": None,
                    "gross_return": None,
                    "net_30bp": None,
                    "net_45bp": None,
                    "net_60bp": None,
                    "scheduled_hold_sessions": int(cfg.exit_sessions_after_signal),
                    "realized_hold_sessions": None,
                    "settlement_tag": (
                        "SETTLEMENT_T3_ERA"
                        if pd.Timestamp(entry_row["date"]) < SETTLEMENT_CUTOVER
                        else "SETTLEMENT_T2_ERA"
                    ),
                    "ca_excluded_hold": False,
                    "ablation": d.at[signal_idx, "ablation"] if "ablation" in d.columns else "primary",
                    "same_close_fill": False,
                }
            )
            i = entry_idx + 1
            continue

        # Scheduled exit = close of Nth session after signal (primary N=3)
        sched_exit_idx = signal_idx + int(cfg.exit_sessions_after_signal)
        if sched_exit_idx >= n:
            break

        # CA in holding window [entry, exit]
        hold_slice = d.loc[entry_idx:sched_exit_idx]
        ca_hit = False
        if "ca_suspect" in d.columns:
            ca_hit = bool(hold_slice["ca_suspect"].map(lambda x: bool(x) if pd.notna(x) else False).any())

        if ca_hit:
            # Drop trade / do not take — CA window exclusion
            trades.append(
                {
                    "symbol": str(d.at[signal_idx, "symbol"]),
                    "signal_date": signal_date,
                    "entry_date": pd.Timestamp(entry_row["date"]),
                    "exit_date": pd.NaT,
                    "filled": False,
                    "entry_flag": "CA_WINDOW_EXCLUDED",
                    "exit_flag": None,
                    "entry_px": None,
                    "exit_px": None,
                    "gross_return": None,
                    "net_30bp": None,
                    "net_45bp": None,
                    "net_60bp": None,
                    "scheduled_hold_sessions": int(cfg.exit_sessions_after_signal),
                    "realized_hold_sessions": None,
                    "settlement_tag": (
                        "SETTLEMENT_T3_ERA"
                        if pd.Timestamp(entry_row["date"]) < SETTLEMENT_CUTOVER
                        else "SETTLEMENT_T2_ERA"
                    ),
                    "ca_excluded_hold": True,
                    "ablation": d.at[signal_idx, "ablation"] if "ablation" in d.columns else "primary",
                    "same_close_fill": False,
                }
            )
            i = sched_exit_idx + 1
            continue

        exit_idx = sched_exit_idx
        exit_flag = None
        # Defer if locked limit-down or zero volume
        for defer in range(0, cfg.max_exit_defer_sessions + 1):
            j = sched_exit_idx + defer
            if j >= n:
                exit_idx = n - 1
                exit_flag = "UNRESOLVED_EXIT_LOCK"
                break
            row = d.loc[j]
            pc = float(d.at[j - 1, "close"]) if j - 1 >= 0 else np.nan
            if float(row["volume"]) <= 0 or is_locked_limit_down(row, pc, cfg.limit_pct):
                if defer == cfg.max_exit_defer_sessions:
                    exit_idx = j
                    exit_flag = "UNRESOLVED_EXIT_LOCK"
                    break
                continue
            exit_idx = j
            exit_flag = "EXIT_DEFERRED" if defer > 0 else "EXIT_SCHEDULED"
            break

        entry_px = float(entry_row["open"])
        exit_px = float(d.at[exit_idx, "close"])
        gross = exit_px / entry_px - 1.0
        entry_date = pd.Timestamp(entry_row["date"])
        trades.append(
            {
                "symbol": str(d.at[signal_idx, "symbol"]),
                "signal_date": signal_date,
                "entry_date": entry_date,
                "exit_date": pd.Timestamp(d.at[exit_idx, "date"]),
                "filled": True,
                "entry_flag": "FILLED",
                "exit_flag": exit_flag,
                "entry_px": entry_px,
                "exit_px": exit_px,
                "gross_return": gross,
                "net_30bp": _net(gross, 30),
                "net_45bp": _net(gross, 45),
                "net_60bp": _net(gross, 60),
                "scheduled_hold_sessions": int(cfg.exit_sessions_after_signal),
                "realized_hold_sessions": int(exit_idx - signal_idx),
                "settlement_tag": (
                    "SETTLEMENT_T3_ERA" if entry_date < SETTLEMENT_CUTOVER else "SETTLEMENT_T2_ERA"
                ),
                "ca_excluded_hold": False,
                "ablation": d.at[signal_idx, "ablation"] if "ablation" in d.columns else "primary",
                "same_close_fill": False,
                "adv50_at_signal": float(d.at[signal_idx, "adv50"]) if "adv50" in d.columns else None,
            }
        )
        # No re-entry until after exit
        i = exit_idx + 1

    return trades


def simulate_panel(df: pd.DataFrame, cfg: ExecConfig | None = None) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, g in df.groupby("symbol", sort=False):
        rows.extend(simulate_symbol_trades(g, cfg=cfg))
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)
