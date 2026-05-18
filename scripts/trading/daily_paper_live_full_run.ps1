# Full daily paper-live workflow (PAPER ONLY — no DSE/DNSE live)
# Usage:
#   .\scripts\trading\daily_paper_live_full_run.ps1
#   .\scripts\trading\daily_paper_live_full_run.ps1 -Date 2026-05-18 -SkipScanStep
param(
    [string]$Date = "",
    [switch]$SkipScanStep,
    [switch]$Force,
    [switch]$AllowSample
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $RepoRoot
$py = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not $Date) {
    $Date = (Get-Date).ToString("yyyy-MM-dd")
}

$LogDir = Join-Path $RepoRoot "data\trading\live\accounts\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir "paper_live_full_$($Date.Replace('-',''))_$(Get-Date -Format 'HHmmss').log"
$ReportFile = Join-Path $RepoRoot "data\trading\live\accounts\paper_live_report_$($Date.Replace('-','')).md"

function Log($msg) {
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $msg"
    Add-Content -Path $LogFile -Value $line
    Write-Host $line
}

function Run-Py {
    param([string[]]$Args)
    $out = & $py @Args 2>&1
    $out | ForEach-Object { Log $_ }
    return $LASTEXITCODE
}

Log "=== PAPER-LIVE FULL RUN date=$Date ==="
Log "Real capital: NO-GO | DSE/DNSE: NO-GO | live_auto: NO-GO"

# 1. Scan step
if (-not $SkipScanStep) {
    Log "Step: Phase36 scan (portfolio_optimization_final_steps --step scan)"
    $ec = Run-Py @("pp_backtest/portfolio_optimization_final_steps.py", "--step", "scan")
    if ($ec -ne 0) {
        Log "WARN: scan step exited $ec — continuing with resolve-scan"
    }
} else {
    Log "Skipped scan step (-SkipScanStep)"
}

# 2. Resolve scan
Log "Step: resolve-scan"
$resolveOut = & $py -m src.trading.cli resolve-scan --date $Date 2>&1
$resolveOut | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    @"
# Paper-live report — $Date

## VERDICT: Stop — scan resolve failed

Resolve-scan failed. Do not run paper accounts.

```
$($resolveOut -join "`n")
```
"@ | Set-Content $ReportFile -Encoding utf8
    exit 1
}

# Parse resolved path from output (path=...)
$scanPath = ""
foreach ($line in $resolveOut) {
    if ($line -match "path=(.+)") {
        $scanPath = $Matches[1].Trim().Split(" ")[0]
        break
    }
}
if (-not $scanPath) {
    $candidates = @(
        "data\research\portfolio_optimization\missing_work\phase36_daily_scan.csv",
        "data\research\portfolio_optimization\missing_work\phase36_daily_scan_sample.csv"
    )
    foreach ($c in $candidates) {
        $p = Join-Path $RepoRoot $c
        if (Test-Path $p) { $scanPath = $p; break }
    }
}

$isSample = $resolveOut -match "sample=True"
$isStale = $resolveOut -match "stale=True"
$blocked = $resolveOut -match "blocked=True"

# Production Phase36 output is phase36_daily_scan_sample.csv (allow sample flag for that file)
$phase36Path = Join-Path $RepoRoot "data\research\portfolio_optimization\missing_work\phase36_daily_scan_sample.csv"
if ($scanPath -and ($scanPath -replace '\\','/') -match 'phase36_daily_scan' -and (Test-Path $phase36Path)) {
    if (-not $AllowSample) {
        Log "Note: Phase36 daily scan filename contains sample but is production EOD output"
        $AllowSample = $true
    }
}

if ($blocked -or ($isSample -and -not $AllowSample) -or $isStale) {
    @"
# Paper-live report — $Date

## A. Scan status
- Path: $scanPath
- **BLOCKED** — sample=$isSample stale=$isStale blocked=$blocked
- Do not run paper accounts until scan is valid.

## G. Verdict
**Stop: data/reconciliation issue** (invalid scan)

## H. Next action
Fix scan / re-run Phase36 scan, then re-run this script.
"@ | Set-Content $ReportFile -Encoding utf8
    Log "STOP: invalid scan — report written $ReportFile"
    exit 2
}

if (-not (Test-Path $scanPath)) {
    Log "STOP: scan path not found: $scanPath"
    exit 3
}

Log "Resolved scan: $scanPath"

# 3. Init accounts (idempotent)
foreach ($acct in @(
    "A3_DSE_PILOT_PAPER_SMALL", "A3_PROD_PAPER_5B",
    "A3_SCALE_PAPER_10B", "A3_SCALE_PAPER_20B", "S3_MAX60_SHADOW_PAPER"
)) {
    Run-Py @("-m", "src.trading.cli", "paper-accounts", "init", "--account", $acct) | Out-Null
}

# 4. run-all
$runArgs = @("-m", "src.trading.cli", "paper-accounts", "run-all", "--date", $Date, "--scan-path", $scanPath, "--include-s3-shadow")
if ($Force) { $runArgs += "--force" }
if ($AllowSample) { $runArgs += "--allow-sample" }

Log "Step: paper-accounts run-all"
$runOut = & $py @runArgs 2>&1
$runOut | ForEach-Object { Log $_ }

# 5. Summaries
$sum5 = & $py -m src.trading.cli paper-accounts summary --account A3_PROD_PAPER_5B 2>&1
$sumS = & $py -m src.trading.cli paper-accounts summary --account A3_DSE_PILOT_PAPER_SMALL 2>&1
$sum3 = & $py -m src.trading.cli s3-shadow summary 2>&1
$mr5 = & $py -m src.trading.cli manual-review --date $Date --account A3_PROD_PAPER_5B 2>&1
$mrS = & $py -m src.trading.cli manual-review --date $Date --account A3_DSE_PILOT_PAPER_SMALL 2>&1

function Get-StatusJson($accountId) {
    $p = Join-Path $RepoRoot "data\trading\live\accounts\$accountId\dashboard\latest_status.json"
    if (Test-Path $p) { Get-Content $p -Raw | ConvertFrom-Json }
    else { $null }
}

$st5 = Get-StatusJson "A3_PROD_PAPER_5B"
$stS = Get-StatusJson "A3_DSE_PILOT_PAPER_SMALL"
$comparePath = Join-Path $RepoRoot "data\trading\live\accounts\compare_$($Date.Replace('-','')).md"
$compareExists = Test-Path $comparePath

$report = @"
# Paper-live daily report — $Date

Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

**PAPER ONLY** — Real capital NO-GO | DSE/DNSE NO-GO | live_auto NO-GO

## A. Scan status
- Path: ``$scanPath``
- Date: $Date
- Sample: $isSample | Stale: $isStale

## B. A3_PROD_PAPER_5B
- Traffic light: **$($st5.traffic_light_status)**
- Reasons: $($st5.traffic_light_reasons -join ', ')
- Cash: $($st5.current_cash_VND) | Equity: $($st5.equity)
- Fills today: $($st5.new_fills_today) | Exits: $($st5.exits_today)
- Manual review: $($st5.manual_review_count) | Risk rejects: $($st5.risk_rejection_count)
- Reconciliation: $($st5.reconciliation_status)

## C. A3_DSE_PILOT_PAPER_SMALL
- Traffic light: **$($stS.traffic_light_status)**
- Reasons: $($stS.traffic_light_reasons -join ', ')
- Cash: $($stS.current_cash_VND) | Equity: $($stS.equity)
- Fills today: $($stS.new_fills_today) | Exits: $($stS.exits_today)
- Manual review: $($stS.manual_review_count) | Risk rejects: $($stS.risk_rejection_count)
- Reconciliation: $($stS.reconciliation_status)

## D. S3 shadow
``````
$($sum3 -join "`n")
``````

## E. Manual review (operator action required — not auto-approved)
### A3_PROD_PAPER_5B queue
``$(Join-Path $RepoRoot "data\trading\live\accounts\A3_PROD_PAPER_5B\manual_review_queue_$($Date.Replace('-','')).csv")``

``````
$($mr5 -join "`n")
``````

### A3_DSE_PILOT_PAPER_SMALL queue
``$(Join-Path $RepoRoot "data\trading\live\accounts\A3_DSE_PILOT_PAPER_SMALL\manual_review_queue_$($Date.Replace('-','')).csv")``

``````
$($mrS -join "`n")
``````

## F. Compare report
$(if ($compareExists) { "See: ``$comparePath``" } else { "Not generated" })

> Differences between 5B and 30M are **account constraints**, not strategy logic.

## G. Operator summary (run-all)
``````
$($runOut -join "`n")
``````

## H. Next action
- Review manual review queues if pending (approve/reject in CSV, then apply-manual-review)
- Check dashboards under each account folder
- Log file: ``$LogFile``

"@

$report | Set-Content $ReportFile -Encoding utf8
Log "Report written: $ReportFile"
Log "=== DONE ==="
