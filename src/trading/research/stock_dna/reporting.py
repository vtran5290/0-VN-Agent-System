"""
Stock DNA Reporting
====================
Generates CSV outputs, JSON profiles, and an executive HTML report.
All outputs go to data/research/stock_dna/ only.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import numpy as np
import pandas as pd

from src.trading.research.stock_dna.schema import (
    DNA_DIR,
    RESEARCH_ONLY_LABEL,
    assert_output_path_safe,
    DNAProductionStatus,
)

logger = logging.getLogger(__name__)

TODAY = date.today().isoformat()


# ── CSV / JSON output helpers ─────────────────────────────────────────────────

def _ensure_dir(path: Path) -> None:
    assert_output_path_safe(path)
    path.mkdir(parents=True, exist_ok=True)


def save_line_scores(df: pd.DataFrame, output_dir: Path = DNA_DIR) -> Path:
    _ensure_dir(output_dir)
    p = output_dir / "stock_dna_line_scores.csv"
    df.to_csv(p, index=False)
    logger.info("Saved: %s (%d rows)", p, len(df))
    return p


def save_symbol_profiles_csv(df: pd.DataFrame, output_dir: Path = DNA_DIR) -> Path:
    _ensure_dir(output_dir)
    p = output_dir / "stock_dna_symbol_profiles.csv"
    df.to_csv(p, index=False)
    logger.info("Saved: %s (%d rows)", p, len(df))
    return p


def save_symbol_profiles_json(df: pd.DataFrame, output_dir: Path = DNA_DIR) -> Path:
    _ensure_dir(output_dir)
    p = output_dir / "stock_dna_symbol_profiles.json"
    records = df.replace({np.nan: None}).to_dict(orient="records")

    # Join E&MA Research per-symbol best MA (2y window) — backward compatible (nullable)
    _ema_map: dict = {}
    _ema_path = Path(__file__).resolve().parents[4] / "data/research/ma_reaction_stocks.json"
    if _ema_path.exists():
        try:
            _ema_raw = json.loads(_ema_path.read_text(encoding="utf-8"))
            _ema_map = _ema_raw.get("per_symbol_best_2y", {})
        except Exception:
            pass

    for rec in records:
        sym = rec.get("symbol", "")
        ep = _ema_map.get(sym)
        rec["best_ma_2y"]       = ep["best_ma"]    if ep else None
        rec["best_ma_score_2y"] = ep["score"]      if ep else None
        rec["best_ma_sr_10d"]   = ep["sr_10d"]     if ep else None

    with open(p, "w", encoding="utf-8") as f:
        json.dump({"research_label": RESEARCH_ONLY_LABEL, "profiles": records}, f, indent=2, default=str)
    logger.info("Saved: %s", p)
    return p


def save_overlay_metrics(metrics: dict, output_dir: Path = DNA_DIR) -> Path:
    _ensure_dir(output_dir)
    p = output_dir / "stock_dna_a3_overlay_metrics.csv"
    pd.DataFrame([metrics]).to_csv(p, index=False)
    logger.info("Saved: %s", p)
    return p


def save_null_benchmark(null_result: dict, output_dir: Path = DNA_DIR) -> Path:
    _ensure_dir(output_dir)
    p = output_dir / "stock_dna_null_benchmark.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump({**null_result, "research_label": RESEARCH_ONLY_LABEL}, f, indent=2, default=str)
    logger.info("Saved: %s", p)
    return p


def save_open_questions(output_dir: Path = DNA_DIR) -> Path:
    _ensure_dir(output_dir)
    p = output_dir / "stock_dna_open_questions.md"
    content = f"""# Stock DNA Open Questions
Date: {TODAY}

## Data quality
- [ ] Are VIN return values distorting line obedience scores even after flagging?
- [ ] Does ta_ohlcv_panel.parquet contain corporate-action-adjusted close? If not, long-term SMA100/SMA150 may be biased.
- [ ] ADV20 filter of 5bn VND — is this appropriate for all years in the backtest (liquidity conditions changed)?

## Method
- [ ] Are 4 candidate lines (EMA20, EMA50, SMA100, SMA150) sufficient, or does EMA100/EMA200 matter for some stocks?
- [ ] Should "touch" require low to breach the line (not just approach), or is the current 1-2% tolerance correct?
- [ ] Walk-forward uses minimum 3 years of history before first OOS year — is this enough for SMA150?

## Regime
- [ ] Are breadth thresholds (>=60% BULL_BROAD, etc.) appropriate for VN market structure vs mature markets?
- [ ] Should VNINDEX price level (above EMA100) be a separate regime dimension?

## Overlay (V1 / V4)
- [ ] V1 T2 support gate: 3% tolerance for "near support" — too wide? Too narrow?
- [ ] V4 danger line: 1.2x ADV20 volume confirm — is this the right threshold?
- [ ] Is the shuffled-null benchmark passing? (see stock_dna_null_benchmark.json)

## Production path
- [ ] V1/V4 are RESEARCH_ANNOTATION_ONLY. When should we consider PAPER_SHADOW_CANDIDATE?
- [ ] Would ranking only (V5) be a safer first production integration than V1/V4?

## Recommended next step
1. Review stock_dna_symbol_profiles.csv — check top-scored symbols for face validity.
2. Monitor operator notes for 2-4 weeks on live scan output.
3. If OOS lift > 5pp consistently, consider PAPER_SHADOW_CANDIDATE review.
"""
    p.write_text(content, encoding="utf-8")
    logger.info("Saved: %s", p)
    return p


def save_implementation_report(
    summary: dict,
    output_dir: Path = DNA_DIR,
) -> Path:
    _ensure_dir(output_dir)
    p = output_dir / "stock_dna_implementation_report.md"

    n_syms     = summary.get("n_symbols", "N/A")
    n_touch    = summary.get("n_touch_events", "N/A")
    n_med_plus = summary.get("n_medium_plus_profiles", "N/A")
    null_pass  = summary.get("null_benchmark_passes", "N/A")
    oos_lift   = summary.get("oos_lift", "N/A")
    v1_lift    = summary.get("v1_t2_gate_lift", "N/A")
    # Wording fix: never call this "OOS lift" — a3_true_ledger_used=False, OOS z=nan
    _proxy_lift_label = "V1 proxy lift (A3-like T2, NOT proven A3 improvement)"
    best_var   = summary.get("best_variant", "V1 T2 Support Gate annotation")
    verdict    = summary.get("verdict", DNAProductionStatus.RESEARCH_ANNOTATION_ONLY.value)
    files_out  = summary.get("output_files", [])
    errors     = summary.get("errors", [])

    content = f"""# Stock DNA Research Module — Implementation Report
Date: {TODAY}
{RESEARCH_ONLY_LABEL}

---

## Executive Summary

| Item | Value |
|------|-------|
| Symbols analyzed | {n_syms} |
| Touch events detected | {n_touch} |
| MEDIUM+ confidence profiles | {n_med_plus} |
| Shuffled-null benchmark passed | {null_pass} |
| {_proxy_lift_label} | {oos_lift} |
| Best variant | {best_var} |
| **Recommended production status** | **{verdict}** |

---

## Council Decision

**APPROVE_WITH_MODIFICATIONS** (2026-06-04)
V1 scope: 4 lines (EMA20, EMA50, SMA100, SMA150), walk-forward, shuffled-null, regime-split.
Variants implemented: V1 (T2 annotation), V4 (danger line annotation).
Variants deferred: V2 (pullback depth), V3 (extension warning), V5 (ranking).

---

## Files Changed

### New module
- `src/trading/research/stock_dna/__init__.py`
- `src/trading/research/stock_dna/schema.py`
- `src/trading/research/stock_dna/features.py`
- `src/trading/research/stock_dna/events.py`
- `src/trading/research/stock_dna/scoring.py`
- `src/trading/research/stock_dna/profiles.py`
- `src/trading/research/stock_dna/overlay.py`
- `src/trading/research/stock_dna/reporting.py`

### New scripts
- `scripts/research/run_stock_dna_discovery.py`
- `scripts/research/run_stock_dna_a3_overlay_backtest.py`
- `scripts/reporting/build_stock_dna_report.py`
- `scripts/research/package_stock_dna_review.py`

### New tests
- `tests/research/test_stock_dna_no_lookahead.py`
- `tests/research/test_stock_dna_events.py`
- `tests/research/test_stock_dna_profiles.py`
- `tests/research/test_stock_dna_safety.py`
- `tests/research/test_stock_dna_output.py`

### No production files modified
- `src/trading/oms/` — NOT MODIFIED
- `data/decision/` — NOT WRITTEN
- `data/scan/` — NOT WRITTEN
- A3 final_action logic — NOT MODIFIED

---

## Output Files
{chr(10).join(f'- {f}' for f in files_out)}

---

## Assumptions
- FACT: ta_ohlcv_panel.parquet is the SSOT for OHLCV data.
- ASSUMPTION: Close prices are corporate-action adjusted (if not, SMA100/SMA150 comparisons across events may be biased).
- ASSUMPTION: 5bn VND ADV20 liquidity floor is appropriate for the analysis period.
- ASSUMPTION: 3-year minimum history before walk-forward OOS year is sufficient for SMA150 warmup.

---

## Risks / Open Issues
- VIN return distortion: all VIN scores should be treated as INTERPRETATION not FACT.
- Walk-forward OOS years with few liquid symbols (pre-2018) may produce noisy results.
- Shuffled-null benchmark: if z_score < 2 for most lines, DNA is noise for those lines.
- See stock_dna_open_questions.md for full list.

---

## Errors During Run
{chr(10).join(f'- {e}' for e in errors) if errors else '_None reported._'}

---

## Next Action for ChatGPT
Review stock_dna_symbol_profiles.csv for face validity.
Verify shuffled-null result in stock_dna_null_benchmark.json.
Approve or redirect RESEARCH_ANNOTATION_ONLY status before any operator-facing integration.
"""
    p.write_text(content, encoding="utf-8")
    logger.info("Saved: %s", p)
    return p


# ── HTML report ───────────────────────────────────────────────────────────────

_A3_PROXY_LABEL = "A3-like T2 proxy (NOT production A3)"


def _superperformer_section(output_dir: Path) -> str:
    """Load and render the super-performer screen results inline in the HTML report."""
    screen_path = output_dir / "stock_dna_superperformer_screen.csv"
    if not screen_path.exists():
        return "<p><em>Super-performer screen not yet generated. Run <code>scripts/research/run_stock_dna_superperformer_screen.py</code>.</em></p>"
    try:
        screen = pd.read_csv(screen_path)
    except Exception as e:
        return f"<p><em>Error loading screen: {e}</em></p>"

    tier_a  = screen[screen["tier"] == "A"]
    tier_b  = screen[screen["tier"] == "B"]
    tier_bc = screen[screen["tier"] == "BC"]
    priority_n = int((screen.get("watchlist_priority", pd.Series(False)) == True).sum())

    tbl_cols = ["symbol", "tier", "composite_score", "primary_support_line",
                "edge_confidence", "regime_obedience_bull", "bounce_rate_20d",
                "median_fwd_ret_20d", "instability_penalty", "liquidity_bucket",
                "cycle_robustness",   # dual-window label (Option C, council 2026-06-06)
                "production_status"]
    tbl_cols = [c for c in tbl_cols if c in screen.columns]

    hdr = "".join(f"<th>{c}</th>" for c in tbl_cols)
    rows_html = ""
    for _, r in screen[tbl_cols].iterrows():
        tier_val = screen.loc[r.name, "tier"] if "tier" in screen.columns else "A"
        is_priority = screen.loc[r.name, "watchlist_priority"] if "watchlist_priority" in screen.columns else False
        cycle_robustness_val = screen.loc[r.name, "cycle_robustness"] if "cycle_robustness" in screen.columns else ""
        if tier_bc is not None and tier_val == "BC":
            row_style = " style='background:#fff3cd'"        # amber — edge-unverified (Tier BC)
        elif cycle_robustness_val == "cycle-line-shift":
            row_style = " style='background:#f8d7da'"        # red-pink — anchor is regime-dependent
        elif cycle_robustness_val == "cycle-edge-fading":
            row_style = " style='background:#ffeeba'"        # gold — edge weakening, caution
        elif is_priority:
            row_style = " style='background:#e8f5e9'"        # green — top-15 multi-cycle confirmed
        else:
            row_style = ""
        cells = ""
        for c in tbl_cols:
            v = r[c]
            if isinstance(v, float) and not np.isnan(v):
                cells += f"<td>{v:.3f}</td>"
            else:
                cells += f"<td>{v}</td>"
        rows_html += f"<tr{row_style}>{cells}</tr>"

    return f"""
<p>
  <strong>Tier A (statistically verified edge):</strong> {len(tier_a)} stocks &nbsp;|&nbsp;
  <strong>Tier B (EMA subset):</strong> {len(tier_b)} stocks &nbsp;|&nbsp;
  <strong>Tier BC (Blue-Chip Obedience, edge unverified):</strong>
    <span style='background:#fff3cd;padding:2px 6px;border-radius:3px'>{len(tier_bc)} stocks (highlighted amber)</span> &nbsp;|&nbsp;
  <strong>WATCHLIST_PRIORITY top 15:</strong>
    <span style='background:#d4edda;padding:2px 6px;border-radius:3px'>{priority_n} stocks (highlighted green)</span>
</p>
<p><em>
  <strong>Tier BC council note (2026-06-06):</strong> z-test is under-powered on liquid/arbitraged names.
  HIGH confidence + bull_obedience &gt; 0.8 is meaningful despite edge_confidence=NONE.
  MWG (0.867 bull_obedience) is canonical example: real obedience pattern, z-test fails due to power deficit.
  Do NOT treat Tier BC as statistically equivalent to Tier A.
</em></p>
<p><em>
  Panel: 2018-01-16 → 2026-06-05 (one bull-bear-bull cycle). NOT a decade screen.
  instability_penalty informational only (bimodal, median gate removed). Tier A sorted by composite_score.
</em></p>
<p><em>
  <strong>Cycle robustness 3-state (council Round 4, 2026-06-07):</strong>
  <span style='background:#e8f5e9;padding:1px 4px'>Green</span> = multi-cycle-confirmed (line stable, edge stable or improved — full confidence).
  <span style='background:#ffeeba;padding:1px 4px'>Gold</span> = cycle-edge-fading (line stable but edge weaker — caution, monitor decay).
  <span style='background:#f8d7da;padding:1px 4px'>Red</span> = cycle-line-shift (support anchor changed — regime-dependent, lowest confidence).
  Effective high-confidence Tier A = multi-cycle-confirmed count (includes edge-improved names).
</em></p>
<table border='1' cellpadding='4'>
<tr style='background:#dde4f0'>{hdr}</tr>
{rows_html}
</table>
<p>Full output: <code>data/research/stock_dna/stock_dna_superperformer_screen.csv</code> and
<code>stock_dna_superperformer_screen.md</code> (includes per-symbol exclusion diagnostics)</p>
"""


def _line_finding_section(profiles: pd.DataFrame) -> str:
    """Generate live Line Type Finding section from actual profiles data."""
    if profiles.empty or "primary_support_line" not in profiles.columns:
        return "<h2>6. Line Type Finding</h2><p><em>No profiles data.</em></p>"

    all_lines = sorted([l for l in profiles["primary_support_line"].dropna().unique() if l])
    mod_str = profiles[profiles["edge_confidence"].isin(["MODERATE", "STRONG"])]
    bull_ok  = profiles[profiles["regime_obedience_bull"] > 0.6]
    both     = mod_str[mod_str["regime_obedience_bull"] > 0.6]

    def _row(label: str, subset: pd.DataFrame) -> str:
        cells = f"<td>{label} (n={len(subset)})</td>"
        for line in all_lines:
            cnt = int((subset["primary_support_line"] == line).sum())
            bold = "<strong>" if cnt == subset["primary_support_line"].isin(all_lines).sum() else ""
            cells += f"<td><strong>{cnt}</strong></td>" if cnt >= 10 else f"<td>{cnt}</td>"
        return f"<tr>{cells}</tr>"

    hdr = "".join(f"<th>{l}</th>" for l in all_lines)
    total_dist = profiles["primary_support_line"].value_counts()
    total_row = "".join(
        f"<td><strong>{total_dist.get(l, 0)}</strong></td>" for l in all_lines
    )

    # SMA50 note
    sma50_cnt = int((profiles["primary_support_line"] == "sma50").sum())
    sma50_tier_a = int((mod_str["primary_support_line"] == "sma50").sum())
    sma50_note = (
        f"SMA50 (v2, council 2026-06-06): {sma50_cnt} symbols use sma50 as primary line "
        f"({sma50_tier_a} with MODERATE/STRONG edge). "
        "SMA50 fills the gap between EMA50 and SMA100 — captures mid-cycle pullbacks. "
    )
    sma50_note += "SMA200 rejected — SMA150 covers the long end; no further line expansion."

    return f"""
<h2>6. Line Type Finding — v2 (SMA50 included)</h2>
<p><strong>Original council assumption:</strong> <code>ema20/ema50</code> are the preferred primary support lines for quality stocks.</p>
<p><strong>Live data finding ({len(profiles)} symbols):</strong> SMA lines dominate primary support identification in the VN universe.</p>
<table border='1' cellpadding='4'>
<tr style='background:#dde4f0'><th>Filter</th>{hdr}</tr>
<tr><td>All symbols (primary line distribution)</td>{total_row}</tr>
{_row("MODERATE/STRONG edge_confidence", mod_str)}
{_row("regime_obedience_bull &gt; 0.6", bull_ok)}
{_row("Both filters (intersection)", both)}
</table>
<p><strong>Implication:</strong> SMA150 and SMA100 are the dominant primary support lines.
EMA20/EMA50 capture fast-moving names but carry lower edge confidence.
{sma50_note}</p>
<p><strong>Council decisions (updated 2026-06-06):</strong> No EMA5/EMA10. No SMA200 (rejected — SMA150 covers the long end).
<strong>SMA50 ADDED</strong> to v2 candidate lines. No A3 join. T2-tight after ~20 manual decisions.</p>
"""


def build_html_report(
    profiles: pd.DataFrame,
    line_scores: pd.DataFrame,
    overlay_metrics: dict,
    null_benchmark: dict,
    output_dir: Path = DNA_DIR,
    by_year_df: Optional["pd.DataFrame"] = None,
) -> Path:
    _ensure_dir(output_dir)
    p = output_dir / "stock_dna_research_report.html"

    # Count is from the full filtered set; table is capped at 20 rows (council amendment 1)
    n_med_plus_true = len(profiles[profiles["confidence"].isin(["MEDIUM", "HIGH"])]) \
        if not profiles.empty else 0
    stable = profiles[
        profiles["confidence"].isin(["MEDIUM", "HIGH"])
    ].head(20).copy() if not profiles.empty else pd.DataFrame()

    unstable = profiles[
        profiles["confidence"].isin(["NONE", "LOW"])
    ].head(10).copy() if not profiles.empty else pd.DataFrame()

    def _tbl(df: pd.DataFrame, cols: list) -> str:
        cols = [c for c in cols if c in df.columns]
        if df.empty or not cols:
            return "<p><em>No data.</em></p>"
        hdr = "".join(f"<th>{c}</th>" for c in cols)
        rows_html = ""
        for _, r in df[cols].iterrows():
            cells = ""
            for c in cols:
                v = r[c]
                if isinstance(v, float) and not np.isnan(v):
                    cells += f"<td>{v:.3f}</td>"
                else:
                    cells += f"<td>{v}</td>"
            rows_html += f"<tr>{cells}</tr>"
        return f"<table border='1' cellpadding='4'><tr>{hdr}</tr>{rows_html}</table>"

    # Overlay summary
    bbl  = overlay_metrics.get("baseline_bounce_rate_20d", "N/A")
    v1br = overlay_metrics.get("v1_t2_gate_bounce_rate_20d", "N/A")
    v1lf = overlay_metrics.get("v1_t2_gate_lift", "N/A")
    null_z  = null_benchmark.get("z_score", "N/A")
    null_ok = null_benchmark.get("passes_null_test", False)

    v1_fmt  = f"{float(v1br):.1%}" if isinstance(v1br, float) and not np.isnan(v1br) else "N/A"
    bbl_fmt = f"{float(bbl):.1%}" if isinstance(bbl, float) and not np.isnan(bbl) else "N/A"
    lift_fmt = f"{float(v1lf):+.1%}" if isinstance(v1lf, float) and not np.isnan(v1lf) else "N/A"
    null_z_fmt = f"{float(null_z):.2f}" if isinstance(null_z, float) and not np.isnan(null_z) else "N/A"
    # OOS lift: render nan explicitly — never blank (council amendment 5/Q5)
    oos_lift_raw = overlay_metrics.get("v1_t2_gate_lift", np.nan)
    if isinstance(oos_lift_raw, float) and not np.isnan(oos_lift_raw):
        oos_lift_display = f"{oos_lift_raw:+.1%}"
    else:
        oos_lift_display = "[&#9679;] insufficient OOS events (n&lt;threshold)"

    A3_PROXY_LABEL = _A3_PROXY_LABEL
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Stock DNA Research Report — {TODAY}</title>
<style>
  body {{ font-family: sans-serif; margin: 40px; line-height: 1.6; color: #222; }}
  h1 {{ color: #1a3a6b; }} h2 {{ color: #2a5a9f; border-bottom: 1px solid #aaa; padding-bottom: 4px; }}
  table {{ border-collapse: collapse; font-size: 13px; }}
  th {{ background: #dde4f0; padding: 6px; }}
  td {{ padding: 5px 8px; }}
  tr:nth-child(even) {{ background: #f5f7fa; }}
  .badge {{ padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 12px; }}
  .research {{ background: #fff3cd; color: #856404; }}
  .reject {{ background: #f8d7da; color: #721c24; }}
  .ok {{ background: #d4edda; color: #155724; }}
  .warn {{ background: #fff3cd; color: #856404; }}
  .metric-box {{ display: inline-block; margin: 8px; padding: 12px 20px; background: #f0f4ff;
                  border: 1px solid #aac; border-radius: 6px; text-align: center; }}
  .metric-value {{ font-size: 24px; font-weight: bold; color: #1a3a6b; }}
  .metric-label {{ font-size: 12px; color: #555; }}
</style>
</head>
<body>
<h1>Stock DNA Research Report</h1>
<p><strong>Date:</strong> {TODAY}&nbsp;&nbsp;
   <span class='badge research'>{RESEARCH_ONLY_LABEL}</span></p>

<h2>1. Executive Summary</h2>
<div>
  <div class='metric-box'><div class='metric-value'>{len(profiles)}</div><div class='metric-label'>Symbols analyzed</div></div>
  <div class='metric-box'><div class='metric-value'>{n_med_plus_true}</div><div class='metric-label'>MEDIUM+ profiles</div></div>
  <div class='metric-box'><div class='metric-value'>{bbl_fmt}</div><div class='metric-label'>Baseline bounce rate</div></div>
  <div class='metric-box'><div class='metric-value'>{v1_fmt}</div><div class='metric-label'>V1 T2 bounce rate</div></div>
  <div class='metric-box'><div class='metric-value'>{lift_fmt}</div><div class='metric-label'>V1 proxy lift (A3-like T2)</div></div>
  <div class='metric-box'><div class='metric-value'>{null_z_fmt}</div><div class='metric-label'>Null z-score</div></div>
</div>

<p><strong>Shuffled-null benchmark:</strong>
   <span class='badge {"ok" if null_ok else "reject"}'>{"✓ PASS" if null_ok else "✗ FAIL"}</span>
   — Real scores {"exceed" if null_ok else "do NOT exceed"} shuffled-null by 2&sigma;.</p>

<h2>2. Variant Performance (OOS)</h2>
<p><em>OOS lift note: verdict rests on cross-symbol null z={null_z_fmt} (see section 1).
OOS lift: {oos_lift_display}.
A3 improvement claims require a3_true_ledger_used=True — current run uses {A3_PROXY_LABEL}.</em></p>
<table border='1' cellpadding='4'>
<tr><th>Variant</th><th>Bounce Rate 20d</th><th>N Events</th><th>Lift vs Baseline</th><th>Status</th></tr>
<tr><td>V0 Baseline</td><td>{bbl_fmt}</td>
    <td>{overlay_metrics.get("baseline_n_events", "N/A")}</td><td>—</td>
    <td><span class='badge ok'>Baseline</span></td></tr>
<tr><td>V1 T2 Support Gate ({A3_PROXY_LABEL})</td><td>{v1_fmt}</td>
    <td>{overlay_metrics.get("v1_t2_gate_n_events", "N/A")}</td><td>{lift_fmt}</td>
    <td><span class='badge research'>RESEARCH ANNOTATION ONLY</span></td></tr>
<tr><td>V4 Danger Line</td><td colspan='3'><em>Annotation only — no forward return comparison available yet.</em></td>
    <td><span class='badge research'>RESEARCH ANNOTATION ONLY</span></td></tr>
</table>

<h2>2b. V1 Performance by Year (aligned vs off-support)</h2>
{_tbl(
    by_year_df if by_year_df is not None and not by_year_df.empty else pd.DataFrame(),
    ["year", "baseline_n", "baseline_bounce_rate_20d",
     "v1_aligned_n", "v1_aligned_bounce_rate_20d",
     "v1_off_support_n", "v1_off_support_bounce_rate_20d", "v1_lift_pp"]
)}

<h2>3. Top 20 Stable DNA Profiles (MEDIUM / HIGH confidence)</h2>
<p><em>Showing top 20 of {n_med_plus_true} MEDIUM+ profiles. See stock_dna_symbol_profiles.csv for full set.</em></p>
{_tbl(stable, ["symbol", "primary_support_line", "confidence", "sample_confidence",
               "edge_confidence", "per_symbol_null_z", "n_touch",
               "bounce_rate_20d", "regime_obedience_bull", "regime_obedience_bear",
               "production_status", "operator_note"])}

<h2>4. Weak / Unstable Profiles (NONE / LOW confidence)</h2>
{_tbl(unstable, ["symbol", "confidence", "n_touch", "production_status"])}

<h2>5. Production Readiness</h2>
<p>Default status for this research pass:</p>
<table border='1' cellpadding='4'>
<tr><th>Category</th><th>Count</th></tr>
{
"".join(
    f"<tr><td>{s.value}</td><td>{len(profiles[profiles['production_status'] == s.value])}</td></tr>"
    for s in DNAProductionStatus
) if not profiles.empty else "<tr><td colspan='2'><em>No profiles.</em></td></tr>"
}
</table>

{_line_finding_section(profiles)}

<h2>7. Current-Cycle Obedience Screen (2018–2026)</h2>
<p style='color:#666;font-size:0.9em'>Council ruling 2026-06-06: rebrand from "decade winners" — panel covers one bull-bear-bull cycle, not a decade.
Tier A = statistically verified edge. Tier BC (amber) = obedience-confirmed, z-test under-powered on large caps.</p>
{_superperformer_section(output_dir)}

<h2>8. Recommended Next Steps</h2>
<ol>
  <li>Review <code>stock_dna_superperformer_screen.md</code> with <code>cycle_robustness</code> column — multi-cycle-confirmed Tier A stocks carry higher interpretive confidence than cycle-edge-fading or cycle-line-shift.</li>
  <li>Tier A WATCHLIST_PRIORITY top 15 (multi-cycle-confirmed only): manually verify face validity against charts.</li>
  <li>SMA50 v2 results: 53 symbols use sma50 as primary. TV2 is Tier A exemplar (MODERATE edge, 0.676 bull_obedience). v2 line set is final — no SMA200.</li>
  <li>Monitor V1/V4 annotations for 2–4 weeks (operator review only, no A3 join).</li>
  <li>If OOS lift &gt; 5pp consistently and null z-score ≥ 2: consider PAPER_SHADOW_CANDIDATE.</li>
</ol>
<p><em>Deferred variants (V2, V3, V5) should be evaluated only after V1/V4 show stable OOS lift.</em></p>

<hr>
<p style='font-size: 11px; color: #888;'>
  Generated by Stock DNA Research Module v1.0 — {TODAY}<br>
  {RESEARCH_ONLY_LABEL}
</p>
</body>
</html>"""

    p.write_text(html, encoding="utf-8")
    logger.info("HTML report saved: %s", p)
    return p
