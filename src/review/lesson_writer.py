"""
Write lesson_learned_YYYY-MM.md and lesson_learned_latest.md.
Template sections + optional Insight Bursts gated by review_policy triggers.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import DECISION_DIR

logger = logging.getLogger(__name__)

REVIEW_POLICY_PATH = DECISION_DIR / "review_policy.json"
LESSON_LATEST_PATH = DECISION_DIR / "lesson_learned_latest.md"


def _load_policy() -> Dict[str, Any]:
    if not REVIEW_POLICY_PATH.exists():
        return {
            "min_sample_to_act": 10,
            "cooldown": {"max_rule_changes_per_month": 1},
            "triggers": {"avg_r_multiple_drop_bps": 50, "high_severity_spike_count": 3, "worst_r_threshold": -1.0},
            "high_severity_patterns": ["BUY in risk_flag!=Normal", "Held through MA20 day2 breach"],
            "rule_change_proposals": [],
        }
    return json.loads(REVIEW_POLICY_PATH.read_text(encoding="utf-8"))


def _trigger_insight_bursts(
    diagnostic: Dict[str, Any],
    policy: Dict[str, Any],
) -> tuple[bool, List[str]]:
    """Return (should_include_bursts, list of burst lines)."""
    bursts: List[str] = []
    summary = diagnostic.get("summary_stats") or {}
    patterns = diagnostic.get("patterns") or {}
    high_severity = set(policy.get("high_severity_patterns") or [])
    triggers = policy.get("triggers") or {}
    compliance = policy.get("compliance_thresholds") or {"red": 0.50, "yellow": 0.20, "green": 0.20}
    worst_r = triggers.get("worst_r_threshold", -1.0)
    spike_count = triggers.get("high_severity_spike_count", 3)

    n_closed = summary.get("n_closed") or 0
    if n_closed < (policy.get("min_sample_to_act") or 10):
        return False, []

    # Compliance-based labels (stop + reason_tag). These override the old "GREEN" default.
    proc = patterns.get("process") or []
    proc_map = {p.get("pattern"): (p.get("count") or 0) for p in proc if isinstance(p, dict)}
    miss_stop_rate = (proc_map.get("Missing stop recorded", 0) / n_closed) if n_closed else 0.0
    miss_reason_rate = (proc_map.get("No reason_tag", 0) / n_closed) if n_closed else 0.0

    def _color(rate: float) -> str:
        if rate >= float(compliance.get("red", 0.50)):
            return "RED"
        if rate >= float(compliance.get("yellow", 0.20)):
            return "YELLOW"
        return "GREEN"

    stop_color = _color(miss_stop_rate)
    reason_color = _color(miss_reason_rate)
    bursts.append(f"[{stop_color}] Missing stop recorded rate: {miss_stop_rate:.0%} ({proc_map.get('Missing stop recorded', 0)}/{n_closed})")
    bursts.append(f"[{reason_color}] No reason_tag rate: {miss_reason_rate:.0%} ({proc_map.get('No reason_tag', 0)}/{n_closed})")

    high_count = 0
    for cat in ("entry_quality", "exit_quality", "process"):
        for p in patterns.get(cat) or []:
            if p.get("pattern") in high_severity and (p.get("count") or 0) >= spike_count:
                high_count += 1
    if high_count > 0:
        bursts.append(f"[RED] High-severity pattern count: {high_count}. Review entry/exit discipline.")

    worst_3 = summary.get("worst_3") or []
    for w in worst_3:
        r = w.get("r_multiple")
        if r is not None and r <= worst_r:
            bursts.append(f"[YELLOW] Worst trade r_multiple={r:.2f}. Consider tighter stop or skip similar setup.")
            break

    avg_r = summary.get("avg_r_multiple")
    if avg_r is not None and avg_r < 0:
        bursts.append(f"[YELLOW] Avg R-multiple negative ({avg_r:.2f}). Sizing or exit review needed.")

    return True, bursts


def _top_patterns(diagnostic: Dict[str, Any], n: int = 3) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    patterns = diagnostic.get("patterns") or {}
    for cat in ("entry_quality", "exit_quality", "process"):
        for p in patterns.get(cat) or []:
            out.append(p)
    out.sort(key=lambda x: -(x.get("count") or 0))
    return out[:n]


def _rule_adjustments_from_masters(masters_path: Path) -> List[str]:
    if not masters_path.exists():
        return []
    data = json.loads(masters_path.read_text(encoding="utf-8"))
    seen = set()
    adj: List[str] = []
    for r in data.get("reviews") or []:
        for m in ("buffett", "oneil", "minervini", "morales"):
            v = (r.get(m) or {}).get("1_rule_adjust")
            if v and v != "—" and v not in seen:
                seen.add(v)
                adj.append(v)
    return adj[:3]


def write_lessons(
    month: Optional[str] = None,
    diagnostic_path: Optional[Path] = None,
    masters_path: Optional[Path] = None,
) -> tuple[Path, Path]:
    """Write lesson_learned_YYYY-MM.md and lesson_learned_latest.md. Idempotent."""
    policy = _load_policy()
    month_key = (month or "")[:7]
    DECISION_DIR.mkdir(parents=True, exist_ok=True)

    if not month_key:
        month_key = "unknown"

    diag_path = diagnostic_path or DECISION_DIR / f"trade_diagnostic_{month_key}.json"
    masters_path = masters_path or DECISION_DIR / f"trade_masters_review_{month_key}.json"

    diagnostic: Dict[str, Any] = {}
    if diag_path.exists():
        diagnostic = json.loads(diag_path.read_text(encoding="utf-8"))

    summary = diagnostic.get("summary_stats") or {}
    top_pat = _top_patterns(diagnostic, 3)
    # Process-first gate: if Missing stop recorded >30% → only process fixes, no rule changes.
    n_closed = summary.get("n_closed") or 0
    proc = (diagnostic.get("patterns") or {}).get("process") or []
    proc_map = {p.get("pattern"): (p.get("count") or 0) for p in proc if isinstance(p, dict)}
    miss_stop_rate = (proc_map.get("Missing stop recorded", 0) / n_closed) if n_closed else 0.0
    miss_reason_rate = (proc_map.get("No reason_tag", 0) / n_closed) if n_closed else 0.0
    if n_closed and miss_stop_rate > 0.30:
        rule_adj = [
            "Require stop_price_at_entry on every trade (no exceptions)",
            "Require reason_tag from controlled set (breakout_base, pocket_pivot, vcp, add_on, reentry, ...)",
        ]
    else:
        rule_adj = _rule_adjustments_from_masters(masters_path)
        if not rule_adj:
            rule_adj = ["Set no_new_buys when risk_flag!=Normal", "Hard exit on day2 breach"]

    lines: List[str] = []
    lines.append(f"# Lesson Learned — {month_key}")
    lines.append("")
    lines.append("## 1) Performance Summary")
    lines.append(f"- n_closed: {summary.get('n_closed', 0)}")
    lines.append(f"- win_rate: {summary.get('win_rate')}")
    lines.append(f"- avg R-multiple: {summary.get('avg_r_multiple')}")
    lines.append(f"- best_3: {summary.get('best_3', [])}")
    lines.append(f"- worst_3: {summary.get('worst_3', [])}")
    lines.append("")

    lines.append("## 2) Top 3 Recurring Patterns")
    for p in top_pat:
        lines.append(f"- **{p.get('pattern', '')}** (count={p.get('count')}, severity={p.get('severity')})")
    if not top_pat:
        lines.append("- None identified this period.")
    lines.append("")

    lines.append("## 3) 1–2 Rule Adjustments (actionable)")
    for a in rule_adj[:2]:
        lines.append(f"- {a}")
    lines.append("")

    lines.append("## 4) What NOT to change (anti-overfit)")
    lines.append("- Do not change entry/exit/sizing rules based on single month.")
    lines.append("- Do not auto-apply rule_change_proposals; review manually.")
    lines.append("")

    lines.append("## 5) Open Questions (max 3)")
    lines.append("- WoW regime vs. execution alignment?")
    lines.append("- R-multiple coverage on open positions?")
    lines.append("- Council execution vs. plan?")
    lines.append("")

    trigger, bursts = _trigger_insight_bursts(diagnostic, policy)
    if trigger and bursts:
        lines.append("## Insight Bursts")
        for b in bursts:
            lines.append(f"- {b}")
        lines.append("")

    content = "\n".join(lines)
    out_month = DECISION_DIR / f"lesson_learned_{month_key}.md"
    out_month.write_text(content, encoding="utf-8")
    LESSON_LATEST_PATH.write_text(content, encoding="utf-8")
    logger.info("Wrote %s and lesson_learned_latest.md", out_month.name)
    return out_month, LESSON_LATEST_PATH
