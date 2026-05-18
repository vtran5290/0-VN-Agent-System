# ChatGPT Review Prompt — Daily Paper-Live 16:30 Fix (Post-Implementation)

Copy everything below the line. Attach **`vn_paper_live_troubleshoot_1630_result.zip`** (repo root).

---

You are a senior quant systems / Windows automation engineer **reviewing a completed fix** for a failed scheduled daily paper-trading run in repo **VN Agent System** (Vietnam equities, **paper only**).

Your job: **QA the patch set**, confirm safety gates unchanged, validate operator runbook, and flag any remaining risks before the next **16:30** scheduled run.

## Non-negotiables (must remain true)

- **Real capital: NO-GO** | **DSE/DNSE live: NO-GO** | **live_auto: NO-GO**
- A3_DP / exact A3_PRODUCTION is the only production paper strategy
- Daily scan CSV is signal SSOT; OMS consumes `final_action` only
- No EMA/cloud/breadth/ATR/trail recompute in OMS
- S3 max60 is paper-shadow only; cannot route to A3 production / DSE / DNSE
- PTS remains shadow/off
- **Do not** write to `data/paper_trade/` (research legacy)
- Do not weaken broker safety gates

---

## 1. Incident (original failure) — FACTS

| Item | Value |
|------|--------|
| Calendar date | **2026-05-18** (Monday) |
| Scheduled task | `VN_Agent_Daily_Paper_Live_1630` |
| Schedule | Mon–Fri **16:30** local |
| Script | `scripts/trading/daily_paper_live_full_run.ps1` |
| Task last run | **18-May-2026 16:30** |
| Task last result | **1** (before fix) |
| Task Start In | `C:\Users\LOLII\Documents\V\0. VN Agent System` (verified correct) |
| Older task | `VN_Agent_Daily_Paper_Live_1600` also failed (duplicate; should be disabled) |

**Missing on 2026-05-18 (before fix):** `daily_operator_pack_20260518.md`, `compare_20260518.md`, `valid_paper_day_20260518.json`, logs, `paper_live_report_20260518.md`

**Manual reference that worked:** `paper-accounts run-all --date 2026-05-15 --scan-path phase36_daily_scan_sample.csv --allow-sample`

---

## 2. Root cause — VERIFIED (ranked)

### P0 — Config + resolver blocked production scan

- `config/live_trading.yaml` had `scan_csv_path: .../phase34_daily_scan_sample.csv`
- `resolve-scan` without `--scan-path` used that fixture → **blocked** (`sample` in filename, `allow_sample_scan: false`)
- Scheduled PS1 called `resolve-scan` with **no** `--scan-path` and **no** `--allow-sample` → exit **1** immediately

### P0 — PowerShell ordering bug

- PS1 set `$AllowSample = $true` for phase36 **after** `resolve-scan` (never reached when resolve failed first)

### P0 — Stale scan date (data, not code)

- After `--step scan`, `as_of_date` in CSV = **2026-05-15 only** (not 2026-05-18)
- Monday run with Friday EOD panel → correct **STOP** under new policy (exit **2**)

### P1 — Path parse bug (spaces in repo path)

- Regex `path=([^\s]+)` truncated at `0.` in `C:\Users\LOLII\Documents\V\0. VN Agent System\...`
- Fixed to `path=(.+?)\s+source=`

### P2 — No bootstrap log on early failure (18-May)

- Explains missing log/report on original scheduled run (pre-patch)

---

## 3. Patches applied (minimal, no strategy change)

| File | Change |
|------|--------|
| `pp_backtest/portfolio_optimization_final_steps.py` | Also writes `phase36_daily_scan_latest.csv` + `phase36_daily_scan_YYYYMMDD.csv` |
| `config/live_trading.yaml` | `scan_csv_path` → `phase36_daily_scan_latest.csv` |
| `src/trading/live/scan_resolver.py` | Prefer latest; legacy `phase36_daily_scan_sample.csv` only with `--allow-sample`; stale blocks; `--use-latest-scan-date` override |
| `src/trading/cli.py` | `resolve-scan` / `run-all`: `--allow-sample`, `--use-latest-scan-date`; richer CLI output |
| `src/trading/live/paper_run_all.py` | Uses `effective_date` from resolver |
| `scripts/trading/daily_paper_live_full_run.ps1` | Bootstrap log first; `Write-StopReport`; try/catch; pick scan path before resolve; exit 2 stale; `-UseLatestScanDate` |
| `scripts/trading/register_daily_paper_live_task.ps1` | `-WorkingDirectory`, principal, `-DisableOld1600` |
| `tests/test_trading_scan_resolver.py` | New tests |
| `tests/test_trading_p0_hardening.py` | Sample policy test updated |
| Docs | `PAPER_TRADING_OPERATIONS_GUIDE.md`, `DAILY_PAPER_OPERATOR_PROMPT.md`, `LIVE_CONFIG_GUIDE.md` |

---

## 4. Date policy (implemented)

| Mode | Behavior |
|------|----------|
| **Scheduled default** | Calendar date must match scan `as_of_date` → else **STOP** (exit 2), log + `paper_live_report` |
| **Manual backfill** | `-UseLatestScanDate` (PS1) / `--use-latest-scan-date` (CLI) → run with latest scan `as_of_date`; outputs use scan date; report notes override |

Rationale: do not silently trade Friday scan on Monday without explicit operator consent.

---

## 5. Validation results (post-patch)

```text
pytest tests/test_trading_scan_resolver.py tests/test_trading_p0_hardening.py::TestScanResolver
  + scale/observation/usability/paper_accounts → 87 passed

pp_backtest/portfolio_optimization_final_steps.py --step scan
  → OK, 94 rows; phase36_daily_scan_latest.csv created

resolve-scan --date 2026-05-18 --scan-path .../phase36_daily_scan_latest.csv
  → blocked=True, stale=True, scan_date=2026-05-15 (expected until panel updates)

daily_paper_live_full_run.ps1 -Date 2026-05-18 -SkipScanStep
  → exit 2, bootstrap log created, paper_live_report written (stale STOP)

schtasks /Query /TN VN_Agent_Daily_Paper_Live_1630
  → WorkingDirectory correct; Last Result still 1 from pre-fix run
```

**Scan dates in production file (FACT):** only `2026-05-15` as of validation run on 2026-05-18.

---

## 6. Expected behavior at next 16:30

| Condition | Outcome |
|-----------|---------|
| Scan `as_of_date` = calendar today | Full success: operator pack, compare, valid_paper_day, success report |
| Scan stale (panel lag) | Clean STOP exit **2**: log + `paper_live_report_YYYYMMDD.md` — **not** silent failure |
| Operator backfill | `-UseLatestScanDate` only |

---

## 7. Remaining blockers (operator)

1. **Refresh EOD panel** so scan includes current trading day (FireAnt / SSOT parquet max date).
2. **Re-register task** (optional): `.\scripts\trading\register_daily_paper_live_task.ps1 -DisableOld1600`
3. **Disable** `VN_Agent_Daily_Paper_Live_1600` if still enabled.

Until panel updates, scheduled run will **correctly stop** on stale scan — this is intended.

---

## 8. Architecture quick reference (read in zip)

1. `docs/trading/PAPER_TRADING_OPERATIONS_GUIDE.md` — scheduled run + troubleshooting
2. `scripts/trading/daily_paper_live_full_run.ps1` — daily automation
3. `src/trading/live/scan_resolver.py` — fail-closed scan policy
4. `config/live_trading.yaml` — `phase36_daily_scan_latest.csv`
5. `config/paper_accounts.yaml` — 5 paper accounts

## Paper accounts (5)

| Account | NAV | Role |
|---------|-----|------|
| A3_DSE_PILOT_PAPER_SMALL | 30M | DSE pilot mimic |
| A3_PROD_PAPER_5B | 5B | Reference |
| A3_SCALE_PAPER_10B | 10B | Scale check |
| A3_SCALE_PAPER_20B | 20B | Liquidity stress |
| S3_MAX60_SHADOW_PAPER | 0 | Shadow only |

---

## 9. Your review deliverables

1. **Patch QA** — Any safety regression? Can arbitrary `*sample*` files slip through?
2. **Resolver logic** — Is legacy `phase36_daily_scan_sample.csv` handling correct?
3. **PS1 robustness** — Bootstrap log, exit codes, path-with-spaces, `Write-StopReport` on all paths?
4. **Date policy** — Is stale STOP + explicit override the right ops model?
5. **Task Scheduler** — Is `register_daily_paper_live_task.ps1` sufficient for interactive logon + working directory?
6. **Test gaps** — What else should be unit-tested?
7. **Operator runbook** — One-page “trading day 16:25–16:45” checklist
8. **Verdict** — Ready for production paper observation at 16:30? [yes/no + conditions]

---

## 10. Verdict template (fill in)

| Item | Your answer |
|------|-------------|
| Primary failure (original) | |
| Fix completeness | |
| Can 16:30 run succeed without panel refresh? | |
| Can 16:30 run fail safely with stale panel? | |
| Minimal follow-up patches | |
| Confidence | high / medium / low |

---

## 11. Commands to re-validate

```powershell
cd "C:\Users\LOLII\Documents\V\0. VN Agent System"

.\.venv\Scripts\python.exe -m pytest tests/test_trading_scan_resolver.py tests/test_trading_p0_hardening.py::TestScanResolver -q

.\.venv\Scripts\python.exe pp_backtest/portfolio_optimization_final_steps.py --step scan

.\.venv\Scripts\python.exe -c "import pandas as pd; df=pd.read_csv('data/research/portfolio_optimization/missing_work/phase36_daily_scan_latest.csv'); print(sorted(df['as_of_date'].astype(str).unique())[-5:])"

.\.venv\Scripts\python.exe -m src.trading.cli resolve-scan --date (Get-Date -Format yyyy-MM-dd) --scan-path data/research/portfolio_optimization/missing_work/phase36_daily_scan_latest.csv

.\scripts\trading\daily_paper_live_full_run.ps1 -Date (Get-Date -Format yyyy-MM-dd)

schtasks /Query /TN "VN_Agent_Daily_Paper_Live_1630" /V /FO LIST
```

---

## Do NOT recommend

- Enabling real capital, DSE/DNSE live, or `live_auto`
- Changing A3 strategy logic
- Ignoring stale scan on scheduled runs
- Pointing production config back to phase34 sample

---

*End of prompt*
