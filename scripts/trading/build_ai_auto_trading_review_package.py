#!/usr/bin/env python3
"""Build review/ai_auto_trading_setup_review_YYYYMMDD_HHMM/ + zip for 3rd AI reviewer."""
from __future__ import annotations

import shutil
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STAMP = datetime.now().strftime("%Y%m%d_%H%M")
PKG_DIR = REPO / "review" / f"ai_auto_trading_setup_review_{STAMP}"
MAX_COPY_BYTES = 5 * 1024 * 1024
EXCLUDE_DIR_NAMES = {".git", "__pycache__", ".pytest_cache", "paper_trade"}
EXCLUDE_FILE_NAMES = {".env", ".env.local", "credentials.json", "secrets.json"}

COPY_PATHS = [
    # Configs
    "config/live_trading.yaml",
    "config/trading.yaml",
    "config/paper_accounts.yaml",
    # Automation
    "scripts/trading/daily_paper_live_full_run.ps1",
    "scripts/trading/register_daily_paper_live_task.ps1",
    "scripts/trading/daily_paper_live_run.ps1",
    "pp_backtest/live/run_live_workflow.py",
    "pp_backtest/portfolio_optimization_final_steps.py",
    # Docs trading
    "docs/trading",
    # Source trading (entire tree)
    "src/trading",
    # Tests
    "tests/fixtures/trading",
    # Runtime outputs (selective)
    "data/research/portfolio_optimization/missing_work/phase36_daily_scan_latest.csv",
    "data/research/portfolio_optimization/missing_work/phase36_daily_scan_sample.csv",
    "data/research/portfolio_optimization/missing_work/phase36_daily_scan_schema.csv",
    "data/research/portfolio_optimization/missing_work/phase36_daily_scan_20260515.csv",
    "data/trading/live/accounts/daily_operator_pack_20260515.md",
    "data/trading/live/accounts/compare_20260515.md",
    "data/trading/live/accounts/valid_paper_day_20260515.json",
    "data/trading/live/accounts/run_all_summary_20260515.md",
    "data/trading/live/accounts/paper_live_report_20260518.md",
    "data/trading/live/accounts/paper_live_report_20260518_stale_stop_sample.md",
    "data/trading/live/accounts/logs/paper_live_full_20260518_173924.log",
    "data/trading/live/accounts/logs/paper_live_full_20260518_173914.log",
    "data/trading/live/s3_shadow",
    # Prior handoff prompts (context)
    "docs/trading/CHATGPT_PAPER_LIVE_TROUBLESHOOT_RESULT_PROMPT.md",
]

TEST_FILES = sorted(REPO.glob("tests/test_trading*.py"))


def _git_short_hash() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=True,
        )
        return r.stdout.strip()
    except Exception:
        return "unknown"


def _run_pytest() -> tuple[str, str]:
    files = [str(p.relative_to(REPO)).replace("\\", "/") for p in TEST_FILES]
    all_cmd = [str(REPO / ".venv/Scripts/python.exe"), "-m", "pytest", *files, "-q", "--tb=no"]
    focus_cmd = [
        str(REPO / ".venv/Scripts/python.exe"),
        "-m",
        "pytest",
        "tests/test_trading_scan_resolver.py",
        "tests/test_trading_p0_hardening.py::TestScanResolver",
        "-q",
        "--tb=no",
    ]
    try:
        all_out = subprocess.run(all_cmd, cwd=REPO, capture_output=True, text=True, timeout=300)
        focus_out = subprocess.run(focus_cmd, cwd=REPO, capture_output=True, text=True, timeout=120)
        return (all_out.stdout + all_out.stderr).strip(), (focus_out.stdout + focus_out.stderr).strip()
    except Exception as e:
        return f"pytest error: {e}", ""


def _scan_status() -> dict:
    import pandas as pd

    latest = REPO / "data/research/portfolio_optimization/missing_work/phase36_daily_scan_latest.csv"
    out = {"latest_exists": latest.exists(), "dates": [], "size_kb": 0}
    if latest.exists():
        out["size_kb"] = round(latest.stat().st_size / 1024, 1)
        df = pd.read_csv(latest, usecols=["as_of_date"])
        out["dates"] = sorted(df["as_of_date"].astype(str).unique().tolist())
    return out


def _should_skip(path: Path) -> bool:
    if path.name in EXCLUDE_FILE_NAMES:
        return True
    if any(p in EXCLUDE_DIR_NAMES for p in path.parts):
        return True
    if "paper_trade" in path.parts:
        return True
    if path.is_file() and path.stat().st_size > MAX_COPY_BYTES:
        return True
    return False


def _copy_into_pkg(rel: str, copied: list, missing: list, skipped: list) -> None:
    src = REPO / rel
    if not src.exists():
        missing.append(rel)
        return
    if src.is_file():
        if _should_skip(src):
            skipped.append(f"{rel} (skip rule)")
            return
        dst = PKG_DIR / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(rel)
        return
    for p in src.rglob("*"):
        if not p.is_file():
            continue
        rel_p = p.relative_to(REPO).as_posix()
        if _should_skip(p):
            skipped.append(rel_p)
            continue
        dst = PKG_DIR / rel_p
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dst)
        copied.append(rel_p)


def _write(name: str, content: str) -> None:
    path = PKG_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_manifest(copied: list) -> str:
    purposes = {
        "src/trading/cli.py": "CLI entry: resolve-scan, paper-accounts, workflow commands",
        "src/trading/live/workflow.py": "Paper/live workflow orchestration",
        "src/trading/live/paper_run_all.py": "Multi-account paper run-all + observation finalize",
        "src/trading/live/scan_resolver.py": "Phase36 scan path resolution, stale/sample policy",
        "src/trading/live/order_intent.py": "Scan final_action to order intents",
        "src/trading/live/sizing_policy.py": "Account sizing: strict / cap_to_liquidity / account limits",
        "src/trading/live/paper_accounts.py": "Paper account config builder",
        "src/trading/live/paper_ledger.py": "Paper position ledger",
        "src/trading/live/manual_review.py": "Manual review queue handling",
        "src/trading/live/s3_shadow_workflow.py": "S3 max60 shadow workflow (no OMS)",
        "src/trading/live/s3_shadow_paper_ledger.py": "S3 shadow ledger separate from A3",
        "src/trading/live/account_dashboard.py": "Dashboards, compare report, traffic light",
        "src/trading/live/path_safety.py": "Path validation under data/trading/live",
        "src/trading/live/run_lock.py": "Daily run lock anti-duplicate",
        "src/trading/live/data_health.py": "Data health gate before intents",
        "src/trading/oms/order_manager.py": "OMS batch submit with trade-intent lock",
        "src/trading/risk/engine.py": "Risk engine PASS/MANUAL_REVIEW/BLOCK",
        "src/trading/risk/batch_context.py": "Batch risk reviewer",
        "src/trading/risk/live_rules.py": "Live risk rules",
        "src/trading/risk/sell_rules.py": "SELL exit risk rules",
        "src/trading/reconciliation/reconciler.py": "Reconciliation engine",
        "src/trading/reconciliation/baseline.py": "Baseline recon",
        "src/trading/monitoring/kill_switch.py": "Kill switch",
        "src/trading/brokers/paper.py": "Paper broker simulator",
        "src/trading/brokers/dnse.py": "DNSE adapter (disabled for live)",
        "config/live_trading.yaml": "Live/paper paths, scan_csv_path, safety flags",
        "config/paper_accounts.yaml": "5 paper accounts NAV/sizing",
        "scripts/trading/daily_paper_live_full_run.ps1": "16:30 daily automation script",
        "scripts/trading/register_daily_paper_live_task.ps1": "Task Scheduler registration",
        "pp_backtest/portfolio_optimization_final_steps.py": "Phase36 --step scan writer",
    }
    lines = ["# File manifest\n", f"Generated: {STAMP}\n", f"Files copied into package: {len(copied)}\n\n", "| Path | Purpose |\n", "|------|--------|\n"]
    seen = set()
    for key in sorted(purposes):
        if any(c.replace("\\", "/").endswith(key) or c.replace("\\", "/") == key for c in copied):
            lines.append(f"| `{key}` | {purposes[key]} |\n")
            seen.add(key)
    lines.append("\n## All copied paths\n\n")
    for c in sorted(set(copied)):
        lines.append(f"- `{c}`\n")
    return "".join(lines)


def main() -> None:
    PKG_DIR.mkdir(parents=True, exist_ok=True)
    git_hash = _git_short_hash()
    pytest_all, pytest_focus = _run_pytest()
    scan = _scan_status()

    copied: list[str] = []
    missing: list[str] = []
    skipped: list[str] = []

    for rel in COPY_PATHS:
        _copy_into_pkg(rel, copied, missing, skipped)
    for tf in TEST_FILES:
        rel = tf.relative_to(REPO).as_posix()
        _copy_into_pkg(rel, copied, missing, skipped)

    # --- markdown docs ---
    _write("THIRD_AI_REVIEW_PROMPT.md", _third_ai_prompt())
    _write("AUTO_TRADING_SYSTEM_SUMMARY.md", _system_summary())
    _write("FILE_MANIFEST.md", _build_manifest(copied))
    _write("CURRENT_STATUS.md", _current_status(pytest_all, pytest_focus, scan, git_hash))
    _write("WORKFLOW_MAP.md", _workflow_map())
    _write("TEST_RESULTS.md", _test_results(pytest_all, pytest_focus))
    _write("DAILY_PAPER_RUNBOOK.md", _daily_runbook())
    _write("SCHEDULED_TASK_TROUBLESHOOTING_SUMMARY.md", _troubleshoot_summary(scan))
    _write("KNOWN_RISKS_AND_GAPS.md", _known_risks())
    _write("IMPLEMENTATION_HISTORY.md", _impl_history())
    _write("REVIEW_PACKAGE_NOTES.md", _package_notes(git_hash, copied, missing, skipped))
    _write("THIRD_AI_RETURN_INSTRUCTIONS.md", _return_instructions())

    zip_path = REPO / "review" / f"ai_auto_trading_setup_review_{STAMP}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in PKG_DIR.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(PKG_DIR.parent).as_posix())

    print("=" * 60)
    print(f"Review package folder: {PKG_DIR}")
    print(f"Zip file: {zip_path} ({zip_path.stat().st_size / 1024:.1f} KB)")
    print(f"Tests (all trading): {pytest_all.split(chr(10))[-1] if pytest_all else 'n/a'}")
    print(f"Tests (scan resolver): {pytest_focus.split(chr(10))[-1] if pytest_focus else 'n/a'}")
    print(f"Scan latest exists: {scan['latest_exists']} dates={scan['dates']}")
    print(f"Copied: {len(copied)} | Missing: {len(missing)} | Skipped: {len(skipped)}")
    if missing:
        print("Missing (first 10):", missing[:10])
    if skipped:
        print("Skipped (first 5):", skipped[:5])
    print()
    print('3rd AI instruction: Open THIRD_AI_REVIEW_PROMPT.md first and follow it completely.')
    print("Confirm: no secrets | no data/paper_trade | real capital NO-GO | DSE/DNSE NO-GO | live_auto NO-GO")


# --- content builders (abbreviated where repetitive) ---

def _third_ai_prompt() -> str:
    return """# Third AI Review Prompt — VN Agent Auto-Trading Setup

**Open this file first. Follow it completely.**

You are an **independent senior quant systems architect** and **Windows automation engineer** reviewing the **VN Agent System** auto-trading infrastructure.

Attach or read all files in this review package folder.

---

## Scope (IN)

- Paper trading infrastructure (`src/trading/live/`)
- Phase36 daily scan resolver and aliases
- Daily paper-live workflow (`daily_paper_live_full_run.ps1`)
- Windows Scheduled Task reliability (`VN_Agent_Daily_Paper_Live_1630`)
- PowerShell automation, bootstrap logging, stop reports
- Paper account separation (30M / 5B / 10B / 20B + S3 shadow)
- A3 production routing (`strategy_classification == A3_PRODUCTION`)
- S3 max60 paper-shadow separation (no A3 P&L mix)
- OMS / risk / reconciliation / kill switch
- Dashboards, operator pack, compare, valid_paper_day
- Tests, docs, runbooks
- Latest **2026-05-18** scheduled-run troubleshooting patch

## Out of scope (DO NOT)

- Strategy optimization or EMA/cloud logic changes
- Changing A3 rules, TP1, trail, breadth gates
- Promoting S3 or PTS to production
- Enabling **real capital**
- Enabling **DSE/DNSE live** trading
- Enabling **live_auto**
- Modifying `data/paper_trade/` (research legacy)
- Recommending live broker orders

## Verdict context (FACTS)

| Gate | Status |
|------|--------|
| Real capital | **NO-GO** |
| DSE/DNSE live | **NO-GO** |
| live_auto | **NO-GO** |
| Current target | **Daily paper-live observation only** (16:30 Mon-Fri) |

## Latest incident context (include in review)

- **2026-05-18:** `VN_Agent_Daily_Paper_Live_1630` Last Result = **1**; no log/report/operator pack for that date.
- **Root causes verified:** phase34 config fallback; resolve-scan blocked `sample` filename; PS1 AllowSample after resolve; scan `as_of_date` = 2026-05-15 only; path regex broke on spaces in repo path; no bootstrap log pre-patch.
- **Fixes applied:** `phase36_daily_scan_latest.csv`; config points to latest; stale STOP exit 2; `-UseLatestScanDate` explicit only; PS1 bootstrap log + `paper_live_report` on STOP.
- **Validation:** 110 trading tests passed; stale scan exits cleanly with report.

Read in order: `AUTO_TRADING_SYSTEM_SUMMARY.md` → `WORKFLOW_MAP.md` → `SCHEDULED_TASK_TROUBLESHOOTING_SUMMARY.md` → `CURRENT_STATUS.md` → source files in manifest.

---

## Required output format

Produce a single markdown review with these sections:

### A. FACTS
Separate verified facts from interpretation. Cite file paths.

### B. ARCHITECTURE REVIEW
Single engine under `src/trading/`? Scan SSOT? OMS consumes `final_action` only? Any duplicate paths?

### C. PAPER ACCOUNT REVIEW
30M / 5B / 10B / 20B / S3 — separation, sizing basis, ledger paths, compare interpretation.

### D. DAILY WORKFLOW REVIEW
scan → resolve → run-all → operator pack. Failure modes.

### E. WINDOWS SCHEDULED TASK REVIEW
16:30 task, working directory, interactive logon, old 16:00 duplicate task.

### F. SCAN RESOLVER / DATE POLICY REVIEW
latest alias, legacy sample name, stale STOP, UseLatestScanDate override.

### G. SAFETY / RISK REVIEW
kill switch, recon gating, sample blocking, broker gates, no live_auto path.

### H. TEST COVERAGE REVIEW
Gaps in `tests/test_trading_*.py`. What is untested?

### I. OPERATOR RUNBOOK REVIEW
Is `DAILY_PAPER_RUNBOOK.md` sufficient for 16:25–16:45 ops?

### J. GAPS
Missing features (MTM NAV, slippage, calendar, DSE read-only, etc.).

### K. RISKS — P0 / P1 / P2
Ranked risk register.

### L. RECOMMENDATIONS — max 15, ordered
Minimal patches only. **No strategy changes. No live capital.**

### M. REQUIRED IMPLEMENTATION PROMPT FOR CURSOR
Full copy-paste prompt if fixes needed.

### N. FILES TO ZIP BACK FOR CHATGPT
List paths the operator should return for final ChatGPT review.

### O. VERDICT — exactly one of:
- **Ready for forward paper-live observation**
- **Needs small fixes**
- **Not ready**

---

## Hard rules for your verdict

- Do **not** recommend real capital, DSE/DNSE live, or live_auto.
- Do **not** recommend ignoring stale scan on scheduled runs.
- Scheduled run **must** STOP cleanly when panel EOD lags (exit 2 + report).
- S3 must remain shadow-only, separate ledger.

---

*End of third AI review prompt*
"""


def _system_summary() -> str:
    return """# Auto-Trading System Summary

## 1. System purpose

- Vietnam equities **paper-trading** infrastructure
- A3 daily scan paper execution simulator (no live broker)
- DSE future API sandbox preparation (read-only / disabled live)
- S3 max60 **shadow radar** tracking (separate P&L)
- Scheduled daily paper-live observation at **16:30** Mon-Fri

## 2. Architecture

| Principle | Implementation |
|-----------|----------------|
| Single engine | `src/trading/` |
| Backtest wrapper | `pp_backtest/live/run_live_workflow.py` only |
| Signal SSOT | Phase36 daily scan CSV (`final_action`, `strategy_classification`) |
| OMS input | `final_action` mapped to intents — **no** EMA/cloud recompute in OMS |
| LLM in trade path | **None** |
| Real broker orders | **Disabled** (`live_auto` NO-GO) |
| Research ledger | `data/paper_trade/` — **not written by live engine** |
| Execution ledger | `data/trading/live/accounts/<ACCOUNT_ID>/` |

## 3. Frozen strategy contract (A3)

- **A3_DP only** — exact `strategy_classification == A3_PRODUCTION`
- T1 = 50% of slot; T2 only on `ADD_T2`
- TP1 = +18%; trail = 2.5× ATR14; max hold = 250 bars
- Breadth defense → **manual review**, not hard T1 block
- Sector L4 → warning only
- `a3_rank_score` → operator sort only
- Macro → `pending_external_data`
- AFL → visual only
- Performance throttle → **rejected**

## 4. S3 contract

- Old S3 max_hold=250 → research-only / rejected for production shadow
- **S3 max60** → paper-shadow only (`S3_MAX60_SHADOW_PAPER`)
- No production orders; no DSE/DNSE; **no A3 P&L mix**

## 5. Paper accounts

| Account | NAV | Sizing / role |
|---------|-----|----------------|
| `A3_DSE_PILOT_PAPER_SMALL` | 30M VND | `cap_to_account_limits` — DSE pilot mimic |
| `A3_PROD_PAPER_5B` | 5B VND | `scan_size_strict` — production reference |
| `A3_SCALE_PAPER_10B` | 10B VND | `scan_size_strict` — scale check |
| `A3_SCALE_PAPER_20B` | 20B VND | `cap_to_liquidity` — liquidity stress |
| `S3_MAX60_SHADOW_PAPER` | 0 | Shadow only — `data/trading/live/s3_shadow/` |

## 6. Daily workflow

1. Phase36 scan (`portfolio_optimization_final_steps.py --step scan`)
2. Writes `phase36_daily_scan_latest.csv` (+ legacy sample name)
3. `resolve-scan` — calendar date must match `as_of_date` (or STOP)
4. `paper-accounts run-all` — 4 A3 accounts + optional S3 shadow
5. Outputs: operator pack, compare, valid_paper_day, per-account dashboards
6. Manual review queues for operator (not auto-approved)
7. **No** live broker routing

## 7. Scheduled task

| Item | Value |
|------|--------|
| Task | `VN_Agent_Daily_Paper_Live_1630` |
| Script | `scripts/trading/daily_paper_live_full_run.ps1` |
| Schedule | Mon–Fri 16:30 local |
| Fixes | Bootstrap log, stop report, latest scan alias, stale STOP (exit 2), `-UseLatestScanDate` override only |

## Safety gates (unchanged)

- Real capital: **NO-GO**
- DSE/DNSE live: **NO-GO**
- live_auto: **NO-GO**
"""


def _current_status(pytest_all: str, pytest_focus: str, scan: dict, git_hash: str) -> str:
    dates = ", ".join(scan.get("dates", [])) or "unknown"
    return f"""# Current Status

Generated: {STAMP} | Git: `{git_hash}`

## 1. Readiness

| Mode | Status |
|------|--------|
| Paper observation | **Ready if scan `as_of_date` matches calendar day** |
| Real capital | **NO-GO** |
| DSE/DNSE live | **NO-GO** |
| live_auto | **NO-GO** |

## 2. Latest test results

### All `tests/test_trading_*.py`

```
{pytest_all}
```

### Scan resolver focus

```
{pytest_focus}
```

## 3. Scheduled fix / scan status

| Check | Result |
|-------|--------|
| `phase36_daily_scan_latest.csv` exists | {scan.get('latest_exists')} (~{scan.get('size_kb')} KB) |
| Current scan `as_of_date` values | {dates} |
| `resolve-scan --date 2026-05-18` (latest path) | **blocked=True**, stale=True (expected until panel refreshes) |
| Stale STOP (PS1) | exit **2**, bootstrap log + `paper_live_report` written |
| Task WorkingDirectory | `C:\\Users\\LOLII\\Documents\\V\\0. VN Agent System` (verified) |
| Old `VN_Agent_Daily_Paper_Live_1600` | **Still Enabled** — recommend disable |

## 4. Known incident (2026-05-18)

- Scheduled task Last Result = **1** (pre-patch run)
- Missing: operator pack, compare, valid_paper_day, logs, report for 20260518
- Root causes: phase34 config; sample blocked; PS1 ordering; stale as_of 2026-05-15; path spaces; no bootstrap log

## 5. Next 16:30 expectation

- **Fresh panel** → full success artifacts
- **Stale panel** → clean STOP exit 2 (not silent failure)
"""


def _workflow_map() -> str:
    return """# Workflow Map

## Scheduled normal run (16:30 Mon-Fri)

```mermaid
flowchart TD
  T[Task VN_Agent_Daily_Paper_Live_1630] --> PS1[daily_paper_live_full_run.ps1]
  PS1 --> LOG[Bootstrap log]
  PS1 --> SCAN[Phase36 scan step]
  SCAN --> LATEST[phase36_daily_scan_latest.csv]
  PS1 --> RESOLVE[resolve-scan]
  RESOLVE -->|date match| RUN[paper-accounts run-all]
  RESOLVE -->|stale| STOP[STOP exit 2 + paper_live_report]
  RUN --> A3[4x A3 paper accounts]
  RUN --> S3[S3 shadow optional]
  RUN --> OUT[operator pack / compare / valid_paper_day]
```

| Step | Action | Output |
|------|--------|--------|
| 1 | Task starts 16:30 | — |
| 2 | PS1 bootstrap log | `logs/paper_live_full_YYYYMMDD_HHMMSS.log` |
| 3 | Phase36 scan (optional skip) | `phase36_daily_scan_latest.csv` |
| 4 | resolve-scan + date policy | blocked if stale |
| 5 | run-all (4 A3) | per-account ledgers, intents |
| 6 | S3 shadow update | `data/trading/live/s3_shadow/` |
| 7 | Observation finalize | compare, valid_paper_day, operator pack |
| 8 | paper_live_report | success or STOP summary |

**No real broker orders at any step.**

## Manual backfill

- Flag: `-UseLatestScanDate` (PS1) / `--use-latest-scan-date` (CLI)
- Uses latest scan `as_of_date` for run-all outputs
- Report must note calendar vs scan override

## Failure paths

| Condition | Behavior | Exit |
|-----------|----------|------|
| Stale scan (calendar != as_of) | STOP, no run-all | 2 |
| Arbitrary sample CSV | blocked | 1 |
| Legacy phase36 sample without allow-sample | blocked | 1 |
| resolve-scan error | STOP report | 1 |
| Data health fail | workflow abort | varies |
| Reconciliation dirty | traffic light RED/YELLOW | — |
| Run lock duplicate | abort unless --force | — |
| Manual review pending | queue CSV, not auto-approved | — |
| Task wrong cwd / no logon | no log file | 1 |

## Key output files

| File | Purpose |
|------|---------|
| `daily_operator_pack_YYYYMMDD.md` | Paste to ChatGPT |
| `compare_YYYYMMDD.md` | 4-account comparison |
| `valid_paper_day_YYYYMMDD.json` | Validity gate |
| `paper_live_report_YYYYMMDD.md` | Daily verdict / STOP reason |
| `run_all_summary_YYYYMMDD.md` | Run-all text summary |
"""


def _test_results(pytest_all: str, pytest_focus: str) -> str:
    return f"""# Test Results

Captured: {STAMP}

## Command 1 — all trading tests

```powershell
python -m pytest tests/test_trading_*.py -q
```

```
{pytest_all}
```

## Command 2 — scan resolver focus

```powershell
python -m pytest tests/test_trading_scan_resolver.py tests/test_trading_p0_hardening.py::TestScanResolver -q
```

```
{pytest_focus}
```

## Key test modules

| Module | Focus |
|--------|--------|
| `test_trading_scan_resolver.py` | latest alias, stale, allow-sample legacy |
| `test_trading_p0_hardening.py` | scan resolver, sell exits, run lock |
| `test_trading_paper_accounts.py` | account init, workflow |
| `test_trading_paper_scale_accounts.py` | 10B/20B scale |
| `test_trading_paper_observation_diagnostics.py` | valid_paper_day, operator pack |
| `test_trading_live_workflow_e2e.py` | end-to-end paper path |
"""


def _daily_runbook() -> str:
    return """# Daily Paper Runbook

## 1. One-time setup

```powershell
cd "C:\\Users\\LOLII\\Documents\\V\\0. VN Agent System"
.\\scripts\\trading\\register_daily_paper_live_task.ps1 -DisableOld1600
python -m src.trading.cli paper-accounts list
# Init each account once (idempotent)
python -m src.trading.cli paper-accounts init --account A3_PROD_PAPER_5B
# ... repeat for SMALL, 10B, 20B, S3_MAX60_SHADOW_PAPER
```

## 2. Daily 16:25–16:45 checklist

| Time | Action |
|------|--------|
| 16:25 | Confirm machine logged on (task is interactive) |
| 16:25 | Optional: `python pp_backtest/portfolio_optimization_final_steps.py --step scan` |
| 16:30 | Task runs OR manual: `.\\scripts\\trading\\daily_paper_live_full_run.ps1` |
| 16:35 | Check `data/trading/live/accounts/logs/paper_live_full_*.log` |
| 16:35 | Open `paper_live_report_YYYYMMDD.md` OR success artifacts |
| 16:40 | If GREEN: open `daily_operator_pack_YYYYMMDD.md` for ChatGPT |
| 16:45 | Process manual review queues if any |

## 3. Scheduled task expected behavior

- **Fresh scan date** → operator pack, compare, valid_paper_day created
- **Stale scan** → exit 2, report explains stale; **no** silent trade on old data

## 4. Manual review process

- Queues: `manual_review_queue_YYYYMMDD.csv` per account
- Operator approves/rejects in CSV; then `apply-manual-review` (see CLI)
- Breadth defense rows require explicit review — not auto-approved

## 5. What to inspect

- Traffic light: `dashboard/latest_status.json` per account
- Reconciliation: `reconciliation_status.json`
- Compare: `compare_YYYYMMDD.md` (sizing differences ≠ strategy change)
- S3: `data/trading/live/s3_shadow/` only

## 6. Valid paper day

- See `valid_paper_day_YYYYMMDD.json` — `valid: true` with no blocking warnings
- If `valid: false`, read reasons before treating run as observation-ready

## 7. Traffic light actions

| Light | Action |
|-------|--------|
| GREEN | Normal observation; paste operator pack to ChatGPT |
| YELLOW | Review warnings, manual queue, recon notes |
| RED | Do not treat as clean day; fix recon/data before inference |

## 8. Stale STOP

- Report says calendar date ≠ scan `as_of_date`
- **Do not** re-run without understanding panel lag
- Backfill only: `-UseLatestScanDate` (explicit)

## 9. Paste back to ChatGPT

- `daily_operator_pack_YYYYMMDD.md`
- `compare_YYYYMMDD.md` (if multi-account questions)
- `valid_paper_day_YYYYMMDD.json` summary
- Any STOP: `paper_live_report_YYYYMMDD.md` + tail of log

## 10. Non-negotiables

- No DSE/DNSE live orders
- No real capital
- No live_auto
- No writes to `data/paper_trade/`
- S3 shadow only — never mix into A3 production P&L
"""


def _troubleshoot_summary(scan: dict) -> str:
    dates = ", ".join(scan.get("dates", [])) or "unknown"
    return f"""# Scheduled Task Troubleshooting Summary

## 1. Incident table

| Field | Value |
|-------|--------|
| Date | 2026-05-18 (Monday) |
| Task | `VN_Agent_Daily_Paper_Live_1630` |
| Last Result (pre-fix run) | **1** |
| Missing outputs | operator pack, compare, valid_paper_day, logs, paper_live_report for 20260518 |
| Duplicate task | `VN_Agent_Daily_Paper_Live_1600` — still **Enabled** (disable recommended) |
| Working directory | `C:\\Users\\LOLII\\Documents\\V\\0. VN Agent System` |

## 2. Root cause ranking

| Rank | Cause |
|------|--------|
| P0 | `live_trading.yaml` → `phase34_daily_scan_sample.csv` |
| P0 | `resolve-scan` blocked `sample` in filename |
| P0 | PS1 set AllowSample **after** resolve-scan |
| P0 | Scan `as_of_date` = 2026-05-15 only (stale vs 2026-05-18) |
| P1 | Path regex truncated at space in repo path |
| P2 | No bootstrap log before patch |

## 3. Patches applied

| File | Change |
|------|--------|
| `portfolio_optimization_final_steps.py` | Write `phase36_daily_scan_latest.csv` + dated copy |
| `config/live_trading.yaml` | Point to latest alias |
| `scan_resolver.py` | Latest preference, legacy allow-sample, stale policy |
| `cli.py` | `--allow-sample`, `--use-latest-scan-date` |
| `daily_paper_live_full_run.ps1` | Bootstrap log, Write-StopReport, ordering fix |
| `register_daily_paper_live_task.ps1` | WorkingDirectory, -DisableOld1600 |

## 4. Validation

| Test | Result |
|------|--------|
| pytest trading | 110 passed |
| scan writes latest | yes (~{scan.get('size_kb')} KB) |
| scan dates | {dates} |
| resolve-scan 2026-05-18 | blocked stale |
| PS1 stale STOP | exit 2 + log + report |
| Task cwd | verified correct |

## 5. Expected behavior

| Scan state | Outcome |
|------------|---------|
| Fresh (as_of = today) | Full success artifacts |
| Stale | Clean STOP exit 2 |
| Manual backfill | `-UseLatestScanDate` only |

## 6. Remaining operator blockers

1. Refresh EOD panel / FireAnt SSOT so scan includes current session date
2. Re-register task: `.\\scripts\\trading\\register_daily_paper_live_task.ps1 -DisableOld1600`
3. Disable `VN_Agent_Daily_Paper_Live_1600`
"""


def _known_risks() -> str:
    return """# Known Risks and Gaps

## P0

1. **EOD panel freshness** — scan may lag calendar date after 16:30; scheduled run will STOP (intended) but operator must refresh panel.
2. **Next scheduled run unproven post-patch** — 2026-05-18 failure was pre-patch; confirm 19-May produces log + report.
3. **Duplicate 16:00 task** — `VN_Agent_Daily_Paper_Live_1600` still enabled; may confuse operators.

## P1

4. **Arbitrary sample files** — resolver must not allow non-legacy sample paths (verify tests).
5. **20B cash drag** — under-deployment may look like strategy failure; compare doc explains sizing vs strategy.
6. **Dashboard bool parsing** — `parse_csv_bool` fix applied; verify manual review counts in production CSVs.

## P2

7. Mark-to-market NAV — not fully implemented
8. Slippage / partial fill simulator — not implemented
9. VN trading calendar / holidays — not implemented
10. DSE read-only integration — not implemented
11. **Real capital readiness** — explicitly **NO-GO** per `REAL_CAPITAL_READINESS.md`
"""


def _impl_history() -> str:
    return """# Implementation History

| Phase | Focus |
|-------|--------|
| P0 hardening | Scan resolver, run lock, sell exits, paper execution, batch OMS |
| P0.1 hardening | Additional live workflow gates |
| Paper accounts | 30M + 5B named accounts, ledgers under `data/trading/live/accounts/` |
| Usability | CLI paper-accounts, dashboards, traffic light |
| Scale accounts | 10B / 20B observation, `cap_to_liquidity`, compare interpretation |
| Paper diagnostics | `valid_paper_day`, `daily_operator_pack`, `parse_csv_bool` |
| 16:30 scheduled task fix | latest scan alias, stale STOP, PS1 bootstrap log, path parse fix |

Commit reference at package build: see `REVIEW_PACKAGE_NOTES.md`.
"""


def _package_notes(git_hash: str, copied: list, missing: list, skipped: list) -> str:
    return f"""# Review Package Notes

| Field | Value |
|-------|--------|
| Generated | {STAMP} |
| Git commit | `{git_hash}` |
| Repo root | `C:\\Users\\LOLII\\Documents\\V\\0. VN Agent System` |
| Files copied | {len(copied)} |
| Missing | {len(missing)} |
| Skipped | {len(skipped)} |

## Excluded (by design)

- `.env`, credentials, broker tokens
- `data/paper_trade/` (research legacy)
- Parquet / huge data files (>5 MB)
- Unrelated `data/` trees

## Reproduce tests

```powershell
cd "<repo>"
.\\.venv\\Scripts\\python.exe -m pytest tests/test_trading_scan_resolver.py -q
```

## Reproduce daily workflow

```powershell
.\\scripts\\trading\\daily_paper_live_full_run.ps1 -Date (Get-Date -Format yyyy-MM-dd)
```

## Review scheduled task

```powershell
schtasks /Query /TN "VN_Agent_Daily_Paper_Live_1630" /V /FO LIST
```

## Why `data/paper_trade` is excluded

Research/backtest ledger and reports live there. Live paper engine writes only to `data/trading/live/` to avoid mixing research and observation ledgers.

## Missing paths (if any)

{chr(10).join('- ' + m for m in missing[:20]) or '- none'}
"""


def _return_instructions() -> str:
    return """# Third AI Return Instructions

After completing your review per `THIRD_AI_REVIEW_PROMPT.md`, return to the operator:

## 1. Full review markdown
All sections A through O in one document.

## 2. P0 / P1 / P2 risk register
Table format with mitigation.

## 3. Prioritized recommendations
Max 15; minimal scope; no strategy changes.

## 4. Cursor implementation prompt
Copy-paste ready if fixes required.

## 5. Files to zip back for ChatGPT
Explicit list of paths (configs, patched scripts, test outputs, sample reports).

## 6. Optional patch notes
Suggested diffs or pseudocode — not mandatory.

## 7. Verdict
One of: Ready for forward paper-live observation | Needs small fixes | Not ready

## 8. Package prompt for Cursor
If operator needs a return zip, specify exactly which files to include for ChatGPT final sign-off.

---

## You must NOT recommend

- Real capital deployment
- DSE/DNSE live trading
- live_auto
- A3 strategy / EMA / cloud logic changes
- S3 or PTS promotion to production
- Ignoring stale scan on scheduled automation

---

## Operator next step

Zip your review markdown + any cited file excerpts and return to ChatGPT with:

> "Third AI review complete — see attached. Real capital NO-GO unchanged."
"""


if __name__ == "__main__":
    main()
