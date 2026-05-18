# Daily paper-live observation (no real capital, no DSE/DNSE live)
# Usage:
#   .\scripts\trading\daily_paper_live_run.ps1 -Date 2026-05-17 -ScanPath "D:\path\phase36_daily_scan.csv"
param(
    [Parameter(Mandatory = $true)][string]$Date,
    [Parameter(Mandatory = $true)][string]$ScanPath,
    [switch]$IncludeS3Shadow,
    [switch]$Force,
    [switch]$AllowSample,
    [switch]$TestMode
)

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $RepoRoot

$py = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$args = @(
    "-m", "src.trading.cli", "paper-accounts", "run-all",
    "--date", $Date,
    "--scan-path", $ScanPath
)
if ($IncludeS3Shadow) { $args += "--include-s3-shadow" }
if ($Force) { $args += "--force" }
if ($AllowSample) { $args += "--allow-sample" }
if ($TestMode) { $args += "--test-mode" }

& $py @args
exit $LASTEXITCODE
