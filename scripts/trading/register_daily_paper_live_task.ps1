# Register Windows Scheduled Task: daily paper-live Mon-Fri at 16:30 (trading days)

# Usage:

#   .\scripts\trading\register_daily_paper_live_task.ps1

#   .\scripts\trading\register_daily_paper_live_task.ps1 -DisableOld1600



param(

    [string]$Time = "16:30",

    [string]$TaskName = "VN_Agent_Daily_Paper_Live_1630",

    [switch]$DisableOld1600

)



$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

$Script = Join-Path $RepoRoot "scripts\trading\daily_paper_live_full_run.ps1"



$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At $Time

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Script`"" -WorkingDirectory $RepoRoot

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest



Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null



Write-Host "Scheduled task: $TaskName"

Write-Host "Schedule: Mon-Fri at $Time"

Write-Host "Script: $Script"

Write-Host "WorkingDirectory: $RepoRoot"

Write-Host "Run as: $env:USERNAME (interactive, highest)"

Write-Host "Operator prompt: docs/trading/DAILY_PAPER_OPERATOR_PROMPT.md"

Write-Host ""

Write-Host "Manual run:"

Write-Host "  .\scripts\trading\daily_paper_live_full_run.ps1"



function Disable-OldPaperTask {

    param([string]$OldTaskName)

    $q = schtasks /Query /TN $OldTaskName /FO LIST 2>&1

    if ($LASTEXITCODE -ne 0) {

        Write-Host "[old task] $OldTaskName : not found (OK)" -ForegroundColor Yellow

        return

    }

    schtasks /Change /TN $OldTaskName /DISABLE 2>&1 | Out-Null

    if ($LASTEXITCODE -eq 0) {

        Write-Host "[old task] $OldTaskName : DISABLED" -ForegroundColor Green

    } else {

        Write-Host "[old task] $OldTaskName : disable FAILED (exit $LASTEXITCODE)" -ForegroundColor Red

    }

    $verify = schtasks /Query /TN $OldTaskName /V /FO LIST 2>&1 | Select-String "Scheduled Task State"

    if ($verify) { Write-Host "  Verify: $($verify.Line.Trim())" }

}



if ($DisableOld1600) {

    Disable-OldPaperTask -OldTaskName "VN_Agent_Daily_Paper_Live_1600"

} else {

    Write-Host ""

    Write-Host "To disable duplicate 16:00 task:"

    Write-Host "  .\scripts\trading\register_daily_paper_live_task.ps1 -DisableOld1600"

    Write-Host "  schtasks /Query /TN VN_Agent_Daily_Paper_Live_1600 /V /FO LIST"

}


