# Daily Donchian+EMA compact scan (3 slots). From repo root:
#   pwsh  -NoProfile -File scripts/research/daily_slots.ps1 AM_OPEN   # PS7 if installed
#   powershell -NoProfile -File scripts/research/daily_slots.ps1 AM_OPEN  # Windows if no pwsh
# Equivalent: node scripts/research/daily_donchian_ema_slot_scan.mjs --slot=AM_OPEN --pretty
# Or dot-source from repo root: .\scripts\research\daily_slots.ps1 AM_MID
param(
  [Parameter(Mandatory = $true)]
  [ValidateSet("AM_OPEN", "AM_MID", "PM_CLOSE")]
  [string] $Slot
)
$ErrorActionPreference = "Stop"
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $root
node "scripts/research/daily_donchian_ema_slot_scan.mjs" "--slot=$Slot" --pretty
