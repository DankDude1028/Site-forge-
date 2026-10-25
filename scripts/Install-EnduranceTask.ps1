param([string]$TaskName = 'SiteForge-Fixture-Endurance', [string]$RunDirectory = 'runtime\endurance')
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
# Windowless interpreter: closing a console window must not end an unattended soak.
$pythonPath = Join-Path $taskRoot '.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Run scripts/Setup.ps1 first.' }
$runPath = [IO.Path]::GetFullPath((Join-Path $taskRoot $RunDirectory)).TrimEnd([IO.Path]::DirectorySeparatorChar,[IO.Path]::AltDirectorySeparatorChar)
if (-not $runPath.StartsWith($taskRoot + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) -or $runPath.Contains('"')) { throw 'Run directory must be a valid path inside this workspace.' }
$runArguments = '-m siteforge.endurance --hours 72 --root "' + $runPath + '"'
$action = New-ScheduledTaskAction -Execute $pythonPath -Argument $runArguments -WorkingDirectory $taskRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Days 5) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description 'SiteForge fixture endurance; no spending, publication or external effects.' -RunLevel Limited | Out-Null
Write-Output "Installed $TaskName for current-user logon. Start-ScheduledTask -TaskName '$TaskName' starts it now."
