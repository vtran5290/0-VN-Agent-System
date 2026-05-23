from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pandas as pd


def write_markdown_report(
    path: Path,
    df: pd.DataFrame,
    payload: Dict[str, Any],
    rejected: List[Dict[str, Any]],
) -> None:
    ctx = payload.get("context") or {}
    val = payload.get("validation") or {}
    sec = payload.get("sector_summary") or {}
    cfg = payload.get("config") or {}
    scan_date = payload.get("scan_date", "")

    lines = [
        "# Institutional Accumulation Scan",
        "",
        f"**Scan date:** {scan_date}  ",
        f"**Role:** Research ranking only — not execution.  ",
        f"**Context:** {ctx.get('source')} | regime: `{ctx.get('regime_label')}`  ",
        f"**Universe:** {((ctx.get('universe_policy') or {}).get('mode') or 'full_liquid_universe')} — fund lists are priors only  ",
        f"**Data:** {cfg.get('data_source')} | benchmark: {cfg.get('benchmark')} | method: {cfg.get('method')}",
        "",
        "## Regime context (Smart Money prior)",
        "",
    ]
    for flag in ctx.get("risk_flags") or []:
        lines.append(f"- {flag}")
    lines.extend(["", "## Sector summary", ""])
    if sec.get("tier12_count_by_sector"):
        lines.append("| Sector | Tier 1–2 count | Avg score (universe) |")
        lines.append("| --- | ---: | ---: |")
        avgs = sec.get("avg_score_by_sector") or {}
        for sector, cnt in sorted(sec["tier12_count_by_sector"].items(), key=lambda x: -x[1]):
            lines.append(f"| {sector} | {cnt} | {avgs.get(sector, '—')} |")
    if sec.get("concentration_warning"):
        lines.append(
            "\n**INTERPRETATION:** Scan top tier is concentrated in one sector/theme — "
            "treat as narrow/fragile confirmation, not broad risk-on."
        )

    lines.extend(["", "## Top candidates (Tier 1)", ""])
    t1 = df[df["tier"] == "Tier 1"].head(15)
    if t1.empty:
        lines.append("_No Tier 1 names at current thresholds._")
    else:
        lines.append(_table_md(t1))

    lines.extend(["", "## Early accumulation (Tier 2)", ""])
    t2 = df[df["tier"] == "Tier 2"].head(20)
    if t2.empty:
        lines.append("_No Tier 2 names._")
    else:
        lines.append(_table_md(t2))

    lines.extend(["", "## Mixed / review (Tier 3, top 10)", ""])
    t3 = df[df["tier"] == "Tier 3"].head(10)
    if not t3.empty:
        lines.append(_table_md(t3))

    emerg = payload.get("emerging_accumulation") or {}
    lines.extend(["", "## Emerging accumulation (outside fund disclosure tags)", ""])
    lines.append(
        "_Names with Tier 1–3 + constructive money flow but **no** consensus/commentary/selective fund tag — "
        "possible accumulation not visible in top holdings._"
    )
    if emerg.get("count", 0) == 0:
        lines.append("\n_None flagged this run._")
    else:
        lines.append(f"\n**Count:** {emerg.get('count')} (showing top 15)")
        edf = pd.DataFrame(emerg.get("top") or []).head(15)
        if not edf.empty:
            cols = [c for c in ["ticker", "tier", "institutional_accumulation_score", "score_money_flow", "sector"] if c in edf.columns]
            lines.append(_table_md(edf[cols]))

    fund_tagged = df[df["has_fund_disclosure_tag"] == True]  # noqa: E712
    lines.extend(["", "## Fund-context names in scan (any tier)", ""])
    lines.append(f"**Count:** {len(fund_tagged)} (core / second_ring / commentary / selective)")
    if not fund_tagged.empty:
        fc = fund_tagged.sort_values("institutional_accumulation_score", ascending=False).head(20)
        cols = [c for c in ["ticker", "tier", "fund_context_bucket", "institutional_accumulation_score", "score_money_flow"] if c in fc.columns]
        lines.append(_table_md(fc[cols]))

    spot = val.get("spot_checks") or {}
    lines.extend(["", "## Validation spot-checks", ""])
    for k, v in spot.items():
        lines.append(f"- **{k}:** {v}")

    if rejected:
        lines.extend(["", "## Near-miss rejections (distortion / risk)", ""])
        rdf = pd.DataFrame(rejected).head(15)
        cols = ["ticker", "institutional_accumulation_score", "reject_reason", "vingroup_distortion_flag"]
        cols = [c for c in cols if c in rdf.columns]
        lines.append(_table_md(rdf[cols]))

    lines.extend(
        [
            "",
            "## Caveats",
            "",
            "- Metrics are OHLCV-derived from repo CSVs; refresh `data/stocks` before relying on dates.",
            "- RS vs sector index not computed (VNINDEX only).",
            "- Vingroup names flagged; cap-weight VNINDEX may be skewed 2025–2026.",
            "- Smart Money tags are priors, not buy signals.",
            "",
            "---",
            "*End of scan report.*",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _table_md(df: pd.DataFrame) -> str:
    cols = [
        "ticker",
        "institutional_accumulation_score",
        "score_money_flow",
        "score_price_structure",
        "smart_money_tag",
        "cmf20_daily",
        "rs_vs_vnindex_20",
        "vingroup_distortion_flag",
        "notes",
    ]
    cols = [c for c in cols if c in df.columns]
    sub = df[cols].copy()
    for c in sub.columns:
        if sub[c].dtype == float:
            sub[c] = sub[c].map(lambda x: f"{x:.2f}" if pd.notna(x) else "—")
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    body = ["| " + " | ".join(str(row[c]) for c in cols) + " |" for _, row in sub.iterrows()]
    return "\n".join([header, sep] + body)
