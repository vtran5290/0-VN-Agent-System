#!/usr/bin/env python3
"""Build ChatGPT handoff zip for workflow cleanup + roadmap review."""
from __future__ import annotations

import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "outputs" / "review_packages"
OUT_ZIP = OUT_DIR / "vn_workflow_roadmap_chatgpt.zip"

INCLUDE: list[tuple[str, str]] = [
    ("docs/workflow/CHATGPT_WORKFLOW_ROADMAP_REVIEW_PROMPT.md", "CHATGPT_WORKFLOW_ROADMAP_REVIEW_PROMPT.md"),
    ("docs/workflow/CHATGPT_WORKSTREAM_PARETO_PROMPT.md", "CHATGPT_WORKSTREAM_PARETO_PROMPT.md"),
    ("docs/OPERATING_BACKBONE_PARETO.md", "docs/OPERATING_BACKBONE_PARETO.md"),
    ("docs/ROADMAP_AND_STAGE_TRACKER.md", "docs/ROADMAP_AND_STAGE_TRACKER.md"),
    ("data/roadmap/stage_tracker.yaml", "data/roadmap/stage_tracker.yaml"),
    ("docs/trading/ORDER_INTENT_DRY_RUN.md", "docs/trading/ORDER_INTENT_DRY_RUN.md"),
    ("docs/trading/AUTO_ACCOUNT_READINESS_LADDER.md", "docs/trading/AUTO_ACCOUNT_READINESS_LADDER.md"),
    ("docs/trading/REAL_CAPITAL_READINESS.md", "docs/trading/REAL_CAPITAL_READINESS.md"),
    ("docs/trading/PAPER_TRADING_OPERATIONS_GUIDE.md", "docs/trading/PAPER_TRADING_OPERATIONS_GUIDE.md"),
    ("docs/trading/DAILY_PAPER_OPERATOR_PROMPT.md", "docs/trading/DAILY_PAPER_OPERATOR_PROMPT.md"),
    ("docs/business/COPYTRADE_AND_CONTENT_ROADMAP.md", "docs/business/COPYTRADE_AND_CONTENT_ROADMAP.md"),
    ("docs/CHATGPT_COMMAND_ALIASES.md", "docs/CHATGPT_COMMAND_ALIASES.md"),
    ("docs/reporting/WEEKLY_REPORT_GENERATION_FLOW.md", "docs/reporting/WEEKLY_REPORT_GENERATION_FLOW.md"),
    ("review_outputs/workflow_cleanup_and_roadmap_summary.md", "review_outputs/workflow_cleanup_and_roadmap_summary.md"),
    ("scripts/trading/weekly_pareto_operator.ps1", "scripts/trading/weekly_pareto_operator.ps1"),
    ("templates/manual_decision_log_template.md", "templates/manual_decision_log_template.md"),
    ("templates/monthly_progress_review_template.md", "templates/monthly_progress_review_template.md"),
    ("templates/content/daily_market_pulse_template.md", "templates/content/daily_market_pulse_template.md"),
    ("templates/content/compliance_safe_post_template.md", "templates/content/compliance_safe_post_template.md"),
    ("config/paper_accounts.yaml", "config/paper_accounts.yaml"),
    ("src/trading/order_intent_dry_run.py", "src/trading/order_intent_dry_run.py"),
    ("tests/test_order_intent_dry_run.py", "tests/test_order_intent_dry_run.py"),
]

# Optional sample outputs (picked up via glob below too)
OPTIONAL: list[str] = []


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if OUT_ZIP.exists():
        OUT_ZIP.unlink()

    added = 0
    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for repo_rel, arc_name in INCLUDE:
            path = REPO / repo_rel
            if path.exists():
                zf.write(path, arc_name)
                added += 1
            else:
                print(f"SKIP missing: {repo_rel}")

        for repo_rel in OPTIONAL:
            path = REPO / repo_rel
            if path.exists() and repo_rel not in {x[0] for x in INCLUDE}:
                zf.write(path, repo_rel)
                added += 1

        # Any order_intent csv
        oi_dir = REPO / "data" / "trading" / "order_intent"
        if oi_dir.is_dir():
            for csv in sorted(oi_dir.glob("order_intent_*.csv"))[-3:]:
                arc = str(csv.relative_to(REPO)).replace("\\", "/")
                if arc not in {i.filename for i in zf.filelist}:
                    zf.write(csv, arc)
                    added += 1

    print(f"Wrote {OUT_ZIP} ({added} files, {OUT_ZIP.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
