$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $taskRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Run scripts/Setup.ps1 first.' }
if (-not (Test-Path -LiteralPath (Join-Path $taskRoot '.env'))) { throw 'Run python -m siteforge.cli init first.' }
$runPath = Join-Path $taskRoot 'runtime'
New-Item -ItemType Directory -Force -Path $runPath | Out-Null
$api = Start-Process -FilePath $pythonPath -ArgumentList @('-m','siteforge.cli','serve') -WorkingDirectory $taskRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runPath 'api-stdout.log') -RedirectStandardError (Join-Path $runPath 'api-stderr.log') -PassThru
$api.Id | Set-Content -LiteralPath (Join-Path $runPath 'api.pid')
Write-Output "Supervisor PID $($api.Id), loopback URL http://127.0.0.1:8080. Owner token is in the ignored .env file."
