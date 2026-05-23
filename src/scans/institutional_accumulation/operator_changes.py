"""Signal-only diff formatting for operator summary (no methodology changes)."""
from __future__ import annotations

from typing import Any, Dict, List

MIN_SCORE_DELTA = 0.05
MAX_SCORE_MOVERS = 5
MAX_TIER_CHANGES = 12


def _round_delta(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return round(float(val), 1)
    except (TypeError, ValueError):
        return None


def _meaningful_movers(rows: List[dict[str, Any]], *, gains: bool) -> List[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for r in rows or []:
        ticker = str(r.get("ticker") or "")
        delta = _round_delta(r.get("score_delta"))
        if not ticker or delta is None or abs(delta) < MIN_SCORE_DELTA:
            continue
        if gains and delta <= 0:
            continue
        if not gains and delta >= 0:
            continue
        if ticker in seen:
            continue
        seen.add(ticker)
        out.append(
            {
                "ticker": ticker,
                "score_delta": delta,
                "tier_cur": r.get("tier_cur"),
                "tier_prev": r.get("tier_prev"),
            }
        )
        if len(out) >= MAX_SCORE_MOVERS:
            break
    return out


def _meaningful_tier_changes(changes: List[dict[str, Any]]) -> List[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in changes or []:
        prev, cur = r.get("tier_prev"), r.get("tier_cur")
        if not prev or not cur or prev == cur:
            continue
        delta = _round_delta(r.get("score_delta"))
        if delta is not None and abs(delta) < MIN_SCORE_DELTA and prev == cur:
            continue
        out.append(
            {
                "ticker": r.get("ticker"),
                "tier_prev": prev,
                "tier_cur": cur,
                "score_delta": delta,
            }
        )
        if len(out) >= MAX_TIER_CHANGES:
            break
    return out


def format_operator_changes(diff: Dict[str, Any]) -> Dict[str, Any]:
    """Operator-grade change block: suppress zero-delta noise."""
    if diff.get("note") == "no_previous_scan" or diff.get("previous_scan") is None:
        return {
            "note": "no_previous_scan",
            "summary_line": "No prior dated scan in outputs/scans/.",
            "new_tier12": [],
            "dropped_tier12": [],
            "tier_changes": [],
            "biggest_score_gains": [],
            "biggest_score_losses": [],
            "has_meaningful_changes": False,
        }

    new_t12 = list(diff.get("new_tier12") or [])
    dropped_t12 = list(diff.get("dropped_tier12") or [])
    tier_changes = _meaningful_tier_changes(diff.get("tier_changes") or [])
    gains = _meaningful_movers(diff.get("biggest_score_gains") or [], gains=True)
    losses = _meaningful_movers(diff.get("biggest_score_losses") or [], gains=False)

    # De-dupe: if same ticker in both gain and loss with tiny float noise, keep larger abs only
    gain_tickers = {g["ticker"] for g in gains}
    losses = [l for l in losses if l["ticker"] not in gain_tickers]

    has = bool(new_t12 or dropped_t12 or tier_changes or gains or losses)
    summary = (
        "No meaningful tier or score changes vs previous scan."
        if not has
        else None
    )

    return {
        "previous_scan": diff.get("previous_scan"),
        "previous_scan_date": _extract_date_from_path(str(diff.get("previous_scan") or "")),
        "summary_line": summary,
        "new_tier12": new_t12,
        "dropped_tier12": dropped_t12,
        "tier_changes": tier_changes,
        "biggest_score_gains": gains,
        "biggest_score_losses": losses,
        "has_meaningful_changes": has,
    }


def _extract_date_from_path(path: str) -> str | None:
    import re

    m = re.search(r"institutional_accumulation_(\d{4}-\d{2}-\d{2})", path)
    return m.group(1) if m else None
