param([string]$TaskName = 'SiteForge-Fixture-Endurance')
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $taskRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Run scripts/Setup.ps1 first.' }
$action = New-ScheduledTaskAction -Execute $pythonPath -Argument '-m siteforge.endurance --hours 72' -WorkingDirectory $taskRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Days 5) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description 'SiteForge fixture endurance; no spending, publication or external effects.' -RunLevel Limited | Out-Null
Write-Output "Installed $TaskName for current-user logon. Start-ScheduledTask -TaskName '$TaskName' starts it now."
