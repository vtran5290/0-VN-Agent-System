#!/usr/bin/env python3
"""Build cloud_strategy_daily_scan_review_package.zip."""
from __future__ import annotations

import shutil
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PKG = REPO / "review" / "cloud_strategy_daily_scan"
ZIP_PATH = REPO / "cloud_strategy_daily_scan_review_package.zip"

COPY_PATHS = [
    "pp_backtest/portfolio_optimization_final_steps.py",
    "pp_backtest/daily_three_strategy_scan.py",
    "scripts/research/fireant_intraday_probe.py",
    "scripts/run_weekly_full_fetch.py",
    "data/research/portfolio_optimization/missing_work/phase36_daily_scan_sample.csv",
    "data/research/portfolio_optimization/missing_work/phase36_daily_scan_latest.csv",
    "data/research/portfolio_optimization/missing_work/phase36_daily_scan_schema.csv",
    "data/research/portfolio_optimization/missing_work/phase35_daily_scan_sample.csv",
    "data/research/portfolio_optimization/missing_work/phase34_daily_scan_sample.csv",
    "data/research/portfolio_optimization/missing_work/phase36_daily_operator_report.md",
    "data/research/portfolio_optimization/missing_work/S3_SHADOW_PAPER_TRADE_RULES.md",
    "data/research/portfolio_optimization/missing_work/S3_UPGRADE_IMPLEMENTATION_NOTES.md",
    "data/research/portfolio_optimization/missing_work/UPDATED_S3_DECISION_MEMO.md",
    "data/research/portfolio_optimization/missing_work/updated_final_candidate_classification.csv",
    "data/research/portfolio_optimization/missing_work/PHASE36_A3_S3_COORDINATION_DECISION_MEMO.md",
    "data/research/portfolio_optimization/missing_work/PHASE36H_PLAYBOOK_FINDINGS.md",
    "data/research/portfolio_optimization/missing_work/PHASE36_DAILY_SCAN_UPDATE.md",
    "data/research/portfolio_optimization/missing_work/PHASE36_DASHBOARD_PROPOSAL.md",
    "data/research/portfolio_optimization/missing_work/UPDATED_PHASE36_DASHBOARD_SPEC.md",
    "data/research/portfolio_optimization/missing_work/UPDATED_FINAL_DAILY_RUNBOOK.md",
    "data/research/portfolio_optimization/missing_work/FINAL_DAILY_RUNBOOK.md",
    "data/research/portfolio_optimization/missing_work/phase36_playbook_summary.csv",
    "data/research/portfolio_optimization/missing_work/phase36_playbook_interaction_matrix.csv",
    "data/research/portfolio_optimization/missing_work/phase36_s3_a3_ranking_tests.csv",
    "data/research/portfolio_optimization/missing_work/phase36_a3_s3_t2_policy_tests.csv",
    "data/research/portfolio_optimization/missing_work/phase36_a3_s3_exit_overlay_tests.csv",
    "data/research/portfolio_optimization/missing_work/phase36_a3_s3_sizing_tests.csv",
    "data/research/portfolio_optimization/missing_work/phase36_sorting_validation.md",
    "data/research/portfolio_optimization/missing_work/phase36_order_intent_validation.md",
    "data/research/portfolio_optimization/missing_work/Cloud_Strategy_A3_20_100_DP_First_FINAL.afl",
    "data/research/portfolio_optimization/missing_work/Cloud_Strategy_S3_21_55_PAPER_SHADOW_MAX60.afl",
    "data/research/portfolio_optimization/missing_work/Cloud_Strategy_S3_21_55_RESEARCH_ONLY.afl",
    "data/research/portfolio_optimization/missing_work/A3_DP_First_User_Guide_FINAL.md",
    "data/research/portfolio_optimization/missing_work/S3_21_55_Paper_Shadow_User_Guide.md",
    "src/trading/intraday/schema.py",
    "src/trading/intraday/data_adapter.py",
    "src/trading/intraday/panel_overlay.py",
    "src/trading/intraday/vnindex_overlay.py",
    "src/trading/intraday/intraday_scan.py",
    "src/trading/intraday/report.py",
    "src/trading/intraday/session.py",
    "src/trading/intraday/volume_projection.py",
    "configs/intraday_scan.yaml",
    "docs/trading/INTRADAY_DATA_SOURCE_DISCOVERY.md",
    "docs/trading/INTRADAY_VNINDEX_OVERLAY.md",
    "docs/trading/INTRADAY_PREVIEW_V3_1_REVIEW_NOTE.md",
    "docs/trading/DAILY_SCAN_OPERATOR_GUIDE.md",
    "docs/trading/PHASE36_FREEZE_NOTE.md",
    "docs/trading/REAL_CAPITAL_READINESS.md",
    "docs/ema_cloud_strategy_spec.md",
    "tests/test_phase36_daily_scan.py",
    "tests/test_s3_phase35.py",
    "tests/test_intraday_scan.py",
    "tests/test_trading_order_intent.py",
    "config/live_trading.yaml",
    "data/research/intraday/phase36_intraday_scan_latest.csv",
    "data/research/intraday/phase36_intraday_scan_latest.md",
    "data/research/intraday/phase36_intraday_scan_latest.html",
    "data/research/intraday/phase36_intraday_scan_latest_meta.json",
    "data/research/intraday/review/intraday_v3_1_test_output.txt",
    "src/trading/live/s3_shadow_paper_ledger.py",
    "src/trading/live/s3_shadow_validation.py",
]

ROOT_DOCS = [
    "REVIEW_PROMPT_FOR_THIRD_AI.md",
    "DOWNLOAD_PROMPT_TEMPLATE_FOR_THIRD_AI.md",
    "CLOUD_STRATEGY_DAILY_SCAN_SUMMARY.md",
    "FILE_MANIFEST.md",
    "MISSING_FILES.md",
    "CURRENT_GIT_STATUS.txt",
    "TEST_OUTPUT_SUMMARY.txt",
    "DATA_PANEL_METADATA.txt",
]

MISSING_EXPECTED = [
    "data/research/portfolio_optimization/missing_work/Cloud_Strategy_A3_20_100_PHASE36_PRODUCTION_RANK_CONTEXT.afl",
    "A3_20_100_PHASE36_User_Guide.md",
    "S3_21_55_PHASE36_User_Guide.md",
    "configs/live_trading.yaml",
]


def main() -> None:
    PKG.mkdir(parents=True, exist_ok=True)
    (PKG / "review_outputs").mkdir(exist_ok=True)
    copied, missing = [], []
    for rel in COPY_PATHS:
        src = REPO / rel
        if not src.is_file():
            missing.append(rel)
            continue
        dst = PKG / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(rel)
    for rel in MISSING_EXPECTED:
        if not (REPO / rel).is_file() and rel not in missing:
            missing.append(rel)
    ro = REPO / "review_outputs"
    if ro.is_dir():
        for f in ro.glob("*.txt"):
            shutil.copy2(f, PKG / "review_outputs" / f.name)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in PKG.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(PKG).as_posix())
    print(f"Zip: {ZIP_PATH} ({ZIP_PATH.stat().st_size / 1024:.1f} KB)")
    print(f"Copied: {len(copied)} | Missing: {len(missing)}")


if __name__ == "__main__":
    main()
