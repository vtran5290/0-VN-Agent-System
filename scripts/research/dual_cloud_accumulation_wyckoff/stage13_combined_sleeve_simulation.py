"""Stage 13 — Combined A3/S3 Sleeve Portfolio Simulation.

Tests whether adding a small S3 sleeve to an A3-only portfolio improves
risk-adjusted return (MAR = CAGR / |MaxDD|).

Research design:
- A3 frozen contract simulated fresh from panel data (ex-VIN universe).
- S3 annual returns loaded from Stage 12B by-year output (no re-simulation).
- Portfolio allocations: A3_ONLY + 5 weights × 2 S3 variants = 11 rows.
- Annual-average weighting: combined[Y] = w_A3 × A3[Y] + w_S3 × S3[Y].
- Equity curve, CAGR, MaxDD, MAR computed on combined annual returns.

Safety invariants:
- S3_GATES_A3 = False: S3 regime gate does NOT filter A3 signals.
- S3 P&L tracked completely separately before combination.
- Forbidden classifications: PRODUCTION_CANDIDATE, PAPER_TRADE_PRIMARY.
- A3 production contract parameters are frozen — not modified here.
- `final_action` not touched anywhere in this file.
- OMS / live / DNSE untouched.

OBSERVATION / RESEARCH ONLY.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from scripts.research.dual_cloud_accumulation_wyckoff.panel_utils import (
    COST_BPS,
    MIN_ADV_VND,
    MIN_HISTORY,
    OUT_DIR,
    cloud_signal,
    load_panel,
)
from scripts.research.dual_cloud_accumulation_wyckoff.stage12_s3_shadow_contract_validation import (
    _atr14,
    _simulate_s3_trade,
    _liq_bucket,
    _VIN_SYMBOLS,
)

log = logging.getLogger(__name__)

# ── Safety constants ─────────────────────────────────────────────────────────────
_STAGE13_WRITE_DIR: Path = OUT_DIR

_OMS_SAFE_PATHS: frozenset[str] = frozenset({
    str(REPO / "data" / "decision" / "daily_scan.json"),
    str(REPO / "data" / "decision" / "daily_scan.md"),
    str(REPO / "data" / "decision" / "allocation_plan.json"),
    str(REPO / "data" / "state" / "regime_state.json"),
    str(REPO / "data" / "raw" / "current_positions_derived.json"),
    str(REPO / "data" / "raw" / "current_positions_digest.md"),
})

# ── A3 frozen contract parameters ────────────────────────────────────────────────
A3_FAST        = 20
A3_SLOW        = 100
A3_TP1_PCT     = 0.18     # +18% TP1 target (same as S3 paper-shadow)
A3_TP1_SIZE    = 0.50     # T1 tranche: 50% of position
A3_T2_PULLBACK = 0.04     # T2 fill threshold: ≥4% pullback from T1 entry
A3_T2_WINDOW   = 30       # bars within which T2 fill is checked
A3_TRAIL_MULT  = 2.5      # remainder trailed at 2.5× ATR14 (tighter than S3)
A3_MAX_HOLD    = 250      # hard stop after 250 bars

COST_RT = COST_BPS / 10_000.0  # 40 bps round-trip

# ── S3 integration flag ──────────────────────────────────────────────────────────
# S3 regime gate does NOT gate or suppress A3 signals. A3 is independent.
S3_GATES_A3 = False

# ── S3 variants studied ──────────────────────────────────────────────────────────
# (label, max_hold value from Stage 12B by-year file)
_S3_VARIANTS: List[Tuple[str, int]] = [
    ("S3_MAX60_OFFICIAL_SHADOW",  60),
    ("S3_MAX105_RESEARCH_ONLY",  105),
]

# ── Portfolio weight allocations ─────────────────────────────────────────────────
# (w_a3, w_s3) — must sum to 1.0
_PORTFOLIO_WEIGHTS: List[Tuple[float, float]] = [
    (1.00, 0.00),   # A3-only baseline
    (0.95, 0.05),
    (0.90, 0.10),
    (0.85, 0.15),
    (0.80, 0.20),
]

# ── Forbidden classifications (S3 and combined can never be these) ───────────────
_FORBIDDEN_CLASSIFICATIONS: frozenset[str] = frozenset({
    "PRODUCTION_CANDIDATE",
    "PAPER_TRADE_PRIMARY",
})

# ── Input file (Stage 12B by-year output) ────────────────────────────────────────
_STAGE12B_BY_YEAR = OUT_DIR / "stage12b_s3_maxhold_by_year.csv"


# ── A3 simulation ────────────────────────────────────────────────────────────────

def _simulate_a3_trade_blended(
    signal_bar: int,
    sym_df: pd.DataFrame,
    atr14_arr: np.ndarray,
) -> Optional[dict]:
    """
    Simulate one A3 blended T1/T2 contract.

    T1 (50%): enters at open[signal_bar+1].
      - TP1 = +18% from T1 entry; trail = 2.5×ATR14; max_hold = 250 bars.

    T2 (50%): enters at open[fill_bar+1] if low[fill_bar] <= T1_entry*(1-4%)
      within the first 30 bars after T1 entry.
      - Same TP1/trail; max_hold = remaining bars before signal+1+250.

    Blended return:
      - T2 filled:     0.5 × T1.blended_net + 0.5 × T2.blended_net
      - T2 not filled: T1.blended_net (full weight on T1 only)

    Returns None if entry bar out of range.
    Returns dict with matured=False if bars exhausted before max_hold.
    """
    n = len(sym_df)
    entry_bar = signal_bar + 1
    if entry_bar >= n:
        return None

    open_arr = sym_df["open"].values
    low_arr  = sym_df["low"].values

    t1_entry = open_arr[entry_bar]
    if t1_entry <= 0 or np.isnan(t1_entry):
        return None

    # ATR at signal bar — fallback 2% of entry if missing
    missing_atr_flag = False
    atr_val = atr14_arr[signal_bar] if signal_bar < len(atr14_arr) else np.nan
    if np.isnan(atr_val) or atr_val <= 0:
        missing_atr_flag = True
        atr_val = t1_entry * 0.02

    # T1 simulation via _simulate_s3_trade (entry = open[signal_bar+1])
    t1 = _simulate_s3_trade(
        signal_bar, sym_df, atr14_arr,
        tp1_pct=A3_TP1_PCT, tp1_size=A3_TP1_SIZE,
        trail_mult=A3_TRAIL_MULT, max_hold=A3_MAX_HOLD,
        cost_rt=COST_RT,
    )
    if t1 is None:
        return None

    # T2 fill detection: scan bars 1..A3_T2_WINDOW from entry_bar
    t2_thresh   = t1_entry * (1.0 - A3_T2_PULLBACK)
    t2_fill_bar = None
    for i in range(1, A3_T2_WINDOW + 1):
        bar = entry_bar + i
        if bar >= n:
            break
        if low_arr[bar] <= t2_thresh:
            t2_fill_bar = bar
            break

    t2_filled = t2_fill_bar is not None
    t2_net    = np.nan
    t2_tp1_hit = False

    if t2_filled:
        # T2 enters at open[t2_fill_bar + 1]
        t2_signal_bar = t2_fill_bar
        # Remaining bars from T2 entry before A3_MAX_HOLD expires
        bars_used     = (t2_fill_bar + 1) - entry_bar   # bars consumed by T2 fill
        t2_max_hold   = A3_MAX_HOLD - bars_used
        if t2_max_hold > 0:
            t2 = _simulate_s3_trade(
                t2_signal_bar, sym_df, atr14_arr,
                tp1_pct=A3_TP1_PCT, tp1_size=A3_TP1_SIZE,
                trail_mult=A3_TRAIL_MULT, max_hold=t2_max_hold,
                cost_rt=COST_RT,
            )
            if t2 is not None:
                t2_net     = t2.get("blended_net_return", np.nan)
                t2_tp1_hit = bool(t2.get("tp1_hit", False))

    t1_net = t1.get("blended_net_return", np.nan)

    # Blended A3 return
    if t2_filled and not np.isnan(t2_net):
        blended_net = 0.5 * t1_net + 0.5 * t2_net
    else:
        blended_net = t1_net

    return {
        "t1_entry":          float(t1_entry),
        "t2_filled":         t2_filled,
        "t2_entry":          float(open_arr[t2_fill_bar + 1]) if (t2_filled and t2_fill_bar + 1 < n) else np.nan,
        "t1_tp1_hit":        bool(t1.get("tp1_hit", False)),
        "t2_tp1_hit":        t2_tp1_hit,
        "t1_exit_bar_offset": t1.get("exit_bar_offset"),
        "t1_net":            float(t1_net) if not np.isnan(t1_net) else np.nan,
        "t2_net":            float(t2_net) if not np.isnan(t2_net) else np.nan,
        "blended_net_return": float(blended_net) if not np.isnan(blended_net) else np.nan,
        "missing_atr_flag":  missing_atr_flag,
        "matured":           bool(t1.get("matured", False)),
    }


# ── A3 trade collection ───────────────────────────────────────────────────────────

def _collect_a3_trades(panels: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Collect A3 signals from ex-VIN panel, simulate blended T1/T2 contracts.

    Returns DataFrame with one row per A3 signal (ADV-gated, post-warmup).
    """
    rows: List[dict] = []

    for sym, df in panels.items():
        n = len(df)
        if n < MIN_HISTORY + A3_SLOW + 5:
            continue

        sig, _, _ = cloud_signal(df, A3_FAST, A3_SLOW)
        adv50_arr = df["adv50"].values if "adv50" in df.columns else np.full(n, np.nan)
        atr14_arr = _atr14(df).values
        date_arr  = df["date"].values
        is_vin    = sym in _VIN_SYMBOLS

        for bar in np.where(sig.values)[0]:
            adv50 = float(adv50_arr[bar]) if bar < len(adv50_arr) else np.nan
            if np.isnan(adv50) or adv50 < MIN_ADV_VND:
                continue

            res = _simulate_a3_trade_blended(int(bar), df, atr14_arr)
            if res is None:
                continue

            signal_date = pd.Timestamp(date_arr[bar])
            rows.append({
                "symbol":            sym,
                "signal_date":       signal_date,
                "year":              signal_date.year,
                "signal_bar_idx":    int(bar),
                "adv50":             adv50,
                "liquidity_bucket":  _liq_bucket(adv50),
                "is_vin":            is_vin,
                **res,
            })

    return pd.DataFrame(rows)


# ── S3 annual returns from Stage 12B output ───────────────────────────────────────

def _load_s3_annual_returns(max_hold: int) -> Dict[int, float]:
    """
    Load S3 average net return by year from stage12b_s3_maxhold_by_year.csv.
    Filters to the given max_hold value.
    Returns {year: avg_net_return}.
    """
    if not _STAGE12B_BY_YEAR.exists():
        log.warning("Stage 12B by-year file not found: %s", _STAGE12B_BY_YEAR)
        return {}

    df = pd.read_csv(_STAGE12B_BY_YEAR)
    sub = df[df["max_hold"] == max_hold]
    if sub.empty:
        log.warning("No rows in Stage 12B by-year for max_hold=%d", max_hold)
        return {}

    result: Dict[int, float] = {}
    for _, row in sub.iterrows():
        yr = int(row["year"])
        r  = float(row["avg_net_return"])
        if not np.isnan(r):
            result[yr] = r
    return result


# ── Annual return computation ─────────────────────────────────────────────────────

def _a3_annual_returns(trades: pd.DataFrame) -> Dict[int, float]:
    """Average blended_net_return by year for matured A3 trades."""
    result: Dict[int, float] = {}
    if trades.empty or "blended_net_return" not in trades.columns:
        return result
    mat = trades[trades["matured"].fillna(False)].copy()
    for yr, grp in mat.groupby("year"):
        valid = grp["blended_net_return"].dropna()
        if len(valid) > 0:
            result[int(yr)] = float(valid.mean())
    return result


# ── Equity curve stats ────────────────────────────────────────────────────────────

def _equity_stats(annual_returns: Dict[int, float]) -> dict:
    """
    CAGR, MaxDD, MAR from year-level average returns dict.
    Uses same annual-average methodology as Stage 12B.
    """
    empty = {"cagr": np.nan, "max_drawdown": np.nan, "mar": np.nan, "n_years": 0}
    if not annual_returns:
        return empty

    years   = sorted(annual_returns.keys())
    yr_rets = np.array([annual_returns[y] for y in years])
    n       = len(yr_rets)

    equity = np.cumprod(1.0 + np.clip(yr_rets, -0.999, 10.0))
    peak   = np.maximum.accumulate(equity)
    max_dd = float(((equity - peak) / peak).min())

    cagr   = float(equity[-1] ** (1.0 / n) - 1.0) if n > 0 else np.nan
    mar    = float(cagr / abs(max_dd)) if (not np.isnan(cagr) and max_dd < -1e-6) else np.nan

    return {"cagr": cagr, "max_drawdown": max_dd, "mar": mar, "n_years": n}


# ── Combined portfolio returns ────────────────────────────────────────────────────

def _combined_annual_returns(
    a3_returns: Dict[int, float],
    s3_returns: Dict[int, float],
    w_a3: float,
    w_s3: float,
) -> Dict[int, float]:
    """
    Combine A3 and S3 annual returns with given weights.
    Only includes years present in BOTH dicts.
    """
    overlap_years = sorted(set(a3_returns.keys()) & set(s3_returns.keys()))
    return {
        y: w_a3 * a3_returns[y] + w_s3 * s3_returns[y]
        for y in overlap_years
    }


# ── Correlation ──────────────────────────────────────────────────────────────────

def _pearson_correlation(
    a3_returns: Dict[int, float],
    s3_returns: Dict[int, float],
) -> Tuple[float, float, int]:
    """Pearson correlation of overlapping annual returns. Returns (r, p_value, n_overlap)."""
    years = sorted(set(a3_returns.keys()) & set(s3_returns.keys()))
    if len(years) < 3:
        return np.nan, np.nan, len(years)
    a3_arr = np.array([a3_returns[y] for y in years])
    s3_arr = np.array([s3_returns[y] for y in years])
    r, p   = scipy_stats.pearsonr(a3_arr, s3_arr)
    return float(r), float(p), len(years)


# ── Sleeve classification ─────────────────────────────────────────────────────────

def _classify_sleeve(
    combined_mar: float,
    a3_mar: float,
    n_overlap_years: int,
) -> Tuple[str, str]:
    """
    Returns (classification, action) for one sleeve configuration.

    Forbidden: PRODUCTION_CANDIDATE, PAPER_TRADE_PRIMARY (enforced by _FORBIDDEN_CLASSIFICATIONS).
    """
    if n_overlap_years < 5:
        return "NEEDS_MORE_DATA", "fewer than 5 overlapping years"

    if np.isnan(combined_mar) or np.isnan(a3_mar):
        return "NEEDS_MORE_DATA", "insufficient data for MAR comparison"

    # Relative improvement threshold: 5% of |a3_mar|
    threshold = 0.05 * abs(a3_mar) if a3_mar != 0 else 0.05

    if combined_mar >= a3_mar + threshold and combined_mar >= 0.30:
        return "IMPROVEMENT_CANDIDATE", "combined MAR ≥ A3-only + 5% and ≥ 0.30 — research-only"

    if combined_mar <= a3_mar - threshold:
        return "DILUTES_A3", "combined MAR < A3-only − 5% — S3 sleeve dilutes A3"

    return "NEUTRAL_SLEEVE", "combined MAR within ±5% of A3-only — negligible effect"


# ── Portfolio evaluation ──────────────────────────────────────────────────────────

def _evaluate_portfolios(
    a3_returns: Dict[int, float],
    s3_variants_returns: Dict[str, Dict[int, float]],
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Evaluate all portfolio configurations.

    Returns:
      - summary_df: one row per (s3_variant, w_a3) configuration
      - by_year_df: one row per (portfolio_label, year)
      - classification_df: classification per sleeve configuration
    """
    a3_stats    = _equity_stats(a3_returns)
    a3_mar      = a3_stats.get("mar", np.nan)
    a3_cagr     = a3_stats.get("cagr", np.nan)
    a3_maxdd    = a3_stats.get("max_drawdown", np.nan)
    a3_n_years  = a3_stats.get("n_years", 0)

    summary_rows: List[dict] = []
    by_year_rows: List[dict] = []
    cls_rows:     List[dict] = []

    for s3_label, s3_returns in s3_variants_returns.items():
        s3_stats   = _equity_stats(s3_returns)
        r, p_val, n_overlap = _pearson_correlation(a3_returns, s3_returns)

        for w_a3, w_s3 in _PORTFOLIO_WEIGHTS:
            if w_s3 == 0.0:
                # A3-only row — no S3 mixing
                portfolio_label = "A3_ONLY"
                combined_rets   = {y: a3_returns[y] for y in a3_returns}
                combined_stats  = a3_stats
                n_ov            = a3_n_years
            else:
                portfolio_label = f"A3_{int(w_a3*100)}__{s3_label}_{int(w_s3*100)}"
                combined_rets   = _combined_annual_returns(a3_returns, s3_returns, w_a3, w_s3)
                combined_stats  = _equity_stats(combined_rets)
                n_ov            = n_overlap

            combined_mar   = combined_stats.get("mar",          np.nan)
            combined_cagr  = combined_stats.get("cagr",         np.nan)
            combined_maxdd = combined_stats.get("max_drawdown",  np.nan)

            cls, action = _classify_sleeve(combined_mar, a3_mar, n_ov)
            assert cls not in _FORBIDDEN_CLASSIFICATIONS, (
                f"_classify_sleeve returned forbidden classification {cls!r}"
            )

            summary_rows.append({
                "portfolio":          portfolio_label,
                "s3_variant":         s3_label if w_s3 > 0 else "—",
                "w_a3":               w_a3,
                "w_s3":               w_s3,
                "n_a3_years":         a3_n_years,
                "n_s3_years":         s3_stats.get("n_years", 0),
                "n_overlap_years":    n_ov,
                "a3_cagr":            a3_cagr,
                "s3_cagr":            s3_stats.get("cagr", np.nan) if w_s3 > 0 else np.nan,
                "combined_cagr":      combined_cagr,
                "a3_maxdd":           a3_maxdd,
                "s3_maxdd":           s3_stats.get("max_drawdown", np.nan) if w_s3 > 0 else np.nan,
                "combined_maxdd":     combined_maxdd,
                "a3_mar":             a3_mar,
                "s3_mar":             s3_stats.get("mar", np.nan) if w_s3 > 0 else np.nan,
                "combined_mar":       combined_mar,
                "a3_s3_correlation":  r if w_s3 > 0 else np.nan,
                "classification":     cls,
                "action":             action,
            })

            for yr, ret in combined_rets.items():
                by_year_rows.append({
                    "portfolio":     portfolio_label,
                    "s3_variant":    s3_label if w_s3 > 0 else "—",
                    "w_a3":          w_a3,
                    "w_s3":          w_s3,
                    "year":          yr,
                    "a3_return":     a3_returns.get(yr, np.nan),
                    "s3_return":     s3_returns.get(yr, np.nan) if w_s3 > 0 else np.nan,
                    "combined_return": ret,
                })

            if w_s3 > 0:
                cls_rows.append({
                    "s3_variant":       s3_label,
                    "w_a3":             w_a3,
                    "w_s3":             w_s3,
                    "combined_mar":     combined_mar,
                    "a3_mar":           a3_mar,
                    "mar_delta_pp":     (combined_mar - a3_mar) * 100 if not (np.isnan(combined_mar) or np.isnan(a3_mar)) else np.nan,
                    "n_overlap_years":  n_ov,
                    "classification":   cls,
                    "action":           action,
                })

    # Deduplicate A3_ONLY across S3 variants — keep just one
    summary_df = pd.DataFrame(summary_rows)
    if not summary_df.empty:
        a3_only_seen = False
        dedup_rows = []
        for _, r in summary_df.iterrows():
            if r["portfolio"] == "A3_ONLY":
                if a3_only_seen:
                    continue
                a3_only_seen = True
            dedup_rows.append(r.to_dict())
        summary_df = pd.DataFrame(dedup_rows)

    return summary_df, pd.DataFrame(by_year_rows), pd.DataFrame(cls_rows)


# ── Correlation table ────────────────────────────────────────────────────────────

def _build_correlation_table(
    a3_returns: Dict[int, float],
    s3_variants_returns: Dict[str, Dict[int, float]],
) -> pd.DataFrame:
    rows = []
    for s3_label, s3_returns in s3_variants_returns.items():
        r, p_val, n_ov = _pearson_correlation(a3_returns, s3_returns)
        rows.append({
            "s3_variant":             s3_label,
            "n_overlap_years":        n_ov,
            "pearson_correlation":    r,
            "p_value":                p_val,
            "diversification_benefit": (not np.isnan(r)) and r < 0.5,
        })
    return pd.DataFrame(rows)


# ── Findings markdown ─────────────────────────────────────────────────────────────

def _generate_findings_md(
    summary_df: pd.DataFrame,
    cls_df: pd.DataFrame,
    corr_df: pd.DataFrame,
    n_a3_trades: int,
    a3_n_years: int,
) -> str:
    def _fmt(v, pct=False, dp=1):
        if isinstance(v, float) and np.isnan(v):
            return "—"
        if pct:
            return f"{v * 100:.{dp}f}%"
        return f"{v:.{dp}f}"

    lines = [
        "# Stage 13 — Combined A3/S3 Sleeve Portfolio Simulation",
        "",
        "## 1. Executive Summary",
        "",
        f"A3 simulated trades: {n_a3_trades} signals (ex-VIN, ADV ≥ 2B VND, matured only for returns)",
        f"A3 year span: {a3_n_years} calendar years",
        "",
        "S3 annual returns sourced from Stage 12B `stage12b_s3_maxhold_by_year.csv`.",
        "",
        "**Research question:** Does a small S3 sleeve (5%–20%) improve A3 portfolio MAR?",
        "",
        "**Guardrails:**",
        "- S3_GATES_A3 = False — S3 does not gate A3 signals.",
        "- S3 P&L tracked completely separately before combination.",
        f"- Forbidden classifications: {sorted(_FORBIDDEN_CLASSIFICATIONS)}",
        "",
        "## 2. A3 Contract Parameters",
        "",
        f"- Signal: EMA{A3_FAST}/{A3_SLOW} cloud transition (ex-VIN, ADV ≥ 2B)",
        f"- T1 (50%): entry = open[t+1], TP1 = +{A3_TP1_PCT*100:.0f}%, trail = {A3_TRAIL_MULT}×ATR14, max_hold = {A3_MAX_HOLD}",
        f"- T2 (50%): fills when low ≤ T1_entry × (1 − {A3_T2_PULLBACK*100:.0f}%) within {A3_T2_WINDOW} bars",
        "",
        "## 3. Portfolio Summary",
        "",
    ]

    if not summary_df.empty:
        display_cols = [
            "portfolio", "w_a3", "w_s3", "n_overlap_years",
            "a3_cagr", "s3_cagr", "combined_cagr",
            "a3_maxdd", "combined_maxdd",
            "a3_mar", "s3_mar", "combined_mar",
            "classification",
        ]
        dc = [c for c in display_cols if c in summary_df.columns]
        lines.append(summary_df[dc].to_markdown(index=False, floatfmt=".3f"))
    else:
        lines.append("_No portfolio data._")
    lines.append("")

    lines += ["## 4. A3 vs S3 Annual Return Correlation", ""]
    if not corr_df.empty:
        lines.append(corr_df.to_markdown(index=False, floatfmt=".3f"))
        for _, row in corr_df.iterrows():
            r = row.get("pearson_correlation", np.nan)
            benefit = row.get("diversification_benefit", False)
            if not np.isnan(r):
                lines.append(
                    f"\n**{row['s3_variant']}**: correlation = {r:.3f} — "
                    + ("diversification benefit present (r < 0.5)." if benefit
                       else "high correlation — limited diversification benefit (r ≥ 0.5).")
                )
    else:
        lines.append("_No correlation data._")
    lines.append("")

    lines += ["## 5. Sleeve Classification", ""]
    if not cls_df.empty:
        dc = ["s3_variant", "w_s3", "combined_mar", "a3_mar", "mar_delta_pp",
              "n_overlap_years", "classification", "action"]
        dc = [c for c in dc if c in cls_df.columns]
        lines.append(cls_df[dc].to_markdown(index=False, floatfmt=".3f"))
    else:
        lines.append("_No sleeve classification data._")
    lines.append("")

    lines += [
        "## 6. Safety Confirmation",
        "",
        "- **S3_GATES_A3 = False** — S3 regime does not filter A3 signals. ✓",
        "- **A3 production contract parameters unchanged.** ✓",
        "- **S3 P&L tracked completely separately.** ✓",
        "- No PRODUCTION_CANDIDATE or PAPER_TRADE_PRIMARY classification made. ✓",
        "- No modification to OMS / live / DNSE. ✓",
        "- `final_action` not modified. ✓",
        "",
        "## 7. Limitations",
        "",
        "- Annual-average return conflates diversified multi-stock portfolio with individual trades.",
        "- S3 annual returns from Stage 12B use ALL signals (BASE_REGIME + ADV ≥ 2B) — "
          "not filtered to only co-occur with A3 signals.",
        "- T2 fill assumes intraday execution at bar's open (gap risk not modeled for T2).",
        "- Correlation computed on overlapping years only — sample size limited.",
        "",
        "## 8. Recommended Next Step",
        "",
    ]

    if not cls_df.empty:
        improvements = cls_df[cls_df["classification"] == "IMPROVEMENT_CANDIDATE"]
        if not improvements.empty:
            lines += [
                "At least one sleeve configuration shows IMPROVEMENT_CANDIDATE classification.",
                "Next step: run 12-month live paper validation to confirm out-of-sample MAR improvement.",
                "Do NOT add S3 sleeve to A3 production portfolio without separate approval.",
            ]
        elif (cls_df["classification"] == "DILUTES_A3").any():
            lines += [
                "S3 sleeve dilutes A3 MAR in some configurations. No further action recommended.",
                "Re-evaluate if S3 base performance improves over next 12 months of live paper trading.",
            ]
        else:
            lines += [
                "All sleeve configurations are NEUTRAL — no material MAR improvement or dilution.",
                "Continue monitoring S3 live paper performance before reconsidering.",
            ]
    else:
        lines.append("_Insufficient data to recommend next step._")

    lines.append("")
    return "\n".join(lines)


# ── Main entry point ──────────────────────────────────────────────────────────────

def run(workers: int = 4) -> None:
    _STAGE13_WRITE_DIR.mkdir(parents=True, exist_ok=True)

    # Load panel (ex-VIN for A3)
    log.info("Loading panel (ex-VIN) for A3 simulation...")
    panels = load_panel(ex_vin=True)
    for sym in panels:
        panels[sym] = panels[sym].sort_values("date").reset_index(drop=True)
    log.info("Panel: %d symbols", len(panels))

    # Collect A3 trades
    log.info("Collecting A3 signals and simulating blended T1/T2 contracts...")
    a3_trades = _collect_a3_trades(panels)
    log.info("A3 trades: %d signals, %d matured",
             len(a3_trades),
             int(a3_trades["matured"].sum()) if not a3_trades.empty else 0)

    # Save A3 trades
    out_a3 = _STAGE13_WRITE_DIR / "stage13_a3_trades.csv"
    a3_trades.to_csv(out_a3, index=False)
    log.info("Saved: %s (%d rows)", out_a3.name, len(a3_trades))

    # A3 annual returns
    a3_returns = _a3_annual_returns(a3_trades)
    a3_stats   = _equity_stats(a3_returns)
    log.info(
        "A3 stats: %d years  CAGR=%.1f%%  MaxDD=%.1f%%  MAR=%.2f",
        a3_stats.get("n_years", 0),
        100 * (a3_stats.get("cagr") or 0),
        100 * (a3_stats.get("max_drawdown") or 0),
        a3_stats.get("mar") or 0,
    )

    # Load S3 annual returns for each variant
    s3_variants_returns: Dict[str, Dict[int, float]] = {}
    for s3_label, mh in _S3_VARIANTS:
        yr_ret = _load_s3_annual_returns(mh)
        s3_variants_returns[s3_label] = yr_ret
        s3_st = _equity_stats(yr_ret)
        log.info("S3 %s (mh=%d): %d years  CAGR=%.1f%%  MaxDD=%.1f%%  MAR=%.2f",
                 s3_label, mh, s3_st.get("n_years", 0),
                 100 * (s3_st.get("cagr") or 0),
                 100 * (s3_st.get("max_drawdown") or 0),
                 s3_st.get("mar") or 0)

    # Portfolio evaluation
    log.info("Evaluating portfolio configurations...")
    summary_df, by_year_df, cls_df = _evaluate_portfolios(a3_returns, s3_variants_returns)

    # Correlation table
    corr_df = _build_correlation_table(a3_returns, s3_variants_returns)

    # Save outputs
    out_summary = _STAGE13_WRITE_DIR / "stage13_portfolio_summary.csv"
    summary_df.to_csv(out_summary, index=False)
    log.info("Saved: %s (%d rows)", out_summary.name, len(summary_df))

    out_year = _STAGE13_WRITE_DIR / "stage13_portfolio_by_year.csv"
    by_year_df.to_csv(out_year, index=False)
    log.info("Saved: %s (%d rows)", out_year.name, len(by_year_df))

    out_corr = _STAGE13_WRITE_DIR / "stage13_a3_s3_correlation.csv"
    corr_df.to_csv(out_corr, index=False)
    log.info("Saved: %s (%d rows)", out_corr.name, len(corr_df))

    out_cls = _STAGE13_WRITE_DIR / "stage13_sleeve_classification.csv"
    cls_df.to_csv(out_cls, index=False)
    log.info("Saved: %s (%d rows)", out_cls.name, len(cls_df))

    # Findings markdown
    findings_md = _generate_findings_md(
        summary_df   = summary_df,
        cls_df       = cls_df,
        corr_df      = corr_df,
        n_a3_trades  = len(a3_trades),
        a3_n_years   = a3_stats.get("n_years", 0),
    )
    out_md = _STAGE13_WRITE_DIR / "STAGE13_COMBINED_SLEEVE_FINDINGS.md"
    out_md.write_text(findings_md, encoding="utf-8")
    log.info("Saved: %s", out_md.name)

    log.info("Stage 13 complete.")


if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
