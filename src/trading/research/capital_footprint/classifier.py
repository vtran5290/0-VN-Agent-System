"""
Capital Footprint Phase Classifier
=====================================
Replaces the v1 "high CF score = bullish" composite with a 6-label
phase classifier that distinguishes market structure states.

Labels (priority order — first matching condition wins):
  EXTENSION_DISTRIBUTION_RISK   — extended, mean-reversion risk
  SUPPLY_ABSORPTION_SETUP       — dry-up pullback near high, potential setup
  BREAKOUT_CONFIRMED            — new 60d high + volume + trend aligned
  BREAKOUT_FOLLOW_THROUGH_PENDING — new 60d high but not yet volume-confirmed
  FAILED_BREAKOUT               — breakout attempt reversed
  NEUTRAL                       — no condition triggered

Phase 3 additions:
  - Event-level deduplication with cooldown windows
  - Refined EXTENSION sublabels (LEADERSHIP_STRONG, EXTENDED_BUT_HEALTHY, EXTENSION_DISTRIBUTION_RISK)
  - Refined FAILED_BREAKOUT sublabels (TRUE_FAILED_BREAKOUT, BREAKOUT_RETEST_SHAKEOUT, RECLAIM_AFTER_FAILURE)
  - Full trade-path metrics for SUPPLY_ABSORPTION_SETUP

Research-only. Does NOT change production A3/OMS/DNSE logic.
"""

from __future__ import annotations

from typing import Optional
import numpy as np
import pandas as pd
from scipy import stats

LABEL_ORDER = [
    "EXTENSION_DISTRIBUTION_RISK",
    "SUPPLY_ABSORPTION_SETUP",
    "BREAKOUT_CONFIRMED",
    "BREAKOUT_FOLLOW_THROUGH_PENDING",
    "FAILED_BREAKOUT",
    "NEUTRAL",
]

FORWARD_RETURN_COLS = ["fwd_ret_5d", "fwd_ret_20d", "fwd_ret_60d", "fwd_ret_120d"]


# ── Label Assignment ──────────────────────────────────────────────────────────

def assign_phase_labels(panel: pd.DataFrame) -> pd.DataFrame:
    """
    Assign one of 6 phase labels per (symbol, date).

    Priority: EXTENSION > SUPPLY_ABSORPTION > BREAKOUT_CONFIRMED >
              BREAKOUT_PENDING > FAILED_BREAKOUT > NEUTRAL

    Higher-priority labels overwrite lower-priority ones when both
    conditions are met simultaneously.
    """
    idx = panel.index

    def _get(col, default=0.0):
        return panel[col].fillna(default) if col in panel.columns else pd.Series(default, index=idx)

    dist_to_ema20 = _get("distance_to_ema20", 0.0)
    dist_cluster  = _get("distribution_cluster_flag", 0)
    rs_rank       = _get("rs_rank_market_20d", 0.5)
    dry_up        = _get("dry_up_pullback_flag", 0)
    near_high     = _get("near_high_60d", 0)
    cloud_bull    = _get("cloud_bull_20_100", 0)
    new_high      = _get("new_high_60d_flag", 0)
    bv_flag       = _get("breakout_volume_flag", 0)
    above_ema50   = _get("above_ema50", 0)
    pb_fail       = _get("post_breakout_failure_flag", 0)
    turnover_z    = _get("turnover_z_20d", 0.0)
    clv           = _get("close_location_value", 0.5)

    # Condition definitions
    extended = (
        (dist_to_ema20 > 0.12) |
        (dist_cluster == 1) |
        (rs_rank >= 0.85) |
        ((turnover_z > 2.0) & (clv < 0.35))
    )

    supply_absorption = (
        (dry_up == 1) &
        (near_high == 1) &
        ~extended
    )

    breakout_confirmed = (
        (new_high == 1) &
        (bv_flag == 1) &
        (cloud_bull == 1) &
        (above_ema50 == 1)
    )

    breakout_pending = (
        (new_high == 1) &
        (cloud_bull == 1) &
        ~breakout_confirmed &
        ~extended
    )

    failed_breakout = (pb_fail == 1) & ~extended

    # Assign in reverse priority (last applied wins)
    labels = pd.Series("NEUTRAL", index=idx, dtype=str)
    labels[failed_breakout]     = "FAILED_BREAKOUT"
    labels[breakout_pending]    = "BREAKOUT_FOLLOW_THROUGH_PENDING"
    labels[breakout_confirmed]  = "BREAKOUT_CONFIRMED"
    labels[supply_absorption]   = "SUPPLY_ABSORPTION_SETUP"
    labels[extended]            = "EXTENSION_DISTRIBUTION_RISK"

    panel = panel.copy()
    panel["phase_label"] = labels
    return panel


# ── Per-Label Statistics ──────────────────────────────────────────────────────

def run_classifier_analysis(panel: pd.DataFrame) -> pd.DataFrame:
    """
    For each phase label, compute:
      - count, base rate
      - mean/median forward return at 5d/20d/60d/120d
      - win rate at 5d/20d/60d/120d
      - TP1 hit rate (tp1_18pct_hit_120d)
      - mean max gain / max drawdown at 20d/60d
      - Spearman IC of dry_up_pullback_flag vs fwd_ret_20d within label
    """
    if "phase_label" not in panel.columns:
        return pd.DataFrame()

    fwd_cols = [c for c in FORWARD_RETURN_COLS if c in panel.columns]
    records = []

    total = len(panel)
    for label in LABEL_ORDER:
        df = panel[panel["phase_label"] == label]
        if df.empty:
            continue

        row: dict = {
            "phase_label": label,
            "n_rows": len(df),
            "base_rate_pct": round(len(df) / max(total, 1) * 100, 1),
        }

        for fwd in fwd_cols:
            clean = df[fwd].dropna()
            if clean.empty:
                continue
            d = fwd.replace("fwd_ret_", "")
            row[f"mean_{d}"] = round(clean.mean(), 4)
            row[f"median_{d}"] = round(clean.median(), 4)
            row[f"win_rate_{d}"] = round((clean > 0).mean(), 3)

        if "tp1_18pct_hit_120d" in df.columns:
            row["tp1_18pct_hit_rate"] = round(df["tp1_18pct_hit_120d"].dropna().mean(), 3)

        for suffix in ["20d", "60d"]:
            mg = f"fwd_max_gain_{suffix}"
            md = f"fwd_max_drawdown_{suffix}"
            if mg in df.columns:
                row[f"mean_max_gain_{suffix}"] = round(df[mg].dropna().mean(), 4)
            if md in df.columns:
                row[f"mean_max_dd_{suffix}"] = round(df[md].dropna().mean(), 4)

        records.append(row)

    return pd.DataFrame(records)


# ── Label-Level IC (Spearman) ─────────────────────────────────────────────────

def run_label_ic_analysis(panel: pd.DataFrame) -> pd.DataFrame:
    """
    IC of dry_up_pullback_flag and phase_label_binary vs forward returns
    within each phase label group.
    """
    if "phase_label" not in panel.columns:
        return pd.DataFrame()

    fwd_cols = [c for c in FORWARD_RETURN_COLS if c in panel.columns]
    test_signals = [c for c in [
        "dry_up_pullback_flag",
        "dry_up_near_high_with_trend_support",
        "distribution_cluster_flag",
        "post_breakout_failure_flag",
        "breakout_volume_flag",
        "pullback_depth_from_high",
    ] if c in panel.columns]

    records = []
    for label in LABEL_ORDER:
        df = panel[panel["phase_label"] == label]
        if len(df) < 50:
            continue
        for sig in test_signals:
            for fwd in fwd_cols:
                mask = df[sig].notna() & df[fwd].notna()
                if mask.sum() < 10:
                    continue
                r, _ = stats.spearmanr(df.loc[mask, sig], df.loc[mask, fwd])
                records.append({
                    "phase_label": label,
                    "signal": sig,
                    "forward_return": fwd,
                    "n": int(mask.sum()),
                    "ic": round(float(r), 4),
                })

    return pd.DataFrame(records)


# ── Classifier Event Study ────────────────────────────────────────────────────

def run_classifier_event_study(
    panel: pd.DataFrame,
    lookback: int = 20,
    lookahead: int = 60,
    max_events_per_label: int = 2000,
) -> pd.DataFrame:
    """
    Average price path from T-lookback to T+lookahead for each phase label.

    Returns a long DataFrame: [phase_label, offset, avg_return, n_events].
    """
    if "phase_label" not in panel.columns:
        return pd.DataFrame()

    all_paths = []
    rng = np.random.default_rng(42)

    for label in LABEL_ORDER:
        events = panel[panel["phase_label"] == label][["date", "symbol"]].copy()
        if events.empty:
            continue
        if len(events) > max_events_per_label:
            idx = rng.choice(len(events), max_events_per_label, replace=False)
            events = events.iloc[idx]

        results = []
        for sym, sym_data in panel[panel["symbol"].isin(events["symbol"].unique())].groupby("symbol"):
            sym_data = sym_data.sort_values("date").reset_index(drop=True)
            sym_events = events[events["symbol"] == sym]

            for _, ev in sym_events.iterrows():
                ev_idx_arr = sym_data[sym_data["date"] == ev["date"]].index
                if ev_idx_arr.empty:
                    continue
                i = ev_idx_arr[0]
                ev_price = sym_data.loc[i, "close"]
                if ev_price <= 0 or np.isnan(ev_price):
                    continue

                row = {}
                for offset in range(-lookback, lookahead + 1, 5):
                    j = i + offset
                    if 0 <= j < len(sym_data):
                        row[f"t{offset:+d}"] = sym_data.loc[j, "close"] / ev_price - 1
                results.append(row)

        if not results:
            continue

        res_df = pd.DataFrame(results)
        t_cols = [c for c in res_df.columns if c.startswith("t")]
        avg_path = res_df[t_cols].mean()

        for offset_str, avg_ret in avg_path.items():
            all_paths.append({
                "phase_label": label,
                "offset": offset_str,
                "avg_return": round(float(avg_ret), 5),
                "n_events": len(results),
            })

    return pd.DataFrame(all_paths)


# ── False Positive / False Negative Examples ─────────────────────────────────

def run_fp_fn_analysis(
    panel: pd.DataFrame,
    fwd_col: str = "fwd_ret_20d",
    n_examples: int = 50,
) -> pd.DataFrame:
    """
    For each label, find examples where the expected outcome did NOT happen:
      - SUPPLY_ABSORPTION_SETUP that failed to produce positive return
      - EXTENSION_DISTRIBUTION_RISK that went on to gain > 10%
      - BREAKOUT_CONFIRMED that reversed
      - FAILED_BREAKOUT that recovered
    """
    if "phase_label" not in panel.columns or fwd_col not in panel.columns:
        return pd.DataFrame()

    df = panel.dropna(subset=["phase_label", fwd_col]).copy()

    conditions = {
        "SUPPLY_ABSORPTION_SETUP": df[fwd_col] < -0.05,
        "EXTENSION_DISTRIBUTION_RISK": df[fwd_col] > 0.10,
        "BREAKOUT_CONFIRMED": df[fwd_col] < -0.05,
        "FAILED_BREAKOUT": df[fwd_col] > 0.10,
    }

    records = []
    for label, failure_mask in conditions.items():
        subset = df[(df["phase_label"] == label) & failure_mask]
        if subset.empty:
            continue
        sample = subset.head(n_examples)
        for _, row in sample.iterrows():
            records.append({
                "phase_label": label,
                "failure_type": "false_positive" if label in ("SUPPLY_ABSORPTION_SETUP", "BREAKOUT_CONFIRMED") else "false_negative",
                "date": row["date"],
                "symbol": row.get("symbol", ""),
                "sector": row.get("sector_primary", ""),
                fwd_col: round(row[fwd_col], 4),
                "dry_up_pullback_flag": int(row.get("dry_up_pullback_flag", 0)),
                "distribution_cluster_flag": int(row.get("distribution_cluster_flag", 0)),
                "distance_to_ema20": round(row.get("distance_to_ema20", 0), 4),
                "rs_rank_market_20d": round(row.get("rs_rank_market_20d", 0.5), 3),
                "cloud_bull_20_100": int(row.get("cloud_bull_20_100", 0)),
                "market_pct_above_ma50": round(row.get("market_pct_above_ma50", 50), 1),
            })

    return pd.DataFrame(records)


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3 — EVENT-LEVEL CLASSIFIER
# ═══════════════════════════════════════════════════════════════════════════════

# ── Event Detection (label entry events) ─────────────────────────────────────

def detect_label_entry_events(
    panel: pd.DataFrame,
    cooldown_days: int = 20,
) -> pd.DataFrame:
    """
    Detect label_entry_event: first bar where phase_label changes from prior bar,
    within cooldown_days per (symbol, label) pair.

    Returns a copy of panel with two new columns:
      label_entry_event   — 1 if this is a new entry event, 0 otherwise
      event_age           — days since last entry event for same (symbol, label), NaN if none

    Cooldown logic: after an entry event, the same (symbol, label) cannot fire again
    for `cooldown_days` trading bars. Events within cooldown window are suppressed.
    This removes the effect of persistent labels re-counting the same trade setup.
    """
    if "phase_label" not in panel.columns:
        raise ValueError("panel must have phase_label column")

    panel = panel.copy()
    panel = panel.sort_values(["symbol", "date"]).reset_index(drop=True)

    event_flags = np.zeros(len(panel), dtype=np.int8)
    event_age   = np.full(len(panel), np.nan)

    for sym, grp in panel.groupby("symbol", sort=False):
        grp = grp.sort_values("date")
        labels = grp["phase_label"].values
        idx    = grp.index.values
        n      = len(labels)

        last_event_pos: dict[str, int] = {}   # label -> last event row position

        for i, (label, row_idx) in enumerate(zip(labels, idx)):
            prev_label = labels[i - 1] if i > 0 else None
            last_pos   = last_event_pos.get(label, -cooldown_days - 1)
            in_cooldown = (i - last_pos) <= cooldown_days

            if label != prev_label and not in_cooldown:
                event_flags[row_idx] = 1
                last_event_pos[label] = i
                event_age[row_idx]    = 0.0
            elif i > 0 and not np.isnan(event_age[idx[i - 1]]):
                # Propagate age within same label run
                if labels[i] == labels[i - 1]:
                    event_age[row_idx] = event_age[idx[i - 1]] + 1

    panel["label_entry_event"] = event_flags
    panel["event_age"]         = event_age
    panel["event_cooldown_flag"] = (~np.isnan(event_age) & (event_age <= cooldown_days)).astype(np.int8)
    return panel


def run_event_level_stats(
    panel: pd.DataFrame,
    cooldown_days: int = 20,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Compute per-label stats at the event level (entry events only).

    Returns:
      event_label_stats       — same schema as classifier_label_stats but event-level
      event_trade_path        — detailed trade-path metrics per label
    """
    if "label_entry_event" not in panel.columns:
        panel = detect_label_entry_events(panel, cooldown_days=cooldown_days)

    events = panel[panel["label_entry_event"] == 1].copy()
    total_events = len(events)
    total_rows   = len(panel)

    print(f"  Event-level: {total_events:,} events from {total_rows:,} rows "
          f"({total_events/max(total_rows,1)*100:.1f}%)")

    fwd_cols = [c for c in FORWARD_RETURN_COLS if c in events.columns]
    records  = []

    for label in LABEL_ORDER:
        df = events[events["phase_label"] == label]
        if df.empty:
            continue

        row: dict = {
            "phase_label":       label,
            "n_events":          len(df),
            "n_rows_total":      int((panel["phase_label"] == label).sum()),
            "event_rate":        round(len(df) / max(total_events, 1) * 100, 1),
            "avg_duration_bars": round(
                (panel["phase_label"] == label).sum() / max(len(df), 1), 1
            ),
        }

        for fwd in fwd_cols:
            clean = df[fwd].dropna()
            if clean.empty:
                continue
            d = fwd.replace("fwd_ret_", "")
            row[f"mean_{d}"]    = round(clean.mean(),   4)
            row[f"median_{d}"]  = round(clean.median(), 4)
            row[f"win_rate_{d}"] = round((clean > 0).mean(), 3)

        if "tp1_18pct_hit_120d" in df.columns:
            row["tp1_18pct_hit_rate"] = round(df["tp1_18pct_hit_120d"].dropna().mean(), 3)

        records.append(row)

    label_stats = pd.DataFrame(records)

    # Trade-path metrics
    trade_path = _run_trade_path_analysis(events)

    return label_stats, trade_path


def _run_trade_path_analysis(events: pd.DataFrame) -> pd.DataFrame:
    """
    Trade-path metrics per label: path-dependent hit rates, MAE, MFE, drawdown before TP.
    """
    records = []
    fwd_cols = [c for c in FORWARD_RETURN_COLS if c in events.columns]

    for label in LABEL_ORDER:
        df = events[events["phase_label"] == label]
        if len(df) < 10:
            continue

        row: dict = {"phase_label": label, "n_events": len(df)}

        for fwd in fwd_cols:
            clean = df[fwd].dropna()
            if clean.empty:
                continue
            d = fwd.replace("fwd_ret_", "")
            row[f"mean_{d}"]    = round(clean.mean(),   4)
            row[f"median_{d}"]  = round(clean.median(), 4)
            row[f"win_rate_{d}"] = round((clean > 0).mean(), 3)
            row[f"pct_loss_gt7pct_{d}"] = round((clean < -0.07).mean(), 3)
            row[f"pct_gain_gt10pct_{d}"] = round((clean > 0.10).mean(), 3)

        # Path-dependent: hit TP before stop
        for gain_th, stop_th, col_suffix in [
            (0.10, -0.07, "tp10_stop7_60d"),
            (0.18, -0.10, "tp18_stop10_60d"),
        ]:
            gain_col = "fwd_max_gain_60d"
            dd_col   = "fwd_max_drawdown_60d"
            ret_col  = "fwd_ret_60d"
            if all(c in df.columns for c in [gain_col, dd_col, ret_col]):
                hit_tp   = (df[gain_col] >= gain_th) & (df[dd_col] > stop_th)
                hit_stop = (df[dd_col] <= stop_th) & (df[gain_col] < gain_th)
                row[f"hit_{col_suffix}"] = round(hit_tp.mean(), 3)
                row[f"stopped_{col_suffix}"] = round(hit_stop.mean(), 3)

        # MAE / MFE
        for sfx in ["20d", "60d"]:
            if f"fwd_max_gain_{sfx}" in df.columns:
                row[f"mfe_{sfx}"] = round(df[f"fwd_max_gain_{sfx}"].dropna().mean(), 4)
            if f"fwd_max_drawdown_{sfx}" in df.columns:
                row[f"mae_{sfx}"] = round(df[f"fwd_max_drawdown_{sfx}"].dropna().mean(), 4)

        if "tp1_18pct_hit_120d" in df.columns:
            row["tp1_hit_rate"] = round(df["tp1_18pct_hit_120d"].dropna().mean(), 3)

        records.append(row)

    return pd.DataFrame(records)


# ── Refined EXTENSION Sublabels ───────────────────────────────────────────────

EXTENSION_SUBLABELS = [
    "LEADERSHIP_STRONG",
    "EXTENDED_BUT_HEALTHY",
    "EXTENSION_DISTRIBUTION_RISK",
]


def refine_extension_labels(panel: pd.DataFrame) -> pd.DataFrame:
    """
    Split EXTENSION_DISTRIBUTION_RISK into 3 sublabels.
    Only operates on rows already labeled EXTENSION_DISTRIBUTION_RISK.

    LEADERSHIP_STRONG:
      - High RS (rs_rank >= 0.80) AND clean close (clv >= 0.5) AND no distribution cluster
      - These are stocks making new highs on leadership, not yet overextended

    EXTENDED_BUT_HEALTHY:
      - Above EMA20 (distance_to_ema20 > 0) AND clv >= 0.4 AND no distribution cluster
      - Extended but not showing distribution signs; healthy trend continuation

    EXTENSION_DISTRIBUTION_RISK:
      - Everything else in EXTENSION bucket: overextended + distribution signals
      - dist_to_ema20 > 0.12, OR distribution_cluster, OR turnover spike with weak close

    Priority: LEADERSHIP_STRONG > EXTENDED_BUT_HEALTHY > EXTENSION_DISTRIBUTION_RISK
    """
    panel = panel.copy()
    if "phase_label" not in panel.columns:
        return panel

    mask_ext = panel["phase_label"] == "EXTENSION_DISTRIBUTION_RISK"
    if not mask_ext.any():
        panel["extension_sublabel"] = pd.NA
        return panel

    ext_rows = panel[mask_ext].copy()
    idx = ext_rows.index

    def _g(col, default=0.0):
        return ext_rows[col].fillna(default) if col in ext_rows.columns else pd.Series(default, index=idx)

    rs_rank    = _g("rs_rank_market_20d", 0.5)
    clv        = _g("close_location_value", 0.5)
    dist_ema20 = _g("distance_to_ema20", 0.0)
    dist_clust = _g("distribution_cluster_flag", 0)
    turnover_z = _g("turnover_z_20d", 0.0)

    leadership_strong = (
        (rs_rank >= 0.80) &
        (clv >= 0.5) &
        (dist_clust == 0) &
        (turnover_z < 2.0)
    )

    extended_healthy = (
        (dist_ema20 > 0) &
        (clv >= 0.40) &
        (dist_clust == 0) &
        (dist_ema20 <= 0.12) &
        ~leadership_strong
    )

    sublabels = pd.Series("EXTENSION_DISTRIBUTION_RISK", index=idx, dtype=str)
    sublabels[extended_healthy]   = "EXTENDED_BUT_HEALTHY"
    sublabels[leadership_strong]  = "LEADERSHIP_STRONG"

    panel.loc[mask_ext, "extension_sublabel"] = sublabels.values
    panel.loc[~mask_ext, "extension_sublabel"] = pd.NA
    return panel


def run_extension_sublabel_stats(panel: pd.DataFrame) -> pd.DataFrame:
    """Per-sublabel forward return stats for EXTENSION rows."""
    if "extension_sublabel" not in panel.columns:
        panel = refine_extension_labels(panel)

    ext = panel[panel["phase_label"] == "EXTENSION_DISTRIBUTION_RISK"].copy()
    if ext.empty:
        return pd.DataFrame()

    fwd_cols = [c for c in FORWARD_RETURN_COLS if c in ext.columns]
    records  = []

    for sublabel in EXTENSION_SUBLABELS:
        df = ext[ext["extension_sublabel"] == sublabel]
        if len(df) < 10:
            continue
        row: dict = {
            "extension_sublabel": sublabel,
            "n_rows": len(df),
            "pct_of_extension": round(len(df) / max(len(ext), 1) * 100, 1),
        }
        for fwd in fwd_cols:
            clean = df[fwd].dropna()
            if clean.empty:
                continue
            d = fwd.replace("fwd_ret_", "")
            row[f"mean_{d}"]    = round(clean.mean(),   4)
            row[f"median_{d}"]  = round(clean.median(), 4)
            row[f"win_rate_{d}"] = round((clean > 0).mean(), 3)
        records.append(row)

    return pd.DataFrame(records)


# ── Refined FAILED_BREAKOUT Sublabels ─────────────────────────────────────────

FAILED_BREAKOUT_SUBLABELS = [
    "TRUE_FAILED_BREAKOUT",
    "BREAKOUT_RETEST_SHAKEOUT",
    "RECLAIM_AFTER_FAILURE",
]


def refine_failed_breakout_labels(panel: pd.DataFrame) -> pd.DataFrame:
    """
    Split FAILED_BREAKOUT into 3 sublabels.
    Only operates on rows already labeled FAILED_BREAKOUT.

    TRUE_FAILED_BREAKOUT:
      - Close breaks below EMA50 (above_ema50 == 0) AND post_breakout_failure_flag == 1
      - Structural failure: breakout reversed AND price below key trend support

    BREAKOUT_RETEST_SHAKEOUT:
      - above_ema50 == 1 AND above_ema20 (distance_to_ema20 > -0.03) AND post_breakout_failure_flag == 1
      - Pullback but holding both EMAs — may be a shakeout before continuation

    RECLAIM_AFTER_FAILURE:
      - post_breakout_failure_flag was set but distance_to_ema20 <= 0.05 AND near_high_60d == 1
      - Price has reclaimed the prior breakout area within recent bars
      - Indicates recovery rather than true failure

    Priority: RECLAIM_AFTER_FAILURE > BREAKOUT_RETEST_SHAKEOUT > TRUE_FAILED_BREAKOUT
    """
    panel = panel.copy()
    if "phase_label" not in panel.columns:
        return panel

    mask_fb = panel["phase_label"] == "FAILED_BREAKOUT"
    if not mask_fb.any():
        panel["failed_breakout_sublabel"] = pd.NA
        return panel

    fb_rows = panel[mask_fb].copy()
    idx = fb_rows.index

    def _g(col, default=0.0):
        return fb_rows[col].fillna(default) if col in fb_rows.columns else pd.Series(default, index=idx)

    above_ema50  = _g("above_ema50", 1)
    dist_ema20   = _g("distance_to_ema20", 0.0)
    near_high    = _g("near_high_60d", 0)
    pb_fail      = _g("post_breakout_failure_flag", 1)

    true_failed = (above_ema50 == 0) & (pb_fail == 1)

    shakeout = (
        (above_ema50 == 1) &
        (dist_ema20 > -0.03) &
        (pb_fail == 1) &
        ~true_failed
    )

    reclaim = (
        (dist_ema20 <= 0.05) &
        (near_high == 1) &
        ~true_failed
    )

    sublabels = pd.Series("TRUE_FAILED_BREAKOUT", index=idx, dtype=str)
    sublabels[shakeout] = "BREAKOUT_RETEST_SHAKEOUT"
    sublabels[reclaim]  = "RECLAIM_AFTER_FAILURE"

    panel.loc[mask_fb, "failed_breakout_sublabel"] = sublabels.values
    panel.loc[~mask_fb, "failed_breakout_sublabel"] = pd.NA
    return panel


def run_failed_breakout_sublabel_stats(panel: pd.DataFrame) -> pd.DataFrame:
    """Per-sublabel forward return stats for FAILED_BREAKOUT rows."""
    if "failed_breakout_sublabel" not in panel.columns:
        panel = refine_failed_breakout_labels(panel)

    fb = panel[panel["phase_label"] == "FAILED_BREAKOUT"].copy()
    if fb.empty:
        return pd.DataFrame()

    fwd_cols = [c for c in FORWARD_RETURN_COLS if c in fb.columns]
    records  = []

    for sublabel in FAILED_BREAKOUT_SUBLABELS:
        df = fb[fb["failed_breakout_sublabel"] == sublabel]
        if len(df) < 10:
            continue
        row: dict = {
            "failed_breakout_sublabel": sublabel,
            "n_rows": len(df),
            "pct_of_failed_breakout": round(len(df) / max(len(fb), 1) * 100, 1),
        }
        for fwd in fwd_cols:
            clean = df[fwd].dropna()
            if clean.empty:
                continue
            d = fwd.replace("fwd_ret_", "")
            row[f"mean_{d}"]    = round(clean.mean(),   4)
            row[f"median_{d}"]  = round(clean.median(), 4)
            row[f"win_rate_{d}"] = round((clean > 0).mean(), 3)
        if "tp1_18pct_hit_120d" in df.columns:
            row["tp1_hit_rate"] = round(df["tp1_18pct_hit_120d"].dropna().mean(), 3)
        records.append(row)

    return pd.DataFrame(records)


# ── SUPPLY_ABSORPTION_SETUP Trade-Path ────────────────────────────────────────

def run_supply_absorption_trade_path(
    panel: pd.DataFrame,
    by_regime: bool = True,
    by_sector: bool = True,
    by_liquidity: bool = True,
) -> dict[str, pd.DataFrame]:
    """
    Full risk-adjusted trade-path analysis for SUPPLY_ABSORPTION_SETUP events.

    Returns a dict of DataFrames:
      'overall'      — aggregate stats (all events)
      'by_regime'    — stats broken down by regime bucket
      'by_sector'    — stats broken down by sector_primary
      'by_liquidity' — stats broken down by adv50 quintile
    """
    if "phase_label" not in panel.columns:
        return {}

    sa = panel[panel["phase_label"] == "SUPPLY_ABSORPTION_SETUP"].copy()
    if sa.empty:
        return {}

    # If event-level detection has been run, use events only
    if "label_entry_event" in sa.columns:
        sa = sa[sa["label_entry_event"] == 1]
        print(f"  SUPPLY_ABSORPTION_SETUP events (entry only): {len(sa)}")
    else:
        print(f"  SUPPLY_ABSORPTION_SETUP rows (row-level): {len(sa)}")

    results: dict[str, pd.DataFrame] = {}

    def _stats(df: pd.DataFrame, group_col: Optional[str] = None, group_val: Optional[str] = None) -> dict:
        row: dict = {}
        if group_col:
            row[group_col] = group_val
        row["n"] = len(df)

        fwd_cols = [c for c in FORWARD_RETURN_COLS if c in df.columns]
        for fwd in fwd_cols:
            clean = df[fwd].dropna()
            if clean.empty:
                continue
            d = fwd.replace("fwd_ret_", "")
            row[f"mean_{d}"]      = round(clean.mean(),   4)
            row[f"median_{d}"]    = round(clean.median(), 4)
            row[f"win_rate_{d}"]  = round((clean > 0).mean(), 3)
            row[f"pct_gain_gt10pct_{d}"] = round((clean > 0.10).mean(), 3)
            row[f"pct_loss_gt7pct_{d}"]  = round((clean < -0.07).mean(), 3)

        # Path-dependent: hit TP before stop (using max_gain vs max_drawdown)
        for gain_th, stop_th, suffix in [
            (0.10, -0.07, "60d_tp10_stop7"),
            (0.18, -0.10, "60d_tp18_stop10"),
        ]:
            gc = "fwd_max_gain_60d"
            dc = "fwd_max_drawdown_60d"
            if gc in df.columns and dc in df.columns:
                hit_tp   = (df[gc] >= gain_th)
                hit_stop = (df[dc] <= stop_th) & (df[gc] < gain_th)
                row[f"hit_{suffix}"] = round(hit_tp.mean(), 3)
                row[f"stopped_{suffix}"] = round(hit_stop.mean(), 3)

        # MAE / MFE
        for sfx in ["20d", "60d"]:
            if f"fwd_max_gain_{sfx}" in df.columns:
                row[f"mfe_{sfx}"] = round(df[f"fwd_max_gain_{sfx}"].dropna().mean(), 4)
            if f"fwd_max_drawdown_{sfx}" in df.columns:
                row[f"mae_{sfx}"] = round(df[f"fwd_max_drawdown_{sfx}"].dropna().mean(), 4)

        if "tp1_18pct_hit_120d" in df.columns:
            row["tp1_hit_rate"] = round(df["tp1_18pct_hit_120d"].dropna().mean(), 3)

        return row

    # Overall
    results["overall"] = pd.DataFrame([_stats(sa)])

    # By regime (check both possible column names)
    regime_col = next(
        (c for c in ["regime_bucket", "breadth_regime_bucket", "market_regime"] if c in sa.columns),
        None,
    )
    if by_regime and regime_col:
        regime_records = []
        for regime in sa[regime_col].dropna().unique():
            sub = sa[sa[regime_col] == regime]
            if len(sub) >= 5:
                regime_records.append(_stats(sub, "regime_bucket", str(regime)))
        if regime_records:
            results["by_regime"] = pd.DataFrame(regime_records)

    # By sector
    if by_sector and "sector_primary" in sa.columns:
        sector_records = []
        for sector in sa["sector_primary"].dropna().unique():
            sub = sa[sa["sector_primary"] == sector]
            if len(sub) >= 5:
                sector_records.append(_stats(sub, "sector_primary", sector))
        if sector_records:
            results["by_sector"] = pd.DataFrame(sector_records).sort_values("n", ascending=False)

    # By liquidity quintile
    if by_liquidity and "adv50_vnd" in sa.columns:
        sa_liq = sa.copy()
        sa_liq["adv50_quintile"] = pd.qcut(
            sa_liq["adv50_vnd"].fillna(0), q=5,
            labels=["Q1_least_liquid", "Q2", "Q3", "Q4", "Q5_most_liquid"],
            duplicates="drop",
        )
        liq_records = []
        for q in sa_liq["adv50_quintile"].cat.categories:
            sub = sa_liq[sa_liq["adv50_quintile"] == q]
            if len(sub) >= 5:
                liq_records.append(_stats(sub, "adv50_quintile", str(q)))
        if liq_records:
            results["by_liquidity"] = pd.DataFrame(liq_records)

    return results
