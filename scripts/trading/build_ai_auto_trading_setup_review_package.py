#!/usr/bin/env python3
"""Build ai_auto_trading_setup_review_package.zip for 3rd-party AI review."""
from __future__ import annotations

import shutil
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PKG = REPO / "review" / "ai_auto_trading_setup_review_package"
ZIP_PATH = REPO / "ai_auto_trading_setup_review_package.zip"
STAMP = datetime.now().strftime("%Y-%m-%d %H:%M:%S %z")
PY = REPO / ".venv" / "Scripts" / "python.exe"

# Required paths (repo-relative). Substitutes noted in MISSING_FILES.md builder.
COPY_PATHS = [
    "docs/trading/REAL_CAPITAL_READINESS.md",
    "docs/trading/DAILY_SCAN_OPERATOR_GUIDE.md",
    "docs/trading/PHASE36_FREEZE_NOTE.md",
    "docs/trading/INTRADAY_PREVIEW_V3_1_REVIEW_NOTE.md",
    "docs/trading/INTRADAY_DATA_SOURCE_DISCOVERY.md",
    "data/research/portfolio_optimization/missing_work/S3_SHADOW_PAPER_TRADE_RULES.md",
    "data/research/portfolio_optimization/missing_work/S3_UPGRADE_IMPLEMENTATION_NOTES.md",
    "data/research/portfolio_optimization/missing_work/PHASE36_A3_S3_COORDINATION_DECISION_MEMO.md",
    "data/research/portfolio_optimization/missing_work/PHASE36H_PLAYBOOK_FINDINGS.md",
    "data/research/portfolio_optimization/missing_work/UPDATED_PHASE36_DASHBOARD_SPEC.md",
    "data/research/portfolio_optimization/missing_work/PHASE36_DASHBOARD_PROPOSAL.md",
    "data/research/portfolio_optimization/missing_work/UPDATED_FINAL_DAILY_RUNBOOK.md",
    "data/research/portfolio_optimization/missing_work/FINAL_DAILY_RUNBOOK.md",
    "data/research/portfolio_optimization/missing_work/UPDATED_FINAL_DECISION_MEMO_CLEAN.md",
    "data/research/portfolio_optimization/missing_work/FINAL_DECISION_MEMO_CLEAN.md",
    "pp_backtest/portfolio_optimization_final_steps.py",
    "pp_backtest/daily_three_strategy_scan.py",
    "pp_backtest/live/run_live_workflow.py",
    "scripts/research/fireant_intraday_probe.py",
    "scripts/run_weekly_full_fetch.py",
    "src/trading/cli.py",
    "src/trading/live/workflow.py",
    "src/trading/live/order_intent.py",
    "src/trading/live/data_health.py",
    "src/trading/live/paper_ledger.py",
    "src/trading/live/scan_resolver.py",
    "src/trading/live/s3_shadow_workflow.py",
    "src/trading/live/s3_shadow_paper_ledger.py",
    "src/trading/risk/live_rules.py",
    "src/trading/risk/batch_context.py",
    "src/trading/reconciliation/baseline.py",
    "src/trading/monitoring/kill_switch.py",
    "src/trading/intraday/schema.py",
    "src/trading/intraday/data_adapter.py",
    "src/trading/intraday/panel_overlay.py",
    "src/trading/intraday/vnindex_overlay.py",
    "src/trading/intraday/intraday_scan.py",
    "src/trading/intraday/report.py",
    "src/trading/intraday/session.py",
    "src/trading/intraday/volume_projection.py",
    "src/trading/intraday/__init__.py",
    "config/live_trading.yaml",
    "configs/intraday_scan.yaml",
    "config/paper_accounts.yaml",
    "config/watchlist.txt",
    "data/trading/holdings.txt",
    "tests/test_trading_risk.py",
    "tests/test_trading_oms.py",
    "tests/test_trading_paper_broker.py",
    "tests/test_trading_reconciliation.py",
    "tests/test_trading_batch_risk.py",
    "tests/test_trading_order_intent.py",
    "tests/test_trading_paper_ledger_live.py",
    "tests/test_trading_trade_intent_lock.py",
    "tests/test_trading_stale_data.py",
    "tests/test_trading_baseline_recon.py",
    "tests/test_trading_kill_switch.py",
    "tests/test_trading_daily_report_filter.py",
    "tests/test_s3_phase35.py",
    "tests/test_phase36_daily_scan.py",
    "tests/test_intraday_scan.py",
    "tests/test_trading_scan_resolver.py",
    "tests/test_trading_p0_hardening.py",
    "data/research/portfolio_optimization/missing_work/phase36_daily_scan_sample.csv",
    "data/research/portfolio_optimization/missing_work/phase36_daily_scan_latest.csv",
    "data/research/portfolio_optimization/missing_work/phase36_daily_scan_schema.csv",
    "data/research/portfolio_optimization/missing_work/phase35_daily_scan_sample.csv",
    "data/research/portfolio_optimization/missing_work/phase34_daily_scan_sample.csv",
    "data/research/intraday/phase36_intraday_scan_latest.csv",
    "data/research/intraday/phase36_intraday_scan_latest.md",
    "data/research/intraday/phase36_intraday_scan_latest.html",
    "data/research/intraday/phase36_intraday_scan_latest_meta.json",
    "data/research/intraday/review/intraday_v3_1_test_output.txt",
    "data/trading/live/dashboard/daily_summary.md",
    "data/trading/live/dashboard/live_status.json",
    "data/trading/live/data_health_report.md",
    "data/trading/live/kill_switch_status.json",
    "data/research/portfolio_optimization/missing_work/Cloud_Strategy_A3_20_100_DP_First_FINAL.afl",
    "data/research/portfolio_optimization/missing_work/Cloud_Strategy_S3_21_55_PAPER_SHADOW_MAX60.afl",
    "data/research/portfolio_optimization/missing_work/A3_DP_First_User_Guide_FINAL.md",
    "data/research/portfolio_optimization/missing_work/S3_21_55_Paper_Shadow_User_Guide.md",
    "docs/trading/PAPER_TRADING_OPERATIONS_GUIDE.md",
    "docs/trading/LIVE_CONFIG_GUIDE.md",
    "docs/trading/DAILY_PAPER_OPERATOR_PROMPT.md",
    "scripts/trading/daily_paper_live_full_run.ps1",
    "docs/trading/INTRADAY_SCAN_REVIEW_PROMPT.md",
]

EXACT_MISSING_EXPECTED = [
    "docs/trading/INTRADAY_VNINDEX_OVERLAY.md",
    "data/research/portfolio_optimization/missing_work/Cloud_Strategy_A3_20_100_PHASE36_PRODUCTION_RANK_CONTEXT.afl",
    "A3_20_100_PHASE36_User_Guide.md",
    "S3_21_55_PHASE36_User_Guide.md",
]


def git_hash() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
        ).strip()
    except Exception:
        return "unknown"


def copy_file(rel: str, copied: list, missing: list) -> None:
    src = REPO / rel
    if not src.is_file():
        missing.append(rel)
        return
    dst = PKG / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    copied.append(rel)


def main() -> None:
    # Preserve root review docs if re-building; wipe only bundle subdirs
    if PKG.exists():
        for child in PKG.iterdir():
            if child.name in {
                "REVIEW_PROMPT_FOR_THIRD_AI.md",
                "DOWNLOAD_PROMPT_TEMPLATE_FOR_THIRD_AI.md",
                "SYSTEM_ARCHITECTURE_SUMMARY.md",
                "FILE_MANIFEST.md",
                "MISSING_FILES.md",
                "CURRENT_GIT_STATUS.txt",
                "TEST_OUTPUT_SUMMARY.txt",
            }:
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    PKG.mkdir(parents=True, exist_ok=True)
    (PKG / "review_outputs").mkdir(parents=True, exist_ok=True)

    ro = REPO / "review_outputs"
    if ro.is_dir():
        for f in ro.iterdir():
            if f.is_file():
                shutil.copy2(f, PKG / "review_outputs" / f.name)

    copied: list[str] = []
    missing: list[str] = []
    for rel in COPY_PATHS:
        copy_file(rel, copied, missing)

    for rel in EXACT_MISSING_EXPECTED:
        if not (REPO / rel).is_file():
            if rel not in missing:
                missing.append(rel)

    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in PKG.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(PKG).as_posix())

    print(f"Package: {PKG}")
    print(f"Zip: {ZIP_PATH} ({ZIP_PATH.stat().st_size / 1024:.1f} KB)")
    print(f"Copied: {len(copied)} | Missing: {len(missing)}")
    if missing:
        print("Missing:", missing[:15])


if __name__ == "__main__":
    main()
