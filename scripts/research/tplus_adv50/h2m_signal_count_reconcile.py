#!/usr/bin/env python3
"""H2M signal-count reconciliation — READ-ONLY counts only.

Reproduces the method from:
  outputs/research/tplus_adv50_prereg/20260725_TPLUS_ADV50_H2M_Sample_Ceiling_Result.md §Method
as operationalized in:
  outputs/research/tplus_adv50_prereg/20260725_TPLUS_ADV50_Cursor_B3_Probe_Prompt.md Probe B

No writes to data/, data/decision/, or data/fireant_ssot/.
No returns / P&L / backtest.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
PANEL = REPO / "data" / "fireant_ssot" / "ta_ohlcv_panel.parquet"
EX_VIN = {"VIC", "VHM", "VRE"}
ENTRY_DATE_MIN = pd.Timestamp("2022-08-29")
ADV50_THRESHOLD = 2e9  # 2B VND, as per spec


def rolling_ols(g: pd.DataFrame) -> pd.DataFrame:
    g = g.sort_values("date").reset_index(drop=True)
    r = g["r"].values
    m = g["mkt"].values
    win = 120
    min_obs = 80
    alpha = pd.array([float("nan")] * len(g))
    beta = pd.array([float("nan")] * len(g))
    for i in range(win - 1, len(g)):
        sl = slice(max(0, i - win + 1), i + 1)
        rw, mw = r[sl], m[sl]
        mask = ~(pd.isna(rw) | pd.isna(mw))
        if mask.sum() < min_obs:
            continue
        rw, mw = rw[mask], mw[mask]
        mr, mm = rw.mean(), mw.mean()
        cov = ((rw - mr) * (mw - mm)).mean()
        var = ((mw - mm) ** 2).mean()
        if var == 0:
            continue
        b = cov / var
        a = mr - b * mm
        alpha[i] = a
        beta[i] = b
    g["alpha"] = alpha
    g["beta"] = beta
    return g


def rolling_z_prompt(g: pd.DataFrame) -> pd.DataFrame:
    """Probe-prompt loop: z at i uses shock3 window ending at i (includes i)."""
    g = g.sort_values("date").reset_index(drop=True)
    s3 = g["shock3"].values
    z = pd.array([float("nan")] * len(g))
    win = 120
    min_obs = 60
    for i in range(win - 1, len(g)):
        sl = slice(max(0, i - win + 1), i + 1)
        sw = s3[sl]
        mask = ~pd.isna(sw)
        if mask.sum() < min_obs:
            continue
        mu, sd = sw[mask].mean(), sw[mask].std()
        if sd == 0 or pd.isna(sd):
            continue
        if not pd.isna(s3[i]):
            z[i] = (s3[i] - mu) / sd
    g["z_shock3"] = z
    return g


def count_signals(panel: pd.DataFrame, z_col: str) -> dict:
    p = panel.copy()
    p["signal"] = (
        (p[z_col] <= -2.0)
        & (p["close"] > p["open"])
        & (
            (p["close"] - p["low"])
            / (p["high"] - p["low"]).replace(0, float("nan"))
            >= 0.50
        )
        & (p["high"] > p["low"])
        & (p["volume"] > 0)
    )
    p["adv50"] = p.groupby("symbol")["value"].transform(
        lambda x: x.rolling(50, min_periods=40).mean()
    )
    p["pos50"] = p.groupby("symbol")["value"].transform(
        lambda x: (x > 0).rolling(50).sum()
    )
    p["hist120"] = p.groupby("symbol")["value"].transform(
        lambda x: (x > 0).rolling(120).sum()
    )
    p["eligible"] = (
        (p["adv50"] > ADV50_THRESHOLD)
        & (p["pos50"] >= 40)
        & (p["hist120"] >= 120)
    )
    signals = p[p["signal"] & p["eligible"] & (p["date"] >= ENTRY_DATE_MIN)]
    return {
        "n": int(len(signals)),
        "dates": int(signals["date"].nunique()),
        "symbols": int(signals["symbol"].nunique()),
        "years": int(signals["date"].dt.year.nunique()),
    }


def main() -> int:
    if not PANEL.is_file():
        print(f"ERROR: panel not found: {PANEL}", file=sys.stderr)
        return 2

    panel = pd.read_parquet(PANEL)
    panel = panel[~panel["symbol"].isin(EX_VIN)].copy()
    panel["date"] = pd.to_datetime(panel["date"])

    # --- exactly as ceiling doc / probe prompt §Method ---
    panel = panel.sort_values(["symbol", "date"])
    panel["r"] = panel.groupby("symbol")["close"].pct_change()
    panel.loc[panel["r"].abs() >= 0.60, "r"] = float("nan")

    n = panel.groupby("date")["r"].transform("count")
    sum_r = panel.groupby("date")["r"].transform("sum")
    panel["mkt"] = (sum_r - panel["r"]) / (n - 1)
    panel = panel[n >= 51].copy()  # need n-1 >= 50

    panel = panel.groupby("symbol", group_keys=False).apply(rolling_ols)

    panel["a3"] = panel.groupby("symbol")["alpha"].shift(3)
    panel["b3"] = panel.groupby("symbol")["beta"].shift(3)
    panel["eps"] = panel["r"] - panel["a3"] - panel["b3"] * panel["mkt"]

    panel["shock3"] = panel.groupby("symbol")["eps"].transform(
        lambda x: x + x.shift(1) + x.shift(2)
    )

    # PRIMARY: prompt's rolling_z (window ends at i)
    panel = panel.groupby("symbol", group_keys=False).apply(rolling_z_prompt)
    primary = count_signals(panel, "z_shock3")

    # AMBIGUITY CHECK vs ceiling §Method text:
    #   Z = (SHOCK3 - roll120_mean.shift(3)) / roll120_std.shift(3)
    # Prompt loop does NOT apply .shift(3) to the rolling moments.
    panel["z_ceiling_shift3"] = (
        panel["shock3"]
        - panel.groupby("symbol")["shock3"].transform(
            lambda x: x.rolling(120, min_periods=60).mean().shift(3)
        )
    ) / panel.groupby("symbol")["shock3"].transform(
        lambda x: x.rolling(120, min_periods=60).std().shift(3)
    )
    alt = count_signals(panel, "z_ceiling_shift3")

    print(f"ADV50 threshold : {ADV50_THRESHOLD / 1e9:.0f}B VND")
    print("--- PRIMARY (probe prompt rolling_z, window ends at i) ---")
    print(f"Signals         : {primary['n']}")
    print(f"Unique dates    : {primary['dates']}")
    print(f"Unique symbols  : {primary['symbols']}")
    print(f"Calendar years  : {primary['years']}")
    print("--- ALT (ceiling §Method: roll moments .shift(3)) ---")
    print(f"Signals         : {alt['n']}")
    print(f"Unique dates    : {alt['dates']}")
    print(f"Unique symbols  : {alt['symbols']}")
    print(f"Calendar years  : {alt['years']}")
    if primary["n"] != alt["n"]:
        print(
            "AMBIGUITY: prompt rolling_z vs ceiling roll_mean/std.shift(3) diverge; "
            "return to Claude for adjudication. Primary count is the prompt script."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
