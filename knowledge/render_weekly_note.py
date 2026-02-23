# knowledge/render_weekly_note.py — JSON → Markdown view (source of truth: JSON only)
"""
Generate weekly note MD from JSON knowledge. Run once per week.
Output: knowledge/weekly_notes/YYYYMMDD.md
Sections: Regime snapshot, Backtest edge highlights, Stale warnings, Personal improvement, Rule tweaks, Checklist.
"""
from __future__ import annotations
import argparse
import json
from datetime import date
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
INDEX_PATH = _REPO / "knowledge" / "backtests" / "index.json"
PROFILE_PATH = _REPO / "knowledge" / "personal_improvement" / "profile.json"
REGIME_BREAK_PATH = _REPO / "knowledge" / "regime_break.json"
WEEKLY_NOTES_DIR = _REPO / "knowledge" / "weekly_notes"
REGIME_STATE_PATH = _REPO / "data" / "state" / "regime_state.json"
MARKET_FLAGS_PATH = _REPO / "data" / "alerts" / "market_flags.json"


def _load_json(path: Path) -> dict | list:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def render(date_str: str, regime_state_path: Path | None, market_flags_path: Path | None) -> str:
    lines = [f"# Weekly Note — {date_str}", ""]
    regime_state_path = regime_state_path or REGIME_STATE_PATH
    market_flags_path = market_flags_path or MARKET_FLAGS_PATH

    # —— Regime snapshot ——
    lines.append("## Regime snapshot")
    regime_state = _load_json(regime_state_path) if isinstance(_load_json(regime_state_path), dict) else {}
    mkt_flags = _load_json(market_flags_path) if isinstance(_load_json(market_flags_path), dict) else {}
    regime = regime_state.get("regime", "N/A")
    vn30_dd = mkt_flags.get("distribution_days_rolling_20") if isinstance(mkt_flags, dict) else None
    lines.append(f"- Regime: {regime}")
    lines.append(f"- VN30 DD/20: {vn30_dd if vn30_dd is not None else 'N/A'}")
    rb = _load_json(REGIME_BREAK_PATH)
    if isinstance(rb, dict) and rb.get("active"):
        exp = rb.get("expires_at", "")
        lines.append(f"- Regime break: **active** (reason: {rb.get('reason', '')}, since: {rb.get('since', '')}, expires_at: {exp})")
    else:
        lines.append("- Regime break: inactive")
    lines.append("")

    # —— Backtest edge highlights ——
    lines.append("## Backtest edge highlights")
    index = _load_json(INDEX_PATH)
    if isinstance(index, dict):
        latest = index.get("latest", {})
        tickers_list = list(latest.keys())[:10]
        for sym in tickers_list:
            strategies = latest.get(sym, {})
            for strat, rel_path in (strategies or {}).items():
                rec_path = _REPO / rel_path.replace("/", "\\")
                if rec_path.exists():
                    try:
                        rec = json.loads(rec_path.read_text(encoding="utf-8"))
                        s = rec.get("stats", {})
                        lines.append(f"- **{sym}** ({strat}): WR {s.get('win_rate', 0):.0%}, PF {s.get('profit_factor', 0):.2f}, MDD {s.get('max_drawdown', 0):.1%}")
                    except Exception:
                        pass
        if not tickers_list:
            lines.append("- No backtest records in index.")
    else:
        lines.append("- No backtest index.")
    lines.append("")

    # —— Stale warnings summary ——
    lines.append("## Stale warnings summary")
    lines.append("- Stale / mtime warnings appear in Decision layer when data is newer than record. Re-run publish_knowledge if needed.")
    lines.append("")

    # —— Personal improvement reminders ——
    lines.append("## Personal improvement reminders")
    profile = _load_json(PROFILE_PATH)
    if isinstance(profile, dict):
        user = profile.get("user_patterns", {})
        leaks = user.get("leaks", [])[:3]
        strengths = user.get("strengths", [])[:3]
        for L in leaks:
            lines.append(f"- **Leak:** {L.get('id', '')} — {L.get('description', '')}")
        for S in strengths:
            lines.append(f"- **Strength:** {S.get('id', '')} — {S.get('description', '')}")
        if not leaks and not strengths:
            lines.append("- No leaks/strengths in profile (run analyze_trades to update).")
    else:
        lines.append("- No personal_improvement profile yet.")
    lines.append("")

    # —— Proposed rule tweaks ——
    lines.append("## Proposed rule tweaks")
    lines.append("- (Add any rule changes to test this week.)")
    lines.append("")

    # —— Checklist tuần tới (static template; no LLM; tick or comment by hand) ——
    lines.append("## Checklist tuần tới")
    lines.append("- [ ] Run backtest + pivot")
    lines.append("- [ ] Publish knowledge")
    lines.append("- [ ] Import trade log tuần trước")
    lines.append("- [ ] Review stale warnings")
    lines.append("- [ ] Review regime_break status")
    lines.append("- [ ] Review top 3 leaks")
    lines.append("")

    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Render weekly note MD from JSON knowledge.")
    ap.add_argument("--date", default=date.today().strftime("%Y%m%d"), help="Date YYYYMMDD")
    ap.add_argument("--regime-state", type=Path, help="Path to regime_state.json")
    ap.add_argument("--market-flags", type=Path, help="Path to market_flags.json")
    args = ap.parse_args()
    WEEKLY_NOTES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = WEEKLY_NOTES_DIR / f"{args.date}.md"
    md = render(args.date, args.regime_state, args.market_flags)
    out_path.write_text(md, encoding="utf-8")
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()
