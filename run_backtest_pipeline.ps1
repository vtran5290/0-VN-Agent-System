Param(
  [Parameter(Mandatory=$false)]
  [string[]]$Symbols
)

$ErrorActionPreference = "Stop"

# Repo root = folder chứa script
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

# Ensure venv
$VenvPy = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$VenvPip = Join-Path $RepoRoot ".venv\Scripts\pip.exe"

if (!(Test-Path $VenvPy)) {
  Write-Host "[run_backtest_pipeline] ERROR: .venv not found at $VenvPy" -ForegroundColor Red
  Write-Host "Create/activate venv first, then install deps:" -ForegroundColor Yellow
  Write-Host "  .\.venv\Scripts\Activate.ps1"
  Write-Host "  pip install -r pp_backtest/requirements.txt"
  exit 1
}

# PYTHONPATH = repo root
$env:PYTHONPATH = $RepoRoot

Write-Host "== Using python ==" -ForegroundColor Cyan
& $VenvPy -c "import sys; print(sys.executable)"

# Optional: ensure deps (comment out if you don't want)
# & $VenvPip install -r (Join-Path $RepoRoot "pp_backtest\requirements.txt") | Out-Null

# 1) Backtest
Write-Host "`n== 1) Backtest ==" -ForegroundColor Cyan
if ($Symbols -and $Symbols.Length -gt 0) {
  & $VenvPy -m pp_backtest.run --symbols @($Symbols)
} else {
  & $VenvPy -m pp_backtest.run
}

# 2) Pivot (tail + MFE)
Write-Host "`n== 2) Pivot (tail + MFE) ==" -ForegroundColor Cyan
$PivotScript = Join-Path $RepoRoot "run_pivot.ps1"
if (!(Test-Path $PivotScript)) {
  Write-Host "[run_backtest_pipeline] ERROR: run_pivot.ps1 not found at $PivotScript" -ForegroundColor Red
  exit 1
}
& $PivotScript --tail -0.05 --mfe --mfe-bars 20

# 3) Publish knowledge
Write-Host "`n== 3) Publish knowledge ==" -ForegroundColor Cyan
$publishArgs = @("--strategy","PP_GIL_V4","--start","2018-01-01","--end","2026-02-21")
if ($Symbols -and $Symbols.Length -gt 0) {
  $publishArgs += @("--symbols") + @($Symbols)
}
& $VenvPy -m pp_backtest.publish_knowledge @publishArgs

# 4) Weekly report
Write-Host "`n== 4) Weekly report ==" -ForegroundColor Cyan
& $VenvPy -m src.report.weekly

# 5) Render weekly note
Write-Host "`n== 5) Render weekly note ==" -ForegroundColor Cyan
& $VenvPy (Join-Path $RepoRoot "knowledge\render_weekly_note.py")

# Print outputs
$ResultsCsv = Join-Path $RepoRoot "pp_backtest\pp_sell_backtest_results.csv"
$LedgerCsv  = Join-Path $RepoRoot "pp_backtest\pp_trade_ledger.csv"
Write-Host "`n== Outputs ==" -ForegroundColor Green
Write-Host "Results CSV: $ResultsCsv"
Write-Host "Ledger CSV:  $LedgerCsv"
Write-Host "Weekly notes: " (Join-Path $RepoRoot "knowledge\weekly_notes")
