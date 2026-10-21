param([double]$Hours = 72, [switch]$Smoke)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $taskRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Run scripts/Setup.ps1 first.' }
$runPath = Join-Path $taskRoot 'runtime\endurance'
New-Item -ItemType Directory -Force -Path $runPath | Out-Null
$pidPath = Join-Path $runPath 'runner.pid'
if (Test-Path -LiteralPath $pidPath) {
  $existingPid = [int](Get-Content -LiteralPath $pidPath)
  if (Get-Process -Id $existingPid -ErrorAction SilentlyContinue) { throw "Endurance process $existingPid is already running." }
}
$runArgs = @('-m', 'siteforge.endurance', '--hours', "$Hours")
if ($Smoke) { $runArgs += @('--cycles', '3', '--interval', '0') }
$process = Start-Process -FilePath $pythonPath -ArgumentList $runArgs -WorkingDirectory $taskRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runPath 'stdout.log') -RedirectStandardError (Join-Path $runPath 'stderr.log') -PassThru
$process.Id | Set-Content -LiteralPath $pidPath
Write-Output "Started PID $($process.Id). Report: $runPath\report.json. 72-hour acceptance stays PENDING until verified."
