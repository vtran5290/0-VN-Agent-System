"""Aggregate / per-ticker metrics for B0_CLEAN (facts only — no verdict)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .universe import EX_VIN

PRIMARY_COST = "net_45bp"


def _pf(returns: pd.Series) -> float:
    r = returns.dropna()
    if r.empty:
        return float("nan")
    gains = r[r > 0].sum()
    losses = -r[r < 0].sum()
    if losses == 0:
        return float("inf") if gains > 0 else float("nan")
    return float(gains / losses)


def summarize_trades(trades: pd.DataFrame) -> dict[str, Any]:
    if trades is None or trades.empty:
        return {"n_signals": 0, "n_filled": 0}

    n_sig = len(trades)
    filled = trades[trades["filled"] == True]  # noqa: E712
    n_filled = len(filled)
    primary = filled[filled["settlement_tag"] == "SETTLEMENT_T2_ERA"] if n_filled else filled

    def _block(df: pd.DataFrame, label: str) -> dict[str, Any]:
        if df.empty:
            return {"label": label, "n": 0}
        return {
            "label": label,
            "n": int(len(df)),
            "mean_gross": float(df["gross_return"].mean()),
            "mean_net_45bp": float(df[PRIMARY_COST].mean()),
            "pf_gross": _pf(df["gross_return"]),
            "pf_net_45bp": _pf(df[PRIMARY_COST]),
            "hit_rate": float((df["gross_return"] > 0).mean()),
        }

    ex_vin = primary[~primary["symbol"].isin(EX_VIN)] if n_filled else primary
    full = primary

    return {
        "n_signals_attempted": n_sig,
        "n_filled": n_filled,
        "pct_entry_locked": float((trades["entry_flag"] == "ENTRY_LOCKED_NO_FILL").mean()),
        "pct_entry_no_vol": float((trades["entry_flag"] == "ENTRY_NO_VOL").mean()),
        "pct_ca_excluded": float((trades["entry_flag"] == "CA_WINDOW_EXCLUDED").mean()),
        "pct_settlement_t3_era": float((trades["settlement_tag"] == "SETTLEMENT_T3_ERA").mean()),
        "same_close_fills": int((trades.get("same_close_fill") == True).sum()) if "same_close_fill" in trades else 0,  # noqa: E712
        "primary_T2_FULL": _block(full, "HOSE_HNX_PROXY_FULL_T2"),
        "primary_T2_EX_VIN": _block(ex_vin, "EX_VIN_T2"),
        "all_filled_incl_T3_era": _block(filled, "ALL_FILLED"),
    }


def per_ticker_metrics(trades: pd.DataFrame) -> pd.DataFrame:
    filled = trades[trades["filled"] == True].copy()  # noqa: E712
    if filled.empty:
        return pd.DataFrame()
    rows = []
    for sym, g in filled.groupby("symbol"):
        rows.append(
            {
                "symbol": sym,
                "n": int(len(g)),
                "mean_gross": float(g["gross_return"].mean()),
                "mean_net_45bp": float(g[PRIMARY_COST].mean()),
                "pf_net_45bp": _pf(g[PRIMARY_COST]),
            }
        )
    return pd.DataFrame(rows).sort_values("n", ascending=False)


def year_regime_metrics(trades: pd.DataFrame) -> pd.DataFrame:
    filled = trades[trades["filled"] == True].copy()  # noqa: E712
    if filled.empty:
        return pd.DataFrame()
    filled["year"] = pd.to_datetime(filled["entry_date"]).dt.year
    rows = []
    for year, g in filled.groupby("year"):
        rows.append(
            {
                "year": int(year),
                "n": int(len(g)),
                "mean_gross": float(g["gross_return"].mean()),
                "mean_net_45bp": float(g[PRIMARY_COST].mean()),
                "pf_net_45bp": _pf(g[PRIMARY_COST]),
            }
        )
    return pd.DataFrame(rows)


def vin_sensitivity(trades: pd.DataFrame) -> pd.DataFrame:
    filled = trades[
        (trades["filled"] == True) & (trades["settlement_tag"] == "SETTLEMENT_T2_ERA")  # noqa: E712
    ].copy()
    if filled.empty:
        return pd.DataFrame()
    full = filled
    ex = filled[~filled["symbol"].isin(EX_VIN)]
    vin_only = filled[filled["symbol"].isin(EX_VIN)]
    rows = []
    for label, g in [("FULL", full), ("EX_VIN", ex), ("VIN_ONLY", vin_only)]:
        rows.append(
            {
                "cell": label,
                "n": int(len(g)),
                "mean_gross": float(g["gross_return"].mean()) if len(g) else np.nan,
                "mean_net_45bp": float(g[PRIMARY_COST].mean()) if len(g) else np.nan,
                "pf_net_45bp": _pf(g[PRIMARY_COST]) if len(g) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def aggregate_metrics_table(summary: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for key in ("primary_T2_EX_VIN", "primary_T2_FULL", "all_filled_incl_T3_era"):
        block = summary.get(key) or {}
        rows.append({"cell": key, **{k: v for k, v in block.items() if k != "label"}})
    return pd.DataFrame(rows)
