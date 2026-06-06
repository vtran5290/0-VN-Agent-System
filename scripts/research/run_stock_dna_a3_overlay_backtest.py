"""
Stock DNA A3-like T2 Proxy Backtest — CLI runner
Tests whether DNA profiles improve A3-like T2 proxy add quality (Variant 1) and
whether danger-line annotations precede drawdown (Variant 4).

IMPORTANT LABEL: This script uses a SIMPLIFIED A3-LIKE T2 PROXY, not the full
production A3 DP-first engine. Results must NOT be interpreted as proving Stock DNA
improves actual A3 performance. Use --a3-trade-ledger with an actual A3 signal CSV
to compute true overlay results.

Simplified proxy rules (not production A3):
  - Stock in uptrend: close > EMA20 and close > EMA100
  - Pullback: >= pullback_pct from recent 20D high within 30 bars
  - Market regime: breadth >= 40% (T2 not blocked)

RESEARCH ONLY — does not modify final_action, OMS, or DNSE.

Usage:
  python scripts/research/run_stock_dna_a3_overlay_backtest.py \
    --start 2016-01-01 \
    --end 2026-05-31 \
    --profile-dir data/research/stock_dna \
    --output-dir data/research/stock_dna \
    [--a3-trade-ledger path/to/a3_signals.csv]
"""
import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.trading.research.stock_dna.features import build_dna_panel
from src.trading.research.stock_dna.schema import DNA_DIR, RESEARCH_ONLY_LABEL, assert_output_path_safe
from src.trading.research.stock_dna.reporting import save_overlay_metrics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("stock_dna.overlay_backtest")

A3_PROXY_LABEL = "A3-like T2 proxy (NOT production A3)"   # P1 label requirement
A3_T2_PULLBACK_PCT: float = 0.04    # >= 4% pullback from recent high
A3_T2_WINDOW_BARS: int  = 30
A3_MIN_BREADTH:    float = 40.0     # breadth >= 40% for T2


# ── Simplified A3 T2 event detector ──────────────────────────────────────────

def detect_a3_t2_candidates(panel: pd.DataFrame) -> pd.DataFrame:
    """
    Detect simplified A3-like T2 candidate events per (symbol, date):
      1. close > ema20 and close > sma100 (uptrend proxy)
      2. Pulled back >= A3_T2_PULLBACK_PCT from 20D high within A3_T2_WINDOW_BARS bars
      3. Breadth >= A3_MIN_BREADTH (T2 not blocked)

    Returns rows that are "T2-eligible" under simplified A3-like rules.
    """
    required = ["ema20", "sma100", "adv20_vnd", "market_pct_above_sma50"]
    missing = [c for c in required if c not in panel.columns]
    if missing:
        logger.warning("Missing cols for A3 T2 detection: %s", missing)
        return pd.DataFrame()

    # Uptrend check
    in_uptrend = (panel["close"] > panel["ema20"]) & (panel["close"] > panel["sma100"])

    # Recent high within window
    roll_high = panel.groupby("symbol")["high"].transform(
        lambda s: s.rolling(A3_T2_WINDOW_BARS, min_periods=A3_T2_WINDOW_BARS // 2).max().shift(1)
    )
    pullback_pct = (roll_high - panel["close"]) / roll_high.replace(0, np.nan)
    deep_pullback = pullback_pct >= A3_T2_PULLBACK_PCT

    # Breadth gate
    breadth_ok = panel["market_pct_above_sma50"].fillna(50.0) >= A3_MIN_BREADTH

    is_t2 = in_uptrend & deep_pullback & breadth_ok & roll_high.notna()

    t2_df = panel[is_t2].copy()
    t2_df["a3_t2_pullback_pct"] = pullback_pct[is_t2].values

    # Attach forward returns
    fwd_cols = [c for c in ["fwd_ret_5d", "fwd_ret_10d", "fwd_ret_20d", "mfe_20d", "mae_20d"]
                if c in panel.columns]
    keep = ["symbol", "date", "close", "a3_t2_pullback_pct",
            "stock_phase", "breadth_regime", "vin_return_distortion_flag"] + fwd_cols
    keep = [c for c in keep if c in t2_df.columns]
    return t2_df[keep].reset_index(drop=True)


# ── V1 T2 support gate overlay ────────────────────────────────────────────────

def evaluate_v1_t2_gate(
    t2_df: pd.DataFrame,
    profiles: pd.DataFrame,
    panel: pd.DataFrame,
) -> dict:
    """
    V1: Among A3 T2 candidates, compare outcomes for:
      - DNA-aligned: symbol has MEDIUM/HIGH profile AND price near primary support line
      - DNA-off: all other T2 candidates

    Returns metrics dict.
    """
    if t2_df.empty or profiles.empty:
        return {}

    med_plus = profiles[
        profiles["confidence"].isin(["MEDIUM", "HIGH"])
    ].set_index("symbol")

    # Join primary support line value per (symbol, date)
    line_values = {}
    for line_col in ["ema20", "ema50", "sma100", "sma150"]:
        if line_col in panel.columns:
            lv = panel.set_index(["symbol", "date"])[line_col]
            line_values[line_col] = lv

    dna_aligned, dna_off = [], []

    for _, row in t2_df.iterrows():
        symbol = row["symbol"]
        close  = float(row["close"])

        if symbol not in med_plus.index:
            dna_off.append(row)
            continue

        profile = med_plus.loc[symbol]
        primary = profile.get("primary_support_line")
        if not primary or primary not in line_values:
            dna_off.append(row)
            continue

        try:
            line_val = float(line_values[primary].get((symbol, row["date"]), np.nan))
        except Exception:
            line_val = np.nan

        if pd.isna(line_val) or line_val <= 0:
            dna_off.append(row)
            continue

        dist = abs(close - line_val) / line_val
        if dist <= 0.03:   # within 3%
            dna_aligned.append(row)
        else:
            dna_off.append(row)

    def _stats(rows: list) -> dict:
        if not rows:
            return {"n": 0, "bounce_rate_20d": np.nan, "median_fwd_ret_20d": np.nan}
        df = pd.DataFrame(rows)
        if "fwd_ret_20d" not in df.columns:
            return {"n": len(df), "bounce_rate_20d": np.nan, "median_fwd_ret_20d": np.nan}
        vals = df["fwd_ret_20d"].dropna()
        return {
            "n": len(vals),
            "bounce_rate_20d": float((vals > 0).mean()) if len(vals) else np.nan,
            "median_fwd_ret_20d": float(vals.median()) if len(vals) else np.nan,
        }

    aligned_stats = _stats(dna_aligned)
    off_stats     = _stats(dna_off)

    lift = (
        float(aligned_stats["bounce_rate_20d"] - off_stats["bounce_rate_20d"])
        if (pd.notna(aligned_stats["bounce_rate_20d"]) and pd.notna(off_stats["bounce_rate_20d"]))
        else np.nan
    )

    return {
        "variant": "V1_T2_SUPPORT_GATE (A3-like T2 proxy — NOT production A3)",
        "dna_aligned_n": aligned_stats["n"],
        "dna_aligned_bounce_rate_20d": aligned_stats["bounce_rate_20d"],
        "dna_aligned_median_fwd_ret_20d": aligned_stats["median_fwd_ret_20d"],
        "dna_off_n": off_stats["n"],
        "dna_off_bounce_rate_20d": off_stats["bounce_rate_20d"],
        "dna_off_median_fwd_ret_20d": off_stats["median_fwd_ret_20d"],
        "v1_lift_vs_dna_off": lift,
        "research_label": RESEARCH_ONLY_LABEL,
    }


# ── Annual breakdown ──────────────────────────────────────────────────────────

def compute_annual_overlay(
    t2_df: pd.DataFrame,
    profiles: pd.DataFrame,
    panel: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute V1 metrics by year for OOS stability assessment.
    Columns: year, baseline_n, baseline_bounce_rate_20d,
             v1_aligned_n, v1_aligned_bounce_rate_20d,
             v1_off_support_n, v1_off_support_bounce_rate_20d, v1_lift_pp
    """
    if t2_df.empty or "fwd_ret_20d" not in t2_df.columns:
        return pd.DataFrame()

    t2_df = t2_df.copy()
    t2_df["year"] = pd.to_datetime(t2_df["date"]).dt.year

    # Determine DNA-aligned flag per row
    med_plus = profiles[
        profiles["confidence"].isin(["MEDIUM", "HIGH"])
    ].set_index("symbol") if not profiles.empty else pd.DataFrame()

    line_values: dict = {}
    for line_col in ["ema20", "ema50", "sma100", "sma150"]:
        if line_col in panel.columns:
            line_values[line_col] = panel.set_index(["symbol", "date"])[line_col]

    aligned_mask = pd.Series(False, index=t2_df.index)
    if not med_plus.empty:
        for idx, row in t2_df.iterrows():
            sym = row["symbol"]
            if sym not in med_plus.index:
                continue
            profile = med_plus.loc[sym]
            primary = profile.get("primary_support_line")
            if not primary or primary not in line_values:
                continue
            try:
                line_val = float(line_values[primary].get((sym, row["date"]), np.nan))
            except Exception:
                continue
            if pd.isna(line_val) or line_val <= 0:
                continue
            if abs(float(row["close"]) - line_val) / line_val <= 0.03:
                aligned_mask.at[idx] = True

    rows = []
    for year, grp in t2_df.groupby("year"):
        fwd = grp["fwd_ret_20d"].dropna()
        base_br = float((fwd > 0).mean()) if len(fwd) else np.nan

        aligned_grp = grp[aligned_mask.loc[grp.index]]
        off_grp     = grp[~aligned_mask.loc[grp.index]]

        a_fwd = aligned_grp["fwd_ret_20d"].dropna()
        o_fwd = off_grp["fwd_ret_20d"].dropna()

        a_br = float((a_fwd > 0).mean()) if len(a_fwd) else np.nan
        o_br = float((o_fwd > 0).mean()) if len(o_fwd) else np.nan
        lift_pp = float((a_br - o_br) * 100) if (pd.notna(a_br) and pd.notna(o_br)) else np.nan

        rows.append({
            "year": int(year),
            "baseline_n": len(grp),
            "baseline_bounce_rate_20d": base_br,
            "v1_aligned_n": len(a_fwd),
            "v1_aligned_bounce_rate_20d": a_br,
            "v1_off_support_n": len(o_fwd),
            "v1_off_support_bounce_rate_20d": o_br,
            "v1_lift_pp": lift_pp,
        })

    return pd.DataFrame(rows)


def _load_a3_trade_ledger(path: str) -> pd.DataFrame:
    """
    Load an actual A3 historical signal / trade ledger CSV.
    Expected columns: symbol, date, signal_type (at minimum).
    Returns empty DataFrame if path is None or file not found.
    """
    if not path:
        return pd.DataFrame()
    p = Path(path)
    if not p.exists():
        logger.warning("A3 trade ledger not found at %s — skipping true overlay", p)
        return pd.DataFrame()
    df = pd.read_csv(p, low_memory=False)
    df["date"] = pd.to_datetime(df["date"])
    logger.info("Loaded A3 trade ledger: %d rows from %s", len(df), p)
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Stock DNA A3-like T2 Proxy Backtest")
    parser.add_argument("--start",             default="2016-01-01",  help="Panel start date")
    parser.add_argument("--end",               default=None)
    parser.add_argument("--profile-dir",       default=str(DNA_DIR),  help="Directory with existing profiles CSV")
    parser.add_argument("--output-dir",        default=str(DNA_DIR))
    parser.add_argument("--data-dir",          default="data")
    parser.add_argument("--a3-trade-ledger",   default=None,
                        help="Optional path to actual A3 historical signal/trade CSV for true overlay. "
                             "Without this, results use simplified A3-like T2 proxy rules only.")
    args = parser.parse_args()

    output_dir  = Path(args.output_dir)
    data_dir    = Path(args.data_dir)
    profile_dir = Path(args.profile_dir)

    # Safety: block writes to production paths
    assert_output_path_safe(output_dir)

    logger.info("=" * 60)
    logger.info("Stock DNA A3-like T2 Proxy Backtest — %s", RESEARCH_ONLY_LABEL)
    logger.info("Label: %s", A3_PROXY_LABEL)
    logger.info("=" * 60)

    # Load profiles
    profiles_path = profile_dir / "stock_dna_symbol_profiles.csv"
    if not profiles_path.exists():
        logger.error("Profiles not found at %s — run discovery first.", profiles_path)
        sys.exit(1)

    profiles = pd.read_csv(profiles_path)
    logger.info("Loaded %d profiles from %s", len(profiles), profiles_path)

    # Optional: true A3 historical ledger
    a3_ledger = _load_a3_trade_ledger(args.a3_trade_ledger)
    if not a3_ledger.empty:
        logger.info("True A3 ledger loaded — will compute true overlay metrics in addition to proxy.")

    # Build panel
    logger.info("Building DNA panel for overlay backtest...")
    panel = build_dna_panel(
        data_dir=data_dir,
        start_date=args.start,
        end_date=args.end,
        min_adv20_vnd=5e9,
        apply_liquidity_filter=True,
    )

    # Detect T2 candidates
    logger.info("Detecting simplified A3 T2 candidates...")
    t2_df = detect_a3_t2_candidates(panel)
    logger.info("T2 candidates: %d events", len(t2_df))

    if t2_df.empty:
        logger.warning("No T2 candidates detected.")
        sys.exit(0)

    # V1 overlay evaluation
    logger.info("Evaluating V1 T2 support gate overlay...")
    v1_metrics = evaluate_v1_t2_gate(t2_df, profiles, panel)

    if v1_metrics:
        logger.info(
            "V1 result: aligned=%d (br=%.1f%%), off=%d (br=%.1f%%), lift=%+.1f%%",
            v1_metrics.get("dna_aligned_n", 0),
            v1_metrics.get("dna_aligned_bounce_rate_20d", float("nan")),
            v1_metrics.get("dna_off_n", 0),
            v1_metrics.get("dna_off_bounce_rate_20d", float("nan")),
            v1_metrics.get("v1_lift_vs_dna_off", float("nan")),
        )

    # Annual breakdown
    annual_df = compute_annual_overlay(t2_df, profiles, panel)
    if not annual_df.empty:
        annual_path = output_dir / "stock_dna_a3_overlay_by_year.csv"
        output_dir.mkdir(parents=True, exist_ok=True)
        annual_df.to_csv(annual_path, index=False)
        logger.info("Annual overlay saved: %s", annual_path)

    # Trade-level CSV — enrich with DNA columns, then save full + sample
    med_plus_idx = profiles[
        profiles["confidence"].isin(["MEDIUM", "HIGH"])
    ].set_index("symbol") if not profiles.empty else pd.DataFrame()

    line_values_tl: dict = {}
    for lc in ["ema20", "ema50", "sma100", "sma150"]:
        if lc in panel.columns:
            line_values_tl[lc] = panel.set_index(["symbol", "date"])[lc]

    t2_enriched = t2_df.copy()
    aligned_col, psl_col, pst_col, dist_col = [], [], [], []
    conf_col, sconf_col, econf_col, nullz_col = [], [], [], []
    annot_col, dl_col, dl_flag_col = [], [], []

    for _, row in t2_enriched.iterrows():
        sym = row["symbol"]
        close = float(row["close"])

        if not med_plus_idx.empty and sym in med_plus_idx.index:
            prof = med_plus_idx.loc[sym]
            primary = prof.get("primary_support_line")
            tol     = prof.get("best_tolerance")
            conf    = prof.get("confidence", "NONE")
            sconf   = prof.get("sample_confidence", conf)
            econf   = prof.get("edge_confidence", "NONE")
            nullz   = prof.get("per_symbol_null_z", np.nan)
            dline   = prof.get("danger_line")

            if primary and primary in line_values_tl:
                try:
                    lv = float(line_values_tl[primary].get((sym, row["date"]), np.nan))
                except Exception:
                    lv = np.nan
            else:
                lv = np.nan

            if pd.notna(lv) and lv > 0:
                dist = abs(close - lv) / lv
                is_aligned = int(dist <= 0.03)
            else:
                dist = np.nan
                is_aligned = 0

            dl_val = dline if dline else None
            dl_flag = 0
            if dl_val and dl_val in line_values_tl:
                try:
                    dlv = float(line_values_tl[dl_val].get((sym, row["date"]), np.nan))
                    if pd.notna(dlv) and dlv > 0 and close < dlv:
                        dl_flag = 1
                except Exception:
                    pass

            annot = f"V1_ALIGNED:{primary}@{tol}" if is_aligned else "V1_OFF_SUPPORT"
        else:
            primary = tol = conf = sconf = econf = dline = annot = None
            nullz = dist = np.nan
            is_aligned = dl_flag = 0
            dl_val = None

        aligned_col.append(is_aligned)
        psl_col.append(primary)
        pst_col.append(tol)
        dist_col.append(round(dist, 5) if pd.notna(dist) else np.nan)
        conf_col.append(conf)
        sconf_col.append(sconf)
        econf_col.append(econf)
        nullz_col.append(round(float(nullz), 4) if pd.notna(nullz) else np.nan)
        annot_col.append(annot)
        dl_col.append(dl_val)
        dl_flag_col.append(dl_flag)

    t2_enriched["is_stock_dna_aligned"]     = aligned_col
    t2_enriched["primary_support_line"]     = psl_col
    t2_enriched["primary_support_tolerance"]= pst_col
    t2_enriched["distance_to_support_pct"]  = dist_col
    t2_enriched["stock_dna_confidence"]     = conf_col
    t2_enriched["sample_confidence"]        = sconf_col
    t2_enriched["edge_confidence"]          = econf_col
    t2_enriched["per_symbol_null_z"]        = nullz_col
    t2_enriched["v1_annotation"]            = annot_col
    t2_enriched["danger_line"]              = dl_col
    t2_enriched["danger_line_flag"]         = dl_flag_col

    output_dir.mkdir(parents=True, exist_ok=True)
    full_path   = output_dir / "stock_dna_trade_level_overlay_full.csv"
    sample_path = output_dir / "stock_dna_trade_level_overlay_sample.csv"
    trade_path  = output_dir / "stock_dna_trade_level_overlay.csv"   # backward-compat → sample

    t2_enriched.to_csv(full_path, index=False)
    t2_enriched.head(500).to_csv(sample_path, index=False)
    t2_enriched.head(500).to_csv(trade_path, index=False)
    logger.info("Trade-level overlay full saved: %s (%d rows)", full_path, len(t2_enriched))
    logger.info("Trade-level overlay sample saved: %s (500 rows)", sample_path)

    # Save overlay metrics
    baseline_br = float((t2_df["fwd_ret_20d"].dropna() > 0).mean()) if "fwd_ret_20d" in t2_df.columns else float("nan")
    full_metrics = {
        "proxy_label": A3_PROXY_LABEL,
        "baseline_bounce_rate_20d": baseline_br,
        "baseline_n_events": len(t2_df),
        "v1_t2_gate_bounce_rate_20d": v1_metrics.get("dna_aligned_bounce_rate_20d", float("nan")),
        "v1_t2_gate_n_events": v1_metrics.get("dna_aligned_n", 0),
        "v1_t2_gate_lift": v1_metrics.get("v1_lift_vs_dna_off", float("nan")),
        "n_dna_profiled_symbols": len(profiles[profiles["confidence"].isin(["MEDIUM", "HIGH"])]),
        "oos_start": "from_profiles",
        "a3_true_ledger_used": not a3_ledger.empty,
        "research_label": RESEARCH_ONLY_LABEL,
        "WARNING": "proxy_label applies — do not claim A3 improvement without a3_true_ledger_used=True",
    }
    save_overlay_metrics(full_metrics, output_dir)

    logger.info("=" * 60)
    logger.info("Overlay backtest complete. Outputs in: %s", output_dir)
    logger.info("Next step: run build_stock_dna_report.py")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
