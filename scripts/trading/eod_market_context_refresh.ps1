# EOD market context + decision support - NO ORDERS
# Refresh OHLCV, ex-VIN, distribution-risk lens, phase36 scan, daily packets.
# Usage:
#   .\scripts\trading\eod_market_context_refresh.ps1
#   .\scripts\trading\eod_market_context_refresh.ps1 -Date 2026-05-21 -OpenCloudReport
param(
    [string]$Date = "",
    [switch]$SkipFireAntAppend,
    [switch]$SkipExVinRebuild,
    [switch]$SkipDistributionRisk,
    [switch]$SkipPhase36Scan,
    [switch]$SkipDailyScan,
    [switch]$SkipCloudReport,
    [switch]$OpenCloudReport,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $RepoRoot
$py = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

if (-not $Date) { $Date = (Get-Date).ToString("yyyy-MM-dd") }

$LensJson = Join-Path $RepoRoot "data\research\market_risk\distribution_risk_latest.json"
$LensHtml = Join-Path $RepoRoot "data\research\market_risk\distribution_risk_latest.html"
$ScanPath = Join-Path $RepoRoot "data\research\portfolio_optimization\missing_work\phase36_daily_scan_latest.csv"
$DailyScanMd = Join-Path $RepoRoot "data\decision\daily_scan.md"
$CloudHtml = Join-Path $RepoRoot "data\research\reports\cloud_daily_report_latest.html"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " EOD MARKET CONTEXT + DECISION SUPPORT ONLY - NO ORDERS" -ForegroundColor Cyan
Write-Host " Distribution Risk = context only (not final_action)" -ForegroundColor Cyan
Write-Host " No live-workflow. No broker. No live_auto. No intraday OMS." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

function Invoke-Step($label, [scriptblock]$block) {
    Write-Host ">> $label"
    if ($DryRun) {
        Write-Host "   [DryRun] skipped"
        return
    }
    & $block
    if ($LASTEXITCODE -ne 0) {
        throw "Step failed ($label): exit $LASTEXITCODE"
    }
}

try {
    if (-not $SkipFireAntAppend) {
        Invoke-Step "FireAnt OHLCV append" {
            & $py scripts/append_fireant_ohlcv_to_data_stocks.py --data-stocks --minervini-raw --end $Date
        }
    } else {
        Write-Host ">> FireAnt OHLCV append skipped"
    }

    if (-not $SkipExVinRebuild) {
        Invoke-Step "ex-VIN series rebuild" {
            & $py scripts/research/vnindex_low_dist_ex_vin.py --end $Date
        }
    } else {
        Write-Host ">> ex-VIN rebuild skipped"
    }

    if (-not $SkipDistributionRisk) {
        Invoke-Step "distribution-risk (market context only)" {
            & $py -m src.trading.cli distribution-risk --start 2012-01-01 --as-of latest
        }
    } else {
        Write-Host ">> distribution-risk skipped"
    }

    if (-not $SkipPhase36Scan) {
        Invoke-Step "phase36 scan (signal SSOT)" {
            & $py pp_backtest/portfolio_optimization_final_steps.py --step scan
        }
    } else {
        Write-Host ">> phase36 scan skipped"
    }

    if (-not $SkipDailyScan) {
        Invoke-Step "daily_scan_report.py" {
            & $py scripts/reporting/daily_scan_report.py
        }
    } else {
        Write-Host ">> daily_scan_report skipped"
    }

    if (-not $SkipCloudReport) {
        Invoke-Step "cloud-daily-report --mode eod" {
            & $py -m src.trading.cli cloud-daily-report --mode eod
        }
    } else {
        Write-Host ">> cloud-daily-report skipped"
    }

    Write-Host ""
    Write-Host "=== Artifacts ===" -ForegroundColor Green
    if (-not $SkipDistributionRisk) {
        Write-Host "  $LensJson"
        Write-Host "  $LensHtml"
    }
    if (-not $SkipDailyScan) { Write-Host "  $DailyScanMd" }
    if (-not $SkipCloudReport) { Write-Host "  $CloudHtml" }
    if (-not $SkipPhase36Scan) { Write-Host "  $ScanPath" }
    Write-Host ""
    Write-Host "Distribution Risk Lens does not change final_action. Real capital: NO-GO." -ForegroundColor Green

    if ($OpenCloudReport -and (Test-Path $CloudHtml)) {
        Start-Process $CloudHtml
    }

    exit 0
}
catch {
    Write-Host "FAILED: $_" -ForegroundColor Red
    exit 1
}
