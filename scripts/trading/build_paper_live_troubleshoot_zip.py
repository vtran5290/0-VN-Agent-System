#!/usr/bin/env python3
"""Build vn_paper_live_troubleshoot_1630.zip for external AI troubleshooting."""
from __future__ import annotations

import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT_ZIP = REPO / "vn_paper_live_troubleshoot_1630.zip"

INCLUDE_PATHS = [
    # Prompt + ops docs
    "docs/trading/CHATGPT_PAPER_LIVE_TROUBLESHOOT_PROMPT.md",
    "docs/trading/DAILY_PAPER_OPERATOR_PROMPT.md",
    "docs/trading/PAPER_TRADING_OPERATIONS_GUIDE.md",
    "docs/trading/LIVE_CONFIG_GUIDE.md",
  # Config
    "config/live_trading.yaml",
    "config/paper_accounts.yaml",
    "config/trading.yaml",
  # Scheduler + daily run
    "scripts/trading/daily_paper_live_full_run.ps1",
    "scripts/trading/daily_paper_live_run.ps1",
    "scripts/trading/register_daily_paper_live_task.ps1",
  # Core resolver / workflow / CLI
    "src/trading/cli.py",
    "src/trading/config.py",
    "src/trading/live/scan_resolver.py",
    "src/trading/live/paper_run_all.py",
    "src/trading/live/paper_observation.py",
    "src/trading/live/paper_accounts.py",
    "src/trading/live/workflow.py",
    "src/trading/live/account_dashboard.py",
    "pp_backtest/live/run_live_workflow.py",
  # Scan pipeline (step entry)
    "pp_backtest/portfolio_optimization_final_steps.py",
  # Incident: production scan + reference outputs
    "data/research/portfolio_optimization/missing_work/phase36_daily_scan_sample.csv",
    "data/research/portfolio_optimization/missing_work/phase36_daily_scan_schema.csv",
    "data/trading/live/accounts/daily_operator_pack_20260515.md",
    "data/trading/live/accounts/valid_paper_day_20260515.json",
    "data/trading/live/accounts/compare_20260515.md",
    "data/trading/live/accounts/run_all_summary_20260515.md",
  # Tests for scan resolver / paper daily
    "tests/test_trading_paper_daily_ready.py",
    "tests/test_trading_paper_observation_diagnostics.py",
    "scripts/trading/build_paper_live_troubleshoot_zip.py",
]

SKIP_SUFFIXES = {".pyc", ".pyo"}
SKIP_DIRS = {"__pycache__", ".pytest_cache"}


def _add_path(zf: zipfile.ZipFile, rel: str) -> int:
    root = REPO / rel
    if not root.exists():
        print(f"WARN missing: {rel}")
        return 0
    n = 0
    if root.is_file():
        zf.write(root, rel.replace("\\", "/"))
        return 1
    for p in root.rglob("*"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix in SKIP_SUFFIXES:
            continue
        if p.is_file():
            arc = p.relative_to(REPO).as_posix()
            zf.write(p, arc)
            n += 1
    return n


def main() -> None:
    if OUT_ZIP.exists():
        OUT_ZIP.unlink()
    total = 0
    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in INCLUDE_PATHS:
            total += _add_path(zf, rel)
    size_kb = OUT_ZIP.stat().st_size / 1024
    print(f"Wrote {OUT_ZIP} ({size_kb:.1f} KB, {total} files)")


if __name__ == "__main__":
    main()
