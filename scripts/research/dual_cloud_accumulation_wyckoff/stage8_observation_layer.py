#!/usr/bin/env python3
"""Stage 8 — Observation Layer / Forward Validation

PAPER VALIDATION / OBSERVATION ONLY.
No production/OMS/live changes. No final_action modification.
No ranking, sizing, blocking, or order-generation logic.
No DNSE/live enablement.

Exports Stage 7 WATCHLIST_ONLY observation fields alongside A3/S3 signal
records for forward validation over the next 3–12 months.

SAFETY ENFORCEMENT:
    _OMS_SAFE_PATHS : frozenset of OMS/live file paths Stage 8 must NEVER write to.
    _STAGE8_WRITE_DIR: the ONLY directory Stage 8 writes to.
    All score/quintile fields are labeled observation_only.
    old_composite_rejected_flag is always True.
    wyckoff_sos is diagnostic_only; LPS/spring not used as positive signals.

Outputs (all in outputs/research/dual_cloud_accumulation_wyckoff/):
    stage8_observation_fields.csv              — full A3+S3 signal universe
    stage8_forward_validation_ledger_template.csv  — recent signals, blank fwd returns
    stage8_daily_scan_overlay.csv              — recent signals for daily monitoring
    STAGE8_OBSERVATION_LAYER_FINDINGS.md

Usage:
    .venv\\Scripts\\python.exe scripts/research/dual_cloud_accumulation_wyckoff/stage8_observation_layer.py
"""
from __future__ import annotations

import logging
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from scripts.research.dual_cloud_accumulation_wyckoff.panel_utils import (
    OUT_DIR, MIN_ADV_VND, load_vnindex_regime,
)
from scripts.research.dual_cloud_accumulation_wyckoff.features import (
    compute_candidate_score_dategroup,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Safety enforcement ────────────────────────────────────────────────────────

# Stage 8 writes ONLY to this directory — tests verify this
_STAGE8_WRITE_DIR: Path = OUT_DIR

# Paths Stage 8 must never write to — tested in test suite
_OMS_SAFE_PATHS: frozenset[str] = frozenset({
    str(REPO / "data" / "decision" / "daily_scan.json"),
    str(REPO / "data" / "decision" / "daily_scan.md"),
    str(REPO / "data" / "decision" / "allocation_plan.json"),
    str(REPO / "data" / "state" / "regime_state.json"),
    str(REPO / "data" / "raw" / "current_positions_derived.json"),
    str(REPO / "data" / "raw" / "current_positions_digest.md"),
})

# ── Stage 7 watchlist candidate specs (WATCHLIST_ONLY classification) ────────

_SPEC_BVE = [
    ("bo_vol_exp",   True, 0.40),
    ("bo_range_exp", True, 0.30),
    ("vol_trend_10", True, 0.30),
]

_SPEC_TPBCQ = [
    ("pt_20",        True, 0.25),
    ("pt_40",        True, 0.25),
    ("bo_close_str", True, 0.30),
    ("bo_vol_exp",   True, 0.20),
]

# ── Input paths ───────────────────────────────────────────────────────────────

_STAGE1_TRADES = OUT_DIR / "stage1_trades.csv"
_STAGE4_S3     = OUT_DIR / "stage4_s3_trades.csv"

# ── Observation window ────────────────────────────────────────────────────────

_LEDGER_CUTOFF  = "2024-01-01"   # forward validation ledger: signals from this date
_OVERLAY_CUTOFF = "2025-01-01"   # daily scan overlay: signals from this date


# ── Liquidity bucket ──────────────────────────────────────────────────────────

def _liq_bucket(adv50: float) -> str:
    if pd.isna(adv50) or adv50 < 2e9:
        return "below_2B"
    if adv50 < 5e9:
        return "2B_5B"
    if adv50 < 20e9:
        return "5B_20B"
    return "20B_plus"


# ── Data loaders ──────────────────────────────────────────────────────────────

def _load_a3_signals() -> pd.DataFrame:
    """Load Stage 1 trades, deduplicate to unique A3 signal events."""
    if not _STAGE1_TRADES.exists():
        raise FileNotFoundError(
            f"Stage 1 output not found: {_STAGE1_TRADES}\n"
            "Run Stage 1 first: run_all.py --stage 1"
        )
    df = pd.read_csv(_STAGE1_TRADES)
    df = df[df["horizon"] == 63].copy()
    df["signal_date"] = pd.to_datetime(df["signal_date"])
    df = df.drop_duplicates(subset=["symbol", "signal_bar", "signal_date"]).reset_index(drop=True)
    df["signal_type"] = "A3"
    df["a3_signal"]   = True
    df["s3_signal"]   = False
    df["s3lead5"]     = False
    log.info("A3 signals loaded: %d unique across %d symbols", len(df), df["symbol"].nunique())
    return df


def _load_s3_signals() -> pd.DataFrame | None:
    """Load Stage 4 S3 shadow trades. Returns None if file not present."""
    if not _STAGE4_S3.exists():
        log.warning("Stage 4 S3 output not found — S3 signals will not be merged")
        return None
    df = pd.read_csv(_STAGE4_S3)
    df["signal_date"] = pd.to_datetime(df["signal_date"])
    df = df.drop_duplicates(subset=["symbol", "signal_bar", "signal_date"]).reset_index(drop=True)
    df["signal_type"] = "S3"
    df["a3_signal"]   = False
    df["s3_signal"]   = True
    log.info("S3 signals loaded: %d unique across %d symbols", len(df), df["symbol"].nunique())
    return df


def _mark_s3_lead(a3_df: pd.DataFrame, s3_df: pd.DataFrame | None, window: int = 5) -> pd.DataFrame:
    """
    For each A3 signal, flag s3lead5=True if an S3 signal fired on the same
    symbol within `window` calendar days before the A3 signal date.
    """
    if s3_df is None or s3_df.empty:
        return a3_df
    s3_lookup: dict[str, list[pd.Timestamp]] = {}
    for sym, grp in s3_df.groupby("symbol"):
        s3_lookup[str(sym)] = sorted(grp["signal_date"].tolist())

    leads = []
    cutoff = pd.Timedelta(days=window)
    for _, row in a3_df.iterrows():
        sym   = str(row["symbol"])
        adate = row["signal_date"]
        dates = s3_lookup.get(sym, [])
        flag  = any((adate - cutoff) <= d < adate for d in dates)
        leads.append(flag)
    a3_df = a3_df.copy()
    a3_df["s3lead5"] = leads
    return a3_df


# ── Score computation ─────────────────────────────────────────────────────────

def _compute_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute date-group stable observation scores for both watchlist candidates.
    Scores use only historical signal dates < current date (causal).
    Quintiles are cross-sectional across the full dataset (observation display only,
    not used for selection).

    Returns df with added columns:
        breakout_value_expansion_score, breakout_value_expansion_q
        tightness_plus_breakout_close_quality_score, tightness_plus_breakout_close_quality_q
        old_composite_score (from stage1 'score' column if present)
        old_composite_q    (quintile of old_composite_score)
    """
    df = df.copy()

    bve_score  = compute_candidate_score_dategroup(df, _SPEC_BVE)
    tpbcq_score = compute_candidate_score_dategroup(df, _SPEC_TPBCQ)

    df["breakout_value_expansion_score"] = bve_score.values
    df["tightness_plus_breakout_close_quality_score"] = tpbcq_score.values

    # Global quintiles for observation display only
    df["breakout_value_expansion_q"] = pd.qcut(
        bve_score.rank(method="first"), 5, labels=False
    ).astype("Int64") + 1

    df["tightness_plus_breakout_close_quality_q"] = pd.qcut(
        tpbcq_score.rank(method="first"), 5, labels=False
    ).astype("Int64") + 1

    # Old composite score (from Stage 1 output; pre-computed using rejected spec)
    if "score" in df.columns:
        df["old_composite_score"] = df["score"]
        df["old_composite_q"] = pd.qcut(
            df["score"].rank(method="first"), 5, labels=False
        ).astype("Int64") + 1
    else:
        df["old_composite_score"] = np.nan
        df["old_composite_q"]     = pd.NA

    return df


# ── Regime and liquidity labels ───────────────────────────────────────────────

def _add_regime(df: pd.DataFrame, regime_map: pd.Series) -> pd.DataFrame:
    df = df.copy()
    aligned = regime_map.reindex(df["signal_date"]).ffill().fillna(False)
    df["vnindex_regime"] = aligned.values
    df["vnindex_regime"] = df["vnindex_regime"].map({True: "bull", False: "bear_sideways"})
    return df


def _add_liquidity_bucket(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    adv_col = "adv50" if "adv50" in df.columns else None
    if adv_col:
        df["liquidity_bucket"] = df[adv_col].apply(_liq_bucket)
    else:
        df["liquidity_bucket"] = "unknown"
    return df


# ── Observation flags ─────────────────────────────────────────────────────────

def _add_observation_flags(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add classification flags. All flags are observation_only.

    Rules:
    - old_composite_rejected_flag: ALWAYS True (REJECT classification)
    - breakout_value_expansion_watchlist_flag: True if BVE score Q4/Q5
    - tightness_plus_breakout_watchlist_flag: True if TPBCQ score Q4/Q5
    - wyckoff_sos_diagnostic_flag: True if sos==1 (diagnostic only, not tradable)
    - wyckoff_lps_rejected_flag: True if lps==1 (LPS anti-predictive, not a positive signal)
    - wyckoff_spring_rejected_flag: True if spring==1 (spring anti-predictive)
    """
    df = df.copy()

    df["old_composite_rejected_flag"]                 = True  # always
    df["breakout_value_expansion_watchlist_flag"]     = (
        df.get("breakout_value_expansion_q", pd.Series(pd.NA, index=df.index)) >= 4
    ).fillna(False)
    df["tightness_plus_breakout_watchlist_flag"]      = (
        df.get("tightness_plus_breakout_close_quality_q", pd.Series(pd.NA, index=df.index)) >= 4
    ).fillna(False)
    df["wyckoff_sos_diagnostic_flag"]                 = (
        df.get("sos", pd.Series(0, index=df.index)) == 1
    )
    df["wyckoff_lps_rejected_flag"]                   = (
        df.get("lps", pd.Series(0, index=df.index)) == 1
    )
    df["wyckoff_spring_rejected_flag"]                = (
        df.get("spring", pd.Series(0, index=df.index)) == 1
    )
    # Wyckoff alias columns (original names)
    df["wyckoff_sos"]         = df.get("sos",    pd.Series(0, index=df.index))
    df["wyckoff_lps"]         = df.get("lps",    pd.Series(0, index=df.index))
    df["wyckoff_spring_test"] = df.get("spring", pd.Series(0, index=df.index))

    # Safety label: no field here is decision-path
    df["field_usage"] = "observation_only"
    return df


# ── Column selection ──────────────────────────────────────────────────────────

_OBSERVATION_COLS = [
    # Identity
    "signal_date", "symbol", "signal_type", "a3_signal", "s3_signal", "s3lead5",
    "year",
    # Market context
    "close_kvnd", "adv50_vnd", "liquidity_bucket", "vnindex_regime",
    "sector_l4", "breadth_bucket",
    # Core features
    "pt_20", "pt_40", "bo_vol_exp", "vol_trend_10", "bo_close_str",
    "bo_range_exp", "atr_ratio", "vol_drying",
    # Watchlist candidate scores (observation only)
    "breakout_value_expansion_score", "breakout_value_expansion_q",
    "tightness_plus_breakout_close_quality_score", "tightness_plus_breakout_close_quality_q",
    # Wyckoff tags (diagnostic only)
    "wyckoff_sos", "wyckoff_lps", "wyckoff_spring_test",
    # Rejected score (kept for reference)
    "old_composite_score", "old_composite_q",
    # Classification flags
    "breakout_value_expansion_watchlist_flag",
    "tightness_plus_breakout_watchlist_flag",
    "wyckoff_sos_diagnostic_flag",
    "wyckoff_lps_rejected_flag",
    "wyckoff_spring_rejected_flag",
    "old_composite_rejected_flag",
    # Safety label
    "field_usage",
]

_LEDGER_COLS = [
    "observation_date", "symbol", "signal_type", "a3_signal", "s3_signal", "s3lead5",
    "close_kvnd", "adv50_vnd", "liquidity_bucket", "vnindex_regime",
    "sector_l4", "breadth_bucket",
    "breakout_value_expansion_q", "tightness_plus_breakout_close_quality_q",
    "wyckoff_sos", "old_composite_q",
    # Forward return columns — blank initially, to be filled as data becomes available
    "fwd_5d_return", "fwd_10d_return", "fwd_20d_return", "fwd_40d_return", "fwd_63d_return",
    "tp1_hit_63d", "max_adverse_excursion_63d", "max_favorable_excursion_63d",
    # Operator fields
    "actual_trade_taken", "actual_trade_reason", "operator_note",
]


def _build_observation_df(a3_df: pd.DataFrame, s3_df: pd.DataFrame | None,
                          regime_map: pd.Series) -> pd.DataFrame:
    """Build the full observation fields DataFrame from A3 signals."""
    df = a3_df.copy()
    df = _mark_s3_lead(df, s3_df)
    df = _compute_scores(df)
    df = _add_regime(df, regime_map)
    df = _add_liquidity_bucket(df)
    df = _add_observation_flags(df)

    # Column aliases
    df["close_kvnd"]    = df.get("entry_price", np.nan)
    df["adv50_vnd"]     = df.get("adv50",       np.nan)
    df["sector_l4"]     = np.nan
    df["breadth_bucket"] = np.nan

    # Select and order columns, filling missing with NaN
    out_cols = [c for c in _OBSERVATION_COLS if c in df.columns or c in {
        "sector_l4", "breadth_bucket", "s3lead5", "s3_signal",
        "close_kvnd", "adv50_vnd",
    }]
    for c in out_cols:
        if c not in df.columns:
            df[c] = np.nan

    return df[out_cols].sort_values("signal_date").reset_index(drop=True)


def _build_ledger_template(obs_df: pd.DataFrame) -> pd.DataFrame:
    """Build forward validation ledger — recent signals with blank fwd return fields."""
    recent = obs_df[obs_df["signal_date"] >= _LEDGER_CUTOFF].copy()
    recent = recent.rename(columns={"signal_date": "observation_date"})

    for c in _LEDGER_COLS:
        if c not in recent.columns:
            recent[c] = np.nan

    # Forward return fields are always blank (to be filled by operator/future runs)
    for c in ["fwd_5d_return", "fwd_10d_return", "fwd_20d_return",
              "fwd_40d_return", "fwd_63d_return",
              "tp1_hit_63d", "max_adverse_excursion_63d", "max_favorable_excursion_63d",
              "actual_trade_taken", "actual_trade_reason", "operator_note"]:
        recent[c] = np.nan

    return recent[_LEDGER_COLS].sort_values("observation_date").reset_index(drop=True)


def _build_daily_overlay(obs_df: pd.DataFrame) -> pd.DataFrame:
    """Build daily scan overlay — most recent signals for monitoring."""
    overlay_cols = [
        "signal_date", "symbol", "signal_type", "a3_signal", "s3_signal", "s3lead5",
        "close_kvnd", "adv50_vnd", "liquidity_bucket", "vnindex_regime",
        "pt_20", "pt_40", "bo_vol_exp", "vol_trend_10",
        "breakout_value_expansion_score", "breakout_value_expansion_q",
        "tightness_plus_breakout_close_quality_score", "tightness_plus_breakout_close_quality_q",
        "wyckoff_sos", "old_composite_q",
        "breakout_value_expansion_watchlist_flag",
        "tightness_plus_breakout_watchlist_flag",
        "wyckoff_sos_diagnostic_flag",
        "old_composite_rejected_flag",
        "field_usage",
    ]
    recent = obs_df[obs_df["signal_date"] >= _OVERLAY_CUTOFF].copy()
    for c in overlay_cols:
        if c not in recent.columns:
            recent[c] = np.nan
    return recent[overlay_cols].sort_values("signal_date").reset_index(drop=True)


# ── Markdown report ───────────────────────────────────────────────────────────

def _write_findings(obs_df: pd.DataFrame, ledger_df: pd.DataFrame,
                    overlay_df: pd.DataFrame) -> None:
    n_a3  = int(obs_df["a3_signal"].sum())
    n_s3  = int(obs_df.get("s3_signal", pd.Series(False)).sum())
    n_bve = int(obs_df.get("breakout_value_expansion_watchlist_flag", pd.Series(False)).sum())
    n_tpb = int(obs_df.get("tightness_plus_breakout_watchlist_flag", pd.Series(False)).sum())
    n_sos = int(obs_df.get("wyckoff_sos_diagnostic_flag", pd.Series(False)).sum())
    n_rej = int(obs_df.get("old_composite_rejected_flag", pd.Series(False)).sum())

    bve_q5  = obs_df[obs_df.get("breakout_value_expansion_q", pd.Series(pd.NA)) == 5]
    tpb_q5  = obs_df[obs_df.get("tightness_plus_breakout_close_quality_q", pd.Series(pd.NA)) == 5]
    bve_wr  = float((bve_q5["net_return"] >= 0.15).mean()) if "net_return" in bve_q5.columns and len(bve_q5) > 0 else float("nan")
    all_wr  = float((obs_df["net_return"] >= 0.15).mean()) if "net_return" in obs_df.columns else float("nan")

    lines = [
        "# Stage 8 — Observation Layer / Forward Validation",
        "",
        f"**Run date:** {pd.Timestamp.now().date()}",
        "",
        "## 1. Safety Confirmation",
        "",
        "| Check | Status |",
        "|---|---|",
        "| A3 production contract unchanged | YES — research only |",
        "| S3 remains paper-shadow only | YES |",
        "| S3 does not gate A3 | YES |",
        "| OMS/live/DNSE files untouched | YES — writes only to outputs/research/ |",
        "| final_action unchanged | YES — Stage 8 does not write decision fields |",
        "| All Stage 8 fields observation_only | YES — field_usage='observation_only' |",
        "| old_composite_score marked REJECT | YES — old_composite_rejected_flag=True always |",
        "| Wyckoff SOS diagnostic_only | YES — wyckoff_sos_diagnostic_flag |",
        "| LPS/spring NOT positive ranking signals | YES — wyckoff_lps_rejected_flag/wyckoff_spring_rejected_flag |",
        "",
        "## 2. Objective",
        "",
        "Stage 8 exports Stage 7 WATCHLIST_ONLY observation fields to support",
        "forward validation over 3–12 months. No trading decisions are made.",
        "The two WATCHLIST_ONLY candidates from Stage 7 are:",
        "- **breakout_value_expansion** (BVE): Q5 delta +4.3pp, 3/3 train/val/test positive",
        "- **tightness_plus_breakout_close_quality** (TPBCQ): Q5 delta +4.3pp, highest Spearman rho",
        "",
        "Both remain WATCHLIST_ONLY. Neither is approved for order-generation, sizing, or blocking.",
        "",
        "## 3. Output Coverage",
        "",
        f"| File | Rows |",
        f"|---|---|",
        f"| stage8_observation_fields.csv | {len(obs_df)} A3 signals |",
        f"| stage8_forward_validation_ledger_template.csv | {len(ledger_df)} (2024+ signals) |",
        f"| stage8_daily_scan_overlay.csv | {len(overlay_df)} (2025+ signals) |",
        "",
        "## 4. Signal Counts",
        "",
        f"| Field | Count |",
        f"|---|---|",
        f"| A3 signals (total) | {n_a3} |",
        f"| breakout_value_expansion_watchlist_flag (Q4/Q5) | {n_bve} |",
        f"| tightness_plus_breakout_watchlist_flag (Q4/Q5) | {n_tpb} |",
        f"| wyckoff_sos_diagnostic_flag | {n_sos} |",
        f"| old_composite_rejected_flag | {n_rej} (all rows) |",
        "",
        "## 5. Historical Performance (reference only)",
        "",
        "From Stage 7 research (not forward-validated):",
        f"- All A3 signals: win_rate={all_wr:.1%} at 63-bar horizon" if not np.isnan(all_wr) else "- All A3 signals: win_rate=n/a",
        f"- BVE Q5 historical: win_rate={bve_wr:.1%} ({len(bve_q5)} signals)" if not np.isnan(bve_wr) else "- BVE Q5: n/a",
        "- These are in-sample backtested numbers. Forward results may differ.",
        "",
        "## 6. Forward Validation Design",
        "",
        "The ledger template contains blank columns for future fills:",
        "- fwd_5d/10d/20d/40d/63d_return — to be filled as market data arrives",
        "- tp1_hit_63d — whether +15% was reached within 63 bars",
        "- max_adverse/favorable_excursion_63d — drawdown and runup",
        "- actual_trade_taken — operator field (YES/NO/NA)",
        "- operator_note — free text",
        "",
        "Forward validation acceptance threshold (from Stage 7 rules):",
        "- Q5 win_rate must exceed all-signals win_rate by ≥5pp over ≥40 new observations",
        "- Confirmation required in ≥2 of: bull regime, bear/sideways, 2024–2025 signals",
        "",
        "## 7. By-Year Reference (historical)",
        "",
        obs_df.groupby("year").agg(
            n_signals=("a3_signal", "sum"),
            bve_watchlist=("breakout_value_expansion_watchlist_flag", "sum"),
        ).reset_index().to_markdown(index=False) if "year" in obs_df.columns else "n/a",
        "",
        "## 8. FACTS vs INTERPRETATION",
        "",
        "**FACTS:**",
        "- Stage 8 exports observation fields only.",
        "- No production or OMS file was modified.",
        "- Both WATCHLIST candidates are below the PARALLEL_PAPER_RESEARCH threshold.",
        "- old_composite_score is REJECTED in all contexts.",
        "- Wyckoff SOS is DIAGNOSTIC ONLY.",
        "",
        "**INTERPRETATION (not yet validated):**",
        "- BVE and TPBCQ show 3/3 split-period lift in Stage 7 backtest.",
        "- These results require 3–12 months forward validation before any action.",
        "- Do NOT use Stage 8 quintiles for A3 entry decisions.",
        "- Do NOT gate, size, or block based on Stage 8 fields.",
        "",
        "## 9. Open Questions",
        "",
        "1. Will BVE Q5 lift hold in 2026 live signals? (test-period delta was +3.2pp)",
        "2. Does TPBCQ Q5 recover test-period weakness (+0.6pp) in fresh live data?",
        "3. Is 2021 regime anomaly (BVE Q5 +26.3pp) replicable or a sampling artifact?",
        "4. Does S3 signal co-occurrence improve or reduce A3 forward returns?",
        "",
        "## 10. Next Step",
        "",
        "Fill ledger template with actual forward returns as data arrives.",
        "Target: 40+ new Q5 observations before reassessment.",
        "At current A3 rate (~370 signals/year), Q5 adds ~74 new observations/year.",
        "Reassessment window: 6–9 months from first signal capture.",
    ]
    (OUT_DIR / "STAGE8_OBSERVATION_LAYER_FINDINGS.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


# ── Runner ────────────────────────────────────────────────────────────────────

def run(workers: int = 4) -> None:  # noqa: ARG001
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    a3_df = _load_a3_signals()
    s3_df = _load_s3_signals()

    log.info("Loading VNINDEX regime")
    regime_map = load_vnindex_regime()

    obs_df    = _build_observation_df(a3_df, s3_df, regime_map)
    ledger_df = _build_ledger_template(obs_df)
    overlay_df = _build_daily_overlay(obs_df)

    obs_df.to_csv(    OUT_DIR / "stage8_observation_fields.csv", index=False)
    ledger_df.to_csv( OUT_DIR / "stage8_forward_validation_ledger_template.csv", index=False)
    overlay_df.to_csv(OUT_DIR / "stage8_daily_scan_overlay.csv", index=False)
    _write_findings(obs_df, ledger_df, overlay_df)

    n_bve = int(obs_df.get("breakout_value_expansion_watchlist_flag", pd.Series(False)).sum())
    n_tpb = int(obs_df.get("tightness_plus_breakout_watchlist_flag", pd.Series(False)).sum())
    n_sos = int(obs_df.get("wyckoff_sos_diagnostic_flag", pd.Series(False)).sum())

    log.info(
        "Stage 8 complete: %d A3 signals | BVE watchlist Q4/Q5=%d | TPBCQ watchlist Q4/Q5=%d | "
        "SOS diagnostic=%d | old_composite rejected=%d",
        len(obs_df), n_bve, n_tpb, n_sos, len(obs_df),
    )
    log.info(
        "Outputs: observation=%d rows, ledger=%d rows, overlay=%d rows",
        len(obs_df), len(ledger_df), len(overlay_df),
    )
    log.info("Outputs in %s", OUT_DIR)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Stage 8 — Observation Layer")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    run(workers=args.workers)


if __name__ == "__main__":
    main()
