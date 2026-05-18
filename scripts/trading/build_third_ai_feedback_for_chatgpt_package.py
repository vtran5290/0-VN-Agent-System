#!/usr/bin/env python3
"""Package 3rd AI review + verification files for ChatGPT final review."""
from __future__ import annotations

import shutil
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STAMP = datetime.now().strftime("%Y%m%d_%H%M")
PKG_NAME = f"third_ai_feedback_for_chatgpt_{STAMP}"
PKG_DIR = REPO / "review" / PKG_NAME
ZIP_PATH = REPO / "review" / f"{PKG_NAME}.zip"
MAX_BYTES = 5 * 1024 * 1024
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".git", "paper_trade"}
SKIP_FILES = {".env", ".env.local", "credentials.json", "secrets.json"}


def _git_hash() -> str:
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


def _should_skip(p: Path) -> bool:
    if p.name in SKIP_FILES:
        return True
    if any(x in p.parts for x in SKIP_DIRS):
        return True
    if "paper_trade" in p.parts:
        return True
    if p.is_file() and p.stat().st_size > MAX_BYTES:
        return True
    return False


def _copy_tree(rel: str, copied: list, missing: list, skipped: list) -> None:
    src = REPO / rel
    if not src.exists():
        missing.append(rel)
        return
    if src.is_file():
        if _should_skip(src):
            skipped.append(rel)
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


def _write(name: str, text: str) -> None:
    (PKG_DIR / name).write_text(text, encoding="utf-8")


# --- 3rd AI review content (from independent review 2026-05-18) ---

FULL_REVIEW = """# Third AI Full Review — VN Agent Auto-Trading Setup

**Reviewer:** Independent 3rd AI (Claude Sonnet 4.6 class)  
**Review date:** 2026-05-18 | Git at package build: see PACKAGE_NOTES.md  
**Scope:** Paper trading infrastructure only  

**Verdict:** **Needs small fixes** — see section O.

---

## A. FACTS

| Fact | Source |
|------|--------|
| Single engine under `src/trading/` | architecture docs, manifest |
| Scan SSOT = `phase36_daily_scan_latest.csv` | `config/live_trading.yaml`, `scan_resolver.py` |
| OMS reads `final_action` only | `order_intent.py` ACTION_MAP |
| `live_auto` disabled | `live_trading.yaml`, `workflow.py` |
| DNSE hard-blocked in execute path | `order_manager.py` |
| S3 shadow separate ledger, no real orders | `paper_accounts.yaml` |
| `path_safety.py` blocks `data/paper_trade/` writes | `path_safety.py` |
| Bootstrap log + Write-StopReport in PS1 | `daily_paper_live_full_run.ps1` |
| Stale scan → exit 2 + report | PS1 + resolver |
| 110 trading tests passed (at package time) | `TEST_RESULTS` in pytest output file |
| `VN_Agent_Daily_Paper_Live_1600` still Enabled | operator schtasks query |
| scan `as_of_date` = 2026-05-15 (stale vs 2026-05-18) | phase36 latest CSV |
| 2026-05-18 scheduled task Last Result = 1 (pre-patch) | incident |
| Backfill run exited 4; SMALL RED `sample_scan` | log `paper_live_full_20260518_173938.log` |

**Interpretation:** Backfill RED/`sample_scan` likely **stale `latest_status.json`** from prior run when workflow aborts early (run lock / scan block) without `write_account_dashboard`.

---

## B. ARCHITECTURE REVIEW

- Single engine: yes (`src/trading/`).
- Scan SSOT: clean post-patch (`phase36_daily_scan_latest.csv`).
- OMS: `final_action` only; no EMA/cloud recompute.
- S3 ledger separate from A3.
- Double resolve: outer `paper_run_all` + inner `workflow` — safe if `effective_date` passed; divergence risk if edited independently.
- Three `Reconciler` instances per run in `workflow.py` — wasteful, not unsafe for paper.

---

## C. PAPER ACCOUNT REVIEW

| Account | NAV | Role |
|---------|-----|------|
| A3_DSE_PILOT_PAPER_SMALL | 30M | DSE mimic, cap_to_account_limits |
| A3_PROD_PAPER_5B | 5B | Reference, scan_size_strict |
| A3_SCALE_PAPER_10B | 10B | Scale check |
| A3_SCALE_PAPER_20B | 20B | Liquidity stress, cap_to_liquidity |
| S3_MAX60_SHADOW_PAPER | 0 | Shadow only |

20B cash drag is sizing/reference NAV, not strategy failure.

---

## D. DAILY WORKFLOW REVIEW

Fresh scan path: scan → resolve → run-all → observation artifacts — complete.  
Stale path: STOP exit 2 + report — correct.  
Gaps: abort does not refresh `latest_status.json`; backfill needs `-Force` when run lock exists; `in_a3_universe=False` rows dropped silently.

---

## E. WINDOWS SCHEDULED TASK REVIEW

- `VN_Agent_Daily_Paper_Live_1630`: cwd verified; PS1 repo root resolve handles spaces.
- **`VN_Agent_Daily_Paper_Live_1600` still Enabled** — P0 operational risk (lock before 16:30).
- Interactive logon required — no alert if session locked.

---

## F. SCAN RESOLVER / DATE POLICY REVIEW

- Latest alias correct; legacy sample requires `--allow-sample`.
- Stale policy correct for scheduled automation.
- **Bug:** `allow_sample` missing from `scan_resolve.metadata` → latent traffic-light gate issue in `account_dashboard.py`.

---

## G. SAFETY / RISK REVIEW

- live_auto: multi-layer NO-GO.
- DNSE: blocked in order manager for paper.
- Kill switch: evaluated in memory; **may not persist** to disk on main workflow path.
- Reconciliation: fail-closed gates present.
- No `data/paper_trade/` writes via path_safety.

---

## H. TEST COVERAGE REVIEW

Strong coverage on resolver, P0, paper accounts, scale, observation. Gaps: abort-status stale JSON, PS1 automation, backfill+Force, traffic light with missing allow_sample metadata.

---

## I. OPERATOR RUNBOOK REVIEW

`DAILY_PAPER_RUNBOOK.md` adequate but §8 missing `-Force` for backfill when run lock exists; no stale-status debugging path.

---

## J. GAPS

MTM NAV, slippage, VN calendar, DSE read-only, alerting, kill switch persistence, abort status JSON, allow_sample metadata, silent universe drops, `_watch_row` arg order (P2).

---

## O. VERDICT

**Needs small fixes**

Ready for forward paper-live observation after:
1. Disable `VN_Agent_Daily_Paper_Live_1600`.
2. Document `-Force` backfill in runbook §8.

Rec 3 (abort-status on early return) strongly recommended before next backfill.

**Real capital / DSE-DNSE live / live_auto: NO-GO** (enforced in code).
"""

RISK_REGISTER = """# Third AI Risk Register

## P0 — Before next scheduled run

| ID | Risk | Mitigation |
|----|------|------------|
| P0-1 | `VN_Agent_Daily_Paper_Live_1600` still Enabled — may acquire run lock before 16:30 task | `register_daily_paper_live_task.ps1 -DisableOld1600` |
| P0-2 | Post-patch 16:30 run not yet validated on scheduler | Verify 2026-05-19 log + report or clean STOP |

## P1 — Fix within 1–2 days

| ID | Risk | Mitigation |
|----|------|------------|
| P1-1 | Backfill without `-Force` → run lock abort → stale RED in summary | `write_abort_status` on workflow early return; runbook §8 |
| P1-2 | No alert if machine locked at 16:28 | Toast/email or SYSTEM task |
| P1-3 | Kill switch not saved to disk in main workflow | `save_kill_switch` after `run_monitoring()` |
| P1-4 | `allow_sample` absent from scan metadata | Add to `resolve_scan()` metadata dict |

## P2 — Track

| ID | Risk |
|----|------|
| P2-1 | No VN holiday detection |
| P2-2 | No MTM NAV |
| P2-3 | `_watch_row` positional arg order (2 call sites) |
| P2-4 | `in_a3_universe=False` silent drop |
| P2-5 | Triple Reconciler instantiation |
| P2-6 | Double scan resolve |
"""

RECOMMENDATIONS = """# Third AI Recommendations (max 15, ordered)

| # | Priority | Action |
|---|----------|--------|
| 1 | P0 | Disable `VN_Agent_Daily_Paper_Live_1600` |
| 2 | P0 | Validate next 16:30 scheduled run outputs |
| 3 | P1 | Write abort-status to `latest_status.json` on workflow early return |
| 4 | P1 | Update `DAILY_PAPER_RUNBOOK.md` §8 with `-Force` backfill |
| 5 | P1 | Persist kill switch after `run_monitoring()` |
| 6 | P1 | Add `allow_sample` to scan resolver metadata |
| 7 | P1 | Add PS1 end notification (toast/email) |
| 8 | P2 | Fix `_watch_row` keyword args in `order_intent.py` |
| 9 | P2 | Emit intent row for `in_a3_universe=False` (WATCH/SKIP) |
| 10 | P2 | Single Reconciler instance in `workflow.py` |
| 11 | P2 | VN holiday STOP at top of PS1 |
| 12 | P2 | Pass `ScanResolveResult` into workflow (no double resolve) |
| 13 | P2 | Test: run lock abort → RED `run_lock_conflict`, not `sample_scan` |
| 14 | P2 | Test: backfill with `-Force` |
| 15 | P2 | Test: S3 `s3_no_real_order_flag` blocks real order path |

**Do not:** enable real capital, DSE/DNSE live, live_auto, or change A3 strategy logic.
"""

CURSOR_PROMPT = """# Third AI Cursor Implementation Prompt

**Packaging note:** This is the suggested implementation prompt from the 3rd AI reviewer.  
**Do not apply until ChatGPT final review approves.**

```
## Cursor Implementation Task — VN Agent Paper-Live Infrastructure Fixes
## Priority: P0 → P1 → P2 (in order)
## Repo: VN Agent System (Windows; .venv\\Scripts\\python.exe)

CONSTRAINT: Do NOT modify data/paper_trade/, A3 strategy rules, EMA/cloud logic,
S3 shadow sizing, or scan classifier. Paper observation only.
Real capital: NO-GO. DSE/DNSE live: NO-GO. live_auto: NO-GO.

### FIX 1 (P0) — Disable duplicate scheduled task
  .\\scripts\\trading\\register_daily_paper_live_task.ps1 -DisableOld1600
Verify: schtasks /Query /TN "VN_Agent_Daily_Paper_Live_1600" → Disabled

### FIX 2 (P1) — write_abort_status on workflow early return
Files: src/trading/live/workflow.py, src/trading/live/account_dashboard.py
On run-lock except and scan-blocked return: write RED latest_status.json with reason.

### FIX 3 (P1) — allow_sample in scan_resolve.metadata
File: src/trading/live/scan_resolver.py

### FIX 4 (P1) — save_kill_switch after run_monitoring()
File: src/trading/live/workflow.py

### FIX 5 (P1) — DAILY_PAPER_RUNBOOK.md §8: -Force backfill example

### FIX 6 (P2) — _watch_row keyword args in order_intent.py (2 sites)

### FIX 7 (P2) — single Reconciler instance in workflow.py

### VERIFY
  .\\.venv\\Scripts\\python.exe -m pytest tests/test_trading_*.py -q
```
"""

PATCH_NOTES = """# Third AI Patch Notes / Diffs

**Status:** No patches were applied as part of this packaging step.

This package is **review + verification files only**. Suggested changes are documented in:
- `THIRD_AI_CURSOR_IMPLEMENTATION_PROMPT.md`
- `THIRD_AI_RECOMMENDATIONS.md`

When implementing, produce unified diffs per file and re-run full `tests/test_trading_*.py`.
"""

COPY_REL_PATHS = [
    "src/trading",
    "config/live_trading.yaml",
    "config/trading.yaml",
    "config/paper_accounts.yaml",
    "scripts/trading",
    "pp_backtest/live/run_live_workflow.py",
    "pp_backtest/portfolio_optimization_final_steps.py",
    "docs/trading",
    "tests/fixtures/trading",
    "data/research/portfolio_optimization/missing_work/phase36_daily_scan_latest.csv",
    "data/research/portfolio_optimization/missing_work/phase36_daily_scan_schema.csv",
    "review/ai_auto_trading_setup_review_20260518_1807/THIRD_AI_REVIEW_PROMPT.md",
    "review/ai_auto_trading_setup_review_20260518_1807/SCHEDULED_TASK_TROUBLESHOOTING_SUMMARY.md",
    "review/ai_auto_trading_setup_review_20260518_1807/CURRENT_STATUS.md",
]


def _recent_globs() -> list[str]:
    patterns = [
        "data/trading/live/accounts/daily_operator_pack_*.md",
        "data/trading/live/accounts/compare_*.md",
        "data/trading/live/accounts/valid_paper_day_*.json",
        "data/trading/live/accounts/paper_live_report_*.md",
        "data/trading/live/accounts/logs/*.log",
        "data/trading/live/accounts/run_all_summary_*.md",
    ]
    out: list[str] = []
    for pat in patterns:
        files = sorted(REPO.glob(pat), key=lambda p: p.stat().st_mtime, reverse=True)
        for p in files[:5]:
            rel = p.relative_to(REPO).as_posix()
            if rel not in out:
                out.append(rel)
    return out


def main() -> None:
    if PKG_DIR.exists():
        shutil.rmtree(PKG_DIR)
    PKG_DIR.mkdir(parents=True)

    git = _git_hash()
    copied: list[str] = []
    missing: list[str] = []
    skipped: list[str] = []

    _write("THIRD_AI_FULL_REVIEW.md", FULL_REVIEW)
    _write("THIRD_AI_RISK_REGISTER.md", RISK_REGISTER)
    _write("THIRD_AI_RECOMMENDATIONS.md", RECOMMENDATIONS)
    _write("THIRD_AI_CURSOR_IMPLEMENTATION_PROMPT.md", CURSOR_PROMPT)
    _write("THIRD_AI_PATCH_NOTES_OR_DIFFS.md", PATCH_NOTES)

    for rel in COPY_REL_PATHS + _recent_globs():
        _copy_tree(rel, copied, missing, skipped)

    for tf in sorted(REPO.glob("tests/test_trading*.py")):
        _copy_tree(tf.relative_to(REPO).as_posix(), copied, missing, skipped)

    # pytest capture
    py = REPO / ".venv/Scripts/python.exe"
    test_files = [str(p.relative_to(REPO)) for p in sorted(REPO.glob("tests/test_trading*.py"))]
    pytest_out = "pytest not run"
    if py.exists() and test_files:
        r = subprocess.run(
            [str(py), "-m", "pytest", *test_files, "-q", "--tb=no"],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=300,
        )
        pytest_out = (r.stdout + r.stderr).strip()

    (PKG_DIR / "pytest_output_at_package_time.txt").write_text(pytest_out, encoding="utf-8")

    files_for_chatgpt = """# Files for ChatGPT Final Review

## Primary review documents (read first)

1. `THIRD_AI_FULL_REVIEW.md`
2. `THIRD_AI_RISK_REGISTER.md`
3. `THIRD_AI_RECOMMENDATIONS.md`
4. `THIRD_AI_CURSOR_IMPLEMENTATION_PROMPT.md`

## Key source files to verify findings

| Path | Why |
|------|-----|
| `src/trading/live/workflow.py` | Abort paths, kill switch, recon |
| `src/trading/live/scan_resolver.py` | Latest alias, stale, metadata |
| `src/trading/live/account_dashboard.py` | Traffic light, compare |
| `src/trading/live/paper_run_all.py` | run-all, effective_date |
| `src/trading/live/order_intent.py` | final_action map, watch rows |
| `src/trading/oms/order_manager.py` | DNSE block, kill switch gate |
| `scripts/trading/daily_paper_live_full_run.ps1` | 16:30 automation |
| `config/live_trading.yaml` | scan path, safety flags |
| `config/paper_accounts.yaml` | 5 accounts |

## Runtime evidence

- `runtime_outputs/` or `data/trading/live/accounts/logs/` — recent paper_live logs
- `paper_live_report_*.md` — STOP/success reports
- `daily_operator_pack_20260515.md` — last successful observation pack
- `pytest_output_at_package_time.txt` — test run at package time

## Message for ChatGPT

> Third AI review complete — see attached zip. Real capital NO-GO | DSE/DNSE NO-GO | live_auto NO-GO unchanged. Approve or revise Cursor prompt before implementation.
"""
    _write("FILES_FOR_CHATGPT_REVIEW.md", files_for_chatgpt)

    package_notes = f"""# Package Notes

| Field | Value |
|-------|--------|
| Generated | {STAMP} |
| Git commit | `{git}` |
| Repo root | `{REPO}` |
| Package folder | `review/{PKG_NAME}/` |
| Zip | `review/{PKG_NAME}.zip` |

## Excluded

- `.env`, credentials, broker tokens
- `data/paper_trade/` (entire tree)
- Files > 5 MB (parquet, large raw data)
- `__pycache__`

## Included

- 7 third-AI review markdown files at package root
- Full `src/trading/` source tree
- Configs, scripts, docs/trading, tests/test_trading_*.py
- Recent operator outputs and logs (latest 5 per pattern)
- phase36 scan latest + schema (small CSVs)
- Original setup review excerpts under `review/ai_auto_trading_setup_review_20260518_1807/`

## Reproduce tests

```powershell
cd "<repo>"
.\\.venv\\Scripts\\python.exe -m pytest tests/test_trading_scan_resolver.py -q
```

## Implementation status

**No code changes were made to produce this package.**

## Copy stats

- Copied: {len(copied)} paths
- Missing: {len(missing)}
- Skipped: {len(skipped)}

### Missing (if any)

{chr(10).join('- ' + m for m in missing[:30]) or '- none'}

### Skipped sample

{chr(10).join('- ' + s for s in skipped[:15]) or '- none'}
"""
    _write("PACKAGE_NOTES.md", package_notes)

    # zip
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in PKG_DIR.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(PKG_DIR.parent).as_posix())

    all_files = list(PKG_DIR.rglob("*"))
    file_count = sum(1 for p in all_files if p.is_file())
    print("=" * 60)
    print(f"Folder: {PKG_DIR}")
    print(f"Zip:    {ZIP_PATH} ({ZIP_PATH.stat().st_size / 1024:.1f} KB)")
    print(f"Files:  {file_count}")
    print(f"Copied: {len(copied)} | Missing: {len(missing)} | Skipped: {len(skipped)}")
    print(f"Pytest: {pytest_out.split(chr(10))[-1] if pytest_out else 'n/a'}")
    print("Open THIRD_AI_FULL_REVIEW.md first for ChatGPT.")
    print("No secrets | no data/paper_trade | no implementation done")


if __name__ == "__main__":
    main()
