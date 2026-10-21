param([switch]$Once)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
if (-not $env:SITEFORGE_WORKER_ID -or -not $env:SITEFORGE_WORKER_TOKEN) {
    throw 'Set SITEFORGE_WORKER_ID and SITEFORGE_WORKER_TOKEN for a short-lived, scoped worker principal first.'
}
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Create the project virtual environment first.' }
Push-Location -LiteralPath $projectRoot
try {
    if ($Once) { & $pythonPath -m siteforge.worker --once }
    else { & $pythonPath -m siteforge.worker }
    if ($LASTEXITCODE -ne 0) { throw "Worker exited with code $LASTEXITCODE" }
} finally { Pop-Location }
