# LEGACY ALIAS: prefer .\scripts\trading\eod_market_context_refresh.ps1
# This script is a subset wrapper (optional positions, OHLCV/ex-VIN flags only).
# Canonical EOD driver: eod_market_context_refresh.ps1
# Usage:
#   .\scripts\trading\daily_eod_operator.ps1 -RefreshOhlcv -RebuildExVin
param(
    [string]$Date = "",
    [switch]$SkipPositions,
    [switch]$RefreshOhlcv,
    [switch]$RebuildExVin,
    [switch]$SkipDistributionRisk,
    [switch]$SkipScan,
    [switch]$SkipDailyScan,
    [switch]$SkipCloudReport,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $RepoRoot
$py = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

if (-not $Date) { $Date = (Get-Date).ToString("yyyy-MM-dd") }

$LensJson = Join-Path $RepoRoot "data\research\market_risk\distribution_risk_latest.json"
$ScanPath = Join-Path $RepoRoot "data\research\portfolio_optimization\missing_work\phase36_daily_scan_latest.csv"
$CloudHtml = Join-Path $RepoRoot "data\research\reports\cloud_daily_report_latest.html"
$DailyScanMd = Join-Path $RepoRoot "data\decision\daily_scan.md"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " LEGACY ALIAS — prefer eod_market_context_refresh.ps1" -ForegroundColor Yellow
Write-Host " DAILY EOD — DECISION SUPPORT ONLY" -ForegroundColor Cyan
Write-Host " Distribution risk = context only" -ForegroundColor Cyan
Write-Host " final_action SSOT = phase36 scan" -ForegroundColor Cyan
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
    if (-not $SkipPositions) {
        Invoke-Step "derive-current (optional)" {
            & $py -m src.review.cli derive-current
        }
    }

    if ($RefreshOhlcv) {
        Invoke-Step "append FireAnt OHLCV" {
            & $py scripts/append_fireant_ohlcv_to_data_stocks.py --data-stocks --minervini-raw --end $Date
        }
    }

    if ($RebuildExVin) {
        Invoke-Step "rebuild ex-VIN series" {
            & $py scripts/research/vnindex_low_dist_ex_vin.py --end $Date
        }
    }

    if (-not $SkipDistributionRisk) {
        # Freshness guard for v1.3 breadth: update ta_ohlcv_panel first (best-effort).
        Write-Host ">> v1.3 panel freshness guard: refresh ta_ohlcv_panel to $Date (best-effort)" -ForegroundColor Cyan
        try {
            & $py scripts/update_ohlcv_panel_incremental.py --end $Date
        } catch {
            Write-Host "WARN: ta_ohlcv_panel refresh failed (continuing with existing panel): $($_.Exception.Message)" -ForegroundColor Yellow
        }

        Invoke-Step "distribution-risk v1.3 (market context only; breadth freshness guarded)" {
            & $py scripts/research/run_distribution_risk_v13.py --start 2012-01-01 --as-of $Date
        }
    }

    if (-not $SkipScan) {
        Invoke-Step "phase36 scan (signal SSOT)" {
            & $py pp_backtest/portfolio_optimization_final_steps.py --step scan
        }
    }

    if (-not $SkipDailyScan) {
        Invoke-Step "daily_scan_report.py" {
            & $py scripts/reporting/daily_scan_report.py
        }
    }

    if (-not $SkipCloudReport) {
        Invoke-Step "cloud-daily-report --mode eod" {
            & $py -m src.trading.cli cloud-daily-report --mode eod
        }
    }

    Write-Host ""
    Write-Host "=== Artifacts ===" -ForegroundColor Green
    if (-not $SkipDistributionRisk) { Write-Host "  $LensJson" }
    if (-not $SkipScan) { Write-Host "  $ScanPath" }
    if (-not $SkipDailyScan) { Write-Host "  $DailyScanMd" }
    if (-not $SkipCloudReport) { Write-Host "  $CloudHtml" }
    Write-Host ""
    Write-Host "Lens does not override final_action. Real capital: NO-GO." -ForegroundColor Green
    exit 0
}
catch {
    Write-Host "FAILED: $_" -ForegroundColor Red
    exit 1
}
