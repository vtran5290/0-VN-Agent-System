"""Read-only RS correction lens card for daily / cloud / weekly reports."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
LATEST_JSON = REPO / "data" / "research" / "market_risk" / "rs_correction_latest.json"
SAFETY_NOTE = "RS correction lens is market context only and does not change final_action."
_NEW_T1_ACTIONS = frozenset({"NEW_T1", "NEW_T1_MANUAL_REVIEW_BREADTH"})
_EXIT_ACTIONS = frozenset({"TRAIL_EXIT", "TP1_PARTIAL", "MAX_HOLD_EXIT"})

_RS_TABLE_HEADERS = [
    "Symbol",
    "Close (anchor→end)",
    "Ret leg",
    "RS leg",
    "RS20 before",
    "RS20 after",
    "Δ RS20",
    "Impr",
    "Hold",
    "final_action",
    "T1",
    "S3 lead",
    "A3/S3 cloud",
]


def refresh_rs_correction_for_reports(
    *,
    as_of: str | None = None,
    anchor_date: str | None = None,
) -> list[str]:
    from src.market.rs_correction_lens.pipeline import run_rs_correction_lens

    result = run_rs_correction_lens(as_of=as_of, anchor_date=anchor_date)
    return list(result.get("load_warnings") or [])


def load_rs_correction_latest(path: Optional[Path] = None) -> tuple[Optional[dict[str, Any]], list[str]]:
    p = path or LATEST_JSON
    if not p.is_file():
        return None, [f"rs_correction_latest.json missing: {p}"]
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None, []
    except (json.JSONDecodeError, OSError) as exc:
        return None, [f"failed to read rs correction JSON: {exc}"]


def _fmt_pct(v: Any) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):+.2f}%"
    except (TypeError, ValueError):
        return str(v)


def _fmt_close_pair(r: dict[str, Any]) -> str:
    a, e = r.get("close_anchor"), r.get("close_end")
    if a is None or e is None:
        return "—"
    return f"{a}→{e}"


def _fmt_rs20_delta(r: dict[str, Any]) -> str:
    d = r.get("rs20_delta_pp")
    if d is None and r.get("rs20_end_pct") is not None and r.get("rs20_anchor_pct") is not None:
        d = float(r["rs20_end_pct"]) - float(r["rs20_anchor_pct"])
    return _fmt_pct(d)


def _fmt_cloud_pair(r: dict[str, Any]) -> str:
    a3 = r.get("a3_cloud", "—")
    s3 = r.get("s3_cloud", "—")
    return f"{a3}/{s3}"


def _build_operator_lookup(
    scan_df: Optional[pd.DataFrame],
    holdings: Optional[list[str]],
) -> dict[str, dict[str, Any]]:
    """Map symbol → Phase36 / portfolio crosswalk (display only)."""
    lookup: dict[str, dict[str, Any]] = {}
    holdings_set = {x.strip().upper() for x in (holdings or []) if x}

    def _bool_cloud(v: Any) -> str:
        if v is True or v == "True" or v == 1:
            return "Y"
        if v is False or v == "False" or v == 0:
            return "N"
        return "—"

    if scan_df is not None and not scan_df.empty:
        for _, row in scan_df.iterrows():
            sym = str(row.get("symbol", "")).upper()
            if not sym:
                continue
            fa = str(row.get("final_action", "") or "—")
            fa_short = fa.replace("NEW_T1_MANUAL_REVIEW_BREADTH", "NEW_T1_MR")
            lookup[sym] = {
                "in_holdings": "Y" if sym in holdings_set else "—",
                "final_action": fa_short,
                "is_new_t1": "Y" if fa in _NEW_T1_ACTIONS else "—",
                "is_exit": "Y" if fa in _EXIT_ACTIONS else "—",
                "s3_lead": str(row.get("s3_lead_bucket") or "—"),
                "s3_cloud": _bool_cloud(row.get("s3_cloud_bull")),
                "a3_cloud": _bool_cloud(row.get("a3_cloud_bull")),
            }

    for sym in holdings_set:
        if sym not in lookup:
            lookup[sym] = {
                "in_holdings": "Y",
                "final_action": "not_in_scan",
                "is_new_t1": "—",
                "is_exit": "—",
                "s3_lead": "—",
                "s3_cloud": "—",
                "a3_cloud": "—",
            }
    return lookup


def _enrich_rs_rows(
    rows: list[dict[str, Any]],
    lookup: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in rows:
        sym = str(r.get("symbol", "")).upper()
        ctx = lookup.get(sym, {})
        merged = {**r, **ctx}
        if sym and sym not in lookup:
            merged.setdefault("in_holdings", "—")
            merged.setdefault("final_action", "—")
            merged.setdefault("is_new_t1", "—")
            merged.setdefault("s3_lead", "—")
            merged.setdefault("a3_cloud", "—")
            merged.setdefault("s3_cloud", "—")
        out.append(merged)
    return out


def enrich_rs_payload_with_operator_context(
    data: dict[str, Any],
    *,
    scan_df: Optional[pd.DataFrame] = None,
    holdings: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Copy payload with operator crosswalk on list sections (no SSOT mutation)."""
    lookup = _build_operator_lookup(scan_df, holdings)
    out = dict(data)
    for key in ("leaders_top25", "improving_top25", "defensive_flat_top25", "laggards_bottom15"):
        if key in out and isinstance(out[key], list):
            out[key] = _enrich_rs_rows(out[key], lookup)
    return out


def _row_to_md_cells(r: dict[str, Any]) -> list[str]:
    return [
        str(r.get("symbol", "—")),
        _fmt_close_pair(r),
        _fmt_pct(r.get("ret_pct")),
        _fmt_pct(r.get("rs_pct")),
        _fmt_pct(r.get("rs20_anchor_pct")),
        _fmt_pct(r.get("rs20_end_pct")),
        _fmt_rs20_delta(r),
        "Y" if r.get("rs_improving_flag") else "—",
        str(r.get("in_holdings", "—")),
        str(r.get("final_action", "—")),
        str(r.get("is_new_t1", "—")),
        str(r.get("s3_lead", "—")),
        _fmt_cloud_pair(r),
    ]


def render_rs_correction_md(
    data: dict[str, Any],
    *,
    include_title: bool = True,
    scan_df: Optional[pd.DataFrame] = None,
    holdings: Optional[list[str]] = None,
) -> str:
    data = enrich_rs_payload_with_operator_context(data, scan_df=scan_df, holdings=holdings)
    anc = data.get("anchor") or {}
    lines: list[str] = []
    if include_title:
        lines.extend(["### RS vs VNINDEX (correction leg)", ""])
    lines.extend([
        "| Metric | Value |",
        "| --- | --- |",
        f"| Anchor date | {anc.get('anchor_date', '—')} (close {anc.get('anchor_close', '—')}) |",
        f"| End date | {anc.get('end_date', '—')} (close {anc.get('end_close', '—')}) |",
        f"| VNINDEX return | {_fmt_pct(anc.get('vnindex_ret_pct'))} |",
        f"| Drawdown from peak | {_fmt_pct(anc.get('drawdown_from_peak_pct'))} |",
        f"| Detection | {anc.get('detection_method', '—')} |",
        f"| Universe n | {data.get('n_symbols', '—')} |",
        f"| Outperform (RS>0) | {data.get('n_outperform_rs_gt_0', '—')} |",
        f"| Leaders (RS≥+3%) | {data.get('n_leader_rs_ge_3', '—')} |",
        "",
        "**Definitions:** `RS leg` = stock return − VNINDEX return over correction anchor→end. "
        "`RS20 before/after` = 20d RS vs VNINDEX at anchor date vs end date; `Δ RS20` = after − before (pp). "
        "`Close (anchor→end)` = kVND close on anchor bar → end bar. "
        "Hold/T1/S3/A3 columns crosswalk Phase36 `final_action` (display only).",
        "",
    ])
    hdr = "| " + " | ".join(_RS_TABLE_HEADERS) + " |"
    sep = "| " + " | ".join(["---"] * len(_RS_TABLE_HEADERS)) + " |"
    for title, key in (
        ("Top leaders (RS≥+3%)", "leaders_top25"),
        ("RS improving + positive RS", "improving_top25"),
        ("Defensive flat (ret −1%…+2%, RS≥+1%)", "defensive_flat_top25"),
        ("Weakest RS", "laggards_bottom15"),
    ):
        rows = data.get(key) or []
        if not rows:
            continue
        lines.append(f"#### {title}")
        lines.append(hdr)
        lines.append(sep)
        for r in rows[:15]:
            cells = _row_to_md_cells(r)
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
    lines.append(
        "> Cap-weight VNINDEX may be Vingroup-skewed in 2025–2026. "
        "Flag VIN names separately; do not treat VPL as broad-market proof."
    )
    return "\n".join(lines)


def _rs_html_table(rows: list[dict], max_rows: int = 15) -> str:
    """Render a list of RS symbol rows as a proper HTML table."""
    import html as html_mod
    esc = html_mod.escape
    if not rows:
        return ""
    th = "".join(f"<th>{esc(h)}</th>" for h in _RS_TABLE_HEADERS)
    tbody = ""
    for r in rows[:max_rows]:
        rs_val = r.get("rs_pct")
        try:
            rs_color = " style='color:#5edd5e;'" if rs_val is not None and float(rs_val) > 0 else " style='color:#f77;'"
        except (TypeError, ValueError):
            rs_color = ""
        delta = _fmt_rs20_delta(r)
        d_raw = r.get("rs20_delta_pp")
        if d_raw is None and r.get("rs20_end_pct") is not None and r.get("rs20_anchor_pct") is not None:
            d_raw = float(r["rs20_end_pct"]) - float(r["rs20_anchor_pct"])
        try:
            d_color = " style='color:#5edd5e;'" if d_raw is not None and float(d_raw) > 0 else ""
            if d_raw is not None and float(d_raw) < 0:
                d_color = " style='color:#f77;'"
        except (TypeError, ValueError):
            d_color = ""
        cells = [
            esc(str(r.get("symbol", "—"))),
            esc(_fmt_close_pair(r)),
            _fmt_pct(r.get("ret_pct")),
            _fmt_pct(rs_val),
            _fmt_pct(r.get("rs20_anchor_pct")),
            _fmt_pct(r.get("rs20_end_pct")),
            delta,
            "Y" if r.get("rs_improving_flag") else "—",
            esc(str(r.get("in_holdings", "—"))),
            esc(str(r.get("final_action", "—"))),
            esc(str(r.get("is_new_t1", "—"))),
            esc(str(r.get("s3_lead", "—"))),
            esc(_fmt_cloud_pair(r)),
        ]
        tbody += "<tr>"
        for i, c in enumerate(cells):
            if i == 3:
                tbody += f"<td{rs_color}>{c}</td>"
            elif i == 6:
                tbody += f"<td{d_color}>{c}</td>"
            else:
                tbody += f"<td>{c}</td>"
        tbody += "</tr>"
    return (
        '<div class="scroll-table">'
        f"<table><thead><tr>{th}</tr></thead><tbody>{tbody}</tbody></table>"
        "</div>"
    )


def render_rs_correction_html(
    data: dict[str, Any],
    *,
    scan_df: Optional[pd.DataFrame] = None,
    holdings: Optional[list[str]] = None,
) -> str:
    """Render RS Correction card as proper HTML tables (not raw markdown)."""
    import html as html_mod
    esc = html_mod.escape
    data = enrich_rs_payload_with_operator_context(data, scan_df=scan_df, holdings=holdings)
    anc = data.get("anchor") or {}

    meta_rows = [
        ("Anchor date", f"{anc.get('anchor_date', '—')} (close {anc.get('anchor_close', '—')})"),
        ("End date", f"{anc.get('end_date', '—')} (close {anc.get('end_close', '—')})"),
        ("VNINDEX return", _fmt_pct(anc.get("vnindex_ret_pct"))),
        ("Drawdown from peak", _fmt_pct(anc.get("drawdown_from_peak_pct"))),
        ("Detection", str(anc.get("detection_method", "—"))),
        ("Universe n", str(data.get("n_symbols", "—"))),
        ("Outperform (RS>0)", str(data.get("n_outperform_rs_gt_0", "—"))),
        ("Leaders (RS≥10%)", str(data.get("n_leader_rs_ge_3", "—"))),
    ]
    meta_tbody = "".join(
        f"<tr><th style='width:200px'>{esc(k)}</th><td>{esc(str(v))}</td></tr>"
        for k, v in meta_rows
    )
    meta_table = f"<table><tbody>{meta_tbody}</tbody></table>"

    section_parts: list[str] = []
    for title, key in (
        ("Top leaders (RS≥10%)", "leaders_top25"),
        ("RS improving + positive RS", "improving_top25"),
        ("Defensive flat (−1%…+2%, RS≥1%)", "defensive_flat_top25"),
        ("Weakest RS", "laggards_bottom15"),
    ):
        rows = data.get(key) or []
        if rows:
            section_parts.append(
                f'<div class="subsection-title">{esc(title)}</div>'
                + _rs_html_table(rows)
            )

    return (
        '<div class="subsection-title">RS vs VNINDEX (correction leg) '
        '<span class="ctx-tag">MARKET CONTEXT</span></div>'
        + meta_table
        + "".join(section_parts)
        + '<div class="ctx-safety">RS Correction is market/leader context only. '
        'It does <strong>not</strong> set or override <code>final_action</code>.</div>'
        + f'<p class="footnote">{SAFETY_NOTE}</p>'
        + '<p class="footnote">Cap-weight VNINDEX may be Vingroup-skewed in 2025–2026. '
        'VIN names are flagged in the VIN column above.</p>'
    )


def build_rs_correction_section_for_daily_scan(
    *,
    as_of: str | None = None,
    refresh: bool = True,
    holdings: list[str] | None = None,
    scan_symbols: list[str] | None = None,
    scan_df: Optional[pd.DataFrame] = None,
) -> tuple[str, list[str]]:
    warnings: list[str] = []
    if refresh:
        try:
            warnings.extend(refresh_rs_correction_for_reports(as_of=as_of))
        except Exception as exc:
            return (
                "\n## RS vs VNINDEX (correction leg)\n\n"
                f"**WARN:** refresh failed: {exc}\n\n"
                f"_{SAFETY_NOTE}_\n",
                warnings + [str(exc)],
            )
    data, load_warns = load_rs_correction_latest()
    warnings.extend(load_warns)
    if not data:
        return (
            "\n## RS vs VNINDEX (correction leg)\n\n"
            "_rs_correction_latest.json missing — run RS correction lens._\n\n"
            f"_{SAFETY_NOTE}_\n",
            warnings,
        )

    lines = [
        "\n## RS vs VNINDEX (correction leg)\n",
        "**FACTS** (market context only; does not change final_action)\n",
        render_rs_correction_md(
            data, include_title=False, scan_df=scan_df, holdings=holdings
        ),
        "",
        f"**SSOT:** `data/research/market_risk/rs_correction_latest.json` · "
        f"**method:** {data.get('method_version', '—')}",
        "",
        f"_{SAFETY_NOTE}_\n",
    ]

    # Holdings + new-entry queue (full crosswalk table)
    if holdings or scan_symbols:
        csv_path = REPO / "data" / "research" / "market_risk" / "rs_correction_latest.csv"
        if csv_path.is_file():
            rs_df = pd.read_csv(csv_path)
            want = {x.upper() for x in (holdings or [])} | {x.upper() for x in (scan_symbols or [])}
            sub = rs_df[rs_df["symbol"].str.upper().isin(want)].sort_values("rs_pct", ascending=False)
            sub_rows = sub.to_dict(orient="records")
            lookup = _build_operator_lookup(scan_df, holdings)
            enriched = _enrich_rs_rows(sub_rows, lookup)
            lines.append("\n### Holdings & scan queue — RS crosswalk\n\n")
            hdr = "| " + " | ".join(_RS_TABLE_HEADERS) + " |"
            sep = "| " + " | ".join(["---"] * len(_RS_TABLE_HEADERS)) + " |"
            lines.append(hdr)
            lines.append(sep)
            for r in enriched:
                lines.append("| " + " | ".join(_row_to_md_cells(r)) + " |")
            missing = sorted(want - {str(s).upper() for s in sub["symbol"]})
            if missing:
                lines.append(f"\n_Not in RS universe today:_ {', '.join(missing)}\n")

    return "\n".join(lines), warnings


def merge_rs_into_scan_df(scan_df: Any) -> Any:
    """Add rs_correction_* columns from latest CSV (no-op if missing)."""
    import pandas as pd

    if scan_df is None or (hasattr(scan_df, "empty") and scan_df.empty):
        return scan_df
    csv_path = REPO / "data" / "research" / "market_risk" / "rs_correction_latest.csv"
    if not csv_path.is_file():
        return scan_df
    rs = pd.read_csv(csv_path)
    cols = [
        "symbol",
        "close_anchor",
        "close_end",
        "rs_pct",
        "ret_pct",
        "rs20_anchor_pct",
        "rs20_end_pct",
        "rs20_delta_pp",
        "rs_improving_flag",
        "bucket",
        "mdd_since_anchor_pct",
    ]
    rename = {
        "rs_pct": "rs_correction_pct",
        "ret_pct": "rs_correction_ret_pct",
        "close_anchor": "rs_correction_close_anchor",
        "close_end": "rs_correction_close_end",
        "rs20_anchor_pct": "rs_correction_rs20_anchor_pct",
        "rs20_end_pct": "rs_correction_rs20_end_pct",
        "rs20_delta_pp": "rs_correction_rs20_delta_pp",
        "rs_improving_flag": "rs_correction_improving",
        "bucket": "rs_correction_bucket",
        "mdd_since_anchor_pct": "rs_correction_mdd_pct",
    }
    rs = rs[[c for c in cols if c in rs.columns]].rename(columns=rename)
    out = scan_df.merge(rs, on="symbol", how="left")
    return out
