from __future__ import annotations

"""
Council Performance Review — monthly summary (CPR v1.0).

Reads:
- review/index.csv  (built by src.review.run)

Writes:
- review/reports/monthly_report.md

Focus: governance / risk calibration, not trade-level PnL.
"""

import argparse
import csv
import logging
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import REPO

logger = logging.getLogger(__name__)

REVIEW_ROOT = REPO / "review"
INDEX_PATH = REVIEW_ROOT / "index.csv"
REPORTS_DIR = REVIEW_ROOT / "reports"
REPORT_PATH = REPORTS_DIR / "monthly_report.md"

# Simple heuristic threshold for "meaningful drawdown" over 4 weeks.
DRAW_THRESHOLD_4W = -0.05


def _parse_float(value: str | None) -> Optional[float]:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _read_index() -> List[Dict[str, Any]]:
    if not INDEX_PATH.exists():
        return []
    with INDEX_PATH.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows: List[Dict[str, Any]] = []
        for row in reader:
            row = dict(row)
            # Parse numeric fields we care about.
            row["gross_cap"] = _parse_float(row.get("gross_cap"))
            row["next_4w_ret"] = _parse_float(row.get("next_4w_ret"))
            row["drawdown_4w"] = _parse_float(row.get("drawdown_4w"))
            row["n_positions"] = _parse_float(row.get("n_positions"))
            rows.append(row)
        return rows


def _select_window(
    rows: Sequence[Dict[str, Any]], lookback_weeks: int, end_asof: Optional[str] = None
) -> List[Dict[str, Any]]:
    if not rows:
        return []
    rows_sorted = sorted(rows, key=lambda r: r.get("asof_date") or "")
    if end_asof:
        rows_sorted = [r for r in rows_sorted if (r.get("asof_date") or "") <= end_asof]
    if not rows_sorted:
        return []
    return rows_sorted[-lookback_weeks:]


def _mean(vals: List[Optional[float]]) -> Optional[float]:
    xs = [v for v in vals if v is not None]
    if not xs:
        return None
    return mean(xs)


def _fmt_pct(x: Optional[float]) -> str:
    if x is None:
        return "Unknown"
    return f"{x*100:.1f}%"


def _fmt_num(x: Optional[float]) -> str:
    if x is None:
        return "Unknown"
    return f"{x:.3f}"


def _section_governance(rows: List[Dict[str, Any]]) -> Tuple[List[str], Dict[str, Any]]:
    """
    Regime / risk governance effectiveness.
    """
    stats: Dict[str, Any] = {}
    lines: List[str] = []
    if not rows:
        lines.append("- Unknown (no review/index.csv rows).")
        return lines, stats

    mismatch_true = [r for r in rows if (r.get("mismatch") or "").lower() == "true"]
    mismatch_false = [r for r in rows if (r.get("mismatch") or "").lower() == "false"]

    m_true_ret = _mean([r.get("next_4w_ret") for r in mismatch_true])
    m_false_ret = _mean([r.get("next_4w_ret") for r in mismatch_false])
    m_true_dd = _mean([r.get("drawdown_4w") for r in mismatch_true])
    m_false_dd = _mean([r.get("drawdown_4w") for r in mismatch_false])

    stats["mismatch_true_weeks"] = len(mismatch_true)
    stats["mismatch_false_weeks"] = len(mismatch_false)
    stats["mismatch_true_next4w_ret"] = m_true_ret
    stats["mismatch_false_next4w_ret"] = m_false_ret
    stats["mismatch_true_dd4w"] = m_true_dd
    stats["mismatch_false_dd4w"] = m_false_dd

    lines.append(
        f"- Mismatch=True weeks: {len(mismatch_true)} | "
        f"avg next_4w_ret={_fmt_num(m_true_ret)} | "
        f"avg drawdown_4w={_fmt_num(m_true_dd)}"
    )
    lines.append(
        f"- Mismatch=False weeks: {len(mismatch_false)} | "
        f"avg next_4w_ret={_fmt_num(m_false_ret)} | "
        f"avg drawdown_4w={_fmt_num(m_false_dd)}"
    )
    return lines, stats


def _section_risk_flag(rows: List[Dict[str, Any]]) -> Tuple[List[str], Dict[str, Any]]:
    stats: Dict[str, Any] = {}
    lines: List[str] = []
    high = [r for r in rows if (r.get("risk_flag") or "").lower() == "high"]
    if not high:
        lines.append("- No weeks with risk_flag=High.")
        return lines, stats

    dd_hits = [
        r
        for r in high
        if isinstance(r.get("drawdown_4w"), float)
        and r["drawdown_4w"] <= DRAW_THRESHOLD_4W
    ]
    stats["risk_high_weeks"] = len(high)
    stats["risk_high_dd_hits"] = len(dd_hits)
    stats["risk_high_precision_dd"] = (
        len(dd_hits) / len(high) if high else None
    )
    lines.append(
        f"- risk_flag=High weeks: {len(high)} | "
        f"drawdown_4w<={DRAW_THRESHOLD_4W:.0%} in {len(dd_hits)} weeks "
        f"({_fmt_pct(stats['risk_high_precision_dd'])} precision)."
    )
    return lines, stats


def _section_cap_new_buys(
    rows: List[Dict[str, Any]]
) -> Tuple[List[str], Dict[str, Any]]:
    stats: Dict[str, Any] = {}
    lines: List[str] = []
    if not rows:
        lines.append("- Unknown (no rows).")
        return lines, stats

    def _group(filter_fn) -> Tuple[int, Optional[float], Optional[float]]:
        subset = [r for r in rows if filter_fn(r)]
        return (
            len(subset),
            _mean([r.get("next_4w_ret") for r in subset]),
            _mean([r.get("drawdown_4w") for r in subset]),
        )

    nb_block_cnt, nb_block_ret, nb_block_dd = _group(
        lambda r: (r.get("new_buys_allowed") or "").lower() == "false"
    )
    nb_allow_cnt, nb_allow_ret, nb_allow_dd = _group(
        lambda r: (r.get("new_buys_allowed") or "").lower() == "true"
    )

    stats["nb_block_weeks"] = nb_block_cnt
    stats["nb_block_next4w_ret"] = nb_block_ret
    stats["nb_block_dd4w"] = nb_block_dd
    stats["nb_allow_weeks"] = nb_allow_cnt
    stats["nb_allow_next4w_ret"] = nb_allow_ret
    stats["nb_allow_dd4w"] = nb_allow_dd

    lines.append(
        f"- New buys BLOCKED weeks: {nb_block_cnt} | "
        f"avg next_4w_ret={_fmt_num(nb_block_ret)} | "
        f"avg drawdown_4w={_fmt_num(nb_block_dd)}"
    )
    lines.append(
        f"- New buys ALLOWED weeks: {nb_allow_cnt} | "
        f"avg next_4w_ret={_fmt_num(nb_allow_ret)} | "
        f"avg drawdown_4w={_fmt_num(nb_allow_dd)}"
    )
    return lines, stats


def _section_dist_calibration(
    rows: List[Dict[str, Any]]
) -> Tuple[List[str], Dict[str, Any]]:
    stats: Dict[str, Any] = {}
    lines: List[str] = []
    if not rows:
        lines.append("- Unknown (no rows).")
        return lines, stats

    by_dist: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        key = (r.get("dist_composite") or "Unknown").strip()
        by_dist.setdefault(key, []).append(r)

    for level, subset in sorted(by_dist.items(), key=lambda kv: kv[0]):
        stats.setdefault("dist_levels", {})[level] = {
            "count": len(subset),
            "avg_next4w_ret": _mean([r.get("next_4w_ret") for r in subset]),
            "avg_dd4w": _mean([r.get("drawdown_4w") for r in subset]),
        }
        lines.append(
            f"- Dist={level}: n={len(subset)} | "
            f"avg next_4w_ret={_fmt_num(stats['dist_levels'][level]['avg_next4w_ret'])} | "
            f"avg drawdown_4w={_fmt_num(stats['dist_levels'][level]['avg_dd4w'])}"
        )
    return lines, stats


def build_monthly_report(
    rows: List[Dict[str, Any]], lookback_weeks: int
) -> str:
    if not rows:
        return "\n".join(
            [
                "# Council Performance Review — Monthly",
                "",
                "## FACTS",
                "- No review/index.csv data available.",
                "",
                "## INTERPRETATION",
                "- Unknown (no data).",
                "",
                "## Actions",
                "- Run `make weekly` and `make review` for at least a few weeks.",
            ]
        )

    latest_asof = rows[-1].get("asof_date") or "Unknown"
    window = rows
    n = len(window)

    gov_lines, gov_stats = _section_governance(window)
    risk_lines, risk_stats = _section_risk_flag(window)
    cap_lines, cap_stats = _section_cap_new_buys(window)
    dist_lines, dist_stats = _section_dist_calibration(window)

    lines: List[str] = []
    lines.append("# Council Performance Review — Monthly")
    lines.append("")
    lines.append("## FACTS")
    lines.append(
        f"- Window: last {n} weeks (lookback={lookback_weeks}) up to asof_date={latest_asof}."
    )
    lines.append(f"- Mismatch weeks: {gov_stats.get('mismatch_true_weeks', 0)}.")
    lines.append(f"- risk_flag=High weeks: {risk_stats.get('risk_high_weeks', 0)}.")
    lines.append("")

    lines.append("## Governance Effectiveness (Regime / Mismatch)")
    lines.extend(gov_lines)
    lines.append("")

    lines.append("## Risk Flag Calibration (High → Drawdown?)")
    lines.extend(risk_lines)
    lines.append("")

    lines.append("## Cap / New Buys Policy")
    lines.extend(cap_lines)
    lines.append("")

    lines.append("## Dist Composite Calibration")
    lines.extend(dist_lines)
    lines.append("")

    # Simple interpretation layer (facts-first; Unknown when data missing).
    lines.append("## INTERPRETATION")
    if gov_stats.get("mismatch_true_weeks", 0) >= 3:
        mt = gov_stats.get("mismatch_true_next4w_ret")
        mf = gov_stats.get("mismatch_false_next4w_ret")
        if mt is not None and mf is not None:
            if mt < mf:
                lines.append(
                    "- Weeks with regime/council mismatch tended to underperform vs aligned weeks."
                )
            else:
                lines.append(
                    "- Mismatch weeks did not clearly underperform vs aligned weeks in this sample."
                )
        else:
            lines.append("- Sample size for mismatch impact is still thin (Unknown).")
    else:
        lines.append(
            "- Too few mismatch weeks to draw conclusions about mismatch impact."
        )

    if risk_stats.get("risk_high_weeks", 0) >= 3:
        prec = risk_stats.get("risk_high_precision_dd")
        if prec is not None:
            lines.append(
                f"- risk_flag=High predicted a {DRAW_THRESHOLD_4W:.0%}+ drawdown with precision {_fmt_pct(prec)}."
            )
        else:
            lines.append(
                "- Drawdown data missing; cannot calibrate risk_flag=High precision."
            )
    else:
        lines.append(
            "- Not enough risk_flag=High weeks to calibrate drawdown prediction."
        )

    lines.append("")
    lines.append("## Actions (Process, not Strategy)")
    # Up to 3 concrete process actions, based on simple heuristics.
    actions: List[str] = []
    if (
        gov_stats.get("mismatch_true_weeks", 0) >= 3
        and gov_stats.get("mismatch_true_next4w_ret") is not None
        and gov_stats.get("mismatch_false_next4w_ret") is not None
        and gov_stats["mismatch_true_next4w_ret"]
        < gov_stats["mismatch_false_next4w_ret"]
    ):
        actions.append(
            "- Add governance rule: when mismatch=True AND risk_flag=High, default to BLOCK new buys unless explicit written override."
        )
    if (
        risk_stats.get("risk_high_weeks", 0) >= 3
        and risk_stats.get("risk_high_precision_dd") is not None
        and risk_stats["risk_high_precision_dd"] < 0.4
    ):
        actions.append(
            "- risk_flag=High produced many false alarms; consider tightening dist/breadth thresholds before flipping to High."
        )

    if not actions:
        actions.append(
            "- Maintain current governance rules; sample size / signal quality not strong enough to change process this month."
        )

    lines.extend(actions[:3])

    lines.append("")
    lines.append("## If X happens → do Y (Council Calibration)")
    lines.append(
        "- If future mismatch=True weeks continue to underperform, codify a hard downgrade rule (BLOCK buys + cap gross) for mismatch+High combos."
    )
    lines.append(
        "- If risk_flag=High rarely coincides with drawdown, raise the bar for setting High (e.g., require 2-week confirmation in dist composite)."
    )

    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Council Performance Review — monthly summary (CPR v1.0)."
    )
    parser.add_argument(
        "--lookback-weeks",
        type=int,
        default=8,
        help="Number of weeks to include (default: 8).",
    )
    parser.add_argument(
        "--end-asof",
        default=None,
        help="Optional YYYY-MM-DD; default: latest asof_date in review/index.csv.",
    )
    args = parser.parse_args(argv)

    rows_all = _read_index()
    if not rows_all:
        logger.error("review/index.csv missing or empty; run `python -m src.review.run` first.")
        return 1

    end_asof = args.end_asof or max(r.get("asof_date") or "" for r in rows_all)
    window = _select_window(rows_all, lookback_weeks=args.lookback_weeks, end_asof=end_asof)
    if not window:
        logger.error("No rows selected for window; check asof_date values in review/index.csv.")
        return 1

    content = build_monthly_report(window, lookback_weeks=args.lookback_weeks)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(content, encoding="utf-8")
    logger.info("Monthly CPR report written: %s", REPORT_PATH)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())

