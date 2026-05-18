# ChatGPT Troubleshooting Prompt — Daily Paper-Live 16:30 Run Failed

Copy everything below the line. Attach **`vn_paper_live_troubleshoot_1630.zip`** (repo root).

---

You are a senior quant systems / Windows automation engineer helping troubleshoot a **failed scheduled daily paper-trading run** in repo **VN Agent System** (Vietnam equities, paper only).

## Incident summary (FACTS)

| Item | Value |
|------|--------|
| Calendar date | **2026-05-18** (Monday) |
| Scheduled task | `VN_Agent_Daily_Paper_Live_1630` |
| Schedule | Mon–Fri **16:30** local |
| Script | `scripts/trading/daily_paper_live_full_run.ps1` |
| Task last run | **18-May-2026 16:30** |
| Task last result | **1** (exit code 1 — failure) |
| Next run | 19-May-2026 16:30 |
| Older task | `VN_Agent_Daily_Paper_Live_1600` also ran 16:00, Last Result **1** |

**Expected outputs after success (missing for 2026-05-18):**

- `data/trading/live/accounts/daily_operator_pack_20260518.md`
- `data/trading/live/accounts/compare_20260518.md`
- `data/trading/live/accounts/valid_paper_day_20260518.json`
- `data/trading/live/accounts/logs/paper_live_full_20260518_*.log`
- `data/trading/live/accounts/paper_live_report_20260518.md` (written on early STOP)

**Outputs that DO exist (manual run, different date):**

- `data/trading/live/accounts/daily_operator_pack_20260515.md`
- `data/trading/live/accounts/valid_paper_day_20260515.json`
- `data/trading/live/accounts/compare_20260515.md`

**Manual run that worked (reference):**

```powershell
cd "C:\Users\LOLII\Documents\V\0. VN Agent System"
python pp_backtest/portfolio_optimization_final_steps.py --step scan   # OK, 94 rows
python -m src.trading.cli resolve-scan --date 2026-05-18               # FAIL blocked
python -m src.trading.cli paper-accounts run-all --date 2026-05-15 `
  --scan-path data/research/portfolio_optimization/missing_work/phase36_daily_scan_sample.csv `
  --include-s3-shadow --allow-sample                                      # OK
```

## Non-negotiables (do not suggest changing without explicit approval)

- **Real capital: NO-GO** | **DSE/DNSE live: NO-GO** | **live_auto: NO-GO**
- Paper only; OMS consumes scan `final_action` only; no strategy recompute in OMS
- Do not modify `data/paper_trade/` (research legacy)
- Do not enable live broker orders

## Architecture (read first in zip)

1. `docs/trading/PAPER_TRADING_OPERATIONS_GUIDE.md`
2. `docs/trading/DAILY_PAPER_OPERATOR_PROMPT.md`
3. `scripts/trading/daily_paper_live_full_run.ps1`
4. `scripts/trading/register_daily_paper_live_task.ps1`
5. `src/trading/live/scan_resolver.py`
6. `config/live_trading.yaml` — note `paths.scan_csv_path` fallback
7. `config/paper_accounts.yaml`

## Paper accounts (5)

| Account | NAV | Role |
|---------|-----|------|
| A3_DSE_PILOT_PAPER_SMALL | 30M | DSE pilot mimic |
| A3_PROD_PAPER_5B | 5B | Reference |
| A3_SCALE_PAPER_10B | 10B | Scale check |
| A3_SCALE_PAPER_20B | 20B | Liquidity stress |
| S3_MAX60_SHADOW_PAPER | 0 | Shadow only |

## Suspected root causes (verify with evidence)

### A. Scan resolver / config mismatch

- `config/live_trading.yaml` fallback: `phase34_daily_scan_sample.csv` (test fixture name)
- `resolve-scan --date 2026-05-18` without `--scan-path` → **blocked=True**, exit code **1**
- Production Phase36 output file is always named **`phase36_daily_scan_sample.csv`** (contains word `sample` but is real EOD output)
- `allow_sample_scan: false` in config → resolver blocks any path with `sample` in filename unless `--allow-sample` on **run-all** (not on resolve-scan CLI)

### B. Stale scan date

- After `--step scan`, `phase36_daily_scan_sample.csv` contained **`as_of_date` = 2026-05-15 only** (not 2026-05-18)
- Resolver marks **stale** when `--date` calendar day not in scan file
- Script stops at step 2 with **exit 2** if stale (see `daily_paper_live_full_run.ps1` lines 104–120)

### C. PowerShell script ordering bug (hypothesis)

- Script auto-enables `$AllowSample` for phase36 path **after** `resolve-scan` (lines 95–102)
- But if `resolve-scan` exits **1** when blocked (lines 57–69), script never reaches phase36 AllowSample logic
- If resolve returns blocked + exit 1 for phase34 config path, scheduled run dies immediately

### D. Scheduled task environment

- Task runs: `powershell.exe -File daily_paper_live_full_run.ps1` with WorkingDirectory = repo root
- **No log file** found under `data/trading/live/accounts/logs/` for 20260518 → script may have failed before logging, wrong working directory, or permissions
- Task may run when user logged off (check "Run only when user is logged on" vs battery settings)
- Last Result **1** = script exit 1 (resolve-scan failure path) not necessarily PowerShell crash

### E. Missing operator artifacts on STOP

- Early STOP should write `paper_live_report_YYYYMMDD.md` but none found for 20260518
- Suggests failure before report write, or different repo path when task runs, or commit not deployed on machine that ran task

## Commands to reproduce (operator machine)

```powershell
cd "C:\Users\LOLII\Documents\V\0. VN Agent System"

# 1) Scan
.\.venv\Scripts\python.exe pp_backtest/portfolio_optimization_final_steps.py --step scan

# 2) Resolve (calendar today)
.\.venv\Scripts\python.exe -m src.trading.cli resolve-scan --date (Get-Date -Format yyyy-MM-dd)

# 3) Inspect scan dates in file
.\.venv\Scripts\python.exe -c "import pandas as pd; df=pd.read_csv('data/research/portfolio_optimization/missing_work/phase36_daily_scan_sample.csv'); print(sorted(df['as_of_date'].astype(str).unique())[-5:])"

# 4) Full script (verbose)
.\scripts\trading\daily_paper_live_full_run.ps1 -AllowSample

# 5) Task status
schtasks /Query /TN "VN_Agent_Daily_Paper_Live_1630" /V /FO LIST
```

## Your deliverables

1. **Root cause ranking** — P0/P1/P2 with file:line evidence for the 16:30 failure
2. **Timeline** — what the script should do step-by-step vs what likely happened
3. **Fix plan** — minimal patches only (no strategy changes), e.g.:
   - Update `live_trading.yaml` `scan_csv_path` → phase36 production file
   - Treat `phase36_daily_scan_sample.csv` as production (rename or resolver allowlist)
   - Pass `--allow-sample` inside `daily_paper_live_full_run.ps1` before resolve OR fix resolve-scan exit ordering
   - Use **scan asof date** vs calendar date when EOD panel lags (Mon run with Fri scan)
   - Ensure STOP paths always write log + `paper_live_report_YYYYMMDD.md`
   - Task Scheduler: user logon, highest privileges, working directory, failure audit
4. **Exact config / script diffs** — propose concrete YAML + PS1 + optional Python changes
5. **Validation checklist** — commands to confirm next 16:30 run succeeds
6. **Operator runbook** — what to do each trading day until automated run is green

## Questions you must answer

- Why Last Result = 1 but no `paper_live_report_20260518.md` and no log file?
- Should `--date` be calendar today or latest `as_of_date` in scan CSV?
- Is blocking `phase36_daily_scan_sample.csv` a false positive? Best fix?
- Should scheduled task pass `-AllowSample` by default for production phase36?
- Is panel/scan pipeline failing to update Monday EOD (only 2026-05-15 in file)?

## Do NOT recommend

- Enabling real capital, DSE/DNSE live, or `live_auto`
- Changing A3 strategy logic, TP1/trail, or production gates
- Writing to `data/paper_trade/`
- Ignoring stale scan and running paper anyway without operator disclosure

## Verdict template (fill in)

- **Primary failure:** [scan resolve / stale date / task env / script bug / other]
- **Can paper run tomorrow at 16:30 without code change?** [yes/no + conditions]
- **Minimal patch set:** [list files]
- **Confidence:** [high/medium/low]

---

*End of prompt*
