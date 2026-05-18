#!/usr/bin/env python3
"""Build vn_auto_trading_paper_accounts_review.zip for external AI review."""
from __future__ import annotations

import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT_ZIP = REPO / "vn_auto_trading_paper_accounts_review.zip"

INCLUDE_PATHS = [
    "src/trading",
    "pp_backtest/live/run_live_workflow.py",
    "config/trading.yaml",
    "config/live_trading.yaml",
    "config/paper_accounts.yaml",
    "docs/trading/AUTO_TRADING_DESIGN_SUMMARY.md",
    "docs/trading/README.md",
    "docs/trading/REAL_CAPITAL_READINESS.md",
    "docs/trading/LIVE_CONFIG_GUIDE.md",
    "docs/trading/PAPER_TRADING_OPERATIONS_GUIDE.md",
    "docs/trading/CHATGPT_PAPER_ACCOUNTS_REVIEW_PROMPT.md",
    "docs/trading/CHATGPT_PAPER_USABILITY_REVIEW_PROMPT.md",
    "docs/trading/CHATGPT_P01_REVIEW_PROMPT.md",
    "docs/trading/CHATGPT_P0_REVIEW_PROMPT.md",
    "tests/test_trading_risk.py",
    "tests/test_trading_oms.py",
    "tests/test_trading_paper_broker.py",
    "tests/test_trading_paper_ledger_live.py",
    "tests/test_trading_reconciliation.py",
    "tests/test_trading_stale_data.py",
    "tests/test_trading_baseline_recon.py",
    "tests/test_trading_kill_switch.py",
    "tests/test_trading_daily_report_filter.py",
    "tests/test_trading_batch_risk.py",
    "tests/test_trading_trade_intent_lock.py",
    "tests/test_trading_order_intent.py",
    "tests/test_trading_p0_hardening.py",
    "tests/test_trading_p01_hardening.py",
    "tests/test_trading_live_workflow_e2e.py",
    "tests/test_trading_paper_accounts.py",
    "tests/test_trading_paper_usability.py",
    "tests/test_trading_paper_daily_ready.py",
    "scripts/trading/daily_paper_live_run.ps1",
    "tests/fixtures/trading",
    "scripts/trading/build_paper_accounts_review_zip.py",
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
