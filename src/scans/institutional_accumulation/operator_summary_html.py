"""Operator summary HTML report (lean dark theme; same data as .md)."""
from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence

# Acceptance: 18 scroll-spy sections (evidence-status → appendix); header is sidebar "Overview" only.
OPERATOR_HTML_SECTION_IDS: Sequence[str] = (
    "evidence-status",
    "how-to-read",
    "benchmark-context",
    "snapshot",
    "changes",
    "risk-clean",
    "heat-warnings",
    "dist-avoid",
    "fund-backed",
    "emerging",
    "rejects",
    "distortion",
    "warnings",
    "signals",
    "playbook",
    "research-actions",
    "not-promote",
    "files",
    "appendix",
)

_CSS = """
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
:root {
  --bg:#0d0f12; --panel:#13161b; --card:#181c22; --border:#252a35;
  --accent:#00c896; --red:#f05050; --amber:#f0a030; --blue:#4a9eff;
  --purple:#b07fff; --text:#d8dde8; --dim:#7a8399; --muted:#4a5168;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:"IBM Plex Sans",sans-serif;font-size:13px;line-height:1.6}
.layout{display:flex;min-height:100vh}
.sidebar{width:180px;position:sticky;top:0;height:100vh;overflow-y:auto;border-right:1px solid var(--border);background:var(--panel);padding:16px 0;flex-shrink:0}
.sidebar-logo{padding:10px 16px 14px;font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.1em;border-bottom:1px solid var(--border);margin-bottom:10px}
.sidebar h3{margin:14px 14px 5px;font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}
.sidebar a{display:block;margin:1px 8px;padding:6px 8px;color:var(--dim);text-decoration:none;font-size:11px;border-radius:4px}
.sidebar a:hover,.sidebar a.active{background:#1e2330;color:var(--text)}
.main{flex:1;max-width:1060px;padding:24px 28px;overflow-x:hidden}
.card{background:var(--card);border:1px solid var(--border);border-radius:6px;padding:16px 18px;margin-bottom:12px}
.card-title{font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--dim);font-weight:600;margin-bottom:12px}
.card-ok{border-left:3px solid var(--accent)}
.card-warn{border-left:3px solid var(--amber)}
.card-alert{border-left:3px solid var(--red)}
.card-blue{border-left:3px solid var(--blue)}
.report-title{font-size:1.3rem;font-weight:700;margin-bottom:4px}
.report-meta{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--dim)}
.regime-badge{display:inline-block;margin-top:8px;padding:3px 10px;border-radius:4px;font-size:10px;font-weight:600;background:rgba(240,160,48,.15);color:var(--amber);border:1px solid rgba(240,160,48,.3)}
.kpi-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:8px;margin-bottom:4px}
.kpi{background:var(--panel);border:1px solid var(--border);border-radius:6px;padding:10px 12px}
.kpi .label{font-size:9px;color:var(--muted);text-transform:uppercase}
.kpi .value{font-family:"IBM Plex Mono",monospace;font-size:15px;margin-top:3px;font-weight:500}
.kpi .sub{font-size:9px;color:var(--dim);margin-top:1px}
.kpi-accent .value{color:var(--accent)} .kpi-amber .value{color:var(--amber)}
.kpi-red .value{color:var(--red)} .kpi-blue .value{color:var(--blue)} .kpi-dim .value{color:var(--dim)}
.tbl-wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:12px}
th{color:var(--muted);font-size:9px;text-transform:uppercase;padding:5px 8px;border-bottom:1px solid var(--border);text-align:left}
td{padding:6px 8px;border-bottom:1px solid rgba(37,42,53,.6);vertical-align:top}
tr:last-child td{border-bottom:none}
tr:hover td{background:rgba(255,255,255,.02)}
.tk{font-family:"IBM Plex Mono",monospace;font-weight:600;font-size:12px;color:var(--accent)}
.tk-warn{color:var(--amber)} .tk-red{color:var(--red)}
.mono{font-family:"IBM Plex Mono",monospace}
.badge{display:inline-block;font-size:9px;padding:2px 7px;border-radius:3px;font-weight:600}
.b-t1{background:rgba(0,200,150,.18);color:var(--accent)}
.b-t2{background:rgba(74,158,255,.18);color:var(--blue)}
.b-t3{background:rgba(240,160,48,.18);color:var(--amber)}
.b-rej{background:rgba(240,80,80,.15);color:var(--red)}
.b-vin{background:rgba(240,80,80,.12);color:var(--red);border:1px solid rgba(240,80,80,.3)}
.b-core{background:rgba(0,200,150,.1);color:var(--accent);font-size:9px;padding:1px 5px;border-radius:3px}
.b-ring{background:rgba(74,158,255,.1);color:var(--blue);font-size:9px;padding:1px 5px;border-radius:3px}
.b-sel{background:rgba(240,160,48,.1);color:var(--amber);font-size:9px;padding:1px 5px;border-radius:3px}
.b-com{background:rgba(176,127,255,.1);color:var(--purple);font-size:9px;padding:1px 5px;border-radius:3px}
.b-out{background:rgba(122,131,153,.1);color:var(--dim);font-size:9px;padding:1px 5px;border-radius:3px}
.bar-wrap{width:56px;height:4px;background:var(--border);border-radius:2px;display:inline-block;vertical-align:middle;margin-left:4px}
.bar-fill{height:4px;border-radius:2px;display:block}
.bar-green{background:var(--accent)} .bar-blue{background:var(--blue)}
.bar-amber{background:var(--amber)} .bar-red{background:var(--red)}
.risk-ok{color:var(--accent)} .risk-low{color:var(--dim)}
.risk-med{color:var(--amber)} .risk-high{color:var(--red);font-weight:600}
.section-note{font-size:11px;color:var(--dim);margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid var(--border)}
.warn-strip{background:rgba(240,160,48,.08);border:1px solid rgba(240,160,48,.25);border-radius:4px;padding:7px 11px;margin-bottom:8px;font-size:11px;color:var(--amber)}
.crit-strip{background:rgba(240,80,80,.08);border:1px solid rgba(240,80,80,.25);border-radius:4px;padding:7px 11px;margin-bottom:8px;font-size:11px;color:var(--red)}
.p1-strip{border-color:rgba(240,80,80,.35);background:rgba(240,80,80,.06);color:var(--text)}
.evidence-banner{background:#0c1a10;border:2px solid var(--accent);border-radius:6px;padding:14px 18px;margin-bottom:4px}
.evidence-banner .ev-title{font-size:9px;letter-spacing:.1em;text-transform:uppercase;color:var(--accent);font-weight:700;margin-bottom:10px}
.ev-row{display:flex;gap:12px;padding:5px 0;border-bottom:1px solid rgba(37,42,53,.5);font-size:11px;align-items:baseline}
.ev-row:last-child{border-bottom:none}
.ev-label{min-width:220px;flex-shrink:0;color:var(--dim)}
.ev-val-warn{color:var(--amber);font-weight:600}
.ev-val-ok{color:var(--accent);font-weight:600}
.ev-val-red{color:var(--red);font-weight:600}
.ev-val-dim{color:var(--muted)}
.safety-note{background:#160d0d;border:1px solid rgba(240,80,80,.3);border-radius:4px;padding:8px 12px;font-size:11px;color:var(--red);margin-top:10px}
.research-note{background:#0d1420;border:1px solid rgba(74,158,255,.25);border-radius:4px;padding:8px 12px;font-size:11px;color:var(--blue);margin-top:6px}
.not-promote-item{padding:5px 0;font-size:12px;border-bottom:1px solid rgba(37,42,53,.4)}
.not-promote-item:last-child{border-bottom:none}
.not-promote-item::before{content:"✕ ";color:var(--red);font-weight:bold}
.bench-row{display:flex;justify-content:space-between;padding:4px 0;font-size:11px;border-bottom:1px solid rgba(37,42,53,.4)}
.bench-row:last-child{border-bottom:none}
.bench-label{color:var(--dim)}
.bench-val{font-family:"IBM Plex Mono",monospace;color:var(--text)}
.evidence-kpi-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:10px}
.diff-none{color:var(--muted);font-style:italic;font-size:11px}
.filemap{display:grid;grid-template-columns:1fr 1fr;gap:6px}
.fmap-row{background:var(--panel);border:1px solid var(--border);border-radius:4px;padding:8px 10px}
.fmap-path{font-family:"IBM Plex Mono",monospace;font-size:10px;color:var(--blue)}
.fmap-role{font-size:10px;color:var(--dim);margin-top:2px}
.fmap-active .fmap-path{color:var(--accent)} .fmap-active .fmap-role{color:var(--text)}
h1{font-size:1.25rem;font-weight:700}
"""


def _esc(val: Any) -> str:
    if val is None:
        return ""
    return html.escape(str(val))


def _tier_badge(tier: str) -> str:
    t = tier or ""
    cls = {
        "Tier 1": "b-t1",
        "Tier 2": "b-t2",
        "Tier 3": "b-t3",
        "Reject": "b-rej",
    }.get(t, "b-out")
    return f'<span class="badge {cls}">{_esc(t)}</span>'


def _bucket_badge(bucket: str) -> str:
    b = bucket or "outside_fund_disclosure"
    mapping = {
        "consensus_core": ("b-core", "core"),
        "consensus_second_ring": ("b-ring", "ring"),
        "selective_fund_bet": ("b-sel", "sel"),
        "fund_commentary_mention": ("b-com", "com"),
    }
    cls, short = mapping.get(b, ("b-out", "out"))
    return f'<span class="{cls}">{_esc(short)}</span>'


def _risk_html(risk: float, vin: bool = False) -> str:
    if risk >= 50:
        return f'<span class="mono risk-high">{risk:.0f}</span>'
    if risk >= 30:
        return f'<span class="mono risk-med">{risk:.0f}</span>'
    if risk > 0:
        return f'<span class="mono risk-low">{risk:.0f}</span>'
    return '<span class="mono risk-ok">0</span>'


def _score_bar(score: float, tier: str) -> str:
    pct = max(0, min(100, score))
    color = "bar-green" if tier == "Tier 2" else "bar-blue" if tier == "Tier 1" else "bar-amber"
    if score < 35:
        color = "bar-red"
    return (
        f'<span class="mono">{score:.1f}</span>'
        f'<span class="bar-wrap"><span class="bar-fill {color}" style="width:{pct:.0f}%"></span></span>'
    )


def _row_highlight(card: dict[str, Any]) -> str:
    risk = float(card.get("score_risk_penalty") or 0)
    if card.get("vingroup_distortion_flag"):
        return ' style="background:rgba(240,80,80,.06)"'
    if risk >= 50:
        return ' style="background:rgba(240,160,48,.04)"'
    return ""


def _cards_table(
    cards: List[dict[str, Any]],
    *,
    mode: str = "tier",
) -> str:
    if not cards:
        return '<p class="diff-none">None this run.</p>'
    rows: list[str] = []
    for c in cards:
        tk_cls = "tk"
        if c.get("vingroup_distortion_flag"):
            tk_cls += " tk-red"
        elif float(c.get("score_risk_penalty") or 0) >= 45:
            tk_cls += " tk-warn"
        sector = c.get("sector") or "Unknown"
        sector_html = _esc(sector)
        if sector == "Unknown":
            sector_html = f'{sector_html} <span style="color:var(--amber)">⚠</span>'
        note = _esc(c.get("primary_driver") or "")
        risk_note = _esc(c.get("main_risk") or "")
        op_note = _esc(c.get("operator_note") or "")
        vin_badge = (
            ' <span class="badge b-vin">VIN flag</span>' if c.get("vingroup_distortion_flag") else ""
        )
        if mode == "reject":
            rows.append(
                f"<tr{_row_highlight(c)}>"
                f'<td><span class="{tk_cls}">{_esc(c["ticker"])}</span></td>'
                f'<td><span class="mono">{float(c["institutional_accumulation_score"]):.1f}</span></td>'
                f'<td><span class="mono">{float(c["score_money_flow"]):.0f}</span></td>'
                f'<td>{_risk_html(float(c["score_risk_penalty"]))}</td>'
                f"<td>{_bucket_badge(c.get('fund_context_bucket', ''))}</td>"
                f'<td style="font-size:11px;color:var(--dim)">{_esc(c.get("reject_failure_reason") or note)}</td>'
                f"</tr>"
            )
        else:
            ev_badge = _evidence_label_badge(str(c.get("evidence_label", "DISPLAY_ONLY")))
            rows.append(
                f"<tr{_row_highlight(c)}>"
                f'<td><span class="{tk_cls}">{_esc(c["ticker"])}</span></td>'
                f"<td>{_tier_badge(c.get('tier', ''))}</td>"
                f"<td>{_score_bar(float(c['institutional_accumulation_score']), str(c.get('tier', '')))}</td>"
                f"<td>{ev_badge}</td>"
                f'<td><span class="mono">{float(c["score_money_flow"]):.0f}</span></td>'
                f"<td>{_risk_html(float(c['score_risk_penalty']), bool(c.get('vingroup_distortion_flag')))}</td>"
                f"<td>{sector_html}</td>"
                f"<td>{_bucket_badge(c.get('fund_context_bucket', ''))}</td>"
                f'<td style="font-size:11px;color:var(--dim)">{_esc(c.get("primary_driver", ""))}{vin_badge}'
                f'<br><span style="color:var(--muted)">{risk_note}</span>'
                + (f'<br><span style="color:var(--accent)">{op_note}</span>' if op_note else "")
                + "</td>"
                f"</tr>"
            )
    if mode == "reject":
        head = "<tr><th>Ticker</th><th>Score</th><th>MF</th><th>Risk</th><th>Bucket</th><th>Failed because</th></tr>"
    else:
        head = (
            "<tr><th>Ticker</th><th>Tier</th><th>Score</th><th>Evidence</th><th>MF</th>"
            "<th>Risk</th><th>Sector</th><th>Bucket</th><th>Why / Risk</th></tr>"
        )
    return f'<div class="tbl-wrap"><table><thead>{head}</thead><tbody>{"".join(rows)}</tbody></table></div>'


def _bucket_mix_panel(diag: dict[str, Any]) -> str:
    mix = diag.get("bucket_mix_percentages_top_tier") or {}
    counts = diag.get("bucket_mix_counts_top_tier") or {}
    denom = _esc(diag.get("bucket_mix_denominator") or "")
    lines = []
    order = [
        ("outside_fund_disclosure", "Outside fund disclosure"),
        ("emerging", "Emerging (no fund tag)"),
        ("fund_backed", "Fund-backed"),
        ("caution_proxy", "Caution-proxy (§4 rule)"),
        ("vin_distortion_flagged", "vin_distortion_flag"),
    ]
    for key, label in order:
        if key not in mix:
            continue
        color = "var(--accent)" if key == "emerging" else "var(--text)"
        if key == "vin_distortion_flagged":
            color = "var(--red)"
        if key == "caution_proxy":
            color = "var(--amber)"
        lines.append(
            f'<div style="display:flex;justify-content:space-between">'
            f'<span style="color:var(--dim)">{_esc(label)}</span>'
            f'<span class="mono" style="color:{color}">{counts.get(key, 0)} / {mix[key]:.1f}%</span></div>'
        )
    vin_watch = diag.get("count_vin_watch_in_caution_proxy")
    foot = ""
    if vin_watch:
        foot = (
            f'<p style="font-size:10px;color:var(--amber);margin-top:6px">'
            f"VIN watch in caution-proxy: {vin_watch} (may not increment vin_distortion_flagged %)</p>"
        )
    return (
        f'<div style="background:var(--panel);border:1px solid var(--border);border-radius:4px;padding:9px 12px">'
        f'<div style="font-size:9px;color:var(--muted);text-transform:uppercase;margin-bottom:6px">Bucket mix</div>'
        f'<div style="font-size:10px;color:var(--dim);margin-bottom:6px">{denom}</div>'
        f'<div style="display:flex;flex-direction:column;gap:4px;font-size:11px">{"".join(lines)}</div>'
        f"{foot}</div>"
    )


def _changes_panel(ch: dict[str, Any]) -> str:
    if ch.get("note") == "no_previous_scan":
        return (
            '<div style="background:var(--panel);border:1px solid var(--border);border-radius:4px;padding:9px 12px">'
            '<div style="font-size:9px;color:var(--muted);text-transform:uppercase;margin-bottom:6px">WoW changes</div>'
            '<p class="diff-none">No prior dated scan.</p></div>'
        )
    prev = ch.get("previous_scan_date") or ""
    if not ch.get("has_meaningful_changes"):
        return (
            '<div style="background:var(--panel);border:1px solid var(--border);border-radius:4px;padding:9px 12px">'
            '<div style="font-size:9px;color:var(--muted);text-transform:uppercase;margin-bottom:6px">WoW changes</div>'
            f'<p style="font-size:10px;color:var(--dim)">vs {_esc(prev)}</p>'
            '<p class="diff-none">No meaningful tier or score changes.</p></div>'
        )
    parts = [f'<p style="font-size:10px;color:var(--dim)">vs {_esc(prev)}</p>']
    if ch.get("new_tier12"):
        parts.append(
            f'<p style="font-size:11px"><span style="color:var(--accent)">+T1–2:</span> {_esc(", ".join(ch["new_tier12"][:14]))}</p>'
        )
    if ch.get("dropped_tier12"):
        parts.append(
            f'<p style="font-size:11px"><span style="color:var(--red)">−T1–2:</span> {_esc(", ".join(ch["dropped_tier12"][:14]))}</p>'
        )
    for tc in (ch.get("tier_changes") or [])[:6]:
        parts.append(
            f'<p style="font-size:11px;color:var(--dim)">{_esc(tc.get("ticker"))}: '
            f'{_esc(tc.get("tier_prev"))}→{_esc(tc.get("tier_cur"))}</p>'
        )
    for g in (ch.get("biggest_score_gains") or [])[:3]:
        parts.append(
            f'<p style="font-size:11px;color:var(--accent)">↑ {_esc(g.get("ticker"))} Δ{g.get("score_delta", 0):+.1f}</p>'
        )
    return (
        '<div style="background:var(--panel);border:1px solid var(--border);border-radius:4px;padding:9px 12px">'
        '<div style="font-size:9px;color:var(--muted);text-transform:uppercase;margin-bottom:6px">WoW changes</div>'
        + "".join(parts)
        + "</div>"
    )


def _warnings_html(warnings: List[str]) -> str:
    if not warnings:
        return '<p class="diff-none">No elevated workflow warnings.</p>'
    out = []
    for w in warnings:
        cls = "warn-strip"
        if w.startswith("[P1"):
            cls += " p1-strip crit-strip"
        elif "VIN" in w or "caution" in w.lower():
            cls = "crit-strip" if "vin_distortion_flag=0" in w else "warn-strip"
        out.append(f'<div class="{cls}">{_esc(w)}</div>')
    return "".join(out)


def _signals_html(payload: dict[str, Any]) -> str:
    diag = payload.get("bucket_diagnostics") or {}
    tiers = diag.get("tier_counts") or {}
    t2 = payload.get("tier2_focus_list") or []
    lines = []
    if tiers.get("Tier 1", 0) == 0:
        lines.append(
            '<div class="signal-row"><div class="signal-label" style="color:var(--amber)">No Tier 1</div>'
            '<div class="signal-body">Use Tier 2 focus list + tier3 near-miss; fragile regime floors active.</div></div>'
        )
    if t2:
        tickers = ", ".join(c["ticker"] for c in t2[:8])
        lines.append(
            f'<div class="signal-row"><div class="signal-label" style="color:var(--blue)">Tier 2 focus</div>'
            f'<div class="signal-body">Monitor flow persistence: {_esc(tickers)}</div></div>'
        )
    ch = payload.get("changes_since_previous") or {}
    if ch.get("new_tier12"):
        lines.append(
            f'<div class="signal-row"><div class="signal-label">New T1–2</div>'
            f'<div class="signal-body">{_esc(", ".join(ch["new_tier12"][:10]))}</div></div>'
        )
    if not lines:
        lines.append('<p class="diff-none">See workflow warnings and scan CSV for detail.</p>')
    return "".join(lines)


def _playbook_html(payload: dict[str, Any]) -> str:
    ch = payload.get("changes_since_previous") or {}
    rows = [
        (
            "Any consensus_core name crosses fragile Tier 3 floor with CMF daily+weekly &gt; 0",
            "Re-run scan; upgrade research priority if MF confirms",
        ),
        (
            "VIN watch name (VIC/VHM) risk_penalty drops below 45",
            "Re-check caution-proxy; distortion flag may still be off",
        ),
        (
            "Emerging count shifts &gt;5 vs prior scan",
            "Reconcile with April fund priors; check for regime shift",
        ),
    ]
    if ch.get("dropped_tier12"):
        rows.append(
            (
                f"Prior Tier 1–2 dropped: {', '.join(ch['dropped_tier12'][:5])}",
                "Review whether flow deterioration is broad or name-specific",
            )
        )
    html_rows = []
    for cond, action in rows[:6]:
        html_rows.append(
            '<div class="playbook-if" style="background:var(--panel);border:1px solid var(--border);'
            'border-radius:4px;padding:8px 10px;font-size:11px">'
            f'<div style="font-size:9px;color:var(--muted);text-transform:uppercase">If</div>'
            f'<div style="color:var(--amber);margin:4px 0">{_esc(cond)}</div>'
            f'<div style="font-size:9px;color:var(--muted);text-transform:uppercase;margin-top:6px">Then</div>'
            f'<div>{_esc(action)}</div></div>'
        )
    return (
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">'
        + "".join(html_rows)
        + "</div>"
    )


def _evidence_label_badge(label: str) -> str:
    lbl = str(label or "INCONCLUSIVE_NOT_BUY_SIGNAL")
    if lbl == "HEAT_RISK_MANUAL_REVIEW":
        return f'<span class="badge" style="background:rgba(240,160,48,.15);color:var(--amber);font-size:9px">{_esc(lbl)}</span>'
    if lbl == "AVOID_OR_MANUAL_REVIEW":
        return f'<span class="badge" style="background:rgba(240,80,80,.12);color:var(--red);font-size:9px">{_esc(lbl)}</span>'
    if lbl == "RISK_CLEAN_RESEARCH_ONLY":
        return f'<span class="badge" style="background:rgba(0,200,150,.15);color:var(--accent);font-size:9px">{_esc(lbl)}</span>'
    if lbl == "RISK_CONTROL_SUPPORTED":
        return f'<span class="badge" style="background:rgba(74,158,255,.12);color:var(--blue);font-size:9px">{_esc(lbl)}</span>'
    if lbl == "DISPLAY_ONLY":
        return f'<span class="badge" style="background:rgba(122,131,153,.12);color:var(--dim);font-size:9px">{_esc(lbl)}</span>'
    return f'<span class="badge" style="background:rgba(122,131,153,.12);color:var(--dim);font-size:9px">{_esc(lbl)}</span>'


def _evidence_status_html(cfg: dict[str, Any]) -> str:
    """Full-history v0.2 evidence banner from SSOT config."""
    from .operator_explain import EVIDENCE_RESEARCH_NOTE, EVIDENCE_SAFETY_NOTE

    n_prom = int(cfg.get("portfolio_promising_count", 0))
    findings = [
        ("Portfolio promotion", str(cfg.get("portfolio_promotion", "NO-GO")), "ev-val-red"),
        ("Validated portfolio-promising variants", str(n_prom), "ev-val-red"),
        ("Raw IA score", str(cfg.get("raw_score_assessment", "INCONCLUSIVE / not a buy signal")), "ev-val-warn"),
        ("Top-decile score", str(cfg.get("top_decile_assessment", "HEAT_RISK / manual review")), "ev-val-warn"),
        (
            "Distribution-risk filter",
            str(cfg.get("distribution_filter_assessment", "RISK_CONTROL_SUPPORTED")),
            "ev-val-ok",
        ),
        ("Best use", str(cfg.get("best_use", "risk avoidance + research prioritization")), "ev-val-dim"),
    ]
    rows = "".join(
        f'<div class="ev-row"><span class="ev-label">{_esc(label)}</span>'
        f'<span class="{cls}">{_esc(val)}</span></div>'
        for label, val, cls in findings
    )
    safety = str(cfg.get("safety_note") or EVIDENCE_SAFETY_NOTE)
    report_path = str(cfg.get("validation_report_path") or "")
    return (
        f'<div class="evidence-banner">'
        f'<div class="ev-title">{_esc(cfg.get("banner_title", "Full-History Evidence Status"))} '
        f'— RESEARCH_ONLY_NOT_PRODUCTION</div>'
        f"{rows}"
        f"</div>"
        f'<div class="safety-note">&#x26A0; {_esc(safety)}</div>'
        f'<div class="research-note">&#x1F4CB; {_esc(EVIDENCE_RESEARCH_NOTE)}</div>'
        f'<p style="font-size:10px;color:var(--muted);margin-top:8px">'
        f"Full-history validation source: <span class=\"mono\">{_esc(report_path)}</span></p>"
    )


def _how_to_read_html(cfg: dict[str, Any]) -> str:
    text = str(
        cfg.get("how_to_read")
        or "Use this dashboard to avoid weak/risky setups first, then prioritize manual research."
    )
    return f'<p class="section-note">{_esc(text)}</p>'


def _benchmark_context_html(cfg: dict[str, Any]) -> str:
    """Full-history portfolio simulation context (defensive; not P3.2-only)."""
    bench = cfg.get("benchmark_context") or {}
    if not isinstance(bench, dict):
        bench = {}
    rows = [
        ("Analysis window", str(bench.get("analysis_window", "2017–2026 stock universe"))),
        ("PORTFOLIO_PROMISING variants", str(bench.get("portfolio_promising_variants", 0))),
        ("VNINDEX caveat", str(bench.get("vnindex_caveat", ""))),
        ("Benchmark guidance", str(bench.get("primary_benchmark_note", ""))),
        ("V4 variant role", str(bench.get("v4_variant_note", ""))),
        (
            "2024+ sensitivity (P3.2 only)",
            "Modern-liquidity window showed mixed results; not primary SSOT for promotion.",
        ),
    ]
    html_rows = "".join(
        f'<div class="bench-row"><span class="bench-label">{_esc(k)}</span>'
        f'<span class="bench-val">{_esc(v)}</span></div>'
        for k, v in rows
    )
    return (
        f'<div style="background:var(--panel);border:1px solid var(--border);border-radius:4px;padding:10px 14px">'
        f'<div style="font-size:9px;color:var(--muted);text-transform:uppercase;margin-bottom:8px">'
        f"Full-History Portfolio Simulation Context</div>"
        f"{html_rows}"
        f"</div>"
        f'<p style="font-size:10px;color:var(--muted);margin-top:8px">'
        f"Useful risk/research dashboard — not a validated alpha engine. "
        f"RESEARCH_ONLY_NOT_PRODUCTION.</p>"
    )


def _evidence_queue_table(cards: List[dict[str, Any]], *, section: str = "risk_clean") -> str:
    if not cards:
        return '<p class="diff-none">None this scan.</p>'
    rows: list[str] = []
    for c in cards:
        ev_label = str(c.get("evidence_label", ""))
        if section == "dist" and not ev_label:
            ev_label = "AVOID_OR_MANUAL_REVIEW"
        if section == "risk_clean" and not ev_label:
            ev_label = "RISK_CLEAN_RESEARCH_ONLY"
        ev_badge = _evidence_label_badge(ev_label)
        decile = int(c.get("score_decile", 0))
        ext = float(c.get("extension_pct_above_ma20", 0))
        dd25 = float(c.get("distribution_days_25", 0))
        turn = float(c.get("turnover_accel_ratio_5d50d", 0))
        dist_flag = bool(c.get("distribution_risk_flag", False))
        risk_pen = float(c.get("score_risk_penalty", 0))
        op_note = _esc(c.get("operator_note") or c.get("dashboard_operator_note", ""))
        rows.append(
            f"<tr>"
            f'<td><span class="tk">{_esc(c["ticker"])}</span></td>'
            f"<td>{_score_bar(float(c['institutional_accumulation_score']), str(c.get('tier', '')))}</td>"
            f'<td><span class="mono">{decile}</span></td>'
            f"<td>{_tier_badge(c.get('tier', ''))}</td>"
            f'<td><span class="mono">{"Y" if dist_flag else "N"}</span></td>'
            f'<td><span class="mono">{dd25:.0f}</span></td>'
            f'<td><span class="mono">{ext:.1f}%</span></td>'
            f"<td>{_risk_html(risk_pen)}</td>"
            f"<td>{ev_badge}</td>"
            f'<td style="font-size:10px;color:var(--dim)">{op_note}</td>'
            f"</tr>"
        )
    head = (
        "<tr><th>Ticker</th><th>Score</th><th>Decile</th><th>Tier</th>"
        "<th>Dist flag</th><th>DD25</th><th>Ext%MA20</th><th>Risk</th>"
        "<th>Evidence</th><th>Operator note</th></tr>"
    )
    if section == "heat":
        head = (
            "<tr><th>Ticker</th><th>Score</th><th>Decile</th><th>Tier</th>"
            "<th>Ext%MA20</th><th>Turnover</th><th>DD25</th><th>Dist flag</th>"
            "<th>Evidence</th><th>Operator note</th></tr>"
        )
        rows = []
        for c in cards:
            ev_badge = _evidence_label_badge(c.get("evidence_label", "HEAT_RISK_MANUAL_REVIEW"))
            rows.append(
                f"<tr>"
                f'<td><span class="tk">{_esc(c["ticker"])}</span></td>'
                f"<td>{_score_bar(float(c['institutional_accumulation_score']), str(c.get('tier', '')))}</td>"
                f'<td><span class="mono">{int(c.get("score_decile", 0))}</span></td>'
                f"<td>{_tier_badge(c.get('tier', ''))}</td>"
                f'<td><span class="mono">{float(c.get("extension_pct_above_ma20", 0)):.1f}%</span></td>'
                f'<td><span class="mono">{float(c.get("turnover_accel_ratio_5d50d", 0)):.2f}</span></td>'
                f'<td><span class="mono">{float(c.get("distribution_days_25", 0)):.0f}</span></td>'
                f'<td><span class="mono">{"Y" if c.get("distribution_risk_flag") else "N"}</span></td>'
                f"<td>{ev_badge}</td>"
                f'<td style="font-size:10px;color:var(--dim)">{_esc(c.get("dashboard_operator_note", ""))}</td>'
                f"</tr>"
            )
    return f'<div class="tbl-wrap"><table><thead>{head}</thead><tbody>{"".join(rows)}</tbody></table></div>'


def _research_actions_html() -> str:
    actions = [
        ("V4 filter passed (risk_clean_flag=True)", "Include in research pipeline — distribute to risk-clean queue"),
        ("top_decile_heat_risk=True", "Flag for late-stage review; confirm MF trend before any sizing"),
        ("distribution_risk_flag=True", "Exclude from accumulation thesis; monitor for flag removal"),
        ("controlled_accumulation_flag=True", "Priority for controlled-entry research; combine with CMF confirmation"),
        ("Score decile 9+ without heat condition", "Neutral — score rank not validated; verify with MF block"),
        ("V4B (decile 6–8) + score_risk_reduction_only", "Risk-reduction application only; not entry signal"),
    ]
    rows = "".join(
        f'<div style="background:var(--panel);border:1px solid var(--border);border-radius:4px;'
        f'padding:8px 10px;font-size:11px;margin-bottom:6px">'
        f'<div style="font-size:9px;color:var(--muted);text-transform:uppercase;margin-bottom:3px">Condition</div>'
        f'<div style="color:var(--amber)">{_esc(cond)}</div>'
        f'<div style="font-size:9px;color:var(--muted);text-transform:uppercase;margin-top:5px;margin-bottom:2px">Research action</div>'
        f'<div style="color:var(--text)">{_esc(action)}</div>'
        f"</div>"
        for cond, action in actions
    )
    return f'<div style="columns:2;column-gap:8px">{rows}</div>'


def _not_promote_html() -> str:
    items = [
        "Do not use raw IA score as buy rank.",
        "Do not use top decile as automatic priority.",
        "Do not route IA output to OMS.",
        "Do not modify final_action from this dashboard.",
        "Do not size positions from IA evidence labels.",
        "Do not trade IA variants live.",
    ]
    rows = "".join(
        f'<div class="not-promote-item">{_esc(item)}</div>' for item in items
    )
    return f'<div style="font-size:12px">{rows}</div>'


def _liquid_appendix_html(scan_date: str) -> str:
    """Build Tier 2/3 liquid stock tables for the appendix section."""
    try:
        import pandas as pd

        csv_path = (
            Path(__file__).parents[3]
            / "outputs"
            / "scans"
            / f"institutional_accumulation_{scan_date}.csv"
        )
        if not csv_path.exists():
            return '<p class="diff-none">Scan CSV not found — run scan pipeline to populate.</p>'
        df = pd.read_csv(csv_path, low_memory=False)
        liq_mask = df["liquidity_ok"].astype(str).str.lower().isin(["true", "1"])
        liquid = df[liq_mask].sort_values("institutional_accumulation_score", ascending=False)
        if liquid.empty:
            return '<p class="diff-none">No liquid stocks in scan CSV.</p>'

        def _tier_tbl(sub: "pd.DataFrame") -> str:
            rows = []
            for _, r in sub.iterrows():
                score = float(r.get("institutional_accumulation_score") or 0)
                risk = float(r.get("score_risk_penalty") or 0)
                sector = str(r.get("sector") or "Unknown")
                tier = str(r.get("tier") or "")
                rows.append(
                    f"<tr>"
                    f'<td><span class="tk">{_esc(r["ticker"])}</span></td>'
                    f"<td>{_tier_badge(tier)}</td>"
                    f"<td>{_score_bar(score, tier)}</td>"
                    f"<td>{_risk_html(risk)}</td>"
                    f'<td style="font-size:11px;color:var(--dim)">{_esc(sector)}</td>'
                    f"</tr>"
                )
            head = (
                "<tr><th>Ticker</th><th>Tier</th><th>Score</th>"
                "<th>Risk</th><th>Sector</th></tr>"
            )
            return (
                f'<div class="tbl-wrap"><table><thead>{head}</thead>'
                f'<tbody>{"".join(rows)}</tbody></table></div>'
            )

        def _sub_block(label: str, sub: "pd.DataFrame") -> str:
            if sub.empty:
                return ""
            return (
                f'<div style="margin-bottom:14px">'
                f'<div style="font-size:9px;color:var(--muted);text-transform:uppercase;'
                f'margin-bottom:6px">{label} ({len(sub)})</div>'
                f"{_tier_tbl(sub)}</div>"
            )

        parts: list[str] = [
            f'<p class="section-note">{len(liquid)} stocks pass liquidity screen'
            f" — sorted by score desc within tier.</p>"
        ]
        for tier_label in ("Tier 1", "Tier 2", "Tier 3"):
            parts.append(_sub_block(tier_label, liquid[liquid["tier"] == tier_label]))
        rej = liquid[liquid["tier"] == "Reject"]
        if not rej.empty:
            parts.append(
                f'<p style="font-size:11px;color:var(--muted);margin-top:4px">'
                f"Liquid Rejects (fail accumulation score): {len(rej)}</p>"
            )
        return "".join(parts)
    except Exception as exc:
        return f'<p class="diff-none">Liquid tier data error: {_esc(str(exc))}</p>'


def render_operator_summary_html(payload: Dict[str, Any]) -> str:
    """Build full HTML document from operator summary JSON payload."""
    scan_date = payload.get("scan_date") or "N/A"
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    diag = payload.get("bucket_diagnostics") or {}
    tiers = diag.get("tier_counts") or {}
    look = payload.get("look_first") or {}
    ch = payload.get("changes_since_previous") or {}

    ev = payload.get("evidence_lists") or {}
    n_risk_clean = ev.get("n_risk_clean", 0)
    n_heat = ev.get("n_heat_warnings", 0)
    n_dist = ev.get("n_dist_avoid", 0)
    ev_cfg = payload.get("evidence_config") or {}
    if not ev_cfg:
        from .operator_explain import load_dashboard_evidence_config

        ev_cfg = load_dashboard_evidence_config()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Institutional Accumulation — {_esc(scan_date)}</title>
  <style>{_CSS}
  .signal-row{{display:flex;gap:12px;padding:7px 0;border-bottom:1px solid rgba(37,42,53,.6)}}
  .signal-row:last-child{{border-bottom:none}}
  .signal-label{{color:var(--dim);font-size:11px;min-width:120px;flex-shrink:0}}
  .signal-body{{font-size:11px}}
  </style>
</head>
<body>
<div class="layout">
<aside class="sidebar">
  <div class="sidebar-logo">Inst. Accumulation</div>
  <h3>Overview</h3>
  <a href="#header">Header</a>
  <a href="#evidence-status">Evidence Status</a>
  <a href="#how-to-read">How To Read</a>
  <a href="#benchmark-context">Benchmark</a>
  <a href="#snapshot">Snapshot</a>
  <a href="#changes">Changes</a>
  <h3>Evidence Lists</h3>
  <a href="#risk-clean">Risk-Clean Queue</a>
  <a href="#heat-warnings">Heat Warnings</a>
  <a href="#dist-avoid">Dist. Avoid</a>
  <h3>Candidates</h3>
  <a href="#fund-backed">Fund-Backed</a>
  <a href="#emerging">Emerging</a>
  <h3>Risk</h3>
  <a href="#rejects">Key Rejects</a>
  <a href="#distortion">Caution</a>
  <a href="#warnings">Warnings</a>
  <h3>Playbook</h3>
  <a href="#signals">Signals</a>
  <a href="#playbook">If X → Do Y</a>
  <a href="#research-actions">Research Actions</a>
  <a href="#not-promote">What NOT To Do</a>
  <h3>Files</h3>
  <a href="#files">File Map</a>
  <a href="#appendix">Liquid Tiers</a>
</aside>
<main class="main">

<section class="card" id="header">
  <h1 class="report-title">Institutional Accumulation Scan</h1>
  <p class="report-meta">ASOF {_esc(scan_date)} · Generated {_esc(generated)} · v{_esc(payload.get("methodology_version"))} · {diag.get("rows_scored", 0):,} rows</p>
  <div class="warn-strip" style="margin-top:10px">
    <strong>Date split:</strong> Market / OHLCV as-of <span class="mono">{_esc(scan_date)}</span>
    · Fund / smart-money context: <span class="mono">{_esc(payload.get("smart_money_month") or "2026-04")}</span>
    ({_esc(payload.get("context_source"))}) — fund priors not rolled to May
  </div>
  <div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap;align-items:center">
    <span class="regime-badge">{_esc(payload.get("regime_label"))}</span>
  </div>
  <p style="font-size:11px;color:var(--muted);margin-top:10px">Research / prioritization only — not <code style="color:var(--red)">final_action</code>, orders, OMS, or execution</p>
</section>

<section class="card" id="evidence-status">
  <div class="card-title">Full-History Evidence Status</div>
  {_evidence_status_html(ev_cfg)}
  <div style="margin-top:12px" class="evidence-kpi-grid">
    <div class="kpi kpi-accent"><div class="label">Risk-Clean Queue</div><div class="value">{n_risk_clean}</div><div class="sub">No dist risk; not heat; decile 5–8 preferred</div></div>
    <div class="kpi kpi-amber"><div class="label">Heat Warnings</div><div class="value">{n_heat}</div><div class="sub">Decile ≥9 or heat-risk label</div></div>
    <div class="kpi kpi-red"><div class="label">Dist. Avoid</div><div class="value">{n_dist}</div><div class="sub">distribution_risk_flag=True</div></div>
  </div>
</section>

<section class="card" id="how-to-read">
  <div class="card-title">How To Read This Dashboard</div>
  {_how_to_read_html(ev_cfg)}
</section>

<section class="card card-blue" id="benchmark-context">
  <div class="card-title">Full-History Benchmark Context</div>
  <p class="section-note">Portfolio simulation context from full-history validation (2017–2026 universe). Not a buy signal.</p>
  {_benchmark_context_html(ev_cfg)}
</section>

<section class="card" id="snapshot">
  <div class="card-title">Scan Snapshot</div>
  <div class="kpi-grid">
    <div class="kpi kpi-dim"><div class="label">Tier 1</div><div class="value">{tiers.get("Tier 1", 0)}</div></div>
    <div class="kpi kpi-blue"><div class="label">Tier 2</div><div class="value">{tiers.get("Tier 2", 0)}</div></div>
    <div class="kpi kpi-amber"><div class="label">Tier 3</div><div class="value">{tiers.get("Tier 3", 0)}</div></div>
    <div class="kpi kpi-red"><div class="label">Reject</div><div class="value">{tiers.get("Reject", 0)}</div></div>
    <div class="kpi kpi-accent"><div class="label">Emerging</div><div class="value">{diag.get("emerging_count_total", 0)}</div></div>
    <div class="kpi kpi-amber"><div class="label">Caution-proxy</div><div class="value">{diag.get("count_top_tier_caution_proxy", 0)}</div></div>
  </div>
  <div style="margin-top:10px;display:grid;grid-template-columns:1fr 1fr;gap:8px">
    {_bucket_mix_panel(diag)}
    {_changes_panel(ch)}
  </div>
</section>

<section class="card" id="changes">
  <div class="card-title">Changes Since Previous Scan</div>
  {_changes_panel(ch).replace("WoW changes", "Detail")}
</section>

<section class="card card-ok" id="risk-clean">
  <div class="card-title">Risk-Clean Research Queue</div>
  <p class="section-note">distribution_risk_flag=False AND not top-decile heat-risk; score_decile 5–8 preferred. Label: RISK_CLEAN_RESEARCH_ONLY. Not a buy signal.</p>
  {_evidence_queue_table(ev.get("risk_clean_queue") or [], section="risk_clean")}
</section>

<section class="card card-warn" id="heat-warnings">
  <div class="card-title">Top-Decile Heat / Exhaustion Warnings</div>
  <p class="section-note">score_decile ≥ 9 or HEAT_RISK_MANUAL_REVIEW. High score may reflect late-stage heat — manual review only.</p>
  {(f'<div class="warn-strip">&#x26A0; {n_heat} top-decile heat name(s) detected this scan. Review before any sizing consideration.</div>' if n_heat > 0 else '<p class="diff-none">No top-decile heat conditions triggered this scan.</p>')}
  {_evidence_queue_table(ev.get("heat_warning_names") or [], section="heat")}
</section>

<section class="card card-alert" id="dist-avoid">
  <div class="card-title">Distribution-Risk Avoid / Manual Review List</div>
  <p class="section-note">distribution_risk_flag=True. Label: AVOID_OR_MANUAL_REVIEW. Full-history evidence supports distribution-risk filtering as risk control only.</p>
  {_evidence_queue_table(ev.get("dist_avoid_names") or [], section="dist")}
</section>

<section class="card card-ok" id="fund-backed">
  <div class="card-title">Fund-Backed Candidates (Tier 1–3)</div>
  <p class="section-note">Fund disclosure tags only — flow confirmation still required. Check dashboard_operator_note for backtest evidence caveat per name.</p>
  {_cards_table(look.get("fund_backed_candidates") or [])}
</section>

<section class="card card-blue" id="emerging">
  <div class="card-title">Emerging Candidates (no fund tag)</div>
  <p class="section-note">Tier 1–3, MF gate, risk ≤30, no fund disclosure tag. Score rank not validated — use MF confirmation.</p>
  {_cards_table(look.get("emerging_candidates") or [])}
</section>

<section class="card card-warn" id="rejects">
  <div class="card-title">Important Rejects (fund-linked)</div>
  <p class="section-note">Consensus / commentary names failing flow confirmation.</p>
  {_cards_table(look.get("important_rejects") or [], mode="reject")}
</section>

<section class="card card-alert" id="distortion">
  <div class="card-title">Elevated Risk / Distortion / Distribution</div>
  <p class="section-note">Matches caution-proxy % in bucket mix (risk≥45, dist flag, or vin flag).</p>
  {_cards_table(look.get("distortion_caution") or [])}
</section>

<section class="card card-warn" id="warnings">
  <div class="card-title">Workflow Warnings (priority order)</div>
  {_warnings_html(payload.get("key_warnings") or [])}
</section>

<section class="card" id="signals">
  <div class="card-title">Signals to Monitor Next Week</div>
  {_signals_html(payload)}
</section>

<section class="card" id="playbook">
  <div class="card-title">If X → Do Y (research steps only)</div>
  {_playbook_html(payload)}
</section>

<section class="card" id="research-actions">
  <div class="card-title">Research Actions by Evidence Flag</div>
  <p class="section-note">How to use each derived evidence field in practice.</p>
  {_research_actions_html()}
</section>

<section class="card card-alert" id="not-promote">
  <div class="card-title">What NOT To Promote From This Dashboard</div>
  <p class="section-note">Research-only. Does not set final_action, OMS orders, DNSE routing, sizing, or live execution.</p>
  {_not_promote_html()}
</section>

<section class="card" id="files">
  <div class="card-title">Output File Map</div>
  <div class="filemap">
    <div class="fmap-row fmap-active">
      <div class="fmap-path">institutional_accumulation_operator_summary_{scan_date}.html</div>
      <div class="fmap-role">This file — start here (browser)</div>
    </div>
    <div class="fmap-row fmap-active">
      <div class="fmap-path">institutional_accumulation_operator_summary_{scan_date}.md</div>
      <div class="fmap-role">Same content — markdown</div>
    </div>
    <div class="fmap-row"><div class="fmap-path">institutional_accumulation_{scan_date}.csv</div><div class="fmap-role">Full universe</div></div>
    <div class="fmap-row"><div class="fmap-path">data/decision/institutional_accumulation_compact.json</div><div class="fmap-role">Weekly compact</div></div>
  </div>
</section>

<section class="card" id="appendix">
  <div class="card-title">Appendix — Liquid Universe Tiers (liquidity_ok = True)</div>
  {_liquid_appendix_html(scan_date)}
</section>

</main></div>
<script>
const sections=document.querySelectorAll('section[id]');
const links=document.querySelectorAll('.sidebar a');
const obs=new IntersectionObserver(entries=>{{
  entries.forEach(e=>{{if(e.isIntersecting){{
    links.forEach(l=>l.classList.remove('active'));
    const a=document.querySelector('.sidebar a[href="#'+e.target.id+'"]');
    if(a)a.classList.add('active');
  }}}});
}},{{threshold:0.25}});
sections.forEach(s=>obs.observe(s));
</script>
</body>
</html>"""


def validate_operator_summary_html(doc: str) -> list[str]:
    """Return validation errors; empty list means acceptance criteria pass."""
    errors: list[str] = []
    for sid in OPERATOR_HTML_SECTION_IDS:
        if f'id="{sid}"' not in doc:
            errors.append(f"missing section id={sid}")
    if "IntersectionObserver" not in doc:
        errors.append("missing IntersectionObserver scroll-spy script")
    if 'class="kpi-grid"' not in doc:
        errors.append("missing KPI grid")
    if 'class="sidebar"' not in doc:
        errors.append("missing sidebar nav")
    if 'id="header"' not in doc:
        errors.append("missing header overview section")
    if "Full-History" not in doc:
        errors.append("missing Full-History evidence status section content")
    if "PORTFOLIO_PROMISING" not in doc and "portfolio-promising" not in doc.lower():
        errors.append("missing portfolio-promising count reference")
    safety = "This dashboard does not set final_action, OMS orders, DNSE routing, sizing, or live execution."
    if safety not in doc:
        errors.append("missing exact research-only safety note")
    if "not a buy signal" not in doc.lower() and "not validated as a buy" not in doc.lower():
        errors.append("missing score-not-buy-signal caveat")
    if "full_history_accumulation_validation.html" not in doc:
        errors.append("missing full-history validation report reference")
    if "RESEARCH_ONLY_NOT_PRODUCTION" not in doc:
        errors.append("missing RESEARCH_ONLY safety banner text")
    return errors


def write_operator_summary_html(path: Path, payload: Dict[str, Any]) -> None:
    doc = render_operator_summary_html(payload)
    errs = validate_operator_summary_html(doc)
    if errs:
        raise ValueError("operator summary HTML failed acceptance: " + "; ".join(errs))
    path.write_text(doc, encoding="utf-8")
