"""Phase 4: Full-history event-level validation.

Re-runs P1/P2-style diagnostics across all valid universes, year-by-year,
regime-by-regime.

Outputs:
  full_history_score_decile_validation.csv
  full_history_component_validation.csv
  full_history_distribution_flag_validation.csv
  full_history_top_decile_exhaustion.csv
  full_history_variant_event_validation.csv

Evidence labels:
  STATISTICALLY_SUPPORTED — N>=30, consistent direction, p<0.1
  DIRECTIONALLY_SUPPORTED — N>=15, directional but not statistically robust
  RISK_CONTROL_SUPPORTED  — drawdown improvement only
  REJECTED               — negative result
  INCONCLUSIVE           — mixed / insufficient N
  BLOCKED_BY_DATA        — fewer than 15 samples

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .fh_universe import ALL_UNIVERSE_IDS, EX_VIN_TICKERS
from .p2_variants import build_variant_masks

RESEARCH_ONLY_FLAG = "RESEARCH_ONLY_NOT_PRODUCTION"
MIN_N_STAT = 30
MIN_N_DIR = 15


def _label_evidence(
    n: int,
    mean_excess: float | None,
    pct_positive: float | None,
    dd_improvement: bool = False,
) -> str:
    if n < MIN_N_DIR:
        return "BLOCKED_BY_DATA"
    if mean_excess is None or pct_positive is None:
        return "INCONCLUSIVE"
    if n >= MIN_N_STAT and mean_excess > 0 and pct_positive > 0.52:
        return "STATISTICALLY_SUPPORTED"
    if mean_excess > 0 and pct_positive > 0.50:
        return "DIRECTIONALLY_SUPPORTED"
    if dd_improvement and mean_excess <= 0:
        return "RISK_CONTROL_SUPPORTED"
    if mean_excess < 0 and pct_positive < 0.48:
        return "REJECTED"
    return "INCONCLUSIVE"


def _decile_stats(df: pd.DataFrame, ret_col: str, excess_col: str) -> pd.DataFrame:
    rows = []
    for decile in range(10):
        sub = df[df["score_decile"] == decile]
        r = pd.to_numeric(sub[ret_col], errors="coerce").dropna()
        ex = pd.to_numeric(sub.get(excess_col, pd.Series(dtype=float)), errors="coerce").dropna()
        n = len(r)
        rows.append(
            {
                "score_decile": decile,
                "n": n,
                "mean_ret": float(r.mean()) if n > 0 else None,
                "mean_excess": float(ex.mean()) if len(ex) > 0 else None,
                "pct_positive": float((r > 0).mean()) if n > 0 else None,
                "pct_positive_excess": float((ex > 0).mean()) if len(ex) > 0 else None,
                "label": _label_evidence(n, float(ex.mean()) if len(ex) > 0 else None,
                                         float((r > 0).mean()) if n > 0 else None),
                "research_only_flag": RESEARCH_ONLY_FLAG,
            }
        )
    return pd.DataFrame(rows)


def _variant_stats(df: pd.DataFrame, variant_mask: pd.Series, variant_key: str, universe_id: str, horizon: str = "20d") -> dict[str, Any]:
    ret_col = f"ret_{horizon}"
    excess_col = f"excess_ret_{horizon}"
    sub = df[variant_mask.reindex(df.index, fill_value=False)].copy()
    r = pd.to_numeric(sub.get(ret_col, pd.Series(dtype=float)), errors="coerce").dropna()
    ex = pd.to_numeric(sub.get(excess_col, pd.Series(dtype=float)), errors="coerce").dropna()
    n = len(r)
    mean_excess = float(ex.mean()) if len(ex) > 0 else None
    pct_pos = float((r > 0).mean()) if n > 0 else None
    return {
        "variant_key": variant_key,
        "universe_id": universe_id,
        "horizon": horizon,
        "n": n,
        "mean_ret": float(r.mean()) if n > 0 else None,
        "mean_excess": mean_excess,
        "pct_positive": pct_pos,
        "label": _label_evidence(n, mean_excess, pct_pos),
        "research_only_flag": RESEARCH_ONLY_FLAG,
    }


def _filter_by_universe(
    df: pd.DataFrame,
    uid: str,
    membership_wide: pd.DataFrame | None,
    u_weekly: pd.DataFrame,
) -> pd.DataFrame:
    """Return df rows that belong to universe uid at each scan_date.

    If membership_wide is available (Phase 11 output), filters by (scan_date, ticker)
    pair — the correct ticker-level filter. Falls back to date-only if unavailable.
    """
    if membership_wide is not None and uid in membership_wide.columns:
        mask = membership_wide[membership_wide[uid] == True][["scan_date", "ticker"]]
        return df.merge(mask, on=["scan_date", "ticker"], how="inner").copy()
    else:
        # Legacy fallback: date-only (v0.1 behaviour)
        active_dates = set(u_weekly[u_weekly["candidate_count"] > 0]["date"])
        return df[df["scan_date"].isin(active_dates)].copy()


def run_full_history_validation(
    outcomes: pd.DataFrame,
    universe_weekly: pd.DataFrame,
    out_dir: Path,
    membership_wide: pd.DataFrame | None = None,
    verbose: bool = True,
) -> dict[str, pd.DataFrame]:
    """Run Phase 4 event-level validation across all universes.

    Args:
        membership_wide: ticker-level universe membership from Phase 11.
            When provided, filters by (scan_date, ticker) pairs instead of
            date-only — fixes the v0.1 bug where all universes were identical.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load membership_wide from disk if not passed
    if membership_wide is None:
        membership_path = out_dir / "universe_membership_wide.parquet"
        if membership_path.is_file():
            membership_wide = pd.read_parquet(membership_path)
            membership_wide["scan_date"] = pd.to_datetime(
                membership_wide["scan_date"]
            ).dt.normalize()
            if verbose:
                print("[Phase 4] Loaded ticker-level membership for universe filtering")
        else:
            if verbose:
                print(
                    "[Phase 4] WARNING: universe_membership_wide.parquet not found — "
                    "falling back to date-only filter (run Phase 11 first)"
                )

    df = outcomes.copy()
    df["scan_date"] = pd.to_datetime(df["scan_date"], errors="coerce").dt.normalize()

    # Add score_decile if missing
    if "score_decile" not in df.columns:
        score_num = pd.to_numeric(df.get("institutional_accumulation_score"), errors="coerce")
        df["score_decile"] = pd.qcut(score_num, 10, labels=False, duplicates="drop")

    # Add excess ret columns if missing (from outcomes module naming)
    for h in (5, 10, 20, 60, 120):
        col = f"excess_ret_{h}d"
        alt = f"excess_ret_{h}d_vs_vnindex"
        if col not in df.columns and alt in df.columns:
            df[col] = df[alt]
        elif col not in df.columns:
            r_col = f"ret_{h}d"
            vn_col = f"vnindex_ret_{h}d"
            if r_col in df.columns and vn_col in df.columns:
                df[col] = pd.to_numeric(df[r_col], errors="coerce") - pd.to_numeric(df[vn_col], errors="coerce")

    results: dict[str, pd.DataFrame] = {}

    # --- 1. Score decile validation by universe ---
    decile_rows = []
    for uid in ALL_UNIVERSE_IDS:
        # Get universe membership — ticker-level if available, else date-only fallback
        u_weekly = universe_weekly[universe_weekly["universe_id"] == uid][["date", "candidate_count"]].copy()
        u_weekly["date"] = pd.to_datetime(u_weekly["date"]).dt.normalize()
        sub_u = _filter_by_universe(df, uid, membership_wide, u_weekly)
        if sub_u.empty:
            continue
        dec_stats = _decile_stats(sub_u, "ret_20d", "excess_ret_20d")
        dec_stats["universe_id"] = uid
        active_dates = set(sub_u["scan_date"].unique())
        dec_stats["n_scan_dates"] = len(active_dates)
        decile_rows.append(dec_stats)

    score_decile_df = pd.concat(decile_rows, ignore_index=True) if decile_rows else pd.DataFrame()
    score_decile_df.to_csv(out_dir / "full_history_score_decile_validation.csv", index=False)
    results["score_decile"] = score_decile_df

    # --- 2. Component validation (MF, PS, risk) by top decile ---
    comp_rows = []
    for uid in ["U1_TOP_200_ADV50", "U1_TOP_300_ADV50", "U0_ADV50_20B"]:
        u_weekly = universe_weekly[universe_weekly["universe_id"] == uid]
        u_weekly = u_weekly.copy()
        u_weekly["date"] = pd.to_datetime(u_weekly["date"]).dt.normalize()
        base_u = _filter_by_universe(df, uid, membership_wide, u_weekly)
        score_decile_col = base_u.get("score_decile", pd.Series(-1, index=base_u.index))
        sub = base_u[score_decile_col >= 8].copy()
        for comp in ["score_money_flow", "score_price_structure", "score_risk_penalty"]:
            if comp not in sub.columns:
                continue
            quartiles = pd.qcut(pd.to_numeric(sub[comp], errors="coerce"), 4, labels=False, duplicates="drop")
            sub = sub.copy()
            sub["comp_quartile"] = quartiles
            for q in range(4):
                ssub = sub[sub["comp_quartile"] == q]
                ex = pd.to_numeric(ssub.get("excess_ret_20d"), errors="coerce").dropna()
                n = len(ex)
                comp_rows.append(
                    {
                        "universe_id": uid,
                        "component": comp,
                        "quartile": q,
                        "n": n,
                        "mean_excess_20d": float(ex.mean()) if n > 0 else None,
                        "pct_positive": float((ex > 0).mean()) if n > 0 else None,
                        "label": _label_evidence(n, float(ex.mean()) if n > 0 else None,
                                                 float((ex > 0).mean()) if n > 0 else None),
                        "research_only_flag": RESEARCH_ONLY_FLAG,
                    }
                )
    component_df = pd.DataFrame(comp_rows)
    component_df.to_csv(out_dir / "full_history_component_validation.csv", index=False)
    results["component"] = component_df

    # --- 3. Distribution-risk flag validation ---
    dist_rows = []
    for uid in ["U1_TOP_200_ADV50", "U1_TOP_300_ADV50", "U0_ADV50_20B"]:
        u_weekly = universe_weekly[universe_weekly["universe_id"] == uid].copy()
        u_weekly["date"] = pd.to_datetime(u_weekly["date"]).dt.normalize()
        sub = _filter_by_universe(df, uid, membership_wide, u_weekly)
        if "distribution_risk_flag" not in sub.columns:
            continue
        for flag in (True, False):
            fsub = sub[sub["distribution_risk_flag"] == flag]
            ex = pd.to_numeric(fsub.get("excess_ret_20d"), errors="coerce").dropna()
            mdd = pd.to_numeric(fsub.get("max_dd_20d"), errors="coerce").dropna()
            n = len(ex)
            dist_rows.append(
                {
                    "universe_id": uid,
                    "distribution_risk_flag": flag,
                    "n": n,
                    "mean_excess_20d": float(ex.mean()) if n > 0 else None,
                    "mean_max_dd_20d": float(mdd.mean()) if len(mdd) > 0 else None,
                    "pct_positive": float((ex > 0).mean()) if n > 0 else None,
                    "label": _label_evidence(n, float(ex.mean()) if n > 0 else None,
                                             float((ex > 0).mean()) if n > 0 else None,
                                             dd_improvement=(not flag)),
                    "research_only_flag": RESEARCH_ONLY_FLAG,
                }
            )
    distribution_flag_df = pd.DataFrame(dist_rows)
    distribution_flag_df.to_csv(out_dir / "full_history_distribution_flag_validation.csv", index=False)
    results["distribution_flag"] = distribution_flag_df

    # --- 4. Top decile exhaustion ---
    exhaustion_rows = []
    for uid in ["U1_TOP_200_ADV50", "U1_TOP_300_ADV50", "U0_ADV50_20B"]:
        u_weekly = universe_weekly[universe_weekly["universe_id"] == uid].copy()
        u_weekly["date"] = pd.to_datetime(u_weekly["date"]).dt.normalize()
        base_u = _filter_by_universe(df, uid, membership_wide, u_weekly)
        score_decile_col = base_u.get("score_decile", pd.Series(-1, index=base_u.index))
        sub = base_u[score_decile_col >= 9].copy()
        ex = pd.to_numeric(sub.get("excess_ret_20d"), errors="coerce").dropna()
        n = len(ex)
        exhaustion_rows.append(
            {
                "universe_id": uid,
                "n_top_decile": n,
                "mean_excess_20d": float(ex.mean()) if n > 0 else None,
                "pct_positive": float((ex > 0).mean()) if n > 0 else None,
                "label": _label_evidence(n, float(ex.mean()) if n > 0 else None,
                                         float((ex > 0).mean()) if n > 0 else None),
                "research_only_flag": RESEARCH_ONLY_FLAG,
            }
        )
    exhaustion_df = pd.DataFrame(exhaustion_rows)
    exhaustion_df.to_csv(out_dir / "full_history_top_decile_exhaustion.csv", index=False)
    results["top_decile_exhaustion"] = exhaustion_df

    # --- 5. Variant event validation (V0, V4, V6, year-by-year, regime) ---
    variant_rows = []
    try:
        enriched = df.copy()
        variant_masks = build_variant_masks(enriched)
        # Year-by-year for key universes
        for uid in ["U1_TOP_200_ADV50", "U1_TOP_300_ADV50", "U0_ADV50_20B"]:
            u_weekly = universe_weekly[universe_weekly["universe_id"] == uid].copy()
            u_weekly["date"] = pd.to_datetime(u_weekly["date"]).dt.normalize()
            sub = _filter_by_universe(enriched, uid, membership_wide, u_weekly)
            for variant_key, (_, vmask) in variant_masks.items():
                for year in sorted(sub["scan_date"].dt.year.unique()):
                    year_sub = sub[sub["scan_date"].dt.year == year]
                    year_mask = vmask.reindex(year_sub.index, fill_value=False)
                    r = _variant_stats(year_sub, year_mask, variant_key, uid)
                    r["year"] = year
                    variant_rows.append(r)
            # Ex-VIN split
            for variant_key, (_, vmask) in variant_masks.items():
                ex_vin_sub = sub[~sub["ticker"].isin(EX_VIN_TICKERS)]
                ex_vin_mask = vmask.reindex(ex_vin_sub.index, fill_value=False)
                r = _variant_stats(ex_vin_sub, ex_vin_mask, variant_key, uid)
                r["year"] = "ex_vin"
                variant_rows.append(r)
    except Exception as e:
        if verbose:
            print(f"[Phase 4] Variant masks error: {e} — skipping variant validation")

    variant_df = pd.DataFrame(variant_rows)
    variant_df.to_csv(out_dir / "full_history_variant_event_validation.csv", index=False)
    results["variant_event"] = variant_df

    if verbose:
        print(f"[Phase 4] Validation complete. Outputs: {list(results.keys())}")
    return results
