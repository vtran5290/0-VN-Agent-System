from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple


REPO = Path(__file__).resolve().parents[2]
WEEKLY_DIR = REPO / "data" / "smart_money" / "weekly"
DEFAULT_OUT = REPO / "data" / "decision" / "smart_money_weekly_diff.md"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_risk_flags(payload: Dict[str, Any]) -> List[str]:
    signals = payload.get("smart_money_signals")
    if not isinstance(signals, dict):
        return []
    raw = signals.get("risk_flags")
    if not isinstance(raw, list):
        return []
    out: List[str] = []
    for item in raw:
        if isinstance(item, str):
            text = item.strip()
            if text:
                out.append(text)
        elif isinstance(item, dict):
            detail = item.get("detail") or item.get("type")
            text = str(detail).strip() if detail is not None else ""
            if text:
                out.append(text)
    return out


def _extract_scores(payload: Dict[str, Any]) -> Dict[str, float | None]:
    signals = payload.get("smart_money_signals")
    if not isinstance(signals, dict):
        return {"crowding_score": None, "risk_on_score": None, "policy_alignment_score": None}
    return {
        "crowding_score": _to_float(signals.get("crowding_score")),
        "risk_on_score": _to_float(signals.get("risk_on_score")),
        "policy_alignment_score": _to_float(signals.get("policy_alignment_score")),
    }


def _extract_bias(payload: Dict[str, Any]) -> str:
    card = payload.get("consensus_card")
    if not isinstance(card, dict):
        return "unknown"
    bias = card.get("bias")
    return str(bias).strip() if bias is not None else "unknown"


def _top_mega_consensus(payload: Dict[str, Any], n: int = 3) -> List[str]:
    signals = payload.get("smart_money_signals")
    if not isinstance(signals, dict):
        return []
    mega = signals.get("mega_consensus")
    if not isinstance(mega, list):
        return []
    rows: List[Tuple[str, float]] = []
    for row in mega:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").strip()
        if not ticker:
            continue
        n_top = _to_float(row.get("n_funds_top10"))
        rows.append((ticker, n_top if n_top is not None else -1.0))
    rows.sort(key=lambda x: (-x[1], x[0]))
    return [r[0] for r in rows[:n]]


def _find_dated_snapshots() -> List[Path]:
    if not WEEKLY_DIR.exists():
        return []
    out: List[Path] = []
    for p in sorted(WEEKLY_DIR.glob("smart_money_consensus_*.json")):
        suffix = p.stem.replace("smart_money_consensus_", "")
        if DATE_RE.match(suffix):
            out.append(p)
    return out


def _resolve_two_files(current: str | None, previous: str | None) -> Tuple[Path | None, Path | None]:
    snapshots = _find_dated_snapshots()
    if current and previous:
        cur = WEEKLY_DIR / f"smart_money_consensus_{current}.json"
        prev = WEEKLY_DIR / f"smart_money_consensus_{previous}.json"
        return (cur if cur.exists() else None, prev if prev.exists() else None)
    if len(snapshots) >= 2:
        return snapshots[-1], snapshots[-2]
    return None, None


def build_weekly_diff_markdown(current_path: Path, previous_path: Path) -> str:
    current = _read_json(current_path)
    previous = _read_json(previous_path)

    current_scores = _extract_scores(current)
    previous_scores = _extract_scores(previous)
    current_bias = _extract_bias(current)
    previous_bias = _extract_bias(previous)

    current_flags = set(_extract_risk_flags(current))
    previous_flags = set(_extract_risk_flags(previous))
    new_flags = sorted(current_flags - previous_flags)
    removed_flags = sorted(previous_flags - current_flags)

    current_top = _top_mega_consensus(current)
    previous_top = set(_top_mega_consensus(previous))
    new_top = [t for t in current_top if t not in previous_top]

    def _delta_line(label: str, key: str) -> str:
        cur = current_scores.get(key)
        prev = previous_scores.get(key)
        if cur is None or prev is None:
            return f"- {label}: current={cur}, previous={prev}, delta=Unknown"
        delta = round(cur - prev, 2)
        return f"- {label}: current={cur}, previous={prev}, delta={delta:+.2f}"

    lines: List[str] = [
        "# Smart Money Weekly Diff",
        "",
        "## FACTS",
        f"- Current snapshot: `{current_path}`",
        f"- Previous snapshot: `{previous_path}`",
        f"- Current asof_date: {current.get('asof_date')}",
        f"- Previous asof_date: {previous.get('asof_date')}",
        _delta_line("Crowding score", "crowding_score"),
        _delta_line("Risk-on score", "risk_on_score"),
        _delta_line("Policy alignment score", "policy_alignment_score"),
        f"- Consensus bias: previous={previous_bias} -> current={current_bias}",
        f"- New risk flags: {', '.join(new_flags) if new_flags else 'None'}",
        f"- Removed risk flags: {', '.join(removed_flags) if removed_flags else 'None'}",
        f"- Current top mega consensus: {', '.join(current_top) if current_top else 'Unknown'}",
        f"- New top mega names vs previous: {', '.join(new_top) if new_top else 'None'}",
        "",
        "## INTERPRETATION",
    ]

    if current_scores.get("crowding_score") is None or current_scores.get("risk_on_score") is None:
        lines.append("- Unknown (missing score fields in current snapshot).")
    else:
        lines.append("- Use this diff as Council pre-read; do not override guardrails from weekly packet.")
        if new_flags:
            lines.append("- New risk flags detected; confirm whether they are mirrored in market risk controls.")
        if current_bias != previous_bias:
            lines.append("- Bias shifted week-over-week; review if change is signal or data noise.")
        if not new_flags and current_bias == previous_bias:
            lines.append("- No major positioning regime change detected in this weekly snapshot.")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Smart Money weekly diff from last two snapshots.")
    parser.add_argument("--current", default=None, help="Current asof date (YYYY-MM-DD).")
    parser.add_argument("--previous", default=None, help="Previous asof date (YYYY-MM-DD).")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output markdown path.")
    args = parser.parse_args()

    current_path, previous_path = _resolve_two_files(args.current, args.previous)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not current_path or not previous_path:
        out_path.write_text(
            "# Smart Money Weekly Diff\n\n## FACTS\n- Not enough dated snapshots in `data/smart_money/weekly/`.\n",
            encoding="utf-8",
        )
        print(f"Wrote: {out_path}")
        return

    content = build_weekly_diff_markdown(current_path, previous_path)
    out_path.write_text(content, encoding="utf-8")
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()
