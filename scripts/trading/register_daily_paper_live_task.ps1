# Register Windows Scheduled Task: daily paper-live Mon-Fri at 16:30 (trading days)
# Usage:
#   .\scripts\trading\register_daily_paper_live_task.ps1
#   .\scripts\trading\register_daily_paper_live_task.ps1 -Time "16:30"

param(
    [string]$Time = "16:30",
    [string]$TaskName = "VN_Agent_Daily_Paper_Live_1630"
)

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Script = Join-Path $RepoRoot "scripts\trading\daily_paper_live_full_run.ps1"

# Mon(1) through Fri(5) at 16:30 local time
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At $Time
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Script`"" -WorkingDirectory $RepoRoot
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

Write-Host "Scheduled task: $TaskName"
Write-Host "Schedule: Mon-Fri at $Time"
Write-Host "Script: $Script"
Write-Host "Operator prompt: docs/trading/DAILY_PAPER_OPERATOR_PROMPT.md"
Write-Host ""
Write-Host "Manual run:"
Write-Host "  .\scripts\trading\daily_paper_live_full_run.ps1"
