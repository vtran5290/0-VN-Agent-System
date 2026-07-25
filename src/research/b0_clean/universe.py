"""Point-in-time universe eligibility for B0_CLEAN."""

from __future__ import annotations

import re
from typing import Iterable

import numpy as np
import pandas as pd

EX_VIN = frozenset({"VIC", "VHM", "VRE"})
ADV50_THRESHOLD = 2_000_000_000.0  # raw VND, strict >
MIN_HISTORY_BARS = 120
MIN_NONZERO_VALUE_BARS_50 = 40
ADV_WINDOW = 50
VPL_MIN_BARS = 252

ETF_RE = re.compile(r"^(E1|FUE|FUC)", re.IGNORECASE)


def classify_instrument(symbol: str) -> str:
    sym = str(symbol).upper().strip()
    if ETF_RE.match(sym):
        return "ETF_EXCLUDED"
    # No PIT security master yet — common equities assumed; flag unknown.
    return "UNKNOWN_INSTRUMENT_TYPE"


def is_etf_excluded(symbol: str) -> bool:
    return classify_instrument(symbol) == "ETF_EXCLUDED"


def compute_pit_universe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add PIT eligibility columns on a per-symbol sorted frame.

    Requires columns: date, close, volume, value; optional ca_suspect.
    ADV50 uses `value` (FireAnt totalValue, raw VND) — NOT close*volume.
    """
    out = df.sort_values("date").copy()
    vol = pd.to_numeric(out["volume"], errors="coerce").fillna(0.0)
    val = pd.to_numeric(out["value"], errors="coerce")

    out["history_bars"] = np.arange(1, len(out) + 1)
    nonzero = (vol > 0) & val.notna() & (val > 0)
    out["nonzero_value_50"] = nonzero.astype(int).rolling(ADV_WINDOW, min_periods=1).sum()

    # ADV50: mean of last 50 bars' value (including zeros) — design uses T-49..T.
    # Handoff: valid_nonzero_value_bars_in_last_50 >= 40 separately; ADV on value window.
    out["adv50"] = val.rolling(ADV_WINDOW, min_periods=ADV_WINDOW).mean()

    suspended = vol <= 0
    out["instrument_type"] = classify_instrument(str(out["symbol"].iloc[0]) if "symbol" in out.columns else "")

    etf = is_etf_excluded(str(out["symbol"].iloc[0])) if "symbol" in out.columns else False
    vpl_block = False
    if "symbol" in out.columns and str(out["symbol"].iloc[0]).upper() == "VPL":
        vpl_block = out["history_bars"] < VPL_MIN_BARS
    else:
        vpl_block = pd.Series(False, index=out.index)

    ca = (
        out["ca_suspect"].map(lambda x: bool(x) if pd.notna(x) else False)
        if "ca_suspect" in out.columns
        else pd.Series(False, index=out.index)
    )

    eligible = (
        (out["history_bars"] >= MIN_HISTORY_BARS)
        & (out["nonzero_value_50"] >= MIN_NONZERO_VALUE_BARS_50)
        & (out["adv50"] > ADV50_THRESHOLD)
        & (~suspended)
        & (~etf)
        & (~vpl_block)
        & (~ca if isinstance(ca, pd.Series) else True)
    )
    out["universe_eligible"] = eligible.fillna(False)

    reason = np.where(etf, "ETF_EXCLUDED", "OK")
    reason = np.where(vpl_block, "VPL_LT_252", reason)
    reason = np.where(suspended, "SUSPENDED_ZERO_VOL", reason)
    reason = np.where(out["history_bars"] < MIN_HISTORY_BARS, "LT_120_BARS", reason)
    reason = np.where(out["nonzero_value_50"] < MIN_NONZERO_VALUE_BARS_50, "LT_40_NONZERO_50", reason)
    reason = np.where(~(out["adv50"] > ADV50_THRESHOLD), "ADV50_LE_2B", reason)
    if isinstance(ca, pd.Series):
        reason = np.where(ca, "CA_SUSPECT", reason)
    out["universe_reject_reason"] = np.where(out["universe_eligible"], "OK", reason)
    out["ex_vin_member"] = ~out["symbol"].astype(str).str.upper().isin(EX_VIN) if "symbol" in out.columns else True
    return out


def apply_universe_panel(panel: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for sym, g in panel.groupby("symbol", sort=False):
        gg = g.copy()
        gg["symbol"] = sym
        parts.append(compute_pit_universe(gg))
    return pd.concat(parts, ignore_index=True)
