"""
Build distribution_risk_workflow_integration_chatgpt_YYYYMMDD.zip for ChatGPT workflow review.

Usage:
  python -m scripts.reporting.build_distribution_risk_workflow_integration_chatgpt_zip
"""
from __future__ import annotations

import zipfile
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STAMP = datetime.now().strftime("%Y%m%d")
OUT_DIR = REPO / "outputs" / "review_packages"
OUT_ZIP = OUT_DIR / f"distribution_risk_workflow_integration_chatgpt_{STAMP}.zip"

FILES: list[tuple[str, str]] = [
    (
        "docs/trading/CHATGPT_DISTRIBUTION_RISK_WORKFLOW_INTEGRATION_PROMPT.md",
        "REVIEW_PROMPT.md",
    ),
    (
        "docs/DISTRIBUTION_RISK_OPERATOR_INTEGRATION.md",
        "docs/DISTRIBUTION_RISK_OPERATOR_INTEGRATION.md",
    ),
    ("docs/OPERATING_BACKBONE_PARETO.md", "docs/OPERATING_BACKBONE_PARETO.md"),
    ("docs/DIST_SESSION_MONITOR.md", "docs/DIST_SESSION_MONITOR.md"),
    (
        "scripts/trading/eod_market_context_refresh.ps1",
        "scripts/trading/eod_market_context_refresh.ps1",
    ),
    ("scripts/monitor_vnindex_distribution_session.py", "scripts/monitor_vnindex_distribution_session.py"),
    ("docs/trading/DAILY_SCAN_OPERATOR_GUIDE.md", "docs/trading/DAILY_SCAN_OPERATOR_GUIDE.md"),
    ("docs/trading/CLOUD_DAILY_REPORT_GUIDE.md", "docs/trading/CLOUD_DAILY_REPORT_GUIDE.md"),
    ("docs/research/VIN_EMA_CLOUD_BASELINE.md", "docs/research/VIN_EMA_CLOUD_BASELINE.md"),
    ("src/trading/cli.py", "src/trading/cli.py"),
    ("src/trading/reports/distribution_risk_card.py", "src/trading/reports/distribution_risk_card.py"),
    ("src/trading/reports/cloud_daily_report.py", "src/trading/reports/cloud_daily_report.py"),
    ("src/market/distribution_risk_lens/pipeline.py", "src/market/distribution_risk_lens/pipeline.py"),
    ("src/market/distribution_risk_lens/index_views.py", "src/market/distribution_risk_lens/index_views.py"),
    ("scripts/reporting/daily_scan_report.py", "scripts/reporting/daily_scan_report.py"),
    ("monitor_distribution_risk.cmd", "monitor_distribution_risk.cmd"),
    (
        "data/research/market_risk/distribution_risk_latest.json",
        "outputs/distribution_risk_latest.json",
    ),
    (
        "data/research/market_risk/distribution_risk_latest.html",
        "outputs/distribution_risk_latest.html",
    ),
    (
        "data/research/market_risk/distribution_risk_latest.md",
        "outputs/distribution_risk_latest.md",
    ),
    ("data/decision/daily_scan.md", "outputs/daily_scan.md"),
    (
        "data/research/reports/cloud_daily_report_latest.html",
        "outputs/cloud_daily_report_latest.html",
    ),
    (
        "data/research/portfolio_optimization/missing_work/phase36_daily_scan_latest.csv",
        "outputs/phase36_daily_scan_latest.csv",
    ),
]

LENS_GLOB = "src/market/distribution_risk_lens/*.py"


def _readme() -> str:
    return f"""Distribution Risk — Workflow Integration (ChatGPT / Codex)
Built: {datetime.now().isoformat(timespec='seconds')}
Zip: {OUT_ZIP.name}

HOW TO USE
==========
1. New ChatGPT chat (High or Codex).
2. Upload this zip.
3. Paste FULL text of REVIEW_PROMPT.md (workflow integration prompt).

GOAL
====
Fit distribution-risk + HTML session monitor into existing Pareto Stage-0 workflow
without SSOT duplication or strategy creep.

REGENERATE ZIP
==============
  .venv\\Scripts\\python.exe -m scripts.reporting.build_distribution_risk_workflow_integration_chatgpt_zip

REFRESH DATA FIRST (EOD)
========================
  .venv\\Scripts\\python.exe scripts\\append_fireant_ohlcv_to_data_stocks.py --data-stocks --minervini-raw --end YYYY-MM-DD
  .venv\\Scripts\\python.exe scripts\\research\\vnindex_low_dist_ex_vin.py --end YYYY-MM-DD
  .venv\\Scripts\\python.exe -m src.trading.cli distribution-risk --start 2012-01-01 --as-of latest

RELATED (methodology QA — separate review)
=========================================
  docs/trading/CHATGPT_DISTRIBUTION_RISK_DAILY_SCAN_REVIEW_PROMPT.md
  scripts/reporting/build_distribution_risk_daily_scan_chatgpt_zip.py

NOT INCLUDED
============
- portfolio_state.json (local gitignored)
- Full forward_returns 2012 CSV (size)
- Bulk data/stocks OHLCV tree
"""


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    missing: list[str] = []
    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.txt", _readme())
        for repo_rel, zip_path in FILES:
            src = REPO / repo_rel
            if not src.is_file():
                missing.append(repo_rel)
                continue
            zf.write(src, zip_path)
        lens_dir = REPO / "src" / "market" / "distribution_risk_lens"
        for py in sorted(lens_dir.glob("*.py")):
            if py.name in ("pipeline.py", "index_views.py"):
                continue
            zf.write(py, f"src/market/distribution_risk_lens/{py.name}")
    print(f"Wrote {OUT_ZIP}")
    if missing:
        print("WARN missing (skipped):")
        for m in missing:
            print(f"  - {m}")


if __name__ == "__main__":
    main()
