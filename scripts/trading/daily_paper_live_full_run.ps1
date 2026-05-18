# Full daily paper-live workflow (PAPER ONLY - no DSE/DNSE live)
# Usage:
#   .\scripts\trading\daily_paper_live_full_run.ps1
#   .\scripts\trading\daily_paper_live_full_run.ps1 -Date 2026-05-18
#   .\scripts\trading\daily_paper_live_full_run.ps1 -Date 2026-05-18 -UseLatestScanDate
param(
    [string]$Date = "",
    [switch]$SkipScanStep,
    [switch]$Force,
    [switch]$AllowSample,
    [switch]$UseLatestScanDate
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

function Write-StopReport {
    param(
        [string]$Date,
        [string]$Reason,
        [string]$Details,
        [int]$ExitCode = 1
    )
    $body = @"
# Paper-live report - $Date

Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

**PAPER ONLY** - Real capital NO-GO | DSE/DNSE NO-GO | live_auto NO-GO

## VERDICT: Stop - $Reason

$Details

## Next action
- Check log: ``$LogFile``
- Fix scan or re-run Phase36 scan, then re-run this script.
- Manual backfill only with ``-UseLatestScanDate`` (explicit operator override).

Exit code: $ExitCode
"@
    $body | Set-Content $ReportFile -Encoding utf8
    Log "STOP report written: $ReportFile (exit $ExitCode)"
}

try {
    Log "=== PAPER-LIVE FULL RUN bootstrap ==="
    Log "script=$PSCommandPath"
    Log "repo_root=$RepoRoot"
    Log "cwd=$(Get-Location)"
    Log "powershell=$($PSVersionTable.PSVersion)"
    Log "user=$env:USERNAME"
    Log "python=$py"
    Log "date=$Date AllowSample=$AllowSample UseLatestScanDate=$UseLatestScanDate"

    if (-not (Test-Path $py)) {
        Write-StopReport -Date $Date -Reason "Python not found" -Details "Missing venv: $py" -ExitCode 9
        exit 9
    }

    function Run-Py {
        param([string[]]$Args)
        $out = & $py @Args 2>&1
        $out | ForEach-Object { Log $_ }
        return $LASTEXITCODE
    }

    # 1. Scan step
    if (-not $SkipScanStep) {
        Log "Step: Phase36 scan (portfolio_optimization_final_steps --step scan)"
        $ec = Run-Py @("pp_backtest/portfolio_optimization_final_steps.py", "--step", "scan")
        if ($ec -ne 0) {
            Log "WARN: scan step exited $ec - continuing with resolve-scan"
        }
    } else {
        Log "Skipped scan step (-SkipScanStep)"
    }

    # 2. Pick Phase36 scan path BEFORE resolve-scan
    $phase36Latest = Join-Path $RepoRoot "data\research\portfolio_optimization\missing_work\phase36_daily_scan_latest.csv"
    $phase36Legacy = Join-Path $RepoRoot "data\research\portfolio_optimization\missing_work\phase36_daily_scan_sample.csv"
    $preferredScan = $null
    if (Test-Path $phase36Latest) {
        $preferredScan = $phase36Latest
        Log "Using Phase36 latest scan: $preferredScan"
    } elseif (Test-Path $phase36Legacy) {
        $preferredScan = $phase36Legacy
        if (-not $AllowSample) { $AllowSample = $true }
        Log "Using legacy Phase36 sample-named production scan with AllowSample=true: $preferredScan"
    } else {
        Write-StopReport -Date $Date -Reason "No Phase36 scan file" -Details "Missing phase36_daily_scan_latest.csv and phase36_daily_scan_sample.csv" -ExitCode 10
        exit 10
    }

    $resolveArgs = @("-m", "src.trading.cli", "resolve-scan", "--date", $Date, "--scan-path", $preferredScan)
    if ($AllowSample) { $resolveArgs += "--allow-sample" }
    if ($UseLatestScanDate) { $resolveArgs += "--use-latest-scan-date" }

    Log "Step: resolve-scan $($resolveArgs -join ' ')"
    $resolveOut = & $py @resolveArgs 2>&1
    $resolveOut | ForEach-Object { Log $_ }

    $scanPath = ""
    $effectiveDate = $Date
    $isSample = $false
    $isStale = $false
    $blocked = $false
    $scanDate = ""
    $resolveLine = ($resolveOut | Where-Object { $_ -match '^path=' }) | Select-Object -Last 1
    if ($resolveLine) {
        if ($resolveLine -match 'path=(.+?)\s+source=') { $scanPath = $Matches[1].Trim() }
        if ($resolveLine -match 'effective_date=(\S+)') { $effectiveDate = $Matches[1] }
        if ($resolveLine -match 'scan_date=(\S+)') { $scanDate = $Matches[1] }
        if ($resolveLine -match 'sample=True') { $isSample = $true }
        if ($resolveLine -match 'stale=True') { $isStale = $true }
        if ($resolveLine -match 'blocked=True') { $blocked = $true }
    }

    if ($LASTEXITCODE -ne 0 -and -not $blocked) {
        Write-StopReport -Date $Date -Reason "scan resolve failed" -Details ($resolveOut -join "`n") -ExitCode 1
        exit 1
    }

    if ($blocked -or ($isStale -and -not $UseLatestScanDate)) {
        $staleNote = if ($isStale) { "Calendar date $Date differs from scan as_of_date (latest in file: $scanDate). Scheduled run stops. Use -UseLatestScanDate for explicit backfill only." } else { "" }
        Write-StopReport -Date $Date -Reason "invalid or stale scan" -Details @"
- Path: $scanPath
- sample=$isSample stale=$isStale blocked=$blocked
- scan_date=$scanDate effective_date=$effectiveDate
$staleNote
"@ -ExitCode 2
        exit 2
    }

    if (-not $scanPath -or -not (Test-Path $scanPath)) {
        Write-StopReport -Date $Date -Reason "scan path missing" -Details "Resolved path not found: $scanPath" -ExitCode 3
        exit 3
    }

    if ($UseLatestScanDate -and $effectiveDate -ne $Date) {
        Log "Operator override: outputs will use effective_date=$effectiveDate (requested $Date)"
        $Date = $effectiveDate
        $ReportFile = Join-Path $RepoRoot "data\trading\live\accounts\paper_live_report_$($Date.Replace('-','')).md"
    }

    Log "Resolved scan: $scanPath (effective_date=$Date)"

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
    if ($UseLatestScanDate) { $runArgs += "--use-latest-scan-date" }

    Log "Step: paper-accounts run-all"
    $runOut = & $py @runArgs 2>&1
    $runOut | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Write-StopReport -Date $Date -Reason "paper-accounts run-all failed" -Details ($runOut -join "`n") -ExitCode 4
        exit 4
    }

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
    $packPath = Join-Path $RepoRoot "data\trading\live\accounts\daily_operator_pack_$($Date.Replace('-','')).md"
    $validPath = Join-Path $RepoRoot "data\trading\live\accounts\valid_paper_day_$($Date.Replace('-','')).json"

    $overrideNote = ""
    if ($UseLatestScanDate) {
        $overrideNote = "`n`n> Calendar date differed from scan as_of_date; operator override (-UseLatestScanDate) used.`n"
    }

    $report = @"
# Paper-live daily report - $Date

Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

**PAPER ONLY** - Real capital NO-GO | DSE/DNSE NO-GO | live_auto NO-GO
$overrideNote

## A. Scan status
- Path: ``$scanPath``
- Date: $Date
- Sample: $isSample | Stale: $isStale | scan_date: $scanDate

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

## E. Manual review
### A3_PROD_PAPER_5B
``````
$($mr5 -join "`n")
``````

### A3_DSE_PILOT_PAPER_SMALL
``````
$($mrS -join "`n")
``````

## F. Artifacts
- Compare: $(if ($compareExists) { "``$comparePath``" } else { "not generated" })
- Operator pack: $(if (Test-Path $packPath) { "``$packPath``" } else { "not generated" })
- Valid paper day: $(if (Test-Path $validPath) { "``$validPath``" } else { "not generated" })

## G. Operator summary (run-all)
``````
$($runOut -join "`n")
``````

## H. Next action
- Review manual review queues if pending
- Log file: ``$LogFile``

"@

    $report | Set-Content $ReportFile -Encoding utf8
    Log "Report written: $ReportFile"
    Log "=== DONE ==="
}
catch {
    $err = $_.Exception.Message
    Log "FATAL: $err"
    Log $_.ScriptStackTrace
    Write-StopReport -Date $Date -Reason "unhandled exception" -Details $err -ExitCode 99
    exit 99
}
