from __future__ import annotations
from typing import Dict, Any, List

def render_policy_section(notes: Dict[str, Any]) -> List[str]:
    lines = []
    lines.append("## Vietnam Policy")
    items = notes.get("policy_facts", [])
    lines.append("- FACTS:")
    if not items:
        lines.append("  - Unknown (no policy facts provided)")
        return lines
    for it in items:
        lines.append(f"  - {it.get('date')} | {it.get('title')} | {it.get('summary')}")
    lines.append("- INTERPRETATION (template):")
    lines.append("  - Transmission: rates → credit → FX → sentiment")
    lines.append("  - Likely winners/losers: (fill once facts confirmed)")
    return lines

def render_earnings_section(notes: Dict[str, Any]) -> List[str]:
    lines = []
    lines.append("## Sectors & Companies (Earnings / Broker Notes)")
    lines.append("- FACTS:")
    earnings = notes.get("earnings_facts", [])
    brokers = notes.get("broker_notes", [])
    if not earnings and not brokers:
        lines.append("  - Unknown (no earnings/broker facts provided)")
        return lines
    for e in earnings:
        lines.append(f"  - {e.get('ticker')} | {e.get('period')} | {e.get('summary')}")
    for b in brokers:
        lines.append(f"  - {b.get('firm')} | {b.get('ticker')} | {b.get('summary')}")
    lines.append("- INTERPRETATION (template):")
    lines.append("  - Earnings momentum / revision risk: (fill)")
    lines.append("  - Catalysts / risks: (fill)")
    return lines
