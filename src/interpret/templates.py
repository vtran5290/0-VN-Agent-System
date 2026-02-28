from __future__ import annotations
from typing import Dict, Any, List

# Intake type → section heading
INTAKE_TYPE_HEADING = {
    "macro_report": "Macro",
    "sector_report": "Sector",
    "company_report": "Company",
    "policy_report": "Policy",
}

def render_research_intake_section(notes: Dict[str, Any]) -> List[str]:
    """Render intake_takeaways from weekly_notes as 'Research Intake This Week' (Macro / Sector / Company / Policy)."""
    lines = []
    lines.append("## Research Intake This Week")
    takeaways = notes.get("intake_takeaways") or []
    if not takeaways:
        lines.append("- None reported this week.")
        return lines
    by_type: Dict[str, List[Dict[str, Any]]] = {}
    for t in takeaways:
        typ = t.get("type") or "company_report"
        by_type.setdefault(typ, []).append(t)
    for typ in ("macro_report", "sector_report", "company_report", "policy_report"):
        items = by_type.get(typ, [])
        if not items:
            continue
        heading = INTAKE_TYPE_HEADING.get(typ, typ.replace("_report", "").title())
        lines.append(f"### {heading}")
        for it in items:
            bullets = it.get("summary_bullets") or []
            if not bullets and it.get("summary"):
                lines.append(f"- {it.get('summary')}")
            for b in bullets:
                lines.append(f"  {b}")
        lines.append("")
    return lines

def render_policy_section(notes: Dict[str, Any]) -> List[str]:
    lines = []
    lines.append("## Vietnam Policy")
    items = notes.get("policy_facts", [])
    lines.append("- FACTS:")
    if not items or all(not it.get("summary") or str(it.get("summary", "")).strip().lower().startswith("unknown") for it in items):
        lines.append("  - None reported this week.")
        return lines
    for it in items:
        s = (it.get("summary") or "").strip()
        if s.lower().startswith("unknown"):
            continue
        lines.append(f"  - {it.get('date')} | {it.get('title')} | {s}")
    if len(lines) <= 2:
        lines = [lines[0], lines[1], "  - None reported this week."]
    return lines

def render_earnings_section(notes: Dict[str, Any]) -> List[str]:
    lines = []
    lines.append("## Sectors & Companies (Earnings / Broker Notes)")
    lines.append("- FACTS:")
    earnings = [e for e in notes.get("earnings_facts", []) if e.get("summary") and str(e.get("summary", "")).strip().lower() not in ("unknown", "unknown (fill later)")]
    brokers = [b for b in notes.get("broker_notes", []) if b.get("summary") and str(b.get("summary", "")).strip().lower() not in ("unknown", "unknown (fill later)")]
    if not earnings and not brokers:
        lines.append("  - None reported this week.")
        return lines
    for e in earnings:
        lines.append(f"  - {e.get('ticker')} | {e.get('period')} | {e.get('summary')}")
    for b in brokers:
        lines.append(f"  - {b.get('firm')} | {b.get('ticker')} | {b.get('summary')}")
    return lines


def render_portfolio_health_section(
    tech_status: Dict[str, Any],
    sell_eval: List[Dict[str, Any]],
) -> List[str]:
    """Render Portfolio Health: % below MA20, % sell_v4 active, avg R multiple, risk by sector."""
    lines = []
    lines.append("## Portfolio Health")
    tickers = tech_status.get("tickers") or []
    if not tickers:
        lines.append("- No positions in tech_status; add tickers for diagnostics.")
        return lines
    n = len(tickers)
    below_ma = sum(1 for t in tickers if t.get("close_below_ma") is True)
    pct_below_ma = round(100 * below_ma / n, 1) if n else 0
    lines.append(f"- **% positions below MA20:** {pct_below_ma}% ({below_ma}/{n})")

    sell_active = sum(1 for s in sell_eval if (s.get("action") or "HOLD") != "HOLD")
    pct_sell = round(100 * sell_active / n, 1) if n else 0
    lines.append(f"- **% positions with sell/trim active:** {pct_sell}% ({sell_active}/{n})")

    r_vals = [t.get("r_multiple") for t in tickers if t.get("r_multiple") is not None]
    if r_vals:
        try:
            avg_r = round(sum(float(x) for x in r_vals) / len(r_vals), 2)
            lines.append(f"- **Avg R multiple (open):** {avg_r}")
        except (TypeError, ValueError):
            lines.append("- **Avg R multiple (open):** — (invalid r_multiple)")
    else:
        lines.append("- **Avg R multiple (open):** — (add r_multiple in tech_status)")

    sectors: Dict[str, int] = {}
    for t in tickers:
        sec = t.get("sector") or "—"
        sectors[sec] = sectors.get(sec, 0) + 1
    if any(s != "—" for s in sectors):
        lines.append("- **Risk concentration by sector:**")
        for sec, count in sorted(sectors.items(), key=lambda x: -x[1]):
            pct = round(100 * count / n, 1)
            lines.append(f"  - {sec}: {pct}% ({count})")
    else:
        lines.append("- **Risk concentration by sector:** — (add sector in tech_status)")
    return lines
