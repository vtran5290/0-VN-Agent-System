"""Report Suite — canonical top-level build entry point.

Runs every VN Agent HTML report this repo owns, in a written-down, fail-fast order,
instead of relying on an operator remembering the right sequence by hand. Built
2026-08-10 in response to two observed gaps (see
00. Command Center/05_AI_Handoffs/2026-08-10-1251_ReviewPack_ReportSuiteOrchestrator.md
and its ChatGPT REDIRECT decision, Chatgpt/responses/2026-08-10_ReportSuiteOrchestrator_Decision.md):

  1. Only `portfolio-monitor` had a Makefile target; the other report generators were
     run from memory, in whatever order the operator remembered.
  2. `tollbooth_tracker_latest.html`'s shell-rebuild step (rebuild_laban_html_shell.py)
     silently destroyed injected content when run out of order — this actually happened
     on 2026-08-09 (tab T6 vanished from the live report; a human had to notice and
     hand-patch it). See scripts/reporting/rebuild_laban_html_shell.py and
     scripts/reporting/build_vn_structural_signals.py (--publish-shell) for the staged
     SHELL_ONLY -> INJECTED -> atomic-publish fix.

Hierarchy (per REDIRECT decision, Open Question 1): this script is the top-level
suite command. It invokes `run_weekly_full_fetch.py` as its weekly-lane subroutine
rather than duplicating that script's internal sequence. The reverse dependency
(weekly driver calling the suite) is deliberately NOT created — a subset driver
should not call its superset.

What this script does NOT do (deliberately, per approved scope — see review pack
§8 Out of Scope): no cross-report value-consistency check (S1), no Fact-card
recompute guard (S2), no staleness/honest-degradation gate (S3), no change to any
business content (axis state, scenarios, portfolio gates, signal logic). Those
remain explicitly deferred.

Routine daily use does NOT rebuild the tollbooth shell/template — only
`build_vn_structural_signals.py --inject` runs (safe, in-place data refresh, never
touches the template). The shell-rebuild step is opt-in via --rebuild-shell,
because rebuilding the template is a rare, manual, template-maintenance operation
(you only need it after editing rebuild_laban_html_shell.py itself) — running it on
every suite build would be pointless work with no data-freshness benefit and, per
ChatGPT risk flag #5, an unnecessary re-run of a generator whose non-idempotency
root cause (a 6x/24x block-duplication bug from 2026-08-06) is not yet understood.

Usage:
    python scripts/build_report_suite.py                  # full suite, weekly lane included
    python scripts/build_report_suite.py --skip-weekly     # skip the (slow, network-bound) weekly lane
    python scripts/build_report_suite.py --rebuild-shell   # ALSO rebuild+publish the tollbooth template
    python scripts/build_report_suite.py --asof 2026-08-10 # pass an as-of date to the weekly lane
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

try:
    from dotenv import load_dotenv

    load_dotenv(REPO / ".env", override=False)
except Exception:
    pass


def _run(cmd: list[str], timeout: int) -> int:
    print(f"\n>>> {' '.join(cmd)}\n", flush=True)
    r = subprocess.run(cmd, cwd=REPO, timeout=timeout)
    return r.returncode


class SuiteStep:
    """One line in the final structured summary. status is one of:
    PASS | FAIL | SKIPPED | WARN | EXTERNAL_NOT_BUILT | MISSING
    """

    def __init__(self, name: str, status: str, note: str = ""):
        self.name = name
        self.status = status
        self.note = note

    def line(self) -> str:
        tag = f"[{self.status}]".ljust(20)
        return f"{tag} {self.name}" + (f" — {self.note}" if self.note else "")


def _check_street_coverage(summary: list[SuiteStep]) -> None:
    """street_coverage_fragment.html is built by street_corpus.py, which lives in a
    DIFFERENT domain folder (03. Capital Investment/02_Stock_Research/_tools/) and a
    different git repository. Per REDIRECT Open Question 3: this suite does not invoke
    that generator across the repo boundary — it only checks presence and reports
    observed freshness. No staleness threshold is invented here (that would drift into
    the explicitly-deferred S3 scope) — age is reported as information only.
    """
    path = REPO / "reports" / "street_coverage_fragment.html"
    if not path.is_file():
        summary.append(SuiteStep(
            "street_coverage_fragment.html", "MISSING",
            "external artifact (built by a different repo's street_corpus.py) — not present. "
            "This does NOT fail the suite's exit code (nothing here can rebuild it), but "
            "the suite is not a complete 6-artifact set until it exists.",
        ))
        return
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    age_days = (datetime.now(tz=timezone.utc) - mtime).days
    summary.append(SuiteStep(
        "street_coverage_fragment.html", "EXTERNAL_NOT_BUILT",
        f"present, last modified {mtime.date().isoformat()} ({age_days}d ago) — "
        "no freshness threshold defined here; informational only.",
    ))


def main() -> int:
    ap = argparse.ArgumentParser(description="VN Agent Report Suite — canonical build entry point")
    ap.add_argument("--asof", default=None, help="As-of date YYYY-MM-DD (default: today); passed to weekly lane")
    ap.add_argument("--skip-weekly", action="store_true", help="Skip run_weekly_full_fetch.py (weekly lane)")
    ap.add_argument(
        "--rebuild-shell", action="store_true",
        help="ALSO rebuild the tollbooth template (rare — only needed after editing "
             "rebuild_laban_html_shell.py itself). Off by default.",
    )
    args = ap.parse_args()

    asof = args.asof or date.today().isoformat()
    py = sys.executable
    summary: list[SuiteStep] = []

    print("=== VN Agent Report Suite build ===", flush=True)
    print(f"asof={asof}  skip_weekly={args.skip_weekly}  rebuild_shell={args.rebuild_shell}", flush=True)

    # ---- 1. Weekly lane (delegated subroutine — not duplicated here) ----
    if args.skip_weekly:
        summary.append(SuiteStep("weekly lane (run_weekly_full_fetch.py)", "SKIPPED", "--skip-weekly"))
    else:
        rc = _run([py, str(REPO / "scripts" / "run_weekly_full_fetch.py"), "--asof", asof], timeout=1800)
        if rc != 0:
            summary.append(SuiteStep("weekly lane (run_weekly_full_fetch.py)", "FAIL", f"exit={rc}"))
            _print_summary(summary)
            return rc  # fail-fast: required step failed, do not build downstream artifacts
        summary.append(SuiteStep("weekly lane (run_weekly_full_fetch.py)", "PASS"))

    # ---- 2. PM Regime Dashboard ----
    rc = _run([py, str(REPO / "scripts" / "reporting" / "generate_pm_regime_dashboard.py")], timeout=180)
    if rc != 0:
        summary.append(SuiteStep("pm_regime_dashboard_latest.html", "FAIL", f"exit={rc}"))
        _print_summary(summary)
        return rc
    summary.append(SuiteStep("pm_regime_dashboard_latest.html", "PASS"))

    # ---- 3. Portfolio Monitor ----
    rc = _run([py, str(REPO / "scripts" / "reporting" / "generate_portfolio_monitor.py")], timeout=180)
    if rc != 0:
        summary.append(SuiteStep("portfolio_monitor_latest.html", "FAIL", f"exit={rc}"))
        _print_summary(summary)
        return rc
    summary.append(SuiteStep("portfolio_monitor_latest.html", "PASS"))

    # ---- 4. Tollbooth tracker — routine path: in-place data refresh only ----
    # This is the SAFE, non-destructive path (see build_vn_structural_signals.py
    # module docstring on `inject()`). It never touches the page template/shell.
    rc = _run(
        [py, str(REPO / "scripts" / "reporting" / "build_vn_structural_signals.py"), "--inject"],
        timeout=180,
    )
    if rc != 0:
        summary.append(SuiteStep("tollbooth_tracker_latest.html (data refresh)", "FAIL", f"exit={rc}"))
        _print_summary(summary)
        return rc
    summary.append(SuiteStep("tollbooth_tracker_latest.html (data refresh)", "PASS"))

    # ---- 4b. Tollbooth tracker — OPT-IN template rebuild (rare) ----
    if args.rebuild_shell:
        rc = _run([py, str(REPO / "scripts" / "reporting" / "rebuild_laban_html_shell.py")], timeout=120)
        if rc != 0:
            summary.append(SuiteStep("tollbooth shell rebuild", "FAIL", f"exit={rc}"))
            _print_summary(summary)
            return rc
        rc = _run(
            [py, str(REPO / "scripts" / "reporting" / "build_vn_structural_signals.py"), "--publish-shell"],
            timeout=180,
        )
        if rc != 0:
            summary.append(SuiteStep("tollbooth shell publish", "FAIL", f"exit={rc}"))
            _print_summary(summary)
            return rc
        summary.append(SuiteStep("tollbooth shell rebuild + publish", "PASS"))
    else:
        summary.append(SuiteStep("tollbooth shell rebuild", "SKIPPED", "routine builds don't touch the template — pass --rebuild-shell after editing it"))

    # ---- 5. street_coverage_fragment.html — external, check-only ----
    _check_street_coverage(summary)

    _print_summary(summary)

    # Exit code reflects only the required BUILD steps this orchestrator actually runs
    # (per REDIRECT direction #4). The external street-coverage artifact is reported
    # prominently (MISSING is not silent) but does not flip this process's exit code —
    # nothing in this repo can rebuild it, and failing five successfully-built, unrelated
    # reports because a cross-repo artifact is absent would be the wrong incentive.
    return 0


def _print_summary(summary: list[SuiteStep]) -> None:
    print("\n=== Report Suite build summary ===", flush=True)
    for step in summary:
        print("  " + step.line(), flush=True)
    failed = [s for s in summary if s.status == "FAIL"]
    if failed:
        print(f"\nRESULT: FAILED ({len(failed)} required step(s) did not complete)", flush=True)
    else:
        print("\nRESULT: build steps complete.", flush=True)
        missing = [s for s in summary if s.status == "MISSING"]
        if missing:
            print(
                f"  NOTE: {len(missing)} external artifact(s) missing — suite is not a "
                "complete 6-artifact set. See lines above.",
                flush=True,
            )


if __name__ == "__main__":
    raise SystemExit(main())
