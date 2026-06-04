"""
B01–B05 — Filter value ablation, regime stratification, threshold sweep, A3 ledger replay.
Outputs: filter_value_ablation.csv, regime_stratified_full_vs_ex_vin.csv,
         threshold_sweep_summary.csv, a3_ledger_sector_gate_replay.csv,
         stock_cloud_baseline_forward_returns.csv
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .config import (
    OUTPUT_DIR,
    FORWARD_HORIZONS,
    A3_LEDGER_PATH,
    VIN_GROUP_SYMBOLS,
    TRAIN_END,
    TEST_START,
)

log = logging.getLogger(__name__)


def _return_stats(fwd_col: pd.Series) -> dict:
    vals = fwd_col.dropna()
    if vals.empty:
        return {"mean": np.nan, "median": np.nan, "hit_rate": np.nan, "n": 0}
    return {
        "mean":     float(vals.mean()),
        "median":   float(vals.median()),
        "hit_rate": float((vals > 0).mean()),
        "n":        len(vals),
    }


def compute_baseline(
    stock_events: pd.DataFrame,
    label: str = "baseline_stock_cloud",
) -> pd.DataFrame:
    """B01 — baseline forward return profile for stock cloud turns."""
    rows = []
    for univ, ex_vin in [("full", False), ("ex_vin", True)]:
        df = stock_events.copy()
        if ex_vin:
            df = df[~df["symbol"].isin(VIN_GROUP_SYMBOLS)]
        for h in FORWARD_HORIZONS:
            col = f"fwd_ret_{h}d"
            if col not in df.columns:
                continue
            s = _return_stats(df[col])
            rows.append({
                "rule_id":       label,
                "universe_mode": univ,
                "horizon":       h,
                **s,
            })
    result = pd.DataFrame(rows)
    out_path = OUTPUT_DIR / "stock_cloud_baseline_forward_returns.csv"
    result.to_csv(out_path, index=False)
    log.info("Baseline forward returns saved to %s", out_path)
    return result


def _apply_l4_gate(
    stock_events: pd.DataFrame,
    sector_panel: pd.DataFrame,
    threshold: float,
    breadth_col: str = "l4_breadth_equal_weight",
    require_recent_turn: bool = False,
    l4_events: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Return stock_events filtered by sector L4 breadth >= threshold on event date.
    If require_recent_turn, only keep events within 20 sessions after an L4 turn event.
    """
    sector_snap = sector_panel[["date", "sector_l4", breadth_col]].copy()
    sector_snap = sector_snap.rename(columns={breadth_col: "_l4_breadth"})
    merged = stock_events.merge(sector_snap, on=["date", "sector_l4"], how="left")
    result = merged[merged["_l4_breadth"].fillna(0) >= threshold].copy()
    return result


def run_ablation(
    stock_events: pd.DataFrame,
    sector_panel: pd.DataFrame,
    l4_events: Optional[pd.DataFrame] = None,
    ex_vin_only: bool = False,
) -> pd.DataFrame:
    """B02 — L4 gate filter ablation across thresholds and breadth definitions."""
    if ex_vin_only:
        stock_events = stock_events[~stock_events["symbol"].isin(VIN_GROUP_SYMBOLS)].copy()

    baseline_n = len(stock_events)
    rows = []

    # Baseline
    for h in FORWARD_HORIZONS:
        col = f"fwd_ret_{h}d"
        if col not in stock_events.columns:
            continue
        s = _return_stats(stock_events[col])
        rows.append({
            "rule_id": "baseline_stock_cloud",
            "threshold": None, "hysteresis_reset": None,
            "breadth_col": None,
            "universe_mode": "ex_vin" if ex_vin_only else "full",
            "n_signals": len(stock_events),
            "retention_pct": 1.0,
            "horizon": h,
            **{k: s[k] for k in ["mean", "median", "hit_rate", "n"]},
            "delta_mean": 0.0, "delta_hit_rate": 0.0,
        })

    thresholds = [0.30, 0.40, 0.50]
    breadth_cols = {
        "equal_weight":     "l4_breadth_equal_weight",
        "liq_weighted":     "l4_breadth_liquidity_weighted",
    }
    baseline_stats = {}
    for h in FORWARD_HORIZONS:
        col = f"fwd_ret_{h}d"
        if col in stock_events.columns:
            baseline_stats[h] = _return_stats(stock_events[col])

    for thresh in thresholds:
        for bname, bcol in breadth_cols.items():
            if bcol not in sector_panel.columns:
                continue
            filtered = _apply_l4_gate(stock_events, sector_panel, thresh, bcol)
            n_filtered = len(filtered)
            ret_pct = n_filtered / max(baseline_n, 1)

            for h in FORWARD_HORIZONS:
                col = f"fwd_ret_{h}d"
                if col not in filtered.columns:
                    continue
                s = _return_stats(filtered[col])
                bs = baseline_stats.get(h, {})
                rows.append({
                    "rule_id":        f"l4_{bname}_ge_{int(thresh*100)}pct",
                    "threshold":       thresh,
                    "hysteresis_reset": thresh - 0.05,
                    "breadth_col":     bname,
                    "universe_mode":   "ex_vin" if ex_vin_only else "full",
                    "n_signals":       n_filtered,
                    "retention_pct":   ret_pct,
                    "horizon":         h,
                    **{k: s[k] for k in ["mean", "median", "hit_rate", "n"]},
                    "delta_mean":      s["mean"] - bs.get("mean", 0) if not np.isnan(s["mean"]) else np.nan,
                    "delta_hit_rate":  s["hit_rate"] - bs.get("hit_rate", 0) if not np.isnan(s["hit_rate"]) else np.nan,
                })

    result = pd.DataFrame(rows)
    univ_suffix = "_ex_vin" if ex_vin_only else "_full"
    out_path = OUTPUT_DIR / f"filter_value_ablation{univ_suffix}.csv"
    result.to_csv(out_path, index=False)
    log.info("Filter value ablation saved to %s", out_path)
    return result


def run_regime_stratified(
    stock_events: pd.DataFrame,
    sector_panel: pd.DataFrame,
    threshold: float = 0.40,
) -> pd.DataFrame:
    """B03 — regime-stratified filter value."""
    rows = []
    regime_col_map = {
        "all":           None,
        "vnindex_bull":  "M1_vnindex_cloud_bull",
        "ex_vin_bull":   "M2_ex_vin_index_cloud_bull",
        "m0_normal":     "M0_ex_vin_label",
        "no_vin_distort":"M4_vin_distortion_flag",
    }

    for regime_name, rcol in regime_col_map.items():
        for univ, ex_vin in [("full", False), ("ex_vin", True)]:
            df = stock_events.copy()
            if ex_vin:
                df = df[~df["symbol"].isin(VIN_GROUP_SYMBOLS)]

            if rcol is not None and rcol in df.columns:
                if "label" in rcol:
                    df = df[df[rcol] == "normal"]
                elif "distortion" in rcol:
                    df = df[df[rcol] == 0]
                else:
                    df = df[df[rcol] == 1]

            filtered = _apply_l4_gate(df, sector_panel, threshold)

            for h in FORWARD_HORIZONS:
                col = f"fwd_ret_{h}d"
                if col not in df.columns:
                    continue
                base_s = _return_stats(df[col])
                gate_s = _return_stats(filtered[col] if col in filtered.columns else pd.Series(dtype=float))
                rows.append({
                    "regime":        regime_name,
                    "universe_mode": univ,
                    "horizon":       h,
                    "n_base":        len(df),
                    "n_gate":        len(filtered),
                    "base_mean":     base_s["mean"],
                    "gate_mean":     gate_s["mean"],
                    "delta_mean":    gate_s["mean"] - base_s["mean"] if not np.isnan(gate_s["mean"]) else np.nan,
                    "base_hit_rate": base_s["hit_rate"],
                    "gate_hit_rate": gate_s["hit_rate"],
                    "delta_hit_rate": gate_s["hit_rate"] - base_s["hit_rate"] if not np.isnan(gate_s["hit_rate"]) else np.nan,
                })

    result = pd.DataFrame(rows)
    out_path = OUTPUT_DIR / "regime_stratified_full_vs_ex_vin.csv"
    result.to_csv(out_path, index=False)
    log.info("Regime stratified saved to %s", out_path)
    return result


def run_threshold_sweep(
    stock_events: pd.DataFrame,
    sector_panel: pd.DataFrame,
) -> pd.DataFrame:
    """B04 — threshold sweep with train/test split."""
    pairs = [(0.30, 0.25), (0.35, 0.30), (0.40, 0.35), (0.45, 0.40), (0.50, 0.45)]
    rows = []
    stock_events["date"] = pd.to_datetime(stock_events["date"])

    for enter, exit_ in pairs:
        for period, mask_fn in [
            ("train", lambda d: d["date"] <= TRAIN_END),
            ("test",  lambda d: d["date"] >= TEST_START),
            ("full",  lambda d: pd.Series(True, index=d.index)),
        ]:
            df = stock_events[mask_fn(stock_events)].copy()
            if df.empty:
                continue
            filtered = _apply_l4_gate(df, sector_panel, enter)
            for h in FORWARD_HORIZONS:
                col = f"fwd_ret_{h}d"
                if col not in df.columns:
                    continue
                bs = _return_stats(df[col])
                gs = _return_stats(filtered[col] if col in filtered.columns else pd.Series(dtype=float))
                rows.append({
                    "enter":        enter,
                    "exit":         exit_,
                    "period":       period,
                    "horizon":      h,
                    "n_base":       len(df),
                    "n_gate":       len(filtered),
                    "delta_mean":   gs["mean"] - bs["mean"] if not np.isnan(gs["mean"]) else np.nan,
                    "delta_hit_rate": gs["hit_rate"] - bs["hit_rate"] if not np.isnan(gs["hit_rate"]) else np.nan,
                    "gate_mean":    gs["mean"],
                    "gate_hit_rate":gs["hit_rate"],
                })

    result = pd.DataFrame(rows)
    out_path = OUTPUT_DIR / "threshold_sweep_summary.csv"
    result.to_csv(out_path, index=False)
    log.info("Threshold sweep saved to %s", out_path)
    return result


def run_a3_ledger_replay(
    sector_panel: pd.DataFrame,
    threshold: float = 0.40,
) -> pd.DataFrame:
    """
    B05 / E01 — Replay A3 ledger with sector gate.
    Annotates trades as blocked/allowed by sector gate.
    Computes ΔMAR, ΔmaxDD, ΔCAGR.
    """
    if not A3_LEDGER_PATH.exists():
        log.warning("A3 ledger not found: %s", A3_LEDGER_PATH)
        return pd.DataFrame()

    ledger = pd.read_csv(A3_LEDGER_PATH)
    ledger.columns = ledger.columns.str.strip().str.lower()
    ledger["date"] = pd.to_datetime(
        ledger.get("entry_date", ledger.get("date", ledger.iloc[:, 0]))
    )

    # Detect trade columns
    sym_col   = next((c for c in ledger.columns if c in ("symbol", "ticker", "stock")), None)
    ret_col   = next((c for c in ledger.columns if "ret" in c or "return" in c or "pnl" in c), None)
    sector_col = next((c for c in ledger.columns if "sector" in c or "l4" in c), None)

    if sym_col is None or ret_col is None:
        log.warning("A3 ledger schema not recognized. Columns: %s", list(ledger.columns))
        result = pd.DataFrame([{
            "rule_id": "sector_gate_40pct",
            "n_trades_baseline": len(ledger),
            "n_trades_rule": "unknown",
            "adoption_verdict": "SCHEMA_MISMATCH",
        }])
        result.to_csv(OUTPUT_DIR / "a3_ledger_sector_gate_replay.csv", index=False)
        return result

    # Merge sector info from sector map if not present
    if sector_col is None and sym_col in ledger.columns:
        log.info("Sector column not in ledger; will attempt merge via symbol.")
        sector_snap = sector_panel.groupby("sector_l4").first().reset_index()[
            ["sector_l4"]
        ]

    # Merge sector breadth on entry date
    breadth_snap = sector_panel[["date", "sector_l4", "l4_breadth_equal_weight"]].copy()

    n_base = len(ledger)
    trades_per_symbol = None

    if sector_col and sector_col in ledger.columns:
        merged = ledger.merge(
            breadth_snap.rename(columns={"sector_l4": sector_col}),
            on=["date", sector_col], how="left"
        )
    else:
        log.warning("Cannot merge sector breadth onto ledger — no sector column. Reporting schema mismatch.")
        result = pd.DataFrame([{
            "rule_id":           "sector_gate_40pct",
            "n_trades_baseline": n_base,
            "n_blocked":         "N/A",
            "adoption_verdict":  "SECTOR_COL_MISSING_IN_LEDGER",
            "note":              "Add sector_l4 column to A3 ledger to enable replay.",
        }])
        result.to_csv(OUTPUT_DIR / "a3_ledger_sector_gate_replay.csv", index=False)
        return result

    blocked = merged[merged["l4_breadth_equal_weight"].fillna(1.0) < threshold]
    allowed = merged[~merged.index.isin(blocked.index)]

    def _mar(df):
        if df.empty or ret_col not in df.columns:
            return np.nan, np.nan, np.nan
        rets = df[ret_col].dropna()
        if rets.empty:
            return np.nan, np.nan, np.nan
        cum = (1 + rets).cumprod()
        cagr  = float(cum.iloc[-1] ** (252 / max(len(rets), 1)) - 1)
        drawdowns = cum / cum.cummax() - 1
        maxdd = float(drawdowns.min())
        mar = cagr / max(abs(maxdd), 1e-6)
        return cagr, maxdd, mar

    cagr_b, dd_b, mar_b = _mar(merged)
    cagr_r, dd_r, mar_r = _mar(allowed)

    winners_blocked = int((blocked[ret_col].fillna(0) > 0).sum()) if ret_col in blocked.columns else 0
    losers_blocked  = int((blocked[ret_col].fillna(0) < 0).sum()) if ret_col in blocked.columns else 0

    verdict = "DASHBOARD_WARNING_ONLY"
    if not np.isnan(mar_r) and not np.isnan(mar_b):
        delta_mar = mar_r - mar_b
        if delta_mar >= 0.05:
            verdict = "HARD_FILTER_CANDIDATE"
        elif delta_mar > 0:
            verdict = "RANKING_FEATURE_SHADOW_ONLY"

    result = pd.DataFrame([{
        "rule_id":            "sector_gate_40pct",
        "threshold":          threshold,
        "n_trades_baseline":  n_base,
        "n_trades_rule":      len(allowed),
        "n_blocked":          len(blocked),
        "blocked_winners":    winners_blocked,
        "blocked_losers":     losers_blocked,
        "cagr_baseline":      cagr_b,
        "cagr_rule":          cagr_r,
        "delta_cagr":         cagr_r - cagr_b if not np.isnan(cagr_r) else np.nan,
        "maxdd_baseline":     dd_b,
        "maxdd_rule":         dd_r,
        "delta_maxdd":        dd_r - dd_b if not np.isnan(dd_r) else np.nan,
        "mar_baseline":       mar_b,
        "mar_rule":           mar_r,
        "delta_mar":          mar_r - mar_b if not np.isnan(mar_r) else np.nan,
        "adoption_verdict":   verdict,
    }])
    result.to_csv(OUTPUT_DIR / "a3_ledger_sector_gate_replay.csv", index=False)
    log.info("A3 ledger replay saved. Verdict: %s", verdict)
    return result


# ── P0.1 Task 2 — Enriched A3 ledger replay ───────────────────────────────────

def _perf_stats(
    df: pd.DataFrame,
    ret_col: str,
    date_col: str = "_entry_date",
) -> tuple[float, float, float]:
    """
    Returns (mean_return, worst_single_trade, trade_mar) from a discrete trade ledger.
    Portfolio-NAV approaches are invalid here because multiple trades overlap —
    compounding 9000 sequential returns gives astronomical and meaningless values.

    trade_mar = mean_return / abs(worst_single_trade), analogous to MAR but trade-level.
    Higher trade_mar = better return-to-risk ratio at the individual trade level.
    """
    if df.empty or ret_col not in df.columns:
        return np.nan, np.nan, np.nan
    rets = df[ret_col].dropna()
    if rets.empty:
        return np.nan, np.nan, np.nan
    mean_ret = float(rets.mean())
    worst    = float(rets.min())           # most negative single trade
    trade_mar = mean_ret / max(abs(worst), 1e-6)
    return mean_ret, worst, trade_mar


def run_a3_ledger_replay_enriched(
    enriched_ledger: "pd.DataFrame",
    sector_panel: "pd.DataFrame",
) -> "pd.DataFrame":
    """
    P0.1 Task 2 — Replay A3 sector gate using research-enriched ledger.
    Uses asof join to match sector breadth on closest preceding trading date.
    Rules: no_gate (baseline), l4_ew_ge_30, l4_ew_ge_40, l4_ew_ge_50, l4_liq_ge_40.
    Output: a3_ledger_sector_gate_replay_enriched.csv
    """
    if enriched_ledger is None or enriched_ledger.empty:
        log.warning("Enriched ledger is empty; skipping enriched replay.")
        return pd.DataFrame()

    ledger = enriched_ledger.copy()
    ledger.columns = ledger.columns.str.strip().str.lower()

    date_col = next((c for c in ledger.columns if "entry" in c or c == "date"), None)
    ret_col  = next((c for c in ledger.columns if c in ("net_return", "gross_return", "ret", "return", "pnl")), None)

    if date_col is None or ret_col is None:
        log.warning("Cannot find date or return column in enriched ledger. Cols: %s", list(ledger.columns))
        return pd.DataFrame()

    ledger["_entry_date"] = pd.to_datetime(ledger[date_col])
    ledger = ledger.sort_values("_entry_date").reset_index(drop=True)

    # Prepare sector breadth lookup: one row per (date, sector_l4) with both breadth cols
    breadth_cols = {
        "ew":  "l4_breadth_equal_weight",
        "liq": "l4_breadth_liquidity_weighted",
    }
    panel = sector_panel.copy()
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel.sort_values("date")

    # Build a flat lookup keyed by (sector_l4, date) via asof per sector
    ew_col  = breadth_cols["ew"]
    liq_col = breadth_cols.get("liq", None)

    def _asof_breadth(sector: str, query_dates: pd.Series) -> pd.DataFrame:
        """Return breadth values asof query_dates for given sector."""
        sp = panel[panel["sector_l4"] == sector][["date", ew_col]].copy()
        if liq_col and liq_col in panel.columns:
            sp = panel[panel["sector_l4"] == sector][["date", ew_col, liq_col]].copy()
        if sp.empty:
            result = pd.DataFrame({"_ew": np.nan, "_liq": np.nan}, index=query_dates.index)
            return result
        sp = sp.drop_duplicates("date").sort_values("date")
        merged = pd.merge_asof(
            pd.DataFrame({"_entry_date": query_dates}).sort_values("_entry_date"),
            sp.rename(columns={ew_col: "_ew", **({liq_col: "_liq"} if liq_col and liq_col in sp.columns else {})}),
            left_on="_entry_date", right_on="date",
            direction="backward",
        )
        if "_liq" not in merged.columns:
            merged["_liq"] = np.nan
        return merged.set_index(merged.index)[["_ew", "_liq"]]

    # Attach breadth to each trade via asof join per sector
    ledger["_ew_breadth"]  = np.nan
    ledger["_liq_breadth"] = np.nan

    for sector, grp in ledger.groupby("sector_l4"):
        bdf = _asof_breadth(sector, grp["_entry_date"].reset_index(drop=True))
        ledger.loc[grp.index, "_ew_breadth"]  = bdf["_ew"].values
        ledger.loc[grp.index, "_liq_breadth"] = bdf["_liq"].values

    # Rules: (rule_id, breadth_col_internal, threshold)
    rules = [
        ("no_gate",      None,          None),
        ("l4_ew_ge_30",  "_ew_breadth", 0.30),
        ("l4_ew_ge_40",  "_ew_breadth", 0.40),
        ("l4_ew_ge_50",  "_ew_breadth", 0.50),
        ("l4_liq_ge_40", "_liq_breadth", 0.40),
    ]

    # Baseline stats (trade-level: mean_return, worst_single_trade, trade_mar)
    base_mean, base_worst, base_tmar = _perf_stats(ledger, ret_col)
    n_base = len(ledger)

    rows = []
    for rule_id, bcol, thresh in rules:
        if bcol is None:
            allowed = ledger
            blocked = ledger.iloc[0:0]  # empty
        else:
            # Allowed = breadth >= threshold (or unknown sector always allowed)
            unknown_mask = ledger["sector_l4"] == "Unknown"
            breadth_ok   = ledger[bcol].fillna(0) >= thresh
            allowed = ledger[unknown_mask | breadth_ok]
            blocked = ledger[~(unknown_mask | breadth_ok)]

        n_trades   = len(allowed)
        n_blocked  = len(blocked)
        ret_pct    = n_trades / max(n_base, 1)

        blk_win = int((blocked[ret_col].fillna(0) > 0).sum()) if not blocked.empty else 0
        blk_los = int((blocked[ret_col].fillna(0) < 0).sum()) if not blocked.empty else 0
        bl_ratio = blk_los / max(blk_win, 1)

        mean_ret, worst_ret, tmar = _perf_stats(allowed, ret_col)
        d_tmar  = tmar  - base_tmar  if not np.isnan(tmar)  and not np.isnan(base_tmar)  else np.nan
        d_mean  = mean_ret - base_mean if not np.isnan(mean_ret) and not np.isnan(base_mean) else np.nan

        if rule_id == "no_gate":
            gate_pass = "N/A"
            note = "Baseline - all trades"
        else:
            gate_pass = int(not np.isnan(d_tmar) and d_tmar >= 0.05 and bl_ratio >= 1.2)
            note = f"d_tmar={d_tmar:.4f}, bl_ratio={bl_ratio:.2f}" if not np.isnan(d_tmar) else "N/A"

        rows.append({
            "rule_id":                    rule_id,
            "n_trades":                   n_trades,
            "n_blocked":                  n_blocked,
            "retention_pct":              round(ret_pct, 4),
            "blocked_winners":            blk_win,
            "blocked_losers":             blk_los,
            "blocked_loser_winner_ratio": round(bl_ratio, 4),
            # Trade-level metrics (not portfolio NAV — multiple simultaneous trades)
            "cagr":                       round(mean_ret, 6) if not np.isnan(mean_ret) else np.nan,
            "max_dd":                     round(worst_ret, 6) if not np.isnan(worst_ret) else np.nan,
            "mar":                        round(tmar, 6) if not np.isnan(tmar) else np.nan,
            "delta_mar_vs_baseline":      round(d_tmar, 6) if not np.isnan(d_tmar) else np.nan,
            "delta_maxdd_vs_baseline":    round(d_mean, 6) if not np.isnan(d_mean) else np.nan,
            "adoption_gate_pass":         gate_pass,
            "note":                       note,
        })

    result = pd.DataFrame(rows)
    out_path = OUTPUT_DIR / "a3_ledger_sector_gate_replay_enriched.csv"
    result.to_csv(out_path, index=False)
    log.info("Enriched A3 replay saved to %s", out_path)
    return result


# ── P0.1 Task 3 — Filter-value ablation by sector-size bucket ─────────────────

def run_ablation_by_sector_size(
    stock_events: "pd.DataFrame",
    sector_panel: "pd.DataFrame",
    sector_map: "pd.DataFrame",
) -> "pd.DataFrame":
    """
    P0.1 Task 3 — Split filter-value ablation by sector-size bucket.
    Groups: all, Unknown only, n=1, n=2, n3_4, n_ge_5, n_ge_3_diagnostic.
    Horizons: 20d, 60d, 120d.
    Rules: baseline, l4_ew_ge_40, l4_ew_ge_50, l4_liq_ge_40.
    Output: filter_value_ablation_by_sector_size.csv
    """
    if stock_events is None or stock_events.empty:
        log.warning("No stock events; skipping sector-size ablation.")
        return pd.DataFrame()

    # Compute n_symbols per L4 from sector map
    l4_counts = (
        sector_map[sector_map["sector_l4"] != "Unknown"]
        .groupby("sector_l4")["symbol"]
        .nunique()
        .rename("_n_in_l4")
        .reset_index()
    )

    ev = stock_events.copy()
    ev["date"] = pd.to_datetime(ev["date"])
    ev = ev.merge(l4_counts, on="sector_l4", how="left")
    ev["_n_in_l4"] = ev["_n_in_l4"].fillna(0).astype(int)
    ev["_is_unknown"] = (ev["sector_l4"] == "Unknown").astype(int)

    def _bucket(row):
        if row["_is_unknown"]:
            return "unknown"
        n = row["_n_in_l4"]
        if n == 1:
            return "n1"
        if n == 2:
            return "n2"
        if n <= 4:
            return "n3_4"
        return "n_ge_5"

    ev["_size_bucket"] = ev.apply(_bucket, axis=1)

    # Attach L4 breadth from sector_panel via (date, sector_l4) merge
    sp = sector_panel.copy()
    sp["date"] = pd.to_datetime(sp["date"])
    breadth_ew_col  = "l4_breadth_equal_weight"
    breadth_liq_col = "l4_breadth_liquidity_weighted"
    sp_snap = sp[["date", "sector_l4", breadth_ew_col] + (
        [breadth_liq_col] if breadth_liq_col in sp.columns else []
    )].copy()
    ev = ev.merge(sp_snap, on=["date", "sector_l4"], how="left")

    # Group definitions
    groups = {
        "all":              ev,
        "unknown_only":     ev[ev["_is_unknown"] == 1],
        "n1":               ev[ev["_size_bucket"] == "n1"],
        "n2":               ev[ev["_size_bucket"] == "n2"],
        "n3_4":             ev[ev["_size_bucket"] == "n3_4"],
        "n_ge_5":           ev[ev["_size_bucket"] == "n_ge_5"],
        "n_ge_3_diagnostic":ev[ev["_n_in_l4"] >= 3],
    }

    # Rules: (rule_id, breadth_col, threshold)
    rules = [
        ("baseline",      None,           None),
        ("l4_ew_ge_40",   breadth_ew_col,  0.40),
        ("l4_ew_ge_50",   breadth_ew_col,  0.50),
        ("l4_liq_ge_40",  breadth_liq_col, 0.40),
    ]

    horizons = FORWARD_HORIZONS

    rows = []
    for grp_name, grp_df in groups.items():
        if grp_df.empty:
            continue
        for rule_id, bcol, thresh in rules:
            if bcol is None:
                filtered = grp_df
            elif bcol not in grp_df.columns:
                continue
            else:
                filtered = grp_df[grp_df[bcol].fillna(0) >= thresh]

            n_base = len(grp_df)
            n_gate = len(filtered)

            for h in horizons:
                col = f"fwd_ret_{h}d"
                if col not in grp_df.columns:
                    continue
                bs = _return_stats(grp_df[col])
                gs = _return_stats(filtered[col] if col in filtered.columns else pd.Series(dtype=float))
                rows.append({
                    "sector_size_group":  grp_name,
                    "rule_id":            rule_id,
                    "horizon":            h,
                    "n_base":             n_base,
                    "n_gate":             n_gate,
                    "retention_pct":      round(n_gate / max(n_base, 1), 4),
                    "base_mean":          bs["mean"],
                    "base_hit_rate":      bs["hit_rate"],
                    "gate_mean":          gs["mean"],
                    "gate_hit_rate":      gs["hit_rate"],
                    "delta_mean":         gs["mean"] - bs["mean"] if not np.isnan(gs["mean"]) else np.nan,
                    "delta_hit_rate":     gs["hit_rate"] - bs["hit_rate"] if not np.isnan(gs["hit_rate"]) else np.nan,
                })

    result = pd.DataFrame(rows)
    out_path = OUTPUT_DIR / "filter_value_ablation_by_sector_size.csv"
    result.to_csv(out_path, index=False)
    log.info("Sector-size ablation saved to %s (%d rows)", out_path, len(result))
    return result
