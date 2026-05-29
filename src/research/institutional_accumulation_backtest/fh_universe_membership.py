"""Phase 11/12/13: Ticker-level universe membership from panel parquet.

Fixes the v0.1 bug where universe filtering was date-only
(scan_dates.isin(active_dates)) rather than ticker-level
((scan_date, ticker) pair membership).

Three public functions:
  build_membership_from_panel       — Phase 11: derives ticker-level membership
  run_adv_unit_audit                — Phase 12: audits ADV unit inflation (2017-2018)
  run_universe_filter_effectiveness — Phase 13: verifies universes are distinct

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .fh_universe import ALL_UNIVERSE_IDS, _assign_universe_membership

RESEARCH_ONLY_FLAG = "RESEARCH_ONLY_NOT_PRODUCTION"


# ---------------------------------------------------------------------------
# Phase 11: Build ticker-level membership from panel parquet
# ---------------------------------------------------------------------------

def build_membership_from_panel(
    panel_path: Path,
    out_dir: Path,
    verbose: bool = True,
) -> pd.DataFrame:
    """Build ticker-level universe membership from the full-history panel parquet.

    Loads the panel (288k rows, has scan_date + ticker + adv50_vnd), groups by
    scan_date, applies _assign_universe_membership per date, and saves:

      universe_membership_wide.parquet — columns: scan_date, ticker, adv50_vnd,
          adv50_rank, adv50_pct_rank, U0_ADV50_20B, U1_TOP_100_ADV50, ...,
          U3_ADV50_20B, is_vin, research_only_flag

      universe_membership_long.csv    — melted on universe_id, only is_member=True
          rows; useful for quick cross-tabulation

    Returns membership_wide DataFrame (scan_date + ticker keyed, boolean uid cols).

    Runtime: ~30 seconds for 288k rows / 720 scan_dates.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    panel = pd.read_parquet(panel_path)
    panel["scan_date"] = pd.to_datetime(panel["scan_date"]).dt.normalize()

    if "adv50_vnd" not in panel.columns:
        raise ValueError(
            f"Panel missing 'adv50_vnd' column. Available: {list(panel.columns)}"
        )

    scan_dates = sorted(panel["scan_date"].dropna().unique())
    if verbose:
        print(
            f"[Phase 11] Building ticker-level membership: "
            f"{len(scan_dates)} scan_dates, {len(panel):,} rows"
        )

    parts: list[pd.DataFrame] = []
    for i, dt in enumerate(scan_dates):
        sub = panel[panel["scan_date"] == dt][["ticker", "adv50_vnd"]].copy()
        sub = sub.dropna(subset=["adv50_vnd"])
        sub = sub[sub["adv50_vnd"] > 0]

        if sub.empty:
            continue

        adv50 = sub.set_index("ticker")["adv50_vnd"]
        membership = _assign_universe_membership(adv50)

        # Add rank columns
        membership["adv50_rank"] = (
            membership["adv50_vnd"].rank(ascending=False, method="min").astype(int)
        )
        n = len(membership)
        membership["adv50_pct_rank"] = membership["adv50_rank"] / n
        membership["scan_date"] = dt
        membership["research_only_flag"] = RESEARCH_ONLY_FLAG
        parts.append(membership)

        if verbose and i % 100 == 0:
            print(f"[Phase 11]   {i}/{len(scan_dates)} scan_dates processed")

    if not parts:
        print("[Phase 11] WARNING: no membership rows built (panel may be empty)")
        return pd.DataFrame()

    membership_wide = pd.concat(parts, ignore_index=True)

    # Reorder columns: scan_date, ticker first, uid booleans last
    uid_cols = [c for c in membership_wide.columns if c in ALL_UNIVERSE_IDS]
    meta_cols = [
        c for c in membership_wide.columns
        if c not in uid_cols and c not in ("scan_date", "ticker")
    ]
    col_order = (
        ["scan_date", "ticker"]
        + [c for c in meta_cols if c in membership_wide.columns]
        + uid_cols
    )
    membership_wide = membership_wide[[c for c in col_order if c in membership_wide.columns]]

    # Save parquet (primary — used by fh_validation and fh_portfolio)
    out_path = out_dir / "universe_membership_wide.parquet"
    membership_wide.to_parquet(out_path, index=False)
    if verbose:
        print(f"[Phase 11] Membership saved: {out_path} rows={len(membership_wide):,}")

    # Save long CSV (melted to is_member=True rows only)
    uid_cols_present = [c for c in membership_wide.columns if c in ALL_UNIVERSE_IDS]
    id_cols = [c for c in membership_wide.columns if c not in uid_cols_present]
    membership_long = membership_wide.melt(
        id_vars=id_cols,
        value_vars=uid_cols_present,
        var_name="universe_id",
        value_name="is_member",
    )
    membership_long = membership_long[membership_long["is_member"] == True].drop(
        columns=["is_member"]
    )
    long_path = out_dir / "universe_membership_long.csv"
    membership_long.to_csv(long_path, index=False)
    if verbose:
        print(f"[Phase 11] Membership long saved: {long_path} rows={len(membership_long):,}")

    return membership_wide


# ---------------------------------------------------------------------------
# Phase 12: ADV unit audit
# ---------------------------------------------------------------------------

def run_adv_unit_audit(
    loader: Any,
    panel: pd.DataFrame,
    out_dir: Path,
    verbose: bool = True,
) -> pd.DataFrame:
    """Audit ADV unit inflation in 2017-2018 parquet data.

    The universe_coverage_by_year.csv shows U0_ADV50_20B avg_adv50=8T VND in 2017
    (vs 13B in 2019). The formula close×volume×1000 assumes close is in kVND.
    If close is stored in full VND in 2017-2018 parquet, the formula inflates by 1000x.

    For sample tickers × sample years this function:
      - Computes adv50 via close×volume×1000 (fh_universe.py formula)
      - Compares against panel.adv50_vnd (ground truth from build_panel_fast)
      - Infers unit: PRICE_IN_KVND_USE_X1000 vs PRICE_IN_VND_NO_X1000

    Saves:
      adv_unit_audit.csv   — per-(ticker, year) comparison
      adv_unit_summary.csv — p50/p90 adv50_vnd by year from panel

    Returns audit DataFrame.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    SAMPLE_TICKERS = ["ACB", "VCB", "HPG", "MSN", "VIC", "FPT", "SSI", "CTG"]
    SAMPLE_YEARS = [2017, 2018, 2019, 2020, 2024]

    panel_copy = panel.copy()
    panel_copy["scan_date"] = pd.to_datetime(panel_copy["scan_date"]).dt.normalize()
    panel_copy["year"] = panel_copy["scan_date"].dt.year

    audit_rows: list[dict[str, Any]] = []

    for ticker in SAMPLE_TICKERS:
        df_raw = loader(ticker)
        if df_raw is None or df_raw.empty:
            continue
        df_raw = df_raw.copy()
        df_raw["date"] = pd.to_datetime(df_raw["date"], errors="coerce")

        for year in SAMPLE_YEARS:
            # Pick the first available scan_date for this ticker/year from panel
            panel_sub = panel_copy[
                (panel_copy["ticker"] == ticker) & (panel_copy["year"] == year)
            ]
            if panel_sub.empty:
                continue

            scan_dt = panel_sub["scan_date"].iloc[0]

            # Panel adv50_vnd = ground truth (computed by add_indicators)
            panel_adv50_val_s = panel_sub.loc[
                panel_sub["scan_date"] == scan_dt, "adv50_vnd"
            ]
            if panel_adv50_val_s.empty:
                continue
            panel_adv50_val = float(panel_adv50_val_s.iloc[0])

            # Compute from raw OHLCV: close × volume × 1000
            raw_50 = df_raw[df_raw["date"] <= scan_dt].tail(50)
            if len(raw_50) < 20:
                continue

            close_arr = pd.to_numeric(raw_50["close"], errors="coerce")
            vol_arr = pd.to_numeric(raw_50["volume"], errors="coerce")
            val_x1000 = (close_arr * vol_arr * 1000.0).dropna()
            val_no_x1000 = (close_arr * vol_arr).dropna()

            if len(val_x1000) == 0:
                continue

            adv50_x1000 = float(val_x1000.mean())
            adv50_no_x1000 = float(val_no_x1000.mean())

            # Infer unit by comparing ratio to panel (ground truth)
            ratio_x1000 = adv50_x1000 / panel_adv50_val if panel_adv50_val > 0 else None
            ratio_no_x1000 = (
                adv50_no_x1000 / panel_adv50_val if panel_adv50_val > 0 else None
            )

            inferred_unit = "UNKNOWN"
            if ratio_x1000 is not None and ratio_no_x1000 is not None:
                log_err_x1000 = abs(np.log10(max(ratio_x1000, 1e-10)))
                log_err_no_x1000 = abs(np.log10(max(ratio_no_x1000, 1e-10)))
                if log_err_x1000 <= log_err_no_x1000:
                    inferred_unit = "PRICE_IN_KVND_USE_X1000"
                else:
                    inferred_unit = "PRICE_IN_VND_NO_X1000"
                # Overflow guard: if ×1000 gives >100T, definitely wrong unit
                if adv50_x1000 > 100_000_000_000_000:  # 100T VND
                    inferred_unit = "PRICE_IN_VND_NO_X1000_OVERFLOW"

            close_vals = close_arr.dropna()
            vol_vals = vol_arr.dropna()
            audit_rows.append(
                {
                    "ticker": ticker,
                    "year": year,
                    "scan_date": scan_dt,
                    "close_sample": (
                        float(close_vals.iloc[-1]) if len(close_vals) > 0 else None
                    ),
                    "volume_sample": (
                        float(vol_vals.iloc[-1]) if len(vol_vals) > 0 else None
                    ),
                    "adv50_x1000_formula": adv50_x1000,
                    "adv50_no_x1000_formula": adv50_no_x1000,
                    "panel_adv50_vnd": panel_adv50_val,
                    "ratio_x1000_vs_panel": ratio_x1000,
                    "ratio_no_x1000_vs_panel": ratio_no_x1000,
                    "inferred_unit": inferred_unit,
                    "research_only_flag": RESEARCH_ONLY_FLAG,
                }
            )

    audit_df = pd.DataFrame(audit_rows)
    audit_df.to_csv(out_dir / "adv_unit_audit.csv", index=False)

    # Summary: p50/p90 adv50_vnd by year from panel (ground truth)
    year_groups = panel_copy.groupby("year")["adv50_vnd"]
    summary_rows = []
    for year_val, grp in year_groups:
        vals = grp.dropna()
        n_tickers_gt_20b = int(
            panel_copy[
                (panel_copy["year"] == year_val) & (panel_copy["adv50_vnd"] >= 20_000_000_000)
            ]["ticker"].nunique()
        )
        summary_rows.append(
            {
                "year": year_val,
                "p50_adv50_vnd": float(vals.quantile(0.50)) if len(vals) > 0 else None,
                "p90_adv50_vnd": float(vals.quantile(0.90)) if len(vals) > 0 else None,
                "n_ticker_dates": len(vals),
                "n_tickers_gt_20b": n_tickers_gt_20b,
                "research_only_flag": RESEARCH_ONLY_FLAG,
            }
        )
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(out_dir / "adv_unit_summary.csv", index=False)

    if verbose:
        print(
            f"[Phase 12] ADV unit audit: {len(audit_rows)} samples -> "
            f"{out_dir / 'adv_unit_audit.csv'}"
        )
        if not audit_df.empty:
            unit_counts = audit_df["inferred_unit"].value_counts()
            print(f"[Phase 12] Unit inference: {unit_counts.to_dict()}")
        print(
            f"[Phase 12] ADV summary: {out_dir / 'adv_unit_summary.csv'} "
            f"({len(summary_rows)} years)"
        )

    return audit_df


# ---------------------------------------------------------------------------
# Phase 13: Universe filter effectiveness audit
# ---------------------------------------------------------------------------

def run_universe_filter_effectiveness(
    membership_wide: pd.DataFrame,
    portfolio_metrics: pd.DataFrame,
    out_dir: Path,
    verbose: bool = True,
) -> pd.DataFrame:
    """Verify that the universe filter produces distinct candidate sets per universe.

    v0.1 bug: all 5 universes showed identical 262,843 eligible rows because
    filtering was date-only — this function guards against regression.

    Checks:
    - Member counts per (universe_id, year) — should differ across universes
    - TOP_100 count < TOP_200 count < TOP_300 count for each year (expected ordering)
    - Guard: if portfolio metrics are identical across all universes → BLOCKED flag

    Saves universe_filter_effectiveness.csv.
    Returns effectiveness DataFrame.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    uid_cols = [c for c in membership_wide.columns if c in ALL_UNIVERSE_IDS]

    mw = membership_wide.copy()
    mw["year"] = pd.to_datetime(mw["scan_date"]).dt.year

    rows: list[pd.DataFrame] = []
    for uid in uid_cols:
        members = mw[mw[uid] == True]
        if members.empty:
            continue
        by_year = (
            members.groupby("year")["ticker"]
            .nunique()
            .reset_index()
            .rename(columns={"ticker": "unique_tickers"})
        )
        by_year["universe_id"] = uid
        by_year["member_date_rows"] = (
            members.groupby("year").size().reindex(by_year["year"]).values
        )
        rows.append(by_year)

    effectiveness_df = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()

    # Guard: check if portfolio metrics are identical across universes
    guard_status = "MEMBERSHIP_NOT_COMPUTED"
    if not effectiveness_df.empty:
        # Check ordering for a sample year
        sample_year = effectiveness_df["year"].median()
        sy = effectiveness_df[effectiveness_df["year"] == sample_year]
        top100 = sy[sy["universe_id"] == "U1_TOP_100_ADV50"]["unique_tickers"].values
        top200 = sy[sy["universe_id"] == "U1_TOP_200_ADV50"]["unique_tickers"].values
        top300 = sy[sy["universe_id"] == "U1_TOP_300_ADV50"]["unique_tickers"].values
        if len(top100) > 0 and len(top200) > 0 and len(top300) > 0:
            if int(top100[0]) < int(top200[0]) <= int(top300[0]):
                guard_status = "ORDERING_CORRECT"
            else:
                guard_status = "ORDERING_ANOMALY"
        else:
            guard_status = "OK"

    # Check portfolio distinctness
    if not portfolio_metrics.empty and "universe_id" in portfolio_metrics.columns:
        pm_sub = portfolio_metrics
        if "rank_mode" in pm_sub.columns:
            pm_sub = pm_sub[pm_sub["rank_mode"] == "score_desc"]
        if "cumulative_net_return" in pm_sub.columns:
            cum_by_uid = pm_sub.groupby("universe_id")["cumulative_net_return"].mean()
            if len(cum_by_uid) > 1:
                ret_std = float(cum_by_uid.std())
                if ret_std < 1e-10:
                    guard_status = "BLOCKED_UNIVERSE_FILTER_NOT_EFFECTIVE"
                    if verbose:
                        print(
                            "[Phase 13] GUARD: portfolio cum_returns identical "
                            "→ BLOCKED_UNIVERSE_FILTER_NOT_EFFECTIVE"
                        )
                else:
                    guard_status = f"FILTER_EFFECTIVE_std={ret_std:.4f}"

    if not effectiveness_df.empty:
        effectiveness_df["guard_status"] = guard_status
        effectiveness_df["research_only_flag"] = RESEARCH_ONLY_FLAG

    out_path = out_dir / "universe_filter_effectiveness.csv"
    effectiveness_df.to_csv(out_path, index=False)

    if verbose:
        print(
            f"[Phase 13] Effectiveness saved: {out_path} "
            f"rows={len(effectiveness_df)}, guard={guard_status}"
        )

    return effectiveness_df
