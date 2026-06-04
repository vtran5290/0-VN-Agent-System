"""
VN IBD-Style RS Rating Engine.

RESEARCH ONLY — context lens.  Does not set or override final_action.

Public API
----------
compute_rs_ratings(close_px, vni_close, universe) -> pd.DataFrame
    Wide long DataFrame: columns [date, symbol, rs_A1, ..., rs_D3]
    Ratings are 1-99 cross-sectional percentile ranks per date.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parents[3]
PANEL_PATH = REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_ext2012.parquet"
VNI_PATH   = REPO / "data" / "fireant_ssot" / "ta_vnindex.parquet"
UNIVERSE_PATH = REPO / "config" / "universe_liquid_adv50_2b.txt"

EX_VIN = frozenset({"VIC", "VHM", "VRE"})
MIN_BARS = 252  # minimum valid-close bars before a symbol enters ranking

# Variant definitions:
#   key -> (family, lookbacks_days, weights, special_method)
# Family A: US-style weighted lookbacks (12/9/6/3m)
# Family B: VN-compressed weighted lookbacks (6/3/2/1m)
# Family C: RS-line momentum (raw score, not weighted returns)
# Family D: risk-adjusted 3m return
VARIANT_DEFS: dict[str, tuple] = {
    "A1":  ("A", [252, 189, 126,  63], [0.40, 0.20, 0.20, 0.20], None),
    "A2":  ("A", [252, 189, 126,  63], [0.25, 0.25, 0.25, 0.25], None),
    "A3v": ("A", [252, 189, 126,  63], [0.20, 0.20, 0.30, 0.30], None),
    "B1":  ("B", [126,  63,  42,  21], [0.10, 0.40, 0.30, 0.20], None),
    "B2":  ("B", [ 63,  42,  21     ], [0.20, 0.50, 0.30      ], None),
    "B3":  ("B", [126,  63,  42,  21], [0.25, 0.25, 0.25, 0.25], None),
    "C1":  ("C", None, None, "rs_line_3m"),
    "C2":  ("C", None, None, "rs_line_1m"),
    "C3":  ("C", None, None, "rs_line_accel"),
    "D1":  ("D", None, None, "sharpe_3m"),
    "D2":  ("D", None, None, "sortino_3m"),
    "D3":  ("D", None, None, "calmar_3m"),
}


def _compute_raw_scores(
    close_px: pd.DataFrame,
    vni_close: pd.Series,
) -> dict[str, pd.DataFrame]:
    """
    Compute raw score matrices (date × symbol) for all variants.
    All operations are causal — only past data is used on any given date.
    """
    # Period returns for each lookback
    ret: dict[int, pd.DataFrame] = {}
    for lb in [21, 42, 63, 126, 189, 252]:
        ret[lb] = close_px / close_px.shift(lb) - 1

    # RS line = stock close / VNINDEX close (aligned by date)
    rs_line = close_px.div(vni_close, axis=0)
    rs_line_ret = {
        21:  rs_line / rs_line.shift(21)  - 1,
        63:  rs_line / rs_line.shift(63)  - 1,
        126: rs_line / rs_line.shift(126) - 1,
    }

    daily = close_px.pct_change()

    scores: dict[str, pd.DataFrame] = {}
    for name, (fam, lookbacks, weights, method) in VARIANT_DEFS.items():
        if fam in ("A", "B"):
            s = sum(w * ret[lb] for lb, w in zip(lookbacks, weights))
            scores[name] = s
        elif fam == "C":
            if method == "rs_line_3m":
                scores[name] = rs_line_ret[63]
            elif method == "rs_line_1m":
                scores[name] = rs_line_ret[21]
            elif method == "rs_line_accel":
                # recent 3m RS momentum minus 6m RS momentum
                scores[name] = rs_line_ret[63] - rs_line_ret[126]
        elif fam == "D":
            r3m = ret[63]
            roll_std = daily.rolling(63, min_periods=30).std()
            if method == "sharpe_3m":
                denom = (roll_std * np.sqrt(63)).replace(0, np.nan)
                scores[name] = r3m / denom
            elif method == "sortino_3m":
                neg = daily.where(daily < 0, 0.0)
                down_std = neg.pow(2).rolling(63, min_periods=30).mean().pow(0.5)
                denom = (down_std * np.sqrt(63)).replace(0, np.nan)
                scores[name] = r3m / denom
            elif method == "calmar_3m":
                roll_max = close_px.rolling(63, min_periods=1).max()
                mdd = (close_px / roll_max - 1).rolling(63, min_periods=1).min().abs()
                denom = mdd.replace(0, np.nan)
                scores[name] = r3m / denom

    return scores


def _eligibility_mask(close_px: pd.DataFrame, universe: list[str]) -> pd.DataFrame:
    """
    Boolean mask (date × symbol): True when symbol is eligible for cross-sectional ranking.
    Eligible = in universe - EX_VIN AND cumulative valid-bar count >= MIN_BARS.
    """
    eligible_syms = [s for s in close_px.columns if s in set(universe) - EX_VIN]
    sub = close_px[eligible_syms]
    bar_count = sub.notna().cumsum()
    return bar_count >= MIN_BARS


def _rank_to_rating(score: pd.DataFrame, eligible: pd.DataFrame) -> pd.DataFrame:
    """
    Cross-sectional rank of score within eligible symbols → 1-99 percentile.
    Ineligible cells become NaN.
    """
    elig = eligible.reindex(columns=score.columns, fill_value=False)
    masked = score.where(elig)
    # pct=True gives 0..1; scale to 1..99
    rated = masked.rank(axis=1, pct=True, na_option="keep") * 98.0 + 1.0
    return rated.clip(1, 99).round(1)


def compute_rs_ratings(
    close_px: pd.DataFrame,
    vni_close: pd.Series,
    universe: list[str],
) -> pd.DataFrame:
    """
    Compute daily RS ratings (1-99) for all 12 variants.

    Parameters
    ----------
    close_px  : date × symbol pivot of adjusted close prices
    vni_close : VNINDEX close series, indexed by date (same dates as close_px)
    universe  : list of symbols to include (EX_VIN are excluded from ranking)

    Returns
    -------
    Long DataFrame with columns: [date, symbol, rs_A1, rs_A2, ..., rs_D3]
    NaN where a symbol is ineligible or lacks sufficient history.
    """
    raw_scores = _compute_raw_scores(close_px, vni_close)
    eligible   = _eligibility_mask(close_px, universe)

    rating_parts: list[pd.Series] = []
    for name, score_df in raw_scores.items():
        rated = _rank_to_rating(score_df, eligible)
        stacked = rated.stack(future_stack=True).rename(f"rs_{name}")
        rating_parts.append(stacked)

    combined = pd.concat(rating_parts, axis=1)
    combined.index.names = ["date", "symbol"]
    return combined.reset_index()


def load_panel_and_vni(universe: list[str]) -> tuple[pd.DataFrame, pd.Series]:
    """Load OHLCV panel (pivoted) and VNINDEX close aligned to panel dates."""
    panel = pd.read_parquet(PANEL_PATH, columns=["symbol", "date", "close"])
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
    panel = panel[panel["symbol"].isin(universe)]
    close_px = panel.pivot_table(
        index="date", columns="symbol", values="close", aggfunc="last"
    ).sort_index()

    vni = pd.read_parquet(VNI_PATH)
    vni["date"] = pd.to_datetime(vni["date"]).dt.normalize()
    vni_close = vni.set_index("date")["close"].reindex(close_px.index).ffill()

    return close_px, vni_close


def load_universe() -> list[str]:
    if not UNIVERSE_PATH.is_file():
        return []
    return [
        x.strip().upper()
        for x in UNIVERSE_PATH.read_text(encoding="utf-8").splitlines()
        if x.strip() and not x.startswith("#")
    ]
