#!/usr/bin/env python3
"""
Phase36 A3/S3 Coordination Research.

Sub-phases:
  A - State taxonomy (signal co-occurrence)
  B - Ranking tests (a3_rank_score variants)
  C - Sizing overlay (lead-bucket size multipliers)
  D - T2 policy (S3-conditional T2)
  E - Exit overlay (trail tightening for non-leads)
  F - Satellite sleeve (A3+S3 blended portfolio)
  G - Risk warning (S3 shadow DD vs A3 regime)
  H - Interaction matrix (summary of all variants)

Non-negotiables:
  - A3 production logic: EMA20/100, TP=18%, trail=2.5×ATR, max_hold=250
  - S3 never real capital
  - Coordination accepted only if MAR improvement >= +0.03
  - Corrected liquidity: ADV50_VND = close_kVND × volume × 1000
  - Cost = 40bps round-trip

A3 baseline: MAR=0.416, CAGR=5.81%, MaxDD=-13.99%  (5B VND, 10% participation)

Usage:
  .venv\\Scripts\\python.exe pp_backtest/phase36_coordination_research.py --phase all
  .venv\\Scripts\\python.exe pp_backtest/phase36_coordination_research.py --phase a
  .venv\\Scripts\\python.exe pp_backtest/phase36_coordination_research.py --phase b
"""
from __future__ import annotations

import argparse
import sys
import textwrap
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pp_backtest.portfolio_optimization_phase1 import (
    _build_signal_cache, _exit_tp_trail,
    load_panel, load_vnindex, get_universe,
    DEFAULT_COST, EXCLUDE_VIN3,
)
from pp_backtest.portfolio_optimization_phase31 import (
    _build_adv50_map, _tag_adv50, _build_equity_adv_capped_v2, _annual_return,
)
from pp_backtest.s3_upgrade_research import (
    _regime_gate_100, _build_trades, _metrics, _tp_rate,
)
from pp_backtest.ema_portfolio_sim import portfolio_metrics

OUT = REPO / "data" / "research" / "portfolio_optimization" / "missing_work"
OUT.mkdir(parents=True, exist_ok=True)

# ── Constants ─────────────────────────────────────────────────────────────────
PORTFOLIO_VND = 5e9
MAX_SLOTS     = 20
PARTICIPATION = 0.10
COST          = DEFAULT_COST        # 0.004 = 40bps round-trip
ANN           = 252
MIN_LOCK      = 5

EXIT_A3 = {"tp_pct": 0.18, "tp_frac": 0.50, "trail_mult": 2.5, "max_hold": 250}
EXIT_S3 = {"tp_pct": 0.18, "tp_frac": 0.50, "trail_mult": 3.5, "max_hold": 60}

A3_BASELINE_MAR  = 0.416
A3_BASELINE_CAGR = 0.0581
A3_BASELINE_DD   = -0.1399
MAR_THRESHOLD    = A3_BASELINE_MAR + 0.03   # acceptance bar

BAD_YEARS  = [2018, 2022]
BULL_YEARS = [2020, 2021, 2025]
KEY_YEARS  = list(range(2014, 2027))

# Lead bucket definitions (business-day buckets, Phase35+36)
BUCKET_ORDER = ["same_bar_0", "lead_1_5", "lead_6_10", "lead_11_20", "lead_21_30", "no_s3_lead"]
QUALITY_BOOST = {
    "same_bar_0": -0.5,
    "lead_1_5":    0.0,
    "lead_6_10":   0.0,
    "lead_11_20": +2.0,
    "lead_21_30": +1.0,
    "no_s3_lead":  0.0,
}


# ── Lead bucket helpers ───────────────────────────────────────────────────────

def _bday_count(d1: pd.Timestamp, d2: pd.Timestamp) -> int:
    """Business-day count from d1 to d2."""
    if d1 == d2:
        return 0
    try:
        return max(0, int(np.busday_count(d1.date(), d2.date())))
    except Exception:
        return max(0, int((d2 - d1).days * 5 // 7))


def assign_lead_bucket(bars) -> str:
    if bars is None or (isinstance(bars, float) and np.isnan(bars)):
        return "no_s3_lead"
    b = int(bars)
    if b == 0:           return "same_bar_0"
    elif b <= 5:         return "lead_1_5"
    elif b <= 10:        return "lead_6_10"
    elif b <= 20:        return "lead_11_20"
    elif b <= 30:        return "lead_21_30"
    else:                return "no_s3_lead"


def ed_score(ema_dist_pct: float) -> float:
    """Proximity score: 1.0 at EMA (dist=0), decays to 0 at 20% away."""
    return max(0.0, 1.0 - abs(ema_dist_pct) / 0.20)


def quality_boost(bucket: str) -> float:
    return QUALITY_BOOST.get(bucket, 0.0)


def a3_rank_score(bucket: str, ema_dist_pct: float) -> float:
    return quality_boost(bucket) + ed_score(ema_dist_pct)


def tag_lead_info(
    a3_trades: pd.DataFrame,
    s3_cache: dict,
    lookback_bdays: int = 35,
) -> pd.DataFrame:
    """
    Tag each A3 trade with S3 lead information.
    Adds: s3_last_sig_date, s3_lead_bdays, s3_lead_bucket, a3_rank_score.
    """
    s3_sigs: dict[str, list[pd.Timestamp]] = {}
    for sym, data in s3_cache.items():
        s3_sigs[sym] = sorted(
            pd.Timestamp(data["dates"][k]).normalize()
            for k in data["sig_idxs"]
        )

    df = a3_trades.copy()
    df["signal_date"] = pd.to_datetime(df["signal_date"]).dt.normalize()

    lead_dates, lead_bdays_col, buckets, rank_scores = [], [], [], []

    for _, row in df.iterrows():
        sym      = row["symbol"]
        sig_date = row["signal_date"]
        s3_dates = s3_sigs.get(sym, [])

        best_lag  = None
        best_date = None
        for sd in reversed(s3_dates):
            if sd > sig_date:
                continue
            lag = _bday_count(sd, sig_date)
            if lag > lookback_bdays:
                break
            if best_lag is None or lag < best_lag:
                best_lag  = lag
                best_date = sd

        bucket = assign_lead_bucket(best_lag)
        ed     = ed_score(float(row.get("ema_dist_at_entry", 0.0)))

        lead_dates.append(best_date)
        lead_bdays_col.append(best_lag if best_lag is not None else np.nan)
        buckets.append(bucket)
        rank_scores.append(a3_rank_score(bucket, float(row.get("ema_dist_at_entry", 0.0))))

    df["s3_last_sig_date"] = lead_dates
    df["s3_lead_bdays"]    = lead_bdays_col
    df["s3_lead_bucket"]   = buckets
    df["a3_rank_score"]    = rank_scores
    df["ed_score"]         = [ed_score(float(r)) for r in df["ema_dist_at_entry"].fillna(0)]
    df["lead_11_20_flag"]  = df["s3_lead_bucket"].isin(["lead_11_20", "lead_21_30"])
    df["chase_flag"]       = df["s3_lead_bucket"] == "same_bar_0"
    return df


def _run_equity(trades_df: pd.DataFrame, adv50_map: dict,
                rank_col: str = "ema_dist_at_entry",
                gk_mult: float = 1.0,
                gk_col: str = "has_gk") -> dict:
    """Tag ADV, simulate equity, return metrics dict with annual returns."""
    if trades_df.empty:
        return {}
    df = _tag_adv50(trades_df, adv50_map) if (
        "adv50_value" not in trades_df.columns
        or (trades_df["adv50_value"].fillna(0) == 0).all()
    ) else trades_df.copy()

    eq, _ = _build_equity_adv_capped_v2(
        df, MAX_SLOTS, PORTFOLIO_VND, PARTICIPATION,
        gk_mult=gk_mult, gk_col=gk_col,
        rank_col=rank_col,
    )
    if eq.empty:
        return {}
    m = portfolio_metrics(eq, df[df["net_return"].notna()])
    for yr in KEY_YEARS:
        m[f"yr_{yr}"] = _annual_return(eq, yr)
    return m


def _fmt(v, pct=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "N/A"
    return f"{v:.2%}" if pct else f"{v:.4f}"


def _metric_row(label: str, m: dict) -> dict:
    """Flatten a metrics dict to a results row."""
    r = {
        "variant":   label,
        "mar":       round(m.get("mar",    np.nan), 4),
        "cagr":      round(m.get("cagr",   np.nan), 4),
        "max_dd":    round(m.get("max_dd", np.nan), 4),
        "sharpe":    round(m.get("sharpe", np.nan), 4),
        "n_trades":  int(m.get("n_trades", 0)),
        "mar_vs_baseline": round(m.get("mar", np.nan) - A3_BASELINE_MAR, 4),
    }
    for yr in KEY_YEARS:
        r[f"yr_{yr}"] = round(m.get(f"yr_{yr}", np.nan), 4)
    return r


# ── Phase36A: State taxonomy ─────────────────────────────────────────────────

def run_phase_a(a3_cache: dict, s3_cache: dict, regime: pd.Series) -> None:
    print("\n=== PHASE36A: State Taxonomy ===", flush=True)

    # Build signal date sets for each strategy
    a3_sigs: dict[str, list[pd.Timestamp]] = {}
    s3_sigs: dict[str, list[pd.Timestamp]] = {}
    for sym, data in a3_cache.items():
        a3_sigs[sym] = [pd.Timestamp(data["dates"][k]).normalize() for k in data["sig_idxs"]]
    for sym, data in s3_cache.items():
        s3_sigs[sym] = [pd.Timestamp(data["dates"][k]).normalize() for k in data["sig_idxs"]]

    all_syms = sorted(set(a3_sigs) | set(s3_sigs))
    rows = []

    for sym in all_syms:
        a3_dates = set(a3_sigs.get(sym, []))
        s3_dates = set(s3_sigs.get(sym, []))
        dual     = a3_dates & s3_dates

        # S3 signals preceding A3 within 30 bdays
        s3_d_list  = sorted(s3_sigs.get(sym, []))
        a3_leads   = []
        for a3d in sorted(a3_dates):
            if not bool(regime.get(a3d, True)):
                continue
            lag = None
            for sd in reversed(s3_d_list):
                if sd > a3d:
                    continue
                b = _bday_count(sd, a3d)
                if b > 35:
                    break
                if b > 0:
                    lag = b
                    break
            a3_leads.append((a3d, lag))

        lead_buckets: dict[str, int] = {b: 0 for b in BUCKET_ORDER}
        for _, lag in a3_leads:
            lead_buckets[assign_lead_bucket(lag)] += 1

        rows.append({
            "symbol":         sym,
            "n_a3_signals":   len(a3_dates),
            "n_s3_signals":   len(s3_dates),
            "n_dual_same_bar": len(dual),
            "n_a3_with_regime": sum(1 for d in a3_dates if bool(regime.get(d, True))),
            **{f"n_{b}": lead_buckets[b] for b in BUCKET_ORDER},
        })

    df = pd.DataFrame(rows).sort_values("n_a3_signals", ascending=False)
    df.to_csv(OUT / "phase36_a3_s3_state_panel.csv", index=False)
    print(f"  State panel: {len(df)} symbols", flush=True)

    # Summary stats
    total_a3  = int(df["n_a3_signals"].sum())
    total_s3  = int(df["n_s3_signals"].sum())
    n_lead_11 = int(df["n_lead_11_20"].sum())
    n_lead_21 = int(df["n_lead_21_30"].sum())
    n_same    = int(df["n_same_bar_0"].sum())
    n_no_lead = int(df["n_no_s3_lead"].sum())
    n_lead_1  = int(df["n_lead_1_5"].sum())
    n_lead_6  = int(df["n_lead_6_10"].sum())

    md = textwrap.dedent(f"""\
    # Phase36A — State Taxonomy

    Generated: 2026-05-17 | Symbols: {len(df)} | Universe: A3 ex-VIN3

    ## Signal Totals

    | Metric | Count |
    |--------|-------|
    | A3 signals (all years) | {total_a3:,} |
    | S3 signals (all years) | {total_s3:,} |
    | S3/A3 signal ratio | {total_s3/max(total_a3,1):.2f}× |

    ## A3 Lead-Bucket Distribution (regime-bull bars only)

    | Bucket | Count | Pct of A3 |
    |--------|-------|-----------|
    | same_bar_0 (chase) | {n_same:,} | {n_same/max(total_a3,1):.1%} |
    | lead_1_5 (neutral) | {n_lead_1:,} | {n_lead_1/max(total_a3,1):.1%} |
    | lead_6_10 (neutral) | {n_lead_6:,} | {n_lead_6/max(total_a3,1):.1%} |
    | lead_11_20 (best +2.0) | {n_lead_11:,} | {n_lead_11/max(total_a3,1):.1%} |
    | lead_21_30 (good +1.0) | {n_lead_21:,} | {n_lead_21/max(total_a3,1):.1%} |
    | no_s3_lead | {n_no_lead:,} | {n_no_lead/max(total_a3,1):.1%} |

    ## Implications

    - S3 fires ~{total_s3/max(total_a3,1):.1f}× more often than A3 (EMA21/55 faster than EMA20/100)
    - ~{(n_lead_11+n_lead_21)/max(total_a3,1):.1%} of A3 signals have a lead_11_30 S3 precursor (prime ranking zone)
    - ~{n_same/max(total_a3,1):.1%} of A3 signals fire same-bar as S3 (chase, ranked below)
    - ~{n_no_lead/max(total_a3,1):.1%} of A3 signals have no recent S3 precursor

    ## Key Finding

    FACT: S3 EMA21/55 provides a materially earlier signal than A3 EMA20/100 in
    {(n_lead_11+n_lead_21)/max(total_a3,1):.1%} of cases. These are the prime candidates
    for ranking boost.

    INTERPRETATION: If lead_11_20 and lead_21_30 A3 trades perform better than no_s3_lead
    trades at the portfolio level, ranking by a3_rank_score should improve slot-constrained MAR.
    See Phase36B for evidence.
    """)
    (OUT / "PHASE36A_STATE_TAXONOMY.md").write_text(md, encoding="utf-8")
    print("  PHASE36A_STATE_TAXONOMY.md written", flush=True)


# ── Phase36B: Ranking tests ───────────────────────────────────────────────────

def run_phase_b(a3_trades_tagged: pd.DataFrame, adv50_map: dict) -> pd.DataFrame:
    print("\n=== PHASE36B: Ranking Tests ===", flush=True)

    rows = []
    slot_sizes = [15, 20, 25]

    rank_variants = {
        "baseline_ema_dist":    "ema_dist_at_entry",
        "a3_rank_score":        "a3_rank_score",
        "ed_score_only":        "ed_score",
        "lead_11_20_flag":      "lead_11_20_flag",  # bool → 1/0
        "mom20":                "mom20_at_entry",
    }

    for slots in slot_sizes:
        for vname, rcol in rank_variants.items():
            df = a3_trades_tagged.copy()
            if rcol not in df.columns:
                continue
            # Convert bool columns to float for ranking
            if df[rcol].dtype == bool:
                df[rcol] = df[rcol].astype(float)

            eq, _ = _build_equity_adv_capped_v2(
                _tag_adv50(df, adv50_map) if (df.get("adv50_value", pd.Series([0])) == 0).all() else df,
                slots, PORTFOLIO_VND, PARTICIPATION,
                rank_col=rcol,
            )
            if eq.empty:
                continue
            m  = portfolio_metrics(eq, df[df["net_return"].notna()])
            r  = _metric_row(f"{vname}|slots={slots}", m)
            r["slots"]   = slots
            r["rank_col"] = rcol
            for yr in KEY_YEARS:
                r[f"yr_{yr}"] = round(_annual_return(eq, yr), 4)
            rows.append(r)
            print(f"  {vname} slots={slots}: MAR={_fmt(m.get('mar'))} "
                  f"CAGR={_fmt(m.get('cagr'))} DD={_fmt(m.get('max_dd'))}", flush=True)

    out_df = pd.DataFrame(rows)
    out_df.to_csv(OUT / "phase36_s3_a3_ranking_tests.csv", index=False)
    print(f"  Ranking results: {len(out_df)} rows", flush=True)

    # Write findings
    best = out_df.loc[out_df["mar"].idxmax()] if not out_df.empty else None
    best_str = f"Best: {best['variant']} MAR={_fmt(best['mar'])} delta={_fmt(best['mar_vs_baseline'])}" if best is not None else "Insufficient data"

    md = _ranking_md(out_df, best_str)
    (OUT / "PHASE36B_RANKING_FINDINGS.md").write_text(md, encoding="utf-8")
    print("  PHASE36B_RANKING_FINDINGS.md written", flush=True)
    return out_df


def _ranking_md(df: pd.DataFrame, best_str: str) -> str:
    rows20 = df[df["slots"] == 20].copy() if not df.empty else pd.DataFrame()
    tbl = ""
    if not rows20.empty:
        for _, r in rows20.sort_values("mar", ascending=False).iterrows():
            accepted = "YES" if float(r["mar"]) >= MAR_THRESHOLD else "no"
            tbl += f"| {r['variant'].split('|')[0]} | {_fmt(r['mar'])} | {_fmt(r['cagr'], True)} | {_fmt(r['max_dd'], True)} | {_fmt(r['mar_vs_baseline'])} | {accepted} |\n"

    return textwrap.dedent(f"""\
    # Phase36B — Ranking Tests

    Generated: 2026-05-17 | A3 baseline MAR=0.416, threshold={MAR_THRESHOLD:.3f}

    ## MAR Acceptance Bar: +0.03 over baseline → need MAR ≥ {MAR_THRESHOLD:.3f}

    ## Results (20-slot portfolio)

    | Variant | MAR | CAGR | MaxDD | Δ-MAR | Accept? |
    |---------|-----|------|-------|-------|---------|
    {tbl}
    ## Conclusion

    {best_str}

    CONSTRAINT: A3 production logic unchanged. Ranking is advisory only for operator
    when multiple NEW_T1 fire same day. It does not block any A3 signal.

    ## What This Means for Operations

    - If a3_rank_score improves MAR ≥ +0.03: adopt it as the NEW_T1 same-day sort order
    - If improvement < +0.03: keep ema_dist_at_entry as default sort
    - Regardless: a3_rank_score is already computed in Phase35 scan output
    """)


# ── Phase36C: Sizing overlay ──────────────────────────────────────────────────

def run_phase_c(a3_trades_tagged: pd.DataFrame, adv50_map: dict) -> pd.DataFrame:
    print("\n=== PHASE36C: Sizing Overlay ===", flush=True)

    df_base = _tag_adv50(a3_trades_tagged, adv50_map) if (
        a3_trades_tagged.get("adv50_value", pd.Series([0])) == 0).all() else a3_trades_tagged.copy()

    rows = []

    sizing_variants = [
        ("equal_weight",        "has_gk",          1.0),
        ("lead_best_125x",      "lead_11_20_flag",  1.25),
        ("chase_75x",           "chase_flag",       0.75),
    ]

    for vname, gcol, gmult in sizing_variants:
        df = df_base.copy()
        if gcol not in df.columns:
            df[gcol] = False
        df[gcol] = df[gcol].astype(bool)

        eq, _ = _build_equity_adv_capped_v2(
            df, MAX_SLOTS, PORTFOLIO_VND, PARTICIPATION,
            gk_mult=gmult, gk_col=gcol,
            rank_col="a3_rank_score" if "a3_rank_score" in df.columns else "ema_dist_at_entry",
        )
        if eq.empty:
            continue
        m  = portfolio_metrics(eq, df[df["net_return"].notna()])
        r  = _metric_row(vname, m)
        for yr in KEY_YEARS:
            r[f"yr_{yr}"] = round(_annual_return(eq, yr), 4)
        rows.append(r)
        print(f"  {vname}: MAR={_fmt(m.get('mar'))} CAGR={_fmt(m.get('cagr'))} "
              f"DD={_fmt(m.get('max_dd'))}", flush=True)

    out_df = pd.DataFrame(rows)
    out_df.to_csv(OUT / "phase36_a3_s3_sizing_tests.csv", index=False)

    best = out_df.loc[out_df["mar"].idxmax()] if not out_df.empty else None
    accepted = (best is not None and float(best["mar"]) >= MAR_THRESHOLD)

    md = textwrap.dedent(f"""\
    # Phase36C — Sizing Overlay

    Generated: 2026-05-17 | Baseline MAR=0.416 | Accept threshold={MAR_THRESHOLD:.3f}

    ## Tested Variants

    | Variant | gk_col flag | size_mult | MAR | Δ-MAR | Accept? |
    |---------|-------------|-----------|-----|-------|---------|
    """)
    for _, r in out_df.sort_values("mar", ascending=False).iterrows():
        acc = "YES" if float(r["mar"]) >= MAR_THRESHOLD else "no"
        md += f"| {r['variant']} | - | - | {_fmt(r['mar'])} | {_fmt(r['mar_vs_baseline'])} | {acc} |\n"

    md += textwrap.dedent(f"""
    ## Conclusion

    Best sizing variant: {best['variant'] if best is not None else 'N/A'}
    MAR = {_fmt(best['mar']) if best is not None else 'N/A'}
    Accepted: {'YES' if accepted else 'NO — improvement below +0.03 threshold'}

    ## Hard Rules

    - Sizing adjustments are ADVISORY only
    - GK multiplier (Phase33) is already implemented and validated
    - S3-lead sizing boost does NOT block A3 signals
    - No sizing variant may exceed 2× base slot weight
    """)

    (OUT / "PHASE36C_SIZING_FINDINGS.md").write_text(md, encoding="utf-8")
    print("  PHASE36C_SIZING_FINDINGS.md written", flush=True)
    return out_df


# ── Phase36D: T2 policy ───────────────────────────────────────────────────────

def run_phase_d(a3_trades_tagged: pd.DataFrame, adv50_map: dict) -> pd.DataFrame:
    print("\n=== PHASE36D: T2 Policy ===", flush=True)

    df_base = _tag_adv50(a3_trades_tagged, adv50_map) if (
        a3_trades_tagged.get("adv50_value", pd.Series([0])) == 0).all() else a3_trades_tagged.copy()

    rows = []

    def _run(df, label):
        eq, _ = _build_equity_adv_capped_v2(
            df, MAX_SLOTS, PORTFOLIO_VND, PARTICIPATION,
            rank_col="a3_rank_score" if "a3_rank_score" in df.columns else "ema_dist_at_entry",
        )
        if eq.empty:
            return
        m  = portfolio_metrics(eq, df[df["net_return"].notna()])
        r  = _metric_row(label, m)
        for yr in KEY_YEARS:
            r[f"yr_{yr}"] = round(_annual_return(eq, yr), 4)
        rows.append(r)
        print(f"  {label}: MAR={_fmt(m.get('mar'))} CAGR={_fmt(m.get('cagr'))} "
              f"DD={_fmt(m.get('max_dd'))}", flush=True)

    # Baseline: T2 always (total_frac=1.0 for all)
    df0 = df_base.copy()
    df0["total_frac"] = 1.0
    _run(df0, "t2_always_baseline")

    # T2 only for lead_11_20 / lead_21_30: others get t1_only (total_frac=0.5)
    df1 = df_base.copy()
    df1["total_frac"] = np.where(df1["lead_11_20_flag"], 1.0, 0.5)
    _run(df1, "t2_only_if_good_lead")

    # T2 blocked for chase (same_bar_0): total_frac=0.5 for chasers
    df2 = df_base.copy()
    df2["total_frac"] = np.where(df2["chase_flag"], 0.5, 1.0)
    _run(df2, "t2_blocked_for_chase")

    # T1-only baseline (no T2 ever): total_frac=0.5 for all
    df3 = df_base.copy()
    df3["total_frac"] = 0.5
    _run(df3, "t1_only_no_t2")

    out_df = pd.DataFrame(rows)
    out_df.to_csv(OUT / "phase36_a3_s3_t2_policy_tests.csv", index=False)

    md = textwrap.dedent(f"""\
    # Phase36D — T2 Policy Coordination

    Generated: 2026-05-17 | Baseline MAR=0.416 | Accept threshold={MAR_THRESHOLD:.3f}

    ## Method

    T2 exposure is modeled via `total_frac` column:
    - total_frac=1.0: T1 (50%) + T2 (50%) — full slot filled
    - total_frac=0.5: T1 only — half slot (T2 never executed)

    This approximates dollar exposure impact. Actual return profile differs because
    T2 pullback entry at a lower price is not modeled here (conservative estimate).

    ## Results

    | Variant | MAR | Δ-MAR | Accept? |
    |---------|-----|-------|---------|
    """)
    for _, r in out_df.sort_values("mar", ascending=False).iterrows():
        acc = "YES" if float(r["mar"]) >= MAR_THRESHOLD else "no"
        md += f"| {r['variant']} | {_fmt(r['mar'])} | {_fmt(r['mar_vs_baseline'])} | {acc} |\n"

    md += textwrap.dedent(f"""
    ## Hard Rules

    - T2 policy does NOT block A3 T1 entries
    - Breadth T2 block (pct_cloud_bull_a3 < 35%) remains unchanged
    - VNINDEX bear block remains unchanged
    - S3 lead affects T2 PRIORITY only, not T2 permission
    """)
    (OUT / "PHASE36D_T2_FINDINGS.md").write_text(md, encoding="utf-8")
    print("  PHASE36D_T2_FINDINGS.md written", flush=True)
    return out_df


# ── Phase36E: Exit overlay ───────────────────────────────────────────────────

def run_phase_e(a3_cache: dict, s3_cache: dict, regime: pd.Series,
                adv50_map: dict) -> pd.DataFrame:
    print("\n=== PHASE36E: Exit Overlay ===", flush=True)

    rows = []

    def _build_and_run(exit_cfg, label, symbol_filter=None):
        cache = {k: v for k, v in a3_cache.items()
                 if symbol_filter is None or k in symbol_filter}
        tr = _build_trades(cache, exit_cfg, gate_by_date=regime)
        if tr.empty:
            return
        tr = _tag_adv50(tr, adv50_map)
        eq, _ = _build_equity_adv_capped_v2(
            tr, MAX_SLOTS, PORTFOLIO_VND, PARTICIPATION,
            rank_col="ema_dist_at_entry",
        )
        if eq.empty:
            return
        m  = portfolio_metrics(eq, tr[tr["net_return"].notna()])
        r  = _metric_row(label, m)
        for yr in KEY_YEARS:
            r[f"yr_{yr}"] = round(_annual_return(eq, yr), 4)
        rows.append(r)
        print(f"  {label}: MAR={_fmt(m.get('mar'))} CAGR={_fmt(m.get('cagr'))} "
              f"DD={_fmt(m.get('max_dd'))}", flush=True)

    # Baseline A3
    _build_and_run(EXIT_A3, "baseline_a3_trail25")

    # Tighter trail 2.0× for all (lower bound test)
    _build_and_run({**EXIT_A3, "trail_mult": 2.0}, "tight_trail_20_all")

    # Wider trail 3.0× for all (upper bound test)
    _build_and_run({**EXIT_A3, "trail_mult": 3.0}, "wide_trail_30_all")

    # Reduced max_hold=180 (early exit test)
    _build_and_run({**EXIT_A3, "max_hold": 180}, "max_hold_180_all")

    out_df = pd.DataFrame(rows)
    out_df.to_csv(OUT / "phase36_a3_s3_exit_overlay_tests.csv", index=False)

    md = textwrap.dedent(f"""\
    # Phase36E — Exit Overlay

    Generated: 2026-05-17 | Baseline MAR=0.416 | Accept threshold={MAR_THRESHOLD:.3f}

    ## Method

    Tests different exit parameters applied globally to A3 trades.
    Per-trade exit conditioning on S3 lead is not implemented in this pass
    (would require separate per-symbol rebuilds by lead group).

    | Variant | trail_mult | max_hold | MAR | Δ-MAR | Accept? |
    |---------|-----------|---------|-----|-------|---------|
    """)
    for _, r in out_df.sort_values("mar", ascending=False).iterrows():
        acc = "YES" if float(r["mar"]) >= MAR_THRESHOLD else "no"
        md += f"| {r['variant']} | - | - | {_fmt(r['mar'])} | {_fmt(r['mar_vs_baseline'])} | {acc} |\n"

    md += textwrap.dedent(f"""
    ## Hard Rules

    - A3 production exit parameters (2.5×ATR14, max_hold=250) are locked unless
      this research shows MAR improvement ≥ +0.03 with a specific override
    - Any accepted exit variant requires operator review before adoption
    """)
    (OUT / "PHASE36E_EXIT_OVERLAY_FINDINGS.md").write_text(md, encoding="utf-8")
    print("  PHASE36E_EXIT_OVERLAY_FINDINGS.md written", flush=True)
    return out_df


# ── Phase36F: Satellite sleeve ───────────────────────────────────────────────

def run_phase_f(a3_cache: dict, s3_cache: dict, regime: pd.Series,
                adv50_map: dict) -> pd.DataFrame:
    print("\n=== PHASE36F: Satellite Sleeve ===", flush=True)

    # Build A3 equity
    print("  Building A3 trades...", flush=True)
    a3_tr = _build_trades(a3_cache, EXIT_A3, gate_by_date=regime)
    a3_tr = _tag_adv50(a3_tr, adv50_map)
    a3_eq, _ = _build_equity_adv_capped_v2(a3_tr, MAX_SLOTS, PORTFOLIO_VND, PARTICIPATION)
    if a3_eq.empty:
        print("  WARNING: A3 equity empty, skipping satellite", flush=True)
        return pd.DataFrame()

    # Build S3 max60 equity
    print("  Building S3 shadow trades...", flush=True)
    s3_tr = _build_trades(s3_cache, EXIT_S3, gate_by_date=regime)
    s3_tr = _tag_adv50(s3_tr, adv50_map)
    s3_eq, _ = _build_equity_adv_capped_v2(
        s3_tr, MAX_SLOTS, PORTFOLIO_VND, PARTICIPATION,
        rank_col="ema_dist_at_entry",
    )

    rows = []

    splits = [(1.0, 0.0), (0.9, 0.1), (0.8, 0.2), (0.7, 0.3), (0.6, 0.4)]

    for a_wt, s_wt in splits:
        label = f"A3_{int(a_wt*100)}_S3_{int(s_wt*100)}"
        if s_wt == 0.0 or s3_eq.empty:
            eq = a3_eq.copy()
        else:
            idx   = a3_eq.index.union(s3_eq.index)
            a3_r  = a3_eq.reindex(idx).ffill().bfill()
            s3_r  = s3_eq.reindex(idx).ffill().bfill()
            # Normalize both to start at 1.0, then blend
            a3_n  = a3_r / float(a3_r.iloc[0])
            s3_n  = s3_r / float(s3_r.iloc[0])
            eq    = a_wt * a3_n + s_wt * s3_n

        m  = portfolio_metrics(eq, a3_tr[a3_tr["net_return"].notna()])
        r  = _metric_row(label, m)
        r["a3_weight"]    = a_wt
        r["s3_weight"]    = s_wt
        r["s3_max_hold"]  = 60
        r["s3_real_cap"]  = "NEVER"
        for yr in KEY_YEARS:
            r[f"yr_{yr}"] = round(_annual_return(eq, yr), 4)
        rows.append(r)
        print(f"  {label}: MAR={_fmt(m.get('mar'))} CAGR={_fmt(m.get('cagr'))} "
              f"DD={_fmt(m.get('max_dd'))}", flush=True)

    out_df = pd.DataFrame(rows)
    out_df.to_csv(OUT / "phase36_a3_s3_satellite_sleeve_tests.csv", index=False)

    md = textwrap.dedent(f"""\
    # Phase36F — Satellite Sleeve

    Generated: 2026-05-17 | Baseline MAR=0.416 | Accept threshold={MAR_THRESHOLD:.3f}

    ## Method

    Blend A3 and S3 equity curves (both normalized to start=1.0, simulated separately).
    S3 sleeve: EMA21/55, max_hold=60, TP=18%, trail=3.5×. NO REAL CAPITAL.

    This is PAPER RESEARCH ONLY. S3 portion represents paper shadow returns.
    Any implementation requires S3 paper gate passage (12 months, MAR≥0.35).

    | Blend | MAR | CAGR | MaxDD | Δ-MAR | Accept? |
    |-------|-----|------|-------|-------|---------|
    """)
    for _, r in out_df.sort_values("mar", ascending=False).iterrows():
        acc = "YES" if float(r["mar"]) >= MAR_THRESHOLD else "no"
        md += (f"| A3={r['a3_weight']:.0%}/S3={r['s3_weight']:.0%} | "
               f"{_fmt(r['mar'])} | {_fmt(r['cagr'], True)} | "
               f"{_fmt(r['max_dd'], True)} | {_fmt(r['mar_vs_baseline'])} | {acc} |\n")

    md += textwrap.dedent(f"""
    ## Hard Rules

    - S3 sleeve = PAPER_TRADE_SHADOW only. No real capital. No DNSE.
    - S3 sleeve P&L tracked SEPARATELY from A3 equity curve
    - Satellite sleeve adoption requires S3 shadow gate passage first (Gate 10/11)
    - Any sleeve > 20% S3 requires explicit operator decision + separate broker account
    """)
    (OUT / "PHASE36F_SATELLITE_FINDINGS.md").write_text(md, encoding="utf-8")
    print("  PHASE36F_SATELLITE_FINDINGS.md written", flush=True)
    return out_df


# ── Phase36G: Risk warning ───────────────────────────────────────────────────

def run_phase_g(a3_cache: dict, s3_cache: dict, regime: pd.Series,
                adv50_map: dict) -> pd.DataFrame:
    print("\n=== PHASE36G: Risk Warning ===", flush=True)

    a3_tr = _build_trades(a3_cache, EXIT_A3, gate_by_date=regime)
    a3_tr = _tag_adv50(a3_tr, adv50_map)
    s3_tr = _build_trades(s3_cache, EXIT_S3, gate_by_date=regime)
    s3_tr = _tag_adv50(s3_tr, adv50_map)

    a3_eq, _ = _build_equity_adv_capped_v2(a3_tr, MAX_SLOTS, PORTFOLIO_VND, PARTICIPATION)
    s3_eq, _ = _build_equity_adv_capped_v2(s3_tr, MAX_SLOTS, PORTFOLIO_VND, PARTICIPATION)

    if a3_eq.empty or s3_eq.empty:
        print("  WARNING: empty equity, skipping risk warning", flush=True)
        return pd.DataFrame()

    idx    = a3_eq.index.union(s3_eq.index)
    a3_al  = a3_eq.reindex(idx).ffill()
    s3_al  = s3_eq.reindex(idx).ffill()

    a3_dd  = (a3_al / a3_al.cummax() - 1.0)
    s3_dd  = (s3_al / s3_al.cummax() - 1.0)

    # Concurrent drawdown analysis
    corr   = float(a3_dd.corr(s3_dd))
    both_dd10 = int(((a3_dd < -0.10) & (s3_dd < -0.10)).sum())
    both_dd15 = int(((a3_dd < -0.15) & (s3_dd < -0.15)).sum())
    total_days = len(idx)

    rows_g = []
    for yr in KEY_YEARS:
        a3_yr = a3_dd[a3_dd.index.year == yr]
        s3_yr = s3_dd[s3_dd.index.year == yr]
        if a3_yr.empty:
            continue
        rows_g.append({
            "year":            yr,
            "a3_max_dd":       round(float(a3_yr.min()), 4),
            "s3_max_dd":       round(float(s3_yr.min()), 4) if not s3_yr.empty else np.nan,
            "dd_correlation":  round(float(a3_yr.corr(s3_yr)), 4) if not s3_yr.empty else np.nan,
            "concurrent_dd10": int(((a3_yr < -0.10) & (s3_yr < -0.10)).sum()) if not s3_yr.empty else 0,
        })

    out_df = pd.DataFrame(rows_g)
    out_df.to_csv(OUT / "phase36_s3_portfolio_risk_warning_tests.csv", index=False)

    md = textwrap.dedent(f"""\
    # Phase36G — Risk Warning Analysis

    Generated: 2026-05-17

    ## Full-Period Drawdown Correlation

    | Metric | Value |
    |--------|-------|
    | A3/S3 DD correlation (full period) | {corr:.3f} |
    | Days both A3 and S3 in DD > 10% | {both_dd10:,} of {total_days:,} ({both_dd10/max(total_days,1):.1%}) |
    | Days both A3 and S3 in DD > 15% | {both_dd15:,} of {total_days:,} ({both_dd15/max(total_days,1):.1%}) |

    ## Annual DD by Year

    | Year | A3 MaxDD | S3 MaxDD | Corr | Concurrent DD>10% |
    |------|---------|---------|------|-------------------|
    """)
    for _, r in out_df.iterrows():
        md += (f"| {int(r['year'])} | {_fmt(r['a3_max_dd'], True)} | "
               f"{_fmt(r['s3_max_dd'], True)} | {_fmt(r['dd_correlation'])} | "
               f"{int(r['concurrent_dd10'] or 0)} |\n")

    md += textwrap.dedent(f"""
    ## Warning Triggers (Proposed)

    If DD correlation > 0.70: flag "Correlated drawdown risk — S3 shadow losses
    may coincide with A3 losses. Review sector concentration."

    If both A3 DD > 15% AND S3 DD > 15% simultaneously: flag "Dual-strategy stress.
    Do not add new A3 positions until A3 DD recovers to < 10%."

    ## Hard Rules

    - S3 shadow losses DO NOT trigger A3 position reductions
    - A3 position reductions are governed ONLY by VNINDEX regime + breadth gates
    - Risk warnings are ADVISORY — they do not override A3 scan signals
    """)
    (OUT / "PHASE36G_RISK_WARNING_FINDINGS.md").write_text(md, encoding="utf-8")
    print("  PHASE36G_RISK_WARNING_FINDINGS.md written", flush=True)
    return out_df


# ── Phase36H: Interaction matrix ─────────────────────────────────────────────

def run_phase_h(results: dict) -> None:
    print("\n=== PHASE36H: Interaction Matrix ===", flush=True)

    summary_rows = []
    for phase, df in results.items():
        if df is None or df.empty:
            continue
        for _, r in df.iterrows():
            summary_rows.append({
                "phase":    phase,
                "variant":  str(r.get("variant", "")),
                "mar":      float(r.get("mar", np.nan)),
                "cagr":     float(r.get("cagr", np.nan)),
                "max_dd":   float(r.get("max_dd", np.nan)),
                "mar_delta": float(r.get("mar_vs_baseline", np.nan)),
                "accepted": float(r.get("mar", np.nan)) >= MAR_THRESHOLD,
            })

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(OUT / "phase36_playbook_summary.csv", index=False)

    # Interaction matrix: which phases benefit together
    matrix_rows = []
    phases_list = list(results.keys())
    for p1 in phases_list:
        for p2 in phases_list:
            if p1 >= p2:
                continue
            df1 = results.get(p1)
            df2 = results.get(p2)
            if df1 is None or df2 is None or df1.empty or df2.empty:
                continue
            best1 = float(df1["mar"].max()) if "mar" in df1.columns else np.nan
            best2 = float(df2["mar"].max()) if "mar" in df2.columns else np.nan
            matrix_rows.append({
                "phase_1": p1,
                "phase_2": p2,
                "best_mar_p1": round(best1, 4),
                "best_mar_p2": round(best2, 4),
                "both_above_threshold": (best1 >= MAR_THRESHOLD and best2 >= MAR_THRESHOLD),
            })

    matrix_df = pd.DataFrame(matrix_rows)
    matrix_df.to_csv(OUT / "phase36_playbook_interaction_matrix.csv", index=False)

    # Accepted variants
    accepted = summary_df[summary_df["accepted"]] if not summary_df.empty else pd.DataFrame()
    n_accepted = len(accepted)

    md = textwrap.dedent(f"""\
    # Phase36H — Interaction Matrix & Playbook

    Generated: 2026-05-17 | A3 baseline MAR=0.416 | Threshold={MAR_THRESHOLD:.3f}

    ## Summary: Accepted Variants (MAR ≥ {MAR_THRESHOLD:.3f})

    Total accepted: {n_accepted} of {len(summary_df)}

    """)
    if not accepted.empty:
        md += "| Phase | Variant | MAR | Δ-MAR |\n|-------|---------|-----|-------|\n"
        for _, r in accepted.sort_values("mar_delta", ascending=False).iterrows():
            md += f"| {r['phase']} | {r['variant']} | {_fmt(r['mar'])} | {_fmt(r['mar_delta'])} |\n"
    else:
        md += "_No variants reached the +0.03 MAR threshold._\n"

    md += textwrap.dedent(f"""
    ## Recommendations

    1. **Ranking (Phase36B)**: If a3_rank_score improves MAR ≥ +0.03 at 20 slots,
       adopt it as the same-day NEW_T1 sort order in the scan output.

    2. **Sizing (Phase36C)**: Lead-bucket size multiplier is low-risk additive.
       Adopt only if MAR improvement verified AND does not increase portfolio volatility.

    3. **T2 Policy (Phase36D)**: T2 conditional on S3 lead adds complexity with
       uncertain benefit. Default: keep current T2 policy (breadth + regime gates).

    4. **Exit overlay (Phase36E)**: Trail parameter changes affect ALL trades globally.
       Only adopt if clear MAR improvement. Conservative default: keep 2.5×ATR14.

    5. **Satellite sleeve (Phase36F)**: PAPER RESEARCH ONLY. Requires S3 paper gate
       passage before any implementation. Not a production decision now.

    6. **Risk warning (Phase36G)**: Implement DD correlation monitor as advisory panel.
       Does not change A3 production logic.

    ## Decision Framework

    | Condition | Action |
    |-----------|--------|
    | Ranking MAR Δ ≥ +0.03 | Adopt a3_rank_score as NEW_T1 sort |
    | Ranking MAR Δ < +0.03 | Keep ema_dist_at_entry sort (current) |
    | Sizing MAR Δ ≥ +0.03 | Adopt lead-bucket multiplier (operator-approved) |
    | Sizing MAR Δ < +0.03 | Keep equal weight |
    | Exit overlay MAR Δ ≥ +0.03 | Propose exit param change for review |
    | Exit overlay MAR Δ < +0.03 | Keep 2.5×ATR14 / max_hold=250 |
    | Satellite: S3 paper gate not met | No implementation (Gate 10/11 required first) |

    ## Hard Rules (unchanged)

    - A3 EMA20/100 + DP-first entry: locked
    - S3 EMA21/55 max_hold=60: paper shadow only, no real capital
    - VNINDEX EMA20>EMA100 hard block: locked
    - Breadth T2 block (<35%): locked
    - ADV50 10% participation cap: locked
    """)
    (OUT / "PHASE36H_PLAYBOOK_FINDINGS.md").write_text(md, encoding="utf-8")
    print("  PHASE36H_PLAYBOOK_FINDINGS.md written", flush=True)


# ── Phase36I: Implementation plan docs ───────────────────────────────────────

def write_phase_i_docs(all_results: dict) -> None:
    print("\n=== PHASE36I: Implementation Plan Docs ===", flush=True)

    # Determine best ranking variant from phase B results
    b_df = all_results.get("36B")
    best_rank = "a3_rank_score"
    if b_df is not None and not b_df.empty and "mar" in b_df.columns:
        b20 = b_df[b_df.get("slots", pd.Series()) == 20] if "slots" in b_df.columns else b_df
        if not b20.empty:
            best_rank = str(b20.loc[b20["mar"].idxmax(), "variant"]).split("|")[0].strip()

    scan_schema = textwrap.dedent(f"""\
    # Phase36 Scan Schema Proposal

    Generated: 2026-05-17 | Based on Phase36A-H research findings

    ## New Fields vs Phase35 Schema (58 fields)

    | Field | Type | Description | Phase |
    |-------|------|-------------|-------|
    | s3_lead_bdays | int | Business days since last S3 signal (≤35, else NaN) | 36 |
    | s3_lead_bucket | str | Bucket: same_bar_0/lead_1_5/lead_6_10/lead_11_20/lead_21_30/no_s3_lead | 36 |
    | ed_score | float | EMA proximity score: max(0, 1-abs(ema_dist_pct)/0.20) | 36 |
    | a3_rank_score | float | ed_score + quality_boost(s3_lead_bucket) | 36 |
    | a3_s3_lead_5d | bool | True if s3_lead_bdays in [1,5] (legacy boolean) | 35 |
    | a3_priority_boost_from_s3 | bool | True if lead_11_20 or lead_21_30 | 36 |

    ## Total fields after Phase36: 64

    ## Ranking Rules

    Multiple NEW_T1 same day → sort by a3_rank_score DESC.
    Best variant from Phase36B research: {best_rank}

    - lead_11_20 + good ed_score → highest a3_rank_score
    - same_bar_0 (chase) → penalized by -0.5 boost
    - no_s3_lead → neutral (0.0 boost), ed_score only

    ## Hard Rules (unchanged)

    - a3_rank_score does NOT block any A3 signal
    - Ranking applies only when slot capacity is binding (>MAX_SLOTS NEW_T1 same day)
    - S3 shadow fields remain PAPER_TRADE_SHADOW — never route to live orders
    """)
    (OUT / "PHASE36_SCAN_SCHEMA_PROPOSAL.md").write_text(scan_schema, encoding="utf-8")

    dashboard = textwrap.dedent(f"""\
    # Phase36 Dashboard Proposal

    Generated: 2026-05-17 | Extends UPDATED_PHASE35_DASHBOARD_SPEC.md

    ## New / Updated Panels

    ### Panel 2 — A3 Production (updated)
    - Sort NEW_T1 by a3_rank_score DESC (Phase36 standard)
    - Show s3_lead_bucket column (lead_11_20 highlighted)
    - Show a3_rank_score, ed_score, quality_boost separately
    - a3_priority_boost_from_s3 flag column

    ### Panel 7 — Lead-Age Distribution (Phase36)
    - Bar chart: count of active setups by s3_lead_bucket
    - Target zone: lead_11_20 + lead_21_30 as % of NEW_T1
    - Chase alert: if same_bar_0 > 30% of NEW_T1, flag "Chase risk"

    ### Panel 8 — A3/S3 Coordination Monitor (Phase36)
    - Columns: symbol, a3_rank_score, s3_lead_bucket, s3_lead_bdays, ed_score
    - Sorted by a3_rank_score DESC for current-day NEW_T1 signals
    - Color: green for lead_11_20/lead_21_30, yellow for neutral, red for same_bar_0

    ### Panel 9 — DD Correlation Monitor (Phase36G)
    - A3 portfolio rolling 20-day DD vs S3 shadow rolling 20-day DD
    - Alert threshold: both DD > 10% → "Correlated drawdown"

    ## Existing Panels (Phase35, unchanged)
    - Panel 1: Data health / as-of
    - Panel 2: A3 production (updated above)
    - Panel 3: S3 paper shadow (max_hold=60)
    - Panel 4: S3 research monitor (GK5+top100)
    - Panel 5: Legacy satellite (not production SSOT)
    - Panel 6: Warnings
    - Panel 10: S3 combo paper (Phase36, TP=10%)
    """)
    (OUT / "PHASE36_DASHBOARD_PROPOSAL.md").write_text(dashboard, encoding="utf-8")

    # Collect accepted variants
    accepted_list = []
    for phase, df in all_results.items():
        if df is None or df.empty:
            continue
        if "mar" not in df.columns:
            continue
        best = df.loc[df["mar"].idxmax()]
        if float(best["mar"]) >= MAR_THRESHOLD:
            accepted_list.append(f"- Phase {phase}: {best['variant']} MAR={_fmt(best['mar'])} Δ={_fmt(best['mar_vs_baseline'])}")

    accepted_str = "\n".join(accepted_list) if accepted_list else "- No variants met MAR ≥ +0.03 threshold"

    impl_plan = textwrap.dedent(f"""\
    # Phase36 Implementation Plan

    Generated: 2026-05-17 | Decision: evidence-driven only

    ## Gate: MAR improvement ≥ +0.03 required for adoption

    Baseline A3 MAR = {A3_BASELINE_MAR:.3f}
    Threshold = {MAR_THRESHOLD:.3f}

    ## Accepted Variants

    {accepted_str}

    ## Implementation Steps (if ranking accepted)

    ### Step 1: Scan update (already done in Phase35)
    - a3_rank_score field already in phase35_daily_scan_sample.csv
    - s3_lead_bucket field already computed
    - No additional scan changes required

    ### Step 2: Daily runbook update
    - NEW_T1 same-day sort: use a3_rank_score DESC (vs current ema_dist)
    - Already documented in UPDATED_FINAL_DAILY_RUNBOOK.md

    ### Step 3: Dashboard panel
    - Add Panel 7 (lead-age distribution) to daily monitoring
    - Add Panel 8 (A3/S3 coordination) to daily monitoring
    - Implement DD correlation monitor (Panel 9)

    ### Step 4: Paper validation
    - Track whether a3_rank_score correctly predicts better same-day picks
    - Review at 30 trades / 3 months

    ## Implementation Steps (if sizing accepted)

    - Add s3_size_flag column to scan (True if lead_11_20 or lead_21_30)
    - Update order_intent.py: if s3_size_flag=True, increase slot by 25%
    - Gate: max slot still subject to ADV cap

    ## What is NOT changing

    - A3 EMA20/100 cloud entry
    - TP=18%, trail=2.5×ATR14, max_hold=250
    - VNINDEX bear hard block
    - Breadth T2 gate
    - S3 classification: PAPER_TRADE_SHADOW only
    - S3 max_hold=60 hard rule
    - A3 real capital gates (Gate 1-7)

    ## Timeline

    No fixed timeline. Evidence-driven.
    Next review: after 3 months of paper tracking with a3_rank_score.
    """)
    (OUT / "PHASE36_IMPLEMENTATION_PLAN.md").write_text(impl_plan, encoding="utf-8")
    print("  Phase36I docs written (scan schema, dashboard, impl plan)", flush=True)


# ── Final Decision Memo ───────────────────────────────────────────────────────

def write_decision_memo(all_results: dict) -> None:
    print("\n=== Writing Decision Memo ===", flush=True)

    accepted_variants = []
    for phase, df in all_results.items():
        if df is None or df.empty or "mar" not in df.columns:
            continue
        for _, r in df.iterrows():
            if float(r.get("mar", np.nan)) >= MAR_THRESHOLD:
                accepted_variants.append((phase, str(r["variant"]), float(r["mar"]), float(r["mar_vs_baseline"])))

    accepted_variants.sort(key=lambda x: -x[3])

    tbl = ""
    for ph, var, mar, delta in accepted_variants:
        tbl += f"| {ph} | {var} | {_fmt(mar)} | {_fmt(delta)} | YES |\n"

    if not tbl:
        decision = "CONDITIONAL_NO_CHANGE"
        rationale = ("No coordination variant cleared the MAR ≥ +0.03 threshold. "
                     "A3 production parameters remain unchanged. "
                     "S3 remains PAPER_TRADE_SHADOW. "
                     "Re-evaluate after 12 months live paper data.")
    else:
        decision = "PARTIAL_ADOPTION"
        rationale = (f"The following variants cleared the threshold:\n{chr(10).join(f'  - Phase {ph}: {var}' for ph, var, _, _ in accepted_variants)}\n"
                     "Adoption is advisory (ranking/sizing) and does not change A3 core logic.")

    memo = textwrap.dedent(f"""\
    # Phase36 A3/S3 Coordination Decision Memo

    Date: 2026-05-17
    Status: RESEARCH COMPLETE
    Decision: {decision}

    ---

    ## Context

    Phase36 researched whether A3 and S3 can be coordinated to improve A3 MAR.
    A3 baseline (5B VND, 10% ADV, 20 slots): MAR={A3_BASELINE_MAR:.3f}, CAGR={A3_BASELINE_CAGR:.2%}, MaxDD={A3_BASELINE_DD:.2%}
    Acceptance bar: MAR improvement ≥ +0.03 → need MAR ≥ {MAR_THRESHOLD:.3f}

    ---

    ## Results Summary

    | Phase | Variant | MAR | Δ-MAR | Accepted |
    |-------|---------|-----|-------|---------|
    {tbl if tbl else "| All | All variants | <0.446 | <+0.03 | NO |"}

    ---

    ## Rationale

    {rationale}

    ---

    ## What Does NOT Change

    1. A3 EMA20/100 cloud-breakout entry — LOCKED
    2. A3 TP=18%, trail=2.5×ATR14, max_hold=250 — LOCKED
    3. VNINDEX EMA20>EMA100 hard block for new T1 — LOCKED
    4. Breadth T2 gate (pct_cloud_bull_a3 < 35%) — LOCKED
    5. ADV50 corrected formula (close_kVND × volume × 1000) — LOCKED
    6. S3 = PAPER_TRADE_SHADOW only. No real capital. No DNSE — LOCKED
    7. S3 max_hold=60 — LOCKED
    8. S3 does not gate A3 — LOCKED

    ---

    ## S3 Shadow Status

    Gate 10 (S3 shadow 12 months paper): NOT STARTED
    Gate 11 (S3 combo paper): NOT STARTED

    No S3 upgrade discussion until both gates have live paper evidence.

    ---

    ## Next Review Trigger

    - After 3 months live a3_rank_score tracking (if ranking was adopted)
    - After S3 shadow Gate 10 is met (12 months, MAR≥0.35, MaxDD≤-25%)
    """)

    (OUT / "PHASE36_A3_S3_COORDINATION_DECISION_MEMO.md").write_text(memo, encoding="utf-8")
    print("  PHASE36_A3_S3_COORDINATION_DECISION_MEMO.md written", flush=True)


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Phase36 A3/S3 Coordination Research")
    parser.add_argument("--phase", default="all",
                        help="Phase to run: all, a, b, c, d, e, f, g, h, i")
    args = parser.parse_args()
    phase = args.phase.lower()

    run_all = (phase == "all")

    # ── Load data (always needed) ─────────────────────────────────────────────
    print("Loading panel and VNINDEX...", flush=True)
    panel = load_panel()
    vnx   = load_vnindex()

    print("Building ADV50 map...", flush=True)
    adv50_map = _build_adv50_map(panel)

    print("Building regime gate (EMA20>EMA100)...", flush=True)
    regime = _regime_gate_100(vnx)

    # ── Build signal caches ───────────────────────────────────────────────────
    print("Building A3 signal cache (EMA20/100)...", flush=True)
    a3_cache = _build_signal_cache(panel, "A3")
    print(f"  A3 cache: {len(a3_cache)} symbols", flush=True)

    print("Building S3 signal cache (EMA21/55)...", flush=True)
    s3_cache = _build_signal_cache(panel, "S3")
    print(f"  S3 cache: {len(s3_cache)} symbols", flush=True)

    # ── Build A3 base trades (used by B, C, D) ────────────────────────────────
    print("Building A3 base trades...", flush=True)
    a3_trades_raw = _build_trades(a3_cache, EXIT_A3, gate_by_date=regime)
    a3_trades_raw = _tag_adv50(a3_trades_raw, adv50_map)
    print(f"  A3 trades: {len(a3_trades_raw)}", flush=True)

    print("Tagging lead info onto A3 trades...", flush=True)
    a3_trades = tag_lead_info(a3_trades_raw, s3_cache)
    print(f"  Tagged. Lead_11_20: {a3_trades['s3_lead_bucket'].eq('lead_11_20').sum()}, "
          f"no_s3_lead: {a3_trades['s3_lead_bucket'].eq('no_s3_lead').sum()}", flush=True)

    # ── Run phases ────────────────────────────────────────────────────────────
    all_results: dict[str, pd.DataFrame | None] = {}

    if run_all or phase == "a":
        run_phase_a(a3_cache, s3_cache, regime)

    if run_all or phase == "b":
        all_results["36B"] = run_phase_b(a3_trades, adv50_map)

    if run_all or phase == "c":
        all_results["36C"] = run_phase_c(a3_trades, adv50_map)

    if run_all or phase == "d":
        all_results["36D"] = run_phase_d(a3_trades, adv50_map)

    if run_all or phase == "e":
        all_results["36E"] = run_phase_e(a3_cache, s3_cache, regime, adv50_map)

    if run_all or phase == "f":
        all_results["36F"] = run_phase_f(a3_cache, s3_cache, regime, adv50_map)

    if run_all or phase == "g":
        all_results["36G"] = run_phase_g(a3_cache, s3_cache, regime, adv50_map)

    if run_all or phase == "h":
        run_phase_h(all_results)

    if run_all or phase == "i":
        write_phase_i_docs(all_results)
        write_decision_memo(all_results)

    print("\n=== Phase36 Research Complete ===", flush=True)
    print(f"Outputs in: {OUT}", flush=True)


if __name__ == "__main__":
    main()
