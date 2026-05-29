"""P3.1 Coverage / Price-Path QA for Institutional Accumulation Backtest.

RESEARCH_ONLY_NOT_PRODUCTION — no A3/S3/OMS/final_action/DNSE/live-order paths touched.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import numpy as np

from .p2_variants import P3_VARIANT_MAP, build_variant_masks, enrich_outcomes

RESEARCH_ONLY_FLAG = "RESEARCH_ONLY_NOT_PRODUCTION"

ALLOWED_QA_LABELS = {
    "TRUE_SIGNAL_SPARSE",
    "PRICE_ALIGNMENT_ISSUE",
    "TICKER_COVERAGE_ISSUE",
    "EXIT_DATE_ALIGNMENT_ISSUE",
    "VARIANT_TOO_RESTRICTIVE",
    "SELECTION_LOGIC_ISSUE",
    "INCONCLUSIVE",
}

LIQUID_THRESHOLD_20B = 20_000_000_000.0
LIQUID_THRESHOLD_10B = 10_000_000_000.0
LIQUID_THRESHOLD_5B = 5_000_000_000.0
LIQUID_THRESHOLD_2B = 2_000_000_000.0

HOLDING_WEEKS_OPTIONS = (2, 4, 8, 12)


# ---------------------------------------------------------------------------
# Stage funnel helpers
# ---------------------------------------------------------------------------


def _adv50(df: pd.DataFrame) -> pd.Series:
    return pd.to_numeric(df.get("adv50_vnd"), errors="coerce")


def _liquid_mask(df: pd.DataFrame, threshold: float = LIQUID_THRESHOLD_20B) -> pd.Series:
    return _adv50(df) >= threshold


def _v4_mask(df: pd.DataFrame) -> pd.Series:
    return df.get("distribution_risk_flag", pd.Series(False, index=df.index)) == False  # noqa: E712


def _variant_mask(df: pd.DataFrame, variant_key: str) -> pd.Series:
    enriched = enrich_outcomes(df)
    masks = build_variant_masks(enriched)
    if variant_key not in masks:
        return pd.Series(True, index=df.index)
    return masks[variant_key][1]


# ---------------------------------------------------------------------------
# Per-scan candidate loss funnel
# ---------------------------------------------------------------------------


def build_candidate_loss_funnel(
    df: pd.DataFrame,
    variant_key: str = "V4_NO_DISTRIBUTION_RISK",
    liquid_threshold: float = LIQUID_THRESHOLD_20B,
    top_n: int = 30,
) -> pd.DataFrame:
    """Track candidate count at each stage for every scan date."""
    enriched = enrich_outcomes(df.copy())
    enriched["scan_date"] = pd.to_datetime(enriched["scan_date"])

    liq = _liquid_mask(enriched, liquid_threshold)
    var_mask = _variant_mask(enriched, variant_key)
    has_entry = enriched["entry_price_open_t1"].notna()

    rows: list[dict[str, Any]] = []
    for dt, g in enriched.groupby("scan_date"):
        g_idx = g.index
        n_raw = len(g)
        n_liquid = int(liq.reindex(g_idx, fill_value=False).sum())
        n_variant = int((var_mask.reindex(g_idx, fill_value=False)).sum())
        n_var_liq = int((var_mask.reindex(g_idx, fill_value=False) & liq.reindex(g_idx, fill_value=False)).sum())
        n_entry = int((var_mask.reindex(g_idx, fill_value=False) & liq.reindex(g_idx, fill_value=False) & has_entry.reindex(g_idx, fill_value=False)).sum())
        n_selected = min(n_entry, top_n)
        rows.append(
            {
                "scan_date": dt,
                "stage_1_raw_universe": n_raw,
                "stage_2_liquid": n_liquid,
                "stage_3_variant_mask": n_variant,
                "stage_4_variant_and_liquid": n_var_liq,
                "stage_5_valid_entry_price": n_entry,
                "stage_6_selected_top_n": n_selected,
                "top_n": top_n,
                "variant_key": variant_key,
                "liquid_threshold": liquid_threshold,
                "research_only_flag": RESEARCH_ONLY_FLAG,
            }
        )
    return pd.DataFrame(rows)


def summarize_coverage_audit(funnel: pd.DataFrame) -> pd.DataFrame:
    """Aggregate the funnel into a single-row summary with QA label."""
    if funnel.empty:
        return pd.DataFrame()

    n_scans = len(funnel)
    rows = []
    for stage in (
        "stage_1_raw_universe",
        "stage_2_liquid",
        "stage_3_variant_mask",
        "stage_4_variant_and_liquid",
        "stage_5_valid_entry_price",
        "stage_6_selected_top_n",
    ):
        col = funnel[stage]
        rows.append(
            {
                "stage": stage,
                "mean_per_scan": float(col.mean()),
                "median_per_scan": float(col.median()),
                "min_per_scan": int(col.min()),
                "max_per_scan": int(col.max()),
                "scans_with_zero": int((col == 0).sum()),
                "scans_with_lt_10": int((col < 10).sum()),
                "total_across_scans": int(col.sum()),
                "n_scans": n_scans,
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Price-path audit
# ---------------------------------------------------------------------------


def build_price_path_audit(
    df: pd.DataFrame,
    liquid_threshold: float = LIQUID_THRESHOLD_20B,
) -> pd.DataFrame:
    """For liquid candidates, audit entry and exit price availability."""
    enriched = df.copy()
    enriched["scan_date"] = pd.to_datetime(enriched["scan_date"])
    liq = _liquid_mask(enriched, liquid_threshold)
    sub = enriched[liq].copy()

    if sub.empty:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for dt, g in sub.groupby("scan_date"):
        n = len(g)
        n_entry_ok = int(g["entry_price_open_t1"].notna().sum())
        n_entry_missing = n - n_entry_ok

        # Check forward return availability as exit-price proxy
        n_ret5_ok = int(g["ret_5d"].notna().sum())
        n_ret20_ok = int(g["ret_20d"].notna().sum())
        n_ret60_ok = int(g["ret_60d"].notna().sum())

        n_exit_5d_missing = n_entry_ok - n_ret5_ok
        n_exit_20d_missing = n_entry_ok - n_ret20_ok

        rows.append(
            {
                "scan_date": dt,
                "liquid_candidates": n,
                "entry_price_ok": n_entry_ok,
                "entry_price_missing": n_entry_missing,
                "ret5d_ok": n_ret5_ok,
                "ret20d_ok": n_ret20_ok,
                "ret60d_ok": n_ret60_ok,
                "exit_5d_missing": n_exit_5d_missing,
                "exit_20d_missing": n_exit_20d_missing,
                "entry_miss_pct": round(100.0 * n_entry_missing / n, 2) if n else 0.0,
                "research_only_flag": RESEARCH_ONLY_FLAG,
            }
        )
    return pd.DataFrame(rows)


def build_missing_price_reasons(
    df: pd.DataFrame,
    liquid_threshold: float = LIQUID_THRESHOLD_20B,
) -> pd.DataFrame:
    """For rows missing entry prices, categorise likely reason."""
    enriched = df.copy()
    enriched["scan_date"] = pd.to_datetime(enriched["scan_date"])
    liq = _liquid_mask(enriched, liquid_threshold)
    missing = enriched[liq & enriched["entry_price_open_t1"].isna()].copy()

    if missing.empty:
        return pd.DataFrame(columns=["reason", "n"])

    reasons: list[dict[str, Any]] = []
    for _, r in missing.iterrows():
        reason = "TICKER_COVERAGE_ISSUE"
        if pd.isna(r.get("close")) or r.get("close", 0) <= 0:
            reason = "PRICE_ALIGNMENT_ISSUE"
        elif pd.isna(r.get("adv50_vnd")):
            reason = "TICKER_COVERAGE_ISSUE"
        reasons.append(
            {
                "ticker": r.get("ticker"),
                "scan_date": r.get("scan_date"),
                "reason": reason,
                "adv50_vnd": r.get("adv50_vnd"),
                "close": r.get("close"),
                "research_only_flag": RESEARCH_ONLY_FLAG,
            }
        )
    out = pd.DataFrame(reasons)
    return out


# ---------------------------------------------------------------------------
# Candidate density by week / year
# ---------------------------------------------------------------------------


def candidate_density_by_week(
    df: pd.DataFrame,
    liquid_threshold: float = LIQUID_THRESHOLD_20B,
    variant_key: str = "V4_NO_DISTRIBUTION_RISK",
) -> pd.DataFrame:
    enriched = enrich_outcomes(df.copy())
    enriched["scan_date"] = pd.to_datetime(enriched["scan_date"])
    liq = _liquid_mask(enriched, liquid_threshold)
    var_mask = _variant_mask(enriched, variant_key)

    rows: list[dict[str, Any]] = []
    for dt, g in enriched.groupby("scan_date"):
        g_idx = g.index
        n_raw = len(g)
        n_liq = int(liq.reindex(g_idx, fill_value=False).sum())
        n_var_liq = int((var_mask.reindex(g_idx, fill_value=False) & liq.reindex(g_idx, fill_value=False)).sum())

        for top_n in (10, 20, 30):
            rows.append(
                {
                    "scan_date": dt,
                    "raw_universe": n_raw,
                    "liquid_candidates": n_liq,
                    "variant_and_liquid": n_var_liq,
                    "would_fill_top_n": n_var_liq >= top_n,
                    "top_n": top_n,
                    "variant_key": variant_key,
                    "liquid_threshold": liquid_threshold,
                    "research_only_flag": RESEARCH_ONLY_FLAG,
                }
            )
    return pd.DataFrame(rows)


def candidate_density_by_year(
    df: pd.DataFrame,
    liquid_threshold: float = LIQUID_THRESHOLD_20B,
    variant_key: str = "V4_NO_DISTRIBUTION_RISK",
) -> pd.DataFrame:
    enriched = enrich_outcomes(df.copy())
    enriched["scan_date"] = pd.to_datetime(enriched["scan_date"])
    enriched["year"] = enriched["scan_date"].dt.year
    liq = _liquid_mask(enriched, liquid_threshold)
    var_mask = _variant_mask(enriched, variant_key)

    rows: list[dict[str, Any]] = []
    for year, g in enriched.groupby("year"):
        g_idx = g.index
        n_rows = len(g)
        n_scans = int(g["scan_date"].nunique())
        n_liq = int(liq.reindex(g_idx, fill_value=False).sum())
        n_var_liq = int((var_mask.reindex(g_idx, fill_value=False) & liq.reindex(g_idx, fill_value=False)).sum())
        liq_per_scan = n_liq / n_scans if n_scans else 0.0
        zero_liq_scans = int(
            g.groupby("scan_date").apply(lambda gd: int(liq.reindex(gd.index, fill_value=False).sum()) == 0).sum()
        )
        rows.append(
            {
                "year": int(year),
                "scan_count": n_scans,
                "row_count": n_rows,
                "liquid_rows": n_liq,
                "variant_and_liquid_rows": n_var_liq,
                "avg_liquid_per_scan": round(liq_per_scan, 2),
                "scans_with_zero_liquid": zero_liq_scans,
                "coverage_pct": round(100.0 * n_liq / n_rows, 2) if n_rows else 0.0,
                "variant_key": variant_key,
                "liquid_threshold": liquid_threshold,
                "research_only_flag": RESEARCH_ONLY_FLAG,
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Holding-period QA (uses pre-computed forward returns)
# ---------------------------------------------------------------------------


def holding_period_qa(
    df: pd.DataFrame,
    liquid_threshold: float = LIQUID_THRESHOLD_20B,
    variant_key: str = "V4_NO_DISTRIBUTION_RISK",
    top_n: int = 30,
) -> pd.DataFrame:
    """QA using fixed-horizon forward returns instead of next-scan-date exit.

    Uses pre-computed ret_{n}d columns so no additional price lookups needed.
    """
    enriched = enrich_outcomes(df.copy())
    enriched["scan_date"] = pd.to_datetime(enriched["scan_date"])
    liq = _liquid_mask(enriched, liquid_threshold)
    var_mask = _variant_mask(enriched, variant_key)

    candidates = enriched[
        liq.reindex(enriched.index, fill_value=False) & var_mask.reindex(enriched.index, fill_value=False)
    ].copy()

    rows: list[dict[str, Any]] = []
    for dt, g in candidates.groupby("scan_date"):
        ranked = g.sort_values("institutional_accumulation_score", ascending=False).head(top_n)
        n_held = len(ranked)
        for weeks in HOLDING_WEEKS_OPTIONS:
            trading_days = weeks * 5
            col_approx = None
            for h in (5, 10, 20, 60, 120):
                if trading_days <= h:
                    col_approx = f"ret_{h}d"
                    break
            if col_approx is None:
                col_approx = "ret_120d"

            ret_vals = pd.to_numeric(ranked[col_approx], errors="coerce").dropna()
            bench_col = f"vnindex_ret_{col_approx.split('_')[1]}"
            bench_vals = pd.to_numeric(ranked.get(bench_col, pd.Series(dtype=float)), errors="coerce").dropna()

            rows.append(
                {
                    "scan_date": dt,
                    "holding_weeks": weeks,
                    "return_column_used": col_approx,
                    "n_held": n_held,
                    "n_with_return": len(ret_vals),
                    "mean_return": float(ret_vals.mean()) if len(ret_vals) else None,
                    "median_return": float(ret_vals.median()) if len(ret_vals) else None,
                    "mean_bench_return": float(bench_vals.mean()) if len(bench_vals) else None,
                    "hit_rate": float((ret_vals > 0).mean()) if len(ret_vals) else None,
                    "variant_key": variant_key,
                    "liquid_threshold": liquid_threshold,
                    "top_n": top_n,
                    "research_only_flag": RESEARCH_ONLY_FLAG,
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# QA label assignment
# ---------------------------------------------------------------------------


def assign_qa_label(
    funnel_summary: pd.DataFrame,
    price_path_audit: pd.DataFrame,
) -> tuple[str, str]:
    """Assign a single QA label based on where candidates are lost."""
    if funnel_summary.empty:
        return "INCONCLUSIVE", "funnel summary unavailable"

    raw_row = funnel_summary[funnel_summary["stage"] == "stage_1_raw_universe"]
    liq_row = funnel_summary[funnel_summary["stage"] == "stage_2_liquid"]
    varl_row = funnel_summary[funnel_summary["stage"] == "stage_4_variant_and_liquid"]
    entry_row = funnel_summary[funnel_summary["stage"] == "stage_5_valid_entry_price"]

    mean_raw = float(raw_row["mean_per_scan"].iloc[0]) if not raw_row.empty else 0.0
    mean_liq = float(liq_row["mean_per_scan"].iloc[0]) if not liq_row.empty else 0.0
    mean_varl = float(varl_row["mean_per_scan"].iloc[0]) if not varl_row.empty else 0.0
    mean_entry = float(entry_row["mean_per_scan"].iloc[0]) if not entry_row.empty else 0.0
    zero_liq = int(liq_row["scans_with_zero"].iloc[0]) if not liq_row.empty else 0
    zero_varl = int(varl_row["scans_with_zero"].iloc[0]) if not varl_row.empty else 0
    n_scans = int(raw_row["n_scans"].iloc[0]) if not raw_row.empty else 1

    # Loss at liquidity stage: >50% of scans have zero liquid candidates
    liq_zero_pct = zero_liq / n_scans if n_scans else 1.0
    if liq_zero_pct > 0.50:
        return (
            "VARIANT_TOO_RESTRICTIVE",
            f"liquidity filter zeros out {liq_zero_pct:.0%} of scans (mean_liquid={mean_liq:.1f}/scan). "
            f"Threshold too high for historical universe coverage.",
        )

    # Loss at variant stage (after liquid is fine)
    if mean_liq >= 10 and mean_varl < 5:
        return (
            "VARIANT_TOO_RESTRICTIVE",
            f"variant filter reduces mean candidates from {mean_liq:.1f} to {mean_varl:.1f}/scan",
        )

    # Price path issues
    if not price_path_audit.empty:
        entry_miss_mean = float(price_path_audit["entry_miss_pct"].mean())
        if entry_miss_mean > 20:
            return "PRICE_ALIGNMENT_ISSUE", f"mean entry-price miss rate {entry_miss_mean:.1f}%"

    # Ticker coverage
    if mean_liq < 5 and mean_raw > 50:
        return (
            "TICKER_COVERAGE_ISSUE",
            f"low liquid count ({mean_liq:.1f}) vs high raw universe ({mean_raw:.1f}); check OHLCV file coverage",
        )

    if mean_varl >= 10 and mean_entry < mean_varl * 0.7:
        return (
            "PRICE_ALIGNMENT_ISSUE",
            f"entry price drops from {mean_varl:.1f} to {mean_entry:.1f} after price validation",
        )

    if mean_entry >= 10:
        return "TRUE_SIGNAL_SPARSE", f"candidates are available ({mean_entry:.1f}/scan) but holdings still low — check selection logic"

    return "INCONCLUSIVE", f"mean_raw={mean_raw:.1f}, mean_liq={mean_liq:.1f}, mean_varl={mean_varl:.1f}"


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------


def _fmt(v: Any, decimals: int = 2) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if isinstance(v, float):
        return f"{v:.{decimals}f}"
    return str(v)


def _df_to_html_table(df: pd.DataFrame, max_rows: int = 200) -> str:
    if df.empty:
        return "<p><em>No data</em></p>"
    sub = df.head(max_rows)
    cols = list(sub.columns)
    header = "".join(f"<th>{c}</th>" for c in cols)
    body_rows = []
    for _, r in sub.iterrows():
        cells = "".join(f"<td>{_fmt(r[c])}</td>" for c in cols)
        body_rows.append(f"<tr>{cells}</tr>")
    body = "\n".join(body_rows)
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html_report(
    funnel_by_scan: pd.DataFrame,
    funnel_summary: pd.DataFrame,
    price_path_audit: pd.DataFrame,
    density_by_week: pd.DataFrame,
    density_by_year: pd.DataFrame,
    missing_price_reasons: pd.DataFrame,
    holding_period: pd.DataFrame,
    qa_label: str,
    qa_note: str,
    run_date: str,
) -> str:
    # Holding-period aggregate
    if not holding_period.empty:
        hp_agg = (
            holding_period.groupby("holding_weeks")
            .agg(
                n_scans=("scan_date", "nunique"),
                mean_holdings=("n_held", "mean"),
                mean_return=("mean_return", "mean"),
                mean_bench=("mean_bench_return", "mean"),
                hit_rate=("hit_rate", "mean"),
            )
            .reset_index()
        )
    else:
        hp_agg = pd.DataFrame()

    density_year_v4 = density_by_year[density_by_year["variant_key"] == "V4_NO_DISTRIBUTION_RISK"] if not density_by_year.empty else pd.DataFrame()

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>P3.1 Coverage QA — Institutional Accumulation Backtest</title>
<style>
body {{font-family:system-ui,sans-serif;max-width:1400px;margin:0 auto;padding:1.5rem;background:#fafafa;color:#111;}}
h1{{color:#1a1a6e;}} h2{{color:#2a2a7e;border-bottom:2px solid #ccd;padding-bottom:4px;}} h3{{color:#3a3a8e;}}
.banner {{background:#fff3cd;border:2px solid #ffc107;padding:1rem;border-radius:6px;margin-bottom:1.5rem;font-weight:bold;}}
.label {{display:inline-block;padding:4px 12px;border-radius:4px;font-weight:bold;margin:4px;}}
.VARIANT_TOO_RESTRICTIVE {{background:#f8d7da;color:#721c24;}}
.PRICE_ALIGNMENT_ISSUE {{background:#f8d7da;color:#721c24;}}
.TRUE_SIGNAL_SPARSE {{background:#d1ecf1;color:#0c5460;}}
.INCONCLUSIVE {{background:#e2e3e5;color:#383d41;}}
.TICKER_COVERAGE_ISSUE {{background:#fff3cd;color:#856404;}}
table{{border-collapse:collapse;width:100%;font-size:0.82rem;margin-bottom:1.5rem;}}
th{{background:#2a2a7e;color:#fff;padding:6px 8px;text-align:left;}}
td{{padding:5px 8px;border-bottom:1px solid #e0e0e0;}}
tr:nth-child(even){{background:#f4f4ff;}}
.summary-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;margin-bottom:1.5rem;}}
.metric-card{{background:#fff;border:1px solid #ddd;border-radius:6px;padding:1rem;}}
.metric-card .val{{font-size:1.5rem;font-weight:bold;color:#2a2a7e;}}
.metric-card .lbl{{font-size:0.8rem;color:#666;}}
nav{{position:sticky;top:0;background:#fff;border-bottom:1px solid #ddd;padding:0.5rem 0;margin-bottom:1rem;}}
nav a{{margin-right:1rem;color:#2a2a7e;text-decoration:none;font-size:0.85rem;}}
</style>
</head>
<body>
<div class="banner">
  ⚠️ RESEARCH_ONLY_NOT_PRODUCTION — This report does not affect A3 / S3 / OMS / final_action / DNSE / live orders / sizing / Phase36 production behavior.
</div>
<h1>P3.1 Coverage / Price-Path QA</h1>
<p><strong>Run date:</strong> {run_date}</p>
<p><strong>QA Label:</strong> <span class="label {qa_label}">{qa_label}</span></p>
<p><strong>Note:</strong> {qa_note}</p>

<nav>
  <a href="#funnel">Candidate Funnel</a>
  <a href="#yearly">Yearly Density</a>
  <a href="#priceaudit">Price-Path Audit</a>
  <a href="#missing">Missing Prices</a>
  <a href="#holding">Holding-Period QA</a>
  <a href="#weekly">Weekly Density</a>
</nav>

<h2 id="funnel">1. Candidate Loss Funnel (V4 + 20B VND)</h2>
{_df_to_html_table(funnel_summary)}

<h2>2. Per-Scan Funnel (sample, first 100 scans)</h2>
{_df_to_html_table(funnel_by_scan.head(100))}

<h2 id="yearly">3. Candidate Density by Year</h2>
{_df_to_html_table(density_year_v4)}

<h2 id="priceaudit">4. Price-Path Audit by Scan</h2>
{_df_to_html_table(price_path_audit.head(150))}

<h2 id="missing">5. Missing Entry-Price Reasons</h2>
{_df_to_html_table(missing_price_reasons.head(100))}

<h2 id="holding">6. Holding-Period QA (2/4/8/12 weeks)</h2>
<h3>Aggregated</h3>
{_df_to_html_table(hp_agg)}
<h3>Per scan (sample)</h3>
{_df_to_html_table(holding_period.head(200))}

<h2 id="weekly">7. Weekly Candidate Density Detail (V4, sample)</h2>
{_df_to_html_table(density_by_week.head(300))}

<footer style="margin-top:3rem;border-top:1px solid #ccc;padding-top:1rem;color:#666;font-size:0.78rem;">
  RESEARCH_ONLY_NOT_PRODUCTION | Generated {run_date}
</footer>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


@dataclass
class P3CoverageQAOutputs:
    coverage_audit_by_scan: pd.DataFrame
    coverage_audit_summary: pd.DataFrame
    price_path_audit: pd.DataFrame
    candidate_density_by_week: pd.DataFrame
    candidate_density_by_year: pd.DataFrame
    missing_price_reasons: pd.DataFrame
    holding_period_qa: pd.DataFrame
    qa_label: str
    qa_note: str


def run_p3_coverage_qa(
    outcomes: pd.DataFrame,
    out_dir: Path,
    html_path: Path,
    run_date: str,
    liquid_threshold: float = LIQUID_THRESHOLD_20B,
    variant_key: str = "V4_NO_DISTRIBUTION_RISK",
    top_n: int = 30,
) -> P3CoverageQAOutputs:
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path.parent.mkdir(parents=True, exist_ok=True)

    funnel_by_scan = build_candidate_loss_funnel(outcomes, variant_key=variant_key, liquid_threshold=liquid_threshold, top_n=top_n)
    funnel_summary = summarize_coverage_audit(funnel_by_scan)
    price_audit = build_price_path_audit(outcomes, liquid_threshold=liquid_threshold)
    density_week = candidate_density_by_week(outcomes, liquid_threshold=liquid_threshold, variant_key=variant_key)
    density_year = candidate_density_by_year(outcomes, liquid_threshold=liquid_threshold, variant_key=variant_key)
    missing_prices = build_missing_price_reasons(outcomes, liquid_threshold=liquid_threshold)
    hp_qa = holding_period_qa(outcomes, liquid_threshold=liquid_threshold, variant_key=variant_key, top_n=top_n)

    qa_label, qa_note = assign_qa_label(funnel_summary, price_audit)

    funnel_by_scan.to_csv(out_dir / "p3_coverage_audit_by_scan.csv", index=False)
    funnel_summary.to_csv(out_dir / "p3_coverage_audit_summary.csv", index=False)
    price_audit.to_csv(out_dir / "p3_price_path_audit.csv", index=False)
    density_week.to_csv(out_dir / "p3_candidate_density_by_week.csv", index=False)
    density_year.to_csv(out_dir / "p3_candidate_density_by_year.csv", index=False)
    missing_prices.to_csv(out_dir / "p3_missing_price_reasons.csv", index=False)
    hp_qa.to_csv(out_dir / "p3_holding_period_qa.csv", index=False)

    html = build_html_report(
        funnel_by_scan=funnel_by_scan,
        funnel_summary=funnel_summary,
        price_path_audit=price_audit,
        density_by_week=density_week,
        density_by_year=density_year,
        missing_price_reasons=missing_prices,
        holding_period=hp_qa,
        qa_label=qa_label,
        qa_note=qa_note,
        run_date=run_date,
    )
    html_path.write_text(html, encoding="utf-8")

    return P3CoverageQAOutputs(
        coverage_audit_by_scan=funnel_by_scan,
        coverage_audit_summary=funnel_summary,
        price_path_audit=price_audit,
        candidate_density_by_week=density_week,
        candidate_density_by_year=density_year,
        missing_price_reasons=missing_prices,
        holding_period_qa=hp_qa,
        qa_label=qa_label,
        qa_note=qa_note,
    )
