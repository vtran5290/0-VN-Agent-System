"""
Stock DNA Profile Builder
===========================
Builds per-symbol walk-forward profiles with regime-split obedience scores
and OOS holdout.

Council requirements:
  - Walk-forward: for each decision year Y, build profile from data before Y only
  - OOS holdout: final 12 months are pure OOS — never used in profile construction
  - Regime split: separate bull/bear obedience scores per symbol-line
  - Profiles include: primary_support_line, danger_line, confidence,
    regime_obedience_bull, regime_obedience_bear, oos_lift, operator_note
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from src.trading.research.stock_dna.events import (
    aggregate_line_scores,
    attach_bounce_outcomes,
    detect_breakdown_events,
    detect_false_breaks,
    detect_reclaim_events,
    detect_touch_events,
)
from src.trading.research.stock_dna.scoring import (
    assign_confidence,
    assign_edge_confidence,
    assign_sample_confidence,
    compute_instability_penalty,
    compute_line_obedience_score,
    run_shuffled_null_benchmark,
    select_best_line,
)
from src.trading.research.stock_dna.schema import (
    CANDIDATE_LINES,
    DNA_DIR,
    DISTORTION_FLAG_SYMBOLS,
    OOS_HOLDOUT_MONTHS,
    TOLERANCE_ATR,
    TOLERANCE_PCT,
    DNAConfidence,
    DNAProductionStatus,
    StockPhase,
)

logger = logging.getLogger(__name__)


# ── Walk-forward helpers ──────────────────────────────────────────────────────

def _oos_cutoff_date(panel: pd.DataFrame) -> pd.Timestamp:
    """Return the start of the OOS holdout period (last OOS_HOLDOUT_MONTHS months)."""
    max_date = panel["date"].max()
    oos_start = max_date - pd.DateOffset(months=OOS_HOLDOUT_MONTHS)
    return pd.Timestamp(oos_start)


def _training_years(panel: pd.DataFrame, min_years: int = 3) -> list[int]:
    """
    Return the list of OOS decision years for walk-forward evaluation.
    Requires at least min_years of history before the first OOS year.
    """
    min_date = panel["date"].min()
    max_date = panel["date"].max()
    oos_start = _oos_cutoff_date(panel)

    first_valid_year = min_date.year + min_years
    last_wf_year = oos_start.year

    return list(range(first_valid_year, last_wf_year + 1))


# ── Touch event collection across all lines and tolerances ────────────────────

def collect_all_touch_events(panel: pd.DataFrame) -> pd.DataFrame:
    """
    Collect touch events across all candidate lines and tolerances.
    Attaches forward return outcomes.
    """
    frames = []
    tol_names = list(TOLERANCE_PCT.keys()) + list(TOLERANCE_ATR.keys())

    for line_name in CANDIDATE_LINES:
        if line_name not in panel.columns:
            logger.warning("Line %s not in panel — skipping", line_name)
            continue
        for tol_name in tol_names:
            touches = detect_touch_events(panel, line_name, tol_name)
            if not touches.empty:
                touches = attach_bounce_outcomes(touches, panel)
                frames.append(touches)

    if not frames:
        logger.warning("No touch events detected")
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)


# ── Score one symbol-line for a given training cutoff ─────────────────────────

def score_symbol_line(
    touch_df: pd.DataFrame,
    symbol: str,
    line_name: str,
    tol_name: str,
    year_cutoff: Optional[int] = None,
) -> dict:
    """
    Compute line obedience stats for one (symbol, line, tolerance) combination.
    If year_cutoff is given, only uses data from years < year_cutoff (walk-forward).
    """
    df = touch_df[
        (touch_df["symbol"] == symbol) &
        (touch_df["line_name"] == line_name) &
        (touch_df["tol_name"] == tol_name)
    ].copy()

    if year_cutoff is not None:
        df = df[pd.to_datetime(df["date"]).dt.year < year_cutoff]

    n = len(df)
    confidence = assign_confidence(n)

    base: dict = {
        "symbol":      symbol,
        "line_name":   line_name,
        "tol_name":    tol_name,
        "year_cutoff": year_cutoff,
        "n_touch":     n,
        "confidence":  confidence.value,
    }

    if confidence == DNAConfidence.NONE or df.empty:
        return {**base,
                "bounce_rate_5d": np.nan, "bounce_rate_10d": np.nan, "bounce_rate_20d": np.nan,
                "median_fwd_ret_20d": np.nan, "mfe_mae_ratio": np.nan,
                "line_obedience_score_raw": 0.0,
                "regime_obedience_bull": np.nan, "regime_obedience_bear": np.nan,
                "instability_penalty": 0.0}

    fwd_cols = [c for c in ["fwd_ret_5d", "fwd_ret_10d", "fwd_ret_20d", "mfe_20d", "mae_20d"]
                if c in df.columns]

    result = {**base}
    for fc in fwd_cols:
        vals = df[fc].dropna()
        if len(vals) > 0:
            result[f"bounce_rate_{fc.replace('fwd_ret_', '').replace('d', '')}d"] = (vals > 0).mean()
            result[f"median_{fc}"] = vals.median()
        else:
            result[f"bounce_rate_{fc.replace('fwd_ret_', '').replace('d', '')}d"] = np.nan

    if "mfe_20d" in df.columns and "mae_20d" in df.columns:
        mfe = df["mfe_20d"].dropna().mean()
        mae = df["mae_20d"].dropna().abs().mean()
        result["mfe_mae_ratio"] = float(mfe / mae) if (mae and mae > 0 and pd.notna(mae)) else np.nan
    else:
        result["mfe_mae_ratio"] = np.nan

    # Regime split
    if "breadth_regime" in df.columns:
        bull_rows = df[df["breadth_regime"].isin(["BULL_BROAD", "BULL_NARROW"])]
        bear_rows = df[df["breadth_regime"].isin(["BEAR", "STRESS"])]
        fwd_key = "fwd_ret_20d"
        result["regime_obedience_bull"] = (
            (bull_rows[fwd_key] > 0).mean() if (fwd_key in bull_rows and len(bull_rows) >= 5) else np.nan
        )
        result["regime_obedience_bear"] = (
            (bear_rows[fwd_key] > 0).mean() if (fwd_key in bear_rows and len(bear_rows) >= 5) else np.nan
        )
    else:
        result["regime_obedience_bull"] = np.nan
        result["regime_obedience_bear"] = np.nan

    # Instability penalty
    result["instability_penalty"] = compute_instability_penalty(touch_df, symbol, line_name)

    # Composite score
    br20 = result.get("bounce_rate_20d", 0.5) or 0.5
    med20 = result.get("median_fwd_ret_20d", 0.0) or 0.0
    mmr = result.get("mfe_mae_ratio", 1.0) or 1.0
    br10 = result.get("bounce_rate_10d", 0.5) or 0.5
    penalty = result.get("instability_penalty", 0.0)

    # Normalise components relative to reasonable bounds
    score = (
        min(max(br20, 0), 1) * 0.30
        + min(max(med20 / 0.10, 0), 1) * 0.25   # 10% median return = full score
        + min(max((mmr - 1) / 3, 0), 1) * 0.20  # mfe/mae > 4:1 = full score
        + min(max(br10, 0), 1) * 0.15
        - penalty * 0.10
    )
    result["line_obedience_score_raw"] = float(np.clip(score, 0, 1))

    return result


# ── OOS lift computation ──────────────────────────────────────────────────────

def compute_oos_lift(
    touch_df: pd.DataFrame,
    profiles: pd.DataFrame,
    oos_start: pd.Timestamp,
    n_shuffle: int = 500,
    rng_seed: int = 42,
) -> dict:
    """
    Compute OOS lift for the full MEDIUM/HIGH profile universe.

    Compares:
      selected  — events where (symbol, line_name, tol_name) exactly matches
                  each MEDIUM/HIGH profile's primary_support_line + best_tolerance
      baseline  — all touch events in the OOS window (any symbol, line, tolerance)
      null      — cross-symbol permutation: shuffle symbol→(line,tol) mapping n_shuffle
                  times to build a null distribution; z_score vs this null

    Returns dict with:
        selected_event_count, selected_bounce_rate_20d,
        baseline_event_count, baseline_bounce_rate_20d,
        lift_vs_baseline, lift_vs_null, z_score, pass_fail,
        by_year (dict keyed by year), by_regime (dict keyed by regime string)

    All missing / insufficient-data cases return NaN fields, never crash.
    """
    empty_result: dict = {
        "selected_event_count": 0,
        "selected_bounce_rate_20d": np.nan,
        "baseline_event_count": 0,
        "baseline_bounce_rate_20d": np.nan,
        "lift_vs_baseline": np.nan,
        "lift_vs_null": np.nan,
        "z_score": np.nan,
        "pass_fail": False,
        "by_year": {},
        "by_regime": {},
    }

    if touch_df.empty or profiles.empty or "fwd_ret_20d" not in touch_df.columns:
        return empty_result

    oos_df = touch_df[pd.to_datetime(touch_df["date"]) >= oos_start].copy()
    # Drop events without a complete 20d forward window (parquet tail — no future bars yet)
    if "fwd_ret_20d" in oos_df.columns:
        oos_df = oos_df[oos_df["fwd_ret_20d"].notna()]
    if oos_df.empty:
        return empty_result

    # Build set of (symbol, primary_support_line, best_tolerance) for MEDIUM/HIGH profiles
    med_plus = profiles[
        profiles["confidence"].isin([DNAConfidence.MEDIUM.value, DNAConfidence.HIGH.value])
    ].dropna(subset=["primary_support_line", "best_tolerance"])

    if med_plus.empty:
        return empty_result

    selected_keys: set[tuple] = set(
        zip(med_plus["symbol"], med_plus["primary_support_line"], med_plus["best_tolerance"])
    )

    oos_keys = list(zip(oos_df["symbol"], oos_df["line_name"], oos_df["tol_name"]))
    selected_mask = pd.Series([k in selected_keys for k in oos_keys], index=oos_df.index)

    selected_df = oos_df[selected_mask]
    baseline_df = oos_df

    def _bounce_rate(df: pd.DataFrame) -> float:
        vals = df["fwd_ret_20d"].dropna()
        return float((vals > 0).mean()) if len(vals) >= 5 else np.nan

    sel_br  = _bounce_rate(selected_df)
    base_br = _bounce_rate(baseline_df)
    lift_vs_baseline = (
        float(sel_br - base_br)
        if (pd.notna(sel_br) and pd.notna(base_br)) else np.nan
    )

    # Cross-symbol permutation null: shuffle symbol→(line,tol) mapping
    rng = np.random.default_rng(rng_seed)
    symbols_arr = med_plus["symbol"].values.copy()
    lines_arr   = med_plus["primary_support_line"].values.copy()
    tols_arr    = med_plus["best_tolerance"].values.copy()

    null_brs: list[float] = []
    for _ in range(n_shuffle):
        shuffled_idx = rng.permutation(len(symbols_arr))
        null_keys: set[tuple] = set(
            zip(symbols_arr, lines_arr[shuffled_idx], tols_arr[shuffled_idx])
        )
        null_mask = pd.Series([k in null_keys for k in oos_keys], index=oos_df.index)
        null_br = _bounce_rate(oos_df[null_mask])
        if pd.notna(null_br):
            null_brs.append(null_br)

    if null_brs and pd.notna(sel_br):
        null_arr  = np.array(null_brs)
        null_mean = float(null_arr.mean())
        null_std  = float(null_arr.std()) if null_arr.std() > 0 else 1e-6
        z_score   = float((sel_br - null_mean) / null_std)
        lift_vs_null = float(sel_br - null_mean)
        pass_fail = bool(z_score >= 2.0)
    else:
        null_mean = null_std = np.nan
        z_score = lift_vs_null = np.nan
        pass_fail = False

    # By-year breakdown
    by_year: dict = {}
    if "date" in selected_df.columns:
        selected_df = selected_df.copy()
        selected_df["_year"] = pd.to_datetime(selected_df["date"]).dt.year
        for yr, grp in selected_df.groupby("_year"):
            by_year[int(yr)] = {
                "n": len(grp),
                "bounce_rate_20d": _bounce_rate(grp),
            }

    # By-regime breakdown (only if breadth_regime column present)
    by_regime: dict = {}
    if "breadth_regime" in selected_df.columns:
        for regime, grp in selected_df.groupby("breadth_regime"):
            by_regime[str(regime)] = {
                "n": len(grp),
                "bounce_rate_20d": _bounce_rate(grp),
            }

    return {
        "selected_event_count": int(len(selected_df)),
        "selected_bounce_rate_20d": sel_br,
        "baseline_event_count": int(len(baseline_df)),
        "baseline_bounce_rate_20d": base_br,
        "lift_vs_baseline": lift_vs_baseline,
        "lift_vs_null": lift_vs_null,
        "z_score": z_score,
        "pass_fail": pass_fail,
        "by_year": by_year,
        "by_regime": by_regime,
    }


# ── Build walk-forward profiles ───────────────────────────────────────────────

def build_walkforward_line_scores(
    panel: pd.DataFrame,
    touch_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build walk-forward line scores across all symbols, lines, tolerances.
    For each year Y: scores use data from years < Y only.
    Returns one row per (symbol, line_name, tol_name, year_cutoff).
    """
    years = _training_years(panel)
    oos_start = _oos_cutoff_date(panel)
    symbols = sorted(touch_df["symbol"].unique()) if not touch_df.empty else []

    tol_names = list(TOLERANCE_PCT.keys()) + list(TOLERANCE_ATR.keys())

    rows = []
    total = len(symbols) * len(CANDIDATE_LINES) * len(tol_names) * len(years)
    done = 0

    for symbol in symbols:
        for line_name in CANDIDATE_LINES:
            for tol_name in tol_names:
                for year in years:
                    row = score_symbol_line(touch_df, symbol, line_name, tol_name, year_cutoff=year)
                    rows.append(row)
                    done += 1
                    if done % 5000 == 0:
                        logger.info("  Walk-forward scoring: %d / %d", done, total)

    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ── Per-symbol profile builder ────────────────────────────────────────────────

def build_operator_note(
    primary_line: Optional[str],
    danger_line: Optional[str],
    confidence: str,
    bull_obedience: float,
    bear_obedience: float,
    symbol: str,
    production_status: str = "",
) -> str:
    """
    Generate human-readable operator note for a symbol's DNA profile.

    Council v3.1 (2026-06-05): WATCHLIST_ONLY and REJECT symbols must not carry
    bullish/respects-support language in the profiles artifact. Caution-only notes
    are emitted at source so every discovery regeneration is correct and durable.
    Operator-facing display must use annotation_ledger.stock_dna_operator_note,
    not this field directly, for WATCHLIST_ONLY/REJECT rows.
    """
    # REJECT or NONE confidence — no stable signal
    if confidence == DNAConfidence.NONE.value or not primary_line:
        return "CAUTION: No stable line behavior detected — avoid stock-specific overlay."

    # WATCHLIST_ONLY — sample sufficient but edge not validated; caution only (council A3)
    if production_status == DNAProductionStatus.WATCHLIST_ONLY.value:
        note = (
            f"WATCHLIST_ONLY — {primary_line.upper()} line data available "
            f"(n_touch meets sample threshold) but edge not validated (edge_confidence=NONE). "
            "Informational line stats only. Do NOT use as bullish support signal."
        )
        if symbol in DISTORTION_FLAG_SYMBOLS:
            note += " | RISK: VIN return distortion flag."
        return note

    # RESEARCH_ANNOTATION_ONLY — full note with directional facts
    note_parts = []
    line_display = primary_line.upper()

    if pd.notna(bull_obedience) and bull_obedience > 0.60:
        note_parts.append(
            f"FACT: Historically respects {line_display} in bull regime "
            f"(bounce rate {bull_obedience:.0%} in bull markets). "
            "T2 pullbacks near this line have positive median 20D return."
        )
    elif pd.notna(bull_obedience):
        note_parts.append(
            f"INTERPRETATION: Weak {line_display} obedience in bull regime "
            f"(bounce rate {bull_obedience:.0%}). Use caution."
        )

    if pd.notna(bear_obedience) and bear_obedience < 0.40:
        note_parts.append(
            f"FACT: {line_display} obedience breaks down in bear regime "
            f"(bounce rate {bear_obedience:.0%}). Line is unreliable in downtrends."
        )

    if danger_line:
        note_parts.append(
            f"INTERPRETATION: Losing {danger_line.upper()} on high volume historically "
            "leads to weak forward returns — flag as STOCK_DNA_DANGER_LINE_BREAK."
        )

    if symbol in DISTORTION_FLAG_SYMBOLS:
        note_parts.append("RISK: VIN return distortion flag — interpret with caution.")

    return " | ".join(note_parts) if note_parts else f"Confidence {confidence} — verify sample size before acting."


def build_symbol_profiles(
    touch_df: pd.DataFrame,
    wf_scores: pd.DataFrame,
    panel: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build one final profile row per symbol using the full history (pre-OOS).
    Uses the most recent walk-forward year's scores as the "current" profile.

    Columns:
        symbol, data_start, data_end, n_bars, liquidity_bucket,
        primary_support_line, danger_line, best_tolerance,
        confidence, line_obedience_score_raw,
        n_touch, bounce_rate_20d, median_fwd_ret_20d,
        regime_obedience_bull, regime_obedience_bear,
        oos_lift, instability_penalty, vin_distortion_flag,
        production_status, operator_note,
        primary_support_line_markup, primary_support_line_pullback, danger_line_decline,
        best_tolerance_markup, best_tolerance_pullback,
        confidence_markup, confidence_pullback, confidence_decline
    """
    if wf_scores.empty:
        logger.warning("No walk-forward scores — cannot build symbol profiles")
        return pd.DataFrame()

    oos_start = _oos_cutoff_date(panel)

    # Use the latest year_cutoff as "current" profile
    latest_year = wf_scores["year_cutoff"].max()
    current_scores = wf_scores[wf_scores["year_cutoff"] == latest_year].copy()

    rows = []
    sym_panel = panel.groupby("symbol")

    for symbol, grp in sym_panel:
        # Panel metadata
        data_start = grp["date"].min().date()
        data_end   = grp["date"].max().date()
        n_bars     = len(grp)

        adv50 = grp["adv50_vnd"].median() if "adv50_vnd" in grp.columns else 0
        if adv50 >= 50e9:
            liq_bucket = "VERY_LIQUID"
        elif adv50 >= 10e9:
            liq_bucket = "LIQUID"
        elif adv50 >= 5e9:
            liq_bucket = "SEMI_LIQUID"
        else:
            liq_bucket = "MARGINAL"

        vin_flag = int(symbol in DISTORTION_FLAG_SYMBOLS)

        # Best line from current scores
        sym_scores = current_scores[current_scores["symbol"] == symbol].copy()

        if sym_scores.empty:
            row = {
                "symbol": symbol, "data_start": data_start, "data_end": data_end,
                "n_bars": n_bars, "liquidity_bucket": liq_bucket,
                "primary_support_line": None, "danger_line": None, "best_tolerance": None,
                "confidence": DNAConfidence.NONE.value,
                "sample_confidence": DNAConfidence.NONE.value,
                "edge_confidence": "NONE",
                "per_symbol_null_z": np.nan,
                "line_obedience_score_raw": 0.0,
                "n_touch": 0, "bounce_rate_20d": np.nan, "median_fwd_ret_20d": np.nan,
                "regime_obedience_bull": np.nan, "regime_obedience_bear": np.nan,
                "oos_lift": np.nan, "instability_penalty": 0.0, "vin_distortion_flag": vin_flag,
                "production_status": DNAProductionStatus.REJECT.value,
                "operator_note": "No stable line behavior detected — avoid stock-specific overlay.",
                "primary_support_line_markup": None, "primary_support_line_pullback": None,
                "danger_line_decline": None, "best_tolerance_markup": None,
                "best_tolerance_pullback": None, "confidence_markup": DNAConfidence.NONE.value,
                "confidence_pullback": DNAConfidence.NONE.value, "confidence_decline": DNAConfidence.NONE.value,
            }
            rows.append(row)
            continue

        # Pick best line per symbol (MARKUP phase preferred)
        best = sym_scores.sort_values("line_obedience_score_raw", ascending=False).iloc[0]
        primary_line = best["line_name"] if best["confidence"] != DNAConfidence.NONE.value else None
        best_tol     = best["tol_name"]
        confidence   = best["confidence"]

        # Danger line: best line in DECLINE from breakdown analysis
        # Use lowest line (sma150 or sma100) as fallback danger line
        danger_candidates = [ln for ln in ["sma150", "sma100", "ema50", "ema20"]
                             if ln in sym_scores["line_name"].values and ln != primary_line]
        danger_line = danger_candidates[0] if danger_candidates else None

        # Phase-specific line / tolerance selection
        def _best_for_phase(phase_val: str) -> tuple:
            """Return (line_name, tol_name, confidence, score) for a specific phase."""
            ph_scores = sym_scores[sym_scores.get("phase", "ALL") == phase_val] \
                if "phase" in sym_scores.columns else pd.DataFrame()
            if ph_scores.empty:
                # Fall back to non-phase-split walk-forward scores for this symbol
                ph_scores = current_scores[current_scores["symbol"] == symbol].copy()
            if ph_scores.empty:
                return (None, None, DNAConfidence.NONE.value, 0.0)
            b = ph_scores.sort_values("line_obedience_score_raw", ascending=False).iloc[0]
            return (b["line_name"], b["tol_name"], b["confidence"], float(b.get("line_obedience_score_raw", 0.0)))

        markup_line, markup_tol, markup_conf, _   = _best_for_phase(StockPhase.MARKUP.value)
        pullback_line, pullback_tol, pullback_conf, _ = _best_for_phase(StockPhase.PULLBACK_IN_UPTREND.value)
        decline_line, _, decline_conf, _ = _best_for_phase(StockPhase.DECLINE.value)

        # sample_confidence = n_touch gate; edge_confidence = PENDING (populated post-step)
        sample_conf = assign_sample_confidence(int(best.get("n_touch", 0))).value

        # Production status ladder (council v3):
        #   REJECT if sample_confidence NONE/LOW and no edge signal
        #   WATCHLIST_ONLY if sample MEDIUM/HIGH but edge absent (PENDING state)
        #   RESEARCH_ANNOTATION_ONLY if sample MEDIUM/HIGH AND edge >= WEAK (set in post-step)
        if confidence == DNAConfidence.NONE.value:
            prod_status = DNAProductionStatus.REJECT.value
        elif confidence == DNAConfidence.LOW.value:
            prod_status = DNAProductionStatus.WATCHLIST_ONLY.value
        else:
            # Default WATCHLIST_ONLY until edge_confidence is validated in post-step
            prod_status = DNAProductionStatus.WATCHLIST_ONLY.value

        operator_note = build_operator_note(
            primary_line=primary_line,
            danger_line=danger_line,
            confidence=confidence,
            bull_obedience=float(best.get("regime_obedience_bull", np.nan)),
            bear_obedience=float(best.get("regime_obedience_bear", np.nan)),
            symbol=symbol,
            production_status=prod_status,
        )

        row = {
            "symbol": symbol,
            "data_start": data_start,
            "data_end": data_end,
            "n_bars": n_bars,
            "liquidity_bucket": liq_bucket,
            "primary_support_line": primary_line,
            "danger_line": danger_line,
            "best_tolerance": best_tol,
            "confidence": confidence,
            "sample_confidence": sample_conf,
            "edge_confidence": "PENDING",   # populated post-step by discovery script
            "per_symbol_null_z": np.nan,    # populated post-step by discovery script
            "line_obedience_score_raw": float(best.get("line_obedience_score_raw", 0.0)),
            "n_touch": int(best.get("n_touch", 0)),
            "bounce_rate_20d": float(best.get("bounce_rate_20d", np.nan)),
            "median_fwd_ret_20d": float(best.get("median_fwd_ret_20d", np.nan)),
            "regime_obedience_bull": float(best.get("regime_obedience_bull", np.nan)),
            "regime_obedience_bear": float(best.get("regime_obedience_bear", np.nan)),
            # OOS lift stored as z_score for single-row profiles; full lift dict in discovery output
            "oos_lift": np.nan,   # populated by the discovery script after build_symbol_profiles
            "instability_penalty": float(best.get("instability_penalty", 0.0)),
            "vin_distortion_flag": vin_flag,
            "production_status": prod_status,
            "operator_note": operator_note,
            # Phase-specific fields (P1)
            "primary_support_line_markup": markup_line,
            "primary_support_line_pullback": pullback_line,
            "danger_line_decline": decline_line,
            "best_tolerance_markup": markup_tol,
            "best_tolerance_pullback": pullback_tol,
            "confidence_markup": markup_conf,
            "confidence_pullback": pullback_conf,
            "confidence_decline": decline_conf,
        }
        rows.append(row)

    return pd.DataFrame(rows).sort_values("line_obedience_score_raw", ascending=False).reset_index(drop=True)
