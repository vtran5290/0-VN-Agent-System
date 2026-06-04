from __future__ import annotations

from pathlib import Path

import pandas as pd

SAFETY_BANNER = (
    "Research-only. No production trading logic changed. No final_action. No OMS. No DNSE. No sizing."
)


def _tbl(df: pd.DataFrame, cols: list[str] | None = None) -> str:
    if df.empty:
        return "<p><i>No data</i></p>"
    if cols:
        use = [c for c in cols if c in df.columns]
        if use:
            return df[use].to_html(index=False)
    return df.to_html(index=False)


def _note() -> str:
    return f'<div class="note">{SAFETY_BANNER} RESEARCH_ONLY_NOT_PRODUCTION</div>'


def write_p2_html_report(
    out: Path,
    *,
    variant_results: pd.DataFrame,
    top_decile_exhaustion: pd.DataFrame,
    extension_cap_sweep: pd.DataFrame,
    distribution_gate_sweep: pd.DataFrame,
    diagnostic_summary: pd.DataFrame,
    p1_summary: pd.DataFrame | None = None,
) -> None:
    full = variant_results[variant_results["split"] == "full_sample"].copy()
    if "ret_60d_lift_vs_v0" in full.columns:
        leaderboard = full.sort_values("ret_60d_lift_vs_v0", ascending=False, na_position="last")
    else:
        leaderboard = full

    regime = variant_results[variant_results["split"].isin(["normal_regime", "correction_or_bear", "fragile_uptrend_narrow_leadership", "bull_breadth_expansion"])]
    ex_vin = variant_results[variant_results["split"] == "ex_vin"]

    promising = diagnostic_summary[diagnostic_summary["label"] == "PROMISING_RESEARCH_VARIANT"]
    rejected = diagnostic_summary[diagnostic_summary["label"] == "REJECTED_VARIANT"]
    risk_only = diagnostic_summary[diagnostic_summary["label"] == "RISK_REDUCTION_ONLY"]

    p1_block = ""
    if p1_summary is not None and not p1_summary.empty:
        p1_block = _tbl(p1_summary, ["area", "diagnostic_label", "evidence"])

    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>P2 Research Variants</title>
<style>body{{font-family:Arial,sans-serif;background:#0b0f14;color:#d9e1ea;padding:18px}}
table{{border-collapse:collapse;width:100%;margin:10px 0}}td,th{{border:1px solid #2a3442;padding:6px}}
h2{{margin-top:24px}}.note{{background:#1b2532;padding:10px;border-left:4px solid #6ca4ff;margin:10px 0}}</style>
</head><body>
<h1>P2 Research Variants — Institutional Accumulation</h1>
{_note()}
<h2>Executive summary</h2>
{_tbl(diagnostic_summary, ["variant_id", "label", "evidence", "recommended_next_step"])}
<h2>Baseline reminder from P1.1</h2>
{p1_block if p1_block else "<p>P1.1 summary not loaded.</p>"}
{_note()}
<h2>Variant leaderboard (full_sample, by ret_60d_lift_vs_v0)</h2>
{_tbl(leaderboard, ["variant_id", "n", "ret_60d_mean", "ret_60d_lift_vs_v0", "p_dd10_60d", "dd10_lift_vs_v0"])}
<h2>Top-decile exhaustion confirmation</h2>
{_tbl(top_decile_exhaustion)}
{_note()}
<h2>Extension cap sweep</h2>
{_tbl(extension_cap_sweep)}
<h2>Distribution gate sweep</h2>
{_tbl(distribution_gate_sweep)}
<h2>Regime split</h2>
{_tbl(regime, ["variant_id", "split", "n", "ret_60d_mean", "p_dd10_60d"])}
<h2>Ex-VIN split</h2>
{_tbl(ex_vin, ["variant_id", "n", "ret_60d_mean", "ret_60d_lift_vs_v0", "dd10_lift_vs_v0"])}
<h2>Best candidate variants</h2>
{_tbl(promising)}
<h2>Rejected variants</h2>
{_tbl(rejected)}
<h2>Risk-reduction-only variants</h2>
{_tbl(risk_only)}
<h2>What not to promote</h2>
<p>Do not promote any variant to OMS, final_action, production scan, DNSE, or sizing. Labels are research diagnostics only.</p>
<h2>Recommended P3 direction</h2>
<p>Prioritize variants labeled PROMISING_RESEARCH_VARIANT or RISK_REDUCTION_ONLY for controlled P3 research. If none are promising, state explicitly and keep production unchanged.</p>
<h2>Limitations</h2>
<ul>
<li>OHLCV-only; no PIT fund context.</li>
<li>Overlapping forward-return measurement; not investable portfolio simulation.</li>
<li>2022–2026 sample materially stronger than earlier years.</li>
</ul>
{_note()}
</body></html>"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
