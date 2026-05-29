"""Phase 1: Full-history universe design.

Builds multiple universe definitions using ADV50 relative to the cross-section
for each weekly scan date — replacing the fixed 20B VND threshold which was
only valid for modern (2024+) liquidity levels.

Universe IDs:
  U0_ADV50_20B       — fixed modern-only filter (2024+ only)
  U1_TOP_100_ADV50   — top 100 by ADV50 per scan date
  U1_TOP_150_ADV50
  U1_TOP_200_ADV50
  U1_TOP_300_ADV50
  U2_TOP_20PCT_ADV50 — top 20% by ADV50 per scan date
  U2_TOP_30PCT_ADV50
  U2_TOP_40PCT_ADV50
  U3_ADV50_1B        — absolute threshold sensitivity
  U3_ADV50_2B
  U3_ADV50_5B
  U3_ADV50_10B
  U3_ADV50_20B       (same as U0, included for comparison)

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .fh_data_loader import ParquetSymbolLoader, load_fh_benchmark

RESEARCH_ONLY_FLAG = "RESEARCH_ONLY_NOT_PRODUCTION"

_TOP_N_UNIVERSES = {
    "U1_TOP_100_ADV50": ("top_n", 100),
    "U1_TOP_150_ADV50": ("top_n", 150),
    "U1_TOP_200_ADV50": ("top_n", 200),
    "U1_TOP_300_ADV50": ("top_n", 300),
}

_PCT_UNIVERSES = {
    "U2_TOP_20PCT_ADV50": ("pct", 0.20),
    "U2_TOP_30PCT_ADV50": ("pct", 0.30),
    "U2_TOP_40PCT_ADV50": ("pct", 0.40),
}

_THRESHOLD_UNIVERSES = {
    "U3_ADV50_1B": ("threshold", 1_000_000_000.0),
    "U3_ADV50_2B": ("threshold", 2_000_000_000.0),
    "U3_ADV50_5B": ("threshold", 5_000_000_000.0),
    "U3_ADV50_10B": ("threshold", 10_000_000_000.0),
    "U3_ADV50_20B": ("threshold", 20_000_000_000.0),
}

_MODERN_UNIVERSE = {
    "U0_ADV50_20B": ("threshold", 20_000_000_000.0),
}

ALL_UNIVERSE_IDS = list(_MODERN_UNIVERSE) + list(_TOP_N_UNIVERSES) + list(_PCT_UNIVERSES) + list(_THRESHOLD_UNIVERSES)

# VIN group tickers to flag
EX_VIN_TICKERS = {"VIC", "VHM", "VRE"}
ETF_TICKERS = {"E1VFVN30"}
BENCH_TICKERS = {"VNINDEX", "VN30", "HNXINDEX", "UPCOMINDEX"}


def _get_weekly_dates(benchmark: pd.DataFrame, start: str, end: str) -> list[pd.Timestamp]:
    b = benchmark.copy()
    b["date"] = pd.to_datetime(b["date"], errors="coerce")
    b = b.dropna(subset=["date"])
    b = b[(b["date"] >= pd.Timestamp(start)) & (b["date"] <= pd.Timestamp(end))]
    return list(b.groupby(b["date"].dt.to_period("W-FRI"))["date"].max().sort_values())


def _compute_adv50_at_date(loader: ParquetSymbolLoader, symbols: list[str], scan_dt: pd.Timestamp) -> pd.Series:
    """Return Series of adv50_vnd indexed by symbol for a given scan date.

    ADV50 = mean(daily value in VND) over the last 50 trading bars up to scan_dt.

    NOTE: The parquet 'value' column has inconsistent units across time periods
    (sometimes kVND-scaled, sometimes VND-scaled). To avoid unit errors, we
    always compute value from close × volume × 1000, since close is consistently
    in kVND (thousand-VND) and volume is in shares.
    """
    adv50s = {}
    for sym in symbols:
        df = loader(sym)
        if df is None or df.empty:
            continue
        df = df[df["date"] <= scan_dt]
        if len(df) < 50:
            continue
        tail = df.tail(50)
        # Always use close × volume × 1000: close is in kVND, volume in shares
        # → value in VND. This is consistent regardless of 'value' column units.
        close_arr = pd.to_numeric(tail["close"], errors="coerce")
        vol_arr = pd.to_numeric(tail["volume"], errors="coerce")
        val_series = close_arr * vol_arr * 1000.0
        valid = val_series.dropna()
        if len(valid) < 20:
            continue
        adv50 = float(valid.mean())
        if pd.notna(adv50) and adv50 > 0:
            adv50s[sym] = adv50
    return pd.Series(adv50s, name="adv50_vnd")


def _assign_universe_membership(adv50: pd.Series) -> pd.DataFrame:
    """Given ADV50 values for a scan date, assign universe membership flags."""
    df = adv50.reset_index()
    df.columns = ["ticker", "adv50_vnd"]
    df = df.sort_values("adv50_vnd", ascending=False).reset_index(drop=True)
    n = len(df)

    # Top-N
    for uid, (kind, val) in _TOP_N_UNIVERSES.items():
        cutoff = int(val)
        df[uid] = df.index < cutoff

    # Top-pct
    for uid, (kind, val) in _PCT_UNIVERSES.items():
        cutoff = max(1, int(np.ceil(n * val)))
        df[uid] = df.index < cutoff

    # Absolute threshold
    for uid, (kind, threshold) in _THRESHOLD_UNIVERSES.items():
        df[uid] = df["adv50_vnd"] >= threshold

    # Modern
    for uid, (kind, threshold) in _MODERN_UNIVERSE.items():
        df[uid] = df["adv50_vnd"] >= threshold

    # EX-VIN flag
    df["is_vin"] = df["ticker"].isin(EX_VIN_TICKERS)
    return df


def build_universe_coverage(
    loader: ParquetSymbolLoader,
    out_dir: Path,
    start: str = "2017-01-01",
    end: str = "2026-05-31",
    verbose: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run Phase 1: build universe coverage tables.

    Returns (weekly_df, yearly_df).
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    benchmark = load_fh_benchmark()
    scan_dates = _get_weekly_dates(benchmark, start, end)
    skip = BENCH_TICKERS | ETF_TICKERS
    symbols = [s for s in loader.symbols if s not in skip]

    weekly_rows: list[dict[str, Any]] = []

    for dt in scan_dates:
        adv50 = _compute_adv50_at_date(loader, symbols, dt)
        if adv50.empty:
            for uid in ALL_UNIVERSE_IDS:
                weekly_rows.append(
                    {
                        "universe_id": uid,
                        "date": dt,
                        "year": dt.year,
                        "candidate_count": 0,
                        "zero_candidate_week": True,
                        "avg_adv50": None,
                        "median_adv50": None,
                        "status": "NO_DATA",
                        "research_only_flag": RESEARCH_ONLY_FLAG,
                    }
                )
            continue

        membership = _assign_universe_membership(adv50)
        n_all = len(adv50)
        avg_adv = float(adv50.mean())
        med_adv = float(adv50.median())

        for uid in ALL_UNIVERSE_IDS:
            count = int(membership[uid].sum()) if uid in membership.columns else 0
            sparse_note = ""
            if uid.startswith("U3_") and uid.endswith("_20B") and dt.year < 2024:
                sparse_note = "SPARSE_PRE2024_FIXED_THRESHOLD"
            weekly_rows.append(
                {
                    "universe_id": uid,
                    "date": dt,
                    "year": dt.year,
                    "candidate_count": count,
                    "zero_candidate_week": count == 0,
                    "avg_adv50": avg_adv,
                    "median_adv50": med_adv,
                    "status": sparse_note if sparse_note else ("OK" if count > 0 else "ZERO_CANDIDATES"),
                    "research_only_flag": RESEARCH_ONLY_FLAG,
                }
            )

        if verbose and dt.month == 1 and dt.day <= 10:
            counts = {uid: int(membership[uid].sum()) for uid in ["U1_TOP_200_ADV50", "U3_ADV50_20B"]}
            print(f"[Phase 1] {dt.date()} total_with_adv50={n_all}  U1_200={counts.get('U1_TOP_200_ADV50',0)}  U0_20B={counts.get('U3_ADV50_20B',0)}")

    weekly_df = pd.DataFrame(weekly_rows)

    # Yearly summary
    yearly_df = (
        weekly_df.groupby(["universe_id", "year"], as_index=False)
        .agg(
            candidate_count_mean=("candidate_count", "mean"),
            candidate_count_min=("candidate_count", "min"),
            candidate_count_max=("candidate_count", "max"),
            zero_weeks=("zero_candidate_week", "sum"),
            total_weeks=("universe_id", "count"),
            avg_adv50=("avg_adv50", "mean"),
        )
        .assign(research_only_flag=RESEARCH_ONLY_FLAG)
    )

    weekly_df.to_csv(out_dir / "universe_coverage_by_week.csv", index=False)
    yearly_df.to_csv(out_dir / "universe_coverage_by_year.csv", index=False)
    print(f"[Phase 1] Universe coverage: {len(scan_dates)} scan dates, {len(ALL_UNIVERSE_IDS)} universes")
    return weekly_df, yearly_df


def get_scan_date_universe_membership(
    weekly_df: pd.DataFrame, universe_id: str, min_candidates: int = 1
) -> pd.Series:
    """Return boolean Series indexed by date for whether the universe is usable."""
    sub = weekly_df[weekly_df["universe_id"] == universe_id].set_index("date")
    return sub["candidate_count"] >= min_candidates
