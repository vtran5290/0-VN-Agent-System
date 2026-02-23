# Run pivot_ledger with repo .venv (no activate needed)
# Usage: .\run_pivot.ps1
#        .\run_pivot.ps1 --tail -0.05 --mfe --mfe-bars 20
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Error ".venv not found. Run: python -m venv .venv; .\.venv\Scripts\pip.exe install -r pp_backtest/requirements.txt"
}
$env:PYTHONPATH = $root
& $venvPython -m pp_backtest.pivot_ledger @args
