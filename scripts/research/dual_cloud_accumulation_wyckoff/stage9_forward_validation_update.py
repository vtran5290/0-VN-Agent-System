"""Stage 9 — Forward Validation Updater.

Loads the Stage 8 forward validation ledger template and fills forward outcome
columns using available OHLCV panel data. Produces summary analytics by flag,
year, and liquidity bucket.

This is OBSERVATION / RESEARCH only.
- Not a signal generator.
- Not OMS input.
- Does not write to any live/decision path.

Outputs (all under OUT_DIR):
  stage9_forward_validation_updated.csv
  stage9_forward_validation_summary.csv
  stage9_forward_validation_by_flag.csv
  stage9_forward_validation_by_year.csv
  stage9_forward_validation_by_liquidity.csv
  STAGE9_FORWARD_VALIDATION_FINDINGS.md
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from scripts.research.dual_cloud_accumulation_wyckoff.panel_utils import (
    OUT_DIR,
    load_panel,
)

log = logging.getLogger(__name__)

# ── Safety constants ───────────────────────────────────────────────────────────
_STAGE9_WRITE_DIR: Path = OUT_DIR

_OMS_SAFE_PATHS: frozenset[str] = frozenset({
    str(REPO / "data" / "decision" / "daily_scan.json"),
    str(REPO / "data" / "decision" / "daily_scan.md"),
    str(REPO / "data" / "decision" / "allocation_plan.json"),
    str(REPO / "data" / "state" / "regime_state.json"),
    str(REPO / "data" / "raw" / "current_positions_derived.json"),
    str(REPO / "data" / "raw" / "current_positions_digest.md"),
})

# ── Thresholds ─────────────────────────────────────────────────────────────────
TP1_PCT         = 0.18     # +18% for TP1 flag
HORIZONS        = (5, 10, 20, 40, 63)
MAE_MFE_WINDOW  = 63       # bars after entry for MAE/MFE

# Classification thresholds (for summary findings)
_WIN_RATE_THRESHOLD = 0.45   # ≥45% win rate = positive outcome
_Q5_DELTA_THRESHOLD = 0.05   # ≥5pp Q5 delta vs baseline


# ── Core row-level outcome computation ────────────────────────────────────────

def _compute_row_outcomes(
    obs_date: pd.Timestamp,
    entry_price: float,
    sym_df: pd.DataFrame,
    horizons: Tuple[int, ...] = HORIZONS,
    tp1_pct: float = TP1_PCT,
    mae_mfe_window: int = MAE_MFE_WINDOW,
) -> dict:
    """
    Compute forward return outcomes for a single ledger row.

    Lookup:
    - Find idx = last bar whose date <= obs_date in sym_df (the signal bar).
    - Entry price supplied externally (close_kvnd from ledger = open of t+1 bar).
    - Forward returns: close[idx+N] / entry_price - 1, close-to-close convention.
    - TP1: max(high[idx+1 : idx+mae_mfe_window+1]) >= entry * (1 + tp1_pct)
    - MAE: min(low[idx+1 : idx+mae_mfe_window+1]) / entry - 1
    - MFE: max(high[idx+1 : idx+mae_mfe_window+1]) / entry - 1
    - Maturity: True if idx + N < len(sym_df)

    Returns dict with all forward metric keys.
    """
    result: dict = {}

    for h in horizons:
        result[f"fwd_{h}d_return"]    = np.nan
        result[f"fwd_{h}d_matured"]   = False

    result["tp1_hit_63d"]               = np.nan
    result["max_adverse_excursion_63d"] = np.nan
    result["max_favorable_excursion_63d"] = np.nan
    result["mae_mfe_matured"]           = False

    if sym_df is None or len(sym_df) == 0:
        return result
    if entry_price <= 0 or np.isnan(entry_price):
        return result

    dates_np = pd.to_datetime(sym_df["date"]).values
    obs_ts   = np.datetime64(obs_date, "ns")

    # Last bar with date <= obs_date
    idx = int(np.searchsorted(dates_np, obs_ts, side="right")) - 1
    if idx < 0:
        return result

    n      = len(sym_df)
    close  = sym_df["close"].values
    high   = sym_df["high"].values
    low    = sym_df["low"].values

    # Forward returns: close-to-close
    for h in horizons:
        exit_idx = idx + h
        if exit_idx < n:
            fwd = close[exit_idx] / entry_price - 1.0
            result[f"fwd_{h}d_return"]  = float(fwd)
            result[f"fwd_{h}d_matured"] = True

    # MAE / MFE / TP1 over [idx+1, idx+mae_mfe_window] (inclusive slice)
    window_end = idx + mae_mfe_window  # inclusive bar index
    if window_end < n:
        window_high = high[idx + 1 : window_end + 1]
        window_low  = low[idx + 1  : window_end + 1]
        if len(window_high) > 0:
            tp1_threshold = entry_price * (1.0 + tp1_pct)
            result["tp1_hit_63d"]               = bool(window_high.max() >= tp1_threshold)
            result["max_adverse_excursion_63d"] = float(window_low.min() / entry_price - 1.0)
            result["max_favorable_excursion_63d"] = float(window_high.max() / entry_price - 1.0)
            result["mae_mfe_matured"]           = True

    return result


# ── Summary helpers ────────────────────────────────────────────────────────────

def _compute_summary(df: pd.DataFrame, group_col: Optional[str] = None) -> pd.DataFrame:
    """
    Compute win-rate / MAE / MFE / TP1 summary for a horizon-level view.
    If group_col is None, returns overall summary per horizon.
    """
    rows = []
    for h in HORIZONS:
        ret_col     = f"fwd_{h}d_return"
        matured_col = f"fwd_{h}d_matured"
        if ret_col not in df.columns:
            continue

        sub = df[df.get(matured_col, pd.Series(True, index=df.index))].copy()
        valid = sub[ret_col].dropna()
        if len(valid) == 0:
            continue

        base_row = {
            "horizon": h,
            "n_matured": len(valid),
            "win_rate_15pct": float((valid >= 0.15).mean()),
            "loss_rate_8pct": float((valid <= -0.08).mean()),
            "avg_net_return": float(valid.mean()),
            "med_net_return": float(valid.median()),
            "pct_positive":   float((valid > 0).mean()),
        }
        if group_col and group_col in df.columns:
            base_row[group_col] = sub[group_col].iloc[0] if len(sub) else None
        rows.append(base_row)

    return pd.DataFrame(rows)


def _summary_by_group(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """Summary at h=63 broken down by a categorical group column."""
    h          = 63
    ret_col    = f"fwd_{h}d_return"
    mat_col    = f"fwd_{h}d_matured"

    if ret_col not in df.columns or group_col not in df.columns:
        return pd.DataFrame()

    mask = df.get(mat_col, pd.Series(True, index=df.index))
    sub  = df[mask].copy()

    out_rows = []
    for grp, grp_df in sub.groupby(group_col, dropna=False):
        valid = grp_df[ret_col].dropna()
        if len(valid) == 0:
            continue
        tp1_col = "tp1_hit_63d"
        tp1_rate = float(grp_df[tp1_col].dropna().mean()) if tp1_col in grp_df.columns else np.nan
        mae_col  = "max_adverse_excursion_63d"
        mfe_col  = "max_favorable_excursion_63d"
        out_rows.append({
            group_col:      grp,
            "n_matured":    len(valid),
            "win_rate_15pct": float((valid >= 0.15).mean()),
            "loss_rate_8pct": float((valid <= -0.08).mean()),
            "avg_net_return": float(valid.mean()),
            "med_net_return": float(valid.median()),
            "pct_positive":   float((valid > 0).mean()),
            "tp1_rate_63d":   tp1_rate,
            "avg_mae_63d":    float(grp_df[mae_col].dropna().mean()) if mae_col in grp_df.columns else np.nan,
            "avg_mfe_63d":    float(grp_df[mfe_col].dropna().mean()) if mfe_col in grp_df.columns else np.nan,
        })
    return pd.DataFrame(out_rows)


# ── Findings narrative ─────────────────────────────────────────────────────────

def _generate_findings_md(
    summary_df: pd.DataFrame,
    by_flag_df: pd.DataFrame,
    by_year_df: pd.DataFrame,
    by_liq_df: pd.DataFrame,
    n_total: int,
    n_matured_63: int,
    cutoff_date: str,
) -> str:
    lines = [
        "# Stage 9 — Forward Validation Findings",
        "",
        f"**Ledger rows:** {n_total}  |  **63d matured:** {n_matured_63}  |  **Data cutoff:** {cutoff_date}",
        "",
        "## Overall Summary (per horizon)",
        "",
    ]
    if not summary_df.empty:
        lines.append(summary_df.to_markdown(index=False))
    else:
        lines.append("_No matured rows yet._")
    lines.append("")

    lines += [
        "## By Watchlist Flag (h=63)",
        "",
    ]
    if not by_flag_df.empty:
        lines.append(by_flag_df.to_markdown(index=False))
    else:
        lines.append("_No flag data._")
    lines.append("")

    lines += [
        "## By Year (h=63)",
        "",
    ]
    if not by_year_df.empty:
        lines.append(by_year_df.to_markdown(index=False))
    else:
        lines.append("_No year data._")
    lines.append("")

    lines += [
        "## By Liquidity Bucket (h=63)",
        "",
    ]
    if not by_liq_df.empty:
        lines.append(by_liq_df.to_markdown(index=False))
    else:
        lines.append("_No liquidity data._")
    lines.append("")

    lines += [
        "## Interpretation Notes",
        "",
        "- Forward returns are close-to-close (signal bar close → close N bars later).",
        "- Entry price (`close_kvnd`) = open of t+1 bar from Stage 8 ledger.",
        "- TP1 = max(high) over [t+1, t+63] ≥ entry × 1.18.",
        "- MAE = min(low) / entry − 1 over same window.",
        "- MFE = max(high) / entry − 1 over same window.",
        "- Rows with incomplete future windows have matured=False and NaN outcomes.",
        "- **This file is RESEARCH ONLY. Not OMS input.**",
        "",
    ]
    return "\n".join(lines)


# ── Main entry point ───────────────────────────────────────────────────────────

def run(workers: int = 4) -> None:
    _STAGE9_WRITE_DIR.mkdir(parents=True, exist_ok=True)

    ledger_path = _STAGE9_WRITE_DIR / "stage8_forward_validation_ledger_template.csv"
    if not ledger_path.exists():
        log.error("Stage 8 ledger template not found at %s — run Stage 8 first.", ledger_path)
        return

    ledger = pd.read_csv(ledger_path)
    ledger["observation_date"] = pd.to_datetime(ledger["observation_date"])
    log.info("Loaded ledger: %d rows", len(ledger))

    # Load full panel (include all symbols — ex_vin=False for maximum coverage)
    panels: Dict[str, pd.DataFrame] = load_panel(ex_vin=False)
    # Pre-sort dates (load_panel should already sort, but ensure)
    for sym in panels:
        panels[sym] = panels[sym].sort_values("date").reset_index(drop=True)

    log.info("Panel loaded: %d symbols", len(panels))

    # ── Fill outcomes row by row ───────────────────────────────────────────────
    outcome_rows = []

    for _, row in ledger.iterrows():
        sym         = str(row["symbol"])
        obs_date    = row["observation_date"]
        entry_price = float(row.get("close_kvnd", np.nan))

        sym_df = panels.get(sym)
        outcomes = _compute_row_outcomes(
            obs_date=obs_date,
            entry_price=entry_price,
            sym_df=sym_df,
        )
        outcome_rows.append(outcomes)

    outcomes_df = pd.DataFrame(outcome_rows, index=ledger.index)

    # ── Merge outcomes back into ledger ───────────────────────────────────────
    # Drop existing blank forward columns from template (they're all NaN)
    fwd_cols_template = [
        "fwd_5d_return", "fwd_10d_return", "fwd_20d_return",
        "fwd_40d_return", "fwd_63d_return",
        "tp1_hit_63d", "max_adverse_excursion_63d", "max_favorable_excursion_63d",
    ]
    existing_drop = [c for c in fwd_cols_template if c in ledger.columns]
    updated = ledger.drop(columns=existing_drop).copy()
    updated = pd.concat([updated, outcomes_df], axis=1)

    # Add year column for grouping
    updated["year"] = updated["observation_date"].dt.year

    # ── Save updated ledger ────────────────────────────────────────────────────
    out_updated = _STAGE9_WRITE_DIR / "stage9_forward_validation_updated.csv"
    updated.to_csv(out_updated, index=False)
    log.info("Saved updated ledger: %s (%d rows)", out_updated.name, len(updated))

    # ── Summary analytics ──────────────────────────────────────────────────────
    summary_df = _compute_summary(updated)
    out_summary = _STAGE9_WRITE_DIR / "stage9_forward_validation_summary.csv"
    summary_df.to_csv(out_summary, index=False)
    log.info("Saved summary: %s", out_summary.name)

    # By watchlist flag (breakout_value_expansion_watchlist_flag)
    flag_col = "breakout_value_expansion_watchlist_flag"
    if flag_col not in updated.columns and "breakout_value_expansion_q" in updated.columns:
        updated[flag_col] = updated["breakout_value_expansion_q"] >= 4
    by_flag_df = _summary_by_group(updated, flag_col) if flag_col in updated.columns else pd.DataFrame()
    out_flag = _STAGE9_WRITE_DIR / "stage9_forward_validation_by_flag.csv"
    by_flag_df.to_csv(out_flag, index=False)
    log.info("Saved by-flag: %s", out_flag.name)

    # By year
    by_year_df = _summary_by_group(updated, "year")
    out_year = _STAGE9_WRITE_DIR / "stage9_forward_validation_by_year.csv"
    by_year_df.to_csv(out_year, index=False)
    log.info("Saved by-year: %s", out_year.name)

    # By liquidity bucket
    liq_col = "liquidity_bucket"
    by_liq_df = _summary_by_group(updated, liq_col) if liq_col in updated.columns else pd.DataFrame()
    out_liq = _STAGE9_WRITE_DIR / "stage9_forward_validation_by_liquidity.csv"
    by_liq_df.to_csv(out_liq, index=False)
    log.info("Saved by-liquidity: %s", out_liq.name)

    # ── Findings markdown ──────────────────────────────────────────────────────
    mat_col_63 = "fwd_63d_matured"
    n_matured_63 = int(updated[mat_col_63].sum()) if mat_col_63 in updated.columns else 0
    cutoff_date  = str(updated["observation_date"].max().date())

    findings_md = _generate_findings_md(
        summary_df    = summary_df,
        by_flag_df    = by_flag_df,
        by_year_df    = by_year_df,
        by_liq_df     = by_liq_df,
        n_total       = len(updated),
        n_matured_63  = n_matured_63,
        cutoff_date   = cutoff_date,
    )
    out_md = _STAGE9_WRITE_DIR / "STAGE9_FORWARD_VALIDATION_FINDINGS.md"
    out_md.write_text(findings_md, encoding="utf-8")
    log.info("Saved findings: %s", out_md.name)

    log.info(
        "Stage 9 complete. %d rows total, %d with 63d matured outcomes.",
        len(updated), n_matured_63,
    )


if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
