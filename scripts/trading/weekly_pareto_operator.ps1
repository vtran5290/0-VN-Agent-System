# Weekly Pareto operator — DECISION SUPPORT ONLY — NO ORDERS
# Usage:
#   .\scripts\trading\weekly_pareto_operator.ps1
#   .\scripts\trading\weekly_pareto_operator.ps1 -Date 2026-05-17 -Tickers "STB,HDB,MSB" -OpenReport
param(
    [string]$Date = "",
    [string]$Tickers = "",
    [switch]$SkipTechStatus,
    [switch]$SkipPositions,
    [switch]$SkipScan,
    [switch]$SkipOrderIntent,
    [switch]$RefreshMarketContext,
    [switch]$OpenReport,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $RepoRoot
$py = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

if (-not $Date) { $Date = (Get-Date).ToString("yyyy-MM-dd") }

$PositionsPath = Join-Path $RepoRoot "data\raw\current_positions_derived.json"
$ScanPath = Join-Path $RepoRoot "data\research\portfolio_optimization\missing_work\phase36_daily_scan_latest.csv"
$WeeklyJson = Join-Path $RepoRoot "data\processed\weekly_report.json"
$WeeklyHtml = Join-Path $RepoRoot "reports\latest\index.html"
$OrderIntentPath = Join-Path $RepoRoot "data\trading\order_intent\order_intent_$Date.csv"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " DECISION SUPPORT ONLY — NO ORDERS" -ForegroundColor Cyan
Write-Host " No live-workflow. No broker. No live_auto." -ForegroundColor Cyan
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
        Invoke-Step "derive-current (positions SSOT)" {
            & $py -m src.review.cli derive-current
        }
    } else {
        Write-Host ">> derive-current skipped"
    }

    if ($RefreshMarketContext) {
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
    } else {
        Write-Host ">> distribution-risk skipped (use -RefreshMarketContext if lens stale; daily EOD: eod_market_context_refresh.ps1)"
    }

    if (-not $SkipScan) {
        Invoke-Step "phase36 scan (--step scan)" {
            & $py pp_backtest/portfolio_optimization_final_steps.py --step scan
        }
    } else {
        Write-Host ">> scan step skipped"
    }

    if (-not $SkipTechStatus -and $Tickers) {
        Invoke-Step "update_tech_status" {
            & $py scripts/update_tech_status.py --asof $Date --tickers $Tickers
        }
    } elseif (-not $SkipTechStatus) {
        Write-Host ">> update_tech_status skipped (pass -Tickers)"
    }

    Invoke-Step "run_weekly_update" {
        & $py -m scripts.ingest.run_weekly_update
    }

    Invoke-Step "render_weekly_report" {
        & $py -m scripts.reporting.render_weekly_report
    }

    if (-not $SkipOrderIntent) {
        Invoke-Step "generate-order-intent (dry run)" {
            $oiDir = Join-Path $RepoRoot "data\trading\order_intent"
            New-Item -ItemType Directory -Force -Path $oiDir | Out-Null
            & $py -m src.trading.cli generate-order-intent `
                --date $Date `
                --scan-path $ScanPath `
                --positions-path $PositionsPath `
                --output $OrderIntentPath `
                --max-stale-days 7
            # exit 2 = wrote with risk flags — non-fatal for weekly ops
            if ($LASTEXITCODE -eq 2) {
                Write-Host "   WARN: order-intent has risk-flagged rows (review required)" -ForegroundColor Yellow
                $global:LASTEXITCODE = 0
            }
            if (Test-Path $OrderIntentPath) {
                & $py -m src.trading.cli validate-order-intent --path $OrderIntentPath
                if ($LASTEXITCODE -ne 0) {
                    throw "Order-intent validation failed (placeholder date or order_sent != NO)."
                }
            }
        }
    }

    # Critical output checks
    $missing = @()
    if (-not $DryRun) {
        if (-not $SkipPositions -and -not (Test-Path $PositionsPath)) { $missing += $PositionsPath }
        if (-not $SkipScan -and -not (Test-Path $ScanPath)) { $missing += $ScanPath }
        if (-not (Test-Path $WeeklyJson)) { $missing += $WeeklyJson }
        if (-not (Test-Path $WeeklyHtml)) { $missing += $WeeklyHtml }
        if (-not $SkipOrderIntent -and -not (Test-Path $OrderIntentPath)) { $missing += $OrderIntentPath }
    }

    if ($missing.Count -gt 0) {
        Write-Host "CRITICAL: missing outputs:" -ForegroundColor Red
        $missing | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
        exit 1
    }

    $LensJson = Join-Path $RepoRoot "data\research\market_risk\distribution_risk_latest.json"
    if ((Test-Path $LensJson) -and -not $RefreshMarketContext) {
        try {
            $lens = Get-Content $LensJson -Raw | ConvertFrom-Json
            $lensDate = $lens.as_of_date
            if (-not $lensDate) { $lensDate = $lens.requested_as_of_date }
            if ($lensDate) {
                $age = ([datetime]$Date - [datetime]$lensDate).Days
                if ($age -gt 7) {
                    Write-Host "WARN: Distribution Risk lens stale ($lensDate, ${age}d old). Run eod_market_context_refresh.ps1 or -RefreshMarketContext." -ForegroundColor Yellow
                }
            }
            if ($lens.report_status -eq "NEEDS_REVIEW") {
                Write-Host "WARN: Distribution Risk NEEDS_REVIEW — stale index view; probabilities may be caveated." -ForegroundColor Yellow
            }
        } catch {
            Write-Host "WARN: could not read distribution_risk_latest.json for staleness check." -ForegroundColor Yellow
        }
    }

    Write-Host ""
    Write-Host "=== Artifacts ===" -ForegroundColor Green
    Write-Host "  $PositionsPath"
    Write-Host "  $ScanPath"
    Write-Host "  $WeeklyJson"
    Write-Host "  $WeeklyHtml"
    if (-not $SkipOrderIntent) { Write-Host "  $OrderIntentPath" }
    Write-Host ""
    Write-Host "Order-intent dry run sends no orders. Real capital: NO-GO." -ForegroundColor Green

    if ($OpenReport -and (Test-Path $WeeklyHtml)) {
        Start-Process $WeeklyHtml
    }

    exit 0
}
catch {
    Write-Host "FAILED: $_" -ForegroundColor Red
    exit 1
}
