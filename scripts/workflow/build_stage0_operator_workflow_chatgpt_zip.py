"""
Build stage0_operator_workflow_chatgpt_YYYYMMDD.zip — full Stage 0 workflow for ChatGPT optimization.

Usage:
  python -m scripts.workflow.build_stage0_operator_workflow_chatgpt_zip
"""
from __future__ import annotations

import subprocess
import zipfile
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STAMP = datetime.now().strftime("%Y%m%d")
OUT_DIR = REPO / "outputs" / "review_packages"
OUT_ZIP = OUT_DIR / f"stage0_operator_workflow_chatgpt_{STAMP}.zip"

# (repo_relative, zip_path)
FILES: list[tuple[str, str]] = [
    (
        "docs/workflow/CHATGPT_STAGE0_OPERATOR_WORKFLOW_OPTIMIZATION_PROMPT.md",
        "REVIEW_PROMPT.md",
    ),
    ("docs/OPERATING_BACKBONE_PARETO.md", "docs/OPERATING_BACKBONE_PARETO.md"),
    ("docs/ROADMAP_AND_STAGE_TRACKER.md", "docs/ROADMAP_AND_STAGE_TRACKER.md"),
    ("docs/DISTRIBUTION_RISK_OPERATOR_INTEGRATION.md", "docs/DISTRIBUTION_RISK_OPERATOR_INTEGRATION.md"),
    ("docs/DIST_SESSION_MONITOR.md", "docs/DIST_SESSION_MONITOR.md"),
    ("docs/CHATGPT_COMMAND_ALIASES.md", "docs/CHATGPT_COMMAND_ALIASES.md"),
    ("data/roadmap/stage_tracker.yaml", "data/roadmap/stage_tracker.yaml"),
    ("docs/trading/ORDER_INTENT_DRY_RUN.md", "docs/trading/ORDER_INTENT_DRY_RUN.md"),
    ("docs/trading/CLOUD_DAILY_REPORT_GUIDE.md", "docs/trading/CLOUD_DAILY_REPORT_GUIDE.md"),
    ("docs/trading/DAILY_SCAN_OPERATOR_GUIDE.md", "docs/trading/DAILY_SCAN_OPERATOR_GUIDE.md"),
    ("docs/trading/REAL_CAPITAL_READINESS.md", "docs/trading/REAL_CAPITAL_READINESS.md"),
    ("docs/trading/INSTITUTIONAL_ACCUMULATION_SCAN.md", "docs/trading/INSTITUTIONAL_ACCUMULATION_SCAN.md"),
    (
        "docs/trading/INSTITUTIONAL_ACCUMULATION_WEEKLY_REPORT_SPEC.md",
        "docs/trading/INSTITUTIONAL_ACCUMULATION_WEEKLY_REPORT_SPEC.md",
    ),
    (
        "docs/trading/INSTITUTIONAL_ACCUMULATION_REVIEW_WORKFLOW.md",
        "docs/trading/INSTITUTIONAL_ACCUMULATION_REVIEW_WORKFLOW.md",
    ),
    ("docs/research/VIN_EMA_CLOUD_BASELINE.md", "docs/research/VIN_EMA_CLOUD_BASELINE.md"),
    ("docs/research/RESEARCH_INTAKE_WORKFLOW.md", "docs/research/RESEARCH_INTAKE_WORKFLOW.md"),
    ("data/research/intake/README.md", "data/research/intake/README.md"),
    ("data/research/intake/index/research_index.csv", "data/research/intake/index/research_index.csv"),
    ("templates/research/research_card_template.md", "templates/research/research_card_template.md"),
    ("templates/research/weekly_research_digest_template.md", "templates/research/weekly_research_digest_template.md"),
    ("templates/research/sector_thesis_dashboard_template.md", "templates/research/sector_thesis_dashboard_template.md"),
    ("scripts/trading/eod_market_context_refresh.ps1", "scripts/trading/eod_market_context_refresh.ps1"),
    ("scripts/trading/weekly_pareto_operator.ps1", "scripts/trading/weekly_pareto_operator.ps1"),
    ("scripts/trading/daily_eod_operator.ps1", "scripts/trading/daily_eod_operator.ps1"),
    ("templates/manual_decision_log_template.md", "templates/manual_decision_log_template.md"),
    ("templates/monthly_progress_review_template.md", "templates/monthly_progress_review_template.md"),
    ("templates/outside_a3_holding_review_template.md", "templates/outside_a3_holding_review_template.md"),
    ("src/trading/order_intent_dry_run.py", "src/trading/order_intent_dry_run.py"),
    ("src/review/record_weekly_run.py", "src/review/record_weekly_run.py"),
    ("tests/test_order_intent_dry_run.py", "tests/test_order_intent_dry_run.py"),
    ("tests/test_record_weekly_run.py", "tests/test_record_weekly_run.py"),
    ("src/trading/reports/distribution_risk_card.py", "src/trading/reports/distribution_risk_card.py"),
    (
        "data/research/market_risk/distribution_risk_latest.json",
        "samples/distribution_risk_latest.json",
    ),
    (
        "data/research/market_risk/distribution_risk_latest.html",
        "samples/distribution_risk_latest.html",
    ),
    ("data/decision/daily_scan.md", "samples/daily_scan.md"),
    (
        "data/research/reports/cloud_daily_report_latest.html",
        "samples/cloud_daily_report_latest.html",
    ),
    (
        "data/research/reports/cloud_daily_report_latest.json",
        "samples/cloud_daily_report_latest.json",
    ),
    (
        "data/research/portfolio_optimization/missing_work/phase36_daily_scan_latest.csv",
        "samples/phase36_daily_scan_latest.csv",
    ),
    ("data/decision/institutional_accumulation_compact.json", "samples/institutional_accumulation_compact.json"),
    ("config/watchlist.txt", "config/watchlist.txt"),
]

# Optional: latest institutional brief + operator summary (if present)
OPTIONAL_GLOBS: list[tuple[str, str]] = [
    ("outputs/scans/institutional_accumulation_weekly_brief_*.html", "samples/"),
    ("outputs/scans/institutional_accumulation_weekly_brief_*.md", "samples/"),
    ("outputs/scans/institutional_accumulation_operator_summary_latest.html", "samples/"),
    ("data/trading/order_intent/order_intent_*.csv", "samples/order_intent/"),
]


def _git_log(n: int = 15) -> str:
    try:
        r = subprocess.run(
            ["git", "log", f"-{n}", "--oneline"],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return r.stdout.strip() if r.returncode == 0 else "(git log unavailable)"
    except (OSError, subprocess.TimeoutExpired):
        return "(git log unavailable)"


def _readme() -> str:
    return f"""VN Agent System — Stage 0 Operator Workflow (ChatGPT / Codex review)
Built: {datetime.now().isoformat(timespec="seconds")}
Zip: {OUT_ZIP.name}

HOW TO USE
==========
1. New ChatGPT chat (High or Codex).
2. Upload this zip.
3. Paste FULL text of REVIEW_PROMPT.md.

GOAL
====
Streamline daily EOD + weekly Pareto + parallel research workstreams
without strategy creep or SSOT duplication.

KEY SSOT
========
- final_action: phase36_daily_scan_latest.csv
- Distribution context: distribution_risk_latest.json (does NOT change final_action)
- Weekly HTML: reports/latest/index.html (not in zip — generate locally)
- Accumulation research: institutional_accumulation_weekly_brief_*.html (sample if present)

REGENERATE ZIP
==============
  .venv\\Scripts\\python.exe -m scripts.workflow.build_stage0_operator_workflow_chatgpt_zip

REFRESH SAMPLES FIRST (EOD)
===========================
  .\\scripts\\trading\\eod_market_context_refresh.ps1 -Date YYYY-MM-DD -OpenCloudReport

WEEKLY EVIDENCE (after human review)
====================================
  .venv\\Scripts\\python.exe -m src.review.cli record-weekly-run --date YYYY-MM-DD --weekly-reviewed --order-intent-reviewed

NOT INCLUDED
============
- portfolio_state.json (often gitignored)
- reports/latest/index.html (generate via weekly script)
- Full data/stocks OHLCV tree
- Broker credentials

RECENT GIT (oneline)
====================
{_git_log()}
"""


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    missing: list[str] = []
    added = 0

    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.txt", _readme())
        zf.writestr("README_GIT_LOG.txt", _git_log(20))
        added += 2

        for repo_rel, zip_path in FILES:
            src = REPO / repo_rel
            if not src.is_file():
                missing.append(repo_rel)
                continue
            zf.write(src, zip_path)
            added += 1

        for pattern, prefix in OPTIONAL_GLOBS:
            if "order_intent" in pattern:
                oi_dir = REPO / "data/trading/order_intent"
                if oi_dir.is_dir():
                    for src in sorted(oi_dir.glob("order_intent_*.csv"))[-2:]:
                        zf.write(src, f"samples/order_intent/{src.name}")
                        added += 1
                continue
            matches = sorted(REPO.glob(pattern))
            if matches:
                src = matches[-1]
                if src.is_file():
                    zf.write(src, prefix + src.name)
                    added += 1

        # EOD acceptance checklist
        zf.writestr(
            "templates/EOD_DISTRIBUTION_RISK_ACCEPTANCE.md",
            """# EOD Distribution Risk Acceptance

Date: YYYY-MM-DD

- [ ] EOD wrapper completed
- [ ] distribution_risk_latest.json fresh
- [ ] report_status = OK, or NEEDS_REVIEW explained
- [ ] cloud_daily_report_latest.html generated
- [ ] daily_scan.md generated
- [ ] phase36_daily_scan_latest.csv generated
- [ ] Section G in cloud report
- [ ] Distribution Risk did not change final_action
- [ ] Legacy dist_session not used as SSOT
- [ ] Operator time acceptable (~30s cached)

Decision: [ ] Accept into routine  [ ] Needs fix
""",
        )
        added += 1

    print(f"Wrote {OUT_ZIP} ({added} entries, {OUT_ZIP.stat().st_size:,} bytes)")
    if missing:
        print("WARN missing (skipped):")
        for m in missing:
            print(f"  - {m}")


if __name__ == "__main__":
    main()
