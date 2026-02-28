from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
DECISION_LOG_DIR = REPO / "decision_log"
OUT_WEEKLY = REPO / "data" / "decision" / "council_secretary_weekly.md"
OUT_MONTHLY = REPO / "data" / "decision" / "council_audit_monthly.md"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _decision_log_paths() -> list[Path]:
    if not DECISION_LOG_DIR.exists():
        return []
    # Date-based filenames (YYYY-MM-DD.json) sort correctly lexicographically.
    return sorted([p for p in DECISION_LOG_DIR.glob("*.json") if p.is_file()], key=lambda p: p.stem)


def _latest_decision_log() -> tuple[Path | None, dict[str, Any]]:
    paths = _decision_log_paths()
    if not paths:
        return None, {}
    latest = paths[-1]
    return latest, _load_json(latest)


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None


def _fmt_date(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d") if value else "Unknown"


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if item is None:
                continue
            txt = str(item).strip()
            if txt:
                out.append(txt)
        return out
    return []


def _flow_lines_weekly() -> list[str]:
    return [
        "## Flow Reminder (Run Order)",
        "1. `make council-weekly`",
        "2. In `CHAIRMAN` chat, run `prompts/council/orchestrator.md`.",
        "3. Save JSON to `data/decision/council_output.json`.",
        "4. In `CHAIRMAN` chat, run `prompts/council/constraint_enforcer.md`.",
        "5. Re-run `make weekly` to persist council fields into `decision_log/<asof_date>.json`.",
        "6. Confirm `council.status=provided` and non-empty `chair_decision` in latest decision log.",
    ]


def build_weekly_secretary_note() -> str:
    path, log = _latest_decision_log()
    if not path or not log:
        lines = [
            "# Council Secretary — Weekly Checklist",
            "",
            "## FACTS",
            "- Latest decision log: Unknown (no `decision_log/*.json` found).",
            "",
            "## Weekly Checklist",
            "- [ ] Run `make council-weekly`.",
            "- [ ] Run council via `prompts/council/orchestrator.md`.",
            "- [ ] Save output to `data/decision/council_output.json`.",
            "- [ ] Run `prompts/council/constraint_enforcer.md`.",
            "- [ ] Re-run `make weekly` so decision log captures council fields.",
            "",
            "## BLOCKERS",
            "- Missing decision log history.",
            "",
            "## Next Dates",
            "- Next weekly council: Unknown",
            "- Next monthly audit: Unknown",
            "",
        ]
        lines.extend(_flow_lines_weekly())
        lines.extend(
            [
                "",
                "## Cadence Alerts",
                "- Weekly cadence: Unknown (no decision log yet).",
                "- Monthly audit cadence: Unknown (no decision log yet).",
                "",
                "## Process Reminder",
                "- Keep Council chat, Lab chat, and Secretary chat separate.",
            ]
        )
        return "\n".join(lines)

    council = log.get("council") if isinstance(log.get("council"), dict) else {}
    status = str(council.get("status") or "missing")
    has_council_run = status == "provided"
    has_constraint_check = council.get("mechanically_executable") is not None
    has_chair_decision = bool(str(council.get("chair_decision") or "").strip())

    checklist = [
        ("weekly packet generated", True),
        ("council run completed", has_council_run),
        ("constraint check completed", has_constraint_check),
        ("chair decision logged", has_chair_decision),
    ]

    blockers: list[str] = []
    if not has_council_run:
        blockers.append("Council output missing (`data/decision/council_output.json` not provided or not loaded).")
    if not has_constraint_check:
        blockers.append("Constraint check not recorded (`mechanically_executable` is null).")
    if not has_chair_decision:
        blockers.append("Chair decision missing (`chair_decision` is empty).")

    asof = str(log.get("asof_date") or path.stem)
    asof_dt = _parse_date(asof)
    next_weekly = asof_dt + timedelta(days=7) if asof_dt else None
    next_monthly = asof_dt + timedelta(days=30) if asof_dt else None
    today = datetime.now(timezone.utc)
    days_since_log = (today.date() - asof_dt.date()).days if asof_dt else None
    weekly_overdue = bool(days_since_log is not None and days_since_log > 8)
    monthly_overdue = bool(days_since_log is not None and days_since_log > 35)

    lines = [
        "# Council Secretary — Weekly Checklist",
        "",
        "## FACTS",
        f"- Latest decision log: `{path}`",
        f"- asof_date: {asof}",
        f"- council.status: {status}",
        f"- mechanically_executable: {council.get('mechanically_executable')}",
        f"- guardrail_violations: {len(_as_list(council.get('guardrail_violations')))}",
        "",
        "## Weekly Checklist",
    ]
    for task, done in checklist:
        lines.append(f"- [{'x' if done else ' '}] {task}")

    lines.extend(["", "## BLOCKERS"])
    if blockers:
        for item in blockers:
            lines.append(f"- {item}")
    else:
        lines.append("- None.")

    lines.extend(
        [
            "",
            "## Next Dates",
            f"- Next weekly council: {_fmt_date(next_weekly)}",
            f"- Next monthly audit: {_fmt_date(next_monthly)}",
            "",
            "## Cadence Alerts",
        ]
    )
    if days_since_log is None:
        lines.append("- Unable to compute staleness (invalid asof_date).")
    else:
        lines.append(f"- Days since latest decision log: {days_since_log}")
        if weekly_overdue:
            lines.append("- ⚠️ Weekly council appears overdue. Run `make council-weekly` now.")
        else:
            lines.append("- Weekly cadence: on track.")
        if monthly_overdue:
            lines.append("- ⚠️ Monthly audit appears overdue. Run `make council-audit-monthly`.")
        else:
            lines.append("- Monthly audit cadence: on track.")

    lines.extend(
        [
            "",
            *_flow_lines_weekly(),
            "",
            "## Process Reminder",
            "- If council output changes, re-run `make weekly` to refresh decision log.",
            "- If a recommendation violates guardrails, only execute the downgraded executable action list.",
        ]
    )
    return "\n".join(lines)


def build_monthly_audit_note(lookback_weeks: int = 5) -> str:
    paths = _decision_log_paths()
    if not paths:
        return "\n".join(
            [
                "# Council Secretary — Monthly Audit",
                "",
                "## FACTS",
                "- No `decision_log/*.json` found.",
                "",
                "## INTERPRETATION",
                "- Unknown (no logs to audit).",
                "",
                "## Actions",
                "- Start weekly council cycle first (`make council-weekly`).",
                "",
                "## Flow Reminder (Next Cycle)",
                "1. Weekly: `make council-weekly` -> orchestrator -> enforcer -> `make weekly`.",
                "2. Mid-week check: open `data/decision/council_secretary_weekly.md` and clear BLOCKERS.",
                "3. Monthly: `make council-audit-monthly` and review `data/decision/council_audit_monthly.md`.",
            ]
        )

    selected = paths[-lookback_weeks:]
    rows = [_load_json(p) for p in selected]

    council_missing = 0
    missing_chair = 0
    non_executable = 0
    violation_weeks = 0
    no_new_buys_weeks = 0
    violation_counter: Counter[str] = Counter()
    conflict_counter: Counter[str] = Counter()

    for row in rows:
        council = row.get("council") if isinstance(row.get("council"), dict) else {}
        if council.get("status") != "provided":
            council_missing += 1
        if not str(council.get("chair_decision") or "").strip():
            missing_chair += 1
        if council.get("mechanically_executable") is False:
            non_executable += 1

        violations = _as_list(council.get("guardrail_violations"))
        conflicts = _as_list(council.get("conflicts"))
        if violations:
            violation_weeks += 1
            for item in violations:
                violation_counter[item] += 1
        for item in conflicts:
            conflict_counter[item] += 1

        if row.get("new_buys_allowed") is False:
            no_new_buys_weeks += 1

    lines = [
        "# Council Secretary — Monthly Audit",
        "",
        "## FACTS",
        f"- Logs reviewed: {len(rows)} (`{selected[0].stem}` -> `{selected[-1].stem}`)",
        f"- Council missing weeks: {council_missing}",
        f"- Missing chair decision weeks: {missing_chair}",
        f"- Non-executable recommendation weeks: {non_executable}",
        f"- Weeks with guardrail violations: {violation_weeks}",
        f"- Weeks with `new_buys_allowed=false`: {no_new_buys_weeks}",
        "",
        "## INTERPRETATION",
    ]
    if council_missing == 0 and missing_chair == 0:
        lines.append("- Process discipline is stable in the sampled period.")
    else:
        lines.append("- Cadence discipline drift exists; secretary checklist must be enforced weekly.")

    if non_executable > 0:
        lines.append("- Council occasionally proposes non-executable actions; enforce constraint step before chair sign-off.")

    if violation_weeks > 0:
        lines.append("- Guardrail pressure appeared; focus on downgrade-to-executable workflow, not narrative override.")

    lines.extend(["", "## Top Recurring Guardrail Violations"])
    if violation_counter:
        for item, count in violation_counter.most_common(5):
            lines.append(f"- {item} (count={count})")
    else:
        lines.append("- None.")

    lines.extend(["", "## Top Recurring Council Conflicts"])
    if conflict_counter:
        for item, count in conflict_counter.most_common(5):
            lines.append(f"- {item} (count={count})")
    else:
        lines.append("- None.")

    lines.extend(
        [
            "",
            "## Process Improvements (No Strategy Change)",
            "- Make `make council-weekly` mandatory before weekly chairman decision.",
            "- Require non-empty `chair_decision` every week.",
            "- If guardrail violation appears, record nearest executable downgrade in council output.",
            "- Keep Lab research and live decision threads separate to prevent narrative contamination.",
            "",
            "## Flow Reminder (Next Cycle)",
            "1. Weekly: `make council-weekly` -> orchestrator -> enforcer -> `make weekly`.",
            "2. Mid-week check: open `data/decision/council_secretary_weekly.md` and clear BLOCKERS.",
            "3. Monthly: `make council-audit-monthly` and review `data/decision/council_audit_monthly.md`.",
        ]
    )
    return "\n".join(lines)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"Wrote: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Council Secretary helper (weekly checklist / monthly audit).")
    parser.add_argument("--mode", choices=("weekly", "monthly"), default="weekly")
    parser.add_argument("--out", default=None, help="Optional output markdown path.")
    parser.add_argument("--lookback-weeks", type=int, default=5, help="Monthly mode: number of logs to review.")
    args = parser.parse_args()

    if args.mode == "weekly":
        content = build_weekly_secretary_note()
        out = Path(args.out) if args.out else OUT_WEEKLY
    else:
        content = build_monthly_audit_note(lookback_weeks=max(1, args.lookback_weeks))
        out = Path(args.out) if args.out else OUT_MONTHLY

    _write_text(out, content)


if __name__ == "__main__":
    main()
